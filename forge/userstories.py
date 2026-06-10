"""User stories (spec.md §3.2) — the operator intents that TRIGGER work toward the Orchestrator.

Each story maps an operator (or reviewer/developer) intent to the concrete trigger that
starts or steers the pipeline through the Orchestrator. This is what conditions the
operator → orchestrator exchange.
"""
from __future__ import annotations

USER_STORIES = [
    {"id": "US-1", "persona": "Operator", "pri": "P1",
     "want": "Point at a target repo + a one-page goals doc, run one command, and walk away",
     "trigger": "forge up", "to": "Orchestrator validates config, stands up the substrate, spawns the fleet",
     "maps": "FR-001/002, SC-001"},
    {"id": "US-2", "persona": "Operator", "pri": "P1",
     "want": "See, at any moment, what every agent is working on, found, or blocked on",
     "trigger": "forge status / dashboard", "to": "Orchestrator status query (same source as dashboard)",
     "maps": "FR-008, SC-008"},
    {"id": "US-3", "persona": "Operator", "pri": "P2",
     "want": "Ask a free-form question grounded in the evaluation's actual state",
     "trigger": "forge ask \"why was #14 closed?\"", "to": "Orchestrator conversational facet (cited answer)",
     "maps": "FR-013"},
    {"id": "US-4", "persona": "Operator", "pri": "P1",
     "want": "Be told when the evaluation is done, and why",
     "trigger": "coverage-complete ∧ yield-below-threshold", "to": "Orchestrator halts the fleet and reports",
     "maps": "FR-116, SC-006"},
    {"id": "US-5", "persona": "Operator", "pri": "P1",
     "want": "Set a hard ceiling on spend and/or wall-clock time",
     "trigger": "budget caps in forge.yaml", "to": "Budget governor halts on cap (Orchestrator)",
     "maps": "FR-112, US-5"},
    {"id": "US-6", "persona": "Operator", "pri": "P1",
     "want": "Constrain what the fleet can reach on the network and modify on disk",
     "trigger": "sandbox config (allowlist)", "to": "Orchestrator enforces the Docker sandbox",
     "maps": "FR-107, SC-007"},
    {"id": "US-7", "persona": "Reviewer", "pri": "P1",
     "want": "Receive only findings that passed a structural evidence check",
     "trigger": "published findings", "to": "Reporter publishes only evidence-gated true-positives",
     "maps": "FR-052, SC-002"},
    {"id": "US-8", "persona": "Reviewer", "pri": "P2",
     "want": "See which findings were actually demonstrated against a running system",
     "trigger": "exploited flag", "to": "Validator sets exploited; Reporter prioritizes it",
     "maps": "FR-061, SC-003"},
    {"id": "US-10", "persona": "Developer", "pri": "P1",
     "want": "Open a finding and find description, reproduction steps and a runnable PoC",
     "trigger": "open a published report", "to": "Reporter writeup + PoC artifact",
     "maps": "FR-075, US-10"},
    {"id": "US-11", "persona": "Operator", "pri": "P2",
     "want": "Re-run after the target changes and have prior findings deduplicated",
     "trigger": "forge up (again)", "to": "Fingerprint dedup; only the delta is filed",
     "maps": "FR-090/091, SC-005"},
    {"id": "US-12", "persona": "Operator", "pri": "P2",
     "want": "Hand a specific task to the fleet (\"investigate function X\")",
     "trigger": "forge task ...", "to": "Orchestrator queues the task at chosen priority",
     "maps": "FR-014"},
]


def user_stories() -> list[dict]:
    return USER_STORIES
