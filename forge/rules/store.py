"""RuleStore : corpus CodeGuard fédérés + détection (exhaustive | vector).

Charge plusieurs corpus *sources nommées* (maison + tiers spécialisés par domaine),
parse le front-matter CodeGuard, embede chaque règle dans la base vectorielle, et
expose deux modes de détection :
  - exhaustive : applique toutes les règles à chaque fonction (FR-037 strict).
  - vector     : récupère les top-k règles pertinentes via embeddings, puis applique
                 leurs motifs — passage à l'échelle pour de grands corpus fédérés (ADR-002).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .embeddings import EmbeddingProvider
from .vector_index import VectorIndex


@dataclass
class Rule:
    id: str
    title: str
    cwe: str = ""
    owasp: str = ""
    severity: str = "medium"
    domain: str = "generic"
    source: str = "unknown"
    patterns: list[str] = field(default_factory=list)
    body: str = ""

    def text_for_embedding(self) -> str:
        return f"{self.title}\n{self.cwe} {self.owasp} {self.domain}\n{self.body}"


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Parseur minimal de front-matter `--- ... ---` (sous-ensemble, sans dépendance YAML)."""
    meta: dict = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end].strip("\n")
            body = text[end + 4:].lstrip("\n")
            key = None
            for line in block.splitlines():
                if re.match(r"^\s*-\s+", line) and key:           # élément de liste
                    meta.setdefault(key, []).append(line.strip()[2:].strip().strip('"'))
                elif ":" in line:
                    k, _, v = line.partition(":")
                    key = k.strip()
                    v = v.strip()
                    meta[key] = v if v else []
    return meta, body


class RuleStore:
    def __init__(self, *, backend: str = "exhaustive",
                 embedder: EmbeddingProvider | None = None,
                 index: VectorIndex | None = None):
        self.backend = backend
        self.embedder = embedder or EmbeddingProvider()
        self.index = index or VectorIndex()
        self.rules: dict[str, Rule] = {}

    # ----- chargement / fédération ---------------------------------------------
    def load_dir(self, corpora_root: str):
        """Charge chaque sous-dossier de `corpora_root` comme une source nommée."""
        if not os.path.isdir(corpora_root):
            return self
        for source in sorted(os.listdir(corpora_root)):
            sdir = os.path.join(corpora_root, source)
            if os.path.isdir(sdir):
                self.load_corpus(sdir, source)
        return self

    def load_corpus(self, path: str, source: str):
        for fn in sorted(os.listdir(path)):
            if fn.endswith(".md") and not fn.lower().startswith("readme"):
                meta, body = _parse_front_matter(open(os.path.join(path, fn), encoding="utf-8").read())
                rid = meta.get("id", f"{source}-{fn[:-3]}")
                rule = Rule(
                    id=rid, title=meta.get("title", rid), cwe=meta.get("cwe", ""),
                    owasp=meta.get("owasp", ""), severity=meta.get("severity", "medium"),
                    domain=meta.get("domain", "generic"), source=meta.get("source", source),
                    patterns=meta.get("patterns", []) or [], body=body,
                )
                self.rules[rid] = rule
                self.index.add(rid, self.embedder.embed(rule.text_for_embedding()),
                               {"domain": rule.domain, "source": rule.source, "cwe": rule.cwe})
        return self

    # ----- récupération des règles candidates ----------------------------------
    def candidates_for(self, function_source: str, *, top_k: int = 8,
                       domains: list[str] | None = None) -> list[Rule]:
        """Règles à appliquer à une fonction : toutes (exhaustive) ou top-k (vector)."""
        if self.backend == "vector":
            qvec = self.embedder.embed(function_source)
            where = (lambda m: m["domain"] in domains) if domains else None
            hits = self.index.search(qvec, top_k=top_k, where=where)
            return [self.rules[i] for i, _, _ in hits]
        # exhaustive
        rules = list(self.rules.values())
        if domains:
            rules = [r for r in rules if r.domain in domains]
        return rules

    # ----- détection : applique les motifs des règles candidates ---------------
    def detect_in_function(self, function_source: str, *, top_k: int = 8) -> list[tuple[Rule, str]]:
        out = []
        for rule in self.candidates_for(function_source, top_k=top_k):
            for pat in rule.patterns:
                try:
                    if re.search(pat, function_source):
                        out.append((rule, pat))
                        break
                except re.error:
                    continue
        return out

    def sources(self) -> dict:
        d: dict[str, int] = {}
        for r in self.rules.values():
            d[r.source] = d.get(r.source, 0) + 1
        return d

    def __len__(self):
        return len(self.rules)
