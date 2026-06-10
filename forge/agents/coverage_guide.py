"""Coverage-Guide — checklist (composant × goal) + signal couverture-complète (FR-067..074).

Ne détecte/triage/valide jamais elle-même (FR-072) : elle lit, juge, et pose le flag.
« Crédiblement tenté » = le balayage de détection du composant est terminé (FR-069).
"""
from __future__ import annotations

import time


def init_coverage(ctx):
    """Dérive la checklist depuis les goals × composants (FR-067). N'invente pas de goals (FR-068)."""
    goals = ctx.config.get("goals") or ""
    if not goals.strip():
        return  # attend des goals réels
    goal_label = "objectifs d'évaluation"
    components = ctx.security_map.get("components") or sorted(
        {f.file for f in ctx.index.all_functions()})
    conn = ctx.db.connect()
    for comp in components:
        conn.execute(
            "INSERT OR IGNORE INTO coverage(item_id, component, goal, bar, state, updated_ts) "
            "VALUES (?,?,?,?, 'open', ?)",
            (f"cov-{comp}", comp, goal_label, "balayage de détection terminé", time.time()))


def review(ctx) -> bool:
    """Coche les items dont le composant a été balayé ; pose le flag si tout est couvert."""
    conn = ctx.db.connect()
    # un composant est couvert si toutes ses tâches de détection sont closes
    open_detect = conn.execute(
        "SELECT COUNT(*) c FROM tasks WHERE title LIKE 'detect%' AND state NOT IN ('closed','blocked')"
    ).fetchone()["c"]
    if open_detect == 0:
        conn.execute("UPDATE coverage SET state='covered', updated_ts=? WHERE state='open'",
                     (time.time(),))
    remaining = conn.execute(
        "SELECT COUNT(*) c FROM coverage WHERE state='open'").fetchone()["c"]
    total = conn.execute("SELECT COUNT(*) c FROM coverage").fetchone()["c"]
    if total > 0 and remaining == 0:
        if not ctx.coverage_complete.is_set():
            ctx.coverage_complete.set()
            conn.execute("INSERT OR REPLACE INTO run_state(key,value) VALUES('coverage_complete','1')")
            ctx.events.emit("coverage_complete", covered=total)
        return True
    return False
