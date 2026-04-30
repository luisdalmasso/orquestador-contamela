from __future__ import annotations

from pathlib import Path

from app.config.models import AppConfig
from app.utils.paths import resolve_runtime_path


def allowed_roots(config: AppConfig) -> list[Path]:
    roots = [
        config.paths.home_root,
        config.paths.development_repo,
        config.paths.production_repo,
        "/app/docs",
        "/app/skills",
    ]
    return [resolve_runtime_path(path).resolve() for path in roots]


def resolve_allowed_path(config: AppConfig, requested_path: str) -> Path:
    candidate = resolve_runtime_path(requested_path)
    if not candidate.is_absolute():
        candidate = resolve_runtime_path(config.paths.development_repo) / candidate

    resolved_candidate = candidate.resolve(strict=False)
    for root in allowed_roots(config):
        if _is_relative_to(resolved_candidate, root):
            return resolved_candidate

    raise ValueError(f"Path fuera de roots permitidos: {requested_path}")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
