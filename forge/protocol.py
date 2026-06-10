"""Protocole d'échange normalisé entre agents (source de vérité).

Matérialise analysis.md §4 : l'enveloppe commune, les taxonomies fermées, et le contrat
de chaque échange inter-agents — quelles données, quel format, quelle référence normative.
Exposé dans le dashboard (arêtes cliquables + panneau « Échanges »).
"""
from __future__ import annotations

# Enveloppe portée par TOUT message (analysis.md §4.1).
ENVELOPE = {
    "fields": [
        ("msg_id", "UUID", "identité du message"),
        ("schema_version", "str", "versionné, évolution additive seulement"),
        ("producer_role", "Role", "rôle émetteur"),
        ("producer_instance", "str", "ex. detector-2"),
        ("ts", "datetime(UTC)", "horodatage"),
        ("correlation_id", "str", "= fingerprint du finding — relie tout son cycle"),
        ("causation_id", "UUID?", "msg ayant causé celui-ci — provenance (NFR-007)"),
        ("payload_type", "enum", "Candidate | Verdict | ExploitResult | Task | OperatorMessage"),
        ("payload", "object", "validé contre le schéma de payload_type"),
    ],
    "format": "Pydantic / JSON Schema (versionné sous schemas/)",
    "refs": ["NFR-007 (provenance)", "Constitution XI (compat. ascendante)"],
}

# Taxonomies = vocabulaires FERMÉS ; une valeur hors liste est rejetée à la validation.
TAXONOMIES = [
    {"name": "Rôle", "values": "orchestrator, indexer, cartographer, detector, triager, "
     "validator, coverage_guide, reporter", "ref": "spec.md §4.2"},
    {"name": "Verdict", "values": "true-positive, false-positive, needs-review, "
     "not-applicable, code-quality", "ref": "spec.md §6.2 (FR-050)"},
    {"name": "État du finding", "values": "candidate → verdict_assigned → confirmed → "
     "confirmed[exploited?] → published / recorded", "ref": "spec.md §6.1"},
    {"name": "Classe de vulnérabilité", "values": "CWE (id)", "ref": "MITRE CWE — FR-076"},
    {"name": "Sévérité", "values": "tier critical/high/medium/low + score", "ref": "CVSS 3.1 (FIRST) — FR-077"},
    {"name": "Conformité", "values": "OWASP Top 10 (2021)", "ref": "OWASP — mapping secondaire"},
    {"name": "Technique de détection", "values": "rule:<id>, deps, secrets, exploratory, tool:<outil>",
     "ref": "FR-043"},
    {"name": "Kind d'operator message", "values": "blocker, request, feedback, info", "ref": "FR-102a"},
]

# Contrat de chaque échange (arête du pipeline).
EXCHANGES = [
    {"id": "operator->orchestrator", "frm": "operator", "to": "orchestrator",
     "label": "Configuration & goals", "payload": "EvaluationConfig",
     "fields": [("target", "ref"), ("testbed", "desc"), ("goals", "texte"),
                ("rules", "hard-rules"), ("budget", "caps")],
     "format": "YAML (forge.yaml)", "refs": ["spec.md §12 (FR-126/127)"]},
    {"id": "orchestrator->*", "frm": "orchestrator", "to": "(tous)",
     "label": "Supervision (spawn · heartbeat · claim · budget)", "payload": "LifecycleSignal",
     "fields": [("spawn/terminate", "—"), ("heartbeat", "âge"), ("claim/lease", "task_id+fencing"),
                ("budget", "halt")],
     "format": "substrate SQLite (non-message)", "refs": ["FR-002, FR-100 (heartbeat), FR-095/096 (claim)"]},
    {"id": "indexer->*", "frm": "indexer", "to": "(tous)",
     "label": "Index de code", "payload": "CodeIndex",
     "fields": [("functions", "[{file,name,params,line}]"), ("call_graph", "edges"),
                ("resolve_citation", "fn(file,symbol)->bool")],
     "format": "API de requête en mémoire/SQLite", "refs": ["FR-020/022"]},
    {"id": "cartographer->*", "frm": "cartographer", "to": "(tous)",
     "label": "Carte de sécurité", "payload": "SecurityMap",
     "fields": [("flows", "[{entry,chain,validated}]"), ("entrypoints", "[]"),
                ("trust_boundaries", "[]")],
     "format": "documents Markdown + digest JSON", "refs": ["FR-030..035"]},
    {"id": "detector->triager", "frm": "detector", "to": "triager",
     "label": "Candidat", "payload": "Candidate",
     "fields": [("file", "str"), ("symbol", "str"), ("vuln_class", "CWE"),
                ("technique", "str"), ("description", "str"), ("fingerprint", "sha256(path|symbol|class)")],
     "format": "Pydantic/JSON ; import outils via SARIF",
     "refs": ["FR-043", "FR-090 (fingerprint)", "SARIF v2.1.0 (OASIS)", "MITRE CWE"]},
    {"id": "triager->validator", "frm": "triager", "to": "validator",
     "label": "Verdict TP exploitable", "payload": "Verdict + exploitability",
     "fields": [("fp", "fingerprint"), ("verdict", "'true-positive'"),
                ("evidence", "{reachability, trust_boundary, impact : Citation}"), ("cwe", "CWE")],
     "format": "Pydantic (gate = validation de schéma + résolution de citations)",
     "refs": ["FR-087/088 (evidence gate)", "Constitution I"]},
    {"id": "triager->reporter", "frm": "triager", "to": "reporter",
     "label": "Verdict confirmé", "payload": "Verdict",
     "fields": [("fp", "fingerprint"), ("verdict", "enum(5)"),
                ("evidence", "{3 jambes}"), ("severity", "tier+CVSS"), ("cwe", "CWE"), ("owasp", "cat")],
     "format": "Pydantic/JSON", "refs": ["FR-050/054", "CVSS 3.1", "OWASP Top 10"]},
    {"id": "validator->reporter", "frm": "validator", "to": "reporter",
     "label": "Résultat d'exploitation", "payload": "ExploitResult",
     "fields": [("fp", "fingerprint"), ("exploited", "bool"), ("oracle", "sqlmap|nuclei|…|llm"),
                ("request", "str"), ("response", "extrait"), ("poc_path", "fichier .py")],
     "format": "JSON + PoC runnable", "refs": ["FR-060/061/063", "Constitution VII"]},
    {"id": "reporter->output", "frm": "reporter", "to": "(sortie)",
     "label": "Rapport de finding + rollup", "payload": "FindingReport",
     "fields": [("title", "str"), ("cwe", "CWE"), ("severity", "tier+CVSS"), ("owasp", "cat"),
                ("repro", "étapes"), ("poc", "ref"), ("permalink", "file#Lx-Ly@sha")],
     "format": "Markdown ; export SARIF / OCSF / CycloneDX (SBOM)",
     "refs": ["FR-075..084", "SARIF v2.1.0", "OCSF", "CycloneDX"]},
    {"id": "coverage->detector", "frm": "coverage", "to": "detector",
     "label": "Tâche dirigée", "payload": "Task",
     "fields": [("task_id", "stable"), ("title", "str"), ("role", "'detector'"),
                ("priority", "int"), ("payload", "{}")],
     "format": "work queue (SQLite)", "refs": ["FR-070", "FR-094..099"]},
    {"id": "coverage->orchestrator", "frm": "coverage", "to": "orchestrator",
     "label": "Couverture complète", "payload": "CoverageComplete",
     "fields": [("coverage_complete", "bool"), ("items", "[{component,goal,state}]")],
     "format": "flag substrate", "refs": ["FR-071", "Constitution VI"]},
]


def protocol() -> dict:
    return {"envelope": ENVELOPE, "taxonomies": TAXONOMIES, "exchanges": EXCHANGES}
