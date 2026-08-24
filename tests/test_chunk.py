from __future__ import annotations

import json

import pytest

from app.corpus.catalog import CatalogError, load_catalog, project_root
from app.corpus.chunk import (
    SKIP_TEXT_CHARS,
    approx_tokens,
    chunk_all,
    chunk_document,
    pack_education_block,
    read_chunks,
    run,
    split_education_text,
    strip_process_chrome,
)
from app.corpus.parse import run as parse_run

GOLD_URL = "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth"
LARGE_URL = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
GLOSSARY_URL = "https://groww.in/p/types-of-mutual-funds"

SCHEME_IDS = (
    "hdfc-mid-cap-direct-growth",
    "hdfc-small-cap-direct-growth",
    "hdfc-gold-etf-fof-direct-growth",
    "hdfc-large-cap-direct-growth",
    "hdfc-elss-tax-saver-direct-growth",
)


def _load_parsed(source_id: str) -> dict:
    path = project_root() / "data" / "processed" / "parsed" / f"{source_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _allowed() -> set[str]:
    _raw, records = load_catalog()
    return {record.source_url for record in records}


@pytest.fixture(scope="module")
def chunks() -> list[dict]:
    produced, path = run()
    assert path.name == "chunks.jsonl"
    disk = read_chunks(path)
    assert len(disk) == len(produced)
    return disk


def test_scheme_chunks_match_parsed_sections(chunks: list[dict]) -> None:
    for scheme_id in SCHEME_IDS:
        parsed = _load_parsed(scheme_id)
        scheme_chunks = [c for c in chunks if c["scheme_id"] == scheme_id]
        sections = parsed["sections"]
        assert len(scheme_chunks) == len(sections)
        assert len(scheme_chunks) == len({c["chunk_id"] for c in scheme_chunks})
        by_id = {c["chunk_id"]: c for c in scheme_chunks}
        for section in sections:
            fact_types = section["fact_types"]
            slug = fact_types[0] if fact_types else "objective"
            chunk = by_id[f"{scheme_id}--{slug}"]
            assert chunk["text"] == section["text"]
            assert chunk["fact_types"] == fact_types
            assert chunk["doc_type"] == "scheme_page"
            assert chunk["plan"] == "direct"
            assert chunk["option"] == "growth"
            assert chunk["publisher"] == "groww"
            assert chunk["source_url"] == parsed["source_url"]
            assert chunk["source_title"] == parsed["title"]
            assert chunk["as_of"] == parsed["as_of"]
            assert chunk["retrieved_on"] == parsed["retrieved_on"]


def test_ter_chunk_does_not_include_exit_load_or_sip(chunks: list[dict]) -> None:
    ter = next(c for c in chunks if c["chunk_id"] == "hdfc-large-cap-direct-growth--expense_ratio")
    assert ter["text"] == "Expense ratio: 1.03"
    lower = ter["text"].lower()
    assert "exit load" not in lower
    assert "sip" not in lower
    assert ter["fact_types"] == ["expense_ratio"]


def test_elss_has_lockin_others_do_not(chunks: list[dict]) -> None:
    lockin = [c for c in chunks if c["chunk_id"].endswith("--lockin")]
    assert len(lockin) == 1
    assert lockin[0]["scheme_id"] == "hdfc-elss-tax-saver-direct-growth"
    assert lockin[0]["text"] == "Lock-in: 3 years"
    assert lockin[0]["fact_types"] == ["lockin"]
    for scheme_id in SCHEME_IDS:
        if scheme_id == "hdfc-elss-tax-saver-direct-growth":
            continue
        assert not any(c["scheme_id"] == scheme_id and "lockin" in c["fact_types"] for c in chunks)


def test_gold_fof_chunks_stay_on_gold_url(chunks: list[dict]) -> None:
    gold = [c for c in chunks if c["scheme_id"] == "hdfc-gold-etf-fof-direct-growth"]
    assert gold
    assert all(c["source_url"] == GOLD_URL for c in gold)
    assert all(c["category"] == "gold-etf-fof" for c in gold)
    assert all(c["chunk_id"].startswith("hdfc-gold-etf-fof-direct-growth--") for c in gold)
    large_ter = next(c for c in chunks if c["chunk_id"] == "hdfc-large-cap-direct-growth--expense_ratio")
    assert large_ter["source_url"] == LARGE_URL
    assert GOLD_URL not in large_ter["source_url"]
    assert large_ter["scheme_id"] != "hdfc-gold-etf-fof-direct-growth"


def test_process_chunks_have_null_scheme_id(chunks: list[dict]) -> None:
    process = [c for c in chunks if c["doc_type"] == "process"]
    assert len(process) == 3
    ids = {c["chunk_id"] for c in process}
    assert ids == {
        "groww-capital-gains-report--process",
        "groww-transaction-history--process",
        "groww-elss-tax-statement--process",
    }
    for chunk in process:
        assert chunk["scheme_id"] is None
        assert "process" in chunk["fact_types"]
        assert chunk["source_url"].startswith("https://groww.in/help/")
    cg = next(c for c in process if c["chunk_id"].startswith("groww-capital-gains-report"))
    assert "groww.in/help" in cg["text"]
    hist = next(c for c in process if "transaction-history" in c["chunk_id"])
    assert "PAN" in hist["text"]


def test_hub_education_is_skipped(chunks: list[dict]) -> None:
    assert not any("mutual-funds-hub" in c["chunk_id"] for c in chunks)
    assert not any(c["source_url"].rstrip("/") == "https://groww.in/mutual-funds" for c in chunks)


def test_glossary_is_heading_split_not_mega_chunk(chunks: list[dict]) -> None:
    edu = [c for c in chunks if c["doc_type"] == "education"]
    assert 8 <= len(edu) <= 12
    slugs = {c["chunk_id"].split("--", 1)[1] for c in edu}
    assert any(s == "intro" or s.startswith("intro-") for s in slugs)
    assert any(s == "equity" or s.startswith("equity-") for s in slugs)
    assert any(s == "debt" or s.startswith("debt-") for s in slugs)
    assert any(s == "other" or s.startswith("other-") for s in slugs)
    other = next(c for c in edu if c["chunk_id"].endswith("--other") or "--other-" in c["chunk_id"])
    assert "Index Funds" in other["text"] or "FoF" in other["text"]
    assert "Overnight Funds" not in other["text"]
    joined = "\n".join(c["text"] for c in edu)
    assert "Axis Mutual Fund" not in joined
    assert "Mirae Asset Mutual Fund" not in joined
    assert "What type of mutual fund is best?" not in joined
    assert "Which type of mutual fund is safest?" not in joined
    assert "Which mutual fund is good for 5 years?" not in joined
    assert "How do I start a mutual fund?" not in joined
    assert "How many types of funds are there?" in joined
    assert all(c["scheme_id"] is None for c in edu)
    assert all(c["fact_types"] == ["education"] for c in edu)
    assert all(c["source_url"] == GLOSSARY_URL for c in edu)
    assert all(approx_tokens(c["text"]) <= 800 for c in edu)


def test_every_chunk_url_is_catalogued_groww(chunks: list[dict]) -> None:
    allowed = _allowed()
    assert chunks
    for chunk in chunks:
        assert chunk["source_url"].startswith("https://groww.in/")
        assert chunk["source_url"] in allowed
        assert chunk["publisher"] == "groww"
        assert "hdfcfund.com" not in chunk["text"]
        assert "amfiindia.com" not in chunk["text"]


def test_expected_chunk_count(chunks: list[dict]) -> None:
    scheme = [c for c in chunks if c["doc_type"] == "scheme_page"]
    process = [c for c in chunks if c["doc_type"] == "process"]
    education = [c for c in chunks if c["doc_type"] == "education"]
    assert len(scheme) == 31
    assert len(process) == 3
    assert 8 <= len(education) <= 12
    assert 42 <= len(chunks) <= 46


def test_skip_floor_drops_hub_without_catalog_hit() -> None:
    doc = {
        "source_id": "groww-mutual-funds-hub",
        "doc_type": "education",
        "publisher": "groww",
        "source_url": "https://groww.in/mutual-funds",
        "title": "Groww Mutual Funds",
        "scheme_id": None,
        "fact_types": ["education"],
        "sections": [{"heading": "Education", "fact_types": ["education"], "text": "Groww Mutual Funds"}],
        "text": "Groww Mutual Funds",
        "as_of": "2026-08-23",
        "retrieved_on": "2026-08-23",
    }
    assert len(doc["text"]) < SKIP_TEXT_CHARS
    assert chunk_document(doc, allowed_urls=_allowed(), text_chars=18) == []


def test_split_education_uses_hyphen_body_markers_not_toc() -> None:
    text = (
        "Intro paragraph about mutual funds.\n\n"
        "Schemes Based on the Maturity Period\n\nOpen Ended Funds live here.\n\n"
        "Based on Principal Investments\n\n"
        "Equity Schemes\n\nDebt Schemes\n\nHybrid Schemes\n\n"
        "Solution Oriented Schemes\n\nOther Schemes\n\n"
        "- Equity Schemes\n\nSEBI has decided total 11 categories under Equity Schemes.\n\n"
        "- Debt Schemes\n\nSEBI has decided total 16 categories under Debt Schemes.\n\n"
        "- Hybrid Schemes\n\nHybrid body.\n\n"
        "- Solution Oriented Schemes\n\nRetirement Fund lock-in.\n\n"
        "- Other Schemes\n\nIndex Funds/ ETFs and FoFs only.\n\n"
        "Asset Management Company\n\nAxis Mutual Fund\n\nMirae Asset Mutual Fund\n\n"
        "What type of mutual fund is best?\nThe best type is whatever grows fastest.\n\n"
        "How many types of funds are there?\nThere are four main categories.\n\n"
        "How do I start a mutual fund?\nStart with risk profiling.\n\n"
        "Which type of mutual fund is safest?\nThe safest funds have minimal risks.\n\n"
        "Which mutual fund is good for 5 years?\nThe best kind provide higher returns.\n"
    )
    blocks = dict(split_education_text(text))
    assert "Axis Mutual Fund" not in "".join(blocks.values())
    assert "best type" not in "".join(blocks.values()).lower()
    assert blocks["equity"].startswith("- Equity Schemes")
    assert "11 categories" in blocks["equity"]
    assert "16 categories" not in blocks["equity"]
    assert "16 categories" in blocks["debt"]
    assert "Index Funds" in blocks["other"]
    assert "11 categories" not in blocks["other"]
    assert "How many types of funds are there?" in blocks["faq-how-many-types"]
    assert "What type of mutual fund is best?" not in blocks


def test_pack_education_splits_over_token_cap() -> None:
    para = "word " * 50
    block = "\n\n".join(para for _ in range(20))
    assert approx_tokens(block) > 800
    parts = pack_education_block(block)
    assert len(parts) >= 2
    assert all(approx_tokens(p) <= 800 for p in parts)


def test_process_chrome_strip_keeps_pan_note() -> None:
    text = (
        "Where can I get the transaction history\n\n"
        "Groww help page: https://groww.in/help/x\n\n"
        "Customer Support\n\nHelp and Support\n\n"
        "Note: The password to open the report is your PAN number in capital letters.\n\n"
        "REPORTS\n\nCONTACT US"
    )
    cleaned = strip_process_chrome(text)
    assert "Customer Support" not in cleaned
    assert "REPORTS" not in cleaned
    assert "PAN number" in cleaned
    assert "groww.in/help/x" in cleaned


def test_rejects_non_groww_url() -> None:
    doc = {
        "source_id": "bad",
        "doc_type": "process",
        "publisher": "groww",
        "source_url": "https://www.hdfcfund.com/x",
        "title": "bad",
        "scheme_id": None,
        "fact_types": ["process"],
        "sections": [{"heading": "Process", "fact_types": ["process"], "text": "hello " * 20}],
        "text": "hello " * 20,
        "as_of": "2026-08-23",
        "retrieved_on": "2026-08-23",
    }
    with pytest.raises(CatalogError, match="Groww"):
        chunk_document(doc, allowed_urls={"https://www.hdfcfund.com/x"}, text_chars=200)


def test_chunk_all_skips_short_and_keeps_scheme() -> None:
    allowed = {LARGE_URL, GLOSSARY_URL}
    scheme = _load_parsed("hdfc-large-cap-direct-growth")
    hub = {
        "source_id": "groww-mutual-funds-hub",
        "doc_type": "education",
        "publisher": "groww",
        "source_url": GLOSSARY_URL,
        "title": "Groww Mutual Funds",
        "text": "Groww Mutual Funds",
        "sections": [],
        "as_of": "2026-08-23",
        "retrieved_on": "2026-08-23",
    }
    out = chunk_all([(scheme, len(scheme["text"])), (hub, 18)], allowed_urls=allowed)
    assert all(c.scheme_id == "hdfc-large-cap-direct-growth" for c in out)
    assert len(out) == len(scheme["sections"])


def test_parse_then_chunk_roundtrip() -> None:
    documents, _manifest = parse_run()
    assert len(documents) == 10
    produced, path = run()
    assert path.is_file()
    assert any(c.chunk_id == "hdfc-large-cap-direct-growth--expense_ratio" for c in produced)
