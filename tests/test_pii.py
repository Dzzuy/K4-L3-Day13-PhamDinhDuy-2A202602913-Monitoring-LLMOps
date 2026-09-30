from app.pii import scrub_text, scrub_value


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_national_id_card_and_passport() -> None:
    out = scrub_text("CCCD 079203001234; card 4111 1111 1111 1111; passport B1234567")
    assert "079203001234" not in out
    assert "4111 1111 1111 1111" not in out
    assert "B1234567" not in out
    assert "REDACTED_CCCD" in out
    assert "REDACTED_CREDIT_CARD" in out
    assert "REDACTED_PASSPORT_VN" in out


def test_scrub_nested_values_and_preserve_correlation_id() -> None:
    value = {
        "correlation_id": "req-1234abcd",
        "trace_id": "ea35ac89f6f123456789012f49924a86",
        "payload": ["student@vinuni.edu.vn", ("090 123 4567", ValueError("B1234567"))],
    }
    cleaned = scrub_value(value)
    assert cleaned["correlation_id"] == "req-1234abcd"
    assert cleaned["trace_id"] == value["trace_id"]
    assert "student@" not in str(cleaned)
    assert "090 123 4567" not in str(cleaned)
    assert "B1234567" not in str(cleaned)
