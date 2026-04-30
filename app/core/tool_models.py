from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    name: str
    description: str
    category: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    visibility: str = "public"
    is_enabled: bool = True
    tags: list[str] = Field(default_factory=list)


class ToolCallRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    success: bool
    tool: str
    result: Any = None
    error: str | None = None


ToolHandler = Callable[[dict[str, Any]], Any]
