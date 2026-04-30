from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from app.config.models import AppConfig
from app.utils.security import resolve_allowed_path


def search_code_literal(config: AppConfig, arguments: dict) -> dict:
    return _search_literal(config, arguments, default_root=config.paths.development_repo)


def search_docs_literal(config: AppConfig, arguments: dict) -> dict:
    return _search_literal(config, arguments, default_root="/app/docs")


def grep_workspace(config: AppConfig, arguments: dict) -> dict:
    return _search_literal(config, arguments, default_root=config.paths.development_repo)


def _search_literal(config: AppConfig, arguments: dict, default_root: str) -> dict:
    query = arguments.get("query")
    if not query:
        raise ValueError("Se requiere 'query'")

    root = resolve_allowed_path(config, arguments.get("path", default_root))
    include_pattern = arguments.get("include", "*")
    use_regex = bool(arguments.get("regex", False))
    limit = int(arguments.get("limit", 50))

    matches: list[dict[str, object]] = []
    for file_path in _iter_files(root, include_pattern):
        content = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(content, start=1):
            found = bool(re.search(query, line)) if use_regex else query.lower() in line.lower()
            if found:
                matches.append(
                    {
                        "path": str(file_path),
                        "line": index,
                        "text": line,
                    }
                )
                if len(matches) >= limit:
                    return {"query": query, "matches": matches, "count": len(matches)}
    return {"query": query, "matches": matches, "count": len(matches)}


def _iter_files(root: Path, include_pattern: str):
    for path in root.rglob("*"):
        if path.is_file() and fnmatch.fnmatch(path.name, include_pattern):
            yield path
