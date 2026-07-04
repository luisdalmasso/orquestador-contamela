"""
sourcebot_tools.py — Búsqueda de código en Sourcebot v5.0.4.

2 tools MCP que wrappean la REST API de Sourcebot (http://conti-sourcebot:3010):

  sourcebot_search   — Búsqueda en el código indexado de /desarrollo, /compose,
                       /contenedores/conti-backend. Devuelve snippets con path y
                       número de línea. Usar cuando el agent quiere buscar un
                       patrón, función, o símbolo en la codebase.

  sourcebot_list_repos — Lista los repos que Sourcebot tiene indexados.
                         Útil para confirmar que el cwd actual está siendo
                         scrapeado.

Diferencia con RAG (Flamehaven):
  - Sourcebot: BÚSQUEDA DE CÓDIGO (grep-style con índice, snippets con path/línea).
  - Flamehaven: RAG de documentos (PDFs, DOCs, MDs) con answer LLM.

Estas tools son para que el agent omp pueda consultar Sourcebot DURANTE su
trabajo (no solo pre-agent como hace _sourcebot_search en service.py).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("conti.sourcebot_tools")


def _sourcebot_get(endpoint: str, base_url: str) -> dict:
    """Helper HTTP GET contra la REST API de Sourcebot."""
    import httpx  # type: ignore

    url = base_url.rstrip("/") + endpoint
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url)
    if resp.status_code != 200:
        return {
            "status": "error",
            "http_status": resp.status_code,
            "message": f"Sourcebot GET {endpoint} failed: {resp.text[:200]}",
        }
    return resp.json()


def sourcebot_search(config: Any, arguments: dict) -> dict[str, Any]:
    """Busca código en Sourcebot por query (estilo grep semántico).

    Args:
        config: AppConfig (no usado directamente).
        arguments:
          - query (str, REQUERIDO): término o frase a buscar.
          - limit (int, opcional, default=10): máximo de resultados.
          - repos (list[str], opcional): filtrar por repos específicos.
            Default: todos los indexados.

    Returns:
        {"results": [{"repo", "path", "line", "snippet"}, ...], "total": N}
    """
    query = arguments.get("query", "").strip()
    if not query:
        return {"status": "error", "message": "Falta el parámetro 'query'"}
    limit = int(arguments.get("limit", 10))

    base_url = os.getenv("SOURCEBOT_URL", "http://conti-sourcebot:3000")

    import httpx  # type: ignore

    body = {"query": query, "matches": limit}
    if arguments.get("repos"):
        body["repos"] = arguments["repos"]

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{base_url}/api/search",
                json=body,
                headers={"Content-Type": "application/json"},
            )
    except httpx.RequestError as exc:
        return {
            "status": "error",
            "message": f"Sourcebot no accesible en {base_url}: {exc}",
        }

    if resp.status_code != 200:
        return {
            "status": "error",
            "http_status": resp.status_code,
            "message": resp.text[:200],
        }

    data = resp.json()
    if resp.status_code == 401:
        log.warning(
            "[sourcebot_search] Sourcebot requiere autenticación (401). "
            "Configurar SOURCEBOT_API_KEY o deshabilitar auth en Sourcebot."
        )
        return {
            "status": "error",
            "http_status": 401,
            "message": "Sourcebot requiere autenticación. Configure SOURCEBOT_API_KEY.",
        }
    # Sourcebot v5.0.4 devuelve { results: [...], stats: {...} }
    results = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(results, list):
        results = data.get("files", []) if isinstance(data, dict) else []
    log.info("[sourcebot_search] query=%r results=%d", query, len(results))
    return {
        "status": "ok",
        "query": query,
        "total": len(results) if isinstance(results, list) else 0,
        "results": results if isinstance(results, list) else [],
    }


def sourcebot_list_repos(config: Any, arguments: dict) -> dict[str, Any]:
    """Lista los repos indexados en Sourcebot."""
    base_url = os.getenv("SOURCEBOT_URL", "http://conti-sourcebot:3000")
    try:
        data = _sourcebot_get("/api/repos", base_url)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
    return {"status": "ok", "repos": data}


def sourcebot_get_doc(config: Any, arguments: dict) -> dict[str, Any]:
    """Devuelve el contenido de un archivo indexado por path absoluto."""
    path = arguments.get("path", "").strip()
    if not path:
        return {"status": "error", "message": "Falta 'path'"}
    base_url = os.getenv("SOURCEBOT_URL", "http://conti-sourcebot:3000")
    try:
        data = _sourcebot_get(f"/api/doc?path={path}", base_url)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
    return {"status": "ok", "path": path, "content": data.get("content", "")}
