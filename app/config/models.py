from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.utils.paths import resolve_runtime_path


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 9001
    reload: bool = False


class LLMEmulationConfig(BaseModel):
    enabled: bool = True
    default_model: str = "conti-default"
    streaming_enabled: bool = True
    mode: str = "nanobot_serve"
    serve_profile: str = "conti-llm-serve"
    serve_base_url: str = "http://127.0.0.1:8765"


class PathsConfig(BaseModel):
    home_root: str = "/home/nanobot"
    development_repo: str = "/desarrollo"
    production_repo: str = "/compose"
    onboarding_file: str = "/app/docs/onboarding.md"
    onboarding_brief_file: str = "/app/docs/onboarding_brief.md"
    rules_file: str = "/app/docs/rules.md"

    def as_dict(self) -> dict[str, str]:
        return {
            "home_root": self.home_root,
            "development_repo": self.development_repo,
            "production_repo": self.production_repo,
            "onboarding_file": self.onboarding_file,
            "onboarding_brief_file": self.onboarding_brief_file,
            "rules_file": self.rules_file,
        }


class UIConfig(BaseModel):
    enabled: bool = True
    title: str = "Conti MCP Console"


class ProvidersConfig(BaseModel):
    active: str = "openai_compatible"
    openai_compatible: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm_emulation: LLMEmulationConfig = Field(default_factory=LLMEmulationConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    ui: UIConfig = Field(default_factory=UIConfig)

    def redacted_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        openai_compatible = data.get("providers", {}).get("openai_compatible", {})
        for key in list(openai_compatible.keys()):
            if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower():
                openai_compatible[key] = "***REDACTED***"
        return data

    def resolved_paths(self) -> dict[str, dict[str, Any]]:
        path_map: dict[str, dict[str, Any]] = {}
        for key, value in self.paths.as_dict().items():
            path = resolve_runtime_path(value)
            path_map[key] = {
                "path": str(path),
                "exists": path.exists(),
                "is_dir": path.is_dir(),
                "is_file": path.is_file(),
            }
        return path_map
