---
id: cg-web-deser-001
title: Untrusted data deserialized with pickle
cwe: CWE-502
owasp: A08
severity: critical
domain: web
source: forge-core
patterns:
  - "pickle\.loads?\("
  - "yaml\.load\((?!.*Loader)"
---
## Rule — Never deserialize untrusted input with pickle

`pickle.loads` on attacker-controlled bytes executes arbitrary code during deserialization.

**Vulnerable**: `pickle.loads(base64.b64decode(cookie))`
**Safe**: use a data-only format (JSON); if objects are required, sign and verify payloads.

Detection: `pickle.loads` / unsafe `yaml.load`. Sink: the deserializer. Impact: remote code
execution.
