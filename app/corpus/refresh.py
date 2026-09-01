"""Scheduled re-ingest: re-fetch Groww snapshots, verify them, then parse and chunk.

Batch only — never called per user question, and never fetches a non-groww.in host.
Unlike Phase 2.1 acquire, which leaves an existing snapshot alone, this re-fetches
every catalogued source. Every source is fetched and verified before anything is
written, so a bot-block page or a Groww markup change cannot leave the corpus
half-replaced. A snapshot is rewritten only when its *parsed* content changed, so
HTML churn (session ids, A/B markup) does not produce a daily diff.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.corpus import chunk as chunk_stage
from app.corpus import parse as parse_stage
from app.corpus.acquire import MIN_HTML_BYTES, fetch_groww_html
from app.corpus.catalog import (
    CatalogError,
    SourceRecord,
    default_catalog_path,
    load_catalog,
    project_root,
)
from app.corpus.parse import ParsedDocument, parse_html

# Below the chunker's own floor a page yields no chunks, so it is worthless to retrieval.
# Some catalogued help/hub pages already parse to very little, so the real test is
# relative: a page must not lose ground against the text it parsed to last time.
MIN_CHUNKABLE_CHARS = chunk_stage.SKIP_TEXT_CHARS
# Reject a page that keeps less than this share of the text it had before.
MIN_TEXT_RATIO = 0.5

FETCH_ATTEMPTS = 2
RETRY_SLEEP_SECONDS = 5.0
POLITE_SLEEP_SECONDS = 1.0

# Fact keys mirrored into sources.json for each scheme.
CATALOG_FACT_KEYS = (
    "expense_ratio",
    "exit_load",
    "min_sip_investment",
    "riskometer",
    "benchmark",
    "lock_in",
)
LOCK_IN_UNITS = ("years", "months", "days")


@dataclass
class RefreshResult:
    source_id: str
    doc_type: str
    scheme_id: str | None
    source_url: str
    local_path: str
    status: str = "error"  # updated | unchanged | rejected | error
    fetched_bytes: int = 0
    changed_facts: list[str] = field(default_factory=list)
    error: str | None = None
    html: str | None = None
    facts: dict | None = None

    @property
    def ok(self) -> bool:
        return self.status in {"updated", "unchanged"}


@dataclass
class RefreshReport:
    results: list[RefreshResult]
    today: str
    dry_run: bool
    updated_ids: list[str] = field(default_factory=list)
    manifest_path: Path | None = None
    chunk_count: int | None = None

    @property
    def failed(self) -> list[RefreshResult]:
        return [item for item in self.results if not item.ok]

    @property
    def ok(self) -> bool:
        return not self.failed

    @property
    def changed(self) -> bool:
        return bool(self.updated_ids)


def catalog_entries(raw: dict) -> dict[str, dict]:
    """Map source_id to the live catalog dict so updates can be written back in place."""
    entries: dict[str, dict] = {}
    for scheme in raw.get("schemes") or []:
        entries[scheme["scheme_id"]] = scheme
    for section in ("education", "process"):
        for page in raw.get(section) or []:
            entries[page["id"]] = page
    return entries


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def normalize_lock_in(value) -> dict:
    """Put both catalog and parsed lock-in through one shape so 0 and null do not differ."""
    raw = value if isinstance(value, dict) else {}
    normalized: dict = {}
    for unit in LOCK_IN_UNITS:
        amount = raw.get(unit)
        normalized[unit] = None if amount in (None, "", 0) else int(amount)
    return normalized


def lock_in_present(value) -> bool:
    return any(amount is not None for amount in normalize_lock_in(value).values())


def catalog_facts(entry: dict) -> dict:
    stored = entry.get("facts") or {}
    facts = {key: stored.get(key) for key in CATALOG_FACT_KEYS}
    facts["lock_in"] = normalize_lock_in(stored.get("lock_in"))
    return facts


def catalog_facts_from_parsed(document: ParsedDocument) -> dict:
    """Project parsed scheme facts onto the subset sources.json mirrors."""
    parsed = document.facts or {}
    return {
        "expense_ratio": parsed.get("expense_ratio"),
        "exit_load": parsed.get("exit_load"),
        "min_sip_investment": parsed.get("min_sip_investment"),
        "riskometer": parsed.get("riskometer"),
        "benchmark": parsed.get("benchmark"),
        "lock_in": normalize_lock_in(parsed.get("lock_in_raw")),
    }


def coverage_from_facts(facts: dict) -> dict:
    return {
        "expense_ratio": _present(facts.get("expense_ratio")),
        "exit_load": _present(facts.get("exit_load")),
        "min_sip": _present(facts.get("min_sip_investment")),
        "riskometer": _present(facts.get("riskometer")),
        "benchmark": _present(facts.get("benchmark")),
        "lock_in": lock_in_present(facts.get("lock_in")),
    }


def previous_parsed_text(source_id: str, *, root: Path) -> str | None:
    path = root / "data" / "processed" / "parsed" / f"{source_id}.json"
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return document.get("text") or ""


def verify_document(
    document: ParsedDocument,
    *,
    entry: dict,
    previous_text: str | None,
) -> str | None:
    """Return why a refreshed page is unusable, or None when it may replace the snapshot."""
    if document.doc_type == "scheme_page":
        declared = entry.get("coverage") or {}
        if declared:
            actual = coverage_from_facts(catalog_facts_from_parsed(document))
            lost = sorted(name for name, had in declared.items() if had and not actual.get(name))
            if lost:
                return "lost facts that sources.json says this page carries: " + ", ".join(lost)
            return None
        if not document.sections:
            return "no fact sections parsed from the refreshed page"
        return None

    length = len(document.text)
    if previous_text is None:
        if length < MIN_CHUNKABLE_CHARS:
            return f"parsed text is only {length} chars, too little to chunk (minimum {MIN_CHUNKABLE_CHARS})"
        return None
    previous_length = len(previous_text)
    if previous_length >= MIN_CHUNKABLE_CHARS and length < MIN_CHUNKABLE_CHARS:
        return (
            f"parsed text fell to {length} chars from {previous_length}, below the "
            f"{MIN_CHUNKABLE_CHARS}-char chunking floor"
        )
    if previous_length and length < MIN_TEXT_RATIO * previous_length:
        kept = int(MIN_TEXT_RATIO * 100)
        return (
            f"parsed text shrank to {length} chars from {previous_length} "
            f"(must keep at least {kept}%)"
        )
    return None


def fetch_with_retry(
    url: str,
    *,
    attempts: int = FETCH_ATTEMPTS,
    sleep_seconds: float = RETRY_SLEEP_SECONDS,
    fetch=fetch_groww_html,
) -> str:
    """Retry transport failures only. A disallowed host raises CatalogError immediately."""
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fetch(url)
        except (OSError, RuntimeError) as exc:
            last = exc
            if attempt < attempts and sleep_seconds:
                time.sleep(sleep_seconds)
    raise RuntimeError(f"fetch failed after {attempts} attempt(s): {last}")


def refresh_record(
    record: SourceRecord,
    *,
    root: Path,
    entry: dict,
    fetch=fetch_groww_html,
    attempts: int = FETCH_ATTEMPTS,
    retry_sleep: float = RETRY_SLEEP_SECONDS,
) -> RefreshResult:
    """Fetch and verify one source. Writes nothing; the caller commits."""
    result = RefreshResult(
        source_id=record.source_id,
        doc_type=record.doc_type,
        scheme_id=record.scheme_id,
        source_url=record.source_url,
        local_path=record.local_path,
    )
    path = record.absolute_path(root)
    raw_root = (root / "data" / "raw").resolve()
    try:
        if not path.is_relative_to(raw_root):
            raise CatalogError(f"snapshot must live under data/raw/: {record.local_path}")
        try:
            html = fetch_with_retry(
                record.source_url,
                attempts=attempts,
                sleep_seconds=retry_sleep,
                fetch=fetch,
            )
        except (OSError, RuntimeError) as exc:
            result.status = "error"
            result.error = str(exc)
            return result

        result.fetched_bytes = len(html.encode("utf-8"))
        if result.fetched_bytes < MIN_HTML_BYTES:
            raise CatalogError(
                f"fetched HTML too small ({result.fetched_bytes} bytes, minimum {MIN_HTML_BYTES})"
            )

        document = parse_html(html, record)
        previous_text = previous_parsed_text(record.source_id, root=root)
        problem = verify_document(document, entry=entry, previous_text=previous_text)
        if problem:
            raise CatalogError(problem)

        if record.doc_type == "scheme_page":
            facts = catalog_facts_from_parsed(document)
            before = catalog_facts(entry)
            result.facts = facts
            result.changed_facts = sorted(
                key for key in CATALOG_FACT_KEYS if before.get(key) != facts.get(key)
            )

        text_changed = previous_text is None or document.text != previous_text
        if result.changed_facts or text_changed:
            result.status = "updated"
            result.html = html
        else:
            result.status = "unchanged"
        return result
    except CatalogError as exc:
        result.status = "rejected"
        result.error = str(exc)
        return result
    except OSError as exc:
        result.status = "error"
        result.error = str(exc)
        return result


def plan_refresh(
    records: list[SourceRecord],
    *,
    root: Path,
    entries: dict[str, dict],
    fetch=fetch_groww_html,
    polite_sleep: float = POLITE_SLEEP_SECONDS,
    attempts: int = FETCH_ATTEMPTS,
    retry_sleep: float = RETRY_SLEEP_SECONDS,
) -> list[RefreshResult]:
    results: list[RefreshResult] = []
    for index, record in enumerate(records):
        if index and polite_sleep:
            time.sleep(polite_sleep)
        results.append(
            refresh_record(
                record,
                root=root,
                entry=entries.get(record.source_id) or {},
                fetch=fetch,
                attempts=attempts,
                retry_sleep=retry_sleep,
            )
        )
    return results


def apply_catalog_updates(
    raw: dict,
    entries: dict[str, dict],
    results: list[RefreshResult],
    *,
    today: str,
) -> list[str]:
    """Bump dates and mirrored facts for refreshed sources. Mutates the catalog dict."""
    updated: list[str] = []
    for result in results:
        if result.status != "updated":
            continue
        entry = entries.get(result.source_id)
        if entry is None:
            continue
        entry["as_of"] = today
        entry["retrieved_on"] = today
        if result.facts is not None:
            entry["facts"] = result.facts
            entry["coverage"] = coverage_from_facts(result.facts)
        updated.append(result.source_id)
    if updated:
        raw["retrieved_on"] = today
    return updated


def write_catalog(raw: dict, path: Path) -> Path:
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_snapshots(results: list[RefreshResult], *, root: Path) -> list[Path]:
    written: list[Path] = []
    for result in results:
        if result.status != "updated" or result.html is None:
            continue
        path = (root / result.local_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.html, encoding="utf-8")
        written.append(path)
    return written


def write_manifest(
    results: list[RefreshResult],
    *,
    root: Path,
    today: str,
    path: Path | None = None,
) -> Path:
    manifest_path = path or (root / "data" / "processed" / "refresh-manifest.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "refreshed_on": today,
        "publisher": "groww",
        "source_count": len(results),
        "updated_count": sum(1 for item in results if item.status == "updated"),
        "unchanged_count": sum(1 for item in results if item.status == "unchanged"),
        "failed_count": sum(1 for item in results if not item.ok),
        "ok": all(item.ok for item in results),
        "sources": [
            {
                "source_id": item.source_id,
                "doc_type": item.doc_type,
                "scheme_id": item.scheme_id,
                "source_url": item.source_url,
                "local_path": item.local_path,
                "status": item.status,
                "fetched_bytes": item.fetched_bytes,
                "changed_facts": item.changed_facts,
                "error": item.error,
            }
            for item in results
        ],
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest_path


def run(
    *,
    root: Path | None = None,
    catalog_path: Path | None = None,
    dry_run: bool = False,
    only: list[str] | None = None,
    today: str | None = None,
    fetch=fetch_groww_html,
    polite_sleep: float = POLITE_SLEEP_SECONDS,
    attempts: int = FETCH_ATTEMPTS,
    retry_sleep: float = RETRY_SLEEP_SECONDS,
) -> RefreshReport:
    root = root or project_root()
    today = today or date.today().isoformat()
    catalog_file = catalog_path or default_catalog_path(root)
    raw, records = load_catalog(catalog_file, root=root)
    entries = catalog_entries(raw)

    if only:
        wanted = set(only)
        unknown = sorted(wanted - {record.source_id for record in records})
        if unknown:
            raise CatalogError(f"unknown source_id(s): {', '.join(unknown)}")
        records = [record for record in records if record.source_id in wanted]

    results = plan_refresh(
        records,
        root=root,
        entries=entries,
        fetch=fetch,
        polite_sleep=polite_sleep,
        attempts=attempts,
        retry_sleep=retry_sleep,
    )
    report = RefreshReport(results=results, today=today, dry_run=dry_run)

    # All or nothing: one bad fetch leaves the whole corpus on its last good snapshot.
    if not report.ok or dry_run:
        if not dry_run:
            report.manifest_path = write_manifest(results, root=root, today=today)
        return report

    if not any(item.status == "updated" for item in results):
        return report

    write_snapshots(results, root=root)
    report.updated_ids = apply_catalog_updates(raw, entries, results, today=today)
    write_catalog(raw, catalog_file)
    report.manifest_path = write_manifest(results, root=root, today=today)

    # Rebuild downstream artefacts so chunks.jsonl carries the new dates and facts.
    parse_stage.run(root=root, catalog_path=catalog_file)
    chunks, _path = chunk_stage.run(root=root, catalog_path=catalog_file)
    report.chunk_count = len(chunks)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scheduled re-ingest: refresh Groww snapshots, verify, then parse and chunk.",
    )
    parser.add_argument("--catalog", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and verify only; leave the corpus and catalog untouched.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="SOURCE_ID",
        help="Refresh a single catalogued source (repeatable).",
    )
    parser.add_argument(
        "--no-delay",
        action="store_true",
        help="Skip the pause between Groww requests.",
    )
    args = parser.parse_args(argv)

    try:
        report = run(
            catalog_path=args.catalog,
            dry_run=args.dry_run,
            only=args.only,
            polite_sleep=0.0 if args.no_delay else POLITE_SLEEP_SECONDS,
        )
    except (CatalogError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        print(f"refresh failed: {exc}", file=sys.stderr)
        return 1

    mode = " (dry run)" if report.dry_run else ""
    print(f"refreshed {len(report.results)} catalogued Groww sources{mode}")
    for item in report.results:
        flag = "ok" if item.ok else "FAIL"
        detail = f" facts={','.join(item.changed_facts)}" if item.changed_facts else ""
        if item.error:
            detail += f" error={item.error}"
        print(
            f"  [{flag}] {item.doc_type:12} {item.source_id:42} "
            f"{item.status:9} {item.fetched_bytes:8} B{detail}"
        )

    if report.manifest_path:
        print(f"wrote {report.manifest_path}")
    if report.dry_run:
        print("dry run: no snapshot, catalog, or chunk file was written")
    elif report.changed:
        print(f"updated {len(report.updated_ids)} source(s); as_of/retrieved_on set to {report.today}")
        print(f"rebuilt chunks.jsonl with {report.chunk_count} chunks")
    elif report.ok:
        print("corpus unchanged; nothing rewritten")

    if not report.ok:
        print(
            f"{len(report.failed)} source(s) failed verification; corpus left on its "
            "last good snapshot",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
