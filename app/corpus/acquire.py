"""Phase 2.1: identify catalogued Groww sources and acquire/verify local HTML.

Batch only — not called per user question. Never fetches non-groww.in hosts.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from app.corpus.catalog import (
    ALLOWED_HOSTS,
    CatalogError,
    SourceRecord,
    identify_sources,
    is_allowlisted_url,
    load_catalog,
    project_root,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
MIN_HTML_BYTES = 500


@dataclass
class AcquisitionResult:
    source_id: str
    doc_type: str
    scheme_id: str | None
    source_url: str
    local_path: str
    as_of: str
    retrieved_on: str
    bytes: int
    status: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in {"present", "fetched"} and self.error is None


def fetch_groww_html(url: str) -> str:
    if not is_allowlisted_url(url, ALLOWED_HOSTS):
        raise CatalogError(f"refusing to fetch non-Groww URL: {url}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=45, context=context) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return response.read().decode("utf-8", "replace")


def acquire_record(
    record: SourceRecord,
    *,
    root: Path,
    fetch_missing: bool = False,
) -> AcquisitionResult:
    path = record.absolute_path(root)
    raw_root = (root / "data" / "raw").resolve()
    try:
        if not path.is_relative_to(raw_root):
            raise CatalogError(f"acquired file must live under data/raw/: {record.local_path}")
        if path.exists():
            size = path.stat().st_size
            if size < MIN_HTML_BYTES:
                raise CatalogError(f"snapshot too small ({size} bytes): {record.local_path}")
            return AcquisitionResult(
                source_id=record.source_id,
                doc_type=record.doc_type,
                scheme_id=record.scheme_id,
                source_url=record.source_url,
                local_path=record.local_path,
                as_of=record.as_of,
                retrieved_on=record.retrieved_on,
                bytes=size,
                status="present",
            )
        if not fetch_missing:
            raise CatalogError(f"snapshot missing (run with --fetch-missing): {record.local_path}")
        html = fetch_groww_html(record.source_url)
        if len(html.encode("utf-8")) < MIN_HTML_BYTES:
            raise CatalogError(f"fetched HTML too small for {record.source_url}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return AcquisitionResult(
            source_id=record.source_id,
            doc_type=record.doc_type,
            scheme_id=record.scheme_id,
            source_url=record.source_url,
            local_path=record.local_path,
            as_of=record.as_of,
            retrieved_on=record.retrieved_on or date.today().isoformat(),
            bytes=path.stat().st_size,
            status="fetched",
        )
    except (CatalogError, OSError, RuntimeError) as exc:
        return AcquisitionResult(
            source_id=record.source_id,
            doc_type=record.doc_type,
            scheme_id=record.scheme_id,
            source_url=record.source_url,
            local_path=record.local_path,
            as_of=record.as_of,
            retrieved_on=record.retrieved_on,
            bytes=path.stat().st_size if path.exists() else 0,
            status="rejected",
            error=str(exc),
        )


def acquire_all(
    records: list[SourceRecord],
    *,
    root: Path,
    fetch_missing: bool = False,
) -> list[AcquisitionResult]:
    return [acquire_record(record, root=root, fetch_missing=fetch_missing) for record in records]


def write_manifest(
    results: list[AcquisitionResult],
    *,
    root: Path,
    path: Path | None = None,
) -> Path:
    manifest_path = path or (root / "data" / "processed" / "acquisition-manifest.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    ok = [r for r in results if r.ok]
    rejected = [r for r in results if not r.ok]
    payload = {
        "acquired_on": date.today().isoformat(),
        "publisher": "groww",
        "host_allowlist": sorted(ALLOWED_HOSTS),
        "source_count": len(results),
        "ok_count": len(ok),
        "rejected_count": len(rejected),
        "ok": not rejected,
        "sources": [asdict(r) for r in results],
        "rejected": [asdict(r) for r in rejected],
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path


def run(
    *,
    root: Path | None = None,
    catalog_path: Path | None = None,
    fetch_missing: bool = False,
) -> tuple[list[SourceRecord], list[AcquisitionResult], Path]:
    root = root or project_root()
    _raw, records = load_catalog(catalog_path, root=root)
    results = acquire_all(records, root=root, fetch_missing=fetch_missing)
    manifest_path = write_manifest(results, root=root)
    return records, results, manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2.1: identify Groww catalog sources and verify/acquire local HTML.",
    )
    parser.add_argument(
        "--fetch-missing",
        action="store_true",
        help="Download missing snapshots from groww.in only (batch; not per question).",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Override path to data/catalog/sources.json",
    )
    args = parser.parse_args(argv)

    try:
        records, results, manifest_path = run(catalog_path=args.catalog, fetch_missing=args.fetch_missing)
    except (CatalogError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"acquisition failed: {exc}", file=sys.stderr)
        return 1

    print(f"identified {len(records)} catalogued Groww sources")
    for result in results:
        flag = "ok" if result.ok else "REJECT"
        extra = f" error={result.error}" if result.error else ""
        print(
            f"  [{flag}] {result.doc_type:12} {result.source_id:42} "
            f"{result.status:8} {result.bytes:8} B  {result.source_url}{extra}"
        )
    print(f"wrote {manifest_path}")
    if any(not r.ok for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
