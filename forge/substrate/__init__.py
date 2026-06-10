"""Substrate de coordination : work queue, finding store, budget, events.

Déterministe, testable sans LLM (NFR-004). C'est ici que vivent les invariants
de la constitution : claims atomiques et mortels (IV), heartbeat-liveness (III),
persistance atomique (XI).
"""
