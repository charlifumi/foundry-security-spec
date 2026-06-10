"""Detector — produit des candidats (FR-037..049).

Quatre techniques : règles (corpus CodeGuard fédéré), secrets, dépendances, exploration.
Écrit au finding store uniquement (FR-044) ; enfile une tâche de triage par candidat.
Le mode exploration trouve ce qu'aucune règle ne décrit (ex. IDOR) et marque un rule-gap (FR-042).
"""
from __future__ import annotations

import os
import re

# Mini-base d'avis de vulnérabilité pour le scan de dépendances (FR-038).
DEP_ADVISORIES = {
    "Flask": {"vuln_below": "1.0", "cve": "CVE-2018-1000656", "sev": "high"},
    "PyYAML": {"vuln_below": "5.1", "cve": "CVE-2017-18342", "sev": "critical"},
    "requests": {"vuln_below": "2.20.0", "cve": "CVE-2018-18074", "sev": "medium"},
    "Jinja2": {"vuln_below": "2.11.3", "cve": "CVE-2020-28493", "sev": "medium"},
}
SECRET_PATTERNS = [
    (re.compile(r'(SECRET_KEY|API_KEY|ADMIN_API_KEY|DB_PASSWORD|TOKEN)\s*=\s*["\'][^"\']{8,}',
                re.I), "CWE-798"),
]


def _strip_comments(src: str) -> str:
    """Retire docstrings et commentaires (le raisonnement d'autorisation porte sur le code)."""
    src = re.sub(r'(?s)""".*?"""', "", src)
    src = re.sub(r"(?s)'''.*?'''", "", src)
    return re.sub(r"#.*", "", src)


def _lt(a: str, b: str) -> bool:
    """Comparaison de versions (a < b), tolérante."""
    def parts(v): return [int(x) for x in re.findall(r"\d+", v)]
    return parts(a) < parts(b)


def _triage_task(fp, meta):
    return dict(title=f"triage {fp}", role="triager", queue="main", priority=50,
                payload={"fp": fp, **meta}, task_id=f"triage-{fp}")


def handle(task, ctx, agent_id) -> list:
    kind = task["payload"].get("kind", "rules")
    if kind == "rules":
        return _rules(task, ctx)
    if kind == "secrets":
        return _secrets(task, ctx)
    if kind == "deps":
        return _deps(task, ctx)
    if kind == "explore":
        return _explore(task, ctx)
    return []


def _rules(task, ctx) -> list:
    """Balayage par règles : chaque fonction du fichier × règles candidates (FR-037)."""
    rel = task["payload"]["file"]
    follow = []
    funcs = [f for f in ctx.index.all_functions() if f.file == rel]
    for fi in funcs:
        ctx.llm.complete(role="detector", instance="detector", prompt=fi.source[:800],
                         system="Évalue cette fonction contre les règles de détection.")
        for rule, pat in ctx.rulestore.detect_in_function(fi.source):
            fp = ctx.findings.add_candidate(
                file=fi.file, symbol=fi.name, vuln_class=rule.cwe,
                title=rule.title, technique=f"rule:{rule.id}",
                description=f"Règle {rule.id} déclenchée (motif: {pat}).")
            follow.append(_triage_task(fp, {
                "cwe": rule.cwe, "owasp": rule.owasp, "severity": rule.severity,
                "rule_id": rule.id, "presence_is_vuln": rule.cwe in ("CWE-798", "CWE-327", "CWE-916")}))
    return follow


def _secrets(task, ctx) -> list:
    """Scan de secrets en dur (FR-039)."""
    src = ctx.config["target"]["source"]
    follow = []
    for dp, _, files in os.walk(src):
        for fn in files:
            if fn.endswith(".py"):
                path = os.path.join(dp, fn)
                rel = os.path.relpath(path, src)
                text = open(path, encoding="utf-8", errors="ignore").read()
                for pat, cwe in SECRET_PATTERNS:
                    for m in pat.finditer(text):
                        var = m.group(1)
                        fp = ctx.findings.add_candidate(
                            file=rel, symbol=var, vuln_class=cwe,
                            title=f"Secret en dur ({var})", technique="secrets",
                            description=f"Secret littéral assigné à {var} dans le code source.")
                        follow.append(_triage_task(fp, {
                            "cwe": cwe, "owasp": "A07", "severity": "high",
                            "presence_is_vuln": True}))
    return follow


def _deps(task, ctx) -> list:
    """Scan de dépendances (FR-038) contre une mini-base d'avis."""
    src = ctx.config["target"]["source"]
    req = os.path.join(src, "requirements.txt")
    follow = []
    if not os.path.exists(req):
        return []
    for line in open(req, encoding="utf-8"):
        line = line.strip()
        m = re.match(r"([A-Za-z0-9_.\-]+)==([0-9.]+)", line)
        if not m:
            continue
        pkg, ver = m.group(1), m.group(2)
        adv = DEP_ADVISORIES.get(pkg)
        if adv and _lt(ver, adv["vuln_below"]):
            fp = ctx.findings.add_candidate(
                file="requirements.txt", symbol=f"{pkg}=={ver}", vuln_class="CWE-1035",
                title=f"Dépendance vulnérable : {pkg} {ver} ({adv['cve']})", technique="deps",
                description=f"{pkg}=={ver} < {adv['vuln_below']} — {adv['cve']}.")
            follow.append(_triage_task(fp, {
                "cwe": "CWE-1035", "owasp": "A06", "severity": adv["sev"],
                "presence_is_vuln": True, "cve": adv["cve"]}))
    return follow


def _explore(task, ctx) -> list:
    """Exploration libre (FR-040) : trouve ce qu'aucune règle ne décrit -> rule-gap (FR-042).

    Heuristique IDOR : une fonction qui reçoit un identifiant et lit des données d'un
    autre acteur sans contrôle d'autorisation visible.
    """
    follow = []
    ctx.llm.complete(role="detector", instance="detector-explore",
                     prompt="Explore les contrôles d'accès des routes.", system="Chasse exploratoire.")
    for fi in ctx.index.all_functions():
        has_id_param = any(("id" in p.lower()) for p in fi.params)
        # accès à un enregistrement via le graphe d'appels (pas le texte, pour éviter la ligne def)
        accesses_record = any(c in {"get_user", "get_account", "get_record", "fetch_user"}
                              for c in fi.calls)
        # contrôle d'autorisation cherché sur le CODE (commentaires/docstrings retirés)
        code = _strip_comments(fi.source)
        no_authz_check = not re.search(r"==|!=|authoriz|is_admin|\bowner\b|abort|403|forbidden|"
                                       r"current_user|session\[", code)
        looks_idor = has_id_param and accesses_record and no_authz_check
        if looks_idor:
            fp = ctx.findings.add_candidate(
                file=fi.file, symbol=fi.name, vuln_class="CWE-639",
                title="Référence directe à un objet sans contrôle d'accès (IDOR)",
                technique="exploratory",
                description=f"{fi.name} expose des données par identifiant sans vérifier "
                            f"l'autorisation de l'appelant.")
            follow.append(_triage_task(fp, {
                "cwe": "CWE-639", "owasp": "A01", "severity": "high",
                "presence_is_vuln": False, "rule_gap": True}))
    return follow
