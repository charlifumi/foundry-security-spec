"""Budget governor : comptabilité LLM, coût, yield glissant, conditions de halt.

Réalise FR-112..117 et cost-and-routing.md. Le yield est pondéré par sévérité
(échelle géométrique) et par le flag exploited (×2).
"""
from __future__ import annotations

import json
import time
import uuid

from .db import DB
from .events import EventLog

# Poids de sévérité géométriques (~3.16× par tier) — FR-117.
SEVERITY_WEIGHTS = {"critical": 31.6, "high": 10.0, "medium": 3.16, "low": 1.0}
EXPLOITED_MULTIPLIER = 2.0


class Budget:
    def __init__(self, db: DB, events: EventLog, *, spend_cap_usd: float | None = None,
                 time_cap_min: float | None = None, yield_threshold: float = 0.5,
                 window_usd: float = 10.0, min_runtime_min: float = 0.0):
        self.db = db
        self.events = events
        self.spend_cap_usd = spend_cap_usd
        self.time_cap_min = time_cap_min
        self.yield_threshold = yield_threshold
        self.window_usd = window_usd
        self.min_runtime_min = min_runtime_min
        self.start_ts = time.time()

    def record_call(self, *, role: str, instance: str, model: str, provider: str,
                    input_tokens: int, output_tokens: int, cost_usd: float,
                    estimated: bool, correlation_id: str | None = None):
        self.db.connect().execute(
            "INSERT INTO llm_calls(call_id, role, instance, correlation_id, model, provider, "
            "input_tokens, output_tokens, cost_usd, cost_estimated, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f"call-{uuid.uuid4().hex[:12]}", role, instance, correlation_id, model, provider,
             input_tokens, output_tokens, cost_usd, int(estimated), time.time()),
        )

    def total_spend(self) -> float:
        r = self.db.connect().execute("SELECT COALESCE(SUM(cost_usd),0) s FROM llm_calls").fetchone()
        return r["s"]

    def runtime_min(self) -> float:
        return (time.time() - self.start_ts) / 60.0

    def spend_by_role(self) -> dict:
        rows = self.db.connect().execute(
            "SELECT role, COALESCE(SUM(cost_usd),0) s FROM llm_calls GROUP BY role"
        ).fetchall()
        return {r["role"]: round(r["s"], 4) for r in rows}

    def estimated_fraction(self) -> float:
        r = self.db.connect().execute(
            "SELECT COALESCE(SUM(cost_usd),0) t, "
            "COALESCE(SUM(CASE WHEN cost_estimated=1 THEN cost_usd ELSE 0 END),0) e FROM llm_calls"
        ).fetchone()
        return (r["e"] / r["t"]) if r["t"] else 0.0

    def trailing_yield(self) -> float:
        """Yield glissant sur la fenêtre de dépense (FR-115)."""
        spend = self.total_spend()
        if spend <= 0:
            # Sans dépense (mode déterministe/local marginal), on mesure le yield par finding.
            spend = max(1e-6, spend)
        rows = self.db.connect().execute(
            "SELECT severity, exploited FROM findings WHERE verdict='true-positive'"
        ).fetchall()
        score = 0.0
        for r in rows:
            w = SEVERITY_WEIGHTS.get((r["severity"] or "low"), 1.0)
            if r["exploited"]:
                w *= EXPLOITED_MULTIPLIER
            score += w
        return score / max(self.window_usd, spend)

    def caps_exceeded(self) -> str | None:
        if self.spend_cap_usd is not None and self.total_spend() >= self.spend_cap_usd:
            return f"spend cap atteint ({self.total_spend():.2f} ≥ {self.spend_cap_usd} $)"
        if self.time_cap_min is not None and self.runtime_min() >= self.time_cap_min:
            return f"time cap atteint ({self.runtime_min():.1f} ≥ {self.time_cap_min} min)"
        return None

    def should_halt(self, coverage_complete: bool) -> str | None:
        """Halt si cap dur, OU (couverture ∧ yield-bas ∧ runtime-min) — FR-116, Constitution VI."""
        cap = self.caps_exceeded()
        if cap:
            return cap
        if not coverage_complete:
            return None  # jamais d'auto-stop yield avant couverture (Constitution VI)
        if self.runtime_min() < self.min_runtime_min:
            return None
        if self.trailing_yield() < self.yield_threshold:
            return (f"couverture complète + yield bas "
                    f"({self.trailing_yield():.2f} < {self.yield_threshold})")
        return None

    def snapshot(self) -> dict:
        return {
            "spend_usd": round(self.total_spend(), 4),
            "spend_cap_usd": self.spend_cap_usd,
            "runtime_min": round(self.runtime_min(), 2),
            "time_cap_min": self.time_cap_min,
            "trailing_yield": round(self.trailing_yield(), 3),
            "yield_threshold": self.yield_threshold,
            "spend_by_role": self.spend_by_role(),
            "estimated_fraction": round(self.estimated_fraction(), 3),
        }
