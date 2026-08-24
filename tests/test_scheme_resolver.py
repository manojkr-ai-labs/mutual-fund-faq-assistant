from __future__ import annotations

from app.pipeline.scheme_resolver import resolve_scheme


def test_large_cap_alias() -> None:
    result = resolve_scheme("TER of HDFC large cap")
    assert result.status == "resolved"
    assert result.scheme_id == "hdfc-large-cap-direct-growth"


def test_lrg_cap_misspelling() -> None:
    result = resolve_scheme("HDFC lrg cap fund dir growth TER")
    assert result.scheme_id == "hdfc-large-cap-direct-growth"


def test_gold_fund() -> None:
    result = resolve_scheme("Expense ratio of the gold fund")
    assert result.scheme_id == "hdfc-gold-etf-fof-direct-growth"


def test_elss_tax_saver() -> None:
    result = resolve_scheme("Lock-in of HDFC ELSS Tax Saver Direct")
    assert result.scheme_id == "hdfc-elss-tax-saver-direct-growth"


def test_bare_hdfc_is_ambiguous() -> None:
    result = resolve_scheme("What is the expense ratio of HDFC?")
    assert result.status == "ambiguous"
    assert result.scheme_id is None


def test_the_fund_without_name_is_ambiguous() -> None:
    result = resolve_scheme("What is the expense ratio of the fund?")
    assert result.status == "ambiguous"


def test_unnamed_ter_is_none() -> None:
    result = resolve_scheme("What is the expense ratio?")
    assert result.status == "none"
    assert result.scheme_id is None


def test_two_categories_are_ambiguous() -> None:
    result = resolve_scheme("Expense ratio of mid cap and small cap")
    assert result.status == "ambiguous"
    assert set(result.scheme_ids) == {
        "hdfc-mid-cap-direct-growth",
        "hdfc-small-cap-direct-growth",
    }
