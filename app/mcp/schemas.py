from __future__ import annotations

from pydantic import BaseModel, Field


class MCPCallRequest(BaseModel):
    tool: str
    arguments: dict = Field(default_factory=dict)
