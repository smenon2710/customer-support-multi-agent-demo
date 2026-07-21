import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from shared import config
from shared.auth import verify_internal_token


@pytest.fixture()
def protected_app():
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(verify_internal_token)])
    async def protected():
        return {"ok": True}

    return TestClient(app)


def test_auth_disabled_when_no_token_configured(protected_app, monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_TOKEN", None)
    response = protected_app.get("/protected")
    assert response.status_code == 200


def test_auth_disabled_when_token_is_empty_string(protected_app, monkeypatch):
    # Docker Compose's ${INTERNAL_API_TOKEN:-} substitution sets this env var to ""
    # rather than leaving it truly unset — must be treated as disabled too, not
    # just None, or auth gets enforced everywhere with an unsatisfiable secret.
    monkeypatch.setattr(config, "INTERNAL_API_TOKEN", "")
    response = protected_app.get("/protected")
    assert response.status_code == 200


def test_rejects_missing_token_when_configured(protected_app, monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_TOKEN", "secret123")
    response = protected_app.get("/protected")
    assert response.status_code == 401


def test_rejects_wrong_token(protected_app, monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_TOKEN", "secret123")
    response = protected_app.get("/protected", headers={"X-Internal-Token": "wrong"})
    assert response.status_code == 401


def test_accepts_correct_token(protected_app, monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_TOKEN", "secret123")
    response = protected_app.get("/protected", headers={"X-Internal-Token": "secret123"})
    assert response.status_code == 200
