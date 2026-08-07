"""Thin wrapper around the Anthropic SDK: one function for structured output,
one for plain text. Every agent goes through these two.
"""
from typing import TypeVar

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5"
client = anthropic.Anthropic()

T = TypeVar("T", bound=BaseModel)


def structured(system: str, user: str, schema: type[T]) -> T:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {**schema.model_json_schema(), "additionalProperties": False},
            }
        },
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return schema.model_validate_json(text)


def text(system: str, user: str) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return next(b.text for b in resp.content if b.type == "text")
