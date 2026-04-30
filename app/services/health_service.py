from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config.models import AppConfig


class HealthService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def build_status(self) -> dict[str, Any]:
        serve_url = self._config.llm_emulation.serve_base_url
        return {
            "status": "ok",
            "service": "conti-backend",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "llm_backend": {
                "mode": self._config.llm_emulation.mode,
                "serve_profile": self._config.llm_emulation.serve_profile,
                "serve_base_url": serve_url,
                "configured": bool(serve_url),
            },
            "paths": self._config.resolved_paths(),
            "workspace": {
                "home_root": str(Path(self._config.paths.home_root)),
                "development_repo": str(Path(self._config.paths.development_repo)),
                "production_repo": str(Path(self._config.paths.production_repo)),
            },
        }
