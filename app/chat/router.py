"""Chat API router — POST /v1/chat endpoint."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.chat.memory import get_session_manager
from app.chat.orchestrator import get_orchestrator
from app.tenants.registry import get_tenant_registry

log = logging.getLogger("conti.chat_router")

router = APIRouter(prefix="/v1", tags=["chat"])


class ChatRequest(BaseModel):
    """Incoming chat message."""
    tenant_id: str = Field(..., description="Tenant identifier (e.g. 'catolico')")
    session_id: str = Field(..., description="Unique session/conversation ID")
    message: str = Field(..., description="User message text")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata (channel, user_id, etc.)",
    )


class ChatResponse(BaseModel):
    """Chat response."""
    response: str
    intent: str | None = None
    tenant_id: str
    session_id: str


@router.post("/chat", response_model=ChatResponse)
async def post_chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message through the tenant's orchestrator."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    orchestrator = get_orchestrator()
    result = await orchestrator.process_message(
        tenant_id=request.tenant_id,
        session_id=request.session_id,
        message=request.message,
        metadata=request.metadata,
    )
    return ChatResponse(**result)


@router.get("/chat/tenants")
def get_tenants() -> dict:
    """List available chat tenants."""
    registry = get_tenant_registry()
    return {
        "status": "ok",
        "tenants": registry.list_tenants(),
    }


@router.get("/chat/health")
def chat_health() -> dict:
    """Check Redis connectivity for chat."""
    memory = get_session_manager()
    redis_ok = memory.ping()
    return {
        "status": "ok" if redis_ok else "error",
        "redis": redis_ok,
    }


@router.delete("/chat/{tenant_id}/{session_id}")
def delete_session(tenant_id: str, session_id: str) -> dict:
    """Clear a chat session."""
    memory = get_session_manager()
    memory.clear_session(tenant_id, session_id)
    return {"status": "ok", "cleared": f"{tenant_id}/{session_id}"}
