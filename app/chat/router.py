"""Chat API router — POST /v1/chat endpoint."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.chat.memory import get_session_manager
from app.chat.orchestrator import get_orchestrator
from app.services.tts_service import get_tts_service
from app.services.transcription_service import get_transcription_service
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

class TenantListResponse(BaseModel):
    """Lista de tenants disponibles."""
    status: str = Field(default="ok", description="Estado de la respuesta")
    tenants: list[str] = Field(..., description="Lista de identificadores de tenant (ej. ['catolico', 'odoo'])")

class ChatHealthResponse(BaseModel):
    """Estado de salud del sistema de chat."""
    status: str = Field(..., description="Estado general (ok/error)")
    redis: bool = Field(..., description="Conectividad con la base de datos Redis")

class DeleteSessionResponse(BaseModel):
    """Resultado de la limpieza de sesión."""
    status: str = Field(default="ok")
    cleared: str = Field(..., description="Identificador de la sesión limpiada")


class TranscriptionResponse(BaseModel):
    """Resultado de la transcripción de audio."""
    transcript: str = Field(..., description="Texto transcripto")
    language: str = Field(..., description="Idioma detectado o solicitado")
    duration: float = Field(default=0.0, description="Duración estimada del audio en segundos")
    engine: str = Field(..., description="Motor de transcripción utilizado")
    model: str = Field(..., description="Modelo STT utilizado")


class TTSRequest(BaseModel):
    """Solicitud de síntesis de voz."""
    text: str = Field(..., description="Texto a sintetizar")
    tenant_id: str = Field(default="odoo", description="Tenant/perfil para resolver la voz")


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Procesar un mensaje de chat",
    description=(
        "Recibe un mensaje de usuario para un tenant específico, actúa como proxy "
        "transparente hacia el Nanobot correspondiente y devuelve la respuesta de IA."
    )
)
async def post_chat(
    request: ChatRequest,
    x_mesa_id: str | None = Header(default=None, alias="X-Mesa-Id"),
) -> ChatResponse:
    """Process a chat message through the tenant's orchestrator."""
    message_text = request.message.strip()
    
    # Allow empty message if there are attachments
    has_attachments = bool(request.metadata.get("attachments"))
    if not message_text and not has_attachments:
        # Evita el error 400 si el usuario solo interactúa con botones
        message_text = "[Interacción del usuario]"

    if request.tenant_id == "resto":
        if x_mesa_id:
            request.metadata.setdefault("id_mesa", x_mesa_id)
            request.metadata.setdefault("mesaid", x_mesa_id)
        elif request.metadata.get("id_mesa"):
            request.metadata.setdefault("mesaid", str(request.metadata["id_mesa"]))
        elif request.metadata.get("mesaid"):
            request.metadata.setdefault("id_mesa", str(request.metadata["mesaid"]))

    orchestrator = get_orchestrator()
    result = await orchestrator.process_message(
        tenant_id=request.tenant_id,
        session_id=request.session_id,
        message=message_text,
        metadata=request.metadata,
    )
    return ChatResponse(**result)


@router.get(
    "/chat/tenants",
    response_model=TenantListResponse,
    summary="Listar tenants disponibles"
)
def get_tenants() -> dict:
    """List available chat tenants."""
    registry = get_tenant_registry()
    return {
        "status": "ok",
        "tenants": registry.list_tenants(),
    }


@router.get(
    "/chat/health",
    response_model=ChatHealthResponse,
    summary="Verificar salud de memoria (Redis)"
)
def chat_health() -> dict:
    """Check Redis connectivity for chat."""
    memory = get_session_manager()
    redis_ok = memory.ping()
    return {
        "status": "ok" if redis_ok else "error",
        "redis": redis_ok,
    }


@router.delete(
    "/chat/{tenant_id}/{session_id}",
    response_model=DeleteSessionResponse,
    summary="Limpiar sesión de chat"
)
def delete_session(tenant_id: str, session_id: str) -> dict:
    """Clear a chat session."""
    memory = get_session_manager()
    memory.clear_session(tenant_id, session_id)
    return {"status": "ok", "cleared": f"{tenant_id}/{session_id}"}


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    summary="Transcribir audio localmente",
    description="Recibe un archivo de audio y devuelve la transcripción usando Whisper local.",
)
async def post_transcribe(
    audio: UploadFile = File(..., description="Archivo de audio a transcribir"),
    language: str = Form(default="es"),
) -> TranscriptionResponse:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="El archivo de audio está vacío")

    try:
        result = get_transcription_service().transcribe_bytes(
            audio_bytes,
            filename=audio.filename,
            language=language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("Error transcribiendo audio local")
        raise HTTPException(status_code=500, detail=f"No se pudo transcribir el audio: {exc}") from exc

    return TranscriptionResponse(**result)


@router.post(
    "/tts",
    summary="Sintetizar voz",
    description="Genera audio TTS usando la configuración Hermes del tenant/perfil.",
    responses={200: {"content": {"audio/mpeg": {}}}},
)
async def post_tts(request: TTSRequest) -> Response:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="El texto está vacío")
    try:
        audio_bytes, media_type = await get_tts_service().synthesize(
            text=text,
            tenant_id=request.tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("Error generando TTS")
        raise HTTPException(status_code=500, detail=f"No se pudo sintetizar audio: {exc}") from exc
    return Response(content=audio_bytes, media_type=media_type)
