# `vulnshop` — Application cible volontairement vulnérable

> ⚠️ **`vulnshop` est intentionnellement non sécurisée.** Elle existe uniquement comme **cible
> de démonstration** pour Forge. Ne la déployez jamais hors d'un sandbox jetable, sur aucun
> réseau accessible. Toute vulnérabilité ci-dessous est **semée** délibérément.

## But

Donner à Forge une cible réaliste et compacte contenant **plusieurs classes de vulnérabilités
distinctes**, chacune :

- détectable par au moins une technique du Detector (règle, dépendance, secret, ou exploration) ;
- triable avec une **chaîne de preuve à trois jambes** (atteignabilité → frontière → impact) ;
- **exploitable en live** par le Validator dans le conteneur (pour poser `exploited`).

C'est ce qui permet de démontrer le pipeline complet **et** le flywheel : on peut retirer la
règle correspondant à une vuln pour montrer qu'un agent exploratoire la trouve quand même, puis
qu'un rule-gap est enregistré.

## Forme

Petite app **Flask** (un panier d'e-commerce factice) : authentification, profils utilisateurs,
recherche de produits, panier, upload d'avatar, page admin, et un petit proxy d'image.
Stockage SQLite. Quelques templates Jinja2 (certains rendus en mode non échappé exprès).

```
targets/vulnshop/
├── app.py                 # routes Flask
├── auth.py                # login, sessions, hash de mot de passe
├── db.py                  # accès SQLite (requêtes construites par concaténation → SQLi)
├── products.py            # recherche, détail produit
├── profile.py             # profil, avatar upload, accès par id
├── admin.py               # page admin, export, ping de diagnostic
├── imageproxy.py          # récupère une image distante par URL (SSRF)
├── templates/             # Jinja2 (rendu non échappé sur certains champs → XSS stored)
├── config.py              # secret en dur, clé API en dur
└── requirements.txt       # inclut une dépendance volontairement obsolète (FR-038)
```

## Catalogue des vulnérabilités semées

| # | Classe | CWE | OWASP 2021 | Localisation prévue | Technique de détection | Exploitable live ? |
|---|---|---|---|---|---|---|
| V1 | Injection SQL | CWE-89 | A03 | `db.py` (login, recherche) | règle SQLi + exploration | ✅ bypass auth / dump |
| V2 | XSS stocké | CWE-79 | A03 | `templates/`, `products.py` (avis) | règle XSS | ✅ exécution JS |
| V3 | Injection de commande | CWE-78 | A03 | `admin.py` (ping de diagnostic) | règle cmd-injection | ✅ RCE |
| V4 | SSRF | CWE-918 | A10 | `imageproxy.py` | règle SSRF + exploration | ✅ accès interne |
| V5 | IDOR / contrôle d'accès cassé | CWE-639 | A01 | `profile.py` (accès par id) | exploration | ✅ lecture d'autrui |
| V6 | Path traversal | CWE-22 | A01 | `profile.py` (avatar) | règle traversal | ✅ lecture FS |
| V7 | Secret en dur | CWE-798 | A07 | `config.py` | scan de secrets | n/a (présence = vuln, FR-087a) |
| V8 | Crypto faible (MD5 mots de passe) | CWE-327 | A02 | `auth.py` | règle crypto | n/a (présence = vuln) |
| V9 | Désérialisation non sûre | CWE-502 | A08 | `profile.py` (cookie de préférences `pickle`) | règle désérialisation | ✅ RCE |
| V10 | Dépendance vulnérable | CWE-1035 | A06 | `requirements.txt` | scan de dépendances | n/a (CVE connue) |

Dix vulnérabilités, couvrant **les quatre techniques** du Detector (règles, dépendances,
secrets, exploration) et **les deux carve-outs** de l'evidence gate (jambes data-flow complètes
pour V1–V6/V9 ; « présence = vuln » pour V7/V8).

## Bruit volontaire — ce que le Triager doit ÉCARTER

Tout ce qui est détecté ne doit pas finir en `true-positive` : la valeur du pipeline est de
ne sortir que le pertinent. VulnShop contient donc, en plus des 10 vulns, des cas-pièges :

| Cas | Localisation | Détecté comme | Verdict attendu | Pourquoi |
|---|---|---|---|---|
| Copie en buffer fixe **bornée par l'appelant** | `buffer.py:copy_into_fixed_buffer` | CWE-120 (règle) | **false-positive** | L'unique appelant tronque l'entrée à 64 octets (< 128) : non exploitable dans ce contexte d'appel. Démontre le triage **conscient du graphe d'appels**. |
| XSS **correctement échappée** | `products.py:render_search_safe` | CWE-79 (règle, motif large) | **false-positive** | La sortie passe par `html.escape` : la frontière est gardée. |
| Code d'**exemple** / documentation | `examples.py:example_unsafe_query_DO_NOT_USE` | CWE-89 (règle) | **not-applicable** | Hors périmètre (FR-055) : échantillon non déployé, aucun sink réel. |
| Lead **non prouvable** | `app.py:suspected_timing_side_channel` (exploration) | CWE-208 | **needs-review** | La citation ne résout pas vers une fonction réelle : le gate démote (FR-088), il n'invente pas de preuve. |

Et la distinction **vraie vuln mais non exploitée en live** : les secrets (CWE-798), la crypto
faible (CWE-327/916) et les dépendances (CWE-1035) sont de vrais `true-positive` (« la présence
est la vuln », FR-087a) mais ne portent pas le flag `exploited` — ils ne se démontrent pas par
une requête sur le testbed. Seuls les findings *exploités en clair* portent ⚡.

Résultat d'un run : ~25 candidats détectés → **21 true-positive publiés**, **8 exploités en
live**, et **4 écartés** (2 false-positive, 1 not-applicable, 1 needs-review) avec, pour chacun,
le motif de la décision visible dans le dashboard.

## Ce que la démo doit montrer, étape par étape

1. **Indexer** : `vulnshop` parsé en quelques secondes → fonctions + graphe d'appels queryables.
2. **Cartographe** : carte de sécurité — surface (routes Flask), frontières (input HTTP → SQL/FS/
   shell), flux (mot de passe, cookie de session, URL du proxy).
3. **Detector** : candidats qui apparaissent en flux sur le dashboard (règles + exploration).
4. **Triager** : chaque candidat passe l'**evidence gate** ; les faux positifs sont démotés en
   direct, les citations non résolvantes basculent en `needs-review`.
5. **Validator** : pour V1–V6/V9, un PoC est rejoué **dans le conteneur** et l'impact est observé
   → flag `exploited` posé, PoC runnable écrit sous `runs/<id>/poc/`.
6. **Coverage-Guide** : la barre de couverture par goal se remplit ; quand tout est tenté et que
   le yield retombe → arrêt autonome.
7. **Reporter** : un rapport Markdown par finding confirmé + un rollup groupé par composant.

## Démonstration du flywheel (optionnelle mais frappante)

Retirer la règle SQLi du corpus, relancer : un agent **exploratoire** retrouve V1, le Triager le
confirme, et comme aucune règle ne l'aurait produit, un **rule-gap** est enregistré (FR-042). On
généralise le gap en règle CodeGuard, on la remet au corpus : au run suivant, V1 est attrapée dès
la première passe de balayage. C'est la valeur ajoutée centrale du pipeline, rendue visible.
