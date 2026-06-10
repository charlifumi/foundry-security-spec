# Forge — Plan technique

> Sortie de `/speckit.plan`. Conçu pour satisfaire `spec.md` sous les contraintes de
> `.specify/memory/constitution.md`. Stack : Python 3.11+, LangGraph/LangChain, SQLite,
> Docker, FastAPI + WebSocket.

## 0. Principe directeur

Deux couches strictement séparées :

1. **Couche agent** (intelligence) — chaque rôle est un graphe LangGraph d'un agent LLM
   outillé. Remplaçable, non-déterministe, testable avec un modèle mocké.
2. **Couche substrate** (coordination) — work queue, finding store, heartbeats, claims,
   budget, sandbox. **Déterministe**, testable **sans LLM** (NFR-004). C'est ici que vivent
   les invariants de la constitution (claims atomiques, liveness heartbeat, persistance
   atomique). *Aucune librairie d'agents ne fournit ces garanties ; on les construit.*

La frontière entre les deux est l'erreur classique à ne pas commettre : ne jamais laisser
LangGraph « gérer » la coordination inter-agents ou la liveness. LangGraph orchestre **un**
agent ; le substrate orchestre **le fleet**.

---

## 1. ADR-001 — LangGraph/LangChain pour la couche agent, substrate maison

**Statut :** accepté. **Contexte :** la question « une implémentation type LangChain est-elle
appropriée ? » est tranchée ici.

**Décision.**
- **LangChain** fournit l'abstraction provider (`langchain-anthropic`, interface
  `LLMProvider` swappable — US-13), le tool-calling, et surtout les **sorties structurées
  Pydantic** (`with_structured_output`) qui matérialisent l'evidence gate : le verdict du
  Triager est un objet Pydantic `Verdict{reachability, trust_boundary, impact, citations[]}`,
  donc le gate FR-087/088 est une **validation de schéma + résolution de citations**, pas du
  parsing de prose.
- **LangGraph** fournit, **par agent** : la boucle d'état (ReAct outillé), le **checkpointing**
  (→ résumabilité NFR-001), et le **streaming d'événements** (`astream_events`) qu'on branche
  directement sur le WebSocket du dashboard → « voir chaque agent actif » (SC-010) sort
  presque gratuitement.

**Ce que LangGraph ne fait PAS chez nous** (et qu'on code à la main) :
- claim atomique et mortel (FR-095/096) → transactions SQLite + heartbeat ;
- liveness par heartbeat sur lane dédiée (FR-100/101) → thread/process séparé ;
- persistance atomique write-then-swap (FR-106a) → helper substrate ;
- sandbox réseau/FS (FR-107/108) → Docker.

**Alternatives écartées.**
- *SDK Anthropic brut + orchestration 100 % maison* : plus de contrôle, moins de deps, mais
  on réécrit boucle d'agent + checkpoint + streaming. Rejeté pour le time-to-demo.
- *CrewAI / AutoGen* : abstraction « équipe d'agents » qui cache justement la coordination
  qu'on veut **rendre visible et conforme à la constitution**. Mauvais fit pédagogique.
- *LangGraph pour TOUT, y compris le fleet* : violerait la séparation §0 ; la liveness et les
  claims finiraient dans un état de graphe en mémoire, non crash-safe. Rejeté (Constitution III/IV/XI).

**Conséquences.** Dépendance à l'écosystème LangChain (versionné, pinné). Les rôles restent
des unités testables. Un builder peut remplacer le provider sans toucher au substrate (US-13).

---

## 1bis. ADR-002 — Base vectorielle pour la fédération de corpus de règles externes

**Statut :** accepté (révise la mise en attente initiale de FR-023). **Contexte :** au-delà du
corpus CodeGuard maison, on veut intégrer des **corpus de règles tiers spécialisés par domaine**
(crypto, web, cloud, mobile…), produits par des entités plus expertes sur certains modules. Ces
corpus peuvent être volumineux ; les appliquer tous, exhaustivement, à chaque fonction ne passe
pas à l'échelle et dilue le signal.

**Décision.** Introduire un **`RuleStore`** à deux backends, et une **base vectorielle** pour la
récupération de règles pertinentes :

- **Backend `exhaustive`** (défaut sur petit corpus) : applique chaque règle à chaque fonction
  (FR-037 strict). Pas d'embeddings.
- **Backend `vector`** (pour corpus larges/fédérés, FR-023) : chaque règle est *embedée* et
  indexée ; pour une fonction/module donné, on récupère les **top-k règles pertinentes** (toutes
  sources confondues) avant l'évaluation LLM. C'est ce qui rend la **fédération** viable : on
  charge N corpus externes, on les interroge par pertinence, on ne paie pas l'application
  exhaustive de tout.
- **Fédération** : chaque corpus est une **source nommée** (`name`, `domain`, `version`, `trust`),
  chargée dans le même index, filtrable à la requête (« seulement les corpus crypto certifiés »).

**Choix techniques.**
- **Index vectoriel** : **sqlite-vec** par défaut (reste dans le SQLite du substrate, zéro infra
  nouvelle, cohérent avec NFR atomique) ; **FAISS** / **Chroma** en local autonome ; **pgvector**
  si Postgres. Interface `VectorIndex` pluggable.
- **Embeddings** : interface `EmbeddingProvider` pluggable — modèle local (sentence-transformers /
  via la passerelle LiteLLM, cohérent avec le routage local de cost-and-routing.md), ou API. Un
  **fallback déterministe** (hachage de n-grammes) permet de faire tourner la démo sans modèle.
- **Format de règle** : **CodeGuard** (markdown unifié) reste le format d'échange ; le `RuleStore`
  parse le front-matter (domaine, CWE, sévérité, source) pour le filtrage et l'embedding.

**Conséquences.** Le corpus n'est plus un simple dossier appliqué en boucle : c'est un **magasin
de connaissances fédéré et interrogeable**, condition pour que des tiers contribuent des règles
de pointe par domaine. FTS5 reste pour le plein-texte. Le backend `exhaustive` garde la
fidélité à FR-037 sur petits corpus ; le backend `vector` ajoute le passage à l'échelle.

---

## 2. Découpage en modules

```
forge/
├── cli.py                  # forge init|up|down|status|ask|task|pause|resume  (Orchestrateur, facette CLI)
├── config.py               # schéma Pydantic de forge.yaml + validation (FR-001/129)
├── orchestrator/
│   ├── lifecycle.py        # spawn/respawn/backoff/drain/gate index (FR-002..012)
│   ├── conversation.py     # Q&A ancré substrate, steering (FR-013..019) — lane async séparée
│   └── supervisor.py       # boucle de supervision : heartbeats, reclamation, budget halt
├── substrate/
│   ├── db.py               # connexion SQLite (WAL), helpers de migration
│   ├── queue.py            # work queue : claim atomique, auto-block N=3 (FR-094..099)
│   ├── findings.py         # finding store + FTS5 + fingerprint (FR-090/091, lifecycle)
│   ├── heartbeat.py        # émission + observation de liveness (FR-100/101)
│   ├── budget.py           # tokens→coût, runtime, yield glissant (FR-112..117)
│   ├── notes.py            # notes partagées bornées + operator messages (FR-102/104)
│   └── persist.py          # write-new-then-swap atomique (FR-106a)
├── agents/
│   ├── base.py             # LangGraph runtime commun : boucle, heartbeat, claim, tools, streaming
│   ├── indexer.py          # tree-sitter Python → symboles + call graph (FR-020..029)
│   ├── cartographer.py     # 5 passes → carte de sécurité (FR-030..036a)
│   ├── detector.py         # 4 modes : rules / deps / secrets / exploratory (FR-037..049)
│   ├── triager.py          # investigation outillée + evidence gate (FR-050..059, 087/088)
│   ├── validator.py        # repro clean-room sur testbed + PoC (FR-060..066)
│   ├── coverage_guide.py   # checklist (composant×goal), flag couverture (FR-067..074)
│   └── reporter.py         # writeups CWE/CVSS + rollup OWASP (FR-075..084)
├── llm/
│   ├── provider.py         # interface LLMProvider (Anthropic par défaut), comptage tokens
│   └── prompts/            # un fichier par rôle (montés read-only dans le sandbox)
├── rules/                  # corpus CodeGuard (markdown) fédérés, versionnés, FR-041
│   ├── store.py            # RuleStore : backends exhaustive | vector (ADR-002, FR-023)
│   ├── embeddings.py       # EmbeddingProvider pluggable (+ fallback déterministe)
│   ├── vector_index.py     # VectorIndex pluggable (sqlite-vec | faiss | chroma | bruteforce)
│   └── corpora/            # sources de règles nommées (maison + tierces fédérées)
├── index/                  # backend tree-sitter + interface de requête (FR-022)
├── dashboard/
│   ├── server.py           # FastAPI + WebSocket, push depuis le substrate (FR-120..125)
│   └── static/             # SPA légère (HTML/JS) : fleet, findings, couverture, budget
└── sandbox/
    ├── Dockerfile.fleet    # conteneur fleet, réseau allowlist
    ├── Dockerfile.testbed  # conteneur de l'app cible
    └── compose.yaml        # réseau Docker custom + egress filtrant
```

L'app cible vit hors de `forge/` :

```
targets/vulnshop/           # app Flask volontairement vulnérable (la cible de démo)
runs/<run-id>/              # sorties d'un run : forge.db (SQLite), reports/, poc/, logs/, map/
```

## 3. Schéma de données (substrate, SQLite)

Tables clés (déterministes, testables sans LLM) :

- `agents(id, role, instance_idx, pid, status, last_heartbeat_ts, restart_count)` — FR-008/100.
- `tasks(id, queue, title, description, priority, state, claimed_by, claim_ts, release_count)` —
  FR-094..099 ; `state ∈ {open, blocked, closed}`.
- `findings(fingerprint, file, symbol, vuln_class, state, verdict, exploited, technique,
  description, evidence_json, severity, cwe, owasp, created_ts, updated_ts)` —
  fingerprint = `sha256(norm_path|symbol|vuln_class)` (FR-090), **sans** ligne ni snippet.
- `findings_fts` — index FTS5 sur description/evidence (FR-022).
- `coverage(item_id, component, goal, bar, state, evidence_ref)` — FR-067..071.
- `budget(run_id, spend, runtime_s, window_json, yield_trailing)` — FR-112..117.
- `messages(id, agent, kind, body, dedup_hash, acked)` — operator messages (FR-102a..d).
- `events(ts, agent, finding, kind, payload_json)` — provenance + flux dashboard (FR-122/123).

Invariants codés au niveau substrate :
- **Claim atomique** (FR-095) : `UPDATE tasks SET claimed_by=? WHERE id=? AND claimed_by IS NULL`
  dans une transaction ; le `rowcount` arbitre le gagnant unique.
- **Claim mortel** (FR-096) : le superviseur libère (`claimed_by=NULL`, `release_count+1`) tout
  claim dont l'agent a un heartbeat périmé.
- **Persistance atomique** (FR-106a) : écrire fichier temporaire + `os.replace()` ; SQLite en WAL.

## 4. Boucle d'agent générique (`agents/base.py`)

Chaque instance d'agent, quel que soit le rôle :
1. s'enregistre dans `agents`, démarre un **thread heartbeat** dédié (FR-101) ;
2. boucle : `claim` une tâche (FR-095) → exécute le graphe LangGraph du rôle → écrit au
   substrate → libère le claim ; émet des `events` à chaque transition (→ dashboard) ;
3. respecte les limites de session souple/dure (FR-118) ; backoff partagé sur 429 (FR-106) ;
4. à la mort, le superviseur récupère le claim (FR-096). Pas de respawn re-queue du travail
   roté (Constitution III).

Le graphe LangGraph par rôle = nœuds `{prepare_context → call_llm(tools) → validate_output →
persist}` avec checkpoint après chaque nœud (NFR-001).

## 5. Evidence gate — réalisation concrète (le cœur)

Le Triager produit un objet Pydantic :

```python
class Citation(BaseModel):
    file: str; symbol: str; line_start: int; line_end: int
class Verdict(BaseModel):
    verdict: Literal["true-positive","false-positive","needs-review","not-applicable","code-quality"]
    reachability: Citation | None       # jambe (a) FR-087
    trust_boundary: Citation | None     # jambe (b)
    impact: Citation | None             # jambe (c)
    reasoning: str
```

Gate (FR-088) = fonction **déterministe** `resolve_citation(c)` qui ouvre `file`, vérifie que
`symbol` existe aux lignes citées via l'index tree-sitter. Si `verdict=="true-positive"` et
qu'une des trois jambes est absente **ou** non résolvante → **démotion automatique** en
`needs-review`. Le modèle ne s'attribue jamais `true-positive` ; le gate le fait (Constitution I).
Carve-out FR-087a pour secrets/crypto (jambes a/b = « le dépôt »).

## 6. Sandbox (FR-107/108)

`docker compose` à deux services sur un réseau bridge custom :
- `testbed` : `vulnshop` exposé seulement sur le réseau interne.
- `fleet` : conteneur des agents ; egress sortant filtré (iptables/`--network` interne + proxy
  egress n'autorisant que `api.anthropic.com` + le testbed). Montages **read-only** : `targets/`,
  `forge/llm/prompts/`, `sandbox/`. Montage **read-write** restreint : `runs/<id>/`.
- Test SC-007 : un agent root tentant `curl https://example.com` doit échouer.

## 7. Dashboard (FR-120, SC-010)

FastAPI sert une SPA légère (un seul `index.html` + JS, pas de build). Le serveur s'abonne à la
table `events` (polling court ou trigger) et **push** par WebSocket :
- **Fleet** : carte des agents (rôle, instance, vivant/mort, claim courant, âge heartbeat) — animé.
- **Pipeline** : colonnes du cycle de vie (candidate → triaged → confirmed → exploited → published)
  avec les findings qui transitent.
- **Couverture** : barre par goal. **Budget** : dépense, runtime, yield glissant, état dégradé.
`forge status` lit la **même** source → cohérence SC-008.

## 8. Mode sans clé API (dégradé)

Le moteur réel utilise un vrai LLM (clé `ANTHROPIC_API_KEY`). Pour permettre `lance-et-marche`
sans clé en démo/CI, `llm/provider.py` accepte un `--provider=replay` qui rejoue des transcripts
LLM enregistrés sur `vulnshop` (fixtures). Le substrate, le gate, le dashboard et la sandbox sont
**identiques** dans les deux modes (NFR-004 : la structure ne dépend pas du modèle). Cela permet
de tester SC-004/005/007/008 en CI sans coût ni clé.

## 9. Stratégie de vérification (jalons)

- **Tests substrate sans LLM** (NFR-004) : claim concurrent (SC-004), dédup fingerprint (SC-005),
  démotion de citation non résolvante (FR-088), persistance atomique sous kill (FR-106a).
- **Test sandbox** (SC-007) : egress hors allowlist refusé.
- **Test E2E mode replay** : `forge up` sur `vulnshop` → ≥1 `true-positive` publié pour une vuln
  semée (SC-001), arrêt couverture∧yield (SC-006), cohérence status/dashboard (SC-008).
- **`/speckit.analyze`** à chaque jalon : drift spec↔plan↔tasks↔code, et re-vérification des 11
  principes de la constitution.

## 10. Dépendances (pinnées dans `requirements.txt`)

`langgraph`, `langchain-core`, `langchain-anthropic`, `pydantic`, `tree-sitter` +
`tree-sitter-python`, `fastapi`, `uvicorn`, `websockets`, `pyyaml`, `httpx`. App cible :
`flask` (+ une dépendance volontairement obsolète pour FR-038). Sandbox : Docker + compose.
