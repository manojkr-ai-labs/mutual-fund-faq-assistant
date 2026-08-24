from __future__ import annotations

from app.pipeline.contract import count_sentences
from app.pipeline.pii import detect_pii


def test_pan_detected() -> None:
    hit = detect_pii("My PAN is ABCDE1234F, what is the TER?")
    assert hit is not None
    assert hit.kind == "pan"


def test_aadhaar_detected() -> None:
    assert detect_pii("Aadhaar 1234 5678 9012, download my statement.") is not None


def test_otp_detected() -> None:
    assert detect_pii("OTP is 482193, confirm my folio.") is not None


def test_email_detected() -> None:
    assert detect_pii("Email me at user@example.com the expense ratio.") is not None


def test_phone_detected() -> None:
    assert detect_pii("Call me on 9876543210 about HDFC ELSS lock-in.") is not None


def test_folio_account_digits_detected() -> None:
    assert detect_pii("Folio 123456789012 and account 000123456789 — exit load?") is not None


def test_pan_word_without_value_is_not_pii() -> None:
    assert detect_pii("Where do I enter PAN to open the Groww report?") is None


def test_sip_amount_is_not_pii() -> None:
    assert detect_pii("What is the minimum SIP amount for HDFC Large Cap?") is None


def test_count_sentences_abbreviations() -> None:
    text = "SEBI. defined large-cap. See e.g. the Groww page."
    assert count_sentences(text) == 2


def test_count_sentences_decimal_ratio() -> None:
    assert count_sentences("The expense ratio is 1.03.") == 1
