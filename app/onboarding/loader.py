from __future__ import annotations

from pathlib import Path

from app.config.models import AppConfig
from app.utils.paths import resolve_runtime_path


def _build_context(config: AppConfig) -> dict[str, str | int | bool]:
    return {
        "workspace_root": config.paths.development_repo,
        "tools_count": 0,
        "active_provider": config.providers.active,
        "gateway_port": config.server.port,
        "web_ui_url": f"http://127.0.0.1:{config.server.port}/ui",
        "home_root": config.paths.home_root,
        "development_repo": config.paths.development_repo,
        "production_repo": config.paths.production_repo,
        "serve_profile": config.llm_emulation.serve_profile,
    }


def load_onboarding_text(config: AppConfig, brief: bool = False) -> dict[str, str | bool]:
    configured_path = (
        config.paths.onboarding_brief_file if brief else config.paths.onboarding_file
    )
    resolved_path = resolve_runtime_path(configured_path)
    content = _read_optional_markdown(resolved_path)
    rendered = content.format(**_build_context(config)) if content else ""
    return {
        "kind": "brief" if brief else "full",
        "configured_path": configured_path,
        "resolved_path": str(resolved_path),
        "exists": resolved_path.exists(),
        "content": rendered,
    }


def _read_optional_markdown(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
