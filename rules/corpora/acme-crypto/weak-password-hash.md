---
id: acme-crypto-pwhash-007
title: Password stored with fast unsalted hash (MD5/SHA-1/SHA-256) instead of a KDF
cwe: CWE-916
owasp: A02
severity: high
domain: crypto
source: acme-crypto-labs
patterns:
  - "hashlib\.(md5|sha1|sha256)\("
  - "(?s)def\s+\w*(hash_password|password)\w*\(.*hashlib\."
---
## Rule (ACME Crypto Labs corpus) — Passwords require a memory-hard KDF

> Corpus tiers spécialisé « crypto », fédéré dans Forge pour démontrer ADR-002 :
> des entités plus expertes maintiennent des règles de pointe par domaine.

A general-purpose hash (even SHA-256) is unsuitable for passwords: it is fast and therefore
cheap to brute-force. Passwords MUST use a memory-hard, salted KDF with a tuned cost factor:
**Argon2id** (preferred), scrypt, or bcrypt. Unsalted hashes additionally enable rainbow-table
and identical-password correlation attacks.

**Vulnerable**: `hashlib.md5(password.encode()).hexdigest()` — no salt, no work factor.
**Safe**: `argon2.PasswordHasher().hash(password)`.

This rule is more specific than the generic `cg-crypto-weakhash-001`: it is scoped to the
*password* context and raises severity accordingly. In `vector` mode, it should out-rank the
generic rule when scoring a function that hashes a password.
