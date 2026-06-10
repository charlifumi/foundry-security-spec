"""Normalisation SARIF -> candidats Forge.

SARIF (OASIS) est le format pivot commun à Semgrep, CodeQL, Bandit, Trivy, OSV-Scanner,
Gitleaks, Nuclei… Le normaliser une fois évite N adaptateurs ad hoc.
"""
from __future__ import annotations

import re


def _cwe_from_rule(rule_id: str, props: dict) -> str:
    # CWE depuis les propriétés de règle, sinon depuis l'id (best effort).
    for key in ("cwe", "cwe_id", "tags"):
        v = props.get(key)
        if isinstance(v, list):
            for item in v:
                m = re.search(r"CWE[-_ ]?(\d+)", str(item), re.I)
                if m:
                    return f"CWE-{m.group(1)}"
        elif v:
            m = re.search(r"CWE[-_ ]?(\d+)", str(v), re.I)
            if m:
                return f"CWE-{m.group(1)}"
    m = re.search(r"CWE[-_ ]?(\d+)", rule_id, re.I)
    return f"CWE-{m.group(1)}" if m else "CWE-Unknown"


def sarif_to_candidates(sarif: dict, tool_id: str) -> list[dict]:
    out = []
    for run in sarif.get("runs", []):
        rules = {r.get("id"): r for r in run.get("tool", {}).get("driver", {}).get("rules", [])}
        for res in run.get("results", []):
            rule_id = res.get("ruleId", "")
            props = (rules.get(rule_id, {}) or {}).get("properties", {})
            cwe = _cwe_from_rule(rule_id, props)
            loc = (res.get("locations") or [{}])[0].get("physicalLocation", {})
            file = loc.get("artifactLocation", {}).get("uri", "?")
            line = loc.get("region", {}).get("startLine")
            msg = (res.get("message") or {}).get("text", rule_id)
            out.append({
                "file": file, "symbol": rule_id, "vuln_class": cwe,
                "title": msg[:120], "technique": f"tool:{tool_id}:{rule_id}",
                "description": msg, "line": line,
            })
    return out
