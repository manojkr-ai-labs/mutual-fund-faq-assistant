"""PII detector. Runs before retrieve, Groq, and any question logging."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Indian PAN: five letters, four digits, one letter (e.g. ABCDE1234F).
PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
# 12-digit Aadhaar, optional spaces or hyphens.
AADHAAR = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
EMAIL = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)
# Indian mobile, optional +91.
PHONE = re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}\b")
# Folio / bank-style runs (12+ digits). Shorter amounts like SIP 100 are ignored.
ACCOUNT = re.compile(r"\b\d{12,}\b")
OTP = re.compile(
    r"\b(?:otp|one[\s-]?time(?:\s+password)?|pin)\b.{0,24}\b(\d{4,8})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PiiHit:
    kind: str


def detect_pii(question: str) -> PiiHit | None:
    """Return a hit if the question contains personal or account *values*.

    Mentioning the word PAN or folio without a value is not PII.
    Do not log or return the matched value.
    """
    if not question:
        return None
    if PAN.search(question):
        return PiiHit("pan")
    if EMAIL.search(question):
        return PiiHit("email")
    if OTP.search(question):
        return PiiHit("otp")
    if PHONE.search(question):
        return PiiHit("phone")
    if ACCOUNT.search(question):
        return PiiHit("account")
    if AADHAAR.search(question):
        return PiiHit("aadhaar")
    return None
