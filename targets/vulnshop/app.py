"""Serveur HTTP VulnShop (stdlib) — le testbed que le Validator exploite en live.

Lancer seul :  python -m targets.vulnshop.app   (écoute sur 127.0.0.1:8081)
Routes exposées (toutes vulnérables, cf. docs/vulnshop.md) :
  GET  /login?username=&password=     -> V1 SQLi (bypass d'auth)
  GET  /search?q=                      -> V2 XSS réfléchi (+ V1bis SQLi)
  GET  /profile?id=                    -> V5 IDOR
  GET  /avatar?file=                   -> V6 Path traversal
  GET  /admin/ping?host=               -> V3 Injection de commande
  GET  /imageproxy?url=                -> V4 SSRF
  GET  /prefs?c=                       -> V9 Désérialisation non sûre
"""
import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import admin, config, db, imageproxy, products, profile


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # silencieux

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        g = lambda k, d="": q.get(k, [d])[0]
        try:
            if parsed.path == "/" or parsed.path == "/health":
                return self._send(200, json.dumps({"app": "vulnshop", "status": "ok"}),
                                  "application/json")
            if parsed.path == "/login":
                user = db.authenticate(g("username"), g("password"))  # V1
                if user:
                    return self._send(200, json.dumps({"ok": True, "user": user}),
                                      "application/json")
                return self._send(401, json.dumps({"ok": False}), "application/json")
            if parsed.path == "/search":
                return self._send(200, products.render_search(g("q")))  # V2 (+V1bis)
            if parsed.path == "/profile":
                data = profile.view_profile(g("id", "1"), session_user_id=1)  # V5 IDOR
                return self._send(200, json.dumps(data), "application/json")
            if parsed.path == "/avatar":
                return self._send(200, profile.read_avatar(g("file")),  # V6
                                  "application/octet-stream")
            if parsed.path == "/admin/ping":
                return self._send(200, admin.diagnostic_ping(g("host", "127.0.0.1")),  # V3
                                  "text/plain")
            if parsed.path == "/imageproxy":
                return self._send(200, imageproxy.fetch_image(g("url")),  # V4
                                  "application/octet-stream")
            if parsed.path == "/prefs":
                prefs = profile.load_preferences(g("c"))  # V9
                return self._send(200, json.dumps({"prefs": str(prefs)}), "application/json")
            return self._send(404, json.dumps({"error": "not found"}), "application/json")
        except Exception as e:  # noqa: BLE001 — un testbed qui ne crash pas
            return self._send(500, json.dumps({"error": str(e)}), "application/json")


def make_server(host=None, port=None):
    db.init_db()
    os.makedirs(profile.AVATAR_DIR, exist_ok=True)
    # un avatar de démo pour la lecture légitime
    with open(os.path.join(profile.AVATAR_DIR, "alice.png"), "wb") as f:
        f.write(b"\x89PNG\r\n_demo_avatar_")
    # port == 0 -> éphémère (ne pas confondre avec "non fourni")
    bind_port = config.PORT if port is None else port
    return ThreadingHTTPServer((host or config.HOST, bind_port), Handler)


def serve_in_thread(host=None, port=None):
    """Démarre le testbed dans un thread démon ; retourne (server, base_url)."""
    srv = make_server(host, port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    h, p = srv.server_address
    return srv, f"http://{h}:{p}"


if __name__ == "__main__":
    srv = make_server()
    print(f"VulnShop écoute sur http://{config.HOST}:{config.PORT}  (Ctrl-C pour arrêter)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
