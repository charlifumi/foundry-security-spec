---
id: cg-web-xss-001
title: HTML response built by concatenating unescaped user input
cwe: CWE-79
owasp: A03
severity: medium
domain: web
source: forge-core
patterns:
  - "(?s)<(html|body|h1|h2|div|li|p|span|table)\b.*?\+\s*\w+"
---
## Rule — Escape output rendered into HTML

User-controlled values placed into an HTML response must be contextually escaped. Building
markup by concatenating raw input enables reflected/stored XSS.

**Vulnerable**: `"<h1>Results for: " + term + "</h1>"`
**Safe**: use a template engine with auto-escaping, or `html.escape(term)`.

Detection: an HTML tag in a string assembled with `+ <var>`. Sink: the HTTP response body.
Impact: arbitrary JavaScript execution in the victim's browser, session theft.
