"""Redis session manager — stores chat history and state per tenant/session.

Uses Redis DB 3. Keys follow the pattern:
  chat:{tenant_id}:{session_id}:history   → JSON list of messages
  chat:{tenant_id}:{session_id}:state     → JSON dict of state flags
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import redis

log = logging.getLogger("conti.memory")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis_odoo")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_CHAT_DB", "10"))


class RedisSessionManager:
    """Manages chat sessions in Redis."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        db: int | None = None,
    ):
        self._host = host or REDIS_HOST
        self._port = port or REDIS_PORT
        self._db = db or REDIS_DB
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                decode_responses=True,
                socket_connect_timeout=5,
            )
        return self._client

    def _key(self, tenant_id: str, session_id: str, suffix: str) -> str:
        return f"chat:{tenant_id}:{session_id}:{suffix}"

    # ── History ──────────────────────────────────────────────────────────

    def get_history(
        self, tenant_id: str, session_id: str, max_messages: int = 30
    ) -> list[dict[str, str]]:
        """Get conversation history (last N messages)."""
        key = self._key(tenant_id, session_id, "history")
        try:
            raw = self.client.get(key)
            if not raw:
                return []
            messages = json.loads(raw)
            return messages[-max_messages:]
        except Exception as exc:
            log.error("Failed to get history %s: %s", key, exc)
            return []

    def append_message(
        self,
        tenant_id: str,
        session_id: str,
        role: str,
        content: str,
        ttl: int = 1800,
        max_messages: int = 50,
    ) -> None:
        """Append a message to the conversation history."""
        key = self._key(tenant_id, session_id, "history")
        try:
            history = self.get_history(tenant_id, session_id, max_messages=max_messages)
            history.append({"role": role, "content": content})
            # Trim to max
            if len(history) > max_messages:
                history = history[-max_messages:]
            self.client.setex(key, ttl, json.dumps(history, ensure_ascii=False))
        except Exception as exc:
            log.error("Failed to append message %s: %s", key, exc)

    # ── State (flags) ────────────────────────────────────────────────────

    def get_state(self, tenant_id: str, session_id: str) -> dict[str, Any]:
        """Get session state (flags, data)."""
        key = self._key(tenant_id, session_id, "state")
        try:
            raw = self.client.get(key)
            if not raw:
                return {}
            return json.loads(raw)
        except Exception as exc:
            log.error("Failed to get state %s: %s", key, exc)
            return {}

    def set_state(
        self, tenant_id: str, session_id: str, state: dict[str, Any], ttl: int = 1800
    ) -> None:
        """Set session state."""
        key = self._key(tenant_id, session_id, "state")
        try:
            self.client.setex(key, ttl, json.dumps(state, ensure_ascii=False))
        except Exception as exc:
            log.error("Failed to set state %s: %s", key, exc)

    def update_state(
        self, tenant_id: str, session_id: str, updates: dict[str, Any], ttl: int = 1800
    ) -> dict[str, Any]:
        """Merge updates into existing state and return the new state."""
        state = self.get_state(tenant_id, session_id)
        state.update(updates)
        self.set_state(tenant_id, session_id, state, ttl)
        return state

    # ── Cleanup ──────────────────────────────────────────────────────────

    def clear_session(self, tenant_id: str, session_id: str) -> None:
        """Delete all data for a session."""
        for suffix in ("history", "state"):
            key = self._key(tenant_id, session_id, suffix)
            self.client.delete(key)

    def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            return self.client.ping()
        except Exception:
            return False


# Singleton
_manager: RedisSessionManager | None = None


def get_session_manager() -> RedisSessionManager:
    global _manager
    if _manager is None:
        _manager = RedisSessionManager()
    return _manager
