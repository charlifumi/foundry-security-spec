"""VectorIndex : interface pluggable + backend brute-force autonome (cosine).

Backend par défaut `bruteforce` : aucune dépendance, cosine exact sur des vecteurs
normalisés. Production : sqlite-vec (reste dans le SQLite du substrate), FAISS, Chroma
ou pgvector — implémenter la même interface `add` / `search` (ADR-002).
"""
from __future__ import annotations


class VectorIndex:
    name = "bruteforce"

    def __init__(self):
        self._items: list[tuple[str, list[float], dict]] = []  # (id, vec, meta)

    def add(self, item_id: str, vector: list[float], meta: dict):
        self._items.append((item_id, vector, meta))

    def search(self, query: list[float], top_k: int = 5,
               where=None) -> list[tuple[str, float, dict]]:
        """Retourne [(id, score_cosine, meta)] trié par pertinence décroissante.

        `where(meta) -> bool` filtre (fédération : ne chercher que dans certains corpus).
        """
        scored = []
        for item_id, vec, meta in self._items:
            if where and not where(meta):
                continue
            score = sum(a * b for a, b in zip(query, vec))  # vecteurs normalisés -> cosine
            scored.append((item_id, score, meta))
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:top_k]

    def size(self) -> int:
        return len(self._items)
