from __future__ import annotations

import pytest

from app.corpus.catalog import CatalogError, identify_sources, is_allowlisted_url, load_catalog


def test_allowlisted_groww_https() -> None:
    assert is_allowlisted_url("https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth")
    assert not is_allowlisted_url("http://groww.in/mutual-funds/x")
    assert not is_allowlisted_url("https://www.hdfcfund.com/factsheet.pdf")
    assert not is_allowlisted_url("https://www.amfiindia.com/")
    assert not is_allowlisted_url("https://www.sebi.gov.in/")


def test_identify_rejects_amc_host() -> None:
    raw = {
        "publisher": "groww",
        "host_allowlist": ["groww.in"],
        "schemes": [
            {
                "scheme_id": "bad",
                "source_url": "https://www.hdfcfund.com/large-cap",
                "local_path": "data/raw/schemes/bad.html",
                "publisher": "groww",
                "as_of": "2026-08-21",
                "retrieved_on": "2026-08-23",
            }
        ],
    }
    with pytest.raises(CatalogError, match="Groww"):
        identify_sources(raw)


def test_identify_rejects_non_groww_publisher() -> None:
    raw = {
        "publisher": "hdfc_amc",
        "host_allowlist": ["groww.in"],
        "schemes": [],
        "education": [],
        "process": [],
    }
    with pytest.raises(CatalogError, match="publisher"):
        identify_sources(raw)


def test_identify_rejects_extra_host_in_allowlist() -> None:
    raw = {
        "publisher": "groww",
        "host_allowlist": ["groww.in", "amfiindia.com"],
        "schemes": [
            {
                "scheme_id": "x",
                "source_url": "https://groww.in/mutual-funds/x",
                "local_path": "data/raw/schemes/x.html",
                "publisher": "groww",
                "as_of": "2026-08-21",
                "retrieved_on": "2026-08-23",
            }
        ],
    }
    with pytest.raises(CatalogError, match="non-Groww"):
        identify_sources(raw)


def test_load_real_catalog_identifies_ten_groww_sources() -> None:
    _raw, records = load_catalog()
    assert len(records) == 10
    assert {r.doc_type for r in records} == {"scheme_page", "education", "process"}
    scheme_ids = {r.scheme_id for r in records if r.doc_type == "scheme_page"}
    assert scheme_ids == {
        "hdfc-mid-cap-direct-growth",
        "hdfc-small-cap-direct-growth",
        "hdfc-gold-etf-fof-direct-growth",
        "hdfc-large-cap-direct-growth",
        "hdfc-elss-tax-saver-direct-growth",
    }
    assert all(r.source_url.startswith("https://groww.in/") for r in records)
    assert all(r.publisher == "groww" for r in records)
    gold = next(r for r in records if r.scheme_id == "hdfc-gold-etf-fof-direct-growth")
    elss = next(r for r in records if r.scheme_id == "hdfc-elss-tax-saver-direct-growth")
    assert gold.category == "gold-etf-fof"
    assert elss.category == "elss"
    assert gold.local_path != elss.local_path
