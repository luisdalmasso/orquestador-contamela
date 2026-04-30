from pathlib import Path

from app.config import loader


def test_get_config_path_prefers_env(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "custom.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(loader.ENV_CONFIG_PATH, str(config_path))
    assert loader.get_config_path() == config_path


def test_get_config_path_falls_back_to_container_path(monkeypatch, tmp_path: Path) -> None:
    container_path = tmp_path / "app_config.json"
    container_path.write_text("{}", encoding="utf-8")
    monkeypatch.delenv(loader.ENV_CONFIG_PATH, raising=False)
    monkeypatch.setattr(loader, "CONTAINER_CONFIG_PATH", str(container_path))
    monkeypatch.setattr(loader, "DEFAULT_CONFIG_PATH", str(tmp_path / "missing.json"))
    assert loader.get_config_path() == container_path


def test_get_config_path_falls_back_to_default(monkeypatch, tmp_path: Path) -> None:
    default_path = tmp_path / "default.json"
    monkeypatch.delenv(loader.ENV_CONFIG_PATH, raising=False)
    monkeypatch.setattr(loader, "CONTAINER_CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setattr(loader, "DEFAULT_CONFIG_PATH", str(default_path))
    assert loader.get_config_path() == default_path
