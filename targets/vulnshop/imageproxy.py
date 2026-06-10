"""Proxy d'image VulnShop.

Contient V4 — SSRF (CWE-918) : récupère une URL fournie par l'utilisateur sans validation.
"""
import urllib.request


def fetch_image(url):
    """V4 — SSRF : `url` (contrôlée par l'utilisateur) est requêtée côté serveur (CWE-918).

    Exploitable par url = "http://169.254.169.254/latest/meta-data/" (métadonnées cloud)
    ou "http://localhost:.../" pour atteindre des services internes.
    """
    with urllib.request.urlopen(url, timeout=3) as resp:  # <-- sink SSRF (aucune allowlist)
        return resp.read()
