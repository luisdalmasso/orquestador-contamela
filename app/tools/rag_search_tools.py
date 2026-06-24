"""
rag_search_tools.py — Recuperación de información desde Flamehaven RAG.

4 tools:
  search_rag          — Búsqueda completa (hybrid/semantic/keyword) con answer generado por LLM.
                        Usar cuando Conti necesita RESPONDER algo al usuario basándose en docs.
  search_rag_quick    — Búsqueda keyword sin LLM. Solo sources.
                        Usar cuando Conti necesita VERIFICAR si algo existe o encadenar tools.
  search_rag_semantic — Búsqueda por similitud conceptual con answer LLM.
                        Usar para queries conceptuales / paráfrasis / sinónimos.
  list_rag_store_docs — Inventario de documentos ingestados en un store.
                        Usar cuando Conti necesita saber QUÉ hay guardado, no buscar.
"""
from __future__ import annotations

import os
from typing import Any


# ---------------------------------------------------------------------------
# Helper HTTP
# ---------------------------------------------------------------------------

def _flamehaven_get(endpoint: str, api_key: str, base_url: str) -> dict:
    import httpx
    url = base_url.rstrip("/") + endpoint
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
    if resp.status_code == 404:
        return {"status": "error", "message": f"Not found: {endpoint}"}
    resp.raise_for_status()
    return resp.json()


def _flamehaven_post(endpoint: str, payload: dict, api_key: str, base_url: str) -> dict:
    import httpx
    url = base_url.rstrip("/") + endpoint
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    if resp.status_code == 404:
        return {"status": "error", "message": f"Store no encontrado o query inválida."}
    resp.raise_for_status()
    return resp.json()


def _get_rag_creds(config) -> tuple[str, str]:
    """Devuelve (api_key, base_url) o lanza ValueError."""
    api_key = os.environ.get(config.rag.api_key_env, "")
    if not api_key:
        raise ValueError(f"Variable de entorno '{config.rag.api_key_env}' no configurada.")
    return api_key, config.rag.base_url


def _iter_dict_items(items: Any):
    """Itera una colección tolerando listas anidadas y devuelve solo dicts."""
    for item in (items or []):
        if isinstance(item, dict):
            yield item
            continue
        if isinstance(item, list):
            for nested in item:
                if isinstance(nested, dict):
                    yield nested


def _clean_sources(sources: list) -> list:
    """Normaliza la lista de sources para devolver solo campos útiles."""
    cleaned = []
    for s in _iter_dict_items(sources):
        cleaned.append({
            "title": s.get("title", ""),
            "uri": s.get("uri", ""),
        })
    return cleaned


# ---------------------------------------------------------------------------
# Tool 1: search_rag — búsqueda completa con answer LLM
# ---------------------------------------------------------------------------

def search_rag(config, args: dict) -> dict:
    """
    Búsqueda completa en Flamehaven con respuesta generada por LLM (Gemini).
    Soporta modos: hybrid (recomendado), semantic, keyword.

    Usar cuando Conti necesita RESPONDER algo al usuario basándose en documentos
    del RAG. Ej: "¿cuál es la política de vacaciones?", "explicame el proceso de
    onboarding", "¿qué dice el manual sobre facturación?".

    El modo hybrid fusiona BM25 (exact match) + semántico (DSP v2.0) via RRF y
    devuelve search_confidence [0-1]. Si low_confidence=true, los resultados son
    débiles.
    """
    query = args.get("query", "").strip()
    if not query:
        return {"error": "Parámetro 'query' requerido."}

    try:
        api_key, base_url = _get_rag_creds(config)
    except ValueError as e:
        return {"error": str(e)}

    store = args.get("store", config.rag.default_store)
    mode = args.get("mode", "hybrid")
    if mode not in ("hybrid", "semantic", "keyword"):
        mode = "hybrid"

    payload: dict[str, Any] = {
        "query": query,
        "store_name": store,
        "search_mode": mode,
        "top_k": int(args.get("top_k", 5)),
    }
    if args.get("threshold") is not None:
        payload["threshold"] = float(args["threshold"])
    if args.get("max_tokens") is not None:
        payload["max_tokens"] = int(args["max_tokens"])

    try:
        result = _flamehaven_post("/api/search", payload, api_key, base_url)
    except Exception as exc:
        return {"error": f"Error consultando Flamehaven: {exc}"}

    return {
        "status": result.get("status"),
        "store": store,
        "mode": result.get("search_mode", mode),
        "query": query,
        "refined_query": result.get("refined_query"),
        "answer": result.get("answer"),
        "sources": _clean_sources(result.get("sources", [])),
        "search_confidence": result.get("search_confidence"),
        "low_confidence": result.get("low_confidence", False),
        "search_intent": result.get("search_intent"),
        "request_id": result.get("request_id"),
    }


# ---------------------------------------------------------------------------
# Tool 2: search_rag_quick — keyword sin LLM, solo sources
# ---------------------------------------------------------------------------

def search_rag_quick(config, args: dict) -> dict:
    """
    Búsqueda rápida por keyword en Flamehaven. Sin generación LLM, solo sources.

    Usar cuando Conti necesita VERIFICAR si algo existe en el RAG antes de tomar
    una decisión, o encadenar con otra tool. Ej: "¿hay documentos sobre
    MercadoPago?", "verificá si está ingestado el manual de Odoo".

    No consume tokens de Gemini — es instantáneo.
    """
    query = args.get("query", "").strip()
    if not query:
        return {"error": "Parámetro 'query' requerido."}

    try:
        api_key, base_url = _get_rag_creds(config)
    except ValueError as e:
        return {"error": str(e)}

    store = args.get("store", config.rag.default_store)

    payload = {
        "query": query,
        "store_name": store,
        "search_mode": "hybrid",
        "top_k": int(args.get("top_k", 5)),
        "max_tokens": 1,  # minimiza uso de LLM
    }

    try:
        result = _flamehaven_post("/api/search", payload, api_key, base_url)
    except Exception as exc:
        return {"error": f"Error consultando Flamehaven: {exc}"}

    sources = _clean_sources(result.get("sources", []))
    return {
        "status": result.get("status"),
        "store": store,
        "query": query,
        "matched": len(sources) > 0,
        "count": len(sources),
        "sources": sources,
        "request_id": result.get("request_id"),
    }


# ---------------------------------------------------------------------------
# Tool 3: search_rag_semantic — semántico puro con answer LLM
# ---------------------------------------------------------------------------

def search_rag_semantic(config, args: dict) -> dict:
    """
    Búsqueda semántica en Flamehaven usando DSP v2.0 (sin BM25).
    Con respuesta generada por LLM.

    Usar para queries conceptuales donde las palabras exactas no importan.
    Ej: "documentos sobre incorporación de personal" (aunque el doc diga
    'onboarding'), "procedimientos de pago" (aunque el doc diga 'cobranza').
    Tolerante a typos y sinónimos gracias a n-gramas de caracteres.
    """
    query = args.get("query", "").strip()
    if not query:
        return {"error": "Parámetro 'query' requerido."}

    try:
        api_key, base_url = _get_rag_creds(config)
    except ValueError as e:
        return {"error": str(e)}

    store = args.get("store", config.rag.default_store)

    payload: dict[str, Any] = {
        "query": query,
        "store_name": store,
        "search_mode": "semantic",
        "top_k": int(args.get("top_k", 5)),
    }
    if args.get("threshold") is not None:
        payload["threshold"] = float(args["threshold"])
    if args.get("max_tokens") is not None:
        payload["max_tokens"] = int(args["max_tokens"])

    try:
        result = _flamehaven_post("/api/search", payload, api_key, base_url)
    except Exception as exc:
        return {"error": f"Error consultando Flamehaven: {exc}"}

    semantic_results = [
        {"uri": r.get("uri", ""), "score": r.get("score", 0)}
        for r in _iter_dict_items(result.get("semantic_results"))
    ]

    return {
        "status": result.get("status"),
        "store": store,
        "mode": "semantic",
        "query": query,
        "refined_query": result.get("refined_query"),
        "answer": result.get("answer"),
        "sources": _clean_sources(result.get("sources", [])),
        "semantic_results": semantic_results,
        "search_confidence": result.get("search_confidence"),
        "request_id": result.get("request_id"),
    }


# ---------------------------------------------------------------------------
# Tool 4: list_rag_store_docs — inventario de documentos ingestados
# ---------------------------------------------------------------------------

def list_rag_store_docs(config, args: dict) -> dict:
    """
    Lista todos los documentos indexados en un store de Flamehaven.
    Sin búsqueda ni LLM — solo inventario.

    Usar cuando Conti necesita saber QUÉ documentos hay guardados en el RAG.
    Ej: "mostrá todos los docs del store contamela", "¿qué está indexado?".
    """
    try:
        api_key, base_url = _get_rag_creds(config)
    except ValueError as e:
        return {"error": str(e)}

    store = args.get("store", config.rag.default_store)

    try:
        result = _flamehaven_get(f"/api/stores/{store}/docs", api_key, base_url)
    except Exception as exc:
        return {"error": f"Error consultando Flamehaven: {exc}"}

    return {
        "status": result.get("status"),
        "store": store,
        "count": result.get("count", 0),
        "docs": result.get("docs", []),
        "request_id": result.get("request_id"),
    }
