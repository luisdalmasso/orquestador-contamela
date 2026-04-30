from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    temperature: float | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


class ResponsesRequest(BaseModel):
    model: str | None = None
    input: Any
    stream: bool = False
    metadata: dict[str, Any] | None = None
