import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_container_health_via_mcp(monkeypatch) -> None:
    container = SimpleNamespace(
        short_id="abc123",
        name="django-api",
        status="running",
        image=SimpleNamespace(tags=["django:latest"]),
        attrs={
            "State": {"Status": "running", "StartedAt": "2026-04-30T10:00:00Z", "Health": {"Status": "healthy"}},
            "NetworkSettings": {"Ports": {"8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8000"}]}},
        },
    )
    client_stub = SimpleNamespace(
        containers=SimpleNamespace(
            list=lambda all=False, filters=None: [container],
            get=lambda name: container,
        )
    )

    monkeypatch.setattr("app.tools.container_tools._docker_client", lambda: client_stub)
    response = client.post("/mcp/call", json={"tool": "get_container_health", "arguments": {}})
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["available"] is True
    assert payload["containers"][0]["name"] == "django-api"
    assert payload["containers"][0]["health"] == "healthy"


def test_get_container_logs_filters_errors(monkeypatch) -> None:
    container = SimpleNamespace(
        logs=lambda **kwargs: b"2026-04-30T10:00:00Z info started\n2026-04-30T10:00:01Z ERROR exploded\n2026-04-30T10:00:02Z warning slow"
    )
    client_stub = SimpleNamespace(containers=SimpleNamespace(get=lambda name: container))
    monkeypatch.setattr("app.tools.container_tools._docker_client", lambda: client_stub)
    response = client.post(
        "/mcp/call",
        json={
            "tool": "get_container_logs",
            "arguments": {"container": "django-api", "lines": 50, "since": "1h", "level": "error"},
        },
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["available"] is True
    assert payload["returned_lines"] == 1
    assert "ERROR exploded" in payload["logs"]


def test_get_vps_status_combines_docker_and_git(monkeypatch) -> None:
    def fake_health(_config, _args):
        return {"available": True, "containers": [{"name": "conti-backend", "status": "Up 1 hour"}], "count": 1}

    def fake_git_summary(_config, _args):
        return {"available": True, "branch": "develop", "is_clean": False}

    monkeypatch.setattr("app.tools.container_tools.get_container_health", fake_health)
    monkeypatch.setattr("app.tools.container_tools.git_tools.get_pipeline_summary", fake_git_summary)

    response = client.post("/mcp/call", json={"tool": "get_vps_status", "arguments": {}})
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["summary"]["containers_total"] == 1
    assert payload["summary"]["git_branch"] == "develop"