"""CLI Forge : `python -m forge up|status|version` (FR-008, US-1/2/5)."""
from __future__ import annotations

import argparse
import glob
import os
import sqlite3
import sys
import threading
import time

from . import config as cfgmod
from . import orchestrator


def _summary(ctx):
    c = ctx.findings.counts()
    tp = len(ctx.findings.confirmed_true_positives())
    print("\n" + "=" * 56)
    print(f"  Évaluation terminée — run {os.path.basename(ctx.run_dir)}")
    print("=" * 56)
    print(f"  Findings confirmés (true-positive) : {tp}")
    print(f"  Démontrés en live (exploited)      : {c.get('exploited', 0)}")
    gaps = ctx.db.connect().execute(
        "SELECT COUNT(*) c FROM events WHERE kind='rule_gap'").fetchone()["c"]
    print(f"  Rule-gaps (à généraliser en règle) : {gaps}")
    b = ctx.budget.snapshot()
    print(f"  Dépense / yield                    : ${b['spend_usd']} / {b['trailing_yield']}")
    print(f"  Rapports                           : {os.path.join(ctx.run_dir, 'reports')}")
    print(f"  Carte de flux                      : {os.path.join(ctx.run_dir, 'map', 'data-flow.md')}")
    print("=" * 56)


def cmd_up(args):
    overrides = {}
    if args.source:
        overrides["target.source"] = args.source
    if args.provider:
        overrides["llm.provider"] = args.provider
        overrides["llm.model"] = args.model or args.provider
    if args.backend:
        overrides["detection.rule_backend"] = args.backend
    if args.no_testbed:
        overrides["testbed.enabled"] = False
    yaml_path = args.config or os.path.join(cfgmod.REPO_ROOT, "forge.yaml")
    cfg = cfgmod.load(yaml_path if os.path.exists(yaml_path) else None, **overrides)

    print(f"[forge] cible : {cfg['target']['source']}")
    print(f"[forge] provider : {cfg['llm']['provider']} · règles : {cfg['detection']['rule_backend']}")

    if args.dashboard:
        from .dashboard import serve
        t = threading.Thread(target=orchestrator.run, args=(cfg,),
                             kwargs={"max_seconds": args.max_seconds}, daemon=True)
        t.start()
        while orchestrator.ACTIVE is None:
            time.sleep(0.05)
        host, port = cfg["dashboard"]["host"], args.port or cfg["dashboard"]["port"]
        print(f"[forge] dashboard : http://{host}:{port}  (Ctrl-C pour quitter)")
        try:
            serve(orchestrator.ACTIVE, host=host, port=port, block=True)
        except KeyboardInterrupt:
            print("\n[forge] arrêt du dashboard.")
    else:
        ctx = orchestrator.run(cfg, max_seconds=args.max_seconds)
        _summary(ctx)


def cmd_status(args):
    runs = sorted(glob.glob(os.path.join(cfgmod.REPO_ROOT, "runs", "*", "forge.db")))
    if not runs:
        print("Aucun run trouvé. Lancez : python -m forge up")
        return
    db = sqlite3.connect(runs[-1]); db.row_factory = sqlite3.Row
    print(f"Run : {os.path.basename(os.path.dirname(runs[-1]))}")
    print("\nAgents :")
    for r in db.execute("SELECT role, instance_idx, status, current_claim FROM agents ORDER BY role"):
        print(f"  {r['role']}-{r['instance_idx']:<2} {r['status']:<8} {r['current_claim'] or ''}")
    fc = {r["state"]: r["c"] for r in db.execute("SELECT state,COUNT(*) c FROM findings GROUP BY state")}
    ex = db.execute("SELECT COUNT(*) c FROM findings WHERE exploited=1").fetchone()["c"]
    print(f"\nFindings : {fc}  | exploités : {ex}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="forge", description="Forge — évaluation de sécurité agentique")
    sub = p.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("up", help="lancer une évaluation")
    up.add_argument("--config"); up.add_argument("--source")
    up.add_argument("--provider", choices=["deterministic", "anthropic"])
    up.add_argument("--model"); up.add_argument("--backend", choices=["exhaustive", "vector"])
    up.add_argument("--dashboard", action="store_true", help="servir le dashboard temps réel")
    up.add_argument("--port", type=int); up.add_argument("--no-testbed", action="store_true")
    up.add_argument("--max-seconds", type=float, default=120.0)
    up.set_defaults(func=cmd_up)
    st = sub.add_parser("status", help="état du dernier run"); st.set_defaults(func=cmd_status)
    ver = sub.add_parser("version"); ver.set_defaults(func=lambda a: print("Forge 0.1.0"))
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
