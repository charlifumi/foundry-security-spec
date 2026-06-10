# Forge — Spécification d'un démonstrateur d'évaluation de sécurité assistée par IA

| Champ | Valeur |
|---|---|
| **Statut** | `DRAFT` |
| **Version** | 0.1.0 |
| **Dérivé de** | `CiscoDevNet/foundry-security-spec` v0.1.0 (seed `SEED`) |
| **Fichiers compagnons** | `.specify/memory/constitution.md` ; `clarifications.md` ; `plan.md` ; `tasks.md` |
| **Méthode** | Produit par `/speckit.clarify` + `/speckit.specify` à partir de la seed Foundry |

> **Ceci est la spécification de *Forge*, pas la seed Foundry.**
>
> Forge est une implémentation de démonstration de la seed Foundry de Cisco. Là où la
> seed est volontairement sous-spécifiée et neutre vis-à-vis de l'infrastructure, Forge
> tranche chaque axe (voir `clarifications.md`) pour produire un système **exécutable,
> visuel et reproductible** sur une seule machine. L'objectif est de démontrer la valeur
> ajoutée du pipeline : détection → triage gated sur preuves → validation par exploitation
> réelle → reporting, le tout observable agent par agent.

---

## 1. Objet & périmètre

### 1.1 Le problème

Une équipe dispose d'un LLM frontier et d'une application web qu'elle doit évaluer en
sécurité. Pointer le modèle sur le code et demander « trouve les bugs » ne marche pas :
sortie non bornée, invérifiable, majoritairement du bruit, sans signal de fin. Forge est
l'échafaudage qui transforme un LLM frontier en système d'évaluation produisant un
ensemble **borné, vérifiable et priorisé** de findings, et qui sait dire quand il a fini.

### 1.2 Ce que fait Forge

À partir d'une cible (le code source de l'app de démo + un déploiement jetable de cette
app + un énoncé de goals), Forge :

1. Construit une compréhension structurée : index de code (symboles, graphe d'appels) +
   carte de sécurité (architecture, surface d'attaque, frontières de confiance, modèle de menace).
2. Lance un *fleet* d'agents LLM spécialisés qui chassent les vulnérabilités : application
   de règles fonction par fonction, scan de dépendances, scan de secrets, exploration libre.
3. Investigue chaque candidat pour séparer le réel du bruit, avec preuves de code et (ici,
   toujours) reproduction live.
4. Rédige les findings confirmés avec sévérité, classification (CWE/OWASP), étapes de repro.
5. Suit la couverture contre les goals et s'arrête seul quand le travail est fait.
6. Garde l'opérateur informé et aux commandes via un **dashboard temps réel** montrant
   chaque agent actif, son claim courant, et les findings qui apparaissent.

### 1.3 Ce que « terminé » signifie

Une évaluation est terminée quand **les deux** conditions tiennent (Constitution VI) :

- **Couverture complète** : chaque goal énoncé a été crédiblement tenté (« on a cherché et
  rien trouvé » satisfait la couverture).
- **Yield décru** : le taux de findings confirmés par unité de coût est passé sous un seuil
  fixé par l'opérateur.

Aucune des deux conditions seule ne suffit.

### 1.4 Dans le périmètre

- Évaluation de sécurité de l'app de démo `targets/vulnshop` (code + déploiement jetable).
- Opération autonome de bout en bout **et** pilotage par l'opérateur à tout moment.
- Démonstration visuelle : le dashboard est un livrable de premier ordre.

### 1.5 Hors périmètre

- Mode boîte noire (sans source) — A-2 satisfaite par construction.
- Multi-tenant (NFR-003 retiré).
- Cibles arbitraires de production : Forge n'attaque que son testbed jetable.
- Rôles d'extension §6 de la seed (Deep-Tester, Variant-Hunter, Attack-Mapper, Remediator,
  Self-Improver) : hors du premier build, notés comme évolutions.

### 1.6 Critères de succès

Reprend les SC de la seed, instanciés pour Forge. Chaque critère est un observable pass/fail.

| ID | Critère | Valide |
|---|---|---|
| **SC-001** | Sur `vulnshop` (vulnérabilités semées connues), un run de bout en bout produit au moins un finding `true-positive` publié pour une vuln semée, preuve §7.3 satisfaite, sans intervention entre `forge up` et la publication. | US-1, US-7, FR-052 |
| **SC-002** | ≥90 % des findings publiés `true-positive` sont confirmés réels à la revue humaine (plancher de précision). | US-7, Constitution I |
| **SC-003** | Aucun finding portant `exploited` n'échoue à la reproduction humaine indépendante via le seul PoC. | US-8, Constitution VII |
| **SC-004** | Tuer n'importe quel processus d'agent ne laisse aucune unité de travail bloquée : son claim est libéré et re-pris par un pair dans la fenêtre heartbeat-stale, sans action opérateur. | FR-096, FR-100, Constitution III/IV |
| **SC-005** | Un second run sur cible inchangée produit zéro doublon dans le store et zéro rapport en double. | US-11, FR-090/091 |
| **SC-006** | Une évaluation avec caps de budget non posés et goals couvrant toute la cible s'arrête seule (couverture-complète ∧ yield-sous-seuil). | US-4, Constitution VI |
| **SC-007** | Un agent dans le sandbox, root et instruit de le faire, ne peut ouvrir de connexion hors de l'allowlist. | US-6, FR-107, Constitution IX |
| **SC-008** | La requête `forge status` et le dashboard rapportent un état de fleet, des compteurs de findings et un budget identiques au même instant. | US-2, FR-008, FR-120 |
| **SC-009** | Pour tout finding publié, la chaîne de provenance complète (technique de détection → transcript de triage → tentative de validation → rendu du rapport) est reconstructible depuis les logs. | NFR-007 |
| **SC-010** *(propre à Forge)* | Le dashboard affiche, à tout instant, chaque instance d'agent vivante avec son rôle et son claim courant, et anime les transitions du cycle de vie des findings. | US-2, demande « voir les agents actifs » |

### 1.7 Hypothèses

| ID | Hypothèse | Si fausse |
|---|---|---|
| **A-1** | L'opérateur est autorisé à évaluer la cible (notre propre app) et à sonder le testbed. | — (vrai par construction). |
| **A-2** | Accès en lecture au code source de la cible. | — (vrai). |
| **A-3** | Un LLM frontier avec tool-calling est dispo via API, comptage de tokens par appel. | Mode démo dégradé (voir `plan.md` §Mode sans clé). |
| **A-4** | L'environnement (Docker) peut imposer egress réseau et write FS sous le process agent. | FR-107 non satisfait : refus de démarrer hors conteneur en prod. |
| **A-6** | L'ensemble de travail d'une évaluation tient dans un SQLite atteignable par tous les agents. | Vrai pour la taille de la démo. |
| **A-8** | Le « tracker » (ici le système de fichiers + SQLite) supporte labels, commentaires, create/update programmatique. | Vrai. |

---

## 2. Glossaire

Identique à la seed Foundry (`GLOSSARY.md`), repris ici pour les termes load-bearing :

| Terme | Définition |
|---|---|
| **Cible (Target)** | L'app sous évaluation : son code source + un déploiement jetable (le *testbed*). Ici `targets/vulnshop`. |
| **Testbed** | L'instance live de la cible que les agents sondent et exploitent. Conteneur Docker. |
| **Opérateur** | L'humain qui configure, lance, pilote et arrête une évaluation. |
| **Goals** | Énoncé écrit des résultats qui comptent (ex. « bypass d'authentification », « RCE ») et du périmètre. |
| **Agent** | Worker adossé à un LLM, rôle défini, tournant en boucle, coordonné via le substrate. |
| **Rôle** | Spécialisation d'agent (Detector, Triager…). Un rôle peut avoir plusieurs instances concurrentes. |
| **Fleet** | Toutes les instances d'agents d'une évaluation. |
| **Finding** | Vulnérabilité revendiquée, à n'importe quel stade du cycle de vie. |
| **Candidate** | Finding détecté mais pas encore investigué. |
| **Verdict** | Classification par le Triager : `true-positive`, `false-positive`, `needs-review`, `not-applicable`, `code-quality`. |
| **Evidence gate** | Exigence structurelle qu'un finding doit satisfaire avant `true-positive` (§7.3). |
| **Exploited** | Finding `true-positive` dont l'impact phare a été reproduit indépendamment sur le testbed (§7.4). |
| **Fingerprint** | Identifiant stable d'un finding pour la dédup inter-runs (§7.5). |
| **Carte de sécurité** | Sortie de la Cartographe : archi, surface d'attaque, frontières de confiance, flux de données, modèle de menace. |
| **Règle de détection** | Vérification réutilisable et versionnée pour une classe de vuln, appliquée fonction par fonction. Format CodeGuard. |
| **Rule-gap** | Trace qu'un finding exploratoire confirmé n'aurait été produit par aucune règle ; entrée de la croissance du corpus (FR-042). |
| **Couverture** | Degré auquel les goals ont été crédiblement tentés. |
| **Yield** | Findings confirmés pondérés par sévérité, par unité de dépense, sur fenêtre glissante. |
| **Work queue** | Liste ordonnée et partagée des tâches que les agents claiment (§8). |
| **Finding store** | Enregistrement durable, indexé par fingerprint, de chaque finding à chaque stade. SQLite. |
| **Substrate** | La machinerie non-agent : work queue, finding store, sandbox, budget, dashboard. |
| **Claim** | Détention exclusive et crash-safe d'une unité de travail par un agent. |
| **Sandbox** | La frontière d'isolation autour du fleet (egress réseau + write FS). |

---

## 3. Personas & user stories

### 3.1 Personas

| Persona | Qui | Besoin envers Forge |
|---|---|---|
| **Opérateur** | Ingénieur sécurité qui lance la démo. | Setup faible friction ; visibilité live sur ce que fait le fleet ; confiance que les findings sont réels ; signal « terminé » clair. |
| **Reviewer** | Architecte sécurité qui lit la sortie. | Liste bornée et priorisée, pas mille issues. |
| **Développeur cible** | Possesseur du code incriminé. | Assez de détail par finding pour reproduire et corriger seul. |
| **Builder** | Vous : l'ingénieur qui étend Forge. | Une forme claire à construire, défauts dangereux déjà bien choisis. |

### 3.2 User stories (reprises de la seed, périmètre Forge)

| ID | Pri | En tant que… | Je veux… | Test indépendant |
|---|---|---|---|---|
| **US-1** | P1 | Opérateur | Pointer Forge sur la cible + un fichier goals, lancer une commande, partir. | Depuis un checkout neuf + config valide, `forge up` atteint « fleet running, index queryable ». |
| **US-2** | P1 | Opérateur | Voir à tout moment ce que fait chaque agent, ce qu'il a trouvé, ce qui le bloque. | `forge status` et le dashboard énumèrent chaque agent vivant avec son claim. |
| **US-3** | P2 | Opérateur | Poser une question libre au système et obtenir une réponse ancrée dans l'état réel. | Une question sur un finding connu renvoie le raisonnement enregistré + citation du store. |
| **US-4** | P1 | Opérateur | Être averti quand l'évaluation est finie, et pourquoi. | SC-006. |
| **US-5** | P1 | Opérateur | Poser un plafond de dépense et/ou de temps. | Cap bas → halt en un intervalle de polling ; FR-011 refuse le redémarrage. |
| **US-6** | P1 | Opérateur | Contraindre ce que le fleet peut atteindre sur le réseau et modifier sur disque. | SC-007. |
| **US-7** | P1 | Reviewer | Ne recevoir que des findings ayant passé le contrôle de preuve structurel. | SC-002 ; chaque finding publié porte des citations §7.3 résolvables. |
| **US-8** | P2 | Reviewer | Voir lesquels ont été réellement démontrés sur un système qui tourne. | SC-003. |
| **US-9** | P2 | Reviewer | Un rollup groupant par composant, identifiant les correctifs à plus fort levier, mappant la couverture. | Le rollup existe et groupe ≥1 finding par composant de la carte. |
| **US-10** | P1 | Dév cible | Ouvrir un finding et trouver description auto-suffisante + repro + PoC runnable. | Un dév reproduit un finding `exploited` échantillonné depuis le seul rapport. |
| **US-11** | P2 | Opérateur | Re-runner après changement de cible et dédup. | SC-005. |
| **US-12** | P2 | Opérateur | Confier une tâche précise au fleet et qu'un agent la prenne. | Une tâche queue par l'opérateur est claimée par le rôle adressé en un cycle. |
| **US-13** | P3 | Builder | Échanger un choix d'intégration sans redessiner les rôles. | Remplacer un binding §11 satisfait le même contrat sans toucher un rôle §5. |
| **US-14** | P3 | Builder | Redéployer le corpus de règles ailleurs comme garde-fou de dev. | Le corpus (FR-041) se charge inchangé dans un consommateur externe (skill CodeGuard). |

---

## 4. Vue d'ensemble du système

### 4.1 Forme

Forge est un **fleet d'agents LLM spécialisés** coordonnés par un **substrate partagé**,
supervisés par un **Orchestrateur**, opérant sur une **cible** dans un **sandbox**.
L'opérateur n'a qu'une surface : l'Orchestrateur (contrôle de cycle de vie + accès
conversationnel), doublé d'un **dashboard** en lecture.

```
                                   OPÉRATEUR
                                      │  (CLI forge + dashboard web)
                       ┌──────────────▼──────────────┐
                       │        ORCHESTRATEUR        │
                       │  cycle de vie · conversation │
                       └──────────────┬──────────────┘
                                      │
                       ══════════ SUBSTRATE (SQLite) ══════════
                        work queue · finding store · heartbeats ·
                        sandbox (Docker) · budget · dashboard (WS)
                       ══════════════╤════════════════════════
                                     │
   couche connaissance              │   pipeline de findings              supervision
 ┌─────────┬───────────┐            │ ┌────────┬────────┬──────────┐  ┌────────┬──────────┐
 │ INDEXER │ CARTOGRAPHE│───────────┘ │DETECTOR│TRIAGER │VALIDATOR │  │REPORTER│COVERAGE  │
 │tree-str │ 5 passes   │             │4 modes │evidence│clean-room│  │CWE/CVSS│GUIDE     │
 └─────────┴───────────┘             └────────┴────────┴──────────┘  └────────┴──────────┘
```

### 4.2 Les huit rôles core

| Rôle | Responsabilité en une ligne | Spécifié en |
|---|---|---|
| **Orchestrateur** | Surface unique de l'opérateur : valider config, spawn/maintenir le fleet, exposer le statut, imposer le budget ; répondre aux questions, accepter tâches et steering. Un rôle, deux facettes qui ne se bloquent pas. | §5.1 |
| **Indexer** | Construire l'index de code (symboles, graphe d'appels, cross-refs). Parser déterministe (tree-sitter). | §5.2 |
| **Cartographe** | Construire la carte de sécurité (archi, surface, frontières, flux, modèle de menace). | §5.3 |
| **Detector** | Produire des candidats par application de règles **et** exploration libre. Breadth-first. | §5.4 |
| **Triager** | Investiguer chaque candidat et poser un verdict, gated sur preuve structurelle. Le filtre à bruit. | §5.5 |
| **Validator** | Pour les findings exploitables, reproduire l'impact phare sur le testbed en clean-room. Le filtre à preuve. | §5.6 |
| **Coverage-Guide** | Traduire les goals en checklist, suivre l'avancement, déclarer la couverture complète. Moitié du signal « fini ». | §5.7 |
| **Reporter** | Produire la sortie humaine : writeups par finding + rollup. | §5.8 |

*Chaque rôle existe pour rattraper le mode d'échec du précédent.* (Constitution & §4.2 seed.)

### 4.3 Le substrate

| Composant | Garanties (réalisées par) |
|---|---|
| **Work queue** | Tâches ordonnées ; claim atomique ; release crash-safe à la mort du détenteur ; retry borné avec auto-block. (Table SQLite + transactions + heartbeat.) |
| **Finding store** | Enregistrement durable de chaque finding à chaque stade ; indexé par fingerprint ; interrogeable par tous. (SQLite + FTS5.) |
| **Sandbox** | Egress réseau borné à une allowlist ; write FS borné à des chemins désignés ; survit au root de l'agent. (Réseau Docker + montages read-only.) |
| **Budget governor** | Suit dépense et runtime vs caps ; calcule le yield glissant ; halt sur cap ou yield-sous-seuil une fois la couverture complète. (Compteur de tokens + table SQLite.) |
| **Dashboard** | Vue live opérateur : état du fleet, findings, couverture, budget, yield. (FastAPI + WebSocket, push depuis le substrate.) |

### 4.4 Déroulé d'une évaluation

Identique à la seed §4.5 : (1) l'opérateur écrit `forge.yaml` ; (2) `forge up` valide,
monte le substrate, spawn un Indexer ; (3) l'Indexer construit l'index, gate FR-003 ;
(4) la Cartographe écrit la carte (sans gate) ; (5) les Detectors balayent et explorent,
queue des candidats ; (6) les Triagers investiguent et posent les verdicts ; (7) le
Validator reproduit en clean-room et pose `exploited` ; (8) le Reporter rédige ; (9) la
Coverage-Guide coche les goals ; (10) le budget governor déclenche l'arrêt
(couverture-complète ∧ yield-bas) ; (11) l'opérateur peut interroger/piloter/arrêter à tout
moment via la CLI et voir tout sur le dashboard.

---

## 5. Rôles d'agents — exigences fonctionnelles

> Les FR ci-dessous **reprennent la numérotation de la seed Foundry** (FR-001…FR-129) pour
> tracabilité, en notant les adaptations Forge. Une exigence inchangée est marquée *(seed)* ;
> une exigence adaptée est détaillée.

### 5.1 Orchestrateur

**Cycle de vie.**
- **FR-001** *(seed)* — Valider la config avant tout spawn, refus avec erreur actionnable. La
  config Forge est `forge.yaml` ; validation par schéma Pydantic (FR-129).
- **FR-002 / FR-002a** *(seed)* — Seul l'Orchestrateur spawn/termine des agents ; les agents
  ne spawnent pas de pairs.
- **FR-003** *(seed)* — Gate le spawn des rôles non-Indexer sur l'Indexer « queryable ».
- **FR-004** *(seed)* — Maintenir un compte configuré par rôle, respawn avec backoff (FR-007).
- **FR-005** *(seed)* — Détecter un agent **mort** par absence de heartbeat (FR-100), jamais
  par wall-clock. Wall-clock → rotation FR-118 seulement.
- **FR-006** *(seed)* — Drain gracieux à l'arrêt.
- **FR-007** *(seed)* — Backoff exponentiel sur crash-loop, plafond par tentative, sans
  plafond de tentatives.
- **FR-008** *(seed)* — `forge status` rapporte par agent : rôle, index d'instance,
  vivant/mort, claim courant, âge du dernier heartbeat, compte de redémarrages.
- **FR-009** *(seed)* — Hot-reload de la composition du fleet sans restart complet.
- **FR-010** *(seed)* — Pré-flight : LLM joignable, testbed joignable, rapporte tous les
  échecs d'un coup.
- **FR-011** *(seed)* — Refuser un nouveau run si le précédent a heurté un cap dur non relevé.
- **FR-012** *(seed)* — L'Orchestrateur ne fait jamais lui-même détection/triage/validation/reporting.

**Conversationnel.**
- **FR-013** *(seed)* — Répondre aux questions libres, ancré dans le substrate, avec citations.
- **FR-014** *(seed)* — Accepter des tâches opérateur sur la work queue.
- **FR-015** *(seed)* — Surveiller et résoudre les help requests opérateur.
- **FR-016** *(seed)* — Steering d'un agent : non-disruptif (au prochain idle) ou disruptif.
- **FR-017** *(seed, SHOULD)* — Session interactive tour-par-tour avec un agent.
- **FR-018** *(seed)* — La facette conversationnelle ne modifie pas verdicts/`exploited`/couverture
  de sa propre initiative ; uniquement sur instruction explicite, en l'enregistrant.
- **FR-019** *(seed)* — Lanes d'exécution séparées : une réponse LLM en vol ne retarde pas
  respawn/heartbeat/status/shutdown. **Forge** : la facette cycle de vie est un boucle
  synchrone dédiée ; la facette conversationnelle est un worker asynchrone séparé.

*Forge — forme retenue :* l'Orchestrateur est une **CLI** (`forge init|up|down|status|ask|task|pause|resume`)
avec état persisté au substrate (modèle mono-opérateur mono-machine, cf. clarification §5.1 seed).

### 5.2 Indexer

- **FR-020** *(adapté)* — Inventaire des fonctions/méthodes par fichier in-scope, par **parser
  déterministe tree-sitter (Python)**. L'extraction LLM ne peut pas être l'unique source.
- **FR-021 / FR-021a** *(seed)* — Graphe d'appels (appels statiques directs au minimum).
- **FR-022** *(adapté)* — Interface de requête : get-function-body, get-callers, get-callees,
  find-symbol, full-text (**FTS5**).
- **FR-023** *(retiré au MVP)* — Embeddings/similarité reportés (voir clarifications).
- **FR-024** *(seed)* — Signaler « queryable » seulement quand FR-020/021/022 sont satisfaits.
- **FR-025 / FR-106a** *(seed)* — Persistance atomique (write-new-then-swap) ; un lecteur ne
  voit jamais un index partiel.
- **FR-026** *(seed)* — Incrémental au re-run (seuls les fichiers changés re-parsés).
- **FR-027** *(seed)* — Respecter le scope include/exclude.
- **FR-028** *(seed)* — Dégradation gracieuse sur fichier non parsable (log + skip).
- **FR-029** *(seed)* — L'indexation ne bloque pas la réactivité de l'Orchestrateur
  (frontière de processus).

### 5.3 Cartographe

- **FR-030** — Vue d'ensemble d'architecture (composants, responsabilités, communications).
- **FR-031** — Énumération de surface d'attaque (tout point d'entrée hors frontière de
  confiance : listeners réseau, APIs, CLI, entrées fichier ; auth requise à chacun).
- **FR-032** — Carte des frontières de confiance (où l'input non fiable devient fiable, et
  quelle validation garde chaque passage).
- **FR-033** — Description des flux de données sensibles (credentials, secrets, données
  utilisateur, commandes de contrôle).
- **FR-034** — Modèle de menace synthétisant FR-030..033.
- **FR-035** *(seed)* — Carte persistée, lisible par tous, résumable en digest pour insertion
  dans le prompt d'un autre rôle.
- **FR-036 / FR-036a** *(seed)* — Les rôles fonctionnent (qualité réduite) sans carte ; en cas
  d'échec d'une passe, écrire un fallback minimal mécaniquement dérivable. Une carte vide est
  un échec, pas une dégradation. **Forge** : pipeline d'une passe par document (évite le 0-byte).
- *Pas de gate du fleet sur la Cartographe* (défaut seed).

### 5.4 Detector

- **FR-037** *(adapté)* — Analyse par règles : pour chaque fonction in-scope, appliquer chaque
  règle du corpus comme **check LLM** demandant si la fonction présente la classe de vuln,
  avec corps + contexte callers/callees fournis. Granularité fonction.
- **FR-038** *(adapté)* — Scan de dépendances sur `requirements.txt` ; signaler les versions à
  vulnérabilités publiées (base locale / OSV).
- **FR-039** — Scan de secrets : credentials/clés/tokens en dur dans l'arbre source.
- **FR-040** — Chasse exploratoire : instance avec goals + carte + description testbed + notes
  persistantes en contexte, libre de choisir quoi investiguer, accès lecture source + réseau
  testbed.
- **FR-041** *(adapté)* — Corpus de règles = **artefact versionné indépendant** sous `rules/`,
  **format CodeGuard** (markdown unifié). Ajoutable/révisable/réutilisable hors Forge.
- **FR-042** *(seed)* — Enregistrer un **rule-gap** quand un finding exploratoire confirmé
  n'aurait été produit par aucune règle. C'est le flywheel détection→prévention.
- **FR-043** *(seed)* — Chaque candidat enregistre : localisation (fichier, fonction), classe,
  paragraphe de justification, technique productrice (quelle règle, ou « exploratory »).
- **FR-044** *(seed)* — Le Detector écrit au finding store, **jamais** au tracker / aux humains.
- **FR-045** *(seed)* — Dédup par fingerprint (FR-090) avant écriture.
- **FR-046 / FR-047** *(seed)* — Consulter le coverage log avant de choisir une zone ; le log
  est un journal d'audit, **pas** une stop-list ; aucun « saturé » écrit par un pair ne fait foi.
- **FR-048** *(seed)* — Respecter scope + règles in/out-of-scope.
- **FR-049** *(seed)* — Front-loader le contexte (corps + callers + callees + extrait carte)
  dans le 1er prompt plutôt que via tool calls.

### 5.5 Triager

- **FR-050** *(seed)* — Exactement un verdict parmi les cinq (§7.2).
- **FR-051** *(seed)* — Investiguer avant de verdicter : lire le code, tracer le flux entrée→sink
  via l'index, repérer sanitization/validation, localiser entrée + frontière dans la carte,
  évaluer l'atteignabilité par un attaquant. **Forge** : boucle d'agent outillée guidée par
  cette checklist.
- **FR-052** *(seed)* — Pas de `true-positive` sans **evidence gate** §7.3 satisfaite (US-7).
- **FR-053** *(seed)* — Candidat échouant le gate mais probablement réel → `needs-review`.
- **FR-054** *(seed)* — Enregistrer le raisonnement complet ; un verdict sans rapport est rejeté
  par le store.
- **FR-055** *(seed)* — Court-circuit des candidats hors scope → `not-applicable` sans investigation.
- **FR-056** *(seed)* — Consulter le testbed quand l'exploitabilité est incertaine depuis le code.
- **FR-057** *(seed)* — Surfacer aux humains (via Reporter) seulement sur `true-positive`.
  **Forge** : `needs-review` reste interne (interrogeable au dashboard).
- **FR-058** *(seed)* — Hériter des verdicts non-`true-positive` fingerprint-équivalents d'un run
  antérieur ; utiliser les `true-positive` antérieurs comme priors.
- **FR-059** *(seed)* — Idempotent : re-triage remplace, ne duplique pas.

### 5.6 Validator

- **FR-060** *(seed)* — Pour chaque `true-positive`, testbed présent, tenter la reproduction de
  l'impact en **clean-room** : instance fraîche, recevant le rapport + l'artefact PoC, sans état
  conversationnel partagé. Non gated sur un hint « exploitabilité » du Triager.
- **FR-061** *(seed)* — Poser `exploited` **seulement** si l'impact phare est directement observé
  sur le testbed live. Listés comme NON-`exploited` : payload accepté sans effet observé ; sink
  atteint au debugger ; branche atteinte sans déclenchement final ; toute repro sans testbed.
- **FR-062** *(seed)* — Sur échec, explication structurée ; ne pas effacer le `true-positive`.
- **FR-063** *(seed)* — PoC auto-suffisant et runnable en cas de succès (US-10).
- **FR-064** *(seed)* — Opérer dans le sandbox, honorer les hard rules. Repro nécessitant une
  violation → not-exploited avec raison.
- **FR-065** *(seed, SHOULD)* — Limiter le nombre de tentatives par finding.
- **FR-066** *(seed)* — Sans testbed → PoC sans exécution, jamais `exploited`. (Non déclenché ici :
  testbed toujours présent.)

### 5.7 Coverage-Guide

- **FR-067** *(seed)* — Dériver à la 1re passe une checklist finie d'items (composant × goal),
  chacun avec sa barre de « crédiblement tenté ».
- **FR-068** *(seed)* — Ne jamais inventer de goals ; goals vides → attendre et re-checker.
- **FR-069** *(seed)* — À chaque cycle, rassembler les preuves et cocher ; « cherché, rien trouvé »
  satisfait autant que « trois findings ». La couverture mesure la tentative, pas le résultat.
- **FR-070** *(seed)* — Queue des tâches dirigées pour les items sans activité.
- **FR-071** *(seed)* — Poser le flag couverture-complète seulement quand tous les items sont clos ;
  l'effacer si l'opérateur change les goals.
- **FR-072** *(seed)* — Ne détecte/triage/valide/clôt pas elle-même. Elle lit, juge, oriente.
- **FR-073** *(seed, SHOULD)* — Estimer le travail restant chaque cycle, une ligne de base.
- **FR-074** *(seed)* — Persister la checklist atomiquement à travers les restarts.

### 5.8 Reporter

- **FR-075** *(seed)* — Rapport auto-suffisant par `true-positive` : titre, composant + localisation,
  description, prérequis attaquant, impact, étapes de repro, preuve du Triager, réf PoC si `exploited`.
- **FR-076** *(adapté)* — Classe de faiblesse = **CWE**.
- **FR-077** *(adapté)* — Sévérité = **tier qualitatif** (critical/high/medium/low) + score CVSS 3.1
  indicatif.
- **FR-078** *(adapté)* — Publier chaque rapport comme **exactement un fichier Markdown** sous
  `runs/<id>/reports/` (+ option un GitHub Issue), labels : `forge:src`, `verdict:`, `sev:`,
  `exploited:`, `cwe:`, `owasp:`.
- **FR-079** *(seed)* — Ne pas publier un verdict ≠ `true-positive`.
- **FR-080** *(seed)* — Mettre à jour, pas dupliquer, le rapport d'un finding qui change.
- **FR-081** *(seed)* — Rollup : compte par sévérité × `exploited` ; findings groupés par composant
  (carte) ; statut de couverture par goal.
- **FR-082** *(seed, SHOULD)* — Identifier les findings-clés (fix cassant le plus de chemins) ;
  proxy = in-degree des cross-refs.
- **FR-083** *(seed)* — Les rapports ne nomment pas le modèle/provider, ni les IDs internes
  d'agents, ni les hostnames internes.
- **FR-084** *(adapté)* — Chaque localisation citée est un permalink `chemin#Lx-Ly` piné sur le SHA
  du run (format GitHub si export activé).

---

## 6. Cycle de vie des findings

### 6.1 États (identique seed §7.1)

```
candidate ─(triage)─► verdict assigné ─TP─► confirmed ─(validate)─► confirmed[exploited?] ─(report)─► published
                                       └─FP/NA/CQ/NR─► recorded (interne)
```

### 6.2 Verdicts (§7.2 seed)

`true-positive` (surfacé), `false-positive`, `needs-review`, `not-applicable`, `code-quality`
(non surfacés). **FR-085** : exactement un verdict, mutable. **FR-086** : le store retient les
non-`true-positive` avec leur raisonnement.

### 6.3 Evidence gate (§7.3 seed — cœur du système)

- **FR-087** — Un `true-positive` est accompagné d'un rapport citant au moins une localisation de
  code pour chacun de : (a) **atteignabilité** depuis un point d'entrée attaquant ; (b) **frontière
  de confiance** franchie sans validation suffisante ; (c) **impact** concret au sink.
- **FR-087a** — Carve-out « la présence est la vuln » (secret en dur CWE-798, crypto déprécié
  CWE-327…) : la jambe frontière peut être « le dépôt source lui-même », l'atteignabilité « inclus
  au build » ; la jambe impact reste obligatoire.
- **FR-088** — Chaque localisation citée est **mécaniquement vérifiée** comme résolvant vers du
  code réel au moment du verdict ; une citation non résolvante **démote** en `needs-review`.

*C'est le contrôle qualité le plus important : on ne demande pas au modèle d'être prudent, on exige
que sa revendication soit vérifiable, et on la vérifie.* (Constitution I.)

### 6.4 Exploited (§7.4)
- **FR-089** — `exploited` est un flag sur un `true-positive`, posé **seulement** par le Validator
  (FR-060/061), jamais inféré.

### 6.5 Fingerprint (§7.5)
- **FR-090** — Hash déterministe de (chemin normalisé, nom de fonction/symbole, classe de vuln).
  **Sans** numéro de ligne, snippet, ni timestamp.
- **FR-091** — Toute dédup clé sur le fingerprint.

### 6.6 Labels (§7.6)
- **FR-092 / FR-093** — Set minimal fixe (cf. FR-078) + un label transitoire « in-progress »
  posé par tout rôle tenant un claim.

---

## 7. Substrate de coordination (§8 seed)

- **FR-094** *(seed)* — Work queue : id stable, titre, description, position de priorité, état
  (`open`/`blocked`/`closed`). Plusieurs files nommées partageant la même sémantique (coverage log,
  checklist, handoff) = instances d'un seul mécanisme.
- **FR-095** *(seed)* — Claim **atomique** (transaction SQLite ; deux claimants concurrents → unités
  différentes).
- **FR-096** *(seed)* — Claim **lié à la liveness** : libéré dans un délai borné à la mort du détenteur.
- **FR-097** *(seed)* — Une tâche claimée/relâchée N fois sans complétion (N=3 par défaut) → `blocked`.
- **FR-098 / FR-098a** *(seed)* — Queue éditable opérateur+agent à chaud ; un agent qui découvre du
  travail hors de son claim **queue une nouvelle tâche** plutôt que de la chasser inline ou steerer un pair.
- **FR-099** *(seed)* — Ids de tâche stables et distincts des positions de priorité.
- **FR-100 / FR-101** *(seed)* — Heartbeat à intervalle court fixe, lane d'exécution dédiée ;
  liveness = âge du heartbeat sous seuil ; jamais le wall-clock.
- **FR-102…102d** *(seed)* — Messages pairs = advisory ; **operator messages** asynchrones
  (`blocker`/`request`/`feedback`/`info`), dédupliqués, sans attente de réponse.
- **FR-103 / FR-104…104b** *(seed)* — Pas de status via messages pairs ; notes partagées bornées,
  lock-protégées, sans claim de couverture/« done ».
- **FR-105 / FR-106** *(seed)* — Le provider est l'arbitre du débit : pas de cap interne sous la
  limite réelle ; backoff partagé fleet-wide sur 429.
- **FR-106a** *(seed)* — Persistance atomique générale (write-new-then-swap).

---

## 8. Gouvernance & sûreté (§9 seed)

- **FR-107** *(adapté)* — Le fleet tourne dans une **isolation Docker** contraignant l'egress à une
  allowlist (API Anthropic + testbed, rien d'autre par défaut) qu'un agent root interne ne peut
  contourner. Sandbox par l'infra, pas par le prompt (Constitution IX).
- **FR-108** *(seed)* — Monter source, config, prompts et la définition du sandbox en **read-only**.
- **FR-109** *(seed)* — Informer l'opérateur que les destinations allowlistées sont des points de
  pivot.
- **FR-110 / FR-111** *(seed)* — Bloc de hard rules opérateur dans le system prompt de chaque agent ;
  par défaut, interdire DoS, suppression/modif de données, changement de credentials, actions sur
  d'autres utilisateurs que les test users.
- **FR-112 / FR-113 / FR-114** *(seed)* — Suivre dépense (devise) et runtime cumulés vs caps ;
  comptabiliser chaque appel par tokens ; caps par défaut non posés, pré-flight avertit.
- **FR-115 / FR-116 / FR-117** *(seed)* — Yield glissant = findings confirmés pondérés sévérité ×
  `exploited`, / dépense, sur fenêtre ; halt seulement si (a) une fenêtre pleine accumulée, (b)
  runtime min écoulé, (c) couverture-complète. Poids géométriques (~3.16×/tier), ×2 pour `exploited`.
- **FR-118 / FR-119 / FR-119a** *(seed)* — Limites de session souples/dures (rotation, pas liveness) ;
  un agent sans travail utile peut se retirer ; interdiction d'inventer du busywork.

---

## 9. Observabilité (§10 seed) & dashboard

- **FR-120** *(adapté)* — **Dashboard temps réel** (FastAPI + WebSocket) affichant : chaque agent
  vivant avec rôle/instance/claim/âge heartbeat ; compteurs de findings par état et verdict ; barre
  de couverture par goal ; budget (dépense, runtime, yield glissant). Source unique = substrate
  (SC-008). C'est le livrable « voir les agents actifs » (SC-010).
- **FR-121** *(seed)* — Logs structurés par agent et par finding.
- **FR-122** *(seed)* — Provenance reconstructible (NFR-007).
- **FR-123 / FR-124** *(seed)* — Événements de cycle de vie poussés au dashboard ; cohérence
  status/dashboard.
- **FR-125** *(seed)* — État « dégradé » surfacé sur 429/quota.

---

## 10. Modèle de configuration (§12 seed)

`forge.yaml`, un fichier par évaluation, sections : `target`, `testbed`, `goals`, `rules`,
`detection`, `fleet`, `sandbox`, `budget`, `integrations`. **FR-126** : un seul document
versionné. **FR-127** : pas de secrets dans la config (référencés via env / `.env` non versionné).
**FR-128/128a** : hot-reload de `budget` et `rules` ; `target`/`sandbox`/`integrations` peuvent
exiger un restart. **FR-129** : champs requis manquants → échec de validation nommant chaque champ.

---

## 11. Exigences non fonctionnelles (§13 seed)

NFR-001 résumabilité (checkpoints LangGraph + substrate) · NFR-002 idempotence · NFR-003 *(retiré,
mono-tenant)* · NFR-004 déterminisme structurel (testable sans LLM live) · NFR-005 dégradation
gracieuse · NFR-006 proportionnalité du coût · NFR-007 auditabilité · NFR-008 pas de perte
silencieuse · NFR-009 override opérateur · NFR-010 posture anti-injection (sandbox + montages RO
= la couche d'enforcement ; l'hygiène de prompt n'est que défense en profondeur).

---

## 12. Traçabilité

Chaque FR ci-dessus cite son origine seed (FR-NNN homonyme). Les SC §1.6 lient FRs et user stories.
`tasks.md` indexe chaque tâche de build sur les FRs qu'elle réalise. La conformité à la constitution
(11 principes) est re-vérifiée à chaque jalon via `/speckit.analyze` (voir `plan.md` §Vérification).
