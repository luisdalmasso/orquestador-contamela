from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from app.config.models import AppConfig
from app.utils.paths import REPO_ROOT, resolve_runtime_path


def load_rules_bundle(config: AppConfig) -> dict[str, object]:
    main_path = resolve_runtime_path(config.paths.rules_file)
    mcp_path = REPO_ROOT / "docs" / "rules_mcp.md"

    main_content = _read_optional_markdown(main_path)
    mcp_content = _read_optional_markdown(mcp_path)
    combined = "\n\n".join(part for part in [main_content, mcp_content] if part.strip())

    source_paths = [str(main_path)]
    if mcp_path.exists():
        source_paths.append(str(mcp_path))

    return {
        "configured_path": config.paths.rules_file,
        "resolved_path": str(main_path),
        "source_paths": source_paths,
        "exists": main_path.exists(),
        "content": combined,
        "raw": {
            "main": main_content,
            "mcp": mcp_content,
        },
        "checksum": sha256(combined.encode("utf-8")).hexdigest() if combined else "",
        "mtime": _mtime_or_none(main_path),
    }


def _read_optional_markdown(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _mtime_or_none(path: Path) -> float | None:
    if not path.exists():
        return None
    return path.stat().st_mtime
