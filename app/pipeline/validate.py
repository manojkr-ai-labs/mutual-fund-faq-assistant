"""Hard gate on generated answers. Citation URL and footer are attached by the orchestrator."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.pipeline.contract import contains_advice, contains_return_percent, count_sentences

URL = re.compile(r"https?://\S+", re.IGNORECASE)
FOOTER = re.compile(r"last updated from sources\s*:.*", re.IGNORECASE)
NUMBER = re.compile(r"\d+(?:\.\d+)?")
PAN_SOLICIT = re.compile(
    r"\b(?:send|share|enter|provide|type|paste|give)\b.{0,48}\b(?:pan|aadhaar|folio|otp)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reasons: tuple[str, ...]
    sentences: tuple[str, ...]
    text: str
    used_chunk_id: str | None


def evidence_text(chunks: list[dict]) -> str:
    parts: list[str] = []
    for chunk in chunks:
        parts.extend(
            [
                str(chunk.get("text") or ""),
                str(chunk.get("scheme_name") or ""),
                str(chunk.get("source_title") or ""),
                str(chunk.get("as_of") or ""),
                str(chunk.get("retrieved_on") or ""),
            ]
        )
    return "\n".join(parts)


def _numbers(text: str) -> list[float]:
    return [float(match.group(0)) for match in NUMBER.finditer(text or "")]


def _number_allowed(value: float, allowed: list[float]) -> bool:
    for item in allowed:
        if abs(item - value) <= max(1e-9, abs(item) * 1e-6):
            return True
    return False


def normalize_sentences(sentences: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for raw in sentences:
        line = FOOTER.sub("", URL.sub("", raw or "")).strip()
        line = re.sub(r"\s+", " ", line).strip(" -;")
        if line:
            cleaned.append(line)
    return tuple(cleaned)


def join_sentences(sentences: tuple[str, ...]) -> str:
    if not sentences:
        return ""
    parts: list[str] = []
    for item in sentences:
        text = item.rstrip()
        if text and text[-1] not in ".!?":
            text += "."
        parts.append(text)
    return " ".join(parts)


def validate_generation(
    sentences: tuple[str, ...] | list[str],
    *,
    chunks: list[dict],
    used_chunk_id: str | None,
    intent: str = "scheme_fact",
) -> ValidationResult:
    reasons: list[str] = []
    normalized = normalize_sentences(sentences)
    text = join_sentences(normalized)

    if not normalized:
        reasons.append("empty answer")
    if count_sentences(text) > 3:
        reasons.append("more than 3 sentences")
    if contains_advice(text):
        reasons.append("advice lexicon")
    if PAN_SOLICIT.search(text):
        reasons.append("asks the user for account data")
    if intent == "performance" and contains_return_percent(text):
        reasons.append("computed return percentage")

    allowed = _numbers(evidence_text(chunks))
    for value in _numbers(text):
        if not _number_allowed(value, allowed):
            reasons.append("numeric claim not in excerpts")
            break

    chunk_ids = {str(chunk.get("chunk_id") or "") for chunk in chunks}
    chosen = used_chunk_id if used_chunk_id in chunk_ids else None

    return ValidationResult(
        ok=not reasons,
        reasons=tuple(reasons),
        sentences=normalized,
        text=text,
        used_chunk_id=chosen,
    )
