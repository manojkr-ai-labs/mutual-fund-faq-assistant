"""Phase 3 guardrails: PII → router → templates. Never calls Groq."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.corpus.catalog import SourceRecord, load_catalog, project_root
from app.pipeline.contract import AskResponse
from app.pipeline.pii import PiiHit, detect_pii
from app.pipeline.router import route
from app.pipeline import templates

MAX_QUESTION_CHARS = 8000


@dataclass(frozen=True)
class GuardResult:
    """If terminal is True, response is ready and Groq must not be called."""

    terminal: bool
    intent: str
    response: AskResponse | None
    pii: PiiHit | None = None


def apply_guardrails(
    question: str | None,
    *,
    root: Path | None = None,
) -> GuardResult:
    """Inspect a question. Does not retrieve, generate, log, or write the question."""
    root = root or project_root()
    _raw, records = load_catalog(root=root)
    return _decide(question, records)


def _decide(question: str | None, records: list[SourceRecord]) -> GuardResult:
    text = "" if question is None else str(question)
    if len(text) > MAX_QUESTION_CHARS:
        return GuardResult(True, "empty", templates.too_long(records), None)
    if not text.strip():
        return GuardResult(True, "empty", templates.empty_question(records), None)

    pii = detect_pii(text)
    intent = route(text, pii=pii is not None)
    if intent == "pii":
        return GuardResult(True, "pii", templates.pii_refusal(records), pii)
    if intent == "advisory":
        return GuardResult(True, intent, templates.advisory_refusal(records), None)
    if intent == "comparison":
        return GuardResult(True, intent, templates.comparison_refusal(records), None)
    if intent == "out_of_scope":
        return GuardResult(True, intent, templates.out_of_scope_refusal(records), None)
    if intent == "performance":
        return GuardResult(True, intent, templates.performance_factsheet(text, records), None)
    if intent == "empty":
        return GuardResult(True, "empty", templates.empty_question(records), None)
    return GuardResult(False, intent, None, None)
