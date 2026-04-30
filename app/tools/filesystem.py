from __future__ import annotations

from pathlib import Path

from app.config.models import AppConfig
from app.utils.security import resolve_allowed_path


def list_files(config: AppConfig, arguments: dict) -> dict:
    requested_path = arguments.get("path", config.paths.development_repo)
    resolved = resolve_allowed_path(config, requested_path)
    if not resolved.exists():
        raise ValueError(f"No existe la ruta: {requested_path}")
    if not resolved.is_dir():
        raise ValueError(f"La ruta no es un directorio: {requested_path}")

    children = sorted(
        child.name + ("/" if child.is_dir() else "")
        for child in resolved.iterdir()
    )
    return {
        "path": str(resolved),
        "entries": children,
    }


def read_file(config: AppConfig, arguments: dict) -> dict:
    requested_path = arguments.get("path")
    if not requested_path:
        raise ValueError("Se requiere 'path'")

    start_line = int(arguments.get("start_line", 1))
    end_line = int(arguments.get("end_line", start_line + 199))
    resolved = resolve_allowed_path(config, requested_path)
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"Archivo no encontrado: {requested_path}")

    lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = lines[start_line - 1:end_line]
    return {
        "path": str(resolved),
        "start_line": start_line,
        "end_line": min(end_line, len(lines)),
        "content": "\n".join(selected),
    }


def file_exists(config: AppConfig, arguments: dict) -> dict:
    requested_path = arguments.get("path")
    if not requested_path:
        raise ValueError("Se requiere 'path'")
    resolved = resolve_allowed_path(config, requested_path)
    return {
        "path": str(resolved),
        "exists": resolved.exists(),
        "is_file": resolved.is_file(),
        "is_dir": resolved.is_dir(),
    }


def get_code_context(config: AppConfig, arguments: dict) -> dict:
    requested_path = arguments.get("path")
    if not requested_path:
        raise ValueError("Se requiere 'path'")
    line_number = int(arguments.get("line", 1))
    context = int(arguments.get("context", 3))
    resolved = resolve_allowed_path(config, requested_path)
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"Archivo no encontrado: {requested_path}")

    lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
    start_line = max(1, line_number - context)
    end_line = min(len(lines), line_number + context)
    selected = lines[start_line - 1:end_line]
    return {
        "path": str(resolved),
        "line": line_number,
        "start_line": start_line,
        "end_line": end_line,
        "content": "\n".join(selected),
    }
