#!/usr/bin/env bash
# Publie les livrables Forge sur ton dépôt GitHub.
# Pré-requis : git installé + être authentifié (gh auth login, ou un credential helper,
# ou un Personal Access Token configuré). Lance ce script depuis CE dossier.
set -euo pipefail

REPO="https://github.com/charlifumi/foundry-security-spec.git"

# 1) Nettoyer un éventuel .git partiel laissé par l'environnement, repartir propre.
rm -rf .git

# 2) Init + commit.
git init -q
git add -A
git commit -q -m "Forge: démonstrateur du pipeline Foundry (Cisco) — phase Spec+Plan + analyse approfondie"
git branch -M main

# 3) Remote + push (force, le dépôt distant est neuf/vide).
git remote add origin "$REPO"
git push -u origin main

echo "✅ Publié sur $REPO"
