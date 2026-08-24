"""Resolve an in-scope scheme from the question. Rules only; no Groq."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.pipeline.scope import SCHEME_ALIASES, fold_question, mentioned_scheme_ids

BARE_FUND = re.compile(r"\b(?:the fund|this fund|that fund|the scheme|this scheme)\b")
HDFC_TOKEN = re.compile(r"\bhdfc\b")

# Extra legal-name / slug fragments not already covered by category aliases.
LEGAL_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "hdfc-elss-tax-saver-direct-growth",
        (
            "hdfc elss tax saver fund",
            "hdfc elss tax saver",
            "hdfc tax saver",
            "hdfc-elss-tax-saver-direct-growth",
        ),
    ),
    (
        "hdfc-gold-etf-fof-direct-growth",
        (
            "hdfc gold etf fund of fund",
            "hdfc gold etf fof",
            "hdfc gold etf",
            "hdfc gold",
            "hdfc-gold-etf-fof-direct-growth",
        ),
    ),
    (
        "hdfc-small-cap-direct-growth",
        (
            "hdfc small cap fund",
            "hdfc small cap",
            "hdfc-small-cap-direct-growth",
        ),
    ),
    (
        "hdfc-mid-cap-direct-growth",
        (
            "hdfc mid cap fund",
            "hdfc mid cap",
            "hdfc-mid-cap-direct-growth",
        ),
    ),
    (
        "hdfc-large-cap-direct-growth",
        (
            "hdfc large cap fund",
            "hdfc large cap",
            "hdfc lrg cap",
            "hdfc-large-cap-direct-growth",
        ),
    ),
)


@dataclass(frozen=True)
class SchemeResolution:
    """status: resolved (exactly one), ambiguous (clarify), none (no scheme mention)."""

    status: str
    scheme_ids: tuple[str, ...] = ()

    @property
    def scheme_id(self) -> str | None:
        if self.status == "resolved" and len(self.scheme_ids) == 1:
            return self.scheme_ids[0]
        return None


def _alias_hits(folded: str) -> list[str]:
    padded = f" {folded} "
    hits: list[str] = []
    for scheme_id, aliases in (*SCHEME_ALIASES, *LEGAL_ALIASES):
        if scheme_id in hits:
            continue
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", padded) for alias in aliases):
            hits.append(scheme_id)
    return hits


def resolve_scheme(question: str) -> SchemeResolution:
    """Map a question to zero, one, or many in-scope scheme ids.

    Bare "HDFC" or "the fund" with no category is ambiguous — never guess.
    """
    folded = fold_question(question)
    if not folded:
        return SchemeResolution("none")

    hits = _alias_hits(folded)
    if not hits:
        hits = mentioned_scheme_ids(question)

    unique = tuple(dict.fromkeys(hits))
    if len(unique) > 1:
        return SchemeResolution("ambiguous", unique)
    if len(unique) == 1:
        return SchemeResolution("resolved", unique)

    if HDFC_TOKEN.search(folded) or BARE_FUND.search(folded):
        return SchemeResolution("ambiguous")
    return SchemeResolution("none")
