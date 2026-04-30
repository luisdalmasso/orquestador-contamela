from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_runtime_path(configured_path: str) -> Path:
    configured = Path(configured_path)
    if configured.exists():
        return configured

    path_text = configured.as_posix()
    if path_text.startswith("/app/"):
        candidate = REPO_ROOT / path_text.removeprefix("/app/")
        if candidate.exists():
            return candidate

    if not configured.is_absolute():
        candidate = REPO_ROOT / configured
        if candidate.exists():
            return candidate

    return configured
