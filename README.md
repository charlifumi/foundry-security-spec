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

## Démarrage rapide (une fois le build réalisé)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

forge init                          # génère forge.yaml
export ANTHROPIC_API_KEY=sk-...      # vrai LLM  (ou : forge up --provider replay  sans clé)
forge up --config forge.yaml         # valide, lance la sandbox, spawn le fleet
#                                      dashboard → http://localhost:8000
forge status                         # état du fleet (même source que le dashboard)
forge down                           # arrêt gracieux
```

La cible évaluée est [`targets/vulnshop`](docs/vulnshop.md), une app Flask **volontairement
vulnérable** (10 classes de vulnérabilités semées). Forge l'indexe, en dresse la carte de
sécurité, détecte, trie sur preuves, **exploite en live** dans le conteneur, puis publie les
rapports sous `runs/<id>/reports/`.

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
