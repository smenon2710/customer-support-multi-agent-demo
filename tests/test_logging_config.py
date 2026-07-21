import json
import logging

from shared.logging_config import JSONFormatter, set_ticket_id


def _make_record(message="hello"):
    return logging.LogRecord(
        name="test.logger", level=logging.INFO, pathname=__file__, lineno=1,
        msg=message, args=(), exc_info=None,
    )


def test_json_formatter_produces_valid_json_with_core_fields():
    set_ticket_id(None)
    formatter = JSONFormatter()
    output = formatter.format(_make_record("hello world"))

    payload = json.loads(output)
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert "timestamp" in payload


def test_json_formatter_includes_ticket_id_when_set():
    set_ticket_id("T123")
    try:
        formatter = JSONFormatter()
        output = formatter.format(_make_record())
        payload = json.loads(output)
        assert payload["ticket_id"] == "T123"
    finally:
        set_ticket_id(None)


def test_json_formatter_omits_ticket_id_when_unset():
    set_ticket_id(None)
    formatter = JSONFormatter()
    output = formatter.format(_make_record())
    payload = json.loads(output)
    assert "ticket_id" not in payload


def test_json_formatter_supports_message_args():
    set_ticket_id(None)
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test.logger", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="failed for %s: %s", args=("T1", "boom"), exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert payload["message"] == "failed for T1: boom"
