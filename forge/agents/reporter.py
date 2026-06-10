"""Reporter — sortie humaine : un rapport par TP + rollup (FR-075..084)."""
from __future__ import annotations

import json
import os


def handle(task, ctx, agent_id) -> list:
    fp = task["payload"]["fp"]
    f = ctx.findings.get(fp)
    if not f or f["verdict"] != "true-positive":
        return []
    ctx.llm.complete(role="reporter", instance=agent_id, correlation_id=fp,
                     prompt=f"Rédige le rapport de {fp}.", system="Rédacteur de findings.")
    rep_dir = os.path.join(ctx.run_dir, "reports")
    os.makedirs(rep_dir, exist_ok=True)
    ev = json.loads(f["evidence"])
    exploited = "✅ oui" if f["exploited"] else "non"
    lines = [
        f"# {f['title']}",
        "",
        f"| Champ | Valeur |",
        f"|---|---|",
        f"| Composant | `{f['file']}` |",
        f"| Localisation | `{f['file']}:{f['symbol']}` |",
        f"| Classe | {f['cwe']} |",
        f"| OWASP | {f['owasp']} |",
        f"| Sévérité | {f['severity']} (CVSS {f['cvss']}) |",
        f"| Exploité (live) | {exploited} |",
        f"| Technique de détection | {f['technique']} |",
        "",
        "## Preuve (evidence gate — 3 jambes)",
        f"- **Atteignabilité** : `{ev['reachability'].get('file','')}:{ev['reachability'].get('symbol','')}` — {ev['reachability'].get('note','')}",
        f"- **Frontière de confiance** : {ev['trust_boundary'].get('note','')}",
        f"- **Impact** : `{ev['impact'].get('file','')}:{ev['impact'].get('symbol','')}` — {ev['impact'].get('note','')}",
        "",
    ]
    if f["poc_path"] and os.path.exists(f["poc_path"]):
        lines += ["## Proof-of-concept", "Voir : `" + os.path.relpath(f["poc_path"], ctx.run_dir) + "`",
                  "```", open(f["poc_path"], encoding="utf-8").read().strip(), "```", ""]
    with open(os.path.join(rep_dir, f"{fp}.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    ctx.findings.publish(fp)
    return []


def write_rollup(ctx):
    """Rollup d'évaluation (FR-081) : groupé par composant, compté par sévérité × exploited."""
    tps = ctx.findings.confirmed_true_positives()
    rep_dir = os.path.join(ctx.run_dir, "reports")
    os.makedirs(rep_dir, exist_ok=True)
    by_comp = {}
    for f in tps:
        by_comp.setdefault(f["file"], []).append(f)
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    n_expl = sum(1 for f in tps if f["exploited"])
    lines = [
        "# Rollup d'évaluation Forge", "",
        f"- Findings confirmés (`true-positive`) : **{len(tps)}**",
        f"- Démontrés en live (`exploited`) : **{n_expl}**", "",
        "## Par composant", "",
    ]
    for comp in sorted(by_comp):
        lines.append(f"### `{comp}`")
        for f in sorted(by_comp[comp], key=lambda x: sev_order.get(x["severity"], 9)):
            tag = " ⚡exploité" if f["exploited"] else ""
            lines.append(f"- [{f['severity']}] {f['cwe']} — {f['title']} (`{f['symbol']}`){tag}")
        lines.append("")
    # couverture par goal
    cov = ctx.db.connect().execute("SELECT component, goal, state FROM coverage").fetchall()
    if cov:
        lines += ["## Couverture", ""]
        for r in cov:
            mark = "✅" if r["state"] == "covered" else "⬜"
            lines.append(f"- {mark} {r['component']} × {r['goal']}")
    with open(os.path.join(rep_dir, "ROLLUP.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    ctx.events.emit("rollup", findings=len(tps), exploited=n_expl)
