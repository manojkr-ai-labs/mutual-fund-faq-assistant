"""Phase 2.3: turn parsed Groww JSON into retrieval chunks.

Reads `data/processed/parsed/*.json` (not raw HTML). Does not embed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.corpus.catalog import (
    CatalogError,
    allowlisted_urls,
    is_allowlisted_url,
    load_catalog,
    project_root,
)

SKIP_TEXT_CHARS = 50
CHARS_PER_TOKEN = 4
MAX_EDU_TOKENS = 800
EDU_SLICE_TOKENS = 400
EDU_OVERLAP_TOKENS = 40

PROCESS_CHROME_LINES = frozenset(
    {
        "customer support",
        "help and support",
        "reports",
        "contact us",
    }
)

# Body markers only — never the bare TOC headings "Equity Schemes", etc.
EDU_BODY_MARKERS: tuple[tuple[str, str], ...] = (
    ("maturity", "Schemes Based on the Maturity Period"),
    ("principal", "Based on Principal Investments"),
    ("equity", "- Equity Schemes"),
    ("debt", "- Debt Schemes"),
    ("hybrid", "- Hybrid Schemes"),
    ("solution", "- Solution Oriented Schemes"),
    ("other", "- Other Schemes"),
)

AMC_DUMP_START = "Asset Management Company"

KEEP_FAQ_QUESTIONS = ("How many types of funds are there?",)
DROP_FAQ_QUESTIONS = (
    "What type of mutual fund is best?",
    "How do I start a mutual fund?",
    "Which type of mutual fund is safest?",
    "Which mutual fund is good for 5 years?",
)
ALL_FAQ_QUESTIONS = DROP_FAQ_QUESTIONS + KEEP_FAQ_QUESTIONS

BLANK_PARAS = re.compile(r"\n\s*\n")
MULTI_NL = re.compile(r"\n{3,}")


@dataclass
class Chunk:
    chunk_id: str
    scheme_id: str | None
    scheme_name: str | None
    plan: str | None
    option: str | None
    category: str | None
    doc_type: str
    fact_types: list[str] = field(default_factory=list)
    source_url: str = ""
    source_title: str | None = None
    as_of: str = ""
    retrieved_on: str = ""
    publisher: str = "groww"
    text: str = ""


def approx_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def _squeeze(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = MULTI_NL.sub("\n\n", text)
    return text.strip()


def _slug(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug or "section"


def _assert_chunk_url(url: str, allowed_urls: frozenset[str] | set[str]) -> None:
    if not is_allowlisted_url(url):
        raise CatalogError(f"refusing non-Groww chunk URL: {url}")
    if url not in allowed_urls:
        raise CatalogError(f"chunk source_url is not in sources.json: {url}")


def _meta_chunk(
    doc: dict,
    *,
    chunk_id: str,
    text: str,
    fact_types: list[str],
    scheme_id: str | None,
    allowed_urls: frozenset[str] | set[str],
) -> Chunk:
    url = doc["source_url"]
    _assert_chunk_url(url, allowed_urls)
    publisher = (doc.get("publisher") or "groww").strip().lower()
    if publisher != "groww":
        raise CatalogError(f"refusing publisher {publisher!r} on {doc.get('source_id')}")
    return Chunk(
        chunk_id=chunk_id,
        scheme_id=scheme_id,
        scheme_name=doc.get("scheme_name"),
        plan=doc.get("plan"),
        option=doc.get("option"),
        category=doc.get("category"),
        doc_type=doc["doc_type"],
        fact_types=list(fact_types),
        source_url=url,
        source_title=doc.get("title"),
        as_of=doc.get("as_of") or "",
        retrieved_on=doc.get("retrieved_on") or "",
        publisher="groww",
        text=_squeeze(text),
    )


def _section_slug(section: dict) -> str:
    fact_types = [ft for ft in (section.get("fact_types") or []) if ft]
    if len(fact_types) == 1:
        return fact_types[0]
    if len(fact_types) > 1:
        return "-".join(fact_types)
    heading = (section.get("heading") or "").strip().lower()
    if "objective" in heading:
        return "objective"
    return _slug(heading or "section")


def chunk_scheme_page(doc: dict, *, allowed_urls: frozenset[str] | set[str]) -> list[Chunk]:
    scheme_id = doc.get("scheme_id")
    if not scheme_id:
        raise CatalogError(f"scheme_page {doc.get('source_id')} is missing scheme_id")
    chunks: list[Chunk] = []
    for section in doc.get("sections") or []:
        text = (section.get("text") or "").strip()
        if not text:
            continue
        slug = _section_slug(section)
        chunks.append(
            _meta_chunk(
                doc,
                chunk_id=f"{scheme_id}--{slug}",
                text=text,
                fact_types=list(section.get("fact_types") or []),
                scheme_id=scheme_id,
                allowed_urls=allowed_urls,
            )
        )
    return chunks


def strip_process_chrome(text: str) -> str:
    kept: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.lower() in PROCESS_CHROME_LINES:
            continue
        kept.append(raw.rstrip())
    cleaned = _squeeze("\n".join(kept))
    return cleaned or text.strip()


def chunk_process_page(doc: dict, *, allowed_urls: frozenset[str] | set[str]) -> list[Chunk]:
    sections = doc.get("sections") or []
    if sections:
        text = sections[0].get("text") or doc.get("text") or ""
        fact_types = list(sections[0].get("fact_types") or doc.get("fact_types") or ["process"])
    else:
        text = doc.get("text") or ""
        fact_types = list(doc.get("fact_types") or ["process"])
    text = strip_process_chrome(text)
    if not text:
        return []
    source_id = doc["source_id"]
    return [
        _meta_chunk(
            doc,
            chunk_id=f"{source_id}--process",
            text=text,
            fact_types=fact_types,
            scheme_id=None,
            allowed_urls=allowed_urls,
        )
    ]


def _slice_long_paragraph(text: str) -> list[str]:
    slice_chars = EDU_SLICE_TOKENS * CHARS_PER_TOKEN
    overlap_chars = EDU_OVERLAP_TOKENS * CHARS_PER_TOKEN
    text = text.strip()
    if not text:
        return []
    if len(text) <= slice_chars:
        return [text]
    parts: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + slice_chars, n)
        piece = text[start:end].strip()
        if piece:
            parts.append(piece)
        if end >= n:
            break
        next_start = end - overlap_chars
        if next_start <= start:
            next_start = end
        start = next_start
    return parts


def pack_education_block(text: str, *, max_tokens: int = MAX_EDU_TOKENS) -> list[str]:
    """Split only when a heading block exceeds the education token cap.

    Paragraph-pack with no overlap. Overlapping slices are used only if a
    single paragraph still exceeds the cap.
    """
    text = _squeeze(text)
    if not text:
        return []
    if approx_tokens(text) <= max_tokens:
        return [text]
    paras = [p.strip() for p in BLANK_PARAS.split(text) if p.strip()]
    if not paras:
        return _slice_long_paragraph(text)
    packs: list[str] = []
    current: list[str] = []
    for para in paras:
        pt = approx_tokens(para)
        if pt > max_tokens:
            if current:
                packs.append("\n\n".join(current))
                current = []
            packs.extend(_slice_long_paragraph(para))
            continue
        candidate = para if not current else "\n\n".join(current + [para])
        if current and approx_tokens(candidate) > max_tokens:
            packs.append("\n\n".join(current))
            current = [para]
        else:
            current.append(para)
    if current:
        packs.append("\n\n".join(current))
    return packs


def _faq_blocks(faq_region: str) -> list[tuple[str, str]]:
    found: list[tuple[int, str]] = []
    for question in ALL_FAQ_QUESTIONS:
        index = faq_region.find(question)
        if index >= 0:
            found.append((index, question))
    found.sort()
    blocks: list[tuple[str, str]] = []
    for i, (start, question) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(faq_region)
        body = faq_region[start:end].strip()
        if body:
            blocks.append((question, body))
    return blocks


def split_education_text(text: str) -> list[tuple[str, str]]:
    """Return (slug, block_text) for glossary chunks. Drops AMC dump and advice FAQs."""
    text = text.replace("\r\n", "\n")
    faq_positions = [text.find(q) for q in ALL_FAQ_QUESTIONS if text.find(q) >= 0]
    faq_start = min(faq_positions) if faq_positions else len(text)
    amc_at = text.find(AMC_DUMP_START)
    if amc_at >= 0:
        body = text[:amc_at]
        faq_region = text[faq_start:] if faq_start < len(text) else ""
    else:
        body = text[:faq_start]
        faq_region = text[faq_start:] if faq_start < len(text) else ""

    found: list[tuple[int, str]] = []
    for slug, marker in EDU_BODY_MARKERS:
        index = body.find(marker)
        if index >= 0:
            found.append((index, slug))
    found.sort()

    blocks: list[tuple[str, str]] = []
    first = found[0][0] if found else len(body)
    intro = body[:first].strip()
    if intro:
        blocks.append(("intro", intro))
    for i, (start, slug) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(body)
        block = body[start:end].strip()
        if block:
            blocks.append((slug, block))

    keep = set(KEEP_FAQ_QUESTIONS)
    for question, faq_text in _faq_blocks(faq_region):
        if question in keep:
            blocks.append(("faq-how-many-types", faq_text))
    return blocks


def _chunk_ids(source_id: str, slug: str, count: int) -> list[str]:
    if count <= 1:
        return [f"{source_id}--{slug}"]
    return [
        f"{source_id}--{slug}" if i == 0 else f"{source_id}--{slug}-{i + 1}"
        for i in range(count)
    ]


def chunk_education_page(doc: dict, *, allowed_urls: frozenset[str] | set[str]) -> list[Chunk]:
    source_id = doc["source_id"]
    text = doc.get("text") or ""
    chunks: list[Chunk] = []
    for slug, block in split_education_text(text):
        parts = pack_education_block(block)
        ids = _chunk_ids(source_id, slug, len(parts))
        for chunk_id, part in zip(ids, parts, strict=True):
            chunks.append(
                _meta_chunk(
                    doc,
                    chunk_id=chunk_id,
                    text=part,
                    fact_types=["education"],
                    scheme_id=None,
                    allowed_urls=allowed_urls,
                )
            )
    return chunks


def chunk_document(
    doc: dict,
    *,
    allowed_urls: frozenset[str] | set[str],
    text_chars: int | None = None,
) -> list[Chunk]:
    chars = text_chars if text_chars is not None else len(doc.get("text") or "")
    if chars < SKIP_TEXT_CHARS:
        return []
    doc_type = doc.get("doc_type")
    if doc_type == "scheme_page":
        return chunk_scheme_page(doc, allowed_urls=allowed_urls)
    if doc_type == "process":
        return chunk_process_page(doc, allowed_urls=allowed_urls)
    if doc_type == "education":
        return chunk_education_page(doc, allowed_urls=allowed_urls)
    raise CatalogError(f"unknown doc_type {doc_type!r} for {doc.get('source_id')}")


def parsed_manifest_path(root: Path) -> Path:
    return root / "data" / "processed" / "parsed-manifest.json"


def chunks_path(root: Path) -> Path:
    return root / "data" / "processed" / "chunks.jsonl"


def load_parsed_documents(root: Path) -> list[tuple[dict, int]]:
    manifest_file = parsed_manifest_path(root)
    if not manifest_file.is_file():
        raise CatalogError("parsed-manifest.json missing; run Phase 2.2 parse first")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    loaded: list[tuple[dict, int]] = []
    for item in manifest.get("documents") or []:
        source_id = item["source_id"]
        rel = item.get("parsed_path") or f"data/processed/parsed/{source_id}.json"
        path = root / rel
        if not path.is_file():
            raise CatalogError(f"parsed document missing: {rel}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        text_chars = int(item.get("text_chars", len(doc.get("text") or "")))
        loaded.append((doc, text_chars))
    if not loaded:
        raise CatalogError("parsed-manifest.json lists no documents")
    return loaded


def chunk_all(
    documents: list[tuple[dict, int]],
    *,
    allowed_urls: frozenset[str] | set[str],
) -> list[Chunk]:
    chunks: list[Chunk] = []
    seen: set[str] = set()
    for doc, text_chars in documents:
        for chunk in chunk_document(doc, allowed_urls=allowed_urls, text_chars=text_chars):
            if chunk.chunk_id in seen:
                raise CatalogError(f"duplicate chunk_id {chunk.chunk_id}")
            if not chunk.text:
                continue
            seen.add(chunk.chunk_id)
            chunks.append(chunk)
    return chunks


def write_chunks(chunks: list[Chunk], *, root: Path) -> Path:
    path = chunks_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(chunk), ensure_ascii=False) for chunk in chunks]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def read_chunks(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def run(*, root: Path | None = None, catalog_path: Path | None = None) -> tuple[list[Chunk], Path]:
    root = root or project_root()
    _raw, records = load_catalog(catalog_path, root=root)
    allowed = allowlisted_urls(records)
    documents = load_parsed_documents(root)
    chunks = chunk_all(documents, allowed_urls=allowed)
    path = write_chunks(chunks, root=root)
    return chunks, path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2.3: chunk parsed Groww JSON into chunks.jsonl.",
    )
    parser.add_argument("--catalog", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        chunks, path = run(catalog_path=args.catalog)
    except (CatalogError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        print(f"chunk failed: {exc}", file=sys.stderr)
        return 1
    by_type: dict[str, int] = {}
    for chunk in chunks:
        by_type[chunk.doc_type] = by_type.get(chunk.doc_type, 0) + 1
    print(f"wrote {len(chunks)} chunks ({path})")
    for doc_type, count in sorted(by_type.items()):
        print(f"  {doc_type:12} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
