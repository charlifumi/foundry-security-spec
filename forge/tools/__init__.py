"""Registre d'outils externes intégrables + adaptateurs.

`registry.py` : le catalogue (outil → tâche → agent → mode d'intégration : CLI/SARIF/MCP/REST).
`base.py`     : l'interface `ToolAdapter` (contrat d'intégration, normalisation vers nos candidats).
`semgrep.py`  : un adaptateur concret (CLI `--sarif`, ou serveur MCP officiel).
`sarif.py`    : normalisation SARIF -> candidats Forge (format pivot commun à la plupart des outils).
"""
from .registry import CATALOG, FUNCTIONS, ToolSpec, catalog, functions

__all__ = ["CATALOG", "FUNCTIONS", "ToolSpec", "catalog", "functions"]
