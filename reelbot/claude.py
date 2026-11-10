"""Thin wrappers around the Anthropic SDK used by the pipeline."""

from __future__ import annotations

import logging
from typing import Type, TypeVar

import anthropic
from pydantic import BaseModel

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Server-side refusal fallback: if the primary model declines, the API retries on a
# suitable fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeRefusal(RuntimeError):
    pass


_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=4)
    return _client


def _check_refusal(message) -> None:
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        raise ClaudeRefusal(f"Claude declined the request: {details}")


def parse(model: str, system, prompt: str, schema: Type[T], effort: str) -> T:
    """Structured-output request that returns a validated pydantic object."""
    response = client().beta.messages.parse(
        model=model,
        max_tokens=16000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
    )
    _check_refusal(response)
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Story response was truncated (max_tokens)")
    return response.parsed_output


def text(model: str, system, prompt: str, effort: str, max_tokens: int = 48000) -> str:
    """Streaming free-text request (used for long SVG output)."""
    with client().beta.messages.stream(
        model=model,
        max_tokens=max_tokens,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()
    _check_refusal(message)
    usage = message.usage
    log.debug(
        "claude usage: in=%s out=%s cache_read=%s",
        usage.input_tokens,
        usage.output_tokens,
        getattr(usage, "cache_read_input_tokens", None),
    )
    return "".join(b.text for b in message.content if b.type == "text")
