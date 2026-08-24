from __future__ import annotations

from app.pipeline.router import route


def test_advisory_should_i_invest() -> None:
    assert route("Should I invest in HDFC Small Cap Fund?") == "advisory"


def test_advisory_shall_i_buy() -> None:
    assert route("Shall I buy HDFC Large Cap Direct Growth?") == "advisory"


def test_advisory_suitable() -> None:
    assert route("Is HDFC Mid Cap suitable for a 30-year-old?") == "advisory"


def test_advisory_recommend() -> None:
    assert route("Recommend a fund from this list.") == "advisory"


def test_conservative_mix_is_advisory() -> None:
    assert route("What is the TER of HDFC Large Cap and should I buy it?") == "advisory"


def test_comparison_which_is_better() -> None:
    assert route("Which fund is better, large cap or mid cap?") == "comparison"


def test_comparison_vs() -> None:
    assert route("HDFC Small Cap vs HDFC Mid Cap — which should I pick?") == "comparison"


def test_comparison_best_tax() -> None:
    assert route("Best HDFC fund for tax saving?") == "comparison"


def test_comparison_rank() -> None:
    assert route("Rank these five funds.") == "comparison"


def test_performance_last_year() -> None:
    assert route("What returns did HDFC Large Cap Fund Direct Growth give last year?") == "performance"


def test_performance_cagr() -> None:
    assert route("What is the 3Y CAGR of HDFC Mid Cap?") == "performance"


def test_forward_looking_is_advisory() -> None:
    assert route("Will this fund beat the benchmark?") == "advisory"
    assert route("Expected return if I SIP 5000 for 10 years.") == "advisory"


def test_oos_other_amc() -> None:
    assert route("Expense ratio of SBI Bluechip Direct Growth") == "out_of_scope"


def test_oos_stock() -> None:
    assert route("Should I buy Reliance stock?") == "advisory"


def test_oos_crypto() -> None:
    assert route("What is Bitcoin’s expense ratio?") == "out_of_scope"


def test_oos_tax_filing() -> None:
    assert route("File my ITR / save tax beyond stating ELSS lock-in fact") == "out_of_scope"


def test_oos_portfolio() -> None:
    assert route("Build me a 60/40 portfolio") == "out_of_scope"


def test_oos_balanced_advantage() -> None:
    assert route("HDFC Balanced Advantage expense ratio") == "out_of_scope"


def test_process_capital_gains() -> None:
    assert route("How do I download a capital gains report?") == "process"


def test_process_statement() -> None:
    assert route("How do I download my mutual fund statement?") == "process"


def test_scheme_fact_ter() -> None:
    assert route("What is the expense ratio of HDFC Large Cap Fund Direct Growth?") == "scheme_fact"


def test_scheme_fact_lockin() -> None:
    assert route("What is the lock-in period for HDFC ELSS Tax Saver Fund Direct Plan Growth?") == "scheme_fact"


def test_pii_wins_over_ter() -> None:
    assert route("My PAN is ABCDE1234F, what is the TER of HDFC Large Cap?") == "pii"


def test_empty() -> None:
    assert route("   ") == "empty"
