from __future__ import annotations

from app.pipeline.generate import GeneratedAnswer

LARGE_TER_ID = "hdfc-large-cap-direct-growth--expense_ratio"
ELSS_LOCK_ID = "hdfc-elss-tax-saver-direct-growth--lockin"


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeUsage:
    def __init__(self, total_tokens: int) -> None:
        self.total_tokens = total_tokens


class FakeResponse:
    def __init__(self, content: str, usage: FakeUsage | None = None) -> None:
        self.choices = [FakeChoice(content)]
        self.usage = usage


class FakeGroq:
    def __init__(
        self,
        content: str,
        *,
        usage: FakeUsage | None = None,
        fail_times: int = 0,
        status_code: int = 429,
    ) -> None:
        self.calls: list[dict] = []
        self.content = content
        self.usage = usage
        self._fail_left = fail_times
        self._status_code = status_code
        client = self

        class Completions:
            def create(self, **kwargs):
                client.calls.append(kwargs)
                if client._fail_left > 0:
                    client._fail_left -= 1
                    error = RuntimeError("rate limited")
                    error.status_code = client._status_code
                    raise error
                return FakeResponse(client.content, client.usage)

        class Chat:
            completions = Completions()

        self.chat = Chat()


def ter_answer(*args, **kwargs) -> GeneratedAnswer:
    return GeneratedAnswer(
        sentences=(
            "HDFC Large Cap Fund Direct Growth has an expense ratio of 1.03 on the loaded Groww page.",
        ),
        used_chunk_id=LARGE_TER_ID,
        raw="{}",
    )


def elss_lock_answer(*args, **kwargs) -> GeneratedAnswer:
    return GeneratedAnswer(
        sentences=("HDFC ELSS Tax Saver Fund Direct Plan Growth has a lock-in of 3 years on the loaded Groww page.",),
        used_chunk_id=ELSS_LOCK_ID,
        raw="{}",
    )


def boom_generate(*args, **kwargs):
    raise AssertionError("Groq must not be called on this path")
