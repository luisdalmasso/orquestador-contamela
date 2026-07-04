from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse

from app.openhands_agent.service import openhands_service

log = logging.getLogger("conti.llm_router")

router = APIRouter(tags=["llm-emulation"])


@router.get("/v1")
@router.get("/v1/")
def get_v1_root() -> dict:
    return {
        "status": "ok",
        "compatible_with": ["openai-base-url", "legacy-backend-ai"],
        "backend": "openhands",
        "endpoints": {
            "models": "/v1/models",
            "chat_completions": "/v1/chat/completions",
            "responses": "/v1/responses",
        },
    }


@router.get("/v1/models")
def get_models() -> dict:
    """Devuelve el modelo configurado internamente (ignorando cualquier request)."""
    try:
        # Obtener el modelo configurado internamente
        models = openhands_service.list_models()
        # Forzar el modelo configurado (ej: mistral-small-latest)
        return {
            "object": "list",
            "data": [
                {
                    "id": models.get("default_model", "mistral-small-latest"),
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": "conti-backend",
                }
            ],
        }
    except Exception as exc:
        log.error("[ROUTER] Error listando modelos OpenHands: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502, detail=f"Error listando modelos del stack OpenHands: {exc}"
        )


@router.post("/v1/chat/completions")
async def post_chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cuerpo JSON inválido: {exc}")

    # Ignorar el campo 'model' en la request y usar el modelo configurado internamente
    if "model" in body:
        log.warning(
            "[ROUTER] Campo 'model' ignorado. Usando modelo configurado internamente."
        )
        body.pop("model")

    # Leer el circuito desde el header HTTP (X-Circuit-ID)
    circuit = request.headers.get("X-Circuit-ID", "libre")  # Default: libre
    body["circuit"] = circuit

    # Session management: X-Session-ID header
    # Si el cliente envía un session_id, se reutiliza la misma sesión omp.
    # Si no se envía, se genera uno nuevo (nueva sesión).
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        body["session_id"] = session_id
        log.info("[ROUTER] session_id=%s (reutilizando sesión)", session_id)
    else:
        # No hay session_id → es el primer mensaje de una nueva sesión
        log.info("[ROUTER] sin session_id → nueva sesión")

    auth_header = request.headers.get("Authorization", "")

    if body.get("stream"):
        log.info("[ROUTER] /v1/chat/completions (stream=true) -> OpenHands")

        async def stream_generator():
            try:
                async for chunk in openhands_service.stream_chat_completions(
                    body, auth_header
                ):
                    yield chunk
            except Exception as exc:
                log.error(
                    "[ROUTER] Error en streaming OpenHands: %s", exc, exc_info=True
                )
                err_payload = f'data: {{"error": "{exc}"}}\n\n'.encode("utf-8")
                yield err_payload

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    log.info("[ROUTER] /v1/chat/completions (sync) -> OpenHands")
    try:
        result = openhands_service.run_task(body)
    except Exception as exc:
        log.error("[ROUTER] Error ejecutando OpenHands: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502, detail=f"Error ejecutando OpenHands: {exc}"
        )
    return JSONResponse(content=result)


@router.post("/v1/responses")
async def post_responses(request: Request):
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cuerpo JSON inválido: {exc}")

    if body.get("stream"):
        raise HTTPException(
            status_code=400, detail="stream=true no está soportado aún en /v1/responses"
        )

    log.info("[ROUTER] /v1/responses -> OpenHands")
    try:
        result = openhands_service.run_task(body)
    except Exception as exc:
        log.error("[ROUTER] Error ejecutando OpenHands: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502, detail=f"Error ejecutando OpenHands: {exc}"
        )
    return JSONResponse(content=result)


@router.get("/llm/backend/status")
def get_llm_backend_status() -> dict:
    try:
        return {"status": "ok", "backend": openhands_service.backend_status()}
    except Exception as exc:
        return {"status": "degraded", "backend": str(exc)}


@router.post("/llm/backend/reload")
def post_llm_backend_reload() -> dict:
    try:
        return {"status": "reloaded", "backend": openhands_service.reload_backend()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
