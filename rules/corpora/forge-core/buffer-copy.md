---
id: cg-mem-bufcopy-001
title: Copy into a fixed-size buffer without a bounds check
cwe: CWE-120
owasp: A06
severity: high
domain: memory
source: forge-core
patterns:
  - "\[\s*\d*\s*:\s*len\("
---
## Rule — Bound every copy into a fixed-size buffer

Copying an input into a fixed-size buffer without verifying that the input fits is a classic
overflow pattern (CWE-120 / CWE-787). The length must be checked against the buffer size.

**Vulnerable**: `buf = bytearray(128); buf[0:len(src)] = src`  (no check that `len(src) <= 128`)
**Safe**: `if len(src) > 128: raise ValueError(); buf[0:len(src)] = src`

Detection note: this pattern is **breadth-first**. Whether it is *exploitable* depends on the
call context — if every caller bounds the input below the buffer size, the finding is not
exploitable and Triage should clear it. That call-graph reasoning is exactly the Triager's job;
the Detector only flags the shape.
