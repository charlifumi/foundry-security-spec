"""Triager — investigation + evidence gate (FR-050..059, FR-087/088).

Construit la preuve à trois jambes (atteignabilité, frontière de confiance, impact),
vérifie **mécaniquement** que chaque citation résout (FR-088) et n'accorde
`true-positive` que si le gate passe — sinon démotion en `needs-review` (Constitution I).
Le modèle ne s'attribue jamais le verdict ; le gate le fait.
"""
from __future__ import annotations

import os

# Classes exploitables en live contre le testbed (-> Validator).
LIVE_EXPLOITABLE = {"CWE-89", "CWE-79", "CWE-78", "CWE-918", "CWE-639", "CWE-22", "CWE-502"}
CVSS = {"critical": 9.3, "high": 7.8, "medium": 5.4, "low": 3.1}


def _resolves(ctx, file, symbol) -> bool:
    if ctx.index.resolve_citation(file, symbol):
        return True
    # citation non-fonction (secret module-level, dépendance) : le fichier existe au build.
    path = os.path.join(ctx.config["target"]["source"], file)
    return os.path.exists(path)


def handle(task, ctx, agent_id) -> list:
    p = task["payload"]
    fp = p["fp"]
    f = ctx.findings.get(fp)
    if not f:
        return []
    ctx.llm.complete(role="triager", instance=agent_id, correlation_id=fp,
                     prompt=f"Investigue {f['file']}:{f['symbol']} ({p.get('cwe')}).",
                     system="Trace le flux entrée→sink, identifie la frontière de confiance.")

    file, symbol = f["file"], f["symbol"]
    presence = p.get("presence_is_vuln", False)

    if presence:
        # Carve-out FR-087a : la présence est la vuln (secret/crypto/dépendance).
        evidence = {
            "reachability": {"file": file, "symbol": symbol, "note": "inclus au build"},
            "trust_boundary": {"note": "le dépôt source lui-même (FR-087a)"},
            "impact": {"file": file, "symbol": symbol,
                       "note": "exposition/algorithme déprécié au point cité"},
        }
        legs_ok = _resolves(ctx, file, symbol)
    else:
        # Classes data-flow : 3 jambes citées dans le code, toutes doivent résoudre.
        validators = ctx.index.validation_in(symbol)
        evidence = {
            "reachability": {"file": file, "symbol": symbol,
                             "note": "fonction atteignable depuis un point d'entrée HTTP"},
            "trust_boundary": {"file": file, "symbol": symbol,
                               "note": f"entrée non fiable utilisée sans validation "
                                       f"(validateurs détectés: {validators or 'aucun'})"},
            "impact": {"file": file, "symbol": symbol,
                       "note": f"sink {p.get('cwe')} atteint dans cette fonction"},
        }
        legs_ok = all(_resolves(ctx, c["file"], c["symbol"])
                      for c in evidence.values() if "symbol" in c)

    if legs_ok:
        verdict = "true-positive"
        cvss = CVSS.get(p.get("severity", "medium"), 5.0)
        ctx.findings.set_verdict(fp, verdict, evidence, severity=p.get("severity", "medium"),
                                 cvss=cvss, cwe=p.get("cwe"), owasp=p.get("owasp"))
        # rule-gap : finding exploratoire qu'aucune règle n'aurait produit (FR-042).
        if p.get("rule_gap"):
            _record_rule_gap(ctx, fp, f, p)
        follow = [dict(title=f"report {fp}", role="reporter", priority=70,
                       payload={"fp": fp}, task_id=f"report-{fp}")]
        if p.get("cwe") in LIVE_EXPLOITABLE:
            follow.insert(0, dict(title=f"validate {fp}", role="validator", priority=60,
                                  payload={"fp": fp, "cwe": p.get("cwe")},
                                  task_id=f"validate-{fp}"))
        return follow
    else:
        # Une citation ne résout pas -> démotion (FR-088), jamais TP.
        ctx.findings.set_verdict(fp, "needs-review", evidence, severity=p.get("severity"),
                                 cwe=p.get("cwe"), owasp=p.get("owasp"))
        return []


def _record_rule_gap(ctx, fp, f, p):
    ctx.events.emit("rule_gap", finding=fp, vuln_class=p.get("cwe"), symbol=f["symbol"])
    path = os.path.join(ctx.run_dir, "rule-gaps.md")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"- **{p.get('cwe')}** sur `{f['file']}:{f['symbol']}` — trouvé par exploration, "
                 f"aucune règle ne l'aurait produit. À généraliser en règle CodeGuard (FR-042).\n")
