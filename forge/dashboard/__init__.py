"""Dashboard temps réel (stdlib http.server) : fleet, pipeline, cartographie, budget."""
from .server import build_snapshot, serve

__all__ = ["serve", "build_snapshot"]
