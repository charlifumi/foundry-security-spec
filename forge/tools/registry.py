"""Catalogue d'outils externes intégrables, organisé PAR FONCTION DU PIPELINE.

La question n'est pas « quels outils » mais « pour quelle **fonction** du pipeline, et
**comment** les brancher ». Chaque fonction (parsing, secrets, SAST, SCA, taint, surface,
exploitation, reporting) a un point d'intégration précis (quel agent, ce que l'outil
**injecte** : candidat / preuve pour le gate / exploitation / surface) et un **mécanisme**
d'intégration générique (CLI→SARIF, serveur MCP, API REST, librairie). Semgrep, sqlmap, etc.
ne sont que des *exemples* interchangeables de chaque fonction.

Principe : le LLM raisonne, les outils déterministes sont des oracles. État : juin 2026.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass

# ── Les FONCTIONS du pipeline : le point d'intégration, indépendant de l'outil ──
FUNCTIONS: dict[str, dict] = {
    "index": {
        "label": "Indexing & parsing",
        "agent": "Indexer",
        "feeds": "the code index (functions, call graph) queried by every role",
        "how": "library imported in the Indexer (parsing frontend)",
    },
    "surface": {
        "label": "Mapping / attack surface",
        "agent": "Cartographe",
        "feeds": "enumeration of entry points and parameters (attack surface, FR-031)",
        "how": "CLI or a daemon's REST API; discovered endpoints enrich the map",
    },
    "secrets": {
        "label": "Detection — static secrets / credentials",
        "agent": "Detector",
        "feeds": "CANDIDATES (CWE-798) into the finding store",
        "how": "CLI → SARIF/JSON, normalized into candidates; then the same evidence gate as the rest",
    },
    "sast": {
        "label": "Detection — SAST (code patterns)",
        "agent": "Detector",
        "feeds": "pre-substantiated CANDIDATES (high-recall pre-filter before LLM reasoning)",
        "how": "CLI → SARIF, OR MCP server (e.g. Semgrep); output normalized into candidates",
    },
    "sca": {
        "label": "Detection — composition / dependencies (SCA)",
        "agent": "Detector",
        "feeds": "CANDIDATES (CWE-1035) + CVE/EPSS into the finding store",
        "how": "CLI → SARIF/JSON over lockfiles; prioritized by EPSS/KEV",
    },
    "taint": {
        "label": "Triage — taint / reachability",
        "agent": "Triager",
        "feeds": "EVIDENCE for the REACHABILITY leg of the evidence gate (FR-087)",
        "how": "CLI (CPG/dataflow) → source→sink path; strengthens the gate beyond citations",
    },
    "exploit": {
        "label": "Validation — live exploitation",
        "agent": "Validator",
        "feeds": "EXPLOITATION EVIDENCE (exploited flag + PoC), a binary oracle",
        "how": "CLI or REST API against the testbed; success = observed impact (Constitution VII)",
    },
    "report": {
        "label": "Reporting / interoperability",
        "agent": "Reporter",
        "feeds": "normalized EXPORT of findings (to GitHub, IDE, vuln-management, SBOM)",
        "how": "SARIF/OCSF pivot format on output; CycloneDX for the SBOM",
    },
}


@dataclass
class ToolSpec:
    id: str
    function: str        # clé dans FUNCTIONS — la fonction du pipeline servie
    name: str
    task: str            # ce que l'outil fait précisément
    integration: str     # cli | sarif | mcp | rest | lib
    invoke: str          # commande type ou endpoint
    produces: str        # candidat | preuve | exploitation | surface | index | export
    normalize: str       # comment sa sortie rejoint le pipeline
    bin: str | None      # binaire testé pour la disponibilité locale
    mcp: str | None      # serveur MCP, si disponible
    homepage: str

    @property
    def role(self) -> str:
        return {"index": "indexer", "surface": "cartographer", "secrets": "detector",
                "sast": "detector", "sca": "detector", "taint": "triager",
                "exploit": "validator", "report": "reporter"}[self.function]


# ── Le catalogue : plusieurs outils interchangeables par fonction ──────────────
CATALOG: list[ToolSpec] = [
    # Indexation & parsing
    ToolSpec("tree-sitter", "index", "tree-sitter",
             "Deterministic multi-language parsing", "lib", "import tree_sitter",
             "index", "frontend de l'Indexer (remplace l'AST mono-langage, FR-020)",
             None, None, "https://tree-sitter.github.io"),
    ToolSpec("ctags", "index", "universal-ctags",
             "Lightweight symbol index, 40+ languages", "cli", "ctags -R --output-format=json",
             "index", "symboles -> table de fonctions de l'index",
             "ctags", None, "https://github.com/universal-ctags/ctags"),

    # Cartographie / surface d'attaque
    ToolSpec("owasp-zap-spider", "surface", "OWASP ZAP (spider)",
             "Endpoint discovery on a live app", "rest", "ZAP daemon, API REST /JSON/spider",
             "surface", "endpoints -> énumération de surface d'attaque (FR-031)",
             "zap.sh", None, "https://www.zaproxy.org"),
    ToolSpec("arjun", "surface", "Arjun",
             "Hidden HTTP parameter discovery", "cli", "arjun -u <url> -oJ -",
             "surface", "paramètres -> surface enrichie",
             "arjun", None, "https://github.com/s0md3v/Arjun"),
    ToolSpec("katana", "surface", "Katana",
             "Fast crawler to map routes", "cli", "katana -u <url> -jsonl",
             "surface", "routes -> points d'entrée de la carte",
             "katana", None, "https://github.com/projectdiscovery/katana"),

    # Détection — secrets
    ToolSpec("gitleaks", "secrets", "Gitleaks",
             "Static secrets/credentials (regex+entropy, git history)", "cli",
             "gitleaks detect --report-format sarif --report-path -",
             "candidat", "results SARIF -> candidats CWE-798", "gitleaks", None,
             "https://github.com/gitleaks/gitleaks"),
    ToolSpec("trufflehog", "secrets", "TruffleHog",
             "Secrets with live validity VERIFICATION", "cli", "trufflehog filesystem . --json",
             "candidat", "secret 'verified' -> candidat CWE-798 à forte confiance",
             "trufflehog", None, "https://github.com/trufflesecurity/trufflehog"),
    ToolSpec("detect-secrets", "secrets", "detect-secrets (Yelp)",
             "Pre-commit secrets, auditable baseline", "cli", "detect-secrets scan",
             "candidat", "results JSON -> candidats CWE-798",
             "detect-secrets", None, "https://github.com/Yelp/detect-secrets"),

    # Détection — SAST
    ToolSpec("semgrep", "sast", "Semgrep",
             "Pattern SAST (30+ languages, 5000+ rules, dataflow)", "mcp",
             "semgrep scan --sarif  (ou outil MCP semgrep_scan)",
             "candidat", "SARIF -> candidats avant raisonnement LLM (pré-filtre haut-rappel)",
             "semgrep", "semgrep-mcp (PyPI) / https://mcp.semgrep.ai (officiel)",
             "https://github.com/semgrep/mcp"),
    ToolSpec("bandit", "sast", "Bandit",
             "Python-specific SAST (exec, pickle, subprocess…)", "sarif", "bandit -r . -f sarif",
             "candidat", "results -> candidats (complète le corpus CodeGuard sur Python)",
             "bandit", None, "https://github.com/PyCQA/bandit"),
    ToolSpec("codeql-sast", "sast", "CodeQL (queries)",
             "Deep semantic analysis, custom queries", "sarif",
             "codeql database analyze --format=sarifv2.1.0",
             "candidat", "results SARIF -> candidats à haute précision",
             "codeql", None, "https://codeql.github.com"),

    # Détection — SCA
    ToolSpec("osv-scanner", "sca", "OSV-Scanner",
             "Dependencies vs OSV.dev (20+ sources)", "sarif", "osv-scanner scan --format sarif .",
             "candidat", "vulns -> candidats CWE-1035 + CVE", "osv-scanner", None,
             "https://github.com/google/osv-scanner"),
    ToolSpec("grype", "sca", "Grype",
             "SCA + EPSS scores (exploitation probability) + CISA KEV", "sarif", "grype dir:. -o sarif",
             "candidat", "candidats CWE-1035 priorisés par EPSS/KEV", "grype", None,
             "https://github.com/anchore/grype"),
    ToolSpec("trivy", "sca", "Trivy",
             "SCA + IaC + secrets in one binary", "sarif", "trivy fs --format sarif -o - .",
             "candidat", "results -> candidats (deps, IaC, secrets)", "trivy", None,
             "https://github.com/aquasecurity/trivy"),

    # Triage — taint / atteignabilité
    ToolSpec("codeql-taint", "taint", "CodeQL (taint)",
             "Inter-procedural source→sink flow analysis", "sarif",
             "codeql … (requêtes de taint)",
             "preuve", "confirme mécaniquement la jambe ATTEIGNABILITÉ du gate (FR-087)",
             "codeql", None, "https://codeql.github.com"),
    ToolSpec("joern", "taint", "Joern",
             "Code Property Graph, flow queries", "cli", "joern-parse . ; joern --script q.sc",
             "preuve", "prouve un chemin réel entrée→sink pour le gate", "joern", None,
             "https://joern.io"),

    # Validation — exploitation live
    ToolSpec("sqlmap", "exploit", "sqlmap",
             "Detection AND exploitation of SQL injections", "cli", "sqlmap -u <url> --batch --dump",
             "exploitation", "exploitation confirmée -> flag exploited + PoC", "sqlmap", None,
             "https://sqlmap.org"),
    ToolSpec("dalfox", "exploit", "Dalfox",
             "XSS detection/exploitation", "cli", "dalfox url <url> --format json",
             "exploitation", "payload XSS confirmé -> flag exploited", "dalfox", None,
             "https://github.com/hahwul/dalfox"),
    ToolSpec("nuclei", "exploit", "Nuclei",
             "Template probes (CVEs, exposures)", "sarif", "nuclei -u <url> -sarif-export -",
             "exploitation", "match de template -> preuve d'exploitabilité (oracle)", "nuclei",
             None, "https://github.com/projectdiscovery/nuclei"),
    ToolSpec("commix", "exploit", "Commix",
             "Command-injection exploitation", "cli", "commix -u <url> --batch",
             "exploitation", "commande exécutée -> flag exploited", "commix", None,
             "https://github.com/commixproject/commix"),
    ToolSpec("owasp-zap-active", "exploit", "OWASP ZAP (scan actif)",
             "Directed attacks on a live app", "rest", "ZAP daemon, API REST /JSON/ascan",
             "exploitation", "alerte confirmée -> preuve d'exploitabilité", "zap.sh", None,
             "https://www.zaproxy.org"),

    # Reporting / interop
    ToolSpec("sarif", "report", "SARIF (OASIS)",
             "Findings pivot format (tool import, GitHub/IDE export)", "sarif",
             "export runs/<id>/findings.sarif",
             "export", "normalise l'entrée des oracles et l'export downstream", None, None,
             "https://sarifweb.azurewebsites.net"),
    ToolSpec("cyclonedx", "report", "CycloneDX",
             "Exportable SBOM (software inventory)", "cli", "cyclonedx-py / syft -o cyclonedx",
             "export", "SBOM joint au rapport pour la traçabilité supply-chain", None, None,
             "https://cyclonedx.org"),
    ToolSpec("ocsf", "report", "OCSF",
             "Security event schema (SOC interop)", "sarif", "export OCSF",
             "export", "findings -> pipeline SOC/SIEM", None, None,
             "https://schema.ocsf.io"),
]


def functions() -> list[dict]:
    """Les fonctions du pipeline, dans l'ordre, avec leur point d'intégration."""
    return [{"id": k, **v} for k, v in FUNCTIONS.items()]


def catalog() -> list[dict]:
    """Catalogue sérialisable + disponibilité locale, pour le dashboard et la doc."""
    out = []
    for t in CATALOG:
        out.append({
            "id": t.id, "function": t.function, "name": t.name, "task": t.task,
            "role": t.role, "integration": t.integration, "invoke": t.invoke,
            "produces": t.produces, "normalize": t.normalize, "mcp": t.mcp,
            "homepage": t.homepage,
            "available": bool(t.bin and shutil.which(t.bin)) if t.bin else None,
        })
    return out
