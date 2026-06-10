"""Accès aux données VulnShop (SQLite).

Contient V1 — Injection SQL (CWE-89) : requêtes construites par concaténation.
"""
import os
import sqlite3
import tempfile

_DB_PATH = os.path.join(tempfile.gettempdir(), "vulnshop.db")


def get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """(Ré)initialise une base de démo avec quelques utilisateurs et produits."""
    conn = get_conn()
    c = conn.cursor()
    c.executescript(
        """
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS products;
        CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, password_md5 TEXT,
                           email TEXT, role TEXT, ssn TEXT);
        CREATE TABLE products(id INTEGER PRIMARY KEY, name TEXT, price REAL, secret_note TEXT);
        """
    )
    # password_md5 = md5("password") etc. (V8 — crypto faible)
    import hashlib
    def md5(s): return hashlib.md5(s.encode()).hexdigest()
    users = [
        (1, "alice", md5("alicepw"), "alice@example.com", "user", "111-22-3333"),
        (2, "bob", md5("bobpw"), "bob@example.com", "user", "444-55-6666"),
        (3, "admin", md5("admin123"), "admin@example.com", "admin", "999-00-0000"),
    ]
    c.executemany("INSERT INTO users VALUES(?,?,?,?,?,?)", users)
    products = [
        (1, "Widget", 9.99, "supplier-cost=2.10"),
        (2, "Gadget", 19.99, "supplier-cost=5.00"),
        (3, "Gizmo", 4.99, "discontinued-internal"),
    ]
    c.executemany("INSERT INTO products VALUES(?,?,?,?)", products)
    conn.commit()
    conn.close()


def authenticate(username, password_md5):
    """V1 — SQLi : la requête de login est construite par concaténation de chaînes.

    Exploitable par `username = "admin' --"` ou `' OR '1'='1`.
    """
    conn = get_conn()
    query = (
        "SELECT id, username, role FROM users "
        "WHERE username = '" + username + "' AND password_md5 = '" + password_md5 + "'"
    )
    row = conn.execute(query).fetchone()  # <-- sink SQLi
    conn.close()
    return dict(row) if row else None


def search_products(term):
    """V1 (bis) — SQLi dans la recherche produit, également par concaténation."""
    conn = get_conn()
    query = "SELECT id, name, price FROM products WHERE name LIKE '%" + term + "%'"
    rows = conn.execute(query).fetchall()  # <-- sink SQLi
    conn.close()
    return [dict(r) for r in rows]


def get_user(user_id):
    """Lecture d'un utilisateur par id (utilisée par le profil — voir V5 IDOR)."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
