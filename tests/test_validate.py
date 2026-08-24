from __future__ import annotations

from app.pipeline.contract import count_sentences
from app.pipeline.validate import validate_generation

CHUNKS = [
    {
        "chunk_id": "hdfc-large-cap-direct-growth--expense_ratio",
        "text": "Expense ratio: 1.03",
        "scheme_name": "HDFC Large Cap Fund — Direct Growth",
        "as_of": "2026-08-21",
        "source_title": "HDFC Large Cap Fund — Direct Growth",
    }
]


def test_count_sentences_decimal_ter() -> None:
    assert count_sentences("The expense ratio is 1.03.") == 1


def test_accepts_grounded_ter() -> None:
    result = validate_generation(
        ("HDFC Large Cap Fund Direct Growth has an expense ratio of 1.03 on the loaded Groww page.",),
        chunks=CHUNKS,
        used_chunk_id="hdfc-large-cap-direct-growth--expense_ratio",
    )
    assert result.ok
    assert count_sentences(result.text) <= 3


def test_rejects_four_sentences() -> None:
    result = validate_generation(
        ("One.", "Two.", "Three.", "Four."),
        chunks=CHUNKS,
        used_chunk_id="hdfc-large-cap-direct-growth--expense_ratio",
    )
    assert not result.ok
    assert "more than 3 sentences" in result.reasons


def test_rejects_advice() -> None:
    result = validate_generation(
        ("You should invest in this fund because the expense ratio is 1.03.",),
        chunks=CHUNKS,
        used_chunk_id="hdfc-large-cap-direct-growth--expense_ratio",
    )
    assert not result.ok
    assert "advice lexicon" in result.reasons


def test_strips_hallucinated_url() -> None:
    result = validate_generation(
        ("The expense ratio is 1.03 according to https://www.hdfcfund.com/factsheet.",),
        chunks=CHUNKS,
        used_chunk_id="hdfc-large-cap-direct-growth--expense_ratio",
    )
    assert result.ok
    assert "hdfcfund.com" not in result.text
    assert "https://" not in result.text


def test_rejects_invented_number() -> None:
    result = validate_generation(
        ("The expense ratio is 0.99.",),
        chunks=CHUNKS,
        used_chunk_id="hdfc-large-cap-direct-growth--expense_ratio",
    )
    assert not result.ok
    assert "numeric claim not in excerpts" in result.reasons


def test_strips_model_footer() -> None:
    result = validate_generation(
        ("The expense ratio is 1.03. Last updated from sources: 2026-08-23.",),
        chunks=CHUNKS,
        used_chunk_id="hdfc-large-cap-direct-growth--expense_ratio",
    )
    assert "last updated" not in result.text.lower()


def test_unknown_chunk_id_dropped() -> None:
    result = validate_generation(
        ("The expense ratio is 1.03.",),
        chunks=CHUNKS,
        used_chunk_id="invented-chunk",
    )
    assert result.ok
    assert result.used_chunk_id is None


def test_rejects_pan_solicitation() -> None:
    result = validate_generation(
        ("Send your PAN so we can download the report.",),
        chunks=[{"chunk_id": "p", "text": "How to download capital gain report", "as_of": "2026-08-23"}],
        used_chunk_id="p",
        intent="process",
    )
    assert not result.ok
    assert "asks the user for account data" in result.reasons
