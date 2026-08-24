from __future__ import annotations

from app.pipeline.retrieve import retrieve_for_question

LARGE = "hdfc-large-cap-direct-growth"
MID = "hdfc-mid-cap-direct-growth"
SMALL = "hdfc-small-cap-direct-growth"
GOLD = "hdfc-gold-etf-fof-direct-growth"
ELSS = "hdfc-elss-tax-saver-direct-growth"

LARGE_URL = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
GOLD_URL = "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth"
ELSS_URL = "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth"
EDU_URL = "https://groww.in/p/types-of-mutual-funds"
CG_URL = "https://groww.in/help/mutual-funds/mf-others/how-to-download-capital-gain-report--50"

FACT_TYPES = (
    "expense_ratio",
    "exit_load",
    "sip",
    "riskometer",
    "benchmark",
)

SCHEMES = (
    (MID, "HDFC Mid Cap Fund Direct Growth"),
    (SMALL, "HDFC Small Cap Fund Direct Growth"),
    (GOLD, "HDFC Gold ETF Fund of Fund Direct Plan Growth"),
    (LARGE, "HDFC Large Cap Fund Direct Growth"),
    (ELSS, "HDFC ELSS Tax Saver Fund Direct Plan Growth"),
)

FACT_QUESTIONS = {
    "expense_ratio": "What is the expense ratio of {name}?",
    "exit_load": "What is the exit load on {name}?",
    "sip": "What is the minimum SIP amount for {name}?",
    "riskometer": "What is the riskometer of {name}?",
    "benchmark": "What is the benchmark of {name}?",
}


def test_one_question_per_fact_type_times_five_schemes() -> None:
    for scheme_id, name in SCHEMES:
        for fact_type in FACT_TYPES:
            question = FACT_QUESTIONS[fact_type].format(name=name)
            result = retrieve_for_question(question, intent="scheme_fact")
            assert result.status == "hit", question
            assert len(result.chunks) == 1
            chunk = result.chunks[0]
            assert chunk["scheme_id"] == scheme_id
            assert fact_type in chunk["fact_types"]
            assert chunk["source_url"].startswith("https://groww.in/")
            assert chunk["chunk_id"] == f"{scheme_id}--{fact_type}"


def test_large_cap_ter_is_only_large_cap_chunk() -> None:
    result = retrieve_for_question(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        intent="scheme_fact",
    )
    assert result.status == "hit"
    assert [c["chunk_id"] for c in result.chunks] == [f"{LARGE}--expense_ratio"]
    assert result.chunks[0]["text"] == "Expense ratio: 1.03"
    assert result.chunks[0]["source_url"] == LARGE_URL
    assert GOLD not in {c["scheme_id"] for c in result.chunks}
    assert SMALL not in {c["scheme_id"] for c in result.chunks}


def test_mid_and_small_ter_both_075_stay_on_asked_scheme() -> None:
    mid = retrieve_for_question(
        "What is the expense ratio of HDFC Mid Cap Fund Direct Growth?",
        intent="scheme_fact",
    )
    small = retrieve_for_question(
        "What is the expense ratio of HDFC Small Cap Fund Direct Growth?",
        intent="scheme_fact",
    )
    assert mid.chunks[0]["text"] == "Expense ratio: 0.75"
    assert small.chunks[0]["text"] == "Expense ratio: 0.75"
    assert mid.chunks[0]["scheme_id"] == MID
    assert small.chunks[0]["scheme_id"] == SMALL
    assert mid.chunks[0]["chunk_id"] != small.chunks[0]["chunk_id"]


def test_gold_exit_load_is_15_days_not_equity_one_year() -> None:
    gold = retrieve_for_question(
        "What is the exit load on HDFC Gold ETF Fund of Fund Direct Plan Growth?",
        intent="scheme_fact",
    )
    large = retrieve_for_question(
        "What is the exit load on HDFC Large Cap Fund Direct Growth?",
        intent="scheme_fact",
    )
    assert gold.chunks[0]["scheme_id"] == GOLD
    assert gold.chunks[0]["source_url"] == GOLD_URL
    assert "15 days" in gold.chunks[0]["text"]
    assert "1 year" in large.chunks[0]["text"]
    assert large.chunks[0]["scheme_id"] == LARGE


def test_elss_lockin_retrieves_lockin_chunk() -> None:
    result = retrieve_for_question(
        "What is the lock-in period for HDFC ELSS Tax Saver Fund Direct Plan Growth?",
        intent="scheme_fact",
    )
    assert result.status == "hit"
    assert result.chunks[0]["chunk_id"] == f"{ELSS}--lockin"
    assert result.chunks[0]["source_url"] == ELSS_URL
    assert "3 years" in result.chunks[0]["text"]


def test_mid_cap_lockin_does_not_copy_elss() -> None:
    result = retrieve_for_question(
        "What is the lock-in period for HDFC Mid Cap Fund Direct Growth?",
        intent="scheme_fact",
    )
    assert result.status == "not_found"
    assert result.scheme_id == MID
    assert result.chunks == []


def test_unnamed_scheme_fact_clarifies_without_scanning() -> None:
    result = retrieve_for_question("What is the expense ratio?", intent="scheme_fact")
    assert result.status == "clarify"
    assert result.lane == "C"
    assert result.chunks == []


def test_process_capital_gains_is_not_expense_ratio() -> None:
    result = retrieve_for_question(
        "How do I download a capital gains report?",
        intent="process",
    )
    assert result.status == "hit"
    assert all(c["doc_type"] == "process" for c in result.chunks)
    assert result.chunks[0]["chunk_id"] == "groww-capital-gains-report--process"
    assert result.chunks[0]["source_url"] == CG_URL
    assert not any("expense_ratio" in (c.get("fact_types") or []) for c in result.chunks)
    assert not any(str(c.get("chunk_id") or "").endswith("--expense_ratio") for c in result.chunks)


def test_education_what_is_elss_is_not_tax_statement() -> None:
    result = retrieve_for_question("What is ELSS?", intent="scheme_fact")
    assert result.status == "hit"
    assert result.lane == "E"
    assert all(c["doc_type"] == "education" for c in result.chunks)
    ids = [c["chunk_id"] for c in result.chunks]
    assert "groww-elss-tax-statement--process" not in ids
    assert any(cid.endswith("--equity") for cid in ids)
    assert all(c["source_url"] == EDU_URL for c in result.chunks)


def test_education_large_cap_definition_is_not_ter() -> None:
    result = retrieve_for_question("What is a large cap fund", intent="scheme_fact")
    assert result.status == "hit"
    assert result.lane == "E"
    ids = [c["chunk_id"] for c in result.chunks]
    assert f"{LARGE}--expense_ratio" not in ids
    assert any(cid.endswith("--equity") for cid in ids)


def test_citation_urls_are_catalogued() -> None:
    from app.corpus.catalog import load_catalog

    _raw, records = load_catalog()
    allowed = {item.source_url for item in records}
    result = retrieve_for_question(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        intent="scheme_fact",
    )
    assert result.citation_chunk is not None
    assert result.citation_chunk["source_url"] in allowed
