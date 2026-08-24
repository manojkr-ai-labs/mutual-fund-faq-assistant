"""Rule-based intent router. Conservative: facts mixed with advice → advisory."""

from __future__ import annotations

import re

from app.pipeline.pii import detect_pii
from app.pipeline.scope import fold_question, mentioned_scheme_ids

INTENTS = (
    "pii",
    "advisory",
    "comparison",
    "performance",
    "process",
    "scheme_fact",
    "out_of_scope",
    "empty",
)

ADVISORY_PHRASES = (
    "should i",
    "shall i",
    "can i invest",
    "could i invest",
    "would you invest",
    "is it good for me",
    "is it safe for me",
    "better for me",
    "risk appetite",
    "suitable",
    "suitability",
    "recommend",
    "recommendation",
    "worth investing",
    "good investment",
    "start sip in",
    "put my money",
    "invest in this",
    "should we",
)
ADVISORY_WORDS = re.compile(
    r"\b(?:buy|sell|advise|advice|recommend(?:ed)?)\b",
)

COMPARISON_PHRASES = (
    "which is better",
    "which fund is better",
    "which should i pick",
    "which should i choose",
    "vs",
    "versus",
    "better than",
    "best fund",
    "best hdfc",
    "rank these",
    "rank the",
    "outperform",
    "side by side",
    "compare",
    "comparison",
)

FORWARD_LOOKING = (
    "will this fund beat",
    "will it beat",
    "expected return",
    "expected returns",
    "future return",
    "forecast",
    "if i sip",
    "for 10 years",
    "for ten years",
    "projection",
    "predict",
)

PERFORMANCE_PHRASES = (
    "cagr",
    "returns",
    "return last",
    "last year",
    "trailing",
    "how much did",
    "how much has",
    "nav grow",
    "nav history",
    "performance",
    "1y",
    "3y",
    "5y",
    "1 y",
    "3 y",
    "5 y",
    "one year return",
    "three year",
    "five year",
    "annualized",
    "gave last",
)

PROCESS_PHRASES = (
    "capital gain",
    "capital gains",
    "transaction history",
    "order history",
    "download statement",
    "account statement",
    "elss statement",
    "tax statement",
    "how do i download",
    "how to download",
    "where can i get the transaction",
    "cas ",
    " consolidated account",
)

SCHEME_FACT_PHRASES = (
    "expense ratio",
    "total expense",
    " ter",
    "ter ",
    "ter?",
    "exit load",
    "redemption load",
    "minimum sip",
    "min sip",
    "min investment",
    "minimum investment",
    "sip amount",
    "riskometer",
    "risk level",
    "how risky",
    "benchmark",
    "lock-in",
    "lock in",
    "lockin",
    "investment objective",
    "what does it invest",
    "what does the scheme",
    "what is a large cap",
    "what is a mid cap",
    "what is a small cap",
    "what is elss",
    "types of mutual fund",
    "types of fund",
    "fund of fund",
)

OTHER_AMC = (
    "sbi ",
    "sbi.",
    "bluechip",
    "icici",
    "axis mutual",
    "axis bluechip",
    "kotak",
    "nippon",
    "uti nifty",
    "uti ",
    "mirae",
    "ppfas",
    "parag parikh",
    "motilal",
    "quant ",
    "bandhan",
    "aditya birla",
    "birla sun",
    "franklin",
    "tata mutual",
    "dsp ",
    "hsbc mutual",
    "edelweiss",
    "canara robeco",
    "whiteoak",
    "baroda",
)
OTHER_HDFC_PRODUCTS = (
    "balanced advantage",
    "flexi cap fund",
    "hdfc flexi",
    "hdfc index",
    "hdfc hybrid",
    "top 100",
)
CRYPTO = ("bitcoin", "btc", "crypto", "ethereum", "dogecoin", "web3 coin")
EQUITY_PRODUCTS = (
    "reliance stock",
    "buy stock",
    "share price",
    "equity share",
    "nse listed",
)
TAX_FILING = (
    "file my itr",
    "file itr",
    "income tax return",
    "tax filing",
    "how to save tax",
    "save tax beyond",
)
PORTFOLIO = ("60/40", "60 40", "build me a", "portfolio for me", "asset allocation for me")
NON_GROWW_SOURCES = ("value research", "morningstar", "hdfcfund.com", "amfiindia", "sebi.gov")


def _has_any(folded: str, phrases: tuple[str, ...]) -> bool:
    padded = f" {folded} "
    return any(phrase in padded or phrase in folded for phrase in phrases)


def _is_advisory(folded: str) -> bool:
    if _has_any(folded, ADVISORY_PHRASES):
        return True
    if ADVISORY_WORDS.search(folded):
        # "buy" in "buy hdfc large cap" is advice; process "download" is not.
        return True
    if _has_any(folded, FORWARD_LOOKING):
        return True
    return False


def _is_comparison(folded: str) -> bool:
    if re.search(r"\bbest\b", folded) and re.search(r"\b(?:fund|scheme|elss|tax)\b", folded):
        return True
    if re.search(r"\brank\b", folded):
        return True
    return _has_any(folded, COMPARISON_PHRASES)


def _is_performance(folded: str) -> bool:
    if re.search(r"\b(?:1y|3y|5y)\b", folded):
        return True
    if re.search(r"\bcagr\b", folded):
        return True
    return _has_any(folded, PERFORMANCE_PHRASES)


def _is_process(folded: str) -> bool:
    if "folio" in folded and detect_pii(folded) is None:
        # Word-only folio questions can be process; values are PII (already handled).
        if "enter" in folded or "where" in folded or "download" in folded:
            return True
    return _has_any(folded, PROCESS_PHRASES)


def _is_out_of_scope(folded: str) -> bool:
    if _has_any(folded, CRYPTO + EQUITY_PRODUCTS + TAX_FILING + PORTFOLIO):
        return True
    if re.search(r"\b(?:stocks?|crypto|bitcoin)\b", folded) and not mentioned_scheme_ids(folded):
        return True
    if _has_any(folded, OTHER_AMC):
        return True
    if _has_any(folded, OTHER_HDFC_PRODUCTS):
        return True
    # Asking us to use a non-Groww publisher as the source, with no in-scope scheme fact.
    if _has_any(folded, NON_GROWW_SOURCES) and not (
        _has_any(folded, SCHEME_FACT_PHRASES) and mentioned_scheme_ids(folded)
    ):
        return True
    return False


def _is_scheme_fact(folded: str) -> bool:
    if _has_any(folded, SCHEME_FACT_PHRASES):
        return True
    if mentioned_scheme_ids(folded):
        return True
    if "hdfc" in folded:
        return True
    return False


def route(question: str, *, pii: bool | None = None) -> str:
    """Classify a question. PII wins. Advice mixed with facts → advisory."""
    if pii is None:
        pii = detect_pii(question) is not None
    if pii:
        return "pii"
    folded = fold_question(question)
    if not folded:
        return "empty"
    if _is_comparison(folded):
        return "comparison"
    if _is_advisory(folded):
        return "advisory"
    if _is_out_of_scope(folded):
        return "out_of_scope"
    if _is_performance(folded):
        return "performance"
    if _is_process(folded):
        return "process"
    if _is_scheme_fact(folded):
        return "scheme_fact"
    return "out_of_scope"
