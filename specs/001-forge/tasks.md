# Forge — Backlog de construction

> Sortie de `/speckit.tasks`. Backlog ordonné et dépendant pour construire Forge à partir de
> `spec.md` + `plan.md`. Chaque tâche cite les FRs qu'elle réalise. Les phases sont séquentielles ;
> à l'intérieur d'une phase, les tâches `[P]` sont parallélisables.
>
> Convention de statut : `[ ]` à faire · `[~]` en cours · `[x]` fait.

## Phase 0 — Échafaudage & substrate (sans LLM)

> Tout ici est déterministe et testable sans modèle (NFR-004). C'est le socle des invariants
> de la constitution. **Ne pas démarrer la couche agent avant que la Phase 0 soit verte.**

- [ ] **T-001** Squelette de repo + `requirements.txt` pinné + `forge.yaml.example`. (plan §2, §10)
- [ ] **T-002** `config.py` : schéma Pydantic des 9 sections de `forge.yaml`, validation nommant
  les champs manquants. → FR-001, FR-126, FR-127, FR-129
- [ ] **T-003** `substrate/db.py` : SQLite WAL, migrations, helper `persist.py` write-then-swap.
  → FR-106a, Constitution XI
- [ ] **T-004** `substrate/queue.py` : work queue, claim atomique, ids stables, auto-block N=3,
  multi-files nommées. → FR-094..099, Constitution IV
- [ ] **T-005** `substrate/heartbeat.py` : émission lane-dédiée + observation de liveness.
  → FR-100, FR-101, Constitution III
- [ ] **T-006** `substrate/findings.py` : finding store, fingerprint (path+symbol+class),
  FTS5, dédup, machine d'états du cycle de vie. → FR-043..045, FR-085..091, Constitution VIII
- [ ] **T-007** `substrate/budget.py` : tokens→coût, runtime, yield glissant géométrique,
  conditions de halt (a∧b∧c). → FR-112..117, Constitution VI
- [ ] **T-008** `substrate/notes.py` : notes partagées bornées + operator messages dédupliqués.
  → FR-102a..d, FR-104..104b
- [ ] **T-009 [P]** `orchestrator/supervisor.py` : boucle heartbeat-scan + reclamation de claims
  + halt budget. → FR-005, FR-096, FR-116
- [ ] **T-010 [P]** Tests substrate sans LLM : claim concurrent (SC-004), dédup (SC-005),
  persistance atomique sous kill, auto-block. → SC-004, SC-005, NFR-004

## Phase 1 — Sandbox & cible

- [ ] **T-011** `targets/vulnshop` : app Flask volontairement vulnérable (voir `docs/vulnshop.md`).
  → cible de démo, FR-038 (dépendance obsolète incluse)
- [ ] **T-012** `sandbox/Dockerfile.testbed` + lancement jetable + procédure de reset.
  → FR-107, §11.12
- [ ] **T-013** `sandbox/Dockerfile.fleet` + `compose.yaml` : réseau bridge custom, egress
  allowlist (Anthropic + testbed), montages read-only (source, prompts, sandbox def).
  → FR-107, FR-108, Constitution IX
- [ ] **T-014** Test sandbox : agent root → egress hors allowlist refusé. → SC-007

## Phase 2 — Couche LLM & corpus de règles

- [ ] **T-015** `llm/provider.py` : interface `LLMProvider`, binding `langchain-anthropic`,
  comptage de tokens, backoff partagé fleet-wide sur 429. → FR-105, FR-106, FR-113, US-13
- [ ] **T-016** `llm/provider.py` mode `replay` (rejoue des transcripts fixtures) pour démo/CI
  sans clé. → plan §8, NFR-004
- [ ] **T-017** `rules/` : corpus CodeGuard de départ (format markdown unifié) couvrant SQLi,
  XSS, cmd-injection, SSRF, IDOR, path-traversal, secrets en dur, crypto faible, désérialisation.
  → FR-037, FR-041, US-14
- [ ] **T-018 [P]** `llm/prompts/` : un prompt système par rôle + bloc hard-rules (FR-110/111).

## Phase 3 — Couche connaissance

- [ ] **T-019** `index/` : backend tree-sitter Python → inventaire de fonctions + graphe d'appels
  + interface de requête (get-body/callers/callees/find-symbol/fts). → FR-020..022
- [ ] **T-020** `agents/base.py` : runtime LangGraph commun (claim→graphe→persist→release),
  heartbeat, streaming d'événements, limites de session. → FR-101, FR-118, plan §4
- [ ] **T-021** `agents/indexer.py` : construit l'index, incrémental, persistance atomique,
  signale « queryable ». → FR-020..029, FR-024
- [ ] **T-022** `agents/cartographer.py` : 5 passes (archi, surface, frontières, flux, menace),
  fallback minimal anti-0-byte, digest pour prompts. → FR-030..036a

## Phase 4 — Pipeline de findings

- [ ] **T-023** `agents/detector.py` mode **règles** : pour chaque fonction, check LLM par règle,
  contexte front-loadé. → FR-037, FR-049
- [ ] **T-024 [P]** `agents/detector.py` modes **deps** + **secrets**. → FR-038, FR-039
- [ ] **T-025 [P]** `agents/detector.py` mode **exploratoire** : consulte coverage log, queue des
  rule-gaps. → FR-040, FR-042, FR-046, FR-047
- [ ] **T-026** `agents/triager.py` : investigation outillée guidée par checklist + **evidence gate**
  Pydantic + `resolve_citation` déterministe + démotion. → FR-050..059, FR-087, FR-088, Constitution I
- [ ] **T-027** `agents/validator.py` : repro clean-room (instance fraîche) sur testbed, flag
  `exploited` binaire, PoC runnable, limite de tentatives. → FR-060..066, Constitution VII
- [ ] **T-028** `agents/coverage_guide.py` : checklist (composant×goal), tâches dirigées, flag
  couverture-complète, persistance atomique. → FR-067..074, Constitution VI
- [ ] **T-029** `agents/reporter.py` : writeups CWE + CVSS + OWASP, un fichier MD par finding,
  rollup groupé par composant, findings-clés, scrubbing des détails internes. → FR-075..084

## Phase 5 — Orchestrateur & surfaces opérateur

- [ ] **T-030** `orchestrator/lifecycle.py` : spawn/respawn/backoff/drain, gate index (FR-003),
  refus post-cap (FR-011), pré-flight (FR-010). → FR-002..012
- [ ] **T-031** `orchestrator/conversation.py` : Q&A ancré substrate avec citations, steering,
  operator messages — **lane async séparée** de la facette cycle de vie. → FR-013..019
- [ ] **T-032** `cli.py` : `forge init|up|down|status|ask|task|pause|resume`. → US-1, US-2, US-5, US-12
- [ ] **T-033** `dashboard/` : FastAPI + WebSocket, push depuis `events`, vues fleet/pipeline/
  couverture/budget. Même source que `status` (SC-008). → FR-120..125, SC-010

## Phase 6 — Bout en bout & vérification

- [ ] **T-034** Test E2E (mode replay) : `forge up` sur vulnshop → ≥1 `true-positive` publié pour
  une vuln semée, sans intervention. → SC-001
- [ ] **T-035** Test arrêt autonome : caps non posés + goals complets → halt couverture∧yield. → SC-006
- [ ] **T-036** Test re-run : cible inchangée → zéro doublon. → SC-005
- [ ] **T-037** Test provenance : pour un finding publié, reconstruire la chaîne depuis les logs. → SC-009
- [ ] **T-038** `/speckit.analyze` : drift spec↔plan↔tasks↔code + re-check des 11 principes.
- [ ] **T-039** `README` de lancement (quickstart 3 commandes) + GIF/captures du dashboard.

## Évolutions (hors premier build — §6 seed)

- [ ] **E-1** Variant-Hunter : à partir d'un finding confirmé, chercher le même motif ailleurs.
- [ ] **E-2** Remediator : générer et vérifier des correctifs candidats.
- [ ] **E-3** Self-Improver : lire logs + rule-gaps, proposer des règles (ferme le flywheel FR-042).
- [ ] **E-4** Embeddings/vector search (FR-023) ; export GitHub Issues (FR-078) ; multi-langage indexer.

---

### Ordre critique (dépendances)

```
Phase 0 (substrate)  ──►  Phase 1 (sandbox/cible)  ──►  Phase 2 (LLM/règles)
        │                                                      │
        └──────────────►  Phase 3 (connaissance)  ◄────────────┘
                                   │
                                   ▼
                         Phase 4 (pipeline findings)
                                   │
                                   ▼
                  Phase 5 (orchestrateur + dashboard)
                                   │
                                   ▼
                         Phase 6 (E2E + vérif)
```

La règle d'or (plan §0) : **Phase 0 verte avant toute couche agent.** Les invariants de la
constitution se prouvent sans LLM ; les construire en premier, c'est ce qui rend le reste fiable.
