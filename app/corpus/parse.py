"""Phase 2.2: parse and normalize acquired Groww HTML into structured documents.

No chunking and no embeddings. Output is one JSON file per catalogued source.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from app.corpus.acquire import acquire_all, write_manifest as write_acquisition_manifest
from app.corpus.catalog import (
    CatalogError,
    SourceRecord,
    load_catalog,
    project_root,
)
from app.corpus.html_text import extract_next_data, html_to_text, normalize_text


@dataclass
class ParsedSection:
    heading: str
    fact_types: list[str]
    text: str


@dataclass
class ParsedDocument:
    source_id: str
    doc_type: str
    publisher: str
    source_url: str
    local_path: str
    as_of: str
    retrieved_on: str
    title: str | None
    scheme_id: str | None = None
    scheme_name: str | None = None
    category: str | None = None
    plan: str | None = None
    option: str | None = None
    fact_types: list[str] = field(default_factory=list)
    facts: dict = field(default_factory=dict)
    sections: list[dict] = field(default_factory=list)
    text: str = ""


def _page_props(html: str) -> dict:
    payload = extract_next_data(html) or {}
    return payload.get("props", {}).get("pageProps", {}) or {}


def _format_lock_in(lock_in: dict | None) -> str | None:
    if not isinstance(lock_in, dict):
        return None
    years = lock_in.get("years") or 0
    months = lock_in.get("months") or 0
    days = lock_in.get("days") or 0
    parts: list[str] = []
    if years:
        parts.append(f"{years} year" if years == 1 else f"{years} years")
    if months:
        parts.append(f"{months} month" if months == 1 else f"{months} months")
    if days:
        parts.append(f"{days} day" if days == 1 else f"{days} days")
    return ", ".join(parts) if parts else None


def _stringify(value) -> str | None:
    if value is None or value == "":
        return None
    return str(value).strip()


def _section(heading: str, fact_types: list[str], body: str) -> ParsedSection | None:
    text = normalize_text(body)
    if not text:
        return None
    return ParsedSection(heading=heading, fact_types=fact_types, text=text)


def parse_scheme_page(html: str, record: SourceRecord) -> ParsedDocument:
    mf = _page_props(html).get("mfServerSideData") or {}
    return_stats = (mf.get("return_stats") or [{}])[0]
    lock_in = mf.get("lock_in") or {}
    lock_in_text = _format_lock_in(lock_in)
    facts = {
        "expense_ratio": _stringify(mf.get("expense_ratio")),
        "exit_load": _stringify(mf.get("exit_load")),
        "min_sip_investment": mf.get("min_sip_investment"),
        "min_investment_amount": mf.get("min_investment_amount"),
        "riskometer": _stringify(return_stats.get("risk") or mf.get("nfo_risk")),
        "benchmark": _stringify(mf.get("benchmark") or mf.get("benchmark_name")),
        "lock_in": lock_in_text,
        "lock_in_raw": lock_in,
        "fund_house": _stringify(mf.get("fund_house")),
        "groww_category": _stringify(mf.get("sub_category") or mf.get("category")),
        "description": normalize_text(mf.get("description") or "") or None,
    }
    name = record.scheme_name or mf.get("scheme_name") or record.source_id
    sections: list[ParsedSection] = []
    if facts["expense_ratio"]:
        sections.append(
            ParsedSection(
                "Expense ratio",
                ["expense_ratio"],
                f"Expense ratio: {facts['expense_ratio']}",
            )
        )
    if facts["exit_load"]:
        sections.append(ParsedSection("Exit load", ["exit_load"], f"Exit load: {facts['exit_load']}"))
    if facts["min_sip_investment"] not in (None, ""):
        sections.append(
            ParsedSection(
                "Minimum SIP",
                ["sip"],
                f"Minimum SIP amount: {facts['min_sip_investment']}",
            )
        )
    if facts["riskometer"]:
        sections.append(
            ParsedSection("Riskometer", ["riskometer"], f"Riskometer: {facts['riskometer']}")
        )
    if facts["benchmark"]:
        sections.append(ParsedSection("Benchmark", ["benchmark"], f"Benchmark: {facts['benchmark']}"))
    if lock_in_text:
        sections.append(ParsedSection("Lock-in", ["lockin"], f"Lock-in: {lock_in_text}"))
    if facts["description"]:
        sections.append(ParsedSection("Investment objective", [], facts["description"]))

    fact_types = sorted({ft for section in sections for ft in section.fact_types})
    text = normalize_text("\n\n".join(section.text for section in sections))
    plan = (mf.get("plan_type") or "Direct").strip().lower()
    option = (mf.get("scheme_type") or "Growth").strip().lower()
    return ParsedDocument(
        source_id=record.source_id,
        doc_type=record.doc_type,
        publisher="groww",
        source_url=record.source_url,
        local_path=record.local_path,
        as_of=record.as_of,
        retrieved_on=record.retrieved_on,
        title=name,
        scheme_id=record.scheme_id,
        scheme_name=name,
        category=record.category,
        plan=plan,
        option=option,
        fact_types=fact_types,
        facts=facts,
        sections=[asdict(section) for section in sections],
        text=text,
    )


def parse_education_page(html: str, record: SourceRecord) -> ParsedDocument:
    glossary = _page_props(html).get("glossaryData") or {}
    title = glossary.get("title") or record.title or record.source_id
    content_html = glossary.get("content") or ""
    meta = glossary.get("meta_description") or ""
    faq_parts: list[str] = []
    for item in glossary.get("faqs") or []:
        question = normalize_text(item.get("question") or "")
        answer = html_to_text(item.get("answer") or "")
        if question and answer:
            faq_parts.append(f"{question}\n{answer}")
    body = normalize_text(
        "\n\n".join(
            part
            for part in (title, html_to_text(content_html), normalize_text(meta), *faq_parts)
            if part
        )
    )
    section = _section("Education", ["education"], body)
    return ParsedDocument(
        source_id=record.source_id,
        doc_type=record.doc_type,
        publisher="groww",
        source_url=record.source_url,
        local_path=record.local_path,
        as_of=record.as_of,
        retrieved_on=record.retrieved_on,
        title=title,
        fact_types=["education"],
        sections=[asdict(section)] if section else [],
        text=body,
    )


def parse_process_page(html: str, record: SourceRecord) -> ParsedDocument:
    title = record.title or record.source_id
    visible = html_to_text(html)
    body = normalize_text(
        "\n\n".join(
            part
            for part in (
                title,
                f"Groww help page: {record.source_url}",
                visible,
            )
            if part
        )
    )
    fact_types = list(record.fact_types) or ["process"]
    section = _section("Process", fact_types, body)
    return ParsedDocument(
        source_id=record.source_id,
        doc_type=record.doc_type,
        publisher="groww",
        source_url=record.source_url,
        local_path=record.local_path,
        as_of=record.as_of,
        retrieved_on=record.retrieved_on,
        title=title,
        fact_types=fact_types,
        sections=[asdict(section)] if section else [],
        text=body,
    )


def parse_html(html: str, record: SourceRecord) -> ParsedDocument:
    if record.publisher != "groww":
        raise CatalogError(f"refusing to parse publisher {record.publisher!r}")
    if not record.source_url.startswith("https://groww.in/"):
        raise CatalogError(f"refusing to parse non-Groww URL {record.source_url}")
    if record.doc_type == "scheme_page":
        return parse_scheme_page(html, record)
    if record.doc_type == "education":
        return parse_education_page(html, record)
    if record.doc_type == "process":
        return parse_process_page(html, record)
    raise CatalogError(f"unknown doc_type {record.doc_type}")


def parse_record(record: SourceRecord, *, root: Path) -> ParsedDocument:
    html = record.absolute_path(root).read_text(encoding="utf-8")
    return parse_html(html, record)


def write_parsed_documents(
    documents: list[ParsedDocument],
    *,
    root: Path,
) -> Path:
    out_dir = root / "data" / "processed" / "parsed"
    out_dir.mkdir(parents=True, exist_ok=True)
    for document in documents:
        path = out_dir / f"{document.source_id}.json"
        path.write_text(json.dumps(asdict(document), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "parsed_on": date.today().isoformat(),
        "publisher": "groww",
        "document_count": len(documents),
        "scheme_ids": [doc.scheme_id for doc in documents if doc.scheme_id],
        "documents": [
            {
                "source_id": doc.source_id,
                "doc_type": doc.doc_type,
                "scheme_id": doc.scheme_id,
                "source_url": doc.source_url,
                "as_of": doc.as_of,
                "fact_types": doc.fact_types,
                "parsed_path": f"data/processed/parsed/{doc.source_id}.json",
                "text_chars": len(doc.text),
            }
            for doc in documents
        ],
    }
    manifest_path = root / "data" / "processed" / "parsed-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def run(*, root: Path | None = None, catalog_path: Path | None = None) -> tuple[list[ParsedDocument], Path]:
    root = root or project_root()
    _raw, records = load_catalog(catalog_path, root=root)
    results = acquire_all(records, root=root, fetch_missing=False)
    failed = [item for item in results if not item.ok]
    if failed:
        write_acquisition_manifest(results, root=root)
        raise CatalogError(
            "acquisition incomplete; cannot parse: "
            + ", ".join(item.source_id for item in failed)
        )
    documents = [parse_record(record, root=root) for record in records]
    manifest_path = write_parsed_documents(documents, root=root)
    return documents, manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2.2: parse and normalize Groww HTML snapshots.",
    )
    parser.add_argument("--catalog", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        documents, manifest_path = run(catalog_path=args.catalog)
    except (CatalogError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        print(f"parse failed: {exc}", file=sys.stderr)
        return 1
    print(f"parsed {len(documents)} Groww documents")
    for document in documents:
        facts = ",".join(document.fact_types) or "-"
        print(
            f"  {document.doc_type:12} {document.source_id:42} "
            f"chars={len(document.text):5} facts={facts}"
        )
    print(f"wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
