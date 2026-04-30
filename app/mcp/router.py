from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.tool_models import ToolCallResponse
from app.mcp.schemas import MCPCallRequest
from app.services.registry_service import registry_service


router = APIRouter(prefix="/mcp", tags=["mcp"])


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


@router.get("")
@router.get("/")
def get_mcp_root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept:
        return _sse_response(request)
    return _mcp_root_payload()


@router.post("")
@router.post("/")
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


@router.get("/tools")
def get_mcp_tools() -> dict:
    registry = registry_service()
    return {
        "status": "ok",
        "tools": registry.list_tools(),
    }


@router.post("/call")
def post_mcp_call(request: MCPCallRequest) -> ToolCallResponse:
    registry = registry_service()
    try:
        result = registry.call(request.tool, request.arguments)
        return ToolCallResponse(success=True, tool=request.tool, result=result)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute", response_model=None)
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


@router.get("/sse")
@router.get("/sse/")
def get_mcp_sse(request: Request) -> StreamingResponse:
    return _sse_response(request, post_path="/mcp")
