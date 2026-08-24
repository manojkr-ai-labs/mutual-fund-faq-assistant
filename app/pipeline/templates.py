"""Fixed refusal / factsheet / not-found templates. Never call Groq."""

from __future__ import annotations

from app.corpus.catalog import SourceRecord, load_catalog, project_root
from app.pipeline.contract import AskResponse, assert_guardrail_payload
from app.pipeline.scope import IN_SCOPE_LABELS, mentioned_scheme_ids

EDUCATION_SOURCE_ID = "groww-types-of-mutual-funds"


def _records(*, root=None) -> list[SourceRecord]:
    _raw, records = load_catalog(root=root or project_root())
    return records


def _allowlist(records: list[SourceRecord]) -> frozenset[str]:
    return frozenset(item.source_url for item in records)


def education_source(records: list[SourceRecord]) -> SourceRecord:
    for item in records:
        if item.source_id == EDUCATION_SOURCE_ID:
            return item
    for item in records:
        if item.doc_type == "education":
            return item
    raise LookupError("catalog has no Groww education URL")


def scheme_source(records: list[SourceRecord], scheme_id: str) -> SourceRecord | None:
    for item in records:
        if item.scheme_id == scheme_id:
            return item
    return None


def _cite(record: SourceRecord, *, type: str, text: str) -> AskResponse:
    label = record.title or record.scheme_name or "Groww"
    response = AskResponse(
        type=type,
        text=text,
        citation_url=record.source_url,
        citation_label=label,
        last_updated_from_sources=record.as_of,
    )
    return response


def pii_refusal(records: list[SourceRecord] | None = None) -> AskResponse:
    records = records or _records()
    src = education_source(records)
    text = (
        "This assistant does not accept personal or account data. "
        "Ask a facts-only question without PAN, Aadhaar, contact, or account numbers. "
        "Read Groww's guide to types of mutual funds."
    )
    response = _cite(src, type="refuse", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def advisory_refusal(records: list[SourceRecord] | None = None) -> AskResponse:
    records = records or _records()
    src = education_source(records)
    text = (
        "This assistant does not give investment advice or suitability views. "
        "It only restates facts published on Groww. "
        "Read Groww's guide to types of mutual funds."
    )
    response = _cite(src, type="refuse", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def comparison_refusal(records: list[SourceRecord] | None = None) -> AskResponse:
    records = records or _records()
    src = education_source(records)
    text = (
        "This assistant does not rank funds or say which one to pick. "
        "It only restates facts published on Groww. "
        "Read Groww's guide to types of mutual funds."
    )
    response = _cite(src, type="refuse", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def out_of_scope_refusal(records: list[SourceRecord] | None = None) -> AskResponse:
    records = records or _records()
    src = education_source(records)
    names = "; ".join(IN_SCOPE_LABELS)
    text = (
        "That topic is outside this assistant's five HDFC Direct Growth schemes. "
        f"In scope: {names}. "
        "Read Groww's guide to types of mutual funds."
    )
    response = _cite(src, type="refuse", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def performance_factsheet(question: str, records: list[SourceRecord] | None = None) -> AskResponse:
    records = records or _records()
    hits = mentioned_scheme_ids(question)
    if len(hits) == 1:
        src = scheme_source(records, hits[0]) or education_source(records)
        text = (
            "This assistant does not calculate or compare returns. "
            "Published performance is on this scheme's Groww page. "
            "Open that page for the latest figures."
        )
    else:
        src = education_source(records)
        text = (
            "This assistant does not calculate or compare returns. "
            "Name one in-scope scheme: Mid Cap, Small Cap, Gold ETF FoF, Large Cap, or ELSS Tax Saver Direct Growth. "
            "Published figures are on that scheme's Groww page."
        )
    response = _cite(src, type="factsheet_only", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def not_found(records: list[SourceRecord] | None = None, *, scheme_id: str | None = None) -> AskResponse:
    records = records or _records()
    src = scheme_source(records, scheme_id) if scheme_id else None
    src = src or education_source(records)
    text = (
        "This fact is not in the loaded Groww pages. "
        "See the catalogued Groww page for published details. "
        "Ask about a listed scheme fact such as expense ratio or exit load."
    )
    response = _cite(src, type="refuse", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def empty_question(records: list[SourceRecord] | None = None) -> AskResponse:
    records = records or _records()
    src = education_source(records)
    text = (
        "Please type a question about one of the five HDFC Direct Growth schemes. "
        "This assistant answers published facts from Groww only. "
        "Read Groww's guide to types of mutual funds."
    )
    response = _cite(src, type="error", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def too_long(records: list[SourceRecord] | None = None) -> AskResponse:
    records = records or _records()
    src = education_source(records)
    text = (
        "That question is too long to process. "
        "Ask a short facts-only question about one in-scope scheme. "
        "Read Groww's guide to types of mutual funds."
    )
    response = _cite(src, type="error", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def clarify_scheme(records: list[SourceRecord] | None = None) -> AskResponse:
    records = records or _records()
    src = education_source(records)
    names = "; ".join(IN_SCOPE_LABELS)
    text = (
        f"Name one in-scope scheme: {names}. "
        "This assistant answers published Groww facts only. "
        "Read Groww's guide to types of mutual funds."
    )
    response = _cite(src, type="refuse", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def empty_index(records: list[SourceRecord] | None = None) -> AskResponse:
    records = records or _records()
    src = education_source(records)
    text = (
        "The Groww snapshot index is not loaded. "
        "Run the ingest CLI, then ask again. "
        "Published scheme facts remain on Groww."
    )
    response = _cite(src, type="error", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def missing_groq_key(records: list[SourceRecord] | None = None, *, scheme_id: str | None = None) -> AskResponse:
    records = records or _records()
    src = scheme_source(records, scheme_id) if scheme_id else None
    src = src or education_source(records)
    text = (
        "This assistant cannot format an answer because GROQ_API_KEY is not set. "
        "Add the key to your local environment file. "
        "Published facts remain on the cited Groww page."
    )
    response = _cite(src, type="error", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def groq_unavailable(records: list[SourceRecord] | None = None, *, scheme_id: str | None = None) -> AskResponse:
    records = records or _records()
    src = scheme_source(records, scheme_id) if scheme_id else None
    src = src or education_source(records)
    text = (
        "The answer formatter is temporarily unavailable. "
        "See the cited Groww page for published facts. "
        "Try again in a moment."
    )
    response = _cite(src, type="error", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def forbidden_model(records: list[SourceRecord] | None = None) -> AskResponse:
    records = records or _records()
    src = education_source(records)
    text = (
        "GROQ_MODEL is not allowed. "
        "Use openai/gpt-oss-120b or openai/gpt-oss-20b. "
        "Compound and decommissioned Llama IDs are rejected."
    )
    response = _cite(src, type="error", text=text)
    assert_guardrail_payload(response, allowlisted=_allowlist(records))
    return response


def verbatim_from_chunk(
    chunk: dict,
    records: list[SourceRecord] | None = None,
    *,
    process: bool = False,
) -> AskResponse:
    records = records or _records()
    allowlisted = _allowlist(records)
    url = chunk.get("source_url") or ""
    src = next((item for item in records if item.source_url == url), None)
    if src is None:
        src = scheme_source(records, chunk.get("scheme_id") or "") or education_source(records)
    if process:
        text = (
            "Follow the steps on the cited Groww help page to download this report. "
            "This assistant restates published Groww process text only. "
            "It does not collect PAN, folio, or other account data."
        )
    else:
        fact = " ".join((chunk.get("text") or "").split())
        name = chunk.get("scheme_name") or chunk.get("source_title") or "This scheme"
        if len(fact) > 220:
            fact = fact[:217].rsplit(" ", 1)[0] + "…"
        text = f"{name} on the loaded Groww page: {fact}."
        if not text.endswith("."):
            text += "."
        text += " This assistant restates published facts only."
    response = _cite(src, type="answer", text=text)
    assert_guardrail_payload(response, allowlisted=allowlisted)
    return response
