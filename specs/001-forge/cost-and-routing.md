# Forge — Coût de l'évaluation & routage des modèles

> Document de conception. Comment Forge **comptabilise**, **calcule**, **arbitre** le coût d'une
> évaluation (consommation et coût des tokens), et comment il **choisit le modèle à l'usage**
> (local vs cloud) tâche par tâche.
>
> Réalise et approfondit la seed Foundry §9.3 (budget, FR-112/113/114), §9.4 (yield auto-stop,
> FR-115/116/117), §11.2 (provider LLM), NFR-006 (proportionnalité du coût). Tarifs cités :
> juin 2026 (voir *Sources*) — **chargés depuis la config, jamais codés en dur**.

---

## 1. Pourquoi le coût est un citoyen de première classe

Un fleet d'agents LLM autonomes est, financièrement, une boucle ouverte : sans comptabilité et
sans arbitre, la facture est non bornée. La seed l'a appris en production — d'où le signal
« terminé » conjonctif (**couverture ∧ yield**) et les caps durs. Forge va plus loin sur trois
exigences que tu as pointées :

1. **Comptabiliser** la consommation de tokens, par appel et attribuée finement.
2. **Chiffrer** le coût réel (et la part estimée), par modèle.
3. **Arbitrer** : caps, auto-stop au yield, et surtout **router chaque tâche vers le bon modèle**
   (un petit modèle local pour le volume, un modèle frontier cloud pour le raisonnement à enjeu).

Le fil conducteur : **NFR-006 — le coût doit suivre la taille de la cible et le nombre de
findings, pas le nombre d'agents ni le temps qui passe.** Ajouter des agents augmente le débit,
pas le coût total pour atteindre « terminé ».

---

## 2. Comptabilité des tokens (capture & attribution)

### 2.1 Ce qu'on capture à chaque appel LLM

Chaque appel passe par l'interface `LLMProvider` (un seul point d'instrumentation). On enregistre
une ligne par appel dans la table `llm_calls` :

```python
class LlmCall(BaseModel):
    call_id: UUID
    run_id: str
    role: Role                 # qui a appelé (detector, triager, ...)
    instance: str              # detector-2
    correlation_id: str        # fingerprint du finding, si applicable  → coût PAR finding
    task_id: str | None        # tâche de la work queue, si applicable
    model: str                 # claude-sonnet-4-6 | local/qwen2.5-coder-32b | ...
    provider: str              # anthropic | ollama | vllm
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int     # prompt caching (lecture) — facturé ~10%
    cache_write_tokens: int    # écriture de cache — léger surcoût
    batch: bool                # appel en mode batch (−50%)
    cost_usd: Decimal          # calculé (§3), 0 si modèle local marginal
    cost_estimated: bool       # True si dérivé de tokens locaux, pas reporté par le provider
    latency_ms: int
    ts: datetime
```

### 2.2 D'où viennent les compteurs

- **Cloud (Anthropic)** : l'API **renvoie l'usage réel** (`usage.input_tokens`,
  `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`). `cost_estimated=False`.
- **Local (Ollama/vLLM)** : pas de facturation, mais on **compte les tokens** via le tokenizer
  du modèle (ou les compteurs renvoyés par vLLM). `cost_estimated=True`, `cost_usd` = coût
  d'infrastructure amorti (§3.3) ou 0 selon la politique.

### 2.3 Axes d'attribution (ce que ça débloque)

Parce qu'on attribue chaque appel à `(run, role, instance, finding, task, model)`, on peut
répondre, en direct, à :

- **Coût par rôle** : « les Detectors brûlent 60 % du budget » → signal pour router plus de leur
  charge vers le local (§5).
- **Coût par finding** (`correlation_id`) : « ce finding a coûté 3,20 $ à confirmer » → entre
  directement dans le **yield** (§4.2).
- **Coût par modèle** : valider que le routage local/cloud tient ses promesses.
- **Part estimée** (FR-113) : le dashboard affiche « X % du total est estimé » (tokens locaux).

C'est aussi la **provenance** (NFR-007, SC-009) : pour tout finding publié, la liste des appels
LLM qui l'ont produit est reconstructible.

---

## 3. Calcul du coût

### 3.1 Rate card (chargée depuis la config, versionnée)

Le coût n'est jamais codé en dur — il vient d'une table de tarifs dans `forge.yaml`, ce qui rend
le système robuste aux changements de prix et au multi-provider. Exemple **à titre indicatif,
tarifs publics juin 2026, par million de tokens** :

| Modèle | Input | Output | Cache read | Notes |
|---|---|---|---|---|
| Claude Opus 4.8 | 5,00 $ | 25,00 $ | ~0,50 $ | frontier ; raisonnement à enjeu |
| Claude Sonnet 4.6 | 3,00 $ | 15,00 $ | ~0,30 $ | défaut cloud équilibré |
| Claude Haiku 4.5 | 1,00 $ | 5,00 $ | ~0,10 $ | cloud bon marché, tâches simples |
| Modèle local (ex. Qwen2.5-Coder 32B via vLLM) | ~0 marginal | ~0 marginal | — | coût = infra amortie (§3.3) |

Leviers tarifaires intégrés : **batch −50 %** (pour le balayage de règles non urgent),
**prompt caching −90 % sur l'input mis en cache** (la carte de sécurité et les prompts système,
réutilisés à chaque appel, sont des candidats parfaits au cache).

### 3.2 Formule

```
cost = input_tokens      × rate.input
     + output_tokens     × rate.output
     + cache_read_tokens × rate.cache_read
     + cache_write_tokens× rate.cache_write
puis × 0.5 si batch
```

### 3.3 Coût d'un modèle local

Le marginal d'un token local est quasi nul, mais ce n'est pas « gratuit » : il y a le GPU
(amortissement + énergie). Deux politiques configurables :

- **`marginal`** (défaut démo) : `cost_usd = 0` → le local ne consomme pas de budget $. Idéal
  pour montrer l'effet du routage sur la facture cloud.
- **`amortized`** : `cost_usd = (coût_GPU_horaire / tokens_par_heure) × tokens` → comparaison
  honnête local vs cloud au seuil de rentabilité (l'auto-hébergement devient rentable au-delà
  d'un volume soutenu — de l'ordre de centaines de M tokens/mois selon les sources).

---

## 4. Arbitrage du budget (le governor)

### 4.1 Caps durs (FR-112/114)

`budget.spend_cap_usd` et `budget.time_cap_min`. Le budget governor suit la **dépense cumulée
sur tous les runs** d'une évaluation et **halte le fleet** dès qu'un cap est franchi (drain
gracieux, FR-006). Pré-flight (FR-010/114) : si les deux caps sont nuls, avertir que le run est
borné uniquement par couverture ∧ yield. FR-011 : refus de redémarrer après un cap dur non relevé.

### 4.2 Auto-stop au yield (FR-115/116/117)

```
yield_glissant = Σ( poids_sévérité(finding) × (2 si exploited) ) / dépense_$    [fenêtre glissante]
```

Halt **seulement si** : (a) une fenêtre pleine de dépense accumulée, (b) runtime min écoulé,
(c) **couverture-complète** posée (Constitution VI). Poids **géométriques** (~3,16×/tier) pour
que le yield soit dominé par les findings à forte valeur et comparable d'une cible à l'autre.
La comptabilité par finding (§2.3) alimente directement le numérateur **et** le dénominateur.

### 4.3 Sous-budgets par rôle (extension Forge)

Au-delà de la seed : un plafond optionnel **par rôle** (`fleet.<role>.spend_cap_usd`). Si les
Detectors exploratoires (FR-040, les plus dépensiers car libres) atteignent leur sous-cap, ils
sont steerés vers le wrap-up sans tuer le run. Garde-fou anti-« rabbit hole » coûteux,
complémentaire de la rotation de session (FR-118).

### 4.4 Proportionnalité (NFR-006)

Mémoïsation (`hash(corps de fonction + version de règle)`) : une fonction inchangée n'est pas
re-soumise au LLM entre deux runs. Le coût suit la **taille de la cible** et le **nombre de
findings**, pas le wall-clock. Ajouter des agents accélère sans gonfler le coût total.

---

## 5. Routage des modèles : local vs cloud à l'usage

C'est le levier de coût le plus puissant, et ta demande centrale. Principe : **dimensionner le
modèle à l'enjeu de la tâche**, pas un modèle frontier partout.

### 5.1 Abstraction & passerelle

L'interface `LLMProvider` (US-13) rend le modèle swappable sans toucher aux rôles. En coulisse,
Forge route via **LiteLLM** — une passerelle open-source qui parle l'API OpenAI en façade et,
derrière, unifie **Ollama / vLLM (local)** et **Anthropic / OpenAI / … (cloud)** sous un seul
endpoint, avec **fallbacks ordonnés** et load-balancing. Pour le serving local en production,
**vLLM** (batching continu, 10–50× le débit d'Ollama sous charge concurrente) ; **Ollama** pour
le poste de dev. *Note coût :* une passerelle d'agrégation ajoute un léger surcoût par token ;
l'auto-hébergement via LiteLLM est rentable au-delà d'un volume soutenu.

### 5.2 Politique de routage par tier de tâche

| Tier | Tâches | Modèle visé | Pourquoi |
|---|---|---|---|
| **Bulk / mécanique** | balayage de règles fonction-par-fonction (FR-037), dédup, résumés de contexte, fallback de cartographie | **Local** (ex. Qwen2.5-Coder 32B) ou **Haiku** | Volume élevé, jugement faible, format contraint → un petit modèle suffit ; énorme part du nombre d'appels. |
| **Raisonnement à enjeu** | chasse exploratoire (FR-040), raisonnement de l'**evidence gate** au triage (FR-087), décision de validation | **Cloud frontier** (Sonnet 4.6 / Opus 4.8) | C'est là que la qualité décide de la précision (Constitution I/VII). Ne pas rogner ici. |
| **Escalade** | un candidat où le local hésite / le gate échoue / sortie non parsable | **Local → escalade Cloud** | Tenter petit d'abord, escalader seulement si nécessaire. |

### 5.3 Escalade & fallback (deux mécanismes distincts)

- **Escalade qualité** (Forge) : un rôle tente le tier local ; si la sortie structurée est
  invalide, la confiance basse, ou le gate non satisfait, il **re-soumet au modèle cloud**. On
  ne paie le frontier que sur les cas qui le justifient.
- **Fallback disponibilité** (LiteLLM) : sur 429 / 5xx / timeout du cloud, bascule
  automatiquement vers un secours (autre provider, puis local). Cohérent avec « le provider est
  l'arbitre du débit » + backoff partagé (FR-105/106) : le fallback gère l'indisponibilité, pas
  un cap interne.

### 5.4 Confidentialité — un bénéfice, pas qu'un coût

Évaluer la sécurité d'un produit, c'est exposer son **code source** au modèle. Router le **bulk
vers un modèle local** garde la majeure partie du code source **on-premise**, et réserve au cloud
les extraits raisonnés. Pour du code sensible, un mode **« local-only »** (aucun appel cloud) est
une politique de routage valide — au prix d'une qualité de raisonnement moindre, à l'opérateur
d'arbitrer.

### 5.5 Configuration (par rôle + politique globale)

```yaml
integrations:
  llm:
    gateway: litellm                 # passerelle unifiée local+cloud
    routing:
      policy: tiered                 # tiered | cloud-only | local-only
      escalate_on: [invalid_schema, low_confidence, gate_failed]
      caching: true                  # prompt caching (carte + system prompts)
      batch_bulk: true               # balayage de règles en mode batch (−50%)
    models:
      bulk:      { provider: vllm,      model: qwen2.5-coder-32b, endpoint_env: VLLM_URL }
      reasoning: { provider: anthropic, model: claude-sonnet-4-6, api_key_env: ANTHROPIC_API_KEY }
      escalation:{ provider: anthropic, model: claude-opus-4-8,   api_key_env: ANTHROPIC_API_KEY }
  rate_card:                          # tarifs $/Mtok — chargés, jamais codés en dur (FR-113)
    claude-opus-4-8:   { input: 5.0, output: 25.0, cache_read: 0.5 }
    claude-sonnet-4-6: { input: 3.0, output: 15.0, cache_read: 0.3 }
    claude-haiku-4-5:  { input: 1.0, output: 5.0,  cache_read: 0.1 }
    qwen2.5-coder-32b: { input: 0.0, output: 0.0,  local_cost_model: marginal }

fleet:                                # surcharge par rôle possible
  detector:  { instances: 3, model_tier: bulk,      spend_cap_usd: 5.00 }
  triager:   { instances: 2, model_tier: reasoning }
  validator: { instances: 1, model_tier: reasoning }
```

---

## 6. Restitution sur le dashboard (FR-120)

Un panneau **Coût** en direct, même source que le reste (SC-008) :

- **Dépense cumulée** vs caps (jauge), **runtime** vs cap.
- **Répartition par rôle** et **par modèle** (camembert) → on *voit* l'effet du routage.
- **Part estimée** (tokens locaux) en pourcentage (FR-113).
- **Yield glissant** + les trois préconditions d'auto-stop (fenêtre / runtime / couverture).
- **Coût par finding** confirmé ; **projection** du coût pour atteindre « terminé » (extrapolation
  du yield).
- Bandeau **état dégradé** sur 429/quota (FR-125).

---

## 7. Synthèse

| Besoin | Réponse Forge |
|---|---|
| Comptabiliser les tokens | Table `llm_calls` instrumentée au seul `LLMProvider` ; attribution (run/rôle/instance/finding/tâche/modèle). |
| Coût des tokens | Rate card configurable (input/output/cache/batch) ; réel pour le cloud, estimé pour le local ; part estimée exposée. |
| Arbitrer | Caps durs + sous-budgets par rôle + auto-stop yield (couverture ∧ yield) + mémoïsation (NFR-006). |
| Local vs cloud à l'usage | Passerelle LiteLLM + routage par tier (bulk→local, raisonnement→cloud) + escalade qualité + fallback dispo + mode local-only confidentiel. |

Tous ces ajouts respectent les principes constitutionnels : on ne rogne jamais la qualité **sur
les étapes à enjeu** (gate, validation), on optimise le coût **sur le volume mécanique**.

---

## Sources (juin 2026)

- Tarifs API Claude (Opus 4.8 5/25 $, Sonnet 4.6 3/15 $, Haiku 4.5 1/5 $ par Mtok ; batch −50 %,
  caching −90 %) : [Pricing — Claude API Docs](https://platform.claude.com/docs/en/about-claude/pricing),
  [CloudZero](https://www.cloudzero.com/blog/claude-api-pricing/),
  [Finout](https://www.finout.io/blog/anthropic-api-pricing)
- Routage local/cloud, LiteLLM, Ollama vs vLLM, fallbacks, seuil de rentabilité de
  l'auto-hébergement : [LiteLLM — Routing & Load Balancing](https://docs.litellm.ai/docs/routing-load-balancing),
  [Local AI Master — LiteLLM gateway](https://localaimaster.com/blog/ai-gateway-litellm),
  [Markaicode — OpenRouter vs LiteLLM](https://markaicode.com/vs/openrouter-vs-litellm/)
