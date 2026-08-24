from __future__ import annotations

from app.pipeline.fact_type import detect_fact_type


def test_expense_ratio() -> None:
    assert detect_fact_type("What is the expense ratio of HDFC Large Cap?") == "expense_ratio"
    assert detect_fact_type("TER of HDFC mid cap") == "expense_ratio"


def test_exit_load() -> None:
    assert detect_fact_type("What is the exit load on HDFC Mid Cap Fund Direct Growth?") == "exit_load"


def test_sip() -> None:
    assert detect_fact_type("What is the minimum SIP amount for HDFC Large Cap?") == "sip"


def test_lockin() -> None:
    assert detect_fact_type("What is the lock-in period for HDFC ELSS Tax Saver?") == "lockin"


def test_lockin_beats_education_elss() -> None:
    assert detect_fact_type("Lock-in of HDFC ELSS") == "lockin"


def test_education_what_is_elss() -> None:
    assert detect_fact_type("What is ELSS?") == "education"


def test_riskometer_not_confused_with_ter() -> None:
    assert detect_fact_type("What is the riskometer of HDFC Large Cap?") == "riskometer"
    assert detect_fact_type("TER of HDFC Large Cap") == "expense_ratio"


def test_education_large_cap_definition() -> None:
    assert detect_fact_type("What is a large cap fund") == "education"



def test_capital_gains() -> None:
    assert detect_fact_type("How do I download a capital gains report?") == "capital_gains"


def test_elss_statement_before_generic_statement() -> None:
    assert detect_fact_type("How to download tax statement for ELSS") == "elss_statement"


def test_account_statement() -> None:
    assert detect_fact_type("How do I download my mutual fund statement?") == "statement"


def test_unknown() -> None:
    assert detect_fact_type("Tell me about HDFC large cap") is None
