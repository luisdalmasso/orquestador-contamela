from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.llm_emulation.models import ChatCompletionRequest, ResponsesRequest
from app.llm_emulation.nanobot_serve_bridge import NanobotServeError
from app.llm_emulation.streaming import passthrough_stream
from app.services.llm_service import llm_service
from app.services.nanobot_serve_service import nanobot_serve_service

log = logging.getLogger("conti.llm_router")

router = APIRouter(tags=["llm-emulation"])


@router.get("/v1")
@router.get("/v1/")
def get_v1_root() -> dict:
    return {
        "status": "ok",
        "compatible_with": ["openai-base-url", "legacy-backend-ai"],
        "endpoints": {
            "models": "/v1/models",
            "chat_completions": "/v1/chat/completions",
            "responses": "/v1/responses",
        },
    }


@router.get("/v1/models")
def get_models() -> dict:
    try:
        return llm_service.get_models()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/v1/chat/completions")
def post_chat_completions(request: ChatCompletionRequest):
    payload = request.model_dump(exclude_none=True)
    log.debug(
        "[ROUTER] request recibido de Kilocode/cliente:\n%s",
        json.dumps(payload, ensure_ascii=False, indent=2),
    )
    try:
        if payload.get("stream"):
            log.debug("[ROUTER] modo streaming activado")
            return StreamingResponse(
                passthrough_stream(llm_service.stream_chat_completions(payload)),
                media_type="text/event-stream",
            )
        result = llm_service.chat_completions(payload)
        log.debug(
            "[ROUTER] respuesta enviada al cliente:\n%s",
            json.dumps(result, ensure_ascii=False, indent=2),
        )
        return result
    except NanobotServeError as exc:
        log.warning("[ROUTER] NanobotServeError %s: %s", exc.status_code, exc.detail)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ValueError as exc:
        log.warning("[ROUTER] ValueError: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/v1/responses")
def post_responses(request: ResponsesRequest):
    payload = request.model_dump(exclude_none=True)
    if payload.get("stream"):
        raise HTTPException(status_code=400, detail="stream=true no está soportado aún en /v1/responses")
    try:
        return llm_service.responses(payload)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/llm/backend/status")
def get_llm_backend_status() -> dict:
    return {
        "status": "ok",
        "backend": nanobot_serve_service.backend_status(),
    }


@router.post("/llm/backend/reload")
def post_llm_backend_reload() -> dict:
    return {
        "status": "reloaded",
        "backend": nanobot_serve_service.reload_backend(),
    }
