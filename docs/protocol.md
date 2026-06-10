# Forge — Échanges normalisés entre agents

> Quelles données, quel format, quelle référence normative. Source exécutable : `forge/protocol.py` (panneau **🔀 Échanges** + arêtes cliquables du dashboard). Voir analysis.md §4.

## Enveloppe commune (tout message)

| Champ | Type | Rôle |
|---|---|---|
| `msg_id` | UUID | identité du message |
| `schema_version` | str | versionné, évolution additive seulement |
| `producer_role` | Role | rôle émetteur |
| `producer_instance` | str | ex. detector-2 |
| `ts` | datetime(UTC) | horodatage |
| `correlation_id` | str | = fingerprint du finding — relie tout son cycle |
| `causation_id` | UUID? | msg ayant causé celui-ci — provenance (NFR-007) |
| `payload_type` | enum | Candidate | Verdict | ExploitResult | Task | OperatorMessage |
| `payload` | object | validé contre le schéma de payload_type |

**Format :** Pydantic / JSON Schema (versionné sous schemas/) · **Réf :** NFR-007 (provenance), Constitution XI (compat. ascendante)

## Taxonomies (vocabulaires fermés)

| Taxonomie | Valeurs | Référence |
|---|---|---|
| Rôle | orchestrator, indexer, cartographer, detector, triager, validator, coverage_guide, reporter | spec.md §4.2 |
| Verdict | true-positive, false-positive, needs-review, not-applicable, code-quality | spec.md §6.2 (FR-050) |
| État du finding | candidate → verdict_assigned → confirmed → confirmed[exploited?] → published / recorded | spec.md §6.1 |
| Classe de vulnérabilité | CWE (id) | MITRE CWE — FR-076 |
| Sévérité | tier critical/high/medium/low + score | CVSS 3.1 (FIRST) — FR-077 |
| Conformité | OWASP Top 10 (2021) | OWASP — mapping secondaire |
| Technique de détection | rule:<id>, deps, secrets, exploratory, tool:<outil> | FR-043 |
| Kind d'operator message | blocker, request, feedback, info | FR-102a |

## Contrats d'échange

### operator → orchestrator — Configuration & goals

- **Payload :** `EvaluationConfig` · **Format :** YAML (forge.yaml)
- **Réf. normatives :** spec.md §12 (FR-126/127)
- **Données :** `target`:ref, `testbed`:desc, `goals`:texte, `rules`:hard-rules, `budget`:caps

### orchestrator → (tous) — Supervision (spawn · heartbeat · claim · budget)

- **Payload :** `LifecycleSignal` · **Format :** substrate SQLite (non-message)
- **Réf. normatives :** FR-002, FR-100 (heartbeat), FR-095/096 (claim)
- **Données :** `spawn/terminate`:—, `heartbeat`:âge, `claim/lease`:task_id+fencing, `budget`:halt

### indexer → (tous) — Index de code

- **Payload :** `CodeIndex` · **Format :** API de requête en mémoire/SQLite
- **Réf. normatives :** FR-020/022
- **Données :** `functions`:[{file,name,params,line}], `call_graph`:edges, `resolve_citation`:fn(file,symbol)->bool

### cartographer → (tous) — Carte de sécurité

- **Payload :** `SecurityMap` · **Format :** documents Markdown + digest JSON
- **Réf. normatives :** FR-030..035
- **Données :** `flows`:[{entry,chain,validated}], `entrypoints`:[], `trust_boundaries`:[]

### detector → triager — Candidat

- **Payload :** `Candidate` · **Format :** Pydantic/JSON ; import outils via SARIF
- **Réf. normatives :** FR-043, FR-090 (fingerprint), SARIF v2.1.0 (OASIS), MITRE CWE
- **Données :** `file`:str, `symbol`:str, `vuln_class`:CWE, `technique`:str, `description`:str, `fingerprint`:sha256(path|symbol|class)

### triager → validator — Verdict TP exploitable

- **Payload :** `Verdict + exploitability` · **Format :** Pydantic (gate = validation de schéma + résolution de citations)
- **Réf. normatives :** FR-087/088 (evidence gate), Constitution I
- **Données :** `fp`:fingerprint, `verdict`:'true-positive', `evidence`:{reachability, trust_boundary, impact : Citation}, `cwe`:CWE

### triager → reporter — Verdict confirmé

- **Payload :** `Verdict` · **Format :** Pydantic/JSON
- **Réf. normatives :** FR-050/054, CVSS 3.1, OWASP Top 10
- **Données :** `fp`:fingerprint, `verdict`:enum(5), `evidence`:{3 jambes}, `severity`:tier+CVSS, `cwe`:CWE, `owasp`:cat

### validator → reporter — Résultat d'exploitation

- **Payload :** `ExploitResult` · **Format :** JSON + PoC runnable
- **Réf. normatives :** FR-060/061/063, Constitution VII
- **Données :** `fp`:fingerprint, `exploited`:bool, `oracle`:sqlmap|nuclei|…|llm, `request`:str, `response`:extrait, `poc_path`:fichier .py

### reporter → (sortie) — Rapport de finding + rollup

- **Payload :** `FindingReport` · **Format :** Markdown ; export SARIF / OCSF / CycloneDX (SBOM)
- **Réf. normatives :** FR-075..084, SARIF v2.1.0, OCSF, CycloneDX
- **Données :** `title`:str, `cwe`:CWE, `severity`:tier+CVSS, `owasp`:cat, `repro`:étapes, `poc`:ref, `permalink`:file#Lx-Ly@sha

### coverage → detector — Tâche dirigée

- **Payload :** `Task` · **Format :** work queue (SQLite)
- **Réf. normatives :** FR-070, FR-094..099
- **Données :** `task_id`:stable, `title`:str, `role`:'detector', `priority`:int, `payload`:{}

### coverage → orchestrator — Couverture complète

- **Payload :** `CoverageComplete` · **Format :** flag substrate
- **Réf. normatives :** FR-071, Constitution VI
- **Données :** `coverage_complete`:bool, `items`:[{component,goal,state}]

