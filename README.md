# Forge — Démonstrateur du pipeline Foundry (Cisco) d'évaluation de sécurité par IA

Forge est une **implémentation de démonstration** de la seed
[**Foundry Security Spec**](https://github.com/CiscoDevNet/foundry-security-spec) de Cisco :
un système d'agents IA qui, à partir du **code source** d'un produit, **trouve** des
vulnérabilités, **vérifie** leur réalité sur preuves de code, **exploite** réellement les
confirmées dans une **sandbox**, et **rapporte** le tout — chaque agent étant **observable en
temps réel** sur un dashboard.

> ⚠️ **Important — ce qu'est Foundry.** Foundry n'est *pas* un modèle ni un outil exécutable :
> c'est une **spécification** écrite (zéro code) que Cisco a publiée. Elle décrit la *forme* d'un
> système. **Forge** est ce que ce dépôt ajoute : l'implémentation que la spec ne fait que
> décrire, sur une stack concrète (Python, LangGraph, SQLite, Docker), avec une app vulnérable de
> démonstration et un dashboard visuel.

## Les trois briques d'amont

| Brique | Rôle | Lien |
|---|---|---|
| **Foundry Security Spec** (Cisco) | La *seed* : 8 rôles d'agents, cycle de vie des findings, 11 principes constitutionnels. | <https://github.com/CiscoDevNet/foundry-security-spec> |
| **spec-kit** (GitHub) | Le workflow *spec-driven* qui consomme la seed (`clarify → specify → plan → tasks → implement`). | <https://github.com/github/spec-kit> |
| **CodeGuard** (CoSAI/OASIS) | Le format des **règles de détection** (markdown unifié), réutilisable comme garde-fou de codage. | <https://project-codeguard.org> |

## La valeur démontrée : le flywheel détection → prévention

Forge ne se contente pas de scanner. Il fait tourner une boucle qui s'améliore :

1. Les **règles** balayent chaque fonction (systématique, reproductible).
2. Les **agents exploratoires** chassent à côté (créatif, spécifique à la cible).
3. Quand l'exploration confirme ce que les règles ont raté → un **rule-gap** est enregistré.
4. Le gap est généralisé en **nouvelle règle CodeGuard** → elle rejoint le corpus.
5. Le balayage suivant attrape toute la classe dès la première passe.
6. Et comme les règles CodeGuard sont **portables**, la même règle qui *détecte* la classe ici
   *prévient* la classe dans l'éditeur du développeur. **Chaque tour améliore la détection ici et
   la prévention partout.**

## Architecture en un coup d'œil

```
                          OPÉRATEUR  (CLI forge + dashboard web temps réel)
                                       │
                              ORCHESTRATEUR  (cycle de vie · conversation)
                                       │
                  ══════════ SUBSTRATE (SQLite) ══════════
                   work queue · finding store · heartbeats ·
                   sandbox (Docker) · budget · dashboard (WS)
                  ════════════════════╤═════════════════════
        INDEXER · CARTOGRAPHE   │   DETECTOR · TRIAGER · VALIDATOR   │  REPORTER · COVERAGE-GUIDE
        (tree-sitter, carte)    │   (4 modes · evidence gate · repro live)   │  (CWE/CVSS · "fini ?")
```

Huit rôles, **chacun rattrapant le mode d'échec du précédent** : indexer sans cartographier =
structure sans contexte ; détecter sans trier = bruit ; trier sans valider = fiction plausible ;
valider sans couvrir = un tas de bugs sans preuve de complétude.

## Démarrage rapide — ça tourne sans rien installer

Le démonstrateur est **implémenté** et fonctionne avec la **bibliothèque standard de Python
3.11+**, sans aucune dépendance ni clé API (moteur déterministe par défaut) :

```bash
# mode PAS-À-PAS — graphe type N8N + inspecteur, on avance étape par étape :
python -m forge up --step                # → http://127.0.0.1:8000  (boutons ⏮ ⏭ ▶)

# dashboard temps réel (le pipeline tourne, on observe) :
python -m forge up --dashboard           # → http://127.0.0.1:8000

# en une passe, résumé en console :
python -m forge up

python -m forge status                   # état du dernier run (même source que le dashboard)
python -m forge up --backend vector      # détection via la base vectorielle fédérée (ADR-002)
```

Deux vues, même donnée live : `/` = **graphe du pipeline type N8N** (nœuds = agents, les
findings circulent le long des arêtes) ; `/panels` = vue à panneaux (fleet, pipeline,
cartographie, budget).

En **mode pas-à-pas** (`--step`), chaque clic exécute réellement l'étape suivante — index,
cartographie, détection, **evidence gate du triage**, **exploitation live** — et l'inspecteur
montre la donnée générée et qui transite (candidats, les 3 jambes de preuve, le PoC observé…).

Aperçu visuel sans rien lancer : ouvrez [`docs/dashboard-preview.html`](docs/dashboard-preview.html)
(le graphe N8N avec les données d'un vrai run figées).

La cible évaluée est [`targets/vulnshop`](docs/vulnshop.md), une app web **volontairement
vulnérable** (10 classes semées). En ~1 s, Forge l'indexe, en dresse la **carte de flux**
(chaînes d'appel entrée→sink + points de validation), détecte (règles CodeGuard fédérées +
secrets + dépendances + exploration), trie sur **preuves vérifiées mécaniquement**, **exploite
en live** sur le testbed, et publie les rapports sous `runs/<id>/reports/`. Résultat typique :
**21 findings confirmés, 8 exploités, 1 rule-gap** (l'IDOR trouvé par exploration → nouvelle règle).

Tests (déterministes, sans LLM) : `python -m tests.test_substrate` et `python -m tests.test_e2e`.

### Ce qui est implémenté

```
forge/substrate/   claim atomique + lease + fencing token, finding store, budget/tokens, events
forge/index/       index AST : fonctions, graphe d'appels, chaînes d'appel, flux d'args, validation
forge/rules/       RuleStore CodeGuard fédéré + base vectorielle (backends exhaustive | vector)
forge/agents/      indexer · cartographe · detector(×4 modes) · triager(evidence gate) · validator(exploit live) · coverage-guide · reporter
forge/dashboard/   serveur + SPA temps réel (fleet, pipeline, cartographie, budget)
forge/cli.py       python -m forge up | status | version
targets/vulnshop/  l'application cible volontairement vulnérable
```

## État du projet

Ce dépôt est à la **phase Spec + Plan** de la méthode spec-kit. Sont présents et complets :

| Livrable | Fichier |
|---|---|
| Constitution adoptée (11 principes) | [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |
| Journal de clarifications (résolution des marqueurs) | [`specs/001-forge/clarifications.md`](specs/001-forge/clarifications.md) |
| Spécification dérivée (8 rôles, FRs) | [`specs/001-forge/spec.md`](specs/001-forge/spec.md) |
| Plan technique (+ ADR LangGraph) | [`specs/001-forge/plan.md`](specs/001-forge/plan.md) |
| Backlog de construction | [`specs/001-forge/tasks.md`](specs/001-forge/tasks.md) |
| **Analyse approfondie** (améliorations, outils externes, async, normalisation, concurrence) | [`specs/001-forge/analysis.md`](specs/001-forge/analysis.md) |
| **Coût & routage modèle** (comptabilité tokens, budget, local vs cloud) | [`specs/001-forge/cost-and-routing.md`](specs/001-forge/cost-and-routing.md) |
| **Librairie d'outils intégrables** (par fonction du pipeline : CLI/SARIF/MCP/REST) | [`docs/tool-integration.md`](docs/tool-integration.md) · code : `forge/tools/` |
| **Échanges normalisés entre agents** (enveloppe, taxonomies, contrats, références normatives) | [`docs/protocol.md`](docs/protocol.md) · code : `forge/protocol.py` |
| Manifeste des agents | [`AGENTS.md`](AGENTS.md) |
| Design de l'app vulnérable | [`docs/vulnshop.md`](docs/vulnshop.md) |

**Prochaine étape** : exécuter le backlog (`specs/001-forge/tasks.md`), Phase 0 d'abord
(substrate déterministe, testable sans LLM), puis la couche agent.

## Crédits & licence

Forge dérive de la **Foundry Security Spec** de Cisco (auteurs : Theo Morales, John Allbritten),
consommée via **spec-kit** (GitHub), avec des règles au format **CodeGuard** (CoSAI/OASIS).
Voir [`NOTICE.md`](NOTICE.md) pour la provenance. Ce dépôt est une œuvre dérivée de démonstration ;
il n'est pas affilié à Cisco. La cible `vulnshop` est intentionnellement non sécurisée et ne doit
jamais être déployée hors d'une sandbox jetable.
