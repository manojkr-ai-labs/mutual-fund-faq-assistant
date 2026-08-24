"""Metadata-first retrieval over chunks.jsonl. No Groq, no unfiltered k-NN."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.corpus.catalog import load_catalog, project_root
from app.corpus.chunk import read_chunks
from app.pipeline.fact_type import detect_fact_type
from app.pipeline.scheme_resolver import SchemeResolution, resolve_scheme
from app.pipeline.scope import fold_question

SCHEME_FACT_TYPES = frozenset(
    {
        "expense_ratio",
        "exit_load",
        "sip",
        "riskometer",
        "benchmark",
        "lockin",
        "objective",
    }
)
PROCESS_FACT_TYPES = frozenset({"capital_gains", "statement", "elss_statement"})
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "do",
        "does",
        "for",
        "how",
        "i",
        "in",
        "is",
        "it",
        "my",
        "of",
        "on",
        "the",
        "to",
        "what",
        "which",
        "with",
    }
)
TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class RetrievalResult:
    """status: hit | not_found | clarify | empty_index."""

    status: str
    chunks: list[dict] = field(default_factory=list)
    lane: str = ""
    scheme_id: str | None = None
    fact_type: str | None = None
    resolution: SchemeResolution | None = None

    @property
    def citation_chunk(self) -> dict | None:
        if not self.chunks:
            return None
        return _prefer_latest(self.chunks)[0]


def default_chunks_path(root: Path | None = None) -> Path:
    return (root or project_root()) / "data" / "processed" / "chunks.jsonl"


def load_index(*, root: Path | None = None, path: Path | None = None) -> list[dict]:
    chunk_path = path or default_chunks_path(root)
    rows = read_chunks(chunk_path)
    _raw, records = load_catalog(root=root or project_root())
    allowed = {item.source_url for item in records}
    return [row for row in rows if row.get("source_url") in allowed]


def retrieve_for_question(
    question: str,
    *,
    intent: str,
    root: Path | None = None,
    chunks: list[dict] | None = None,
) -> RetrievalResult:
    """Select Groww passages. Never scans the full file without a lane filter."""
    root = root or project_root()
    index = chunks if chunks is not None else load_index(root=root)
    if not index:
        return RetrievalResult("empty_index", lane="none")

    resolution = resolve_scheme(question)
    fact_type = detect_fact_type(question)
    asked_direct = "direct" in fold_question(question)
    asked_regular = "regular" in fold_question(question) and not asked_direct

    if intent == "process" or fact_type in PROCESS_FACT_TYPES:
        return _lane_process(index, question, fact_type, resolution)

    if fact_type == "education":
        return _lane_education(index, question, resolution)

    if intent != "scheme_fact":
        return RetrievalResult("not_found", lane="none", resolution=resolution, fact_type=fact_type)

    if asked_regular:
        return RetrievalResult(
            "not_found",
            lane="A",
            scheme_id=resolution.scheme_id,
            fact_type=fact_type,
            resolution=resolution,
        )

    if resolution.status != "resolved":
        # Scheme-specific facts must not guess. Definitional education is Lane E.
        if fact_type in SCHEME_FACT_TYPES or fact_type is None:
            return RetrievalResult(
                "clarify",
                lane="C",
                fact_type=fact_type,
                resolution=resolution,
            )
        return RetrievalResult("not_found", lane="C", fact_type=fact_type, resolution=resolution)

    scheme_id = resolution.scheme_id
    if fact_type in SCHEME_FACT_TYPES:
        return _lane_scheme_fact(index, scheme_id, fact_type, asked_direct, resolution)
    return _lane_scheme_overview(index, scheme_id, asked_direct, resolution)


def _prefer_latest(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: row.get("as_of") or "", reverse=True)


def _filter_plan(rows: list[dict], asked_direct: bool) -> list[dict]:
    if not asked_direct:
        return rows
    return [row for row in rows if (row.get("plan") or "").lower() == "direct"]


def _lane_scheme_fact(
    index: list[dict],
    scheme_id: str,
    fact_type: str,
    asked_direct: bool,
    resolution: SchemeResolution,
) -> RetrievalResult:
    rows = [row for row in index if row.get("scheme_id") == scheme_id and row.get("doc_type") == "scheme_page"]
    rows = _filter_plan(rows, asked_direct)
    if fact_type == "objective":
        rows = [row for row in rows if str(row.get("chunk_id") or "").endswith("--objective")]
    else:
        rows = [row for row in rows if fact_type in (row.get("fact_types") or [])]
    if not rows:
        return RetrievalResult(
            "not_found",
            lane="A",
            scheme_id=scheme_id,
            fact_type=fact_type,
            resolution=resolution,
        )
    top = _prefer_latest(rows)[:1]
    return RetrievalResult(
        "hit",
        chunks=top,
        lane="A",
        scheme_id=scheme_id,
        fact_type=fact_type,
        resolution=resolution,
    )


def _lane_scheme_overview(
    index: list[dict],
    scheme_id: str,
    asked_direct: bool,
    resolution: SchemeResolution,
) -> RetrievalResult:
    rows = [row for row in index if row.get("scheme_id") == scheme_id and row.get("doc_type") == "scheme_page"]
    rows = _filter_plan(rows, asked_direct)
    if not rows:
        return RetrievalResult(
            "not_found",
            lane="B",
            scheme_id=scheme_id,
            resolution=resolution,
        )
    return RetrievalResult(
        "hit",
        chunks=_prefer_latest(rows),
        lane="B",
        scheme_id=scheme_id,
        resolution=resolution,
    )


def _lane_process(
    index: list[dict],
    question: str,
    fact_type: str | None,
    resolution: SchemeResolution,
) -> RetrievalResult:
    rows = [row for row in index if row.get("doc_type") == "process"]
    if not rows:
        return RetrievalResult("not_found", lane="D", fact_type=fact_type, resolution=resolution)
    if fact_type in PROCESS_FACT_TYPES:
        matched = [row for row in rows if fact_type in (row.get("fact_types") or [])]
        if matched:
            return RetrievalResult(
                "hit",
                chunks=_prefer_latest(matched)[:1],
                lane="D",
                fact_type=fact_type,
                resolution=resolution,
            )
    ranked = _bm25_rank(question, rows, k=1, min_score=0.0)
    if not ranked:
        return RetrievalResult("not_found", lane="D", fact_type=fact_type, resolution=resolution)
    return RetrievalResult(
        "hit",
        chunks=ranked,
        lane="D",
        fact_type=fact_type,
        resolution=resolution,
    )


def _lane_education(
    index: list[dict],
    question: str,
    resolution: SchemeResolution,
) -> RetrievalResult:
    rows = [row for row in index if row.get("doc_type") == "education"]
    if not rows:
        return RetrievalResult("not_found", lane="E", fact_type="education", resolution=resolution)
    ranked = _bm25_rank(question, rows, k=4, min_score=0.0, heading_boost=True)
    if not ranked:
        return RetrievalResult("not_found", lane="E", fact_type="education", resolution=resolution)
    return RetrievalResult(
        "hit",
        chunks=ranked,
        lane="E",
        fact_type="education",
        resolution=resolution,
    )


def _tokens(text: str) -> list[str]:
    return [tok for tok in TOKEN.findall(fold_question(text)) if tok not in STOPWORDS]


def _bm25_rank(
    question: str,
    docs: list[dict],
    *,
    k: int,
    min_score: float,
    heading_boost: bool = False,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[dict]:
    query = _tokens(question)
    if not query or not docs:
        return []
    tokenized = [_tokens(_doc_blob(doc)) for doc in docs]
    n_docs = len(docs)
    avgdl = sum(len(toks) or 1 for toks in tokenized) / n_docs
    df: dict[str, int] = {}
    for toks in tokenized:
        for term in set(toks):
            df[term] = df.get(term, 0) + 1

    scored: list[tuple[float, int]] = []
    for i, toks in enumerate(tokenized):
        length = len(toks) or 1
        tf: dict[str, int] = {}
        for term in toks:
            tf[term] = tf.get(term, 0) + 1
        score = 0.0
        overlap = False
        for term in query:
            freq = tf.get(term, 0)
            if freq:
                overlap = True
            idf = math.log((n_docs - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5) + 1.0)
            denom = freq + k1 * (1.0 - b + b * length / avgdl)
            score += idf * (freq * (k1 + 1.0)) / denom
        if heading_boost:
            score += _heading_boost(query, docs[i])
        if overlap and score > min_score:
            scored.append((score, i))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [docs[i] for _, i in scored[:k]]


def _doc_blob(doc: dict) -> str:
    parts = [
        doc.get("chunk_id") or "",
        doc.get("source_title") or "",
        doc.get("scheme_name") or "",
        doc.get("text") or "",
        " ".join(doc.get("fact_types") or []),
    ]
    return " ".join(parts)


def _heading_boost(query: list[str], chunk: dict) -> float:
    text = (chunk.get("text") or "").lower()
    cid = chunk.get("chunk_id") or ""
    qset = set(query)
    boost = 0.0
    if {"large", "cap"} <= qset and ("large cap" in text or cid.endswith("--equity")):
        boost += 6.0
    if {"mid", "cap"} <= qset and ("mid cap" in text or cid.endswith("--equity")):
        boost += 6.0
    if {"small", "cap"} <= qset and ("small cap" in text or cid.endswith("--equity")):
        boost += 6.0
    if "elss" in qset and ("elss" in text or cid.endswith("--equity")):
        boost += 8.0
    if "fof" in qset or {"fund", "of"} <= qset:
        if "fund of fund" in text or cid.endswith("--other"):
            boost += 6.0
    if "index" in qset and ("index" in text or cid.endswith("--other")):
        boost += 4.0
    if "types" in qset and (cid.endswith("--intro") or cid.endswith("--faq-how-many-types")):
        boost += 3.0
    return boost
