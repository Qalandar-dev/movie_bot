import json
import logging

import pytest

from app.core.logging import JsonFormatter, RedactingFilter, redact


@pytest.mark.parametrize(
    ("raw", "leak"),
    [
        ("Authorization: Bearer eyJhbGciOi.abc.def", "eyJhbGciOi"),
        ("Authorization: Basic UGF5Y29tOnNlY3JldA==", "UGF5Y29tOnNlY3JldA"),
        ('{"password": "hunter2"}', "hunter2"),
        ("sign_string=5f4dcc3b5aa765d61d8327deb882cf99&amount=1000", "5f4dcc3b5aa7"),
        ("token 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw0", "AAHdqTcvCH1v"),
        ("card 8600 1234 5678 9012", "5678"),
        ("secret_key='abc123def'", "abc123def"),
    ],
)
def test_redact_removes_secrets(raw: str, leak: str) -> None:
    assert leak not in redact(raw)


def test_redact_keeps_normal_text() -> None:
    text = "Buyurtma ORD-1024 yaratildi, summa 150000 so‘m"
    assert redact(text) == text


def test_filter_and_json_formatter() -> None:
    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1, "login %s", ("password=qwerty",), None
    )
    RedactingFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))
    assert "qwerty" not in payload["msg"]
    assert payload["level"] == "INFO"
