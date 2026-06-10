"""Copie en buffer de taille fixe — vuln réelle mais NON exploitable dans son contexte.

`copy_into_fixed_buffer` copie une entrée dans un buffer fixe de 128 octets sans vérifier
la taille (motif CWE-120 : copie sans contrôle de borne). Prise isolément, c'est une
vulnérabilité. Mais son **unique appelant** borne l'entrée à 64 octets (< 128) : le buffer
n'est jamais débordé. La vulnérabilité existe dans l'absolu mais n'est pas exploitable ici.

Le Triager doit le constater via le **graphe d'appels** et classer ce candidat
FAUX-POSITIF (non exploitable en contexte) — il ne doit pas sortir en true-positive.
"""


def copy_into_fixed_buffer(src):
    """Motif CWE-120 : copie dans un buffer fixe sans vérifier len(src) <= 128."""
    buf = bytearray(128)
    buf[0:len(src)] = src              # <-- aucune vérification de taille (sink CWE-120)
    return buf


def handle_fixed(token):
    """Unique appelant : borne l'entrée à 64 octets, sous la taille du buffer (128)."""
    safe = token[:64]                  # <-- l'appelant garantit len(safe) <= 64 < 128
    return copy_into_fixed_buffer(safe)
