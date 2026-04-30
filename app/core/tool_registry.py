from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.tool_models import ToolDefinition, ToolHandler


@dataclass(slots=True)
class RegisteredTool:
    definition: ToolDefinition
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        self._tools[definition.name] = RegisteredTool(definition=definition, handler=handler)

    def list_tools(self) -> list[dict[str, Any]]:
        return [registered.definition.model_dump() for registered in self._tools.values()]

    def call(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        if tool_name not in self._tools:
            raise KeyError(f"Tool no registrada: {tool_name}")
        payload = arguments or {}
        return self._tools[tool_name].handler(payload)
