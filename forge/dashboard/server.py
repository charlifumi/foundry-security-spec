"""Serveur de dashboard (stdlib) : sert une SPA + un endpoint JSON /api/state.

La SPA interroge /api/state toutes les secondes et anime : le fleet (chaque agent
vivant + son claim), le pipeline des findings, la **cartographie** (chaînes d'appel
entrée→sink + validation), la couverture et le budget. Même source que `forge status`
(SC-008).
"""
from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .flow import PAGE_FLOW
from .page import PAGE


def build_snapshot(ctx) -> dict:
    db = ctx.db.connect()
    now = time.time()
    agents = [
        {"id": r["agent_id"], "role": r["role"], "status": r["status"],
         "claim": r["current_claim"], "hb_age": round(now - r["last_heartbeat"], 1)}
        for r in db.execute("SELECT * FROM agents ORDER BY role, instance_idx").fetchall()
    ]
    findings = [
        {"fp": r["fingerprint"], "file": r["file"], "symbol": r["symbol"], "cwe": r["cwe"],
         "vuln_class": r["vuln_class"], "state": r["state"], "verdict": r["verdict"],
         "exploited": bool(r["exploited"]), "severity": r["severity"], "technique": r["technique"],
         "title": r["title"]}
        for r in db.execute("SELECT * FROM findings ORDER BY updated_ts DESC").fetchall()
    ]
    coverage = [
        {"component": r["component"], "state": r["state"]}
        for r in db.execute("SELECT * FROM coverage ORDER BY component").fetchall()
    ]
    tasks = {r["state"]: r["c"] for r in
             db.execute("SELECT state, COUNT(*) c FROM tasks GROUP BY state").fetchall()}
    flows = ctx.security_map.get("flows", []) if ctx.security_map else []
    events = ctx.events.since(max(0, _last_seq(db) - 30))
    rule_gaps = db.execute("SELECT COUNT(*) c FROM events WHERE kind='rule_gap'").fetchone()["c"]
    role_stats = _role_stats(ctx, db)
    return {
        "run_dir": ctx.run_dir.split("/")[-1],
        "coverage_complete": ctx.coverage_complete.is_set(),
        "agents": agents, "findings": findings, "coverage": coverage, "tasks": tasks,
        "flows": [{"entry": f["entry"], "file": f["file"],
                   "chain": [str(x) for x in f["chain"]], "validated": f["validated"]}
                  for f in flows],
        "budget": ctx.budget.snapshot(),
        "rule_gaps": rule_gaps,
        "index": {"functions": _state(db, "index_functions")},
        "corpora": ctx.rulestore.sources(),
        "events": events[-30:],
        "role_stats": role_stats,
    }


def _role_stats(ctx, db) -> dict:
    """Par rôle : instances vivantes/configurées + consommation de tokens (FR-113)."""
    fleet = ctx.config.get("fleet", {})

    def conf(v):
        return v.get("instances", 0) if isinstance(v, dict) else int(v)

    alive = {r["role"]: r["c"] for r in
             db.execute("SELECT role, COUNT(*) c FROM agents WHERE status='alive' GROUP BY role")}
    toks = {r["role"]: {"calls": r["c"], "in_tok": r["it"], "out_tok": r["ot"], "cost": round(r["co"], 4)}
            for r in db.execute(
                "SELECT role, COUNT(*) c, COALESCE(SUM(input_tokens),0) it, "
                "COALESCE(SUM(output_tokens),0) ot, COALESCE(SUM(cost_usd),0) co "
                "FROM llm_calls GROUP BY role")}
    roles = set(list(alive) + list(toks) + [k for k in fleet])
    out = {}
    for r in roles:
        t = toks.get(r, {"calls": 0, "in_tok": 0, "out_tok": 0, "cost": 0.0})
        out[r] = {"alive": alive.get(r, 0), "configured": conf(fleet.get(r, 0)), **t}
    return out


def _last_seq(db):
    r = db.execute("SELECT COALESCE(MAX(seq),0) s FROM events").fetchone()
    return r["s"]


def _state(db, key):
    r = db.execute("SELECT value FROM run_state WHERE key=?", (key,)).fetchone()
    return r["value"] if r else None


class LiveController:
    """Mode live : le pipeline tourne en fond, le dashboard observe (step/reset = no-op)."""
    mode = "live"

    def __init__(self, ctx):
        self.ctx = ctx

    def snapshot(self):
        s = build_snapshot(self.ctx)
        s["mode"] = "live"
        return s

    def step(self):
        return self.snapshot()

    def reset(self):
        return self.snapshot()


def serve(controller, host="127.0.0.1", port=8000, *, block=True):
    # rétro-compat : on accepte aussi un ctx brut.
    if not hasattr(controller, "snapshot"):
        controller = LiveController(controller)

    def _json(handler, obj):
        body = json.dumps(obj).encode()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def _html(handler, page):
        body = page.encode()
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/api/state"):
                _json(self, controller.snapshot())
            elif self.path.startswith("/panels"):
                _html(self, PAGE)
            else:
                _html(self, PAGE_FLOW)

        def do_POST(self):
            if self.path.startswith("/api/step"):
                _json(self, controller.step())
            elif self.path.startswith("/api/reset"):
                _json(self, controller.reset())
            else:
                self.send_response(404)
                self.end_headers()

    srv = ThreadingHTTPServer((host, port), Handler)
    if block:
        srv.serve_forever()
    return srv
