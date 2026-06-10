"""Chargement de configuration (FR-001/126/127/129).

Sans dépendance : si PyYAML est présent, `forge.yaml` est lu ; sinon on part des
défauts (cible = targets/vulnshop) + surcharges CLI. La forme complète de forge.yaml
est documentée dans forge.yaml.example.
"""
from __future__ import annotations

import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_config() -> dict:
    return {
        "system_name": "Forge",
        "target": {
            "source": os.path.join(REPO_ROOT, "targets", "vulnshop"),
            "scope": {"include": [".py"], "exclude": ["tests", ".venv", "__pycache__"]},
        },
        "testbed": {"enabled": True, "host": "127.0.0.1", "port": 0},  # port éphémère
        "goals": ("Trouver et démontrer : bypass d'authentification, RCE, accès non autorisé "
                  "aux données d'autres utilisateurs, accès à des ressources internes."),
        "detection": {
            "corpora": os.path.join(REPO_ROOT, "rules", "corpora"),
            "rule_backend": "exhaustive",   # exhaustive | vector
        },
        "fleet": {"detector": 3, "triager": 2, "validator": 1, "reporter": 1},
        "budget": {"spend_cap_usd": None, "time_cap_min": None,
                   "yield_threshold": 0.5, "window_usd": 10.0, "min_runtime_min": 0.0},
        "llm": {"provider": "deterministic", "model": "deterministic"},
        "dashboard": {"host": "127.0.0.1", "port": 8000},
    }


def load(path: str | None = None, **overrides) -> dict:
    cfg = default_config()
    if path and os.path.exists(path):
        try:
            import yaml  # type: ignore
            with open(path, encoding="utf-8") as fh:
                user = yaml.safe_load(fh) or {}
            _deep_update(cfg, user)
        except ImportError:
            pass  # PyYAML absent -> défauts
    for k, v in overrides.items():
        if v is not None:
            _set_dotted(cfg, k, v)
    validate(cfg)
    return cfg


def _deep_update(base: dict, extra: dict):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v


def _set_dotted(cfg: dict, dotted: str, value):
    parts = dotted.split(".")
    d = cfg
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value


def validate(cfg: dict):
    """FR-129 : échec nommant chaque champ requis manquant."""
    missing = []
    if not cfg.get("target", {}).get("source"):
        missing.append("target.source")
    if not os.path.isdir(cfg["target"]["source"]):
        missing.append(f"target.source (dossier introuvable: {cfg['target']['source']})")
    if not cfg.get("goals", "").strip():
        missing.append("goals")
    if missing:
        raise ValueError("Configuration invalide, champs manquants : " + ", ".join(missing))
