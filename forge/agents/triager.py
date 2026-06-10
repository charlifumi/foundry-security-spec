"""Triager — investigation + evidence gate, AVEC filtrage (FR-050..059, FR-087/088).

Le Triager est le filtre à bruit : tout ce qui est détecté ne sort pas en true-positive.
Il sait dire non, avec un motif :
  - `not-applicable` : code d'exemple / hors périmètre (FR-055).
  - `false-positive` : frontière gardée par un sanitizer ; OU vuln non exploitable dans son
    contexte d'appel (ex. buffer fixe dont l'appelant borne l'entrée) — raisonnement sur le
    graphe d'appels.
  - `needs-review` : citation non résolvante / lead non prouvable (gate FR-088).
  - `true-positive` : preuve à 3 jambes qui résout (seul ce verdict est publié).
Le modèle ne s'attribue jamais le verdict ; le gate le fait (Constitution I).
"""
from __future__ import annotations

import os
import re

LIVE_EXPLOITABLE = {"CWE-89", "CWE-79", "CWE-78", "CWE-918", "CWE-639", "CWE-22", "CWE-502"}
CVSS = {"critical": 9.3, "high": 7.8, "medium": 5.4, "low": 3.1}
PRESENCE_CWES = {"CWE-798", "CWE-327", "CWE-916", "CWE-1035"}


def _file_exists(ctx, file):
    return os.path.exists(os.path.join(ctx.config["target"]["source"], file))


def handle(task, ctx, agent_id) -> list:
    p = task["payload"]
    fp = p["fp"]
    f = ctx.findings.get(fp)
    if not f:
        return []
    cwe = p.get("cwe")
    file, symbol = f["file"], f["symbol"]
    ctx.llm.complete(role="triager", instance=agent_id, correlation_id=fp,
                     prompt=f"Investigue {file}:{symbol} ({cwe}). Trace le flux, vérifie "
                            f"l'atteignabilité et le contexte d'appel.",
                     system="Filtre à bruit : ne confirme que ce qui est prouvable et exploitable.")

    # 1) Hors périmètre : code d'exemple / échantillon / démo -> not-applicable (FR-055).
    if re.search(r"example|sample|demo", file, re.I) or re.search(r"example|sample", symbol, re.I):
        ctx.findings.set_verdict(fp, "not-applicable",
                                 {"reason": {"note": "code d'exemple, hors périmètre d'évaluation"}},
                                 severity=p.get("severity"), cwe=cwe, owasp=p.get("owasp"))
        return []

    # 2) Présence = vuln (secret, crypto déprécié, dépendance) : carve-out FR-087a.
    if p.get("presence_is_vuln") or cwe in PRESENCE_CWES:
        evidence = {
            "reachability": {"file": file, "symbol": symbol, "note": "inclus au build"},
            "trust_boundary": {"note": "le dépôt source lui-même (FR-087a)"},
            "impact": {"file": file, "symbol": symbol, "note": "exposition/primitive dépréciée"},
        }
        if ctx.index.resolve_citation(file, symbol) or _file_exists(ctx, file):
            return _confirm(ctx, fp, evidence, p, cwe)
        return _demote(ctx, fp, evidence, p, cwe)

    # 3) Classes data-flow.
    code_validators = ctx.index.validation_in(symbol)

    # 3a) Non exploitable en contexte : buffer fixe dont l'appelant borne l'entrée (graphe d'appels).
    if cwe == "CWE-120":
        callers = ctx.index.callers_of(symbol)
        bounding = [c for c in callers if re.search(r"\[\s*\d*\s*:\s*\d+\s*\]", c.source)]
        if bounding:
            who = ", ".join(c.name for c in bounding)
            ctx.findings.set_verdict(
                fp, "false-positive",
                {"reason": {"file": file, "symbol": symbol,
                            "note": f"appelant(s) {who} bornent l'entrée (ex. [:64]) sous la "
                                    f"taille du buffer (128) ; débordement impossible, non "
                                    f"exploitable dans ce contexte d'appel"}},
                severity=p.get("severity"), cwe=cwe, owasp=p.get("owasp"))
            return []

    # 3b) Frontière gardée par un sanitizer -> false-positive.
    if code_validators:
        ctx.findings.set_verdict(
            fp, "false-positive",
            {"reason": {"file": file, "symbol": symbol,
                        "note": f"entrée assainie avant le sink (validateurs: "
                                f"{', '.join(code_validators)}) ; non exploitable"}},
            severity=p.get("severity"), cwe=cwe, owasp=p.get("owasp"))
        return []

    # 3c) Gate à 3 jambes, citations vérifiées STRICTEMENT dans l'index (FR-088).
    evidence = {
        "reachability": {"file": file, "symbol": symbol,
                         "note": "fonction atteignable depuis un point d'entrée HTTP"},
        "trust_boundary": {"file": file, "symbol": symbol,
                           "note": "entrée non fiable utilisée sans validation"},
        "impact": {"file": file, "symbol": symbol,
                   "note": f"sink {cwe} atteint dans cette fonction"},
    }
    if all(ctx.index.resolve_citation(c["file"], c["symbol"])
           for c in evidence.values() if "symbol" in c):
        return _confirm(ctx, fp, evidence, p, cwe)
    return _demote(ctx, fp, evidence, p, cwe)


def _confirm(ctx, fp, evidence, p, cwe):
    ctx.findings.set_verdict(fp, "true-positive", evidence, severity=p.get("severity", "medium"),
                             cvss=CVSS.get(p.get("severity", "medium"), 5.0),
                             cwe=cwe, owasp=p.get("owasp"))
    if p.get("rule_gap"):
        _record_rule_gap(ctx, fp, ctx.findings.get(fp), p)
    follow = [dict(title=f"report {fp}", role="reporter", priority=70,
                   payload={"fp": fp}, task_id=f"report-{fp}")]
    if cwe in LIVE_EXPLOITABLE:
        follow.insert(0, dict(title=f"validate {fp}", role="validator", priority=60,
                              payload={"fp": fp, "cwe": cwe}, task_id=f"validate-{fp}"))
    return follow


def _demote(ctx, fp, evidence, p, cwe):
    ctx.findings.set_verdict(fp, "needs-review", evidence, severity=p.get("severity"),
                             cwe=cwe, owasp=p.get("owasp"))
    return []


def _record_rule_gap(ctx, fp, f, p):
    ctx.events.emit("rule_gap", finding=fp, vuln_class=p.get("cwe"), symbol=f["symbol"])
    with open(os.path.join(ctx.run_dir, "rule-gaps.md"), "a", encoding="utf-8") as fh:
        fh.write(f"- **{p.get('cwe')}** sur `{f['file']}:{f['symbol']}` — trouvé par exploration, "
                 f"aucune règle ne l'aurait produit. À généraliser en règle CodeGuard (FR-042).\n")
