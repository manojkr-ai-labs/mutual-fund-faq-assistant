from __future__ import annotations

from app.corpus.catalog import project_root
from app.pipeline.contract import DISCLAIMER, count_sentences
from app.pipeline.guard import apply_guardrails
from app.pipeline.templates import (
    advisory_refusal,
    comparison_refusal,
    education_source,
    performance_factsheet,
)

EDU_URL = "https://groww.in/p/types-of-mutual-funds"
LARGE_URL = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"


def _assert_contract(response, *, type: str) -> None:
    assert response.type == type
    assert count_sentences(response.text) <= 3
    assert response.citation_url.startswith("https://groww.in/")
    assert response.disclaimer == DISCLAIMER
    assert response.last_updated_from_sources
    lowered = response.text.lower()
    assert "1.03" not in response.text
    assert "0.75" not in response.text
    assert "1.19" not in response.text
    assert "recommend" not in lowered
    assert "should invest" not in lowered
    assert "better than" not in lowered
    assert "outperform" not in lowered


def test_advisory_template_shape() -> None:
    response = advisory_refusal()
    _assert_contract(response, type="refuse")
    assert response.citation_url == EDU_URL
    assert "investment advice" in response.text.lower() or "facts" in response.text.lower()


def test_comparison_template_shape() -> None:
    response = comparison_refusal()
    _assert_contract(response, type="refuse")
    assert response.citation_url == EDU_URL


def test_performance_named_scheme_cites_scheme_page() -> None:
    response = performance_factsheet(
        "What returns did HDFC Large Cap Fund Direct Growth give last year?"
    )
    _assert_contract(response, type="factsheet_only")
    assert response.citation_url == LARGE_URL
    assert "%" not in response.text
    assert "cagr" not in response.text.lower()


def test_performance_unnamed_does_not_guess_large_cap() -> None:
    response = performance_factsheet("How much did NAV grow?")
    _assert_contract(response, type="factsheet_only")
    assert response.citation_url == EDU_URL


def test_education_source_is_types_page() -> None:
    from app.corpus.catalog import load_catalog

    _raw, records = load_catalog()
    assert education_source(records).source_url == EDU_URL


def test_exit_should_i_invest() -> None:
    result = apply_guardrails("Should I invest in HDFC Small Cap Fund?")
    assert result.terminal is True
    assert result.intent == "advisory"
    assert result.response is not None
    _assert_contract(result.response, type="refuse")
    assert result.response.citation_url == EDU_URL
    assert "expense ratio" not in result.response.text.lower()
    assert "0.75" not in result.response.text


def test_exit_which_fund_is_better() -> None:
    result = apply_guardrails("Which fund is better?")
    assert result.terminal is True
    assert result.intent == "comparison"
    assert result.response is not None
    _assert_contract(result.response, type="refuse")


def test_exit_returns_last_year() -> None:
    result = apply_guardrails("What returns did this fund give last year?")
    assert result.terminal is True
    assert result.intent == "performance"
    assert result.response is not None
    _assert_contract(result.response, type="factsheet_only")
    assert "%" not in result.response.text


def test_exit_pii_safety_and_not_persisted() -> None:
    question = "My PAN is ABCDE1234F, what is the TER of HDFC Large Cap?"
    result = apply_guardrails(question)
    assert result.terminal is True
    assert result.intent == "pii"
    assert result.pii is not None
    assert result.response is not None
    _assert_contract(result.response, type="refuse")
    assert "ABCDE1234F" not in result.response.text
    assert "abcde1234f" not in result.response.text.lower()
    data = project_root() / "data"
    for path in data.rglob("*"):
        if path.is_file():
            payload = path.read_text(encoding="utf-8", errors="ignore")
            assert "ABCDE1234F" not in payload


def test_exit_other_amc_oos() -> None:
    result = apply_guardrails("Expense ratio of SBI Bluechip Direct Growth")
    assert result.terminal is True
    assert result.intent == "out_of_scope"
    assert result.response is not None
    _assert_contract(result.response, type="refuse")
    assert "Mid Cap" in result.response.text or "ELSS" in result.response.text


def test_exit_crypto_oos() -> None:
    result = apply_guardrails("What is Bitcoin’s expense ratio?")
    assert result.terminal is True
    assert result.intent == "out_of_scope"


def test_exit_stocks_refuse() -> None:
    result = apply_guardrails("Should I buy Reliance stock?")
    assert result.terminal is True
    assert result.response is not None
    _assert_contract(result.response, type="refuse")


def test_scheme_fact_not_terminal() -> None:
    result = apply_guardrails("What is the expense ratio of HDFC Large Cap Fund Direct Growth?")
    assert result.terminal is False
    assert result.intent == "scheme_fact"
    assert result.response is None


def test_process_not_terminal() -> None:
    result = apply_guardrails("How do I download a capital gains report?")
    assert result.terminal is False
    assert result.intent == "process"


def test_mix_does_not_answer_ter() -> None:
    result = apply_guardrails("What is the TER of HDFC Large Cap and should I buy it?")
    assert result.terminal is True
    assert result.intent == "advisory"
    assert "1.03" not in (result.response.text if result.response else "")


def test_empty_question_error() -> None:
    result = apply_guardrails("  ")
    assert result.terminal is True
    assert result.response is not None
    assert result.response.type == "error"
    assert result.response.citation_url.startswith("https://groww.in/")
