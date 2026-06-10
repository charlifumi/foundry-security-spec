"""Fonctions d'administration VulnShop.

Contient V3 — Injection de commande (CWE-78) : un ping de diagnostic concatène l'entrée
utilisateur dans une commande shell.
"""
import subprocess


def diagnostic_ping(host):
    """V3 — Injection de commande : `host` est concaténé dans une commande shell (CWE-78).

    Exploitable par host = "127.0.0.1; id" ou "127.0.0.1 && echo PWNED".
    """
    cmd = "ping -c 1 " + host                       # <-- construction de commande non sûre
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True)  # <-- sink shell=True
    return out.stdout + out.stderr
