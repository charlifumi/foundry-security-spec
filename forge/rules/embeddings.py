"""EmbeddingProvider : interface pluggable + repli déterministe sans dépendance.

Le repli utilise le *hashing trick* (feature hashing) sur des tokens de mots et des
tri-grammes de caractères, vecteur L2-normalisé de dimension fixe. C'est un vrai
embedding lexical, suffisant pour récupérer les règles pertinentes d'une fonction.

Production : brancher un modèle sémantique (sentence-transformers, ou via la passerelle
LiteLLM en local — cf. cost-and-routing.md) en implémentant la même interface.
"""
from __future__ import annotations

import hashlib
import math
import re

DIM = 256
_word = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]+")


def _stable_hash(tok: str) -> int:
    """Hash déterministe (stable entre processus, contrairement à hash())."""
    return int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "big")


def _tokens(text: str):
    t = text.lower()
    for w in _word.findall(t):
        yield w
    compact = re.sub(r"\s+", " ", t)
    for i in range(len(compact) - 2):  # tri-grammes de caractères
        yield compact[i:i + 3]


class EmbeddingProvider:
    """Interface : embed(text) -> list[float] (normalisé)."""

    name = "hashing-fallback"
    dim = DIM

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for tok in _tokens(text):
            h = _stable_hash(tok)
            vec[h % DIM] += 1.0
            vec[(h // DIM) % DIM] += 0.5  # second bucket = réduit les collisions
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
