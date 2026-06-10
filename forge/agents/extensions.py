"""Extension roles (spec.md §4.3 / §6) — invoked after the core pipeline.

Deterministic implementations for the demo, faithful to the spec's description:
  - Variant-Hunter : given a confirmed finding, search the rest of the target for the same pattern.
  - Attack-Mapper  : assemble confirmed findings into a privilege graph (entry → capability → goal).
  - Remediator     : generate AND verify candidate patches for confirmed findings.

These are §6 extensions, run only in step mode (to illustrate their contribution); the core
pipeline does not depend on them.
"""
from __future__ import annotations

import re

from ..remediation import propose_fix

GOAL_OF = {
    "CWE-89": "Authentication bypass / data access",
    "CWE-78": "Remote code execution",
    "CWE-502": "Remote code execution",
    "CWE-639": "Unauthorized data access",
    "CWE-22": "Unauthorized data access",
    "CWE-918": "Internal network access",
    "CWE-79": "Session theft",
}


def variant_hunt(ctx) -> list[dict]:
    """For each confirmed rule-based class, search ALL functions for the same pattern."""
    tps = ctx.findings.confirmed_true_positives()
    out, seen = [], set()
    for f in tps:
        tech = f["technique"] or ""
        if not tech.startswith("rule:"):
            continue
        rid = tech.split("rule:")[1]
        rule = ctx.rulestore.rules.get(rid)
        if not rule or rid in seen:
            continue
        seen.add(rid)
        confirmed = {(x["file"], x["symbol"]) for x in tps if x["cwe"] == f["cwe"]}
        locs = []
        for fi in ctx.index.all_functions():
            for pat in rule.patterns:
                try:
                    if re.search(pat, fi.source):
                        locs.append({"file": fi.file, "symbol": fi.name,
                                     "already": (fi.file, fi.name) in confirmed})
                        break
                except re.error:
                    pass
        out.append({"origin": f["symbol"], "cwe": f["cwe"], "rule": rid, "variants": locs})
    return out


def attack_map(ctx) -> dict:
    """Privilege graph: each exploited finding is a capability from an entry point to a goal."""
    tps = [f for f in ctx.findings.confirmed_true_positives() if f["exploited"]]
    paths = []
    for f in tps:
        paths.append({"entry": "HTTP request (attacker)",
                      "capability": f"{f['cwe']} in {f['symbol']}",
                      "goal": GOAL_OF.get(f["cwe"], "Impact"), "severity": f["severity"]})
    paths.sort(key=lambda p: p["goal"])
    return {"paths": paths, "goals": sorted({p["goal"] for p in paths})}


def _verify(ctx, cwe: str, safe_code: str) -> bool:
    """A patch is verified if the safe code no longer matches the vulnerability's rule pattern."""
    if not safe_code:
        return False
    for rule in ctx.rulestore.rules.values():
        if rule.cwe == cwe:
            for pat in rule.patterns:
                try:
                    if re.search(pat, safe_code):
                        return False
                except re.error:
                    pass
    return True


def remediate(ctx) -> list[dict]:
    """Generate a fix per confirmed finding (deduped by location) AND verify it."""
    out, seen = [], set()
    for f in ctx.findings.confirmed_true_positives():
        key = (f["file"], f["symbol"], f["cwe"])
        if key in seen:
            continue
        seen.add(key)
        fix = propose_fix(f["cwe"])
        out.append({"symbol": f["symbol"], "file": f["file"], "cwe": f["cwe"],
                    "steps": fix["steps"], "safe_code": fix["safe_code"],
                    "verified": _verify(ctx, f["cwe"], fix["safe_code"])})
    return out
