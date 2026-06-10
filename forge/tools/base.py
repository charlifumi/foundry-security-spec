"""Contrat d'intégration d'un outil externe.

Un adaptateur transforme un outil (CLI, serveur MCP, API REST) en une source de
*candidats* (Detector) ou de *preuves* (Triager/Validator), normalisés dans le schéma
Forge. Tous dégradent gracieusement si l'outil n'est pas installé (l'agent retombe sur
sa logique interne — NFR-005).
"""
from __future__ import annotations

import shutil

from .registry import ToolSpec


class ToolAdapter:
    spec: ToolSpec

    def available(self) -> bool:
        b = self.spec.bin
        return bool(b and shutil.which(b))

    def run(self, **kwargs) -> list[dict]:
        """Retourne une liste de candidats normalisés :
        {file, symbol, vuln_class (CWE), title, technique, description, line?}.
        """
        raise NotImplementedError
