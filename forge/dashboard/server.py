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

from ..protocol import protocol as _protocol
from ..tools import catalog as tool_catalog
from ..tools import functions as tool_functions
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
    findings = [_finding_dict(ctx, r)
                for r in db.execute("SELECT * FROM findings ORDER BY updated_ts DESC").fetchall()]
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
        "verdicts": _verdict_counts(db),
        "sources": _all_sources(ctx),
        "tools": tool_catalog(),
        "tool_functions": tool_functions(),
        "tasks_list": _tasks_list(db),
        "protocol": _protocol(),
        **_funnel_and_priority(findings),
    }


def _tasks_list(db) -> list[dict]:
    """File de tâches : faites (closed), en cours (claimed), à venir (open), bloquées."""
    rows = db.execute(
        "SELECT task_id, title, role, state, claimed_by, priority FROM tasks "
        "ORDER BY CASE state WHEN 'claimed' THEN 0 WHEN 'open' THEN 1 WHEN 'blocked' THEN 2 "
        "ELSE 3 END, priority, created_ts").fetchall()
    return [{"id": r["task_id"], "title": r["title"], "role": r["role"], "state": r["state"],
             "by": r["claimed_by"], "priority": r["priority"]} for r in rows]


SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _funnel_and_priority(findings) -> dict:
    """Entonnoir (détectés→confirmés→distincts→exploités) + sortie dédupliquée et priorisée."""
    vc = {}
    for f in findings:
        vc[f["verdict"]] = vc.get(f["verdict"], 0) + 1
    tps = [f for f in findings if f["verdict"] == "true-positive"]

    # Déduplication par localisation (file, symbol) : la fédération de règles peut flaguer
    # deux fois la même faiblesse (ex. CWE-327 générique + CWE-916 spécialisée).
    groups: dict = {}
    for f in tps:
        key = f"{f['file']}::{f['symbol']}"
        g = groups.setdefault(key, {"file": f["file"], "symbol": f["symbol"],
                                    "cwes": set(), "rules": set(), "fps": [],
                                    "exploited": False, "severity": "low", "title": f["title"]})
        g["cwes"].add(f["cwe"])
        if f.get("rule_id"):
            g["rules"].add(f["rule_id"])
        g["fps"].append(f["fp"])
        g["exploited"] = g["exploited"] or f["exploited"]
        if SEV_RANK.get(f["severity"], 3) < SEV_RANK.get(g["severity"], 3):
            g["severity"] = f["severity"]

    priority = [{"file": g["file"], "symbol": g["symbol"], "cwes": sorted(g["cwes"]),
                 "rules": sorted(g["rules"]), "fps": g["fps"], "exploited": g["exploited"],
                 "severity": g["severity"], "title": g["title"], "dup": len(g["fps"]) > 1}
                for g in groups.values()]
    # priorisation : exploités d'abord, puis par sévérité, puis par classe
    priority.sort(key=lambda x: (0 if x["exploited"] else 1, SEV_RANK.get(x["severity"], 3),
                                 x["cwes"][0] if x["cwes"] else ""))
    return {
        "funnel": {
            "detected": len(findings),
            "true_positive": len(tps),
            "distinct": len(groups),
            "duplicates": len(tps) - len(groups),
            "exploited": sum(1 for g in priority if g["exploited"]),
            "false_positive": vc.get("false-positive", 0),
            "not_applicable": vc.get("not-applicable", 0),
            "needs_review": vc.get("needs-review", 0),
        },
        "priority": priority,
    }


def _verdict_counts(db) -> dict:
    return {r["verdict"]: r["c"] for r in db.execute(
        "SELECT verdict, COUNT(*) c FROM findings WHERE verdict IS NOT NULL GROUP BY verdict")}


def _finding_source(ctx, file, symbol):
    """Code incriminé : corps de la fonction, ou ligne pertinente pour secret/dépendance."""
    if ctx.index:
        for fi in ctx.index.find_symbol(symbol):
            if fi.file == file:
                return fi.source, fi.line_start
    import os
    path = os.path.join(ctx.config["target"]["source"], file)
    try:
        lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    except OSError:
        return "", 0
    key = symbol.split("==")[0]
    for i, ln in enumerate(lines):
        if key and key in ln:
            lo, hi = max(0, i - 1), min(len(lines), i + 2)
            return "\n".join(lines[lo:hi]), lo + 1
    return "", 0


def _finding_dict(ctx, r) -> dict:
    import json
    import os
    ev = json.loads(r["evidence"]) if r["evidence"] else {}
    src, line_start = _finding_source(ctx, r["file"], r["symbol"])
    tech = r["technique"] or ""
    rule_id = tech.split("rule:")[1] if tech.startswith("rule:") else None
    remediation = ""
    if rule_id and rule_id in ctx.rulestore.rules:
        remediation = ctx.rulestore.rules[rule_id].body[:1400]
    # Code d'exploitation généré + exécuté (Validator) + trace d'exécution.
    exploit_code, exploit = "", {}
    poc = r["poc_path"]
    if poc and os.path.exists(poc):
        try:
            exploit_code = open(poc, encoding="utf-8", errors="ignore").read()
        except OSError:
            pass
        tj = (poc[:-3] if poc.endswith(".py") else poc) + ".json"
        if os.path.exists(tj):
            try:
                exploit = json.load(open(tj, encoding="utf-8"))
            except (OSError, ValueError):
                pass
    return {
        "exploit_code": exploit_code, "exploit": exploit,
        "fp": r["fingerprint"], "file": r["file"], "symbol": r["symbol"], "cwe": r["cwe"],
        "vuln_class": r["vuln_class"], "state": r["state"], "verdict": r["verdict"],
        "exploited": bool(r["exploited"]), "severity": r["severity"], "technique": tech,
        "title": r["title"], "description": r["description"], "owasp": r["owasp"],
        "source": src, "line_start": line_start, "rule_id": rule_id,
        "remediation": remediation, "evidence": ev,
    }


def _all_sources(ctx) -> dict:
    """Tout le code source évalué (la cible est petite) pour le panneau 'Code source'."""
    import os
    root = ctx.config["target"]["source"]
    out = {}
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv")]
        for fn in files:
            if fn.endswith(".py"):
                rel = os.path.relpath(os.path.join(dp, fn), root)
                try:
                    out[rel] = open(os.path.join(dp, fn), encoding="utf-8", errors="ignore").read()
                except OSError:
                    pass
    return out


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
