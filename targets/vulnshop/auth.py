"""Authentification VulnShop.

Contient V8 — Crypto faible (CWE-327) : mots de passe hachés en MD5, sans sel.
"""
import hashlib

from . import db


def hash_password(password):
    """V8 — MD5 non salé pour les mots de passe (CWE-327)."""
    return hashlib.md5(password.encode()).hexdigest()  # <-- primitive dépréciée


def login(username, password):
    """Authentifie via db.authenticate (qui est lui-même vulnérable au SQLi, V1)."""
    pw_md5 = hash_password(password)
    return db.authenticate(username, pw_md5)
