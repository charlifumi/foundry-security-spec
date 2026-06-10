"""Remediation proposals (Remediator role, spec.md §6.4).

For each confirmed finding, propose concrete fix steps and a safe-code rewrite of the
offending pattern. Deterministic, per vulnerability class — no LLM required for the demo.
Surfaced in the dashboard (finding modal + the 🛠 Fixes panel) and exportable.
"""
from __future__ import annotations

FIXES: dict[str, dict] = {
    "CWE-89": {"steps": ["Use parameterized queries (placeholders + a values tuple).",
                         "Never concatenate untrusted input into SQL."],
               "safe": 'row = conn.execute(\n    "SELECT id, username, role FROM users "\n'
                       '    "WHERE username = ? AND password_md5 = ?",\n'
                       '    (username, password_md5),\n).fetchone()'},
    "CWE-79": {"steps": ["Escape output for the HTML context.",
                         "Prefer a template engine with auto-escaping."],
               "safe": 'import html\n'
                       'return "<h1>Results for: " + html.escape(term) + "</h1>"'},
    "CWE-78": {"steps": ["Pass an argument list, not a shell string.",
                         "Avoid shell=True and validate the input."],
               "safe": 'import subprocess\n'
                       'out = subprocess.run(["ping", "-c", "1", host],\n'
                       '                     capture_output=True, text=True)  # no shell'},
    "CWE-918": {"steps": ["Validate the URL scheme/host against an allowlist.",
                          "Block private and link-local ranges."],
                "safe": 'from urllib.parse import urlparse\n'
                        'host = urlparse(url).hostname\n'
                        'if host not in ALLOWED_HOSTS:\n    raise ValueError("blocked URL")\n'
                        'return urllib.request.urlopen(url, timeout=3).read()'},
    "CWE-639": {"steps": ["Check the requested id belongs to the caller (or that the caller is admin)."],
                "safe": 'if requested_id != session_user_id and not is_admin(session_user_id):\n'
                        '    abort(403)\nreturn db.get_user(int(requested_id))'},
    "CWE-22": {"steps": ["Resolve the path and verify it stays within the base directory."],
               "safe": 'base = os.path.realpath(AVATAR_DIR)\n'
                       'safe = os.path.realpath(os.path.join(base, filename))\n'
                       'if not safe.startswith(base + os.sep):\n    abort(400)\n'
                       'with open(safe, "rb") as f:\n    return f.read()'},
    "CWE-502": {"steps": ["Use a data-only format (JSON).",
                          "If objects are required, sign and verify the payload."],
                "safe": 'import json, base64\n'
                        'return json.loads(base64.b64decode(cookie_value))  # data-only, no pickle'},
    "CWE-798": {"steps": ["Move the secret to an environment variable or a secrets manager.",
                          "Rotate the exposed secret immediately."],
                "safe": 'import os\nSECRET_KEY = os.environ["SECRET_KEY"]  # never hardcode'},
    "CWE-327": {"steps": ["Use a strong, purpose-appropriate algorithm.",
                          "For passwords use a salted KDF (Argon2/bcrypt)."],
                "safe": 'from argon2 import PasswordHasher\n'
                        'return PasswordHasher().hash(password)'},
    "CWE-916": {"steps": ["Hash passwords with a memory-hard, salted KDF and a tuned cost factor."],
                "safe": 'from argon2 import PasswordHasher\n'
                        'return PasswordHasher().hash(password)  # Argon2id'},
    "CWE-1035": {"steps": ["Upgrade the dependency to a patched version.",
                           "Add SCA (OSV-Scanner/Grype) to CI to catch regressions."],
                 "safe": '# requirements.txt — pinned to patched versions\n'
                         'Flask>=3.0\nPyYAML>=6.0\nrequests>=2.32\nJinja2>=3.1'},
    "CWE-120": {"steps": ["Check the input length against the buffer size before copying."],
                "safe": 'if len(src) > 128:\n    raise ValueError("input too large")\n'
                        'buf[0:len(src)] = src'},
}


def propose_fix(cwe: str | None) -> dict:
    f = FIXES.get(cwe or "")
    if not f:
        return {"steps": ["Manual review required for this class."], "safe_code": ""}
    return {"steps": f["steps"], "safe_code": f["safe"]}
