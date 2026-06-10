"""Journal d'événements : provenance (NFR-007) et flux pour le dashboard."""
from __future__ import annotations

import json
import time

from .db import DB


class EventLog:
    def __init__(self, db: DB):
        self.db = db

    def emit(self, kind: str, agent: str | None = None, finding: str | None = None, **payload):
        self.db.connect().execute(
            "INSERT INTO events(ts, agent, finding, kind, payload) VALUES (?,?,?,?,?)",
            (time.time(), agent, finding, kind, json.dumps(payload)),
        )

    def since(self, seq: int, limit: int = 500):
        rows = self.db.connect().execute(
            "SELECT seq, ts, agent, finding, kind, payload FROM events WHERE seq > ? ORDER BY seq LIMIT ?",
            (seq, limit),
        ).fetchall()
        return [
            {
                "seq": r["seq"], "ts": r["ts"], "agent": r["agent"],
                "finding": r["finding"], "kind": r["kind"], "payload": json.loads(r["payload"]),
            }
            for r in rows
        ]
