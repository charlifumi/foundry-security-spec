"""Connexion SQLite et schéma du substrate.

Une base par run (runs/<id>/forge.db). WAL pour la concurrence ; busy_timeout
pour sérialiser les écritures concurrentes des agents.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

# Le schéma est le contrat de coordination. Chaque table réalise des FR de spec.md §7.
SCHEMA = """
-- Agents vivants et leur état (FR-008, FR-100).
CREATE TABLE IF NOT EXISTS agents (
    agent_id        TEXT PRIMARY KEY,
    role            TEXT NOT NULL,
    instance_idx    INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'alive',   -- alive | dead | retired
    last_heartbeat  REAL NOT NULL,
    current_claim   TEXT,
    restart_count   INTEGER NOT NULL DEFAULT 0,
    started_ts      REAL NOT NULL
);

-- Work queue : tâches ordonnées, claim atomique + lease + fencing (FR-094..099).
CREATE TABLE IF NOT EXISTS tasks (
    task_id        TEXT PRIMARY KEY,
    queue          TEXT NOT NULL DEFAULT 'main',
    title          TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    role           TEXT,                              -- rôle adressé (NULL = n'importe lequel)
    priority       INTEGER NOT NULL DEFAULT 100,
    state          TEXT NOT NULL DEFAULT 'open',      -- open | claimed | blocked | closed
    payload        TEXT NOT NULL DEFAULT '{}',        -- JSON spécifique à la tâche
    claimed_by     TEXT,
    claim_ts       REAL,
    lease_until    REAL,
    release_count  INTEGER NOT NULL DEFAULT 0,
    fencing_token  INTEGER NOT NULL DEFAULT 0,        -- anti-zombie (analysis.md §5.3)
    created_ts     REAL NOT NULL
);

-- Finding store : chaque finding à chaque stade, indexé par fingerprint (FR-090).
CREATE TABLE IF NOT EXISTS findings (
    fingerprint    TEXT PRIMARY KEY,                  -- sha256(path|symbol|class), sans ligne
    file           TEXT NOT NULL,
    symbol         TEXT NOT NULL,
    vuln_class     TEXT NOT NULL,                     -- CWE id
    title          TEXT NOT NULL DEFAULT '',
    state          TEXT NOT NULL DEFAULT 'candidate', -- candidate|verdict_assigned|confirmed|published
    verdict        TEXT,                              -- true-positive|false-positive|needs-review|not-applicable|code-quality
    exploited      INTEGER NOT NULL DEFAULT 0,
    technique      TEXT NOT NULL DEFAULT '',          -- rule:<id> | deps | secrets | exploratory
    description    TEXT NOT NULL DEFAULT '',
    evidence       TEXT NOT NULL DEFAULT '{}',        -- JSON: les 3 jambes du gate (FR-087)
    severity       TEXT,                              -- critical|high|medium|low
    cvss           REAL,
    cwe            TEXT,
    owasp          TEXT,
    poc_path       TEXT,
    created_ts     REAL NOT NULL,
    updated_ts     REAL NOT NULL
);

-- Couverture : items (composant × goal) avec leur barre (FR-067..071).
CREATE TABLE IF NOT EXISTS coverage (
    item_id     TEXT PRIMARY KEY,
    component   TEXT NOT NULL,
    goal        TEXT NOT NULL,
    bar         TEXT NOT NULL DEFAULT '',
    state       TEXT NOT NULL DEFAULT 'open',         -- open | covered
    evidence    TEXT NOT NULL DEFAULT '',
    updated_ts  REAL NOT NULL
);

-- Comptabilité LLM : une ligne par appel (cost-and-routing.md §2, FR-113).
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id        TEXT PRIMARY KEY,
    role           TEXT NOT NULL,
    instance       TEXT NOT NULL,
    correlation_id TEXT,                              -- fingerprint du finding, si applicable
    model          TEXT NOT NULL,
    provider       TEXT NOT NULL,
    input_tokens   INTEGER NOT NULL DEFAULT 0,
    output_tokens  INTEGER NOT NULL DEFAULT 0,
    cost_usd       REAL NOT NULL DEFAULT 0.0,
    cost_estimated INTEGER NOT NULL DEFAULT 0,
    ts             REAL NOT NULL
);

-- Operator messages dédupliqués (FR-102a..d).
CREATE TABLE IF NOT EXISTS messages (
    msg_id     TEXT PRIMARY KEY,
    agent      TEXT NOT NULL,
    kind       TEXT NOT NULL,                         -- blocker|request|feedback|info
    body       TEXT NOT NULL,
    dedup_hash TEXT NOT NULL,
    acked      INTEGER NOT NULL DEFAULT 0,
    ts         REAL NOT NULL
);

-- Journal d'événements : provenance (NFR-007) + flux dashboard (FR-122/123).
CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    agent      TEXT,
    finding    TEXT,
    kind       TEXT NOT NULL,
    payload    TEXT NOT NULL DEFAULT '{}'
);

-- État global du run (flags couverture/halt, méta).
CREATE TABLE IF NOT EXISTS run_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state, priority);
CREATE INDEX IF NOT EXISTS idx_findings_state ON findings(state, verdict);
CREATE INDEX IF NOT EXISTS idx_events_seq ON events(seq);
"""


class DB:
    """Fabrique de connexions SQLite thread-safe (une connexion par thread)."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        # Initialise le schéma une fois.
        conn = self.connect()
        conn.executescript(SCHEMA)
        conn.commit()

    def connect(self) -> sqlite3.Connection:
        """Retourne la connexion du thread courant (créée à la demande)."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.execute("PRAGMA foreign_keys=ON;")
            # WAL pour la concurrence ; repli si le système de fichiers ne le supporte pas
            # (certains montages réseau/FUSE). DELETE reste correct, juste moins concurrent.
            try:
                conn.execute("PRAGMA journal_mode=WAL;").fetchone()
                conn.execute("CREATE TABLE IF NOT EXISTS _wal_probe(x);")
                conn.execute("DROP TABLE IF EXISTS _wal_probe;")
            except sqlite3.OperationalError:
                conn.execute("PRAGMA journal_mode=DELETE;")
            self._local.conn = conn
        return conn
