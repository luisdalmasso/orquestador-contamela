from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.tool_models import ToolCallResponse
from app.mcp.schemas import MCPCallRequest
from app.services.registry_service import registry_service


router = APIRouter(prefix="/mcp", tags=["mcp"])


# --- Modelos de Respuesta para Swagger ---
class MCPRootResponse(BaseModel):
    status: str = Field(default="ok")
    transport: str = Field(..., description="Transporte utilizado (ej. http-json+sse)")
    compatible_with: list[str] = Field(..., description="Lista de clientes compatibles")
    endpoints: dict[str, str] = Field(..., description="Mapa de endpoints disponibles")
    tools_count: int = Field(..., description="Cantidad de herramientas registradas")

class MCPToolItem(BaseModel):
    name: str = Field(..., description="Nombre de la herramienta")
    description: str = Field(default="", description="Descripción funcional de la herramienta")
    inputSchema: dict[str, Any] = Field(..., description="JSON Schema de los argumentos esperados")

class MCPToolsResponse(BaseModel):
    status: str = Field(default="ok")
    tools: list[MCPToolItem] = Field(..., description="Lista de herramientas MCP disponibles")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "tools": [
                    {
                        "name": "read_file",
                        "description": "Lee el contenido de un archivo en el sistema.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"path": {"type": "string"}}
                        }
                    }
                ]
            }
        }
    }

class MCPExecuteResponse(BaseModel):
    success: bool = Field(..., description="Indica si la ejecución fue exitosa")
    result: Any | None = Field(default=None, description="Resultado de la ejecución de la herramienta")
    error: str | None = Field(default=None, description="Mensaje de error si la ejecución falló")


def _mcp_root_payload() -> dict:
    registry = registry_service()
    return {
        "status": "ok",
        "transport": "http-json+sse",
        "compatible_with": ["legacy-backend-ai", "vscode-mcp-url", "amazon-q", "kilocode", "cline"],
        "endpoints": {
            "root": "/mcp",
            "tools": "/mcp/tools",
            "call": "/mcp/call",
            "execute": "/mcp/execute",
            "sse": "/mcp/sse",
            "jsonrpc": "/mcp",
        },
        "tools_count": len(registry.list_tools()),
    }


def _jsonrpc_success(request_id, result: dict | list | str | int | float | None) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id, code: int, message: str, data: dict | None = None) -> JSONResponse:
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if data is not None:
        payload["error"]["data"] = data
    return JSONResponse(status_code=200, content=payload)


def _mcp_tools_payload() -> list[dict]:
    registry = registry_service()
    tools = []
    for tool in registry.list_tools():
        tools.append(
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "inputSchema": tool.get("input_schema") or {"type": "object", "properties": {}},
            }
        )
    return tools


def _mcp_tool_result(tool_name: str, result, is_error: bool = False) -> dict:
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    payload = {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }
    if not is_error and isinstance(result, dict):
        payload["structuredContent"] = result
    if is_error and tool_name:
        payload["tool"] = tool_name
    return payload


async def _sse_event_stream(request: Request, post_path: str):
    session_id = uuid4().hex
    endpoint = f"{post_path}?session_id={session_id}"
    yield f"event: endpoint\ndata: {endpoint}\n\n"
    yield f"event: ready\ndata: {json.dumps({'sessionId': session_id}, ensure_ascii=False)}\n\n"
    while True:
        if await request.is_disconnected():
            break
        await asyncio.sleep(15)
        yield ": keep-alive\n\n"


def _sse_response(request: Request, post_path: str = "/mcp") -> StreamingResponse:
    return StreamingResponse(
        _sse_event_stream(request, post_path=post_path),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "",
    response_model=MCPRootResponse,
    summary="Información del servidor MCP",
    description="Devuelve las capacidades del servidor, endpoints disponibles y cantidad de tools registradas."
)
@router.get(
    "/",
    response_model=MCPRootResponse,
    summary="Información del servidor MCP (Alias)"
)
def get_mcp_root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept:
        return _sse_response(request)
    return _mcp_root_payload()


@router.post(
    "",
    summary="Endpoint JSON-RPC 2.0 (Estándar MCP)",
    description="Punto de entrada principal para clientes MCP nativos que utilizan el protocolo de transporte JSON-RPC 2.0."
)
@router.post(
    "/",
    summary="Endpoint JSON-RPC 2.0 (Alias)"
)
def post_mcp_root(request: dict):
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    if request.get("jsonrpc") != "2.0":
        return _jsonrpc_error(request_id, -32600, "jsonrpc debe ser '2.0'")
    if not method:
        return _jsonrpc_error(request_id, -32600, "method es requerido")

    if method == "initialize":
        return _jsonrpc_success(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "conti-backend", "version": "0.1.0"},
            },
        )

    if method == "notifications/initialized":
        return JSONResponse(status_code=202, content={"jsonrpc": "2.0", "id": request_id, "result": {}})

    if method == "ping":
        return _jsonrpc_success(request_id, {})

    if method == "tools/list":
        return _jsonrpc_success(request_id, {"tools": _mcp_tools_payload()})

    if method == "tools/call":
        tool_name = params.get("name") or params.get("tool_name")
        arguments = params.get("arguments") or {}
        if not tool_name:
            return _jsonrpc_error(request_id, -32602, "tools/call requiere params.name")

        registry = registry_service()
        try:
            result = registry.call(tool_name, arguments)
            return _jsonrpc_success(request_id, _mcp_tool_result(tool_name, result))
        except KeyError as exc:
            return _jsonrpc_success(request_id, _mcp_tool_result(tool_name, {"error": str(exc)}, is_error=True))
        except ValueError as exc:
            return _jsonrpc_success(request_id, _mcp_tool_result(tool_name, {"error": str(exc)}, is_error=True))

    return _jsonrpc_error(request_id, -32601, f"Método no soportado: {method}")


@router.get(
    "/tools",
    response_model=MCPToolsResponse,
    summary="Listar Herramientas (Tools)",
    description="Devuelve el catálogo completo de herramientas (MCP Tools) disponibles junto con sus respectivos JSON Schemas de entrada."
)
def get_mcp_tools() -> dict:
    return {
        "status": "ok",
        "tools": _mcp_tools_payload(),
    }


@router.post(
    "/call",
    response_model=ToolCallResponse,
    summary="Invocar una herramienta (REST)",
    description="Permite invocar una herramienta específica pasando su nombre y argumentos en formato JSON estándar (REST)."
)
def post_mcp_call(request: MCPCallRequest) -> ToolCallResponse:
    registry = registry_service()
    try:
        result = registry.call(request.tool, request.arguments)
        return ToolCallResponse(success=True, tool=request.tool, result=result)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/execute",
    response_model=MCPExecuteResponse,
    summary="Ejecutar herramienta (Legacy)",
    description="Endpoint alternativo para la ejecución de herramientas, compatible con integraciones anteriores y clientes que no siguen el esquema MCP estándar."
)
def post_mcp_execute(request: dict):
    tool_name = request.get("tool_name") or request.get("tool") or request.get("name")
    arguments = request.get("arguments") or request.get("params") or {}
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name es requerido")

    registry = registry_service()
    try:
        result = registry.call(tool_name, arguments)
        return {"success": True, "result": result, "error": None}
    except KeyError as exc:
        return JSONResponse(status_code=404, content={"success": False, "result": None, "error": str(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"success": False, "result": None, "error": str(exc)})


@router.get(
    "/sse",
    summary="Conexión Server-Sent Events (SSE)",
    description="Establece una conexión persistente Server-Sent Events (SSE) para clientes MCP que soportan transporte bidireccional."
)
@router.get(
    "/sse/",
    summary="Conexión Server-Sent Events (SSE) (Alias)"
)
def get_mcp_sse(request: Request) -> StreamingResponse:
    return _sse_response(request, post_path="/mcp")


@router.post(
    "/sse",
    summary="Endpoint JSON-RPC via SSE transport (POST)",
    description="Recibe mensajes JSON-RPC 2.0 de clientes que usan transporte SSE (ej. hermes-agent)."
)
@router.post(
    "/sse/",
    summary="Endpoint JSON-RPC via SSE transport (POST, Alias)"
)
def post_mcp_sse(request: dict):
    return post_mcp_root(request)
