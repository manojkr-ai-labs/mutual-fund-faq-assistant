"""Ask orchestrator: guardrails → retrieve → Groq format → validate → public payload."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.corpus.catalog import load_catalog, project_root
from app.pipeline.config import GroqConfigError
from app.pipeline.contract import AskResponse, assert_guardrail_payload
from app.pipeline.generate import GeneratedAnswer, GroqCallError, generate_answer
from app.pipeline.guard import apply_guardrails
from app.pipeline.retrieve import RetrievalResult, retrieve_for_question
from app.pipeline.validate import validate_generation
from app.pipeline import templates

GenerateFn = Callable[..., GeneratedAnswer]


def _records(*, root: Path | None = None):
    _raw, records = load_catalog(root=root or project_root())
    return records


def _attach_citation(
    text: str,
    chunk: dict,
    records,
    *,
    type: str = "answer",
) -> AskResponse:
    url = chunk.get("source_url") or ""
    src = next((item for item in records if item.source_url == url), None)
    if src is None:
        from app.pipeline.templates import education_source, scheme_source

        src = scheme_source(records, chunk.get("scheme_id") or "") or education_source(records)
    label = chunk.get("source_title") or chunk.get("scheme_name") or src.title or "Groww"
    as_of = chunk.get("as_of") or src.as_of
    response = AskResponse(
        type=type,
        text=text,
        citation_url=src.source_url,
        citation_label=label,
        last_updated_from_sources=as_of,
    )
    allowlisted = {item.source_url for item in records}
    assert_guardrail_payload(response, allowlisted=allowlisted)
    return response


def _pick_chunk(retrieval: RetrievalResult, used_chunk_id: str | None) -> dict:
    if used_chunk_id:
        for chunk in retrieval.chunks:
            if chunk.get("chunk_id") == used_chunk_id:
                return chunk
    return retrieval.citation_chunk or retrieval.chunks[0]


def _fallback_from_retrieval(retrieval: RetrievalResult, records) -> AskResponse:
    chunk = retrieval.citation_chunk
    if chunk is None:
        return templates.not_found(records, scheme_id=retrieval.scheme_id)
    process = retrieval.lane == "D" or (chunk.get("doc_type") == "process")
    return templates.verbatim_from_chunk(chunk, records, process=process)


def _generate(
    question: str,
    chunks: list[dict],
    *,
    generate_fn: GenerateFn | None,
    groq_client: Any | None,
    repair_reason: str | None = None,
) -> GeneratedAnswer:
    if generate_fn is not None:
        return generate_fn(question, chunks, repair_reason=repair_reason, groq_client=groq_client)
    return generate_answer(question, chunks, repair_reason=repair_reason, groq_client=groq_client)


def ask(
    question: str | None,
    *,
    root: Path | None = None,
    generate_fn: GenerateFn | None = None,
    groq_client: Any | None = None,
) -> AskResponse:
    """End-to-end facts-only Ask path. Does not log the raw question."""
    root = root or project_root()
    records = _records(root=root)
    guard = apply_guardrails(question, root=root)
    if guard.terminal:
        assert guard.response is not None
        return guard.response

    retrieval = retrieve_for_question(str(question), intent=guard.intent, root=root)
    if retrieval.status == "empty_index":
        return templates.empty_index(records)
    if retrieval.status == "clarify":
        return templates.clarify_scheme(records)
    if retrieval.status != "hit" or not retrieval.chunks:
        return templates.not_found(records, scheme_id=retrieval.scheme_id)

    try:
        draft = _generate(
            str(question),
            retrieval.chunks,
            generate_fn=generate_fn,
            groq_client=groq_client,
        )
    except GroqConfigError as exc:
        message = str(exc)
        if "GROQ_API_KEY" in message:
            return templates.missing_groq_key(records, scheme_id=retrieval.scheme_id)
        return templates.forbidden_model(records)
    except GroqCallError:
        return _fallback_from_retrieval(retrieval, records)

    checked = validate_generation(
        draft.sentences,
        chunks=retrieval.chunks,
        used_chunk_id=draft.used_chunk_id,
        intent=guard.intent,
    )
    if not checked.ok:
        reason = "; ".join(checked.reasons)
        try:
            draft = _generate(
                str(question),
                retrieval.chunks,
                generate_fn=generate_fn,
                groq_client=groq_client,
                repair_reason=reason,
            )
        except (GroqConfigError, GroqCallError):
            return _fallback_from_retrieval(retrieval, records)
        checked = validate_generation(
            draft.sentences,
            chunks=retrieval.chunks,
            used_chunk_id=draft.used_chunk_id,
            intent=guard.intent,
        )
        if not checked.ok:
            return _fallback_from_retrieval(retrieval, records)

    chunk = _pick_chunk(retrieval, checked.used_chunk_id)
    return _attach_citation(checked.text, chunk, records)
