"""
app/openhands_agent/tool_bridge.py
===================================

Bridge entre las MCP tools de Conti (:9001/mcp) y el agent runtime oh-my-pi.

Cuando omp necesita ejecutar una tool custom de Conti (run_salvar, odoo_*,
catolico_*, sheets_*, etc.), este bridge:
  1. omp invoca `execute(args, context)` del host_tool Python.
  2. El handler hace un POST JSON-RPC a `:9001/mcp` (mismo proceso uvicorn).
  3. El MCP server procesa la request ejecutando la lógica de la tool.
  4. La respuesta vuelve al handler, que la serializa a string para omp.

Arquitectura:

  omp subprocess (conti-omp)
       │
       │ NDJSON over stdio (omp_rpc.RpcClient)
       ▼
  socat (TCP↔stdio bridge en conti-omp:7891)
       │
       │ TCP socket
       ▼
  omp_client.prompt_and_wait()
       │
       │ cuando omp quiere usar una custom_tool, llama execute(args)
       ▼
  [aquí: make_mcp_tool_handler(tool_name, mcp_url)]
       │
       │ httpx POST :9001/mcp (JSON-RPC loopback)
       ▼
  FastAPI app (mismo proceso uvicorn)
       │
       │ MCP JSON-RPC
       ▼
  tool handler (run_salvar, odoo_*, etc.)
       │
       │ return result
       ▼
  result string → omp continúa su loop
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx  # type: ignore

log = logging.getLogger("conti.tool_bridge")


def make_mcp_tool_handler(
    tool_name: str,
    mcp_url: str,
    timeout: float = 30.0,
):
    """Crea un handler Python que omp puede invocar como custom tool.

    Cuando omp llama `handler(args, context)`, el handler:
      1. Construye un JSON-RPC request:
         {
           "jsonrpc": "2.0",
           "id": <timestamp ns>,
           "method": "tools/call",
           "params": {"name": tool_name, "arguments": args}
         }
      2. POST a `mcp_url` (default: http://127.0.0.1:9001/mcp).
      3. Lee la respuesta, extrae `result.content[0].text` o serializa.
      4. Retorna string (lo que omp_rpc espera de `execute()`).

    Args:
        tool_name: nombre de la MCP tool (ej: "run_salvar", "odoo_get_invoice").
        mcp_url: URL del MCP server (default: http://127.0.0.1:9001/mcp).
        timeout: timeout en segundos para el POST HTTP.

    Returns:
        Callable[[dict, Any], str] compatible con omp_rpc.host_tool.execute.
    """

    def handler(args: dict, context: Any) -> str:
        """Handler Python que omp invoca."""
        request_id = time.time_ns()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args,
            },
        }
        log.debug("[tool_bridge] %s args=%s (id=%d)", tool_name, args, request_id)
        t0 = time.time()
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(mcp_url, json=payload)
            elapsed_ms = (time.time() - t0) * 1000

            if resp.status_code != 200:
                log.error(
                    "[tool_bridge] %s HTTP %d (%dms): %s",
                    tool_name,
                    resp.status_code,
                    elapsed_ms,
                    resp.text[:300],
                )
                return (
                    f"ERROR ({tool_name}): HTTP {resp.status_code}: {resp.text[:200]}"
                )

            data = resp.json()

            if "error" in data:
                err = data["error"]
                err_msg = err.get("message", err) if isinstance(err, dict) else err
                log.error(
                    "[tool_bridge] %s error (%dms): %s",
                    tool_name,
                    elapsed_ms,
                    err_msg,
                )
                return f"ERROR ({tool_name}): {err_msg}"

            result = data.get("result", {})
            log.info(
                "[tool_bridge] %s OK (%dms)",
                tool_name,
                elapsed_ms,
            )

            # omp_rpc espera string como return. Si el MCP devuelve
            # structured content, extraemos el primer text o serializamos.
            if isinstance(result, dict):
                content = result.get("content", [])
                if content and isinstance(content, list):
                    first = content[0]
                    if isinstance(first, dict) and "text" in first:
                        return str(first["text"])
                # Si no hay content estructurado, serializar el dict entero.
                return json.dumps(result, ensure_ascii=False, default=str)
            if isinstance(result, str):
                return result
            return str(result)
        except httpx.TimeoutException:
            elapsed_ms = (time.time() - t0) * 1000
            log.error(
                "[tool_bridge] %s timeout después de %dms",
                tool_name,
                elapsed_ms,
            )
            return f"ERROR ({tool_name}): timeout después de {timeout}s"
        except Exception as exc:
            elapsed_ms = (time.time() - t0) * 1000
            log.error(
                "[tool_bridge] %s excepción (%dms): %s: %s",
                tool_name,
                elapsed_ms,
                type(exc).__name__,
                exc,
            )
            return f"ERROR ({tool_name}): {type(exc).__name__}: {exc}"

    return handler


def build_custom_tools_for_circuit(
    circuit_cfg: Any,
    registry: Any,
    mcp_url: str,
) -> list:
    """Construye la lista de custom_tools para omp_rpc.RpcClient.

    Filtra el registry por `cfg.allowed_mcp_categories` y crea un
    `host_tool()` por cada MCP tool del circuito. Estas tools se pasan a
    `RpcClient(custom_tools=...)` y omp las puede invocar como si fueran
    built-in (pero ejecutan via MCP loopback).

    Args:
        circuit_cfg: CircuitConfig con `allowed_mcp_categories`.
        registry: instancia de `registry_service()` (lazy singleton).
        mcp_url: URL del MCP server (default http://127.0.0.1:9001/mcp).

    Returns:
        list[HostTool] lista de custom_tools lista para pasar a omp_rpc.RpcClient.
        Lista vacía si el circuito no permite MCP categories.
    """
    try:
        from omp_rpc import host_tool
    except ImportError:
        log.warning("omp_rpc no disponible; build_custom_tools_for_circuit retorna []")
        return []

    allowed_categories = set(circuit_cfg.allowed_mcp_categories or [])
    if not allowed_categories:
        log.debug(
            "[tool_bridge] circuit %s sin MCP categories; no custom_tools",
            getattr(circuit_cfg, "id", "?"),
        )
        return []

    # Listar todas las tools del registry, filtrar por categorías del circuito.
    tools_def = registry.list_tools()  # list[dict] con name, description, etc.
    custom_tools = []
    for t in tools_def:
        if t.get("category") not in allowed_categories:
            continue
        ht = host_tool(
            name=t["name"],
            description=t.get("description", ""),
            parameters=t.get("input_schema") or {"type": "object", "properties": {}},
            execute=make_mcp_tool_handler(t["name"], mcp_url),
        )
        custom_tools.append(ht)

    log.info(
        "[tool_bridge] circuit %s: %d custom_tools construidas (de %d totales)",
        getattr(circuit_cfg, "id", "?"),
        len(custom_tools),
        len(tools_def),
    )
    return custom_tools
