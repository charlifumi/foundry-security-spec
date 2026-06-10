"""Work queue : claim atomique, lease lié au heartbeat, fencing token, auto-block.

Réalise FR-094..099 et la Constitution IV (claims atomiques et mortels).
Le protocole complet est décrit dans analysis.md §5.
"""
from __future__ import annotations

import json
import time
import uuid

from .db import DB
from .events import EventLog


class WorkQueue:
    def __init__(self, db: DB, events: EventLog, *, claim_max_retries: int = 3):
        self.db = db
        self.events = events
        self.N = claim_max_retries

    # ----- production de tâches -------------------------------------------------
    def add(self, title: str, *, description: str = "", role: str | None = None,
            priority: int = 100, queue: str = "main", payload: dict | None = None,
            task_id: str | None = None) -> str:
        tid = task_id or f"task-{uuid.uuid4().hex[:12]}"
        self.db.connect().execute(
            "INSERT OR IGNORE INTO tasks(task_id, queue, title, description, role, priority, "
            "payload, created_ts) VALUES (?,?,?,?,?,?,?,?)",
            (tid, queue, title, description, role, priority, json.dumps(payload or {}), time.time()),
        )
        return tid

    # ----- claim atomique (un seul gagnant) -------------------------------------
    def claim(self, agent_id: str, role: str, *, lease_ttl: float = 30.0,
              queue: str = "main") -> dict | None:
        """Tente de claimer une tâche ouverte adressée à `role` (ou non adressée).

        Compare-and-set transactionnel : deux agents concurrents reçoivent des
        tâches différentes, ou None (FR-095).
        """
        conn = self.db.connect()
        now = time.time()
        # Sélection d'une tâche candidate (la plus prioritaire, ouverte, du bon rôle).
        row = conn.execute(
            "SELECT task_id FROM tasks WHERE state='open' AND queue=? "
            "AND (role IS NULL OR role=?) ORDER BY priority, created_ts LIMIT 1",
            (queue, role),
        ).fetchone()
        if row is None:
            return None
        tid = row["task_id"]
        # CAS : ne gagne que si toujours 'open'. BEGIN IMMEDIATE sérialise les concurrents.
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "UPDATE tasks SET state='claimed', claimed_by=?, claim_ts=?, lease_until=?, "
                "fencing_token=fencing_token+1 WHERE task_id=? AND state='open'",
                (agent_id, now, now + lease_ttl, tid),
            )
            if cur.rowcount != 1:
                conn.execute("ROLLBACK")
                return None  # un autre agent a gagné ; on réessaiera
            task = conn.execute("SELECT * FROM tasks WHERE task_id=?", (tid,)).fetchone()
            conn.execute("UPDATE agents SET current_claim=? WHERE agent_id=?", (tid, agent_id))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        self.events.emit("claim", agent=agent_id, kind_task=tid)
        return {
            "task_id": task["task_id"], "title": task["title"], "description": task["description"],
            "role": task["role"], "payload": json.loads(task["payload"]),
            "fencing_token": task["fencing_token"],
        }

    def renew(self, task_id: str, agent_id: str, *, lease_ttl: float = 30.0) -> bool:
        """Renouvelle le lease (appelé au rythme du heartbeat)."""
        cur = self.db.connect().execute(
            "UPDATE tasks SET lease_until=? WHERE task_id=? AND claimed_by=? AND state='claimed'",
            (time.time() + lease_ttl, task_id, agent_id),
        )
        return cur.rowcount == 1

    # ----- complétion / libération ---------------------------------------------
    def complete(self, task_id: str, fencing_token: int) -> bool:
        """Clôt la tâche, garde-fou anti-zombie sur le fencing token (analysis.md §5.4)."""
        cur = self.db.connect().execute(
            "UPDATE tasks SET state='closed', claimed_by=NULL, lease_until=NULL "
            "WHERE task_id=? AND fencing_token=?",
            (task_id, fencing_token),
        )
        ok = cur.rowcount == 1
        if ok:
            self.events.emit("close", kind_task=task_id)
        return ok

    def release(self, task_id: str, agent_id: str):
        """Relâche volontairement (revient en open, ou blocked après N échecs, FR-097)."""
        conn = self.db.connect()
        row = conn.execute("SELECT release_count FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            return
        rc = row["release_count"] + 1
        new_state = "blocked" if rc >= self.N else "open"
        conn.execute(
            "UPDATE tasks SET state=?, claimed_by=NULL, lease_until=NULL, release_count=? "
            "WHERE task_id=? AND claimed_by=?",
            (new_state, rc, task_id, agent_id),
        )

    # ----- récupération des claims morts (superviseur) --------------------------
    def reclaim_expired(self) -> int:
        """Libère tout claim dont le lease a expiré (agent présumé mort, FR-096).

        Retourne le nombre de claims récupérés. C'est le mécanisme qui garantit
        qu'aucune unité n'est jamais bloquée par un agent mort (SC-004).
        """
        conn = self.db.connect()
        now = time.time()
        expired = conn.execute(
            "SELECT task_id, release_count FROM tasks WHERE state='claimed' AND lease_until < ?",
            (now,),
        ).fetchall()
        n = 0
        for r in expired:
            rc = r["release_count"] + 1
            new_state = "blocked" if rc >= self.N else "open"
            conn.execute(
                "UPDATE tasks SET state=?, claimed_by=NULL, lease_until=NULL, release_count=? "
                "WHERE task_id=? AND state='claimed' AND lease_until < ?",
                (new_state, rc, r["task_id"], now),
            )
            self.events.emit("reclaim", finding=None, kind_task=r["task_id"], new_state=new_state)
            n += 1
        return n

    # ----- introspection --------------------------------------------------------
    def counts(self) -> dict:
        rows = self.db.connect().execute(
            "SELECT state, COUNT(*) c FROM tasks GROUP BY state"
        ).fetchall()
        return {r["state"]: r["c"] for r in rows}

    def open_count(self, queue: str = "main") -> int:
        r = self.db.connect().execute(
            "SELECT COUNT(*) c FROM tasks WHERE state IN ('open','claimed') AND queue=?", (queue,)
        ).fetchone()
        return r["c"]
