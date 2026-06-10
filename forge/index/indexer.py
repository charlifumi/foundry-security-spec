"""Index de code déterministe (Python/ast) — structure + flux.

Au-delà de l'inventaire (FR-020) et du graphe d'appels (FR-021), cet index répond
aux questions de la démo de cartographie :
  - quelles sont les **chaînes d'appel** d'une fonction jusqu'à un sink ? (`chains_from`)
  - comment les **arguments** se propagent d'appel en appel ? (`argument_flow`)
  - où (ou si) l'entrée est **validée** le long du chemin ? (`validation_in`)

Et `resolve_citation` (FR-088) : la vérification mécanique au cœur de l'evidence gate.
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field

# Sinks de sécurité connus : nom d'appel -> (CWE, libellé). Sert aux chaînes d'appel
# et à la cartographie (entrée -> ... -> sink).
SINKS = {
    "execute": ("CWE-89", "requête SQL"),
    "executescript": ("CWE-89", "requête SQL"),
    "system": ("CWE-78", "shell"),
    "popen": ("CWE-78", "shell"),
    "run": ("CWE-78", "shell/subprocess"),
    "urlopen": ("CWE-918", "requête sortante"),
    "open": ("CWE-22", "lecture/écriture fichier"),
    "loads": ("CWE-502", "désérialisation"),
    "md5": ("CWE-327", "hash faible"),
    "sha1": ("CWE-327", "hash faible"),
}

# Indices de validation/assainissement recherchés le long d'un chemin.
VALIDATORS = (
    "escape", "sanitize", "sanitise", "validate", "quote", "allowlist", "whitelist",
    "is_valid", "clean", "realpath", "normpath", "secure_filename", "parameter",
)


@dataclass
class CallSite:
    callee: str
    arg_names: list[str]          # noms de variables passés en argument
    lineno: int
    is_sink: bool = False


@dataclass
class FunctionInfo:
    name: str
    file: str
    line_start: int
    line_end: int
    source: str
    params: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    call_sites: list[CallSite] = field(default_factory=list)


class CodeIndex:
    def __init__(self):
        self.functions: dict[str, list[FunctionInfo]] = {}
        self.by_name: dict[str, list[FunctionInfo]] = {}

    # ----- construction ---------------------------------------------------------
    def build(self, root: str, includes=(".py",), excludes=("tests", ".venv", "__pycache__")):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in excludes]
            for fn in filenames:
                if fn.endswith(includes):
                    path = os.path.join(dirpath, fn)
                    self._index_file(path, os.path.relpath(path, root))
        return self

    def _index_file(self, path: str, rel: str):
        try:
            src = open(path, encoding="utf-8").read()
            tree = ast.parse(src, filename=rel)
        except (SyntaxError, UnicodeDecodeError):
            return
        lines = src.splitlines()
        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start, end = node.lineno, getattr(node, "end_lineno", node.lineno)
                params = [a.arg for a in node.args.args]
                calls, sites = [], []
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        name = self._call_name(sub.func)
                        if not name:
                            continue
                        calls.append(name)
                        arg_names = [a.id for a in sub.args if isinstance(a, ast.Name)]
                        sites.append(CallSite(name, arg_names, getattr(sub, "lineno", start),
                                              is_sink=name in SINKS))
                info = FunctionInfo(node.name, rel, start, end,
                                    "\n".join(lines[start - 1:end]), params, calls, sites)
                funcs.append(info)
                self.by_name.setdefault(node.name, []).append(info)
        self.functions[rel] = funcs

    @staticmethod
    def _call_name(func) -> str | None:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return None

    # ----- requêtes structurelles (FR-022) -------------------------------------
    def all_functions(self) -> list[FunctionInfo]:
        return [f for fs in self.functions.values() for f in fs]

    def find_symbol(self, name: str) -> list[FunctionInfo]:
        return self.by_name.get(name, [])

    def callers_of(self, name: str) -> list[FunctionInfo]:
        return [f for f in self.all_functions() if name in f.calls]

    def function_count(self) -> int:
        return len(self.all_functions())

    # ----- chaînes d'appel (démo cartographie) ---------------------------------
    def chains_from(self, func_name: str, max_depth: int = 8) -> list[list[str]]:
        """Toutes les chaînes d'appel partant de `func_name`, jusqu'à un sink ou une feuille.

        Chaque chaîne est une liste de noms ; un sink est suffixé par `*<sink>`.
        Répond à : « quelles sont les chaînes d'appel de telle fonction ? »
        """
        chains: list[list[str]] = []

        def walk(name: str, path: list[str], depth: int):
            infos = self.by_name.get(name)
            if not infos or depth >= max_depth:
                chains.append(path)
                return
            info = infos[0]
            # sinks appelés directement -> terminent une chaîne
            sink_sites = [s for s in info.call_sites if s.is_sink]
            internal = [c for c in info.calls if c in self.by_name and c != name and c not in path]
            if not sink_sites and not internal:
                chains.append(path)
                return
            for s in sink_sites:
                chains.append(path + [f"→sink:{s.callee}({SINKS[s.callee][0]})"])
            for callee in internal:
                walk(callee, path + [callee], depth + 1)

        walk(func_name, [func_name], 0)
        return chains

    # ----- flux d'arguments (démo) ---------------------------------------------
    def argument_flow(self, func_name: str) -> list[dict]:
        """Pour chaque appel de la fonction, quels **paramètres** de la fonction y circulent.

        Répond à : « comment sont passés les arguments ? »
        """
        out = []
        for info in self.by_name.get(func_name, []):
            for s in info.call_sites:
                flowing = [a for a in s.arg_names if a in info.params]
                out.append({
                    "callee": s.callee, "line": s.lineno, "args": s.arg_names,
                    "from_params": flowing, "is_sink": s.is_sink,
                    "sink_class": SINKS.get(s.callee, ("", ""))[0] if s.is_sink else None,
                })
        return out

    @staticmethod
    def _strip_comments(src: str) -> str:
        """Retire docstrings et commentaires : la validation s'évalue sur le CODE, pas le texte."""
        src = re.sub(r'(?s)""".*?"""', "", src)
        src = re.sub(r"(?s)'''.*?'''", "", src)
        return re.sub(r"#.*", "", src)

    def validation_in(self, func_name: str) -> list[str]:
        """Indices de validation/assainissement présents dans le CODE de la fonction.

        Répond à : « où sont validés les arguments ? » — une liste vide sur un chemin
        entrée→sink est le signal d'une frontière de confiance non gardée. Commentaires et
        docstrings sont ignorés (sinon un commentaire « aucune allowlist » fausserait l'analyse).
        """
        found = []
        for info in self.by_name.get(func_name, []):
            low = self._strip_comments(info.source).lower()
            for v in VALIDATORS:
                if v in low and v not in found:
                    found.append(v)
        return found

    # ----- résolution de citation (FR-088 — cœur de l'evidence gate) -----------
    def resolve_citation(self, file: str, symbol: str) -> bool:
        for f in self.functions.get(file, []):
            if f.name == symbol:
                return True
        return symbol in self.by_name and any(fi.file == file for fi in self.by_name[symbol])
