# Forge — Librairie d'outils externes, par FONCTION du pipeline

> Pour chaque **fonction** du pipeline : où elle se branche (agent), ce qu'elle **injecte**, le **mode d'intégration**, et des outils *interchangeables* en exemple. Source exécutable : `forge/tools/registry.py` (panneau **🧰 Outils** du dashboard). État juin 2026.

Principe : le LLM raisonne ; les outils déterministes sont des **oracles**. Semgrep, sqlmap… ne sont que des exemples d'une fonction donnée.

## Modes d'intégration

| Mode | Comment Forge l'appelle |
|---|---|
| **CLI → SARIF** | lance le binaire, parse le SARIF (`forge/tools/sarif.py`) |
| **Serveur MCP** | l'hôte connecte le serveur ; l'agent appelle l'outil MCP, normalise la sortie |
| **API REST** | pilote l'API d'un démon (ex. ZAP) |
| **Librairie** | import direct (ex. tree-sitter dans l'Indexer) |

## Indexation & parsing  →  Indexer

- **Injecte dans le pipeline :** l'index de code (fonctions, graphe d'appels) que tous les rôles interrogent
- **Mode d'intégration :** librairie importée dans l'Indexer (frontend de parsing)

| Outil (exemple) | Intégration | Invocation | Injecte | MCP |
|---|---|---|---|---|
| [tree-sitter](https://tree-sitter.github.io) | `lib` | `import tree_sitter` | index | — |
| [universal-ctags](https://github.com/universal-ctags/ctags) | `cli` | `ctags -R --output-format=json` | index | — |

## Cartographie / surface d'attaque  →  Cartographe

- **Injecte dans le pipeline :** l'énumération des points d'entrée et paramètres (surface d'attaque, FR-031)
- **Mode d'intégration :** CLI ou API REST d'un démon ; les endpoints découverts enrichissent la carte

| Outil (exemple) | Intégration | Invocation | Injecte | MCP |
|---|---|---|---|---|
| [OWASP ZAP (spider)](https://www.zaproxy.org) | `rest` | `ZAP daemon, API REST /JSON/spider` | surface | — |
| [Arjun](https://github.com/s0md3v/Arjun) | `cli` | `arjun -u <url> -oJ -` | surface | — |
| [Katana](https://github.com/projectdiscovery/katana) | `cli` | `katana -u <url> -jsonl` | surface | — |

## Détection — secrets / credentials statiques  →  Detector

- **Injecte dans le pipeline :** des CANDIDATS (CWE-798) dans le finding store
- **Mode d'intégration :** CLI → SARIF/JSON, normalisé en candidats ; puis même evidence gate que le reste

| Outil (exemple) | Intégration | Invocation | Injecte | MCP |
|---|---|---|---|---|
| [Gitleaks](https://github.com/gitleaks/gitleaks) | `cli` | `gitleaks detect --report-format sarif --report-path -` | candidat | — |
| [TruffleHog](https://github.com/trufflesecurity/trufflehog) | `cli` | `trufflehog filesystem . --json` | candidat | — |
| [detect-secrets (Yelp)](https://github.com/Yelp/detect-secrets) | `cli` | `detect-secrets scan` | candidat | — |

## Détection — SAST (motifs de code)  →  Detector

- **Injecte dans le pipeline :** des CANDIDATS pré-étayés (pré-filtre haut-rappel avant raisonnement LLM)
- **Mode d'intégration :** CLI → SARIF, OU serveur MCP (ex. Semgrep) ; sortie normalisée en candidats

| Outil (exemple) | Intégration | Invocation | Injecte | MCP |
|---|---|---|---|---|
| [Semgrep](https://github.com/semgrep/mcp) | `mcp` | `semgrep scan --sarif  (ou outil MCP semgrep_scan)` | candidat | semgrep-mcp (PyPI) / https://mcp.semgrep.ai (officiel) |
| [Bandit](https://github.com/PyCQA/bandit) | `sarif` | `bandit -r . -f sarif` | candidat | — |
| [CodeQL (queries)](https://codeql.github.com) | `sarif` | `codeql database analyze --format=sarifv2.1.0` | candidat | — |

## Détection — composition / dépendances (SCA)  →  Detector

- **Injecte dans le pipeline :** des CANDIDATS (CWE-1035) + CVE/EPSS dans le finding store
- **Mode d'intégration :** CLI → SARIF/JSON sur les lockfiles ; priorisation par EPSS/KEV

| Outil (exemple) | Intégration | Invocation | Injecte | MCP |
|---|---|---|---|---|
| [OSV-Scanner](https://github.com/google/osv-scanner) | `sarif` | `osv-scanner scan --format sarif .` | candidat | — |
| [Grype](https://github.com/anchore/grype) | `sarif` | `grype dir:. -o sarif` | candidat | — |
| [Trivy](https://github.com/aquasecurity/trivy) | `sarif` | `trivy fs --format sarif -o - .` | candidat | — |

## Triage — taint / atteignabilité  →  Triager

- **Injecte dans le pipeline :** une PREUVE pour la jambe ATTEIGNABILITÉ de l'evidence gate (FR-087)
- **Mode d'intégration :** CLI (CPG/dataflow) → chemin source→sink ; renforce le gate au-delà des citations

| Outil (exemple) | Intégration | Invocation | Injecte | MCP |
|---|---|---|---|---|
| [CodeQL (taint)](https://codeql.github.com) | `sarif` | `codeql … (requêtes de taint)` | preuve | — |
| [Joern](https://joern.io) | `cli` | `joern-parse . ; joern --script q.sc` | preuve | — |

## Validation — exploitation live  →  Validator

- **Injecte dans le pipeline :** une PREUVE d'EXPLOITATION (flag exploited + PoC), oracle binaire
- **Mode d'intégration :** CLI ou API REST contre le testbed ; succès = impact observé (Constitution VII)

| Outil (exemple) | Intégration | Invocation | Injecte | MCP |
|---|---|---|---|---|
| [sqlmap](https://sqlmap.org) | `cli` | `sqlmap -u <url> --batch --dump` | exploitation | — |
| [Dalfox](https://github.com/hahwul/dalfox) | `cli` | `dalfox url <url> --format json` | exploitation | — |
| [Nuclei](https://github.com/projectdiscovery/nuclei) | `sarif` | `nuclei -u <url> -sarif-export -` | exploitation | — |
| [Commix](https://github.com/commixproject/commix) | `cli` | `commix -u <url> --batch` | exploitation | — |
| [OWASP ZAP (scan actif)](https://www.zaproxy.org) | `rest` | `ZAP daemon, API REST /JSON/ascan` | exploitation | — |

## Reporting / interopérabilité  →  Reporter

- **Injecte dans le pipeline :** l'EXPORT normalisé des findings (vers GitHub, IDE, vuln-management, SBOM)
- **Mode d'intégration :** format pivot SARIF/OCSF en sortie ; CycloneDX pour le SBOM

| Outil (exemple) | Intégration | Invocation | Injecte | MCP |
|---|---|---|---|---|
| [SARIF (OASIS)](https://sarifweb.azurewebsites.net) | `sarif` | `export runs/<id>/findings.sarif` | export | — |
| [CycloneDX](https://cyclonedx.org) | `cli` | `cyclonedx-py / syft -o cyclonedx` | export | — |
| [OCSF](https://schema.ocsf.io) | `sarif` | `export OCSF` | export | — |

## Exemple — recherche de credentials statiques

Fonction **secrets → Detector**. Outils interchangeables : **Gitleaks** (CLI→SARIF, rapide), **TruffleHog** (vérifie le secret en live), **detect-secrets**. Sortie normalisée en candidats CWE-798, puis **même evidence gate** que les findings du corpus CodeGuard.

## Exemple — intégration par serveur MCP (Semgrep)

Fonction **SAST → Detector**. Semgrep a un **serveur MCP officiel** (`semgrep/mcp`, PyPI `semgrep-mcp`, distant `https://mcp.semgrep.ai`). `forge/tools/semgrep.py` montre les deux voies : `run()` (CLI→SARIF) et `run_via_mcp()` (outil MCP `semgrep_scan`), même normalisation SARIF.

