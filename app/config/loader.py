from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from app.config.models import AppConfig
from app.utils.paths import resolve_runtime_path


DEFAULT_CONFIG_PATH = "/contenedores/conti-backend/config/app_config.json"
CONTAINER_CONFIG_PATH = "/app/config/app_config.json"
ENV_CONFIG_PATH = "CONTI_BACKEND_CONFIG"


def get_config_path() -> Path:
    configured_path = os.environ.get(ENV_CONFIG_PATH)
    if configured_path:
        return resolve_runtime_path(configured_path)

    container_path = resolve_runtime_path(CONTAINER_CONFIG_PATH)
    if container_path.exists():
        return container_path

    return resolve_runtime_path(DEFAULT_CONFIG_PATH)


@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    config_path = get_config_path()
    if not config_path.exists():
        return AppConfig()

    with config_path.open("r", encoding="utf-8") as config_file:
        raw_config = json.load(config_file)
    return AppConfig.model_validate(raw_config)


def reload_config() -> AppConfig:
    load_config.cache_clear()
    return load_config()
