"""Extraits d'EXEMPLE / documentation — non déployés, hors périmètre d'évaluation.

Contient volontairement du code qui ressemble à une vulnérabilité, pour démontrer que
le Triager le classe `not-applicable` (code d'exemple, FR-055) plutôt que de polluer la
sortie. Rien ici n'est branché à une route.
"""


def example_unsafe_query_DO_NOT_USE(name):
    """Exemple pédagogique d'anti-pattern SQL — jamais exécuté en production."""
    # Ressemble à V1 (concaténation SQL) mais c'est un échantillon de doc, hors scope.
    query = "SELECT * FROM users WHERE name = '" + name + "' AND active = 1"
    return query  # retourne juste la chaîne ; aucun sink réel, aucune route
