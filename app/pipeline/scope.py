"""In-scope scheme mention helpers for guardrail templates (full resolver is Phase 4)."""

from __future__ import annotations

import re

# More specific aliases first. Matching uses folded lowercase text.
SCHEME_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "hdfc-elss-tax-saver-direct-growth",
        ("elss tax saver", "tax saver", "elss", "tax-saver"),
    ),
    (
        "hdfc-gold-etf-fof-direct-growth",
        (
            "gold etf fund of fund",
            "gold etf fof",
            "gold fof",
            "gold etf",
            "fund of fund",
            "fund of funds",
            "gold fund",
            "gold",
        ),
    ),
    (
        "hdfc-small-cap-direct-growth",
        ("small cap", "small-cap", "smallcap"),
    ),
    (
        "hdfc-mid-cap-direct-growth",
        ("mid cap", "mid-cap", "midcap"),
    ),
    (
        "hdfc-large-cap-direct-growth",
        ("large cap", "large-cap", "largecap", "lrg cap"),
    ),
)

IN_SCOPE_LABELS = (
    "HDFC Mid Cap Fund — Direct Growth",
    "HDFC Small Cap Fund — Direct Growth",
    "HDFC Gold ETF Fund of Fund — Direct Plan Growth",
    "HDFC Large Cap Fund — Direct Growth",
    "HDFC ELSS Tax Saver Fund — Direct Plan Growth",
)


def fold_question(question: str) -> str:
    text = (question or "").lower().replace("'", "'")
    text = re.sub(r"[^\w\s%./+-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def mentioned_scheme_ids(question: str) -> list[str]:
    folded = f" {fold_question(question)} "
    hits: list[str] = []
    for scheme_id, aliases in SCHEME_ALIASES:
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", folded) for alias in aliases):
            hits.append(scheme_id)
    return hits
