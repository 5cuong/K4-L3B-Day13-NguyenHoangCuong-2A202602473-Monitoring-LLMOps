from app.pii import scrub_text


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


def test_scrub_vietnamese_citizen_id() -> None:
    out = scrub_text("CCCD: 079123456789")
    assert "079123456789" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card_formats() -> None:
    for card_number in (
        "4111111111111111",
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
    ):
        out = scrub_text(f"Card: {card_number}")
        assert card_number not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_scrub_event_redacts_nested_and_top_level_strings() -> None:
    from app.logging_config import scrub_event

    event = scrub_event(
        None,
        "info",
        {
            "session_id": "student@example.com",
            "payload": {"detail": "Call 090 123 4567", "context": ["CCCD 079123456789"]},
        },
    )
    rendered = str(event)
    assert "student@example.com" not in rendered
    assert "090 123 4567" not in rendered
    assert "079123456789" not in rendered
