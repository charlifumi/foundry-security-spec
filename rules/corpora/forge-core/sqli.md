---
id: cg-web-sqli-001
title: SQL query built by string concatenation of untrusted input
cwe: CWE-89
owasp: A03
severity: high
domain: web
source: forge-core
patterns:
  - "(?s)(SELECT|INSERT|UPDATE|DELETE)\b.*?\+\s*\w+\s*\+"
---
## Rule — Parameterize all SQL

Untrusted input must never be concatenated into a SQL string. Use parameterized
queries (placeholders + a values tuple) so the driver, not string building, separates
code from data.

**Vulnerable**: `conn.execute("SELECT * FROM users WHERE name='" + name + "'")`
**Safe**: `conn.execute("SELECT * FROM users WHERE name = ?", (name,))`

Detection: a SQL keyword whose statement is assembled with `+ <var> +`. The sink is the
`execute()` call; the trust boundary is the point where the request parameter enters the
string. Impact: authentication bypass, data exfiltration, data modification.
