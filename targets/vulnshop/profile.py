"""Profils utilisateurs VulnShop.

Contient :
  V5 — IDOR / contrôle d'accès cassé (CWE-639) : accès au profil par id, sans autorisation.
  V6 — Path traversal (CWE-22) : lecture d'avatar par nom de fichier non assaini.
  V9 — Désérialisation non sûre (CWE-502) : préférences chargées via pickle.
"""
import base64
import os
import pickle

from . import db

AVATAR_DIR = os.path.join(os.path.dirname(__file__), "avatars")


def view_profile(requested_id, session_user_id):
    """V5 — IDOR : retourne n'importe quel profil par id sans vérifier session_user_id (CWE-639)."""
    # Aucune vérification que requested_id == session_user_id ni que l'appelant est admin.
    return db.get_user(int(requested_id))  # <-- accès direct, non autorisé


def read_avatar(filename):
    """V6 — Path traversal : `filename` est concaténé au chemin sans assainissement (CWE-22).

    Exploitable par filename = "../../../../etc/passwd".
    """
    path = os.path.join(AVATAR_DIR, filename)  # <-- pas de normalisation/validation
    with open(path, "rb") as f:                # <-- sink lecture FS
        return f.read()


def load_preferences(cookie_value):
    """V9 — Désérialisation non sûre : le cookie de préférences est dépicklé (CWE-502).

    Exploitable par un cookie pickle forgé -> exécution de code.
    """
    raw = base64.b64decode(cookie_value)
    return pickle.loads(raw)  # <-- sink désérialisation non sûre
