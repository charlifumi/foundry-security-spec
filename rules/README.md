# Corpus de règles — format CodeGuard, fédéré

Ce dossier contient les **règles de détection** au format **CodeGuard** (markdown unifié),
artefact versionné et indépendant du code des agents (FR-041). Chaque sous-dossier de
`corpora/` est une **source nommée** ; Forge les charge toutes et les interroge ensemble
(fédération, ADR-002).

```
corpora/
├── forge-core/        # corpus maison (web + crypto)
└── acme-crypto-labs/  # exemple de corpus tiers spécialisé (crypto), fédéré
```

## Format d'une règle

Front-matter CodeGuard + corps explicatif :

```markdown
---
id: cg-web-sqli-001            # identifiant stable
title: SQL query built by string concatenation
cwe: CWE-89
owasp: A03
severity: high                 # critical | high | medium | low
domain: web                    # web | crypto | cloud | mobile | ...
source: forge-core             # entité productrice (fédération)
patterns:                      # motifs de détection (regex), appliqués à chaque fonction
  - "(?s)(SELECT|INSERT|UPDATE|DELETE)\b.*?\+\s*\w+\s*\+"
---
## Rule — texte de remédiation, exemples vulnérable/sûr…
```

## Deux modes de chargement (ADR-002)

- **exhaustive** : chaque règle est appliquée à chaque fonction (FR-037 strict). Idéal sur
  un petit corpus.
- **vector** : chaque règle est *embedée* dans une base vectorielle ; pour une fonction
  donnée, on récupère les **top-k règles pertinentes** (toutes sources confondues), puis on
  applique leurs motifs. C'est ce qui permet de **fédérer de gros corpus tiers** par domaine
  sans tout appliquer aveuglément. Sélection : `python -m forge up --backend vector`.

## Ajouter un corpus tiers

Déposez un dossier `corpora/<votre-source>/` avec des fichiers `.md` au format ci-dessus.
Il est automatiquement chargé, embedé et interrogeable. En mode `vector`, une règle plus
spécifique (ex. `acme-crypto-labs` sur le hachage de mot de passe) surclasse la règle
générique pour la fonction concernée.

## Réutilisation (US-14)

Le même corpus se charge inchangé dans un assistant de code comme garde-fou de prévention :
le flywheel rule-gap (FR-042) qui *détecte* ici produit la règle qui *prévient* ailleurs.
