from fastapi.testclient import TestClient

from app.main import app
from app.services import nanobot_config_service as service_module


client = TestClient(app)


def _patch_nanobot_paths(monkeypatch, tmp_path) -> None:
        gateway_path = tmp_path / "config.json"
        llm_path = tmp_path / "llm_serve_config.json"
        gateway_path.write_text(
                """
{
    "agents": {
        "defaults": {
            "model": "gpt-4",
            "provider": "copilot-local",
            "temperature": 0.2,
            "maxToolIterations": 10,
            "maxTokens": 8192,
            "contextWindowTokens": 65536
        }
    },
    "providers": {
        "copilot-local": {
            "apiBase": "http://host.docker.internal:3030/v1",
            "apiKey": "dummy"
        }
    },
    "channels": {
        "telegram": {
            "token": "abc",
            "allowFrom": ["luisdalmasso"]
        }
    }
}
                """.strip(),
                encoding="utf-8",
        )
        llm_path.write_text(gateway_path.read_text(encoding="utf-8"), encoding="utf-8")
        monkeypatch.setattr(service_module, "GATEWAY_CONFIG_PATH", gateway_path)
        monkeypatch.setattr(service_module, "LLM_SERVE_CONFIG_PATH", llm_path)
        monkeypatch.setattr(service_module, "LEGACY_SERVE_CONFIG_PATH", llm_path)


def test_root_redirects_to_ui() -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui"


def test_ui_home_renders_backend_panel() -> None:
    response = client.get("/ui")
    assert response.status_code == 200
    assert "Conti MCP Console" in response.text
    assert "Panel operativo mínimo" in response.text


def test_ui_tools_renders_tool_runner() -> None:
    response = client.get("/ui/tools")
    assert response.status_code == 200
    assert "Tool runner" in response.text
    assert "run_salvar" in response.text


def test_ui_rules_renders_onboarding_and_rules() -> None:
    response = client.get("/ui/rules")
    assert response.status_code == 200
    assert "Onboarding" in response.text
    assert "Rules efectivas" in response.text


def test_ui_nanobots_renders_gateway_and_llm_sections(monkeypatch, tmp_path) -> None:
    _patch_nanobot_paths(monkeypatch, tmp_path)
    response = client.get("/ui/nanobots")
    assert response.status_code == 200
    assert "Gateway" in response.text
    assert "LLM" in response.text


def test_ui_nanobots_gateway_save_redirects(monkeypatch, tmp_path) -> None:
    _patch_nanobot_paths(monkeypatch, tmp_path)
    response = client.post(
        "/ui/nanobots/gateway",
        data={
            "model": "gpt-4",
            "provider": "copilot-local",
            "temperature": "0.2",
            "maxToolIterations": "10",
            "maxTokens": "8192",
            "contextWindowTokens": "65536",
            "api_base": "http://host.docker.internal:3030/v1",
            "api_key": "dummy",
            "telegram_token": "abc",
            "allowFrom": "luisdalmasso",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/ui/nanobots")
