"""Context writer — writes state/history/rule files to the tenant's context/ folder.

FastAPI writes these files BEFORE calling the tenant's nanobot serve.
The nanobot's SOUL.md instructs it to read them before responding.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("conti.context_writer")

TENANTS_ROOT = Path("/tenants")


class ContextWriter:
    """Writes context files that the tenant's nanobot reads."""

    def __init__(self, tenants_root: Path | None = None):
        self._root = tenants_root or TENANTS_ROOT

    def _context_dir(self, tenant_id: str) -> Path:
        return self._root / tenant_id / "context"

    def write_state(self, tenant_id: str, state: dict) -> None:
        """Write current session state as JSON."""
        path = self._context_dir(tenant_id) / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def write_history(self, tenant_id: str, history: list[dict]) -> None:
        """Write recent conversation history as markdown."""
        path = self._context_dir(tenant_id) / "history.md"
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = ["# Historial de conversación\n"]
        if not history:
            lines.append("(Sin mensajes previos)\n")
        else:
            for msg in history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                lines.append(f"**{role}**: {content}\n")

        path.write_text("\n".join(lines), encoding="utf-8")

    def write_rule_context(self, tenant_id: str, instruction: str) -> None:
        """Write the current turn instruction for the nanobot."""
        path = self._context_dir(tenant_id) / "rule_context.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Turno actual\n\n{instruction}\n",
            encoding="utf-8",
        )

    def write_all(
        self,
        tenant_id: str,
        state: dict,
        history: list[dict],
        instruction: str,
    ) -> None:
        """Write all context files in one call."""
        self.write_state(tenant_id, state)
        self.write_history(tenant_id, history)
        self.write_rule_context(tenant_id, instruction)
        log.debug("Context written for tenant %s", tenant_id)
