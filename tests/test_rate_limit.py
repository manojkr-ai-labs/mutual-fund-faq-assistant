from __future__ import annotations

import pytest

from app.pipeline.rate_limit import (
    GPT_OSS_120B_LIMITS,
    GroqLimits,
    GroqQuota,
    GroqQuotaError,
    estimate_prompt_tokens,
    estimate_text_tokens,
)


class FakeClock:
    def __init__(self, t: float = 1_000_000.0) -> None:
        self.t = t

    def time(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def test_gpt_oss_120b_limits() -> None:
    assert GPT_OSS_120B_LIMITS.rpm == 30
    assert GPT_OSS_120B_LIMITS.rpd == 1_000
    assert GPT_OSS_120B_LIMITS.tpm == 8_000
    assert GPT_OSS_120B_LIMITS.tpd == 200_000


def test_estimate_text_tokens_is_conservative() -> None:
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("abcd") == 2  # 3 chars/token, rounded up


def test_estimate_prompt_tokens_includes_overhead() -> None:
    messages = [{"role": "user", "content": "hello"}]
    assert estimate_prompt_tokens(messages) > estimate_text_tokens("hello")


def test_rpm_31st_request_is_blocked() -> None:
    clock = FakeClock()
    quota = GroqQuota(
        limits=GroqLimits(rpm=30, rpd=1_000, tpm=8_000, tpd=200_000),
        max_wait_sec=0,
        clock=clock.time,
        sleep=clock.sleep,
    )
    for _ in range(30):
        quota.reserve(10, max_completion=64)
    with pytest.raises(GroqQuotaError, match="rate limit"):
        quota.reserve(10, max_completion=64)


def test_rpm_recovers_after_minute_window() -> None:
    clock = FakeClock()
    quota = GroqQuota(
        limits=GroqLimits(rpm=30, rpd=1_000, tpm=8_000, tpd=200_000),
        max_wait_sec=70,
        clock=clock.time,
        sleep=clock.sleep,
    )
    for _ in range(30):
        quota.reserve(10, max_completion=64)
    quota.reserve(10, max_completion=64)
    assert clock.t >= 1_000_000.0 + 60.0


def test_tpm_blocks_when_prompt_cannot_fit() -> None:
    quota = GroqQuota(
        limits=GroqLimits(rpm=30, rpd=1_000, tpm=8_000, tpd=200_000),
        max_wait_sec=0,
    )
    with pytest.raises(GroqQuotaError, match="tokens-per-minute"):
        quota.reserve(7_950, max_completion=256)


def test_tpd_blocks_without_waiting() -> None:
    clock = FakeClock()
    quota = GroqQuota(
        limits=GroqLimits(rpm=30, rpd=1_000, tpm=8_000, tpd=500),
        max_wait_sec=10,
        clock=clock.time,
        sleep=clock.sleep,
    )
    quota.reserve(200, max_completion=64)
    with pytest.raises(GroqQuotaError, match="daily token"):
        quota.reserve(200, max_completion=64)
    assert clock.t == 1_000_000.0


def test_rpd_blocks_without_waiting() -> None:
    clock = FakeClock()
    quota = GroqQuota(
        limits=GroqLimits(rpm=30, rpd=2, tpm=8_000, tpd=200_000),
        max_wait_sec=10,
        clock=clock.time,
        sleep=clock.sleep,
    )
    quota.reserve(10, max_completion=64)
    quota.reserve(10, max_completion=64)
    with pytest.raises(GroqQuotaError, match="daily request"):
        quota.reserve(10, max_completion=64)


def test_settle_replaces_reserved_tokens() -> None:
    quota = GroqQuota(max_wait_sec=0)
    reservation = quota.reserve(100, max_completion=256)
    assert quota.snapshot().minute_tokens == 100 + reservation.max_completion_tokens
    quota.settle(reservation, 120)
    snap = quota.snapshot()
    assert snap.minute_requests == 1
    assert snap.minute_tokens == 120


def test_failed_call_still_counts_as_a_request() -> None:
    quota = GroqQuota(
        limits=GroqLimits(rpm=1, rpd=10, tpm=8_000, tpd=200_000),
        max_wait_sec=0,
    )
    reservation = quota.reserve(50, max_completion=64)
    quota.settle(reservation, 0)
    snap = quota.snapshot()
    assert snap.minute_requests == 1
    assert snap.minute_tokens == 0
    with pytest.raises(GroqQuotaError):
        quota.reserve(50, max_completion=64)
