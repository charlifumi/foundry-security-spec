"""Contexte partagé + harnais d'agent (boucle claim→handle→release + heartbeat).

Dans ce MVP, le fleet tourne en threads d'un même processus : les artefacts de
connaissance (index, carte) sont partagés en mémoire via `Context`, tandis que la
coordination (queue, findings, budget, events) passe par le substrate SQLite — c'est
là que vivent les invariants. La production isole chaque agent dans son processus/
conteneur (plan.md) ; la sémantique de claim/lease/fencing est identique.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Context:
    db: object
    queue: object
    findings: object
    budget: object
    events: object
    llm: object
    rulestore: object
    config: dict
    run_dir: str
    index: object = None
    security_map: dict = field(default_factory=dict)
    testbed_url: str | None = None
    coverage_complete: threading.Event = field(default_factory=threading.Event)
    stop: threading.Event = field(default_factory=threading.Event)
    extensions: dict = field(default_factory=dict)


class Worker(threading.Thread):
    """Une instance d'agent : boucle de claim, avec heartbeat sur une lane dédiée (FR-101)."""

    def __init__(self, role: str, instance_idx: int, ctx: Context,
                 handler: Callable[[dict, Context, str], list], *,
                 heartbeat_interval: float = 1.0, lease_ttl: float = 8.0, idle_sleep: float = 0.15):
        super().__init__(daemon=True, name=f"{role}-{instance_idx}")
        self.role = role
        self.agent_id = f"{role}-{instance_idx}"
        self.instance_idx = instance_idx
        self.ctx = ctx
        self.handler = handler
        self.heartbeat_interval = heartbeat_interval
        self.lease_ttl = lease_ttl
        self.idle_sleep = idle_sleep
        self._current_task = None
        self._hb_stop = threading.Event()

    # ----- heartbeat (lane dédiée, FR-100/101) ---------------------------------
    def _heartbeat_loop(self):
        while not self._hb_stop.is_set():
            now = time.time()
            self.ctx.db.connect().execute(
                "UPDATE agents SET last_heartbeat=? WHERE agent_id=?", (now, self.agent_id))
            if self._current_task:
                self.ctx.queue.renew(self._current_task, self.agent_id, lease_ttl=self.lease_ttl)
            self._hb_stop.wait(self.heartbeat_interval)

    # ----- boucle principale ----------------------------------------------------
    def run(self):
        self.ctx.db.connect().execute(
            "INSERT OR REPLACE INTO agents(agent_id, role, instance_idx, status, last_heartbeat, "
            "started_ts) VALUES (?,?,?, 'alive', ?, ?)",
            (self.agent_id, self.role, self.instance_idx, time.time(), time.time()))
        self.ctx.events.emit("spawn", agent=self.agent_id, role=self.role)
        hb = threading.Thread(target=self._heartbeat_loop, daemon=True)
        hb.start()
        try:
            while not self.ctx.stop.is_set():
                task = self.ctx.queue.claim(self.agent_id, self.role, lease_ttl=self.lease_ttl)
                if task is None:
                    time.sleep(self.idle_sleep)
                    continue
                self._current_task = task["task_id"]
                try:
                    follow = self.handler(task, self.ctx, self.agent_id) or []
                    for nt in follow:
                        self.ctx.queue.add(**nt)
                    self.ctx.queue.complete(task["task_id"], task["fencing_token"])
                except Exception as e:  # noqa: BLE001
                    self.ctx.events.emit("error", agent=self.agent_id, error=str(e),
                                         task=task["task_id"])
                    self.ctx.queue.release(task["task_id"], self.agent_id)
                finally:
                    self._current_task = None
                    self.ctx.db.connect().execute(
                        "UPDATE agents SET current_claim=NULL WHERE agent_id=?", (self.agent_id,))
        finally:
            self._hb_stop.set()
            self.ctx.db.connect().execute(
                "UPDATE agents SET status='retired' WHERE agent_id=?", (self.agent_id,))
            self.ctx.events.emit("retire", agent=self.agent_id)
