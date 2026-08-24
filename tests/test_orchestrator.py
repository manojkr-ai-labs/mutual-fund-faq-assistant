from __future__ import annotations

from app.pipeline.contract import DISCLAIMER, count_sentences
from app.pipeline.generate import GeneratedAnswer, GroqCallError, GroqConfigError
from app.pipeline.orchestrator import ask
from tests.fakes import boom_generate, elss_lock_answer, ter_answer

EDU_URL = "https://groww.in/p/types-of-mutual-funds"
LARGE_URL = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
ELSS_URL = "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth"
CG_URL = "https://groww.in/help/mutual-funds/mf-others/how-to-download-capital-gain-report--50"
STMT_URL = "https://groww.in/help/my-account/ma-others/where-can-i-get-the-transaction-history"


def _contract(response, *, type: str) -> None:
    assert response.type == type
    assert count_sentences(response.text) <= 3
    assert response.citation_url.startswith("https://groww.in/")
    assert response.disclaimer == DISCLAIMER
    assert response.last_updated_from_sources
    assert "https://" not in response.text


def test_factual_large_cap_ter() -> None:
    response = ask(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        generate_fn=ter_answer,
    )
    _contract(response, type="answer")
    assert response.citation_url == LARGE_URL
    assert response.last_updated_from_sources == "2026-08-21"
    assert "1.03" in response.text


def test_elss_lockin() -> None:
    response = ask(
        "What is the lock-in period for HDFC ELSS Tax Saver Fund Direct Plan Growth?",
        generate_fn=elss_lock_answer,
    )
    _contract(response, type="answer")
    assert response.citation_url == ELSS_URL
    assert "3 years" in response.text or "3" in response.text


def test_advisory_does_not_call_groq() -> None:
    response = ask("Should I invest in HDFC Small Cap Fund?", generate_fn=boom_generate)
    _contract(response, type="refuse")
    assert response.citation_url == EDU_URL
    assert "1.03" not in response.text
    assert "0.75" not in response.text


def test_comparison_does_not_call_groq() -> None:
    response = ask("Which fund is better?", generate_fn=boom_generate)
    _contract(response, type="refuse")


def test_performance_factsheet_only() -> None:
    response = ask(
        "What returns did HDFC Large Cap Fund Direct Growth give last year?",
        generate_fn=boom_generate,
    )
    _contract(response, type="factsheet_only")
    assert response.citation_url == LARGE_URL
    assert "%" not in response.text


def test_pii_does_not_call_groq_or_echo_pan() -> None:
    response = ask(
        "My PAN is ABCDE1234F, what is the TER of HDFC Large Cap?",
        generate_fn=boom_generate,
    )
    _contract(response, type="refuse")
    assert "ABCDE1234F" not in response.text
    assert response.citation_url == EDU_URL


def test_process_capital_gains_no_pan_request() -> None:
    def gen(*args, **kwargs) -> GeneratedAnswer:
        return GeneratedAnswer(
            sentences=(
                "Download the capital gains report from the Groww help page linked below.",
            ),
            used_chunk_id="groww-capital-gains-report--process",
            raw="{}",
        )

    response = ask("How do I download a capital gains report?", generate_fn=gen)
    _contract(response, type="answer")
    assert response.citation_url == CG_URL
    lowered = response.text.lower()
    assert "send your pan" not in lowered
    assert "enter your pan" not in lowered
    assert "provide your pan" not in lowered


def test_process_statement_no_pan_request() -> None:
    def gen(*args, **kwargs) -> GeneratedAnswer:
        return GeneratedAnswer(
            sentences=("Request transaction history from the Reports section on Groww.",),
            used_chunk_id="groww-transaction-history--process",
            raw="{}",
        )

    response = ask("How do I download my mutual fund statement?", generate_fn=gen)
    _contract(response, type="answer")
    assert response.citation_url == STMT_URL
    assert "send your pan" not in response.text.lower()


def test_mid_cap_lockin_not_found_without_groq() -> None:
    response = ask(
        "What is the lock-in period for HDFC Mid Cap Fund Direct Growth?",
        generate_fn=boom_generate,
    )
    _contract(response, type="refuse")
    assert "3 years" not in response.text


def test_clarify_unnamed_scheme_without_groq() -> None:
    response = ask("What is the expense ratio?", generate_fn=boom_generate)
    _contract(response, type="refuse")
    assert "Large Cap" in response.text or "ELSS" in response.text


def test_missing_groq_key(monkeypatch) -> None:
    monkeypatch.setattr("app.pipeline.generate.groq_api_key", lambda: None)

    def raise_missing(question, chunks, **kwargs):
        raise GroqConfigError("GROQ_API_KEY is not set")

    monkeypatch.setattr("app.pipeline.orchestrator.generate_answer", raise_missing)
    response = ask("What is the expense ratio of HDFC Large Cap Fund Direct Growth?")
    _contract(response, type="error")
    assert "GROQ_API_KEY" in response.text
    assert "sk-" not in response.text
    assert "gsk_" not in response.text


def test_forbidden_model_error(monkeypatch) -> None:
    def raise_forbidden(question, chunks, **kwargs):
        raise GroqConfigError(
            "GROQ_MODEL is forbidden (Compound web-search or decommissioned Llama). "
            "Use openai/gpt-oss-120b or openai/gpt-oss-20b."
        )

    monkeypatch.setattr("app.pipeline.orchestrator.generate_answer", raise_forbidden)
    response = ask("What is the expense ratio of HDFC Large Cap Fund Direct Growth?")
    _contract(response, type="error")
    assert "openai/gpt-oss-120b" in response.text or "not allowed" in response.text.lower()


def test_repair_then_template_fallback_on_advice() -> None:
    calls: list[str | None] = []

    def bad(*args, repair_reason=None, **kwargs) -> GeneratedAnswer:
        calls.append(repair_reason)
        return GeneratedAnswer(
            sentences=("You should invest because the expense ratio is 1.03.",),
            used_chunk_id="hdfc-large-cap-direct-growth--expense_ratio",
            raw="{}",
        )

    response = ask(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        generate_fn=bad,
    )
    _contract(response, type="answer")
    assert len(calls) == 2
    assert calls[1] is not None
    assert "should invest" not in response.text.lower()
    assert "1.03" in response.text
    assert response.citation_url == LARGE_URL


def test_invented_number_falls_back_to_chunk() -> None:
    def bad(*args, **kwargs) -> GeneratedAnswer:
        return GeneratedAnswer(
            sentences=("The expense ratio is 0.99.",),
            used_chunk_id="hdfc-large-cap-direct-growth--expense_ratio",
            raw="{}",
        )

    response = ask(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        generate_fn=bad,
    )
    _contract(response, type="answer")
    assert "0.99" not in response.text
    assert "1.03" in response.text


def test_groq_outage_quotes_chunk() -> None:
    def fail(*args, **kwargs):
        raise GroqCallError("Groq request failed")

    response = ask(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        generate_fn=fail,
    )
    _contract(response, type="answer")
    assert "1.03" in response.text
    assert response.citation_url == LARGE_URL


def test_quota_exhausted_quotes_chunk() -> None:
    from app.pipeline.rate_limit import GroqLimits, GroqQuota, reset_groq_quota
    from tests.fakes import FakeGroq

    quota = GroqQuota(limits=GroqLimits(rpm=1, rpd=10, tpm=8_000, tpd=200_000), max_wait_sec=0)
    quota.reserve(10, max_completion=64)
    reset_groq_quota(quota)
    client = FakeGroq(
        '{"sentences": ["should not run"], "used_chunk_id": "x"}'
    )
    response = ask(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        groq_client=client,
    )
    _contract(response, type="answer")
    assert "1.03" in response.text
    assert response.citation_url == LARGE_URL
    assert client.calls == []


def test_citation_not_taken_from_model_url() -> None:
    def with_url(*args, **kwargs) -> GeneratedAnswer:
        return GeneratedAnswer(
            sentences=(
                "The expense ratio is 1.03. See https://www.morningstar.com/funds/hdfc.",
            ),
            used_chunk_id="hdfc-large-cap-direct-growth--expense_ratio",
            raw="{}",
        )

    response = ask(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        generate_fn=with_url,
    )
    _contract(response, type="answer")
    assert response.citation_url == LARGE_URL
    assert "morningstar" not in response.citation_url
    assert "morningstar" not in response.text.lower()
