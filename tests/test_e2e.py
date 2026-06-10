"""Test bout-en-bout sur vulnshop (mode déterministe, sans clé API).

Vérifie les critères de succès clés : SC-001 (un TP publié pour une vuln semée, sans
intervention), exploitation live, rule-gap exploratoire, couverture complète.
Lancer : FORGE_RUNS_DIR=/tmp/forge-runs python -m tests.test_e2e
"""
import os
import tempfile

os.environ.setdefault("FORGE_RUNS_DIR", os.path.join(tempfile.gettempdir(), "forge-e2e"))

from forge import config, orchestrator  # noqa: E402


def test_e2e_vulnshop():
    ctx = orchestrator.run(config.load(), max_seconds=90)
    tps = ctx.findings.confirmed_true_positives()
    classes = {f["cwe"] for f in tps}
    exploited = {f["cwe"] for f in tps if f["exploited"]}

    # SC-001 : au moins un true-positive publié pour une vuln semée.
    assert any(f["state"] == "published" for f in tps), "aucun finding publié"
    # Couverture des classes semées (rules + secrets + deps + exploratory).
    for cwe in ("CWE-89", "CWE-78", "CWE-918", "CWE-79", "CWE-22", "CWE-502", "CWE-639",
                "CWE-798", "CWE-1035"):
        assert cwe in classes, f"classe {cwe} non détectée"
    # SC-003 : exploitations live observées (SQLi, cmd, SSRF, IDOR, traversal, deser).
    assert {"CWE-89", "CWE-78", "CWE-918", "CWE-639"} <= exploited, f"exploités: {exploited}"
    # Flywheel : l'IDOR exploratoire a généré un rule-gap (FR-042).
    gaps = ctx.db.connect().execute(
        "SELECT COUNT(*) c FROM events WHERE kind='rule_gap'").fetchone()["c"]
    assert gaps >= 1, "aucun rule-gap enregistré"
    # SC-006 (variante) : couverture complète atteinte.
    assert ctx.coverage_complete.is_set(), "couverture non complète"
    print(f"OK e2e : {len(tps)} TP, {len(exploited)} classes exploitées, {gaps} rule-gap(s)")


if __name__ == "__main__":
    test_e2e_vulnshop()
    print("=== E2E vulnshop : OK ===")
