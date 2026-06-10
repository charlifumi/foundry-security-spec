"""Configuration de VulnShop.

AVERTISSEMENT : application volontairement vulnérable, à des fins de démonstration.
Ne jamais déployer hors d'un sandbox jetable.
"""

# V7 — Secret en dur dans la source (CWE-798). "La présence est la vuln" (FR-087a).
SECRET_KEY = "sk_live_51H8xQ2eZvKYlo2C_HARDCODED_DO_NOT_SHIP"
ADMIN_API_KEY = "admin-9f3a-PLAINTEXT-KEY-1234"
DB_PASSWORD = "p@ssw0rd-in-source"

HOST = "127.0.0.1"
PORT = 8081
