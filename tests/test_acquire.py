from __future__ import annotations

import json
from pathlib import Path

from app.corpus.acquire import acquire_all, run, write_manifest
from app.corpus.catalog import identify_sources


def _groww_scheme(tmp_root: Path, *, html: str = "<html>" + ("x" * 600) + "</html>") -> tuple[list, Path]:
    rel = "data/raw/schemes/hdfc-large-cap-direct-growth.html"
    path = tmp_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    raw = {
        "publisher": "groww",
        "host_allowlist": ["groww.in"],
        "retrieved_on": "2026-08-23",
        "schemes": [
            {
                "scheme_id": "hdfc-large-cap-direct-growth",
                "scheme_name": "HDFC Large Cap Fund — Direct Growth",
                "category": "large-cap",
                "source_url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
                "local_path": rel,
                "publisher": "groww",
                "doc_type": "scheme_page",
                "as_of": "2026-08-21",
                "retrieved_on": "2026-08-23",
            }
        ],
        "education": [],
        "process": [],
    }
    return identify_sources(raw), path


def test_acquire_present_local_snapshot(tmp_path: Path) -> None:
    records, path = _groww_scheme(tmp_path)
    results = acquire_all(records, root=tmp_path, fetch_missing=False)
    assert len(results) == 1
    assert results[0].ok
    assert results[0].status == "present"
    assert results[0].bytes == path.stat().st_size
    assert results[0].source_url.startswith("https://groww.in/")


def test_acquire_missing_without_fetch_is_rejected(tmp_path: Path) -> None:
    records, path = _groww_scheme(tmp_path)
    path.unlink()
    results = acquire_all(records, root=tmp_path, fetch_missing=False)
    assert results[0].status == "rejected"
    assert "missing" in (results[0].error or "").lower()


def test_acquire_rejects_tiny_file(tmp_path: Path) -> None:
    records, _path = _groww_scheme(tmp_path, html="<html></html>")
    results = acquire_all(records, root=tmp_path, fetch_missing=False)
    assert results[0].status == "rejected"
    assert "too small" in (results[0].error or "").lower()


def test_manifest_lists_identified_sources(tmp_path: Path) -> None:
    records, _path = _groww_scheme(tmp_path)
    results = acquire_all(records, root=tmp_path, fetch_missing=False)
    manifest_path = write_manifest(results, root=tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["ok_count"] == 1
    assert payload["publisher"] == "groww"
    assert payload["sources"][0]["source_id"] == "hdfc-large-cap-direct-growth"


def test_acquire_repo_catalog_all_present() -> None:
    records, results, manifest_path = run(fetch_missing=False)
    assert len(records) == 10
    assert all(item.ok for item in results)
    assert all(item.status == "present" for item in results)
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["ok_count"] == 10
    assert payload["rejected_count"] == 0
    urls = {item.source_url for item in results}
    assert all(url.startswith("https://groww.in/") for url in urls)
    assert any("hdfc-gold-etf-fund-of-fund" in url for url in urls)
    assert any("hdfc-elss-tax-saver" in url for url in urls)
