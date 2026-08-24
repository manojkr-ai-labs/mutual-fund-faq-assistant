import pytest

from app.pipeline.rate_limit import reset_groq_quota


@pytest.fixture(autouse=True)
def _reset_quota() -> None:
    reset_groq_quota()
    yield
    reset_groq_quota()
