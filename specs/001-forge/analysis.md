# Forge — Analyse approfondie du pipeline

> Document d'architecture. Analyse critique de la *seed* Foundry telle que Forge l'implémente,
> sous quatre angles demandés : (1) où améliorer le pipeline ; (2) quels outils externes
> intégrer dans le travail des agents ; (3) comment garder l'asynchronisme ; (4) comment
> normaliser les échanges inter-agents (taxonomie + paramètres) et garantir la bonne gestion
> de la concurrence (lock/release des tâches).
>
> Les recommandations d'outils sont datées de juin 2026 (voir *Sources*).

---

## 1. Lecture critique : où le pipeline peut gagner

La force de Foundry est l'invariant « **Evidence over Assertion** » : aucun agent ne s'attribue
`true-positive`, c'est le gate qui décide sur citations résolvables. Mais la seed laisse le LLM
au centre de presque chaque étape, ce qui crée trois zones d'amélioration nettes.

### 1.1 Détection — passer du « tout-LLM » au « LLM arbitre d'oracles déterministes »

La seed (FR-037) fait évaluer **chaque fonction** par le LLM contre **chaque règle**. C'est
coûteux (NFR-006 : le coût doit suivre la taille de la cible, pas le nombre d'agents) et le
recall dépend de la qualité du corpus. **Amélioration** : intercaler des analyseurs statiques
déterministes (Semgrep, CodeQL, Bandit) **en amont** comme pré-filtre à fort rappel. Le LLM ne
raisonne plus à blanc : il reçoit les points chauds signalés par les outils + le contexte de
graphe d'appels, et concentre ses tokens sur le *raisonnement de data-flow* et l'exploration,
là où il est irremplaçable. On garde l'exploration libre (FR-040) pour ce qu'aucun outil ne
décrit. Bénéfice : coût ↓, rappel ↑, et chaque candidat arrive déjà avec une trace d'outil
réutilisable comme preuve.

### 1.2 Triage — vérifier mécaniquement la jambe « atteignabilité », pas seulement la citation

Le gate FR-088 vérifie que les citations **résolvent** vers du code réel. C'est nécessaire mais
faible sur les classes *data-flow* (injection, SSRF, IDOR) : la seed reconnaît elle-même que le
gate « vérifie que les citations résolvent, pas que l'argument est valide » (FR-087a). **Amélioration** :
brancher une **analyse de taint** (CodeQL ou Semgrep en mode dataflow, Joern en *code property
graph*) pour confirmer mécaniquement qu'il existe un chemin source→sink. La jambe (a)
atteignabilité devient un fait vérifié par outil, pas une prose vérifiée par résolution. Le gate
passe alors de « les citations existent » à « le chemin existe ». C'est le levier de précision
le plus fort au-delà de l'existant.

### 1.3 Validation — donner au Validator des oracles d'exploitation réels

`exploited` n'est posé que sur impact directement observé (Constitution VII). Aujourd'hui le PoC
est largement LLM-écrit. **Amélioration** : équiper le Validator d'**oracles d'exploitation
déterministes** (sqlmap pour SQLi, Dalfox pour XSS, Nuclei pour les templates connus, ZAP en
attaque dirigée). L'oracle exécute, observe l'effet, et **renvoie un verdict binaire** que le
LLM ne peut pas rationaliser. Le PoC livré (FR-063) est alors la commande/template de l'oracle,
reproductible par un humain sans le système (US-10). L'« agent qui note son propre exploit »
disparaît : l'oracle note.

### 1.4 Autres gains transverses

- **Mémoïsation** : clé de cache `hash(corps de fonction + version de règle)` → ne pas
  re-soumettre au LLM une fonction inchangée entre deux runs (renforce NFR-002/006).
- **Indexer enrichi** : au-delà du graphe d'appels (FR-021), produire un **Code Property Graph**
  (Joern) pour que Triager/Detector posent de vraies requêtes de flux, pas seulement « qui
  appelle qui ».
- **Flywheel outillé** : un rule-gap (FR-042) ne devrait pas seulement produire une règle
  CodeGuard en markdown ; il devrait **émettre aussi une règle Semgrep** exécutable, qui
  rejoint le pré-filtre §1.1. Le tour de boucle améliore alors la détection déterministe, pas
  seulement la détection LLM.
- **Couverture taxonomique** : ancrer la checklist Coverage-Guide sur CWE Top 25 + OWASP Top 10
  pour que « crédiblement tenté » ait une grille objective.

> **Principe directeur de toutes ces améliorations** : *le LLM est le raisonneur et l'explorateur ;
> les outils sont les oracles.* On ne remplace jamais le gate ni l'exploration — on leur donne
> des faits vérifiables en entrée et des verdicts binaires en sortie.

---

## 2. Outils externes à intégrer, par rôle

Chaque agent appelle ces outils comme **tools** (au sens LangChain) dans son sandbox. Tous sont
open-source et maintenus à jour (juin 2026). La règle : sortie machine (SARIF/JSON) → normalisée
dans nos schémas (§4) → fournie au LLM comme preuve.

| Rôle | Outils déterministes (oracles) | Ce qu'ils apportent |
|---|---|---|
| **Indexer** | **tree-sitter** (parsing multi-langage), **Joern** (Code Property Graph), LSP/`ctags` | Inventaire déterministe (FR-020) + graphe de flux pour les requêtes de Triager. |
| **Cartographe** | **OWASP ZAP** (spider/passive scan pour énumérer la surface live), `httpx`/`katana` (découverte d'endpoints), **Arjun** (découverte de paramètres) | Surface d'attaque réelle (FR-031) corroborée par le trafic, pas seulement inférée du code. |
| **Detector — règles** | **Semgrep CE** (rapide, 30+ langages, règles YAML custom), **CodeQL** (analyse sémantique/taint, nightly), **Bandit** (Python) | Pré-filtre haut-rappel §1.1 ; chaque hit = candidat pré-étayé. Complémentaires : Semgrep à chaque passe, CodeQL en profondeur. |
| **Detector — deps** | **OSV-Scanner** (lockfiles, OSV.dev 20+ sources), **Grype** (scores **EPSS** + **CISA KEV**), **Trivy** (SCA+IaC+secrets en un binaire) | FR-038 grounded sur des CVE réelles + priorisation par probabilité d'exploitation. Recouvrement faible (~60 %) → en lancer deux. |
| **Detector — secrets** | **Gitleaks** (regex+entropie, instantané), **TruffleHog** (vérification *live* du credential) | FR-039 : Gitleaks pour le balayage, TruffleHog pour confirmer qu'un secret est **actif** (réduit les faux positifs). |
| **Triager** | **CodeQL/Semgrep dataflow**, **Joern** (requêtes source→sink) | Confirme mécaniquement la jambe atteignabilité du gate §1.2 (FR-087a). |
| **Validator** | **sqlmap** (SQLi), **Dalfox** (XSS), **Nuclei** (templates CVE/exposition), **OWASP ZAP** (attaque dirigée), **commix** (cmd-injection) | Oracles d'exploitation : verdict binaire d'impact observé → `exploited` non rationalisable (§1.3, Constitution VII). |
| **Reporter** | Export **SARIF**, mapping **CWE/CVSS 3.1/OWASP**, génération **CycloneDX** (SBOM) | Interop : SARIF se charge dans GitHub Code Scanning, CVSS/CWE normalisent la sévérité (FR-076/077). |
| **Coverage-Guide** | Référentiels **CWE Top 25**, **OWASP Top 10**, **MITRE ATT&CK** | Grille objective de « crédiblement tenté » (FR-067). |

**Intégration sûre (rappel constitution IX/FR-107)** : ces outils tournent **dans le sandbox
Docker**, egress limité au testbed + à l'API LLM. sqlmap/ZAP/Nuclei ne visent **que** le testbed
jetable ; les hard rules (FR-110/111) le réaffirment en défense en profondeur. Les outils
produisent des fichiers sous `runs/<id>/` (read-write borné), jamais ailleurs.

**Format pivot recommandé : SARIF.** La plupart de ces outils émettent du **SARIF** (Static
Analysis Results Interchange Format, standard OASIS). L'adopter comme format d'entrée normalisé
des candidats (avant traduction dans notre schéma `Finding`) évite N adaptateurs ad hoc et
ouvre l'interop (GitHub, IDE). Pour l'échange de findings inter-systèmes, **OCSF** est l'option
montante côté SOC.

---

## 3. Garder l'asynchronisme du pipeline

La seed est **throughput-oriented, pas latency-oriented** (A-7) : c'est une architecture
asynchrone par nature. Forge doit l'assumer explicitement à chaque couche.

### 3.1 Modèle : producteurs/consommateurs découplés par le substrate

Aucun agent n'appelle un autre agent en direct (pas de RPC synchrone inter-rôles — ce serait un
couplage que la seed interdit de fait via FR-002a et le travail par file). **Tout passe par la
work queue et le finding store** : le Detector *produit* des candidats, le Triager les
*consomme* quand il est libre, etc. Conséquence : chaque rôle est un **worker asynchrone** qui
boucle `claim → travaille → persiste → release`, sans jamais bloquer en attendant un pair. Les
*operator messages* (FR-102a) sont **one-way, sans attente de réponse** — « un fleet qui attend
des réponses humaines est un fleet qui passe son temps en pause ».

### 3.2 Réalisation technique

- **`asyncio`** comme socle ; **LangGraph async** (`astream_events`) pour la boucle de chaque
  agent → les événements streamés alimentent directement le WebSocket du dashboard.
- **Appels LLM asynchrones** avec **backoff partagé fleet-wide** sur 429 (FR-105/106) : le
  provider est l'arbitre du débit, pas un cap interne.
- **Lanes d'exécution séparées** (FR-019, FR-101) : le heartbeat et la boucle de cycle de vie de
  l'Orchestrateur ne partagent **jamais** le thread/lane d'un appel LLM. Sinon un appel lent est
  lu comme un process figé. Heartbeat = thread dédié ; conversation = worker async distinct ;
  cycle de vie = boucle déterministe.
- **I/O non bloquantes** pour les outils externes (§2) : `asyncio.create_subprocess_exec` pour
  sqlmap/Semgrep/etc., avec timeout, plutôt qu'un `subprocess.run` bloquant.
- **Backpressure** : la profondeur des files borne le travail en vol ; pas de cap artificiel sur
  les appels (Constitution V), mais une borne sur les claims concurrents par instance pour ne
  pas saturer le testbed.
- **Consommateurs idempotents** (NFR-002) : re-traiter un message déjà traité ne crée pas de
  doublon (clé = fingerprint). Indispensable dès qu'il y a retry.
- **Résumabilité** (NFR-001) : checkpoints LangGraph + état au substrate ⇒ une opération longue
  reprend de son dernier point après mort de process. *Option avancée* : un moteur d'exécution
  durable (Temporal) si on veut des garanties workflow plus fortes — surdimensionné pour le MVP.

### 3.3 Anti-patterns à proscrire

Pas de `await` d'un rôle sur le résultat d'un autre rôle ; pas de heartbeat sur la lane de
travail ; pas de cap de concurrence sous la limite réelle du provider ; pas d'état de
coordination en mémoire seule (il doit survivre à la mort du process — sinon Constitution III/IV
sont violées).

---

## 4. Normalisation des échanges inter-agents (taxonomie + paramètres)

C'est le point qui fait la différence entre « un tas d'agents qui se parlent » et « un système ».
Tout échange — entre agents, vers le store, vers le dashboard — passe par des **schémas typés et
versionnés** (Pydantic = contrat exécutable). Rien en texte libre non structuré sur le chemin
critique.

### 4.1 L'enveloppe commune (tout message la porte)

```python
class Envelope(BaseModel):
    msg_id: UUID                      # identité du message
    schema_version: str               # ex. "1.0" — versionné, jamais cassé en place
    producer_role: Role               # Detector | Triager | ...
    producer_instance: str            # ex. "detector-2"
    ts: datetime                      # horodatage UTC
    correlation_id: str               # = fingerprint du finding concerné (relie tout son cycle)
    causation_id: UUID | None         # le msg_id qui a causé celui-ci (traçabilité de chaîne)
    payload_type: PayloadType         # Candidate | Verdict | ExploitResult | Task | OperatorMessage | Event
    payload: dict                     # validé contre le schéma de payload_type
```

`correlation_id` + `causation_id` donnent la **provenance reconstructible** (NFR-007, SC-009) :
on rejoue toute la chaîne d'un finding du candidat à la publication.

### 4.2 Les taxonomies (vocabulaires fermés, paramètres définis)

| Taxonomie | Valeurs autorisées | Autorité |
|---|---|---|
| **Rôle** | `orchestrator, indexer, cartographer, detector, triager, validator, coverage_guide, reporter` | spec §4.2 |
| **Verdict** | `true-positive, false-positive, needs-review, not-applicable, code-quality` | spec §6.2, ensemble **fermé** (FR-050) |
| **État du finding** | `candidate → verdict_assigned → confirmed → confirmed[exploited?] → published` / `recorded` | spec §6.1 |
| **Classe de vuln** | **CWE** (id) — référentiel externe stable | FR-076 |
| **Sévérité** | tier `critical/high/medium/low` **+** score **CVSS 3.1** + vecteur | FR-077 |
| **Conformité** | **OWASP Top 10 2021** (cat.) — mapping secondaire | clarifications |
| **Technique de détection** | `rule:<rule-id>, deps, secrets, exploratory` | FR-043 |
| **Kind d'operator message** | `blocker, request, feedback, info` (fermé) | FR-102a |
| **Kind d'event** | `claim, release, state_change, tool_run, llm_call, halt, ...` | observabilité |

Une valeur hors taxonomie est **rejetée à la validation** : c'est ce qui empêche la dérive
sémantique entre agents.

### 4.3 Les schémas de payload load-bearing

**`Candidate`** (Detector → store, FR-043) — `file, symbol, vuln_class(CWE), description,
technique, tool_evidence[] (SARIF refs), fingerprint`.

**`Verdict`** (Triager, le gate matérialisé, FR-087/088) :
```python
class Citation(BaseModel):
    file: str; symbol: str; line_start: int; line_end: int; resolved: bool
class Verdict(BaseModel):
    verdict: VerdictEnum
    reachability: Citation | None      # jambe (a)
    trust_boundary: Citation | None    # jambe (b)  (ou "le dépôt" pour FR-087a)
    impact: Citation                   # jambe (c) — toujours requise
    dataflow_path: list[str] | None    # chemin source→sink confirmé par outil (§1.2)
    reasoning: str
```
Le gate est une **fonction de validation de ce schéma**, pas du parsing de prose : si
`verdict == true-positive` et qu'une jambe manque ou que `resolved == false`, **démotion
automatique** en `needs-review`. Le contrat *est* le contrôle qualité.

**`ExploitResult`** (Validator, FR-060/061) — `finding_fp, oracle (sqlmap|dalfox|nuclei|zap|llm),
observed_impact: bool, poc_artifact_path, transcript_ref`. `exploited` ne peut passer à `true`
que si `observed_impact == true` **et** `oracle != llm-self`.

**`Task`** (work queue, FR-094/099) — `task_id (stable), queue, title, description, priority,
state, claimed_by, claim_ts, lease_until, release_count, fencing_token`.

**`OperatorMessage`** (FR-102a-d) — `kind, body, dedup_hash, acked`. `dedup_hash` réalise la
déduplication fleet-wide (FR-102b).

### 4.4 Gouvernance des schémas

Versionnés (`schema_version`), évolution additive seulement (jamais casser un champ en place —
écho de Constitution XI sur la persistance). Stockés comme **JSON Schema** générés depuis
Pydantic, publiés sous `schemas/` → un consommateur externe (ou un futur rôle) valide sans lire
le code. Pour les findings, **SARIF** en import (depuis les outils) et **SARIF/OCSF** en export.

---

## 5. Gestion de la concurrence : lock / lease / release d'une tâche

C'est l'exigence centrale de la seed (Constitution IV : « Claims Are Atomic And Mortal ») et la
demande explicite. Le principe : **une tâche est tenue par au plus un agent à la fois, le lock
est automatiquement libéré à la fin OU à la mort de l'agent, jamais bloqué indéfiniment.**

### 5.1 Le claim atomique (un seul gagnant)

Compare-and-set transactionnel dans SQLite — pas de race possible (FR-095) :

```sql
-- Un agent tente de claimer ; rowcount==1 ⇒ il a gagné, ==0 ⇒ un autre l'a déjà.
UPDATE tasks
   SET claimed_by   = :agent_id,
       claim_ts     = :now,
       lease_until  = :now + :lease_ttl,
       fencing_token = fencing_token + 1
 WHERE task_id    = :task_id
   AND state      = 'open'
   AND claimed_by IS NULL;            -- la condition qui sérialise les concurrents
```

Deux agents qui exécutent ceci en parallèle : la transaction SQLite sérialise, exactement un
obtient `rowcount == 1` (FR-095, Constitution IV). L'autre reçoit 0 et claime une autre tâche
ou « none ».

### 5.2 Le lease mortel (lié à la liveness, jamais à l'horloge de travail)

Le claim n'est **pas** éternel : il porte un **lease** (`lease_until`) que l'agent **renouvelle**
via son heartbeat (FR-100). Le superviseur (Orchestrateur) libère tout claim dont le lease est
périmé — c'est-à-dire dont l'agent ne heartbeat plus (FR-096, Constitution III) :

```sql
-- Récupération des claims morts : exécutée périodiquement par le superviseur.
UPDATE tasks
   SET claimed_by = NULL, lease_until = NULL,
       state = CASE WHEN release_count + 1 >= :N then 'blocked' ELSE 'open' END,
       release_count = release_count + 1
 WHERE claimed_by IS NOT NULL
   AND lease_until < :now;            -- lease expiré = agent présumé mort
```

**Paramètres bien définis** (configurables, `forge.yaml`/défauts) :

| Paramètre | Rôle | Défaut |
|---|---|---|
| `heartbeat_interval` | période d'émission du heartbeat (lane dédiée) | 10 s |
| `lease_ttl` | durée du lease ; **doit** être ≥ `k × heartbeat_interval` (k≈3) pour tolérer une latence | 30 s |
| `claim_max_retries` (N) | nb de claim/release sans complétion avant `blocked` (FR-097) | 3 |
| `reclaim_scan_interval` | période de scan des leases expirés par le superviseur | 5 s |
| `session_soft / session_hard` | rotation de session (FR-118), **distincte** de la liveness | 150 / 165 min |

Distinction cruciale (Constitution III) : `lease_ttl` borne la **liveness** (mort → reclaim) ;
`session_hard` borne la **durée de session** (rotation) et **ne re-queue jamais** le travail
roté — l'agent l'a relâché proprement au soft limit d'abord.

### 5.3 Fencing token : empêcher un agent « zombie » de corrompre

Problème classique des locks à lease : un agent figé (GC, swap, réseau) dont le lease expire est
reclaimé ; un autre agent prend la tâche ; puis le premier « revient à la vie » et écrit son
résultat périmé. **Parade** : chaque claim incrémente un `fencing_token` monotone (cf. §5.1).
Toute écriture au finding store porte le token de son claim ; le store **rejette** une écriture
dont le token est inférieur au token courant de la tâche. Le zombie ne peut pas écraser le
travail du nouveau détenteur. (Détail souvent négligé, décisif pour la correction sous
concurrence réelle.)

### 5.4 Release propre en fin de travail

À la complétion, l'agent libère explicitement et passe la tâche à `closed`, dans la **même
transaction** que l'écriture du résultat (atomicité résultat+release) :

```sql
BEGIN;
  INSERT INTO findings (...) VALUES (...);          -- le résultat
  UPDATE tasks SET state='closed', claimed_by=NULL, lease_until=NULL
   WHERE task_id=:task_id AND fencing_token=:my_token;   -- garde-fou anti-zombie
COMMIT;
```

Si `fencing_token` ne correspond plus (l'agent a été reclaimé entre-temps), la transaction
n'affecte aucune ligne → l'agent sait qu'il a perdu le claim et abandonne son écriture.

### 5.5 Propriétés garanties

- **Exclusion mutuelle** (au plus un détenteur) — §5.1, FR-095.
- **Absence de famine / pas de strand** — un lease expiré est toujours récupéré ; un mort ne
  bloque rien (§5.2, FR-096, SC-004).
- **Progression bornée** — auto-block après N échecs (FR-097) évite le grinding éternel.
- **Sûreté sous reprise** — fencing tokens empêchent l'écrasement par un zombie (§5.3).
- **Atomicité résultat+release** — pas d'état « fait mais non relâché » ni « relâché mais non
  écrit » (§5.4, Constitution XI).
- **Pas de coordination en mémoire** — tout est au substrate, donc survit aux morts de process.

C'est exactement le test SC-004 : tuer n'importe quel agent à tout moment ne laisse aucune unité
bloquée ; son claim est libéré et re-pris par un pair dans la fenêtre `lease_ttl`, sans action
opérateur.

---

## 6. Synthèse : ce que ces choix changent

| Axe | Seed Foundry | Forge amélioré |
|---|---|---|
| Détection | LLM sur chaque fonction × règle | Oracles SAST/SCA/secrets en pré-filtre + LLM raisonneur + exploration (coût ↓, rappel ↑) |
| Gate de triage | Citations résolvent | Citations résolvent **+** chemin taint confirmé par outil |
| Validation | PoC LLM | Oracles d'exploitation (sqlmap/Dalfox/Nuclei/ZAP), verdict binaire |
| Échanges | comportement décrit | Enveloppe typée versionnée + taxonomies fermées + SARIF/OCSF |
| Concurrence | « atomic & mortal » (principe) | Claim CAS + lease lié au heartbeat + **fencing tokens** + release transactionnel |
| Asynchronisme | throughput-oriented (A-7) | asyncio + LangGraph async + lanes séparées + backoff partagé + I/O outils non bloquantes |

Aucune de ces améliorations ne touche aux 11 principes constitutionnels : elles les **renforcent**
(plus de preuve mécanique, plus de robustesse de concurrence) plutôt qu'elles ne les diluent.

---

## Sources (état des outils, juin 2026)

- SAST — Semgrep vs CodeQL (complémentarité, perfs, couverture) : [Konvu](https://konvu.com/compare/semgrep-vs-codeql), [AppSec Santa](https://appsecsanta.com/sast-tools/semgrep-vs-codeql), [Xygeni — Top SAST 2026](https://xygeni.io/blog/top-sast-tools/)
- SCA — OSV-Scanner / Grype / Trivy (EPSS, KEV, recouvrement ~60 %) : [google/osv-scanner](https://github.com/google/osv-scanner), [AppSec Santa](https://appsecsanta.com/sca-tools/osv-scanner-vs-grype), [Aikido — dependency scanners 2025](https://www.aikido.dev/blog/top-open-source-dependency-scanners)
- Secrets — Gitleaks vs TruffleHog (regex/entropie vs vérification live) : [AppSec Santa](https://appsecsanta.com/secret-scanning-tools/gitleaks-vs-trufflehog), [Jit](https://www.jit.io/resources/appsec-tools/trufflehog-vs-gitleaks-a-detailed-comparison-of-secret-scanning-tools)
- Exploitation/DAST — Nuclei, ZAP, sqlmap, Dalfox, Arjun : [PlexTrac — pentest tools 2026](https://plextrac.com/the-most-popular-penetration-testing-tools-this-year/), [Beagle Security — OWASP tools 2026](https://beaglesecurity.com/blog/article/best-owasp-security-testing-tools.html)
