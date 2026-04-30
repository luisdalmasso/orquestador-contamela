import json

from fastapi.testclient import TestClient

from app.config.loader import reload_config
from app.main import app


client = TestClient(app)


def test_rules_endpoints_load_and_reload_external_files(tmp_path, monkeypatch) -> None:
    onboarding_file = tmp_path / "onboarding.md"
    onboarding_file.write_text("hola", encoding="utf-8")
    onboarding_brief_file = tmp_path / "onboarding_brief.md"
    onboarding_brief_file.write_text("brief", encoding="utf-8")
    rules_file = tmp_path / "rules.md"
    rules_file.write_text("# Rules\n\nPrimera version", encoding="utf-8")
    config_file = tmp_path / "app_config.json"
    config_file.write_text(
        json.dumps(
            {
                "paths": {
                    "onboarding_file": str(onboarding_file),
                    "onboarding_brief_file": str(onboarding_brief_file),
                    "rules_file": str(rules_file),
                    "home_root": "/home/nanobot",
                    "development_repo": "/desarrollo",
                    "production_repo": "/compose"
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CONTI_BACKEND_CONFIG", str(config_file))
    reload_config()

    response = client.get("/rules")
    assert response.status_code == 200
    payload = response.json()
    assert "Primera version" in payload["content"]
    assert "Rules MCP" in payload["content"]

    rules_file.write_text("# Rules\n\nSegunda version", encoding="utf-8")
    reload_response = client.post("/rules/reload")
    assert reload_response.status_code == 200
    assert "Segunda version" in reload_response.json()["content"]

    raw_response = client.get("/rules/raw")
    assert raw_response.status_code == 200
    assert "Segunda version" in raw_response.json()["raw"]["main"]