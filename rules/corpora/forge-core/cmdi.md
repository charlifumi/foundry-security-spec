---
id: cg-web-cmdi-001
title: OS command built from untrusted input with shell=True
cwe: CWE-78
owasp: A03
severity: critical
domain: web
source: forge-core
patterns:
  - "shell\s*=\s*True"
  - "(?s)(os\.system|os\.popen)\(.*\+"
---
## Rule — Never pass untrusted input to a shell

Building a shell command by concatenation and running it with `shell=True` allows command
injection. Pass an argument list and avoid the shell.

**Vulnerable**: `subprocess.run("ping -c1 " + host, shell=True)`
**Safe**: `subprocess.run(["ping", "-c1", host])` (no shell), with input validation.

Detection: `shell=True`, or `os.system`/`os.popen` with concatenation. Sink: the shell.
Impact: remote code execution on the host.
