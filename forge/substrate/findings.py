"""Finding store : cycle de vie, fingerprint stable, dédup (FR-085..091).

Fingerprint = sha256(path|symbol|class), SANS numéro de ligne ni snippet
(Constitution VIII : stable sous édition).
"""
from __future__ import annotations

import hashlib
import json
import time

from .db import DB
from .events import EventLog

VERDICTS = {"true-positive", "false-positive", "needs-review", "not-applicable", "code-quality"}


def fingerprint(file: str, symbol: str, vuln_class: str) -> str:
    norm = f"{file.strip()}|{symbol.strip()}|{vuln_class.strip()}"
    return hashlib.sha256(norm.encode()).hexdigest()[:24]


class FindingStore:
    def __init__(self, db: DB, events: EventLog):
        self.db = db
        self.events = events

    def add_candidate(self, *, file: str, symbol: str, vuln_class: str, title: str,
                      technique: str, description: str) -> str:
        """Écrit un candidat ; dédup par fingerprint (FR-045). Retourne le fingerprint."""
        fp = fingerprint(file, symbol, vuln_class)
        now = time.time()
        cur = self.db.connect().execute(
            "INSERT OR IGNORE INTO findings(fingerprint, file, symbol, vuln_class, title, "
            "state, technique, description, created_ts, updated_ts) "
            "VALUES (?,?,?,?,?, 'candidate', ?, ?, ?, ?)",
            (fp, file, symbol, vuln_class, title, technique, description, now, now),
        )
        if cur.rowcount == 1:
            self.events.emit("candidate", finding=fp, file=file, symbol=symbol,
                             vuln_class=vuln_class, technique=technique)
        return fp

    def set_verdict(self, fp: str, verdict: str, evidence: dict, *,
                    severity: str | None = None, cvss: float | None = None,
                    cwe: str | None = None, owasp: str | None = None):
        """Pose le verdict + le rapport d'investigation (FR-054 : rejet si pas de raisonnement)."""
        assert verdict in VERDICTS, f"verdict invalide: {verdict}"
        if not evidence:
            raise ValueError("un verdict exige un rapport d'investigation (FR-054)")
        state = "confirmed" if verdict == "true-positive" else "verdict_assigned"
        self.db.connect().execute(
            "UPDATE findings SET verdict=?, evidence=?, state=?, severity=?, cvss=?, cwe=?, "
            "owasp=?, updated_ts=? WHERE fingerprint=?",
            (verdict, json.dumps(evidence), state, severity, cvss, cwe, owasp, time.time(), fp),
        )
        self.events.emit("verdict", finding=fp, verdict=verdict, severity=severity)

    def set_exploited(self, fp: str, poc_path: str | None):
        """Pose le flag exploited (Validator uniquement, FR-089)."""
        self.db.connect().execute(
            "UPDATE findings SET exploited=1, poc_path=?, updated_ts=? WHERE fingerprint=?",
            (poc_path, time.time(), fp),
        )
        self.events.emit("exploited", finding=fp, poc=poc_path)

    def publish(self, fp: str):
        self.db.connect().execute(
            "UPDATE findings SET state='published', updated_ts=? WHERE fingerprint=?",
            (time.time(), fp),
        )
        self.events.emit("published", finding=fp)

    def get(self, fp: str) -> dict | None:
        r = self.db.connect().execute("SELECT * FROM findings WHERE fingerprint=?", (fp,)).fetchone()
        return dict(r) if r else None

    def by_state(self, state: str) -> list[dict]:
        rows = self.db.connect().execute(
            "SELECT * FROM findings WHERE state=? ORDER BY created_ts", (state,)
        ).fetchall()
        return [dict(r) for r in rows]

    def confirmed_true_positives(self) -> list[dict]:
        rows = self.db.connect().execute(
            "SELECT * FROM findings WHERE verdict='true-positive' ORDER BY created_ts"
        ).fetchall()
        return [dict(r) for r in rows]

    def counts(self) -> dict:
        rows = self.db.connect().execute(
            "SELECT state, COUNT(*) c FROM findings GROUP BY state"
        ).fetchall()
        d = {r["state"]: r["c"] for r in rows}
        ver = self.db.connect().execute(
            "SELECT verdict, COUNT(*) c FROM findings WHERE verdict IS NOT NULL GROUP BY verdict"
        ).fetchall()
        d["verdicts"] = {r["verdict"]: r["c"] for r in ver}
        r = self.db.connect().execute("SELECT COUNT(*) c FROM findings WHERE exploited=1").fetchone()
        d["exploited"] = r["c"]
        return d
