"""Tests du substrate — déterministes, sans LLM (NFR-004).

Vérifient les invariants de la constitution : claims atomiques et mortels,
fencing token, auto-block, fingerprint stable. Lancer : python -m tests.test_substrate
"""
import os
import tempfile
import threading
import time

from forge.substrate.db import DB
from forge.substrate.events import EventLog
from forge.substrate.findings import fingerprint
from forge.substrate.queue import WorkQueue


def _fresh():
    dbpath = os.path.join(tempfile.mkdtemp(), "forge.db")
    db = DB(dbpath)
    return db, WorkQueue(db, EventLog(db), claim_max_retries=3)


def _register(db, agent_id, role, idx):
    db.connect().execute(
        "INSERT INTO agents(agent_id,role,instance_idx,last_heartbeat,started_ts) VALUES(?,?,?,?,?)",
        (agent_id, role, idx, time.time(), time.time()),
    )


def test_atomic_claim_no_double():
    db, q = _fresh()
    for i in range(20):
        q.add(f"t-{i}", role="detector", priority=i)
    claimed, lock = [], threading.Lock()

    def worker(name):
        _register(db, name, "detector", 0)
        while True:
            t = q.claim(name, "detector", lease_ttl=30)
            if not t:
                break
            with lock:
                claimed.append(t["task_id"])
            q.complete(t["task_id"], t["fencing_token"])

    ths = [threading.Thread(target=worker, args=(f"detector-{n}",)) for n in range(8)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert len(claimed) == 20 and len(set(claimed)) == 20  # SC-004 / FR-095


def test_mortal_lease_reclaim():
    db, q = _fresh()
    q.add("orphan", role="triager", task_id="t-orphan")
    _register(db, "triager-0", "triager", 0)
    t = q.claim("triager-0", "triager", lease_ttl=0.5)
    assert t["task_id"] == "t-orphan"
    time.sleep(0.7)
    assert q.reclaim_expired() == 1  # FR-096
    assert db.connect().execute(
        "SELECT state FROM tasks WHERE task_id='t-orphan'").fetchone()["state"] == "open"


def test_fencing_token_rejects_zombie():
    db, q = _fresh()
    q.add("x", role="triager", task_id="t-x")
    _register(db, "a", "triager", 0)
    t1 = q.claim("a", "triager", lease_ttl=0.3)
    time.sleep(0.5)
    q.reclaim_expired()
    _register(db, "b", "triager", 1)
    t2 = q.claim("b", "triager", lease_ttl=30)
    assert q.complete("t-x", t1["fencing_token"]) is False   # zombie rejeté
    assert q.complete("t-x", t2["fencing_token"]) is True


def test_auto_block_after_N():
    db, q = _fresh()
    q.add("hard", role="detector", task_id="t-hard")
    _register(db, "d", "detector", 0)
    for _ in range(3):
        q.claim("d", "detector")
        q.release("t-hard", "d")
    assert db.connect().execute(
        "SELECT state FROM tasks WHERE task_id='t-hard'").fetchone()["state"] == "blocked"  # FR-097


def test_fingerprint_stable():
    assert fingerprint("auth.py", "login", "CWE-89") == fingerprint("auth.py", "login", "CWE-89")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"OK {name}")
    print("=== substrate: tous les tests passent ===")
