from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.corpus.catalog import CatalogError, load_catalog, project_root
from app.corpus.html_text import normalize_text, strip_non_groww_urls
from app.corpus.parse import parse_html, parse_record, run


def test_strip_non_groww_urls() -> None:
    text = "See SID at https://www.hdfcfund.com/docs/sid.pdf and Groww at https://groww.in/mutual-funds"
    cleaned = strip_non_groww_urls(text)
    assert "hdfcfund.com" not in cleaned
    assert "groww.in" in cleaned


def test_normalize_drops_cta_lines() -> None:
    text = "Expense ratio: 1.03\nDownload the App\nInvest now\nMinimum SIP amount: 100"
    cleaned = normalize_text(text)
    assert "1.03" in cleaned
    assert "Download the App" not in cleaned
    assert "Invest now" not in cleaned


def test_parse_large_cap_scheme_facts() -> None:
    _raw, records = load_catalog()
    record = next(item for item in records if item.scheme_id == "hdfc-large-cap-direct-growth")
    doc = parse_record(record, root=project_root())
    assert doc.publisher == "groww"
    assert doc.source_url.endswith("/hdfc-large-cap-fund-direct-growth")
    assert doc.scheme_id == "hdfc-large-cap-direct-growth"
    assert doc.category == "large-cap"
    assert doc.plan == "direct"
    assert doc.facts["expense_ratio"] == "1.03"
    assert "1%" in (doc.facts["exit_load"] or "")
    assert doc.facts["min_sip_investment"] == 100
    assert doc.facts["riskometer"] == "Very High"
    assert "NIFTY 100" in (doc.facts["benchmark"] or "")
    assert "expense_ratio" in doc.fact_types
    assert "sip" in doc.fact_types
    assert "hdfcfund.com" not in doc.text
    assert "amfiindia.com" not in doc.text
    assert "CAGR" not in doc.text


def test_parse_gold_fof_not_mixed_with_equity() -> None:
    _raw, records = load_catalog()
    gold = parse_record(
        next(item for item in records if item.scheme_id == "hdfc-gold-etf-fof-direct-growth"),
        root=project_root(),
    )
    large = parse_record(
        next(item for item in records if item.scheme_id == "hdfc-large-cap-direct-growth"),
        root=project_root(),
    )
    assert gold.scheme_id != large.scheme_id
    assert gold.category == "gold-etf-fof"
    assert gold.facts["expense_ratio"] == "0.2"
    assert "Gold" in (gold.facts["benchmark"] or "")
    assert gold.source_url != large.source_url


def test_parse_elss_lock_in() -> None:
    _raw, records = load_catalog()
    doc = parse_record(
        next(item for item in records if item.scheme_id == "hdfc-elss-tax-saver-direct-growth"),
        root=project_root(),
    )
    assert doc.facts["lock_in"] == "3 years"
    assert "lockin" in doc.fact_types
    assert "Lock-in: 3 years" in doc.text


def test_parse_education_has_body() -> None:
    _raw, records = load_catalog()
    record = next(item for item in records if item.source_id == "groww-types-of-mutual-funds")
    doc = parse_record(record, root=project_root())
    assert doc.doc_type == "education"
    assert "mutual fund" in doc.text.lower()
    assert doc.source_url.startswith("https://groww.in/")


def test_parse_rejects_non_groww_record() -> None:
    _raw, records = load_catalog()
    record = records[0]
    bad = record.__class__(
        **{
            **record.__dict__,
            "source_url": "https://www.hdfcfund.com/x",
            "publisher": "groww",
        }
    )
    with pytest.raises(CatalogError, match="Groww"):
        parse_html("<html></html>", bad)


def test_run_writes_parsed_json() -> None:
    documents, manifest_path = run()
    assert len(documents) == 10
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["document_count"] == 10
    large = Path("data/processed/parsed/hdfc-large-cap-direct-growth.json")
    assert large.exists()
    data = json.loads(large.read_text(encoding="utf-8"))
    assert data["facts"]["expense_ratio"] == "1.03"
    assert data["source_url"].startswith("https://groww.in/")
