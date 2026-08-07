"""Thin wrapper around the Anthropic SDK: one function for structured output,
one for plain text. Every agent goes through these two, so cost tracking and
the model choice live in exactly one place.
"""
import os
from typing import TypeVar

import anthropic
from pydantic import BaseModel

# Sonnet 5 is ~40% the cost of Opus 5 and plenty capable for this pipeline's
# agents — override with HEDGI_MODEL=claude-opus-5 if you want max quality
# and are less cost-sensitive.
MODEL = os.environ.get("HEDGI_MODEL", "claude-sonnet-5")
MAX_TOKENS = 4000  # these agents return one plan/file-set/report, not essays

# Conservative (non-intro) per-million-token rates, USD. Used only to print a
# running estimate — check console.anthropic.com for actual billed usage.
PRICES = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

client = anthropic.Anthropic()
T = TypeVar("T", bound=BaseModel)
_total_cost = 0.0


def _track(usage) -> None:
    global _total_cost
    in_price, out_price = PRICES.get(MODEL, (0, 0))
    cost = (usage.input_tokens * in_price + usage.output_tokens * out_price) / 1_000_000
    _total_cost += cost
    print(f"[llm] {MODEL}: {usage.input_tokens} in / {usage.output_tokens} out "
          f"(~${cost:.4f}, session total ~${_total_cost:.4f})")


def _forbid_extra_properties(node: object) -> object:
    """Structured outputs requires additionalProperties: false on every
    object schema, not just the top level — Pydantic's nested $defs (e.g. a
    list[SubModel] field) don't get it by default, and the API 400s if any
    object in the tree is missing it."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            node["additionalProperties"] = False
        for value in node.values():
            _forbid_extra_properties(value)
    elif isinstance(node, list):
        for item in node:
            _forbid_extra_properties(item)
    return node


class TruncatedOutput(RuntimeError):
    """Raised when the model hit max_tokens before finishing — the caller got
    a syntactically incomplete response, not a considered short answer."""


def _check_truncation(resp) -> None:
    if resp.stop_reason == "max_tokens":
        raise TruncatedOutput(
            f"Response hit the {resp.usage.output_tokens}-token cap before finishing. "
            "Raise max_tokens for this call rather than trusting a cut-off response."
        )


def structured(system: str, user: str, schema: type[T], max_tokens: int = MAX_TOKENS) -> T:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": _forbid_extra_properties(schema.model_json_schema()),
            }
        },
    )
    _track(resp.usage)
    _check_truncation(resp)
    text = next(b.text for b in resp.content if b.type == "text")
    return schema.model_validate_json(text)


def text(system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    _track(resp.usage)
    _check_truncation(resp)
    return next(b.text for b in resp.content if b.type == "text")
