"""Ask-response contract helpers (Phase 3). No Groq."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

DISCLAIMER = "Facts-only. No investment advice."

ADVICE_LEXICON = (
    "recommend",
    "should invest",
    "better than",
    "outperform",
    "guaranteed",
    "suitable for you",
    "must invest",
)
ADVICE_WORDS = frozenset({"buy", "sell"})

PERCENT = re.compile(r"\d+(?:\.\d+)?\s*%")

_ABBREVIATIONS = (
    "e.g.",
    "i.e.",
    "U.S.",
    "u.s.",
    "Mr.",
    "Mrs.",
    "Dr.",
    "SEBI.",
    "AMFI.",
    "NAV.",
    "TER.",
    "SIP.",
    "ELSS.",
    "FoF.",
    "ETF.",
    "No.",
)


@dataclass(frozen=True)
class AskResponse:
    type: str
    text: str
    citation_url: str
    citation_label: str
    last_updated_from_sources: str
    disclaimer: str = DISCLAIMER

    def as_public_dict(self) -> dict:
        return asdict(self)


def count_sentences(text: str) -> int:
    if not (text or "").strip():
        return 0
    masked = text
    for i, abbr in enumerate(_ABBREVIATIONS):
        masked = masked.replace(abbr, f"⟦ABBREV{i}⟧")
    masked = re.sub(r"\d+\.\d+", lambda match: match.group(0).replace(".", "⟦DOT⟧"), masked)
    masked = masked.replace(".env", "⟦DOTENV⟧")
    masked = masked.replace("...", "⟦ELLIPSIS⟧").replace("…", "⟦ELLIPSIS⟧")
    parts = re.split(r"[.!?]+", masked)
    return len([part for part in parts if part.strip()])


def contains_advice(text: str) -> bool:
    lowered = (text or "").lower()
    if any(phrase in lowered for phrase in ADVICE_LEXICON):
        return True
    return bool(re.search(r"\b(?:buy|sell)\b", lowered))


def contains_return_percent(text: str) -> bool:
    return bool(PERCENT.search(text or ""))


def assert_guardrail_payload(response: AskResponse, *, allowlisted: set[str] | frozenset[str]) -> None:
    if response.type not in {"answer", "refuse", "factsheet_only", "error"}:
        raise ValueError(f"invalid response type {response.type!r}")
    if count_sentences(response.text) > 3:
        raise ValueError("response exceeds 3 sentences")
    if contains_advice(response.text):
        raise ValueError("response contains advice lexicon")
    if response.type == "factsheet_only" and contains_return_percent(response.text):
        raise ValueError("factsheet_only body must not contain return percentages")
    if not response.citation_url.startswith("https://groww.in/"):
        raise ValueError("citation must be a groww.in HTTPS URL")
    if response.citation_url not in allowlisted:
        raise ValueError(f"citation not in catalog: {response.citation_url}")
    if not response.last_updated_from_sources:
        raise ValueError("footer as_of missing")
    if response.disclaimer != DISCLAIMER:
        raise ValueError("disclaimer must be the facts-only line")
