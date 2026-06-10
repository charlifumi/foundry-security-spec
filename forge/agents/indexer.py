"""Indexer — construit l'index de code (FR-020..024). Gate le fleet (FR-003)."""
from __future__ import annotations

import os

from ..index import CodeIndex


def run_indexer(ctx) -> bool:
    """Construit l'index et signale 'queryable'. Appelé par l'Orchestrateur avant le fleet."""
    ctx.events.emit("index_start", agent="indexer-0")
    src = ctx.config["target"]["source"]
    idx = CodeIndex().build(src)
    ctx.index = idx
    n = idx.function_count()
    ctx.db.connect().execute(
        "INSERT OR REPLACE INTO run_state(key,value) VALUES ('index_functions', ?)", (str(n),))
    ctx.events.emit("index_ready", agent="indexer-0", functions=n,
                    files=len(idx.functions))
    return n > 0  # 'queryable' (FR-024)
