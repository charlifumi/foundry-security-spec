# AGENTS.md — Manifeste du fleet Forge

> **AGENTS.md est un format ouvert pour guider les agents IA qui travaillent sur ce dépôt.**
> Ce fichier joue un double rôle : (1) guider les agents de *codage* (Copilot, Cursor, Claude
> Code…) qui construisent Forge ; (2) **déclarer le fleet d'agents d'exécution** de Forge — les
> 8 rôles, leurs capacités, entrées/sorties, outils, prompts et limites de session.
>
> Référence : la seed `CiscoDevNet/foundry-security-spec` (`spec.md` §5, §AGENTS.md).

---

## Partie A — Le fleet d'exécution (les 8 rôles)

Chaque rôle est une spécialisation d'agent LLM (un graphe LangGraph) tournant en boucle,
coordonnée via le substrate SQLite. Un rôle peut avoir **plusieurs instances** concurrentes.
Le **fleet** = toutes les instances d'une évaluation. Seul l'Orchestrateur spawn/termine des
agents (FR-002) ; aucun agent ne spawn de pair (FR-002a).

| Rôle | Instances (défaut) | Entrées | Sorties | Outils principaux | Limite session (soft/hard) |
|---|---|---|---|---|---|
| **Orchestrateur** | 1 | `forge.yaml`, état du fleet, budget | fleet vivant, status, réponses, tâches | spawn/kill, requêtes substrate | n/a (process superviseur) |
| **Indexer** | 1 | arbre source de la cible | index queryable (symboles, call graph) | tree-sitter, FS read-only | n/a (gate FR-024) |
| **Cartographe** | 1 | index, source, goals, desc. testbed | carte de sécurité (5 docs) | requêtes index, lecture source | rotation longue |
| **Detector** | 2–4 | index, carte, source, corpus de règles, goals, coverage log | candidats (finding store), rule-gaps | index, lecture source, réseau testbed, corpus | 150 min / +15 min (exploratoire) |
| **Triager** | 2–3 | candidat, index, carte, source, testbed | verdict + rapport d'investigation | index, lecture source, **testbed (lecture)**, `resolve_citation` | moyenne |
| **Validator** | 1–2 | finding `true-positive`, testbed, PoC | flag `exploited` + PoC runnable | **testbed (exploitation)**, exécution PoC en sandbox | bornée par tentative (FR-065) |
| **Coverage-Guide** | 1 | goals, carte, coverage log, finding store, work queue | checklist, flag couverture, tâches dirigées | requêtes substrate, écriture work queue | cyclique |
| **Reporter** | 1 | finding store, index, carte, checklist | rapports MD par finding + rollup | requêtes substrate, rendu MD | événementielle |

### Invariants par rôle (extraits — voir `spec.md` §5)

- **Orchestrateur** : deux facettes (cycle de vie + conversation) sur **lanes séparées**
  (FR-019) ; ne fait jamais détection/triage/validation/reporting (FR-012).
- **Indexer** : inventaire par **parser déterministe**, jamais LLM seul (FR-020) ; signale
  « queryable » seulement quand FR-020/021/022 OK (FR-024).
- **Cartographe** : ne gate pas le fleet (défaut Forge) ; écrit un fallback minimal plutôt
  qu'une carte vide (FR-036a).
- **Detector** : écrit au store, **jamais** aux humains (FR-044) ; le coverage log est un
  journal, pas une stop-list (FR-046/047).
- **Triager** : ne s'attribue **jamais** `true-positive` — l'**evidence gate** le fait, sur
  citations résolvables (FR-052, FR-087, FR-088 ; Constitution I).
- **Validator** : pose `exploited` **seulement** sur impact directement observé en clean-room
  par une **instance fraîche** (FR-060, FR-061 ; Constitution VII).
- **Coverage-Guide** : ne détecte/triage/valide/clôt jamais elle-même (FR-072) ; n'invente
  jamais de goals (FR-068).
- **Reporter** : ne publie que `true-positive` (FR-079) ; ne nomme jamais le modèle/provider
  ni les IDs internes (FR-083).

### Cycle de vie d'un finding à travers le fleet

```
Detector ─candidate─► [finding store] ─► Triager ─verdict─►
   ├─ TP ─► Reporter ─published─► runs/<id>/reports/
   ├─ TP+exploitable ─► Validator ─exploited?─► Reporter
   └─ FP/NA/CQ/NR ─► recorded (interne, jamais publié)
```

---

## Partie B — Guide pour les agents de *codage* (construire Forge)

### Environnement de dev

- **Python** : 3.11+.
- **Env virtuel** :
  ```bash
  python3 -m venv .venv && source .venv/bin/activate
  python -m pip install -U pip && pip install -r requirements.txt
  ```
- **Docker** requis pour le sandbox (testbed + fleet isolé).

### Quickstart (cible : une fois le build fait)

```bash
forge init                       # génère forge.yaml depuis l'exemple
export ANTHROPIC_API_KEY=...      # clé LLM (ou --provider replay sans clé)
forge up --config forge.yaml      # valide, monte le substrate, lance le fleet
# ouvrir le dashboard :           http://localhost:8000
forge status                      # état du fleet en CLI
forge ask "pourquoi le finding #14 est-il false-positive ?"
forge down                        # drain gracieux
```

### Conventions de contribution

- **Constitution d'abord** : toute PR touchant un invariant cite le(s) principe(s) de
  `.specify/memory/constitution.md` affecté(s) et le(s) FR enforce(nt).
- **Séparation des couches** (plan §0, ADR-001) : ne jamais mettre de coordination inter-agents
  ou de liveness dans LangGraph ; ça vit dans `substrate/`.
- **Testable sans LLM** (NFR-004) : tout comportement structurel (gates, claims, persistance) a
  un test qui passe avec le provider `replay`.
- **Sécurité** : ne committez jamais de credentials ; secrets via env / `.env` non versionné
  (FR-127). La cible `targets/vulnshop` est **volontairement vulnérable** — ne pas la déployer
  hors d'un sandbox jetable.

### MCP / outils recommandés pour le build

- Serveur MCP optionnel exposant le corpus CodeGuard comme garde-fou de codage (US-14).
- Pas de dépendance à une sandbox Cisco DevNet : Forge est auto-contenu (Docker local).

### Tester AGENTS.md

Clonez le dépôt et demandez à votre agent de codage : *« Comment lancer Forge sur vulnshop en
mode replay sans clé API ? »* — la réponse doit dériver du Quickstart ci-dessus.
