from __future__ import annotations

import pytest

from app.pipeline.config import GroqConfigError, resolve_groq_model
from app.pipeline.generate import (
    MAX_COMPLETION_TOKENS,
    TEMPERATURE,
    generate_answer,
    parse_generated_json,
)
from tests.fakes import FakeGroq


def test_parse_json_object() -> None:
    parsed = parse_generated_json(
        '{"sentences": ["The expense ratio is 1.03."], "used_chunk_id": "abc"}'
    )
    assert parsed.sentences == ("The expense ratio is 1.03.",)
    assert parsed.used_chunk_id == "abc"


def test_parse_fenced_json() -> None:
    parsed = parse_generated_json(
        '```json\n{"sentences": ["Fact."], "used_chunk_id": "id"}\n```'
    )
    assert parsed.sentences == ("Fact.",)


def test_parse_malformed_raises() -> None:
    from app.pipeline.generate import GroqCallError

    with pytest.raises(GroqCallError):
        parse_generated_json("not-json")


def test_forbidden_compound_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "groq/compound")
    with pytest.raises(GroqConfigError):
        resolve_groq_model()


def test_forbidden_compound_mini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "groq/compound-mini")
    with pytest.raises(GroqConfigError):
        resolve_groq_model()


def test_decommissioned_llama_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    with pytest.raises(GroqConfigError):
        resolve_groq_model()
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
    with pytest.raises(GroqConfigError):
        resolve_groq_model()


def test_allowed_gpt_oss_120b(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    assert resolve_groq_model() == "openai/gpt-oss-120b"


def test_allowed_gpt_oss_20b(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    assert resolve_groq_model() == "openai/gpt-oss-20b"


def test_generate_uses_json_schema_and_no_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    client = FakeGroq(
        '{"sentences": ["The expense ratio is 1.03."], "used_chunk_id": "hdfc-large-cap-direct-growth--expense_ratio"}'
    )
    chunks = [
        {
            "chunk_id": "hdfc-large-cap-direct-growth--expense_ratio",
            "scheme_name": "HDFC Large Cap Fund — Direct Growth",
            "as_of": "2026-08-21",
            "text": "Expense ratio: 1.03",
        }
    ]
    result = generate_answer(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        chunks,
        groq_client=client,
    )
    assert result.sentences[0].startswith("The expense ratio")
    assert len(client.calls) == 1
    kwargs = client.calls[0]
    assert kwargs["model"] == "openai/gpt-oss-120b"
    assert kwargs["temperature"] == TEMPERATURE
    assert kwargs["max_completion_tokens"] == MAX_COMPLETION_TOKENS
    assert kwargs["stream"] is False
    assert "tools" not in kwargs
    assert kwargs["response_format"]["type"] == "json_schema"


def test_generate_refuses_pii_without_calling_client() -> None:
    client = FakeGroq('{"sentences": ["leak"], "used_chunk_id": "x"}')
    with pytest.raises(RuntimeError, match="PII"):
        generate_answer(
            "My PAN is ABCDE1234F, what is the TER?",
            [{"chunk_id": "x", "text": "Expense ratio: 1.03"}],
            groq_client=client,
        )
    assert client.calls == []


def test_generate_skips_groq_when_quota_exhausted() -> None:
    from app.pipeline.generate import GroqCallError
    from app.pipeline.rate_limit import GroqLimits, GroqQuota

    client = FakeGroq(
        '{"sentences": ["The expense ratio is 1.03."], "used_chunk_id": "x"}'
    )
    quota = GroqQuota(limits=GroqLimits(rpm=1, rpd=10, tpm=8_000, tpd=200_000), max_wait_sec=0)
    quota.reserve(10, max_completion=64)
    with pytest.raises(GroqCallError, match="rate limit"):
        generate_answer(
            "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
            [{"chunk_id": "x", "text": "Expense ratio: 1.03"}],
            groq_client=client,
            quota=quota,
        )
    assert client.calls == []


def test_generate_records_usage_tokens() -> None:
    from app.pipeline.rate_limit import GroqQuota
    from tests.fakes import FakeUsage

    client = FakeGroq(
        '{"sentences": ["The expense ratio is 1.03."], "used_chunk_id": "x"}',
        usage=FakeUsage(140),
    )
    quota = GroqQuota(max_wait_sec=0)
    generate_answer(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        [{"chunk_id": "x", "scheme_name": "HDFC Large Cap", "as_of": "2026-08-21", "text": "Expense ratio: 1.03"}],
        groq_client=client,
        quota=quota,
    )
    snap = quota.snapshot()
    assert snap.minute_requests == 1
    assert snap.minute_tokens == 140


def test_generate_retries_once_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.pipeline.generate.time.sleep", lambda _sec: None)
    client = FakeGroq(
        '{"sentences": ["The expense ratio is 1.03."], "used_chunk_id": "x"}',
        fail_times=1,
        status_code=429,
    )
    result = generate_answer(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        [{"chunk_id": "x", "text": "Expense ratio: 1.03"}],
        groq_client=client,
    )
    assert result.sentences[0].startswith("The expense ratio")
    assert len(client.calls) == 2
