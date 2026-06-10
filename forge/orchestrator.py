"""Orchestrateur — cycle de vie du fleet (FR-002..012) + supervision.

Séquence (spec.md §4.4) : testbed -> index (gate FR-003) -> cartographe -> seed des
tâches -> spawn du fleet -> supervision (reclaim claims morts, review couverture, halt
budget) -> drain -> rollup.
"""
from __future__ import annotations

import os
import time
import uuid

from . import config as cfgmod
from .agents import (cartographer, coverage_guide, detector, indexer, reporter,
                     triager, validator)
from .agents.base import Context, Worker
from .llm import RATE_CARD, LLMProvider
from .rules import RuleStore
from .rules.embeddings import EmbeddingProvider
from .rules.vector_index import VectorIndex
from .substrate.budget import Budget
from .substrate.db import DB
from .substrate.events import EventLog
from .substrate.findings import FindingStore
from .substrate.queue import WorkQueue

HANDLERS = {"detector": detector.handle, "triager": triager.handle,
            "validator": validator.handle, "reporter": reporter.handle}

# Contexte actif (exposé au dashboard, même processus).
ACTIVE: Context | None = None


def setup(cfg: dict) -> tuple[Context, object]:
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    runs_root = os.environ.get("FORGE_RUNS_DIR", os.path.join(cfgmod.REPO_ROOT, "runs"))
    run_dir = os.path.join(runs_root, run_id)
    os.makedirs(run_dir, exist_ok=True)
    db = DB(os.path.join(run_dir, "forge.db"))
    events = EventLog(db)
    queue = WorkQueue(db, events, claim_max_retries=3)
    findings = FindingStore(db, events)
    b = cfg["budget"]
    budget = Budget(db, events, spend_cap_usd=b["spend_cap_usd"], time_cap_min=b["time_cap_min"],
                    yield_threshold=b["yield_threshold"], window_usd=b["window_usd"],
                    min_runtime_min=b["min_runtime_min"])
    llm = LLMProvider(budget, mode=cfg["llm"]["provider"], model=cfg["llm"]["model"],
                      rate_card=RATE_CARD)
    rs = RuleStore(backend=cfg["detection"]["rule_backend"],
                   embedder=EmbeddingProvider(), index=VectorIndex())
    rs.load_dir(cfg["detection"]["corpora"])
    ctx = Context(db=db, queue=queue, findings=findings, budget=budget, events=events,
                  llm=llm, rulestore=rs, config=cfg, run_dir=run_dir)
    events.emit("run_init", run_id=run_id, rules=len(rs), corpora=rs.sources())
    return ctx, run_id


def _start_testbed(ctx):
    if not ctx.config["testbed"]["enabled"]:
        return
    try:
        from targets.vulnshop.app import serve_in_thread
        srv, base = serve_in_thread(host=ctx.config["testbed"]["host"],
                                    port=ctx.config["testbed"]["port"])
        ctx.testbed_url = base
        ctx.events.emit("testbed_up", url=base)
        return srv
    except OSError as e:  # port indisponible, etc. -> le Validator dégrade (FR-066)
        ctx.testbed_url = None
        ctx.events.emit("testbed_unavailable", reason=str(e))
        return None


def _seed_detection(ctx):
    src = ctx.config["target"]["source"]
    files = sorted({f.file for f in ctx.index.all_functions()})
    for rel in files:
        ctx.queue.add(f"detect:rules {rel}", role="detector", priority=80,
                      payload={"kind": "rules", "file": rel}, task_id=f"detect-rules-{rel}")
    ctx.queue.add("detect:secrets", role="detector", priority=80,
                  payload={"kind": "secrets"}, task_id="detect-secrets")
    ctx.queue.add("detect:deps", role="detector", priority=80,
                  payload={"kind": "deps"}, task_id="detect-deps")
    ctx.queue.add("detect:explore", role="detector", priority=85,
                  payload={"kind": "explore"}, task_id="detect-explore")


def run(cfg: dict, *, on_ready=None, max_seconds: float = 120.0) -> Context:
    """Exécute une évaluation complète et retourne le contexte (findings dans le store)."""
    global ACTIVE
    ctx, run_id = setup(cfg)
    ACTIVE = ctx
    testbed = _start_testbed(ctx)

    # Gate FR-003 : index avant tout le reste.
    if not indexer.run_indexer(ctx):
        ctx.events.emit("abort", reason="index non queryable")
        return ctx
    cartographer.run_cartographer(ctx)
    coverage_guide.init_coverage(ctx)
    _seed_detection(ctx)

    if on_ready:
        on_ready(ctx)

    # Spawn du fleet (FR-002).
    workers = []
    for role, count in cfg["fleet"].items():
        for i in range(count):
            w = Worker(role, i, ctx, HANDLERS[role])
            w.start()
            workers.append(w)

    # Supervision : reclaim, couverture, halt, complétion.
    deadline = time.time() + max_seconds
    conn = ctx.db.connect()
    while time.time() < deadline:
        ctx.queue.reclaim_expired()                    # FR-096 : claims morts
        # Auto-réparation : une tâche bloquée par des échecs transitoires (contention) est
        # ré-ouverte pour être retentée — évite de tronquer silencieusement la sortie.
        conn.execute("UPDATE tasks SET state='open', claimed_by=NULL, release_count=0 "
                     "WHERE state='blocked'")
        coverage_guide.review(ctx)                     # FR-069/071
        halt = ctx.budget.should_halt(ctx.coverage_complete.is_set())  # FR-116
        pending = ctx.queue.open_count("main")
        untriaged = conn.execute(
            "SELECT COUNT(*) c FROM findings WHERE verdict IS NULL").fetchone()["c"]
        if halt:
            ctx.events.emit("halt", reason=halt)
            break
        # Terminé seulement quand tout est drainé, la couverture complète, ET aucun candidat
        # ne reste non trié (sortie complète garantie, déterministe).
        if pending == 0 and untriaged == 0 and ctx.coverage_complete.is_set():
            ctx.events.emit("done", reason="couverture complète + tout trié")
            break
        time.sleep(0.15)

    ctx.stop.set()                                     # drain (FR-006)
    for w in workers:
        w.join(timeout=3)
    reporter.write_rollup(ctx)
    ctx.events.emit("shutdown", run_id=run_id)
    return ctx
