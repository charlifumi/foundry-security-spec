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
        "label": "Indexation & parsing",
        "agent": "Indexer",
        "feeds": "l'index de code (fonctions, graphe d'appels) que tous les rôles interrogent",
        "how": "librairie importée dans l'Indexer (frontend de parsing)",
    },
    "surface": {
        "label": "Cartographie / surface d'attaque",
        "agent": "Cartographe",
        "feeds": "l'énumération des points d'entrée et paramètres (surface d'attaque, FR-031)",
        "how": "CLI ou API REST d'un démon ; les endpoints découverts enrichissent la carte",
    },
    "secrets": {
        "label": "Détection — secrets / credentials statiques",
        "agent": "Detector",
        "feeds": "des CANDIDATS (CWE-798) dans le finding store",
        "how": "CLI → SARIF/JSON, normalisé en candidats ; puis même evidence gate que le reste",
    },
    "sast": {
        "label": "Détection — SAST (motifs de code)",
        "agent": "Detector",
        "feeds": "des CANDIDATS pré-étayés (pré-filtre haut-rappel avant raisonnement LLM)",
        "how": "CLI → SARIF, OU serveur MCP (ex. Semgrep) ; sortie normalisée en candidats",
    },
    "sca": {
        "label": "Détection — composition / dépendances (SCA)",
        "agent": "Detector",
        "feeds": "des CANDIDATS (CWE-1035) + CVE/EPSS dans le finding store",
        "how": "CLI → SARIF/JSON sur les lockfiles ; priorisation par EPSS/KEV",
    },
    "taint": {
        "label": "Triage — taint / atteignabilité",
        "agent": "Triager",
        "feeds": "une PREUVE pour la jambe ATTEIGNABILITÉ de l'evidence gate (FR-087)",
        "how": "CLI (CPG/dataflow) → chemin source→sink ; renforce le gate au-delà des citations",
    },
    "exploit": {
        "label": "Validation — exploitation live",
        "agent": "Validator",
        "feeds": "une PREUVE d'EXPLOITATION (flag exploited + PoC), oracle binaire",
        "how": "CLI ou API REST contre le testbed ; succès = impact observé (Constitution VII)",
    },
    "report": {
        "label": "Reporting / interopérabilité",
        "agent": "Reporter",
        "feeds": "l'EXPORT normalisé des findings (vers GitHub, IDE, vuln-management, SBOM)",
        "how": "format pivot SARIF/OCSF en sortie ; CycloneDX pour le SBOM",
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
             "Parsing déterministe multi-langage", "lib", "import tree_sitter",
             "index", "frontend de l'Indexer (remplace l'AST mono-langage, FR-020)",
             None, None, "https://tree-sitter.github.io"),
    ToolSpec("ctags", "index", "universal-ctags",
             "Index de symboles léger, 40+ langages", "cli", "ctags -R --output-format=json",
             "index", "symboles -> table de fonctions de l'index",
             "ctags", None, "https://github.com/universal-ctags/ctags"),

    # Cartographie / surface d'attaque
    ToolSpec("owasp-zap-spider", "surface", "OWASP ZAP (spider)",
             "Découverte d'endpoints d'une app live", "rest", "ZAP daemon, API REST /JSON/spider",
             "surface", "endpoints -> énumération de surface d'attaque (FR-031)",
             "zap.sh", None, "https://www.zaproxy.org"),
    ToolSpec("arjun", "surface", "Arjun",
             "Découverte de paramètres HTTP cachés", "cli", "arjun -u <url> -oJ -",
             "surface", "paramètres -> surface enrichie",
             "arjun", None, "https://github.com/s0md3v/Arjun"),
    ToolSpec("katana", "surface", "Katana",
             "Crawler rapide pour cartographier les routes", "cli", "katana -u <url> -jsonl",
             "surface", "routes -> points d'entrée de la carte",
             "katana", None, "https://github.com/projectdiscovery/katana"),

    # Détection — secrets
    ToolSpec("gitleaks", "secrets", "Gitleaks",
             "Secrets/credentials statiques (regex+entropie, historique git)", "cli",
             "gitleaks detect --report-format sarif --report-path -",
             "candidat", "results SARIF -> candidats CWE-798", "gitleaks", None,
             "https://github.com/gitleaks/gitleaks"),
    ToolSpec("trufflehog", "secrets", "TruffleHog",
             "Secrets avec VÉRIFICATION live de validité", "cli", "trufflehog filesystem . --json",
             "candidat", "secret 'verified' -> candidat CWE-798 à forte confiance",
             "trufflehog", None, "https://github.com/trufflesecurity/trufflehog"),
    ToolSpec("detect-secrets", "secrets", "detect-secrets (Yelp)",
             "Secrets en pré-commit, baseline auditable", "cli", "detect-secrets scan",
             "candidat", "results JSON -> candidats CWE-798",
             "detect-secrets", None, "https://github.com/Yelp/detect-secrets"),

    # Détection — SAST
    ToolSpec("semgrep", "sast", "Semgrep",
             "SAST par motifs (30+ langages, 5000+ règles, dataflow)", "mcp",
             "semgrep scan --sarif  (ou outil MCP semgrep_scan)",
             "candidat", "SARIF -> candidats avant raisonnement LLM (pré-filtre haut-rappel)",
             "semgrep", "semgrep-mcp (PyPI) / https://mcp.semgrep.ai (officiel)",
             "https://github.com/semgrep/mcp"),
    ToolSpec("bandit", "sast", "Bandit",
             "SAST spécifique Python (exec, pickle, subprocess…)", "sarif", "bandit -r . -f sarif",
             "candidat", "results -> candidats (complète le corpus CodeGuard sur Python)",
             "bandit", None, "https://github.com/PyCQA/bandit"),
    ToolSpec("codeql-sast", "sast", "CodeQL (queries)",
             "Analyse sémantique profonde, requêtes custom", "sarif",
             "codeql database analyze --format=sarifv2.1.0",
             "candidat", "results SARIF -> candidats à haute précision",
             "codeql", None, "https://codeql.github.com"),

    # Détection — SCA
    ToolSpec("osv-scanner", "sca", "OSV-Scanner",
             "Dépendances vs OSV.dev (20+ sources)", "sarif", "osv-scanner scan --format sarif .",
             "candidat", "vulns -> candidats CWE-1035 + CVE", "osv-scanner", None,
             "https://github.com/google/osv-scanner"),
    ToolSpec("grype", "sca", "Grype",
             "SCA + scores EPSS (proba d'exploitation) + CISA KEV", "sarif", "grype dir:. -o sarif",
             "candidat", "candidats CWE-1035 priorisés par EPSS/KEV", "grype", None,
             "https://github.com/anchore/grype"),
    ToolSpec("trivy", "sca", "Trivy",
             "SCA + IaC + secrets en un binaire", "sarif", "trivy fs --format sarif -o - .",
             "candidat", "results -> candidats (deps, IaC, secrets)", "trivy", None,
             "https://github.com/aquasecurity/trivy"),

    # Triage — taint / atteignabilité
    ToolSpec("codeql-taint", "taint", "CodeQL (taint)",
             "Analyse de flux source→sink inter-procédurale", "sarif",
             "codeql … (requêtes de taint)",
             "preuve", "confirme mécaniquement la jambe ATTEIGNABILITÉ du gate (FR-087)",
             "codeql", None, "https://codeql.github.com"),
    ToolSpec("joern", "taint", "Joern",
             "Code Property Graph, requêtes de flux", "cli", "joern-parse . ; joern --script q.sc",
             "preuve", "prouve un chemin réel entrée→sink pour le gate", "joern", None,
             "https://joern.io"),

    # Validation — exploitation live
    ToolSpec("sqlmap", "exploit", "sqlmap",
             "Détection ET exploitation d'injections SQL", "cli", "sqlmap -u <url> --batch --dump",
             "exploitation", "exploitation confirmée -> flag exploited + PoC", "sqlmap", None,
             "https://sqlmap.org"),
    ToolSpec("dalfox", "exploit", "Dalfox",
             "Détection/exploitation de XSS", "cli", "dalfox url <url> --format json",
             "exploitation", "payload XSS confirmé -> flag exploited", "dalfox", None,
             "https://github.com/hahwul/dalfox"),
    ToolSpec("nuclei", "exploit", "Nuclei",
             "Sondes par templates (CVE, expositions)", "sarif", "nuclei -u <url> -sarif-export -",
             "exploitation", "match de template -> preuve d'exploitabilité (oracle)", "nuclei",
             None, "https://github.com/projectdiscovery/nuclei"),
    ToolSpec("commix", "exploit", "Commix",
             "Exploitation d'injections de commande", "cli", "commix -u <url> --batch",
             "exploitation", "commande exécutée -> flag exploited", "commix", None,
             "https://github.com/commixproject/commix"),
    ToolSpec("owasp-zap-active", "exploit", "OWASP ZAP (scan actif)",
             "Attaques dirigées sur une app live", "rest", "ZAP daemon, API REST /JSON/ascan",
             "exploitation", "alerte confirmée -> preuve d'exploitabilité", "zap.sh", None,
             "https://www.zaproxy.org"),

    # Reporting / interop
    ToolSpec("sarif", "report", "SARIF (OASIS)",
             "Format pivot des findings (import outils, export GitHub/IDE)", "sarif",
             "export runs/<id>/findings.sarif",
             "export", "normalise l'entrée des oracles et l'export downstream", None, None,
             "https://sarifweb.azurewebsites.net"),
    ToolSpec("cyclonedx", "report", "CycloneDX",
             "SBOM (inventaire logiciel) exportable", "cli", "cyclonedx-py / syft -o cyclonedx",
             "export", "SBOM joint au rapport pour la traçabilité supply-chain", None, None,
             "https://cyclonedx.org"),
    ToolSpec("ocsf", "report", "OCSF",
             "Schéma d'événements de sécurité (interop SOC)", "sarif", "export OCSF",
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
