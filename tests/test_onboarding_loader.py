import json

from fastapi.testclient import TestClient

from app.config.loader import reload_config
from app.main import app


client = TestClient(app)


def test_onboarding_endpoint_uses_external_file(tmp_path, monkeypatch) -> None:
    onboarding_file = tmp_path / "onboarding.md"
    onboarding_file.write_text("Hola {development_repo}", encoding="utf-8")
    onboarding_brief_file = tmp_path / "onboarding_brief.md"
    onboarding_brief_file.write_text("Brief {serve_profile}", encoding="utf-8")
    rules_file = tmp_path / "rules.md"
    rules_file.write_text("# Rules\n", encoding="utf-8")
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

    response = client.get("/onboarding")
    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == "Hola /desarrollo"

    brief_response = client.get("/onboarding?brief=true")
    assert brief_response.status_code == 200
    assert brief_response.json()["content"] == "Brief conti-llm-serve"
