"""Client-side Groq quota for openai/gpt-oss-120b.

Limits (Groq console for this model):
  30 requests / minute
  1_000 requests / day
  8_000 tokens / minute
  200_000 tokens / day

Sliding windows. Does not log questions. Thread-safe.
When the budget cannot be met within a short wait, callers must skip Groq
and fall back to a verbatim Groww quote (GROQ-03).
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

MINUTE_SEC = 60.0
DAY_SEC = 86_400.0
MIN_COMPLETION_TOKENS = 64
DEFAULT_MAX_WAIT_SEC = 2.0
# Conservative vs ~4 chars/token so we do not overshoot 8k TPM.
CHARS_PER_TOKEN = 3
JSON_SCHEMA_OVERHEAD_TOKENS = 96
ROLE_OVERHEAD_TOKENS = 8


@dataclass(frozen=True)
class GroqLimits:
    rpm: int = 30
    rpd: int = 1_000
    tpm: int = 8_000
    tpd: int = 200_000


# openai/gpt-oss-120b (also applied as a conservative cap for gpt-oss-20b).
GPT_OSS_120B_LIMITS = GroqLimits()


class GroqQuotaError(RuntimeError):
    """Local quota exhausted. Never includes the API key or the question."""


@dataclass(frozen=True)
class QuotaSnapshot:
    minute_requests: int
    minute_tokens: int
    day_requests: int
    day_tokens: int


@dataclass
class Reservation:
    event_id: int
    reserved_tokens: int
    max_completion_tokens: int


@dataclass
class _Event:
    event_id: int
    ts: float
    tokens: int


@dataclass
class GroqQuota:
    limits: GroqLimits = field(default_factory=GroqLimits)
    max_wait_sec: float = DEFAULT_MAX_WAIT_SEC
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[_Event] = []
        self._next_id = 1

    def snapshot(self) -> QuotaSnapshot:
        with self._lock:
            now = self.clock()
            self._prune(now)
            minute = [e for e in self._events if e.ts > now - MINUTE_SEC]
            return QuotaSnapshot(
                minute_requests=len(minute),
                minute_tokens=sum(e.tokens for e in minute),
                day_requests=len(self._events),
                day_tokens=sum(e.tokens for e in self._events),
            )

    def reserve(self, prompt_tokens: int, *, max_completion: int) -> Reservation:
        """Reserve one request. Raises GroqQuotaError if it cannot fit soon."""
        if prompt_tokens < 0:
            raise ValueError("prompt_tokens must be >= 0")
        if prompt_tokens + MIN_COMPLETION_TOKENS > self.limits.tpm:
            raise GroqQuotaError("prompt exceeds Groq tokens-per-minute budget")
        if prompt_tokens + MIN_COMPLETION_TOKENS > self.limits.tpd:
            raise GroqQuotaError("prompt exceeds Groq tokens-per-day budget")

        deadline = self.clock() + max(0.0, self.max_wait_sec)
        while True:
            with self._lock:
                now = self.clock()
                self._prune(now)
                completion = self._completion_room(now, prompt_tokens, max_completion)
                wait = 0.0
                if completion >= MIN_COMPLETION_TOKENS:
                    wait = self._request_wait(now)
                    if wait <= 0:
                        reserved = prompt_tokens + completion
                        event_id = self._next_id
                        self._next_id += 1
                        self._events.append(_Event(event_id, now, reserved))
                        return Reservation(
                            event_id=event_id,
                            reserved_tokens=reserved,
                            max_completion_tokens=completion,
                        )
                else:
                    wait = self._token_wait(now, prompt_tokens + MIN_COMPLETION_TOKENS)
                    if math.isinf(wait):
                        raise GroqQuotaError("Groq daily token budget reached")

                if math.isinf(wait):
                    raise GroqQuotaError("Groq daily request budget reached")
                remaining = deadline - now
                sleep_for = min(wait, remaining)

            if sleep_for <= 0:
                raise GroqQuotaError("Groq rate limit reached")
            self.sleep(sleep_for)

    def settle(self, reservation: Reservation, actual_tokens: int) -> None:
        """Replace reserved tokens with measured usage. Request still counts."""
        used = max(0, int(actual_tokens))
        with self._lock:
            for event in self._events:
                if event.event_id == reservation.event_id:
                    event.tokens = used
                    return

    def _completion_room(self, now: float, prompt_tokens: int, max_completion: int) -> int:
        minute = [e for e in self._events if e.ts > now - MINUTE_SEC]
        remain_tpm = self.limits.tpm - sum(e.tokens for e in minute)
        remain_tpd = self.limits.tpd - sum(e.tokens for e in self._events)
        room = min(remain_tpm, remain_tpd) - prompt_tokens
        return min(max_completion, max(0, room))

    def _request_wait(self, now: float) -> float:
        if self.limits.rpm <= 0 or self.limits.rpd <= 0:
            return math.inf
        minute = [e for e in self._events if e.ts > now - MINUTE_SEC]
        if len(self._events) + 1 > self.limits.rpd:
            return math.inf
        if len(minute) + 1 > self.limits.rpm:
            if not minute:
                return math.inf
            overflow = len(minute) + 1 - self.limits.rpm
            return max(0.0, minute[overflow - 1].ts + MINUTE_SEC - now)
        return 0.0

    def _token_wait(self, now: float, needed: int) -> float:
        minute = [e for e in self._events if e.ts > now - MINUTE_SEC]
        day_tokens = sum(e.tokens for e in self._events)
        if day_tokens + needed > self.limits.tpd:
            return math.inf
        used = sum(e.tokens for e in minute)
        if used + needed <= self.limits.tpm:
            return 0.0
        must_free = used + needed - self.limits.tpm
        freed = 0
        wait = 0.0
        for event in minute:
            freed += event.tokens
            wait = event.ts + MINUTE_SEC - now
            if freed >= must_free:
                break
        return max(0.0, wait)

    def _prune(self, now: float) -> None:
        cutoff = now - DAY_SEC
        self._events = [e for e in self._events if e.ts > cutoff]


_DEFAULT: GroqQuota | None = None
_DEFAULT_LOCK = threading.Lock()


def groq_quota() -> GroqQuota:
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = GroqQuota(limits=GPT_OSS_120B_LIMITS)
        return _DEFAULT


def reset_groq_quota(quota: GroqQuota | None = None) -> GroqQuota:
    global _DEFAULT
    with _DEFAULT_LOCK:
        _DEFAULT = quota if quota is not None else GroqQuota(limits=GPT_OSS_120B_LIMITS)
        return _DEFAULT


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def estimate_prompt_tokens(messages: list[dict[str, str]]) -> int:
    total = JSON_SCHEMA_OVERHEAD_TOKENS
    for message in messages:
        total += ROLE_OVERHEAD_TOKENS
        total += estimate_text_tokens(str(message.get("content") or ""))
    return total
