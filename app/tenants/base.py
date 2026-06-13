"""Tenant configuration models (Pydantic)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TenantConfig(BaseModel):
    """Configuration for a single chat tenant."""

    tenant_id: str
    strategy: str = "keyword"  # "keyword" | "rules_engine"
    nanobot_port: int = 8766
    chat_ttl: int = 1800       # Session TTL in seconds
    max_history: int = 30      # Max messages to keep in history
    rag_store: str = "default"

    # Keyword classification (strategy=keyword)
    keywords: dict[str, list[str]] = Field(default_factory=dict)

    # Per-intent instructions sent to nanobot
    instructions: dict[str, str] = Field(default_factory=dict)

    # Rules engine (strategy=rules_engine) — for future Odoo tenant
    state_schema: list[dict[str, str]] = Field(default_factory=list)
    rules: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def nanobot_base_url(self) -> str:
        """URL to this tenant's nanobot serve instance."""
        return f"http://127.0.0.1:{self.nanobot_port}"
