"""Rule-based fact-type detector. No Groq."""

from __future__ import annotations

import re

from app.pipeline.scope import fold_question


def _has_phrase(folded: str, phrase: str) -> bool:
    return phrase in folded


def _has_word(folded: str, word: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", folded) is not None


def detect_fact_type(question: str) -> str | None:
    folded = f" {fold_question(question)} "

    # Longer / unambiguous cues first so "riskometer" is not parsed as TER.
    if (
        _has_word(folded, "riskometer")
        or _has_phrase(folded, "risk level")
        or _has_phrase(folded, "how risky")
        or _has_phrase(folded, "risk classification")
    ):
        return "riskometer"
    if _has_phrase(folded, "expense ratio") or _has_phrase(folded, "total expense") or _has_word(folded, "ter"):
        return "expense_ratio"
    if _has_phrase(folded, "exit load") or _has_phrase(folded, "redemption load"):
        return "exit_load"
    if (
        _has_phrase(folded, "minimum sip")
        or _has_phrase(folded, "min sip")
        or _has_phrase(folded, "min investment")
        or _has_phrase(folded, "minimum investment")
        or _has_phrase(folded, "minimum amount")
        or _has_phrase(folded, "sip amount")
        or _has_word(folded, "sip")
    ):
        return "sip"
    if _has_word(folded, "benchmark"):
        return "benchmark"
    if _has_phrase(folded, "lock-in") or _has_phrase(folded, "lock in") or _has_word(folded, "lockin"):
        return "lockin"
    if (
        _has_phrase(folded, "investment objective")
        or _has_phrase(folded, "what does it invest")
        or _has_phrase(folded, "what does the scheme")
        or _has_phrase(folded, "what does this scheme")
        or _has_phrase(folded, "what does the fund invest")
    ):
        return "objective"
    if _has_phrase(folded, "capital gain") or _has_phrase(folded, "capital gains"):
        return "capital_gains"
    if (
        _has_phrase(folded, "elss statement")
        or _has_phrase(folded, "tax statement")
        or _has_phrase(folded, "elss tax")
        or _has_phrase(folded, "elss report")
    ):
        return "elss_statement"
    if (
        _has_phrase(folded, "transaction history")
        or _has_phrase(folded, "order history")
        or _has_phrase(folded, "account statement")
        or _has_phrase(folded, "download statement")
        or _has_phrase(folded, "mutual fund statement")
        or _has_phrase(folded, "download my statement")
    ):
        return "statement"
    if (
        _has_phrase(folded, "what is a large cap")
        or _has_phrase(folded, "what is a mid cap")
        or _has_phrase(folded, "what is a small cap")
        or _has_phrase(folded, "what are large cap")
        or _has_phrase(folded, "what are mid cap")
        or _has_phrase(folded, "what are small cap")
        or _has_phrase(folded, "what is large cap")
        or _has_phrase(folded, "what is mid cap")
        or _has_phrase(folded, "what is small cap")
        or _has_phrase(folded, "what is elss")
        or _has_phrase(folded, "what is an elss")
        or _has_phrase(folded, "what are elss")
        or _has_phrase(folded, "what is a fund of fund")
        or _has_phrase(folded, "what is fund of fund")
        or _has_phrase(folded, "what is a fof")
        or _has_phrase(folded, "what is fof")
        or _has_phrase(folded, "what is an index fund")
        or _has_phrase(folded, "types of mutual fund")
        or _has_phrase(folded, "types of fund")
        or _has_phrase(folded, "types of funds")
        or _has_phrase(folded, "how many types of fund")
    ):
        return "education"
    return None
