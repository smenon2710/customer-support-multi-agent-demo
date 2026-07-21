import httpx
from openai import APIConnectionError, RateLimitError
from pydantic import BaseModel

from shared.db.models import LLMCallLog
from shared.llm_client import complete_json


class _Schema(BaseModel):
    value: str


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, responses):
        self.chat = _FakeChat(_FakeCompletions(responses))


def test_complete_json_returns_parsed_schema_on_valid_response():
    client = _FakeClient(['{"value": "hello"}'])
    result = complete_json("fake-model", "system", "user", _Schema, client=client)
    assert result == _Schema(value="hello")
    assert client.chat.completions.calls == 1


def test_complete_json_retries_once_on_invalid_json_then_gives_up():
    client = _FakeClient(["not json", "still not json"])
    result = complete_json("fake-model", "system", "user", _Schema, retries=1, client=client)
    assert result is None
    assert client.chat.completions.calls == 2


def test_complete_json_recovers_on_retry():
    client = _FakeClient(["not json", '{"value": "recovered"}'])
    result = complete_json("fake-model", "system", "user", _Schema, retries=1, client=client)
    assert result == _Schema(value="recovered")


def test_complete_json_returns_none_on_any_exception_without_retrying():
    client = _FakeClient([RuntimeError("boom")])
    result = complete_json("fake-model", "system", "user", _Schema, retries=2, client=client)
    assert result is None
    assert client.chat.completions.calls == 1  # no retry storm on transport/provider errors


def test_complete_json_returns_none_without_a_client_or_api_key():
    # No client passed, and OPENROUTER_API_KEY is unset in the test environment.
    result = complete_json("fake-model", "system", "user", _Schema)
    assert result is None


def _rate_limit_error():
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(status_code=429, request=request)
    return RateLimitError("rate limited", response=response, body=None)


def test_complete_json_returns_none_on_rate_limit_without_retrying():
    client = _FakeClient([_rate_limit_error()])
    result = complete_json("fake-model", "system", "user", _Schema, retries=2, client=client)
    assert result is None
    assert client.chat.completions.calls == 1


def test_complete_json_returns_none_on_connection_error_without_retrying():
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    client = _FakeClient([APIConnectionError(request=request)])
    result = complete_json("fake-model", "system", "user", _Schema, retries=2, client=client)
    assert result is None
    assert client.chat.completions.calls == 1


def test_complete_json_logs_success_to_db(db_session):
    client = _FakeClient(['{"value": "hello"}'])
    complete_json("fake-model", "system", "user", _Schema, client=client, db=db_session)
    db_session.commit()

    log = db_session.query(LLMCallLog).first()
    assert log is not None
    assert log.model == "fake-model"
    assert log.success is True
    assert log.reason == "success"


def test_complete_json_logs_rate_limit_reason_to_db(db_session):
    client = _FakeClient([_rate_limit_error()])
    complete_json("fake-model", "system", "user", _Schema, client=client, db=db_session)
    db_session.commit()

    log = db_session.query(LLMCallLog).first()
    assert log is not None
    assert log.success is False
    assert log.reason == "rate_limited"


def test_complete_json_logs_no_api_key_reason_to_db(db_session):
    # No client passed, and OPENROUTER_API_KEY is unset in the test environment.
    complete_json("fake-model", "system", "user", _Schema, db=db_session)
    db_session.commit()

    log = db_session.query(LLMCallLog).first()
    assert log is not None
    assert log.success is False
    assert log.reason == "no_api_key"


def test_complete_json_without_db_does_not_raise():
    # db=None (the default) must never attempt a DB write.
    client = _FakeClient(['{"value": "hello"}'])
    result = complete_json("fake-model", "system", "user", _Schema, client=client)
    assert result == _Schema(value="hello")
