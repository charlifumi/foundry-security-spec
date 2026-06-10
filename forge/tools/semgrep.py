"""Adaptateur Semgrep — exemple concret d'intégration d'oracle SAST.

Deux modes d'intégration, au choix :
  1. CLI local  : `semgrep scan --sarif` -> SARIF -> candidats normalisés (implémenté ici).
  2. Serveur MCP: le serveur MCP officiel de Semgrep (`semgrep-mcp` sur PyPI, ou le distant
     https://mcp.semgrep.ai) expose un outil `semgrep_scan`. Forge appelle cet outil MCP et
     normalise sa sortie SARIF de la même façon (voir docs/tool-integration.md).

Dégrade gracieusement : si `semgrep` n'est pas installé, `run()` renvoie [] et le Detector
retombe sur le corpus CodeGuard interne (NFR-005).
"""
from __future__ import annotations

import json
import subprocess

from .base import ToolAdapter
from .registry import CATALOG
from .sarif import sarif_to_candidates

_SPEC = next(t for t in CATALOG if t.id == "semgrep")


class SemgrepAdapter(ToolAdapter):
    spec = _SPEC

    def __init__(self, config: str = "auto"):
        self.config = config  # "auto" = règles managées ; ou un chemin de règles custom

    def run(self, path: str, timeout: float = 120.0, **_) -> list[dict]:
        if not self.available():
            return []
        try:
            proc = subprocess.run(
                ["semgrep", "scan", "--sarif", "--quiet", "--config", self.config, path],
                capture_output=True, text=True, timeout=timeout)
            sarif = json.loads(proc.stdout or "{}")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return []
        return sarif_to_candidates(sarif, "semgrep")

    # --- variante MCP (esquisse d'intégration) ---------------------------------
    def run_via_mcp(self, path: str, mcp_client) -> list[dict]:
        """Appelle l'outil `semgrep_scan` d'un serveur MCP Semgrep déjà connecté.

        `mcp_client` est un client MCP fourni par l'hôte (stdio `semgrep-mcp` ou HTTP
        `https://mcp.semgrep.ai`). On normalise la sortie SARIF comme en CLI.
        """
        result = mcp_client.call_tool("semgrep_scan", {"path": path, "config": self.config})
        sarif = result.get("sarif") or json.loads(result.get("content", "{}"))
        return sarif_to_candidates(sarif, "semgrep")
