"""Groq model allowlist and env loading. Never log secrets."""

from __future__ import annotations

import os

from dotenv import load_dotenv

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
ALLOWED_GROQ_MODELS = frozenset(
    {
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
    }
)
FORBIDDEN_GROQ_MODELS = frozenset(
    {
        "groq/compound",
        "groq/compound-mini",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    }
)

_DOTENV_LOADED = False


class GroqConfigError(RuntimeError):
    """Invalid Groq configuration. Message must never include the API key."""


def load_env() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    load_dotenv()
    _DOTENV_LOADED = True


def groq_api_key() -> str | None:
    load_env()
    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    return key or None


def is_forbidden_model(model: str) -> bool:
    name = (model or "").strip()
    lowered = name.lower()
    if name in FORBIDDEN_GROQ_MODELS:
        return True
    if "compound" in lowered:
        return True
    if lowered in {item.lower() for item in FORBIDDEN_GROQ_MODELS}:
        return True
    return False


def resolve_groq_model(model: str | None = None) -> str:
    load_env()
    name = (model if model is not None else os.environ.get("GROQ_MODEL") or DEFAULT_GROQ_MODEL).strip()
    if is_forbidden_model(name):
        raise GroqConfigError(
            "GROQ_MODEL is forbidden (Compound web-search or decommissioned Llama). "
            "Use openai/gpt-oss-120b or openai/gpt-oss-20b."
        )
    if name not in ALLOWED_GROQ_MODELS:
        raise GroqConfigError(
            "GROQ_MODEL is not allowed. Use openai/gpt-oss-120b or openai/gpt-oss-20b."
        )
    return name
