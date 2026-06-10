"""Index de code : inventaire déterministe des fonctions + résolution de citations.

Frontend par défaut : module `ast` de la stdlib (Python). FR-020/022 : l'inventaire
vient d'un parser déterministe, jamais d'un LLM seul. tree-sitter est le frontend
multi-langage de production (voir plan.md) ; ici, ast suffit pour la cible Python.
"""
from .indexer import CodeIndex, FunctionInfo

__all__ = ["CodeIndex", "FunctionInfo"]
