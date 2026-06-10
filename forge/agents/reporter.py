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


SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def write_rollup(ctx):
    """Rollup priorisé par exploitation réelle + dédupliqué par localisation (FR-081/082).

    Sortie en deux tiers : (1) prouvés en live (exploited), (2) confirmés non démontrés.
    Les findings sur une même (file, symbol) — ex. règle générique + règle spécialisée
    fédérée — sont fusionnés en une entrée citant toutes les classes/règles.
    """
    tps = ctx.findings.confirmed_true_positives()
    rep_dir = os.path.join(ctx.run_dir, "reports")
    os.makedirs(rep_dir, exist_ok=True)

    groups = {}
    for f in tps:
        g = groups.setdefault((f["file"], f["symbol"]),
                              {"file": f["file"], "symbol": f["symbol"], "cwes": set(),
                               "exploited": False, "severity": "low", "title": f["title"]})
        g["cwes"].add(f["cwe"])
        g["exploited"] = g["exploited"] or bool(f["exploited"])
        if SEV_ORDER.get(f["severity"], 3) < SEV_ORDER.get(g["severity"], 3):
            g["severity"] = f["severity"]
    distinct = list(groups.values())
    proven = sorted([g for g in distinct if g["exploited"]], key=lambda x: SEV_ORDER.get(x["severity"], 9))
    confirmed = sorted([g for g in distinct if not g["exploited"]], key=lambda x: SEV_ORDER.get(x["severity"], 9))

    def line(g):
        cwes = "/".join(sorted(g["cwes"]))
        dup = f" _(détecté par {len(g['cwes'])} règles)_" if len(g["cwes"]) > 1 else ""
        return f"- **[{g['severity']}]** {cwes} — {g['title']} (`{g['file']}:{g['symbol']}`){dup}"

    lines = [
        "# Rollup d'évaluation Forge — sortie priorisée", "",
        f"- Candidats détectés : **{len(tps) + _other(ctx)}** (voir l'entonnoir ci-dessous)",
        f"- Confirmés `true-positive` : **{len(tps)}** → **{len(distinct)} distincts** "
        f"après déduplication ({len(tps) - len(distinct)} doublons inter-règles)",
        f"- **Prouvés en live (`exploited`) : {len(proven)}**", "",
        "## ⚡ Tier 1 — Vulnérabilités PROUVÉES (exploitées en live, prioritaires)", "",
    ]
    lines += [line(g) for g in proven] or ["_(aucune)_"]
    lines += ["", "## ✓ Tier 2 — Vulnérabilités CONFIRMÉES (réelles, non démontrées en live)", "",
              "_Secrets, crypto faible, dépendances : « la présence est la vuln » — réelles mais "
              "non exploitables par une requête sur le testbed._", ""]
    lines += [line(g) for g in confirmed] or ["_(aucune)_"]

    fn = ctx.db.connect().execute("SELECT value FROM run_state WHERE key='index_functions'").fetchone()
    cov = ctx.db.connect().execute("SELECT component, goal, state FROM coverage").fetchall()
    lines += ["", "## Entonnoir de pertinence", "",
              "| Étape | Compte |", "|---|---|",
              f"| Candidats détectés | {len(tps) + _other(ctx)} |",
              f"| Confirmés (true-positive) | {len(tps)} |",
              f"| Distincts (après dédup) | {len(distinct)} |",
              f"| Prouvés en live (exploited) | {len(proven)} |", ""]
    if cov:
        lines += ["## Couverture", ""]
        lines += [f"- {'✅' if r['state']=='covered' else '⬜'} {r['component']} × {r['goal']}" for r in cov]
    with open(os.path.join(rep_dir, "ROLLUP.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    ctx.events.emit("rollup", findings=len(tps), distinct=len(distinct), exploited=len(proven))


def _other(ctx):
    """Candidats écartés (FP/NA/NR) — pour l'entonnoir."""
    r = ctx.db.connect().execute(
        "SELECT COUNT(*) c FROM findings WHERE verdict IN "
        "('false-positive','not-applicable','needs-review')").fetchone()
    return r["c"]
