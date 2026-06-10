---
id: cg-web-ssrf-001
title: Server-side request to a user-controlled URL without allowlist
cwe: CWE-918
owasp: A10
severity: high
domain: web
source: forge-core
patterns:
  - "urlopen\(\s*[a-z_]+"
  - "requests\.(get|post)\(\s*[a-z_]+"
---
## Rule — Validate and allowlist outbound URLs

Fetching a user-supplied URL server-side lets an attacker reach internal services and cloud
metadata endpoints (SSRF).

**Vulnerable**: `urllib.request.urlopen(url)` where `url` is user input.
**Safe**: validate scheme/host against an allowlist; block private/link-local ranges.

Detection: `urlopen`/`requests.get` on a variable. Sink: the outbound HTTP client.
Impact: access to internal services, cloud metadata credential theft.
