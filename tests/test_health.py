from fastapi.testclient import TestClient

from app.config.loader import reload_config
from app.main import app


client = TestClient(app)


def test_health_returns_backend_status(monkeypatch) -> None:
    monkeypatch.setenv("CONTI_BACKEND_CONFIG", "/contenedores/conti-backend/config/app_config.json")
    reload_config()
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "conti-backend"
    assert payload["llm_backend"]["mode"] == "nanobot_serve"
    assert "development_repo" in payload["workspace"]


def test_config_redacts_sensitive_fields(monkeypatch) -> None:
    monkeypatch.setenv("CONTI_BACKEND_CONFIG", "/contenedores/conti-backend/config/app_config.json")
    reload_config()
    response = client.get("/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["config"]["providers"]["openai_compatible"]["api_key_env"] == "***REDACTED***"
    assert payload["config"]["paths"]["development_repo"] == "/desarrollo"
