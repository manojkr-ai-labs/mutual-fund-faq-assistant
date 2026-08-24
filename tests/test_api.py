from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import app
from app.pipeline.generate import GeneratedAnswer

client = TestClient(app)

LARGE_URL = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
EDU_URL = "https://groww.in/p/types-of-mutual-funds"


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_post_ask_large_cap_ter(monkeypatch) -> None:
    def fake_generate(question, chunks, repair_reason=None, groq_client=None, **kwargs):
        return GeneratedAnswer(
            sentences=(
                "HDFC Large Cap Fund Direct Growth has an expense ratio of 1.03 on the loaded Groww page.",
            ),
            used_chunk_id="hdfc-large-cap-direct-growth--expense_ratio",
            raw="{}",
        )

    monkeypatch.setattr("app.pipeline.orchestrator.generate_answer", fake_generate)
    response = client.post(
        "/api/ask",
        json={"question": "What is the expense ratio of HDFC Large Cap Fund Direct Growth?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "type",
        "text",
        "citation_url",
        "citation_label",
        "last_updated_from_sources",
        "disclaimer",
    }
    assert body["type"] == "answer"
    assert body["citation_url"] == LARGE_URL
    assert body["last_updated_from_sources"] == "2026-08-21"
    assert body["disclaimer"] == "Facts-only. No investment advice."
    assert "1.03" in body["text"]


def test_post_ask_advisory(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("Groq must not be called")

    monkeypatch.setattr("app.pipeline.orchestrator.generate_answer", boom)
    response = client.post("/api/ask", json={"question": "Should I invest in HDFC Small Cap Fund?"})
    body = response.json()
    assert body["type"] == "refuse"
    assert body["citation_url"] == EDU_URL


def test_post_ask_performance(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("Groq must not be called")

    monkeypatch.setattr("app.pipeline.orchestrator.generate_answer", boom)
    response = client.post(
        "/api/ask",
        json={"question": "What returns did HDFC Large Cap Fund Direct Growth give last year?"},
    )
    body = response.json()
    assert body["type"] == "factsheet_only"
    assert body["citation_url"] == LARGE_URL
    assert "%" not in body["text"]


def test_cors_allows_next_origin() -> None:
    response = client.options(
        "/api/ask",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_post_ask_pii(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("Groq must not be called")

    monkeypatch.setattr("app.pipeline.orchestrator.generate_answer", boom)
    response = client.post(
        "/api/ask",
        json={"question": "My PAN is ABCDE1234F, what is the TER of HDFC Large Cap?"},
    )
    body = response.json()
    assert body["type"] == "refuse"
    assert "ABCDE1234F" not in body["text"]
    assert "ABCDE1234F" not in response.text
