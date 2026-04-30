import json
from pathlib import Path

from app.services import nanobot_config_service as service_module
from app.services.nanobot_config_service import NanobotConfigService


def test_gateway_payload_reads_selected_provider(tmp_path: Path, monkeypatch) -> None:
    gateway_path = tmp_path / "config.json"
    gateway_path.write_text(
        json.dumps(
            {
                "agents": {"defaults": {"model": "gpt-4", "provider": "copilot-local", "temperature": 0.2, "maxToolIterations": 10, "maxTokens": 8192, "contextWindowTokens": 65536}},
                "providers": {"copilot-local": {"apiBase": "http://host.docker.internal:3030/v1", "apiKey": "dummy"}},
                "channels": {"telegram": {"token": "abc", "allowFrom": ["luis"]}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(service_module, "GATEWAY_CONFIG_PATH", gateway_path)

    payload = NanobotConfigService().get_gateway_config()
    assert payload["editable"]["provider"] == "copilot-local"
    assert payload["editable"]["api_base"] == "http://host.docker.internal:3030/v1"
    assert payload["editable"]["telegram_token"] == "abc"
    assert payload["editable"]["allowFrom"] == ["luis"]


def test_save_llm_config_creates_dedicated_file(tmp_path: Path, monkeypatch) -> None:
    gateway_path = tmp_path / "config.json"
    llm_path = tmp_path / "llm_serve_config.json"
    legacy_path = tmp_path / ".nanobot" / "nanobot" / "config.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        json.dumps(
            {
                "agents": {"defaults": {"model": "old-model", "provider": "openai", "temperature": 0.3, "maxToolIterations": 20, "maxTokens": 4096, "contextWindowTokens": 8192}},
                "providers": {"openai": {"apiBase": "https://old.example/v1", "apiKey": "old-key"}},
            }
        ),
        encoding="utf-8",
    )
    gateway_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(service_module, "GATEWAY_CONFIG_PATH", gateway_path)
    monkeypatch.setattr(service_module, "LLM_SERVE_CONFIG_PATH", llm_path)
    monkeypatch.setattr(service_module, "LEGACY_SERVE_CONFIG_PATH", legacy_path)

    payload = {
        "model": "gpt-4",
        "provider": "copilot-local",
        "temperature": "0.2",
        "maxToolIterations": "10",
        "maxTokens": "8192",
        "contextWindowTokens": "65536",
        "api_base": "http://host.docker.internal:3030/v1",
        "api_key": "dummy",
    }
    saved = NanobotConfigService().save_llm_config(payload)

    assert llm_path.exists()
    data = json.loads(llm_path.read_text(encoding="utf-8"))
    assert data["agents"]["defaults"]["provider"] == "copilot-local"
    assert data["providers"]["copilot-local"]["apiBase"] == "http://host.docker.internal:3030/v1"
    assert saved["editable"]["model"] == "gpt-4"


def test_openai_model_is_normalized_without_provider_prefix(tmp_path: Path, monkeypatch) -> None:
    gateway_path = tmp_path / "config.json"
    llm_path = tmp_path / "llm_serve_config.json"
    legacy_path = tmp_path / ".nanobot" / "nanobot" / "config.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        json.dumps(
            {
                "agents": {"defaults": {"model": "openai/kilo-auto/free", "provider": "openai", "temperature": 0.3, "maxToolIterations": 20, "maxTokens": 4096, "contextWindowTokens": 8192}},
                "providers": {"openai": {"apiBase": "https://api.kilo.ai/api/gateway", "apiKey": "key"}},
            }
        ),
        encoding="utf-8",
    )
    gateway_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(service_module, "GATEWAY_CONFIG_PATH", gateway_path)
    monkeypatch.setattr(service_module, "LLM_SERVE_CONFIG_PATH", llm_path)
    monkeypatch.setattr(service_module, "LEGACY_SERVE_CONFIG_PATH", legacy_path)

    service = NanobotConfigService()
    loaded = service.get_llm_config()
    assert loaded["editable"]["model"] == "kilo-auto/free"

    saved = service.save_llm_config(
        {
            "model": "openai/kilo-auto/free",
            "provider": "openai",
            "temperature": "0.3",
            "maxToolIterations": "20",
            "maxTokens": "8192",
            "contextWindowTokens": "65536",
            "api_base": "https://api.kilo.ai/api/gateway",
            "api_key": "key",
        }
    )
    data = json.loads(llm_path.read_text(encoding="utf-8"))
    assert data["agents"]["defaults"]["model"] == "kilo-auto/free"
    assert saved["editable"]["model"] == "kilo-auto/free"
