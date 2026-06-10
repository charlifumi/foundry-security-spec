"""Interface LLMProvider (US-13) + comptabilité des tokens (FR-113).

Modes :
  - `deterministic` (défaut) : aucune dépendance, aucun coût $ ; compte des tokens
    estimés pour démontrer la comptabilité sans clé API. Les décisions de sécurité
    restent déterministes (motifs + résolution de citations).
  - `anthropic` : appel réel à l'API si le paquet `anthropic` et une clé sont présents ;
    coût calculé depuis la rate card.

Point d'instrumentation UNIQUE : chaque appel passe par `complete()` -> budget.record_call.
"""
from __future__ import annotations

import os
import time

# Rate card $/million de tokens — chargée/écrasable depuis forge.yaml (cost-and-routing.md §3).
RATE_CARD = {
    "claude-opus-4-8":   {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5":  {"input": 1.0, "output": 5.0},
    "deterministic":     {"input": 0.0, "output": 0.0},
}


def _approx_tokens(text: str) -> int:
    # Approximation portable (~4 caractères / token).
    return max(1, len(text) // 4)


class LLMProvider:
    def __init__(self, budget, *, mode: str = "deterministic",
                 model: str = "deterministic", rate_card: dict | None = None):
        self.budget = budget
        self.mode = mode
        self.model = model if mode != "deterministic" else "deterministic"
        self.rate_card = rate_card or RATE_CARD
        self._client = None
        if mode == "anthropic":
            self._init_anthropic()

    def _init_anthropic(self):
        try:
            import anthropic  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("mode anthropic demandé mais le paquet `anthropic` est absent") from e
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY manquante pour le mode anthropic")
        self._client = anthropic.Anthropic(api_key=key)

    def _cost(self, model: str, inp: int, out: int) -> float:
        r = self.rate_card.get(model, {"input": 0.0, "output": 0.0})
        return inp / 1e6 * r["input"] + out / 1e6 * r["output"]

    def complete(self, *, role: str, instance: str, prompt: str, system: str = "",
                 correlation_id: str | None = None, max_tokens: int = 512) -> str:
        """Un tour LLM, comptabilisé. Retourne le texte de réponse."""
        if self.mode == "anthropic":
            resp = self._client.messages.create(
                model=self.model, max_tokens=max_tokens,
                system=system or "Tu es un analyste de sécurité.",
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            inp, out = resp.usage.input_tokens, resp.usage.output_tokens
            estimated = False
        else:
            # Déterministe : réponse-trace courte, tokens estimés, coût marginal nul.
            text = f"[deterministic:{role}] traité ({_approx_tokens(prompt)} tok in)"
            inp, out = _approx_tokens(system + prompt), _approx_tokens(text)
            estimated = True
        self.budget.record_call(
            role=role, instance=instance, model=self.model, provider=self.mode,
            input_tokens=inp, output_tokens=out, cost_usd=self._cost(self.model, inp, out),
            estimated=estimated, correlation_id=correlation_id,
        )
        return text
