"""Catalogue produit VulnShop.

Contient V2 — XSS réfléchi (CWE-79) : le terme de recherche est ré-affiché sans échappement.
"""
from . import db


def render_search(term):
    """V2 — XSS : `term` est interpolé tel quel dans le HTML (CWE-79).

    Exploitable par term = "<script>alert(1)</script>".
    """
    results = db.search_products(term)  # passe aussi par le SQLi (V1 bis)
    rows = "".join(f"<li>{r['name']} — {r['price']} €</li>" for r in results)
    html = (
        "<html><body><h1>Résultats pour : " + term + "</h1>"  # <-- sink XSS (non échappé)
        "<ul>" + rows + "</ul></body></html>"
    )
    return html
