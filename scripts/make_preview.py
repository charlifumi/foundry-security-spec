"""Génère docs/dashboard-preview.html : la vue pipeline (N8N) avec les données d'un vrai
run figées, ouvrable sans rien lancer.

Lancer :  python -m scripts.make_preview   (ou : python scripts/make_preview.py)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forge import config, orchestrator                      # noqa: E402
from forge.dashboard.flow import PAGE_FLOW                   # noqa: E402
from forge.dashboard.server import build_snapshot           # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ctx = orchestrator.run(config.load(), max_seconds=90)
    snap = build_snapshot(ctx)
    snap["mode"] = "live"
    # IMPORTANT : échapper "</" pour qu'un "</script>" présent dans le code cible
    # (ex. payload XSS de démo) ne referme pas la balise <script> inline.
    js = json.dumps(snap).replace("</", "<\\/")
    inject = ("<script>window.__SNAP__=" + js +
              ";window.fetch=async(u,o)=>({json:async()=>window.__SNAP__});</script>")
    html = PAGE_FLOW.replace("</head>", inject + "</head>")
    out = os.path.join(REPO, "docs", "dashboard-preview.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    tp = sum(1 for f in snap["findings"] if f["verdict"] == "true-positive")
    print(f"écrit {out} ({len(html)} octets) — {tp} TP, verdicts {snap['verdicts']}")


if __name__ == "__main__":
    main()
