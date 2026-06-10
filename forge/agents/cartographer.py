"""Cartographe — carte de sécurité (FR-030..036a).

Produit, à partir de l'index : architecture, surface d'attaque, et surtout la
**carte de flux** entrée → chaîne d'appels → sink avec l'état de validation à chaque
maillon (la demande de démo « chaînes d'appel / passage d'arguments / validation »).
"""
from __future__ import annotations

import os

# Points d'entrée (handlers HTTP) de la cible : sources de données non fiables.
ENTRY_HINTS = ("do_GET", "do_POST", "handle", "render_search", "view_profile",
               "diagnostic_ping", "fetch_image", "read_avatar", "load_preferences",
               "authenticate", "search_products", "login")


def run_cartographer(ctx) -> dict:
    idx = ctx.index
    ctx.events.emit("carto_start", agent="cartographer-0")

    # 1) Surface d'attaque : fonctions atteignant un sink (entrée -> ... -> sink).
    flows = []
    for fi in idx.all_functions():
        chains = idx.chains_from(fi.name)
        sink_chains = [c for c in chains if any(str(x).startswith("→sink:") for x in c)]
        if sink_chains and fi.name in ENTRY_HINTS:
            for c in sink_chains:
                # validation présente sur l'un des maillons internes ?
                validated = any(idx.validation_in(step) for step in c if not str(step).startswith("→sink:"))
                flows.append({"entry": fi.name, "file": fi.file, "chain": c, "validated": validated})

    # 2) Frontières de confiance : un flux non validé est une frontière non gardée.
    unguarded = [f for f in flows if not f["validated"]]

    security_map = {
        "components": sorted({fi.file for fi in idx.all_functions()}),
        "entrypoints": sorted({f["entry"] for f in flows}),
        "flows": flows,
        "unguarded_boundaries": len(unguarded),
    }
    ctx.security_map = security_map

    # 3) Persistance des documents de carte (FR-035) — lisibles par tous + dashboard.
    map_dir = os.path.join(ctx.run_dir, "map")
    os.makedirs(map_dir, exist_ok=True)
    lines = ["# Carte de sécurité — flux de données (entrée → sink)\n"]
    for f in flows:
        chain = " → ".join(str(x) for x in f["chain"])
        status = "✅ validé" if f["validated"] else "⚠️ NON validé (frontière non gardée)"
        lines.append(f"- **{f['entry']}** (`{f['file']}`) : {chain}  — {status}")
    with open(os.path.join(map_dir, "data-flow.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    ctx.events.emit("carto_ready", agent="cartographer-0",
                    entrypoints=len(security_map["entrypoints"]),
                    flows=len(flows), unguarded=len(unguarded))
    return security_map
