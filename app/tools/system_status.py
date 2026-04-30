from __future__ import annotations

from app.config.loader import load_config, reload_config
from app.services.health_service import HealthService


def health_check(_: dict) -> dict:
    config = load_config()
    return HealthService(config).build_status()


def reload_backend_config(_: dict) -> dict:
    config = reload_config()
    return {
        "status": "reloaded",
        "config": config.redacted_dict(),
    }
