from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.corpus.catalog import CatalogError
from app.corpus.chunk import chunks_path, read_chunks
from app.corpus.refresh import (
    catalog_facts_from_parsed,
    coverage_from_facts,
    fetch_with_retry,
    normalize_lock_in,
    run,
)

MID_CAP_URL = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
LARGE_CAP_URL = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
EDUCATION_URL = "https://groww.in/p/types-of-mutual-funds"
HUB_URL = "https://groww.in/mutual-funds"

MID_CAP_ID = "hdfc-mid-cap-direct-growth"
LARGE_CAP_ID = "hdfc-large-cap-direct-growth"
EDUCATION_ID = "groww-types-of-mutual-funds"
HUB_ID = "groww-mutual-funds-hub"


def _scheme_html(**overrides) -> str:
    mf = {
        "scheme_name": "HDFC Mid Cap Fund — Direct Growth",
        "expense_ratio": "0.75",
        "exit_load": "Exit load of 1% if redeemed within 1 year.",
        "min_sip_investment": 100,
        "return_stats": [{"risk": "Very High"}],
        "benchmark": "NIFTY Midcap 150 TRI",
        "lock_in": {},
        "plan_type": "Direct",
        "scheme_type": "Growth",
        "description": "The scheme seeks long term capital appreciation. " * 8,
    }
    mf.update(overrides)
    payload = {"props": {"pageProps": {"mfServerSideData": mf}}}
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script></body></html>"
    )


def _education_html(body: str = "Mutual funds are pooled investment vehicles. " * 12) -> str:
    payload = {
        "props": {
            "pageProps": {
                "glossaryData": {
                    "title": "Types of Mutual Fund in India",
                    "content": f"<p>{body}</p>",
                    "meta_description": "Learn the categories of mutual funds in India.",
                    "faqs": [],
                }
            }
        }
    }
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script></body></html>"
    )


def _hub_html() -> str:
    # No glossaryData, like https://groww.in/mutual-funds. Padded past the fetch floor.
    return "<html><body><div>Invest now</div>" + ("<!-- listing widget -->" * 40) + "</body></html>"


def _hub_entry() -> dict:
    return {
        "id": HUB_ID,
        "title": "Groww Mutual Funds",
        "url": HUB_URL,
        "local_path": "data/raw/education/mutual-funds-hub.html",
        "publisher": "groww",
        "doc_type": "education",
        "as_of": "2026-08-23",
        "retrieved_on": "2026-08-23",
    }


def _seed_parsed_text(tmp_root: Path, source_id: str, text: str) -> None:
    path = tmp_root / "data" / "processed" / "parsed" / f"{source_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source_id": source_id, "text": text}), encoding="utf-8")


def _scheme_entry(scheme_id: str, url: str, *, name: str, category: str) -> dict:
    return {
        "scheme_id": scheme_id,
        "scheme_name": name,
        "category": category,
        "source_url": url,
        "source_title": f"Groww — {name}",
        "local_path": f"data/raw/schemes/{scheme_id}.html",
        "publisher": "groww",
        "doc_type": "scheme_page",
        "as_of": "2026-08-21",
        "retrieved_on": "2026-08-23",
        "facts": {
            "expense_ratio": "0.75",
            "exit_load": "Exit load of 1% if redeemed within 1 year.",
            "min_sip_investment": 100,
            "riskometer": "Very High",
            "benchmark": "NIFTY Midcap 150 TRI",
            "lock_in": {"years": None, "months": None, "days": None},
        },
        "coverage": {
            "expense_ratio": True,
            "exit_load": True,
            "min_sip": True,
            "riskometer": True,
            "benchmark": True,
            "lock_in": False,
        },
    }


def _education_entry() -> dict:
    return {
        "id": EDUCATION_ID,
        "title": "Types of Mutual Fund in India",
        "url": EDUCATION_URL,
        "local_path": "data/raw/education/types-of-mutual-funds.html",
        "publisher": "groww",
        "doc_type": "education",
        "as_of": "2026-08-23",
        "retrieved_on": "2026-08-23",
    }


def _write_corpus(
    tmp_root: Path,
    *,
    schemes: list[dict] | None = None,
    education: list[dict] | None = None,
    snapshots: dict[str, str] | None = None,
) -> Path:
    schemes = schemes if schemes is not None else [
        _scheme_entry(MID_CAP_ID, MID_CAP_URL, name="HDFC Mid Cap Fund — Direct Growth", category="mid-cap")
    ]
    education = education or []
    raw = {
        "publisher": "groww",
        "host_allowlist": ["groww.in"],
        "retrieved_on": "2026-08-23",
        "schemes": schemes,
        "education": education,
        "process": [],
    }
    catalog_path = tmp_root / "data" / "catalog" / "sources.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    defaults = {entry["local_path"]: _scheme_html() for entry in schemes}
    defaults.update({entry["local_path"]: _education_html() for entry in education})
    for rel, html in (snapshots or defaults).items():
        path = tmp_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    return catalog_path


def _fetcher(pages: dict[str, str]):
    def fetch(url: str) -> str:
        return pages[url]

    return fetch


def _refresh(tmp_root: Path, pages: dict[str, str], **kwargs):
    return run(
        root=tmp_root,
        fetch=_fetcher(pages),
        polite_sleep=0.0,
        attempts=1,
        retry_sleep=0.0,
        **kwargs,
    )


def _catalog(tmp_root: Path) -> dict:
    return json.loads((tmp_root / "data" / "catalog" / "sources.json").read_text(encoding="utf-8"))


def test_refresh_updates_snapshot_catalog_and_chunks(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    fresh = _scheme_html(expense_ratio="0.68")
    report = _refresh(tmp_path, {MID_CAP_URL: fresh}, today="2026-09-01")

    assert report.ok
    assert report.changed
    assert report.updated_ids == [MID_CAP_ID]

    snapshot = (tmp_path / "data" / "raw" / "schemes" / f"{MID_CAP_ID}.html").read_text(encoding="utf-8")
    assert snapshot == fresh

    scheme = _catalog(tmp_path)["schemes"][0]
    assert scheme["as_of"] == "2026-09-01"
    assert scheme["retrieved_on"] == "2026-09-01"
    assert scheme["facts"]["expense_ratio"] == "0.68"
    assert scheme["coverage"]["expense_ratio"] is True

    rows = read_chunks(chunks_path(tmp_path))
    ter = next(row for row in rows if row["chunk_id"] == f"{MID_CAP_ID}--expense_ratio")
    assert "0.68" in ter["text"]
    assert ter["as_of"] == "2026-09-01"
    assert ter["source_url"] == MID_CAP_URL


def test_refresh_reports_which_facts_changed(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    report = _refresh(
        tmp_path,
        {MID_CAP_URL: _scheme_html(expense_ratio="0.68", benchmark="NIFTY Midcap 100 TRI")},
        today="2026-09-01",
    )
    assert report.results[0].changed_facts == ["benchmark", "expense_ratio"]


def test_second_refresh_with_same_content_is_unchanged(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    pages = {MID_CAP_URL: _scheme_html(expense_ratio="0.68")}
    first = _refresh(tmp_path, pages, today="2026-09-01")
    assert first.changed

    second = _refresh(tmp_path, pages, today="2026-09-10")
    assert second.ok
    assert not second.changed
    assert second.results[0].status == "unchanged"

    scheme = _catalog(tmp_path)["schemes"][0]
    assert scheme["as_of"] == "2026-09-01"
    assert scheme["retrieved_on"] == "2026-09-01"


def test_refresh_rejects_page_that_lost_a_declared_fact(tmp_path: Path) -> None:
    catalog_path = _write_corpus(tmp_path)
    before_snapshot = (tmp_path / "data" / "raw" / "schemes" / f"{MID_CAP_ID}.html").read_text(encoding="utf-8")
    before_catalog = catalog_path.read_text(encoding="utf-8")

    report = _refresh(tmp_path, {MID_CAP_URL: _scheme_html(expense_ratio=None)}, today="2026-09-01")

    assert not report.ok
    assert report.results[0].status == "rejected"
    assert "expense_ratio" in (report.results[0].error or "")
    snapshot_path = tmp_path / "data" / "raw" / "schemes" / f"{MID_CAP_ID}.html"
    assert snapshot_path.read_text(encoding="utf-8") == before_snapshot
    assert catalog_path.read_text(encoding="utf-8") == before_catalog


def test_refresh_rejects_bot_block_page(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    blocked = "<html><body>Access denied</body></html>" + ("<!-- pad -->" * 60)
    report = _refresh(tmp_path, {MID_CAP_URL: blocked}, today="2026-09-01")
    assert report.results[0].status == "rejected"
    assert not report.ok


def test_refresh_rejects_truncated_fetch(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    report = _refresh(tmp_path, {MID_CAP_URL: "<html></html>"}, today="2026-09-01")
    assert report.results[0].status == "rejected"
    assert "too small" in (report.results[0].error or "")


def test_refresh_rejects_collapsed_education_page(tmp_path: Path) -> None:
    _write_corpus(tmp_path, education=[_education_entry()])
    first = _refresh(
        tmp_path,
        {MID_CAP_URL: _scheme_html(), EDUCATION_URL: _education_html()},
        today="2026-09-01",
    )
    assert first.ok

    collapsed = _education_html(body="Short. " + ("<!-- pad -->" * 80))
    report = _refresh(
        tmp_path,
        {MID_CAP_URL: _scheme_html(), EDUCATION_URL: collapsed},
        today="2026-09-05",
    )
    failed = next(item for item in report.results if item.source_id == EDUCATION_ID)
    assert failed.status == "rejected"
    assert "collapsed" in (failed.error or "") or "shrank" in (failed.error or "")


def test_page_that_has_always_parsed_to_little_is_not_rejected(tmp_path: Path) -> None:
    # The real catalog carries a hub page with no glossaryData: it parses to just its
    # catalog title (18 chars) and always has. Verification is relative, so a stable
    # near-empty page must survive a refresh rather than blocking the whole run.
    _write_corpus(tmp_path, education=[_hub_entry()])
    _seed_parsed_text(tmp_path, HUB_ID, "Groww Mutual Funds")
    pages = {MID_CAP_URL: _scheme_html(), HUB_URL: _hub_html()}

    report = _refresh(tmp_path, pages, today="2026-09-01")

    assert report.ok
    hub = next(item for item in report.results if item.source_id == HUB_ID)
    assert hub.status == "unchanged"


def test_new_source_must_parse_to_chunkable_text(tmp_path: Path) -> None:
    # With nothing parsed before, there is no baseline to compare against, so the page
    # has to clear the chunker's floor or it would contribute nothing to retrieval.
    _write_corpus(tmp_path, education=[_hub_entry()])
    report = _refresh(
        tmp_path,
        {MID_CAP_URL: _scheme_html(), HUB_URL: _hub_html()},
        today="2026-09-01",
    )
    hub = next(item for item in report.results if item.source_id == HUB_ID)
    assert hub.status == "rejected"
    assert "too little to chunk" in (hub.error or "")


def test_one_bad_source_blocks_the_whole_refresh(tmp_path: Path) -> None:
    schemes = [
        _scheme_entry(MID_CAP_ID, MID_CAP_URL, name="HDFC Mid Cap Fund — Direct Growth", category="mid-cap"),
        _scheme_entry(LARGE_CAP_ID, LARGE_CAP_URL, name="HDFC Large Cap Fund — Direct Growth", category="large-cap"),
    ]
    catalog_path = _write_corpus(tmp_path, schemes=schemes)
    before_catalog = catalog_path.read_text(encoding="utf-8")
    good_path = tmp_path / "data" / "raw" / "schemes" / f"{MID_CAP_ID}.html"
    before_good = good_path.read_text(encoding="utf-8")

    report = _refresh(
        tmp_path,
        {
            MID_CAP_URL: _scheme_html(expense_ratio="0.68"),
            LARGE_CAP_URL: _scheme_html(exit_load=None),
        },
        today="2026-09-01",
    )

    assert not report.ok
    assert good_path.read_text(encoding="utf-8") == before_good
    assert catalog_path.read_text(encoding="utf-8") == before_catalog
    assert report.updated_ids == []


def test_fetch_failure_leaves_corpus_alone(tmp_path: Path) -> None:
    catalog_path = _write_corpus(tmp_path)
    before_catalog = catalog_path.read_text(encoding="utf-8")

    def fetch(url: str) -> str:
        raise OSError("connection reset")

    report = run(
        root=tmp_path,
        fetch=fetch,
        polite_sleep=0.0,
        attempts=1,
        retry_sleep=0.0,
        today="2026-09-01",
    )
    assert not report.ok
    assert report.results[0].status == "error"
    assert catalog_path.read_text(encoding="utf-8") == before_catalog


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    catalog_path = _write_corpus(tmp_path)
    before_catalog = catalog_path.read_text(encoding="utf-8")
    snapshot_path = tmp_path / "data" / "raw" / "schemes" / f"{MID_CAP_ID}.html"
    before_snapshot = snapshot_path.read_text(encoding="utf-8")

    report = _refresh(
        tmp_path,
        {MID_CAP_URL: _scheme_html(expense_ratio="0.68")},
        today="2026-09-01",
        dry_run=True,
    )

    assert report.ok
    assert report.results[0].status == "updated"
    assert report.updated_ids == []
    assert catalog_path.read_text(encoding="utf-8") == before_catalog
    assert snapshot_path.read_text(encoding="utf-8") == before_snapshot
    assert not chunks_path(tmp_path).exists()
    assert not (tmp_path / "data" / "processed" / "refresh-manifest.json").exists()


def test_manifest_records_every_source(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    _refresh(tmp_path, {MID_CAP_URL: _scheme_html(expense_ratio="0.68")}, today="2026-09-01")
    payload = json.loads(
        (tmp_path / "data" / "processed" / "refresh-manifest.json").read_text(encoding="utf-8")
    )
    assert payload["refreshed_on"] == "2026-09-01"
    assert payload["ok"] is True
    assert payload["updated_count"] == 1
    assert payload["sources"][0]["source_id"] == MID_CAP_ID


def test_only_limits_the_refresh_to_one_source(tmp_path: Path) -> None:
    schemes = [
        _scheme_entry(MID_CAP_ID, MID_CAP_URL, name="HDFC Mid Cap Fund — Direct Growth", category="mid-cap"),
        _scheme_entry(LARGE_CAP_ID, LARGE_CAP_URL, name="HDFC Large Cap Fund — Direct Growth", category="large-cap"),
    ]
    _write_corpus(tmp_path, schemes=schemes)
    report = _refresh(
        tmp_path,
        {MID_CAP_URL: _scheme_html(expense_ratio="0.68")},
        today="2026-09-01",
        only=[MID_CAP_ID],
    )
    assert [item.source_id for item in report.results] == [MID_CAP_ID]
    assert report.updated_ids == [MID_CAP_ID]


def test_only_rejects_an_unknown_source_id(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    with pytest.raises(CatalogError, match="unknown source_id"):
        _refresh(tmp_path, {}, today="2026-09-01", only=["not-a-source"])


def test_fetch_with_retry_survives_one_transport_failure() -> None:
    calls: list[str] = []

    def fetch(url: str) -> str:
        calls.append(url)
        if len(calls) == 1:
            raise OSError("timed out")
        return "<html>ok</html>"

    html = fetch_with_retry(MID_CAP_URL, attempts=2, sleep_seconds=0.0, fetch=fetch)
    assert html == "<html>ok</html>"
    assert len(calls) == 2


def test_fetch_with_retry_does_not_retry_a_disallowed_host() -> None:
    calls: list[str] = []

    def fetch(url: str) -> str:
        calls.append(url)
        raise CatalogError("refusing to fetch non-Groww URL")

    with pytest.raises(CatalogError):
        fetch_with_retry("https://example.com/x", attempts=3, sleep_seconds=0.0, fetch=fetch)
    assert len(calls) == 1


def test_normalize_lock_in_treats_zero_and_null_alike() -> None:
    assert normalize_lock_in({"years": 3, "months": 0, "days": 0}) == normalize_lock_in(
        {"years": 3, "months": None, "days": None}
    )
    assert normalize_lock_in({}) == {"years": None, "months": None, "days": None}


def test_elss_lock_in_survives_the_round_trip(tmp_path: Path) -> None:
    entry = _scheme_entry(MID_CAP_ID, MID_CAP_URL, name="HDFC ELSS Tax Saver", category="elss")
    entry["facts"]["lock_in"] = {"years": 3, "months": 0, "days": 0}
    entry["coverage"]["lock_in"] = True
    _write_corpus(tmp_path, schemes=[entry])

    report = _refresh(
        tmp_path,
        {MID_CAP_URL: _scheme_html(lock_in={"years": 3, "months": 0, "days": 0})},
        today="2026-09-01",
    )
    assert report.ok
    assert "lock_in" not in report.results[0].changed_facts

    dropped = _refresh(
        tmp_path,
        {MID_CAP_URL: _scheme_html(lock_in={})},
        today="2026-09-02",
    )
    assert not dropped.ok
    assert "lock_in" in (dropped.results[0].error or "")


def test_ingest_refresh_flag_forwards_remaining_args(monkeypatch) -> None:
    seen: dict[str, list[str] | None] = {"argv": None}

    def fake_refresh(argv: list[str] | None = None) -> int:
        seen["argv"] = argv
        return 0

    monkeypatch.setattr("app.corpus.ingest.refresh_main", fake_refresh)
    from app.corpus.ingest import main as ingest_main

    assert ingest_main(["--refresh", "--dry-run", "--only", MID_CAP_ID]) == 0
    assert seen["argv"] == ["--dry-run", "--only", MID_CAP_ID]


def test_coverage_from_parsed_facts_matches_catalog_shape() -> None:
    from app.corpus.catalog import identify_sources

    raw = {
        "publisher": "groww",
        "host_allowlist": ["groww.in"],
        "schemes": [_scheme_entry(MID_CAP_ID, MID_CAP_URL, name="HDFC Mid Cap", category="mid-cap")],
    }
    record = identify_sources(raw)[0]
    from app.corpus.parse import parse_html

    document = parse_html(_scheme_html(), record)
    coverage = coverage_from_facts(catalog_facts_from_parsed(document))
    assert coverage == {
        "expense_ratio": True,
        "exit_load": True,
        "min_sip": True,
        "riskometer": True,
        "benchmark": True,
        "lock_in": False,
    }
