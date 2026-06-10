# Forge — Journal de clarifications

> Ce fichier résout les marqueurs `[NEEDS CLARIFICATION]` de la *seed* Foundry
> (`CiscoDevNet/foundry-security-spec`, spec.md §15) contre le contexte de **Forge**,
> le démonstrateur que ce dépôt implémente. C'est la sortie de l'étape `/speckit.clarify`.
>
> Chaque décision ci-dessous est reportée dans `spec.md` (FRs adaptés) et `plan.md`
> (choix techniques). Les rationales de la seed restent valables ; on ne fait que
> trancher les axes laissés ouverts.

## Identité & périmètre

| Axe (seed) | Décision Forge | Justification |
|---|---|---|
| Nom du système (préambule spec) | **Forge** | Clin d'œil à *Foundry* (fonderie → forge). Apparaît dans la CLI (`forge up`), les labels, les préfixes de logs, le schéma SQLite. |
| §1.5 — « évaluation autorisée avec accès au code source » tient-il ? | **Oui** | La cible est notre propre app de démo (`targets/vulnshop`), code source complet, déploiement jetable. A-1 et A-2 sont satisfaites par construction. |
| §4.2 — fusionner / scinder / omettre un des 8 rôles | **Aucun** | On garde les 8 rôles core, c'est la valeur démontrée : chaque rôle rattrape le mode d'échec du précédent. Pédagogiquement, montrer les 8 est l'objectif. |
| §4.3 — quelles extensions (5) | **Aucune au premier build** | Recommandation explicite de la seed. Variant-Hunter et Remediator sont notés comme évolutions futures dans `tasks.md`. |

## Choix d'intégration (§11)

| Surface (seed) | Décision Forge | Détail |
|---|---|---|
| §11.1 VCS / issue tracker | **Système de fichiers + SQLite**, export GitHub Issues optionnel | Le *finding store* est SQLite. Les rapports publiés sont des fichiers Markdown sous `runs/<id>/reports/`. Un exporteur GitHub Issues (FR-078) est branchable mais désactivé par défaut pour la démo. |
| §11.2 LLM provider | **Anthropic (Claude)** via clé API, derrière une interface `LLMProvider` | Abstraction provider-agnostique (LangChain `chat models`). Le mode démo nécessite `ANTHROPIC_API_KEY`. Comptabilité par tokens pour le budget (FR-113). |
| §11.3 Datastore | **SQLite** (un fichier par run) | Work queue, finding store, coverage, heartbeats, budget : tables dans une base SQLite unique. Suffisant pour mono-machine ; satisfait les claims atomiques (transactions) et la persistance atomique (write-then-rename / `WAL`). |
| §11.4 Vector search | **Désactivé au MVP** (FR-023 droppé), full-text FTS5 activé | Recherche par similarité non requise pour le chemin critique. FTS5 de SQLite couvre la recherche plein-texte (FR-022). Embeddings = évolution. |
| §11.5 Topologie de déploiement | **Une machine**, multiprocessing local | Un processus OS par instance d'agent ; coordination via SQLite partagé. |
| §11.6 Runtime d'isolation | **Docker** | La cible (testbed) tourne dans un conteneur. Le fleet tourne dans un conteneur au réseau restreint (allowlist : API Anthropic + testbed). Satisfait FR-107 « sandbox par l'infra, pas par le prompt ». |
| §11.7 Modèle d'auth | **Mono-opérateur local** | Pas de multi-tenant (NFR-003 droppé). |
| §11.8 Agent harness | **LangGraph** (boucle + état + checkpoint) sur **LangChain** (LLM + tools) | Voir ADR-001 dans `plan.md`. Le *substrate* (queue, heartbeat, claims) reste maison. |
| §11.9 Sévérité & classification | **Sévérité = tiers qualitatifs** (critical/high/medium/low) + score CVSS 3.1 indicatif ; **classe = CWE** | Tiers pour le tri reviewer (FR-077) ; CWE pour la taxonomie (FR-076). Échelle de points de sévérité géométrique (~3.16×) pour le yield (FR-117). |
| §11.10 Mapping conformité | **OWASP Top 10 (2021)** | Adapté à une cible web. Chaque finding mappé à une catégorie OWASP en plus du CWE. |
| §11.11 Export downstream | **Aucun** au MVP | Les rapports Markdown + le rollup suffisent. Hook d'export laissé en interface. |
| §11.12 Testbed | **Toujours présent** | L'app de démo tourne ; le Validator peut donc réellement exploiter en live et poser le flag `exploited` (FR-060/061). C'est le cœur de la démonstration demandée. |

## Choix de politique & de procédure

| Axe (seed) | Décision Forge |
|---|---|
| §5.3 — la Cartographe gate-t-elle le spawn du fleet ? | **Non** (défaut seed). Les rôles consomment la carte partielle existante (FR-035/036). Cible petite → carte rapide de toute façon. |
| §5.3 — implémentation Cartographe | **Pipeline de passes ciblées** (une passe par document : archi, surface, frontières, flux de données, modèle de menace). Évite le 0-byte map (FR-036a). |
| §5.4 — techniques de détection retenues | **Les 4** : règles (FR-037), dépendances (FR-038), secrets (FR-039), exploration libre (FR-040). |
| §5.4 — corpus de règles | **Format CodeGuard** (markdown unifié), corpus de départ versionné sous `rules/`, dérivé des règles CodeGuard publiques + règles maison pour les classes web (SQLi, XSS, SSRF, IDOR, traversal, cmd-injection). FR-041 : artefact versionné indépendant du code. |
| §5.5 — procédure d'investigation Triager | **Boucle d'agent outillée** (LangGraph) **guidée par une checklist** (les 5 étapes de FR-051). Compromis coût/qualité retenu par la seed. |
| §5.6 — fréquence du testbed | **Toujours** → Validator pleinement actif. |
| §5.8 — taxonomie de faiblesse | **CWE** ; **sévérité** tiers + CVSS 3.1 ; permalinks (FR-084) construits comme `file#Lstart-Lend` pinés sur le SHA du run (chemins locaux pour la démo, format GitHub si export activé). |
| §5.5 — `needs-review` surfacé aux humains ? | **Non** au MVP (reste interne, interrogeable via le dashboard). FR-057 défaut. |
| §7.6 — noms de labels | Set fixe : `forge:src`, `verdict:<v>`, `sev:<tier>`, `exploited:<yes\|no>`, `cwe:<id>`, `owasp:<cat>`. Création à la volée. |
| §9.1 — application du sandbox réseau | **Réseau Docker custom + egress allowlist** (le conteneur fleet n'a de route que vers l'API LLM et le testbed). « Trust the prompt » refusé. |
| §12 — format de configuration | **YAML** (supporte les commentaires). Un fichier `forge.yaml` par évaluation. Secrets via variables d'environnement / `.env` non versionné (FR-127). |
| §13 NFR-003 multi-tenant | **Droppé** (mono-opérateur). |

## Langages indexés (§5.2)

| Axe | Décision |
|---|---|
| Langages que l'Indexer doit supporter | **Python** (l'app de démo est Flask). Frontend **tree-sitter** (`tree-sitter-python`) pour l'inventaire déterministe des fonctions + graphe d'appels (FR-020/021). Extension multi-langage triviale via grammaires tree-sitter additionnelles. |

## Récapitulatif des FR retirés ou réduits par ces choix

- **FR-023** (embeddings / vector search) → reporté ; remplacé par FTS5.
- **NFR-003** (isolation multi-tenant) → retiré (mono-tenant).
- **FR-038** (scan de dépendances) → conservé, sur `requirements.txt`.
- Rôles d'extension §6 → hors périmètre du premier build.

Tous les autres FR de la seed sont conservés et adaptés dans `spec.md`.
