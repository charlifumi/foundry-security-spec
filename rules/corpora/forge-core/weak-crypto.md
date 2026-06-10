---
id: cg-crypto-weakhash-001
title: Deprecated hash primitive (MD5/SHA1) used for a security purpose
cwe: CWE-327
owasp: A02
severity: medium
domain: crypto
source: forge-core
patterns:
  - "hashlib\.(md5|sha1)\("
---
## Rule — Use strong, purpose-appropriate hashing

MD5 and SHA-1 are broken for security uses. For passwords use a slow, salted KDF
(bcrypt/scrypt/Argon2). "Presence is the vulnerability" (gate carve-out FR-087a).

**Vulnerable**: `hashlib.md5(password.encode()).hexdigest()`
**Safe**: `argon2.hash(password)` or `bcrypt.hashpw(...)`.

Detection: `hashlib.md5`/`sha1`. Impact depends on use (password cracking, collision forgery).
