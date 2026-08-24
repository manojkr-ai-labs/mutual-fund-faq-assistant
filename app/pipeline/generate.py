"""Groq Chat Completions formatter. Does not choose citation URLs or dates."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.pipeline.config import GroqConfigError, groq_api_key, resolve_groq_model
from app.pipeline.pii import detect_pii
from app.pipeline.rate_limit import (
    GroqQuota,
    GroqQuotaError,
    estimate_prompt_tokens,
    groq_quota,
)

TEMPERATURE = 0
MAX_COMPLETION_TOKENS = 256
RETRY_SLEEP_SEC = 0.6
RETRY_MAX_SLEEP_SEC = 2.0

ANSWER_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {"type": "string"},
        },
        "used_chunk_id": {"type": "string"},
    },
    "required": ["sentences", "used_chunk_id"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are a facts-only formatter for a mutual-fund FAQ assistant.
Answer ONLY from the Groww excerpts in the user message. Do not use other knowledge.
Return JSON with keys sentences (array of at most 3 strings) and used_chunk_id.
Rules:
- Maximum three short factual sentences.
- No investment advice, recommendations, comparisons, rankings, or return math.
- Do not invent numbers, dates, or scheme names; copy figures exactly from excerpts.
- Do not mention AMC, AMFI, SEBI, Value Research, Morningstar, or other non-Groww sites.
- Do not include URLs or a last-updated footer; those are attached separately.
- Do not ask the user to send PAN, Aadhaar, folio, OTP, email, or phone.
- If excerpts are insufficient, say the fact is not in the loaded Groww pages.
- Set used_chunk_id to the excerpt id that supports the answer.
"""

FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class GroqCallError(RuntimeError):
    """Transport or provider failure. Never includes the API key."""


@dataclass(frozen=True)
class GeneratedAnswer:
    sentences: tuple[str, ...]
    used_chunk_id: str
    raw: str


def _require_no_pii(question: str) -> None:
    if detect_pii(question) is not None:
        raise RuntimeError("refusing to call Groq for a PII-flagged question")


def build_messages(question: str, chunks: list[dict], *, repair_reason: str | None = None) -> list[dict[str, str]]:
    excerpts: list[str] = []
    for chunk in chunks:
        excerpts.append(
            "\n".join(
                [
                    f"chunk_id: {chunk.get('chunk_id')}",
                    f"scheme: {chunk.get('scheme_name') or ''}",
                    f"as_of: {chunk.get('as_of') or ''}",
                    f"text: {chunk.get('text') or ''}",
                ]
            )
        )
    user = (
        f"Question:\n{question.strip()}\n\n"
        "Groww excerpts:\n"
        + "\n---\n".join(excerpts)
    )
    if repair_reason:
        user += (
            "\n\nYour previous JSON failed validation: "
            f"{repair_reason} "
            "Rewrite using only excerpt facts. Max three sentences. No advice."
        )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def parse_generated_json(raw: str) -> GeneratedAnswer:
    text = FENCE.sub("", (raw or "").strip()).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GroqCallError("model returned malformed JSON") from exc
    if not isinstance(payload, dict):
        raise GroqCallError("model JSON must be an object")
    sentences = payload.get("sentences")
    if isinstance(sentences, str):
        sentences = [sentences]
    if not isinstance(sentences, list) or not all(isinstance(item, str) for item in sentences):
        raise GroqCallError("model JSON sentences must be an array of strings")
    used = payload.get("used_chunk_id") or ""
    if not isinstance(used, str):
        used = ""
    cleaned = tuple(item.strip() for item in sentences if str(item).strip())
    return GeneratedAnswer(sentences=cleaned, used_chunk_id=used.strip(), raw=raw)


def _completion_kwargs(
    model: str,
    messages: list[dict[str, str]],
    *,
    max_completion_tokens: int = MAX_COMPLETION_TOKENS,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": TEMPERATURE,
        "max_completion_tokens": max_completion_tokens,
        "stream": False,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "faq_answer",
                "strict": True,
                "schema": ANSWER_JSON_SCHEMA,
            },
        },
    }
    if model.startswith("openai/gpt-oss"):
        kwargs["reasoning_effort"] = "low"
    return kwargs


def _content_from_response(response: Any) -> str:
    choice = response.choices[0]
    message = choice.message
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    raise GroqCallError("model returned an empty completion")


def _usage_tokens(response: Any, fallback: int) -> int:
    usage = getattr(response, "usage", None)
    if usage is None:
        return fallback
    total = getattr(usage, "total_tokens", None)
    if isinstance(total, int) and total > 0:
        return total
    prompt = getattr(usage, "prompt_tokens", None) or 0
    completion = getattr(usage, "completion_tokens", None) or 0
    counted = int(prompt) + int(completion)
    return counted if counted > 0 else fallback


def _retry_sleep_seconds(exc: BaseException) -> float:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw = None
    if hasattr(headers, "get"):
        raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw is not None:
        try:
            return min(max(0.0, float(raw)), RETRY_MAX_SLEEP_SEC)
        except (TypeError, ValueError):
            pass
    return RETRY_SLEEP_SEC


def _chunks_for_budget(
    question: str,
    chunks: list[dict],
    *,
    repair_reason: str | None,
    tpm: int,
) -> list[dict]:
    """Drop trailing excerpts until prompt + min completion can fit in TPM."""
    selected = list(chunks)
    while selected:
        messages = build_messages(question, selected, repair_reason=repair_reason)
        if estimate_prompt_tokens(messages) + 64 <= tpm:
            return selected
        if len(selected) == 1:
            return selected
        selected = selected[:-1]
    return chunks[:1]


def _reserve_and_call(
    create: Callable[..., Any],
    *,
    model: str,
    messages: list[dict[str, str]],
    quota: GroqQuota,
) -> Any:
    prompt_tokens = estimate_prompt_tokens(messages)
    reservation = quota.reserve(prompt_tokens, max_completion=MAX_COMPLETION_TOKENS)
    kwargs = _completion_kwargs(
        model,
        messages,
        max_completion_tokens=reservation.max_completion_tokens,
    )
    try:
        response = create(**kwargs)
    except Exception:
        quota.settle(reservation, 0)
        raise
    quota.settle(reservation, _usage_tokens(response, reservation.reserved_tokens))
    return response


def _call_with_retry(
    create: Callable[..., Any],
    *,
    model: str,
    messages: list[dict[str, str]],
    quota: GroqQuota,
) -> Any:
    try:
        return _reserve_and_call(create, model=model, messages=messages, quota=quota)
    except GroqQuotaError as exc:
        raise GroqCallError("Groq rate limit reached") from exc
    except Exception as first:
        if not _is_retryable(first):
            raise
        time.sleep(_retry_sleep_seconds(first))
        try:
            return _reserve_and_call(create, model=model, messages=messages, quota=quota)
        except GroqQuotaError as exc:
            raise GroqCallError("Groq rate limit reached") from exc
        except Exception as second:
            raise GroqCallError("Groq request failed after one retry") from second


def _is_retryable(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in {"RateLimitError", "APITimeoutError", "APIConnectionError", "InternalServerError"}:
        return True
    status = getattr(exc, "status_code", None)
    if status in {429, 500, 502, 503, 504}:
        return True
    return False


def generate_answer(
    question: str,
    chunks: list[dict],
    *,
    repair_reason: str | None = None,
    groq_client: Any | None = None,
    model: str | None = None,
    quota: GroqQuota | None = None,
) -> GeneratedAnswer:
    """Call Groq to phrase retrieved Groww facts as JSON. Never send PII."""
    _require_no_pii(question)
    if not chunks:
        raise GroqCallError("no excerpts to format")
    key = groq_api_key() if groq_client is None else "injected"
    if groq_client is None and not key:
        raise GroqConfigError("GROQ_API_KEY is not set")
    model_id = resolve_groq_model(model)
    tracker = quota if quota is not None else groq_quota()
    fitted = _chunks_for_budget(
        question,
        chunks,
        repair_reason=repair_reason,
        tpm=tracker.limits.tpm,
    )
    messages = build_messages(question, fitted, repair_reason=repair_reason)

    if groq_client is None:
        from groq import Groq

        client = Groq(api_key=key, timeout=20.0)
    else:
        client = groq_client

    try:
        response = _call_with_retry(
            client.chat.completions.create,
            model=model_id,
            messages=messages,
            quota=tracker,
        )
    except GroqCallError:
        raise
    except GroqConfigError:
        raise
    except GroqQuotaError as exc:
        raise GroqCallError("Groq rate limit reached") from exc
    except Exception as exc:
        name = type(exc).__name__
        if name in {"AuthenticationError", "PermissionDeniedError"}:
            raise GroqCallError("Groq request was not authorized") from exc
        if _is_retryable(exc):
            raise GroqCallError("Groq request failed") from exc
        raise GroqCallError("Groq request failed") from exc
    return parse_generated_json(_content_from_response(response))
