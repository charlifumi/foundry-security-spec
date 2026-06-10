---
id: cg-web-path-001
title: Filesystem path built from untrusted filename without normalization
cwe: CWE-22
owasp: A01
severity: high
domain: web
source: forge-core
patterns:
  - "open\(\s*path\b"
  - "(?s)os\.path\.join\([^)]*\b(file|filename|path|name)\b[^)]*\).*open\("
---
## Rule — Confine file access to a safe base directory

Joining an unsanitized filename to a base directory allows `../` traversal to read arbitrary
files.

**Vulnerable**: `open(os.path.join(BASE, filename), "rb")` with user `filename`.
**Safe**: resolve the path and verify it stays within BASE (`os.path.realpath` + prefix check).

Detection: `open(path)` where `path` derives from `os.path.join` with user input. Sink: the
file read. Impact: disclosure of arbitrary files (config, secrets, `/etc/passwd`).
