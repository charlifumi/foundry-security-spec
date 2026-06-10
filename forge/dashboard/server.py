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
    }


def _last_seq(db):
    r = db.execute("SELECT COALESCE(MAX(seq),0) s FROM events").fetchone()
    return r["s"]


def _state(db, key):
    r = db.execute("SELECT value FROM run_state WHERE key=?", (key,)).fetchone()
    return r["value"] if r else None


def serve(ctx, host="127.0.0.1", port=8000, *, block=True):
    snap_holder = {"ctx": ctx}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/api/state"):
                body = json.dumps(build_snapshot(snap_holder["ctx"])).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    srv = ThreadingHTTPServer((host, port), Handler)
    if block:
        srv.serve_forever()
    return srv
