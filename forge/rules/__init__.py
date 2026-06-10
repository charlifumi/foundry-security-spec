"""Corpus de règles CodeGuard fédéré + récupération par base vectorielle (ADR-002).

- RuleStore : charge plusieurs corpus nommés (maison + tiers spécialisés), backends
  `exhaustive` (applique toutes les règles) ou `vector` (récupère les top-k pertinentes).
- EmbeddingProvider / VectorIndex : pluggables (fallback autonome sans dépendance).
"""
from .store import Rule, RuleStore

__all__ = ["Rule", "RuleStore"]
