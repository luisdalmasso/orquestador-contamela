# app/openhands_agent/service.py
"""
Plataforma de emulación LLM nativa basada en OpenHands SDK v1.29.

Implementa el flujo del PLAN_LLM.MD (v4) usando la API real de
`openhands.sdk` (LLM, Agent, LocalConversation).

Stack integrado:
  - OpenHands SDK   -> runtime de ejecución del agente
  - oh-my-pi (omp-rpc) -> cliente Python para el protocolo RPC del agente
  - Sourcebot       -> indexación de código (vía HTTP en :3010)
  - Ponytail        -> trazabilidad (wrapper Python + AGENTS.md ruleset)
  - MCP             -> herramientas expuestas al agente (Tools/list)

El servicio NO delega a gateways Hermes en :8767; el stack OpenHands es
el único backend para /v1/chat/completions, /v1/models, /v1/responses.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncIterator

log = logging.getLogger("conti.openhands_agent")

# ─────────────────────────────────────────────────────────────────────
# Stack OpenHands (SDK v1.29)
# ─────────────────────────────────────────────────────────────────────

try:
    from openhands.sdk import LLM, Agent, Conversation, LocalConversation

    OPENHANDS_AVAILABLE = True
    log.info("OpenHands SDK importado correctamente.")
except Exception as _exc:  # pragma: no cover - degradación controlada
    OPENHANDS_AVAILABLE = False
    log.warning("OpenHands SDK NO disponible: %s", _exc)
    LLM = Agent = Conversation = LocalConversation = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────
# oh-my-pi (omp-rpc): cliente Python para invocar el agente vía RPC.
# ─────────────────────────────────────────────────────────────────────

try:
    import omp_rpc  # type: ignore

    OMP_AVAILABLE = True
    log.info("omp-rpc (oh-my-pi) disponible.")
except Exception as _exc:
    OMP_AVAILABLE = False
    log.warning("omp-rpc NO disponible: %s", _exc)

# ─────────────────────────────────────────────────────────────────────
# Ponytail: reglas AGENTS.md + wrapper Python de trazabilidad.
# ─────────────────────────────────────────────────────────────────────

PONYTAIL_RULES = ""
PONYTAIL_TRACES_DIR = "/app/logs/ponytail"

try:
    with open("/app/vendor/ponytail/AGENTS.md", "r", encoding="utf-8") as _f:
        PONYTAIL_RULES = _f.read()
    log.info("Ponytail ruleset cargado (%d bytes).", len(PONYTAIL_RULES))
except Exception as _exc:
    log.warning("No se pudo cargar Ponytail ruleset: %s. Continuando sin él.", _exc)

# ─────────────────────────────────────────────────────────────────────
# Sourcebot: cliente HTTP simple (el contenedor conti-sourcebot vive en
# la misma red docker que conti-backend y expone :3000 internamente).
# ─────────────────────────────────────────────────────────────────────

try:
    import httpx  # type: ignore

    HTTPX_AVAILABLE = True
except Exception:
    HTTPX_AVAILABLE = False

SOURCEBOT_URL = os.getenv("SOURCEBOT_URL", "http://conti-sourcebot:3000")


def _sourcebot_search(query: str, limit: int = 5) -> list[dict]:
    """Busca en Sourcebot por query. Devuelve [] si no está disponible."""
    if not HTTPX_AVAILABLE or not query:
        return []
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                f"{SOURCEBOT_URL}/api/search",
                params={"q": query, "limit": limit},
            )
            if r.status_code == 200:
                return r.json().get("results", [])
    except Exception as exc:
        log.debug("Sourcebot search falló (no crítico): %s", exc)
    return []


# ─────────────────────────────────────────────────────────────────────
# Ponytail: context manager de trazabilidad.
# ─────────────────────────────────────────────────────────────────────


class PonytailTrace:
    """Wrapper mínimo de trazabilidad inspirado en `ponytail.trace()`.

    Persiste cada trace a /app/logs/ponytail/<task_id>.json para que
    el agente quede auditable end-to-end.
    """

    def __init__(self, task_name: str, payload: dict | None = None) -> None:
        self.task_name = task_name or "unnamed-task"
        self.payload = payload or {}
        self.task_id = f"trace-{int(time.time() * 1000)}"
        self.events: list[dict] = []
        self.started_at = time.time()

    def __enter__(self) -> "PonytailTrace":
        try:
            os.makedirs(PONYTAIL_TRACES_DIR, exist_ok=True)
        except Exception:
            pass
        self._log(
            "start", {"task": self.task_name, "payload_keys": list(self.payload.keys())}
        )
        log.info("[ponytail] trace %s START task=%s", self.task_id, self.task_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._log("end", {"duration_s": round(time.time() - self.started_at, 3)})
        log.info(
            "[ponytail] trace %s END duration=%.3fs",
            self.task_id,
            time.time() - self.started_at,
        )
        try:
            with open(
                f"{PONYTAIL_TRACES_DIR}/{self.task_id}.json", "w", encoding="utf-8"
            ) as f:
                json.dump(
                    {
                        "task_id": self.task_id,
                        "task_name": self.task_name,
                        "started_at": self.started_at,
                        "ended_at": time.time(),
                        "events": self.events,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as exc:
            log.debug("Ponytail no pudo persistir trace: %s", exc)

    def _log(self, event: str, data: dict | None = None) -> None:
        self.events.append({"event": event, "ts": time.time(), "data": data or {}})


# ─────────────────────────────────────────────────────────────────────
# OpenHandsService
# ─────────────────────────────────────────────────────────────────────


class OpenHandsService:
    def is_available(self) -> bool:
        return OPENHANDS_AVAILABLE

    def list_models(self) -> dict:
        """GET /v1/models — lista OpenAI-compatible de modelos."""
        available = OPENHANDS_AVAILABLE
        models = [
            {
                "id": "openhands-agent-v1",
                "object": "model",
                "created": 1700000000,
                "owned_by": "openhands",
                "available": available,
            },
            {
                "id": "codevibing-agent",
                "object": "model",
                "created": 1700000000,
                "owned_by": "openhands",
                "available": available,
            },
        ]
        # Incluir cada circuito como modelo "virtual" para que clientes que
        # enrutan por modelo puedan elegir circuito.
        from app.openhands_agent.circuits import CIRCUITS, circuit_manager

        for cid, cfg in CIRCUITS.items():
            models.append(
                {
                    "id": f"circuit/{cid}",
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": "openhands",
                    "available": circuit_manager.is_ready(cid),
                    "circuit": cid,
                    "workspace": cfg.workspace_dir,
                }
            )
        return {
            "object": "list",
            "data": models,
            "backend": "openhands",
            "stack": {
                "openhands_sdk": OPENHANDS_AVAILABLE,
                "oh_my_pi_omp_rpc": OMP_AVAILABLE,
                "ponytail_rules_bytes": len(PONYTAIL_RULES),
                "sourcebot_url": SOURCEBOT_URL,
                "circuits": circuit_manager.status(),
            },
        }

    def backend_status(self) -> dict:
        from app.openhands_agent.circuits import circuit_manager

        return {
            "backend": "openhands",
            "runtime_available": OPENHANDS_AVAILABLE,
            "stack": {
                "oh_my_pi_omp_rpc": OMP_AVAILABLE,
                "ponytail_rules_loaded": bool(PONYTAIL_RULES),
                "ponytail_rules_bytes": len(PONYTAIL_RULES),
                "sourcebot_url": SOURCEBOT_URL,
                "circuits": circuit_manager.status(),
            },
        }

    def reload_backend(self) -> dict:
        global PONYTAIL_RULES
        try:
            with open("/app/vendor/ponytail/AGENTS.md", "r", encoding="utf-8") as _f:
                PONYTAIL_RULES = _f.read()
            log.info("Ponytail ruleset recargado (%d bytes).", len(PONYTAIL_RULES))
        except Exception as exc:
            log.error("No se pudo recargar ponytail: %s", exc)
        return self.backend_status()

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _extract_user_prompt(payload: dict) -> str:
        messages = payload.get("messages") or []
        user_msgs = [
            m for m in messages if isinstance(m, dict) and m.get("role") == "user"
        ]
        if user_msgs:
            content = user_msgs[-1].get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
                return "\n".join(parts)
            return str(content)
        return payload.get("prompt", "") or ""

    def _build_final_prompt(self, user_prompt: str, sourcebot_hits: list[dict]) -> str:
        sections: list[str] = []
        if PONYTAIL_RULES:
            sections.append(PONYTAIL_RULES.strip())
        if sourcebot_hits:
            sections.append("# Code Context (from Sourcebot)")
            for hit in sourcebot_hits[:5]:
                repo = hit.get("repo", "?")
                path = hit.get("path", "?")
                snippet = (hit.get("content") or hit.get("snippet") or "")[:400]
                sections.append(f"### {repo} :: {path}\n```\n{snippet}\n```")
        sections.append("# User Task")
        sections.append(user_prompt)
        return "\n\n---\n\n".join(sections)

    def _to_openai_completion(self, raw: Any, payload: dict) -> dict:
        model_name = payload.get("model", "openhands-agent-v1")
        content = str(raw) if raw is not None else ""
        return {
            "id": f"chatcmpl-openhands-{os.getpid()}-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    # ── ejecución principal ────────────────────────────────────

    def run_task(self, payload: dict) -> dict:
        log.info("OpenHands run_task invocado.")
        user_prompt = self._extract_user_prompt(payload)
        if not user_prompt:
            return {
                "status": "error",
                "details": "No user prompt found in payload.",
            }

        # 0) Detectar qué circuito usar según el prompt (o force desde payload)
        from app.openhands_agent.circuits import (
            CIRCUITS,
            circuit_manager,
            detect_circuit,
        )

        force = payload.get("circuit")  # permite al cliente forzar el circuito
        circuit_id = detect_circuit(user_prompt, force=force)
        circuit_cfg = CIRCUITS[circuit_id]
        log.info("[circuits] prompt → circuito '%s'", circuit_id)

        # 1) Iniciar traza con Ponytail
        with PonytailTrace(
            task_name=user_prompt[:80],
            payload={**payload, "_circuit": circuit_id},
        ) as trace:
            trace._log(
                "circuit_selected",
                {"id": circuit_id, "workspace": circuit_cfg.workspace_dir},
            )

            # 2) Preparar contexto con Sourcebot (RAG sobre código)
            sourcebot_hits = _sourcebot_search(user_prompt)
            trace._log("sourcebot_search", {"hits": len(sourcebot_hits)})

            # 3) Construir prompt final con reglas del circuito + Sourcebot
            final_prompt = self._build_circuit_prompt(
                user_prompt,
                sourcebot_hits,
                circuit_cfg,
            )

            if not OPENHANDS_AVAILABLE:
                trace._log("error", {"reason": "openhands_sdk_unavailable"})
                return {
                    "status": "error",
                    "details": "OpenHands SDK not available.",
                    "stack_status": self.backend_status(),
                    "circuit": circuit_id,
                }

            # 4) Obtener o crear la conversación persistente del circuito
            try:
                conv = circuit_manager.get_or_create(circuit_id)
                if conv is None:
                    raise RuntimeError("circuit_manager returned None")
            except Exception as exc:
                log.error(
                    "Error creando circuito %s: %s", circuit_id, exc, exc_info=True
                )
                trace._log("error", {"exception": str(exc)})
                return {
                    "status": "error",
                    "details": f"Error inicializando circuito '{circuit_id}': {exc}",
                    "circuit": circuit_id,
                }

            # 5) Invocar OpenHands en el circuito seleccionado
            try:
                result_text = self._invoke_on_circuit(conv, final_prompt)
                trace._log(
                    "openhands_invoke", {"circuit": circuit_id, "len": len(result_text)}
                )
                completion = self._to_openai_completion(result_text, payload)
                completion["circuit"] = circuit_id
                return completion
            except Exception as exc:
                log.error(
                    "Error ejecutando OpenHands en %s: %s",
                    circuit_id,
                    exc,
                    exc_info=True,
                )
                trace._log("error", {"exception": str(exc)})
                return {
                    "status": "error",
                    "details": f"An error occurred during OpenHands execution: {exc}",
                    "circuit": circuit_id,
                }

    def _build_circuit_prompt(
        self,
        user_prompt: str,
        sourcebot_hits: list[dict],
        circuit_cfg: Any,
    ) -> str:
        """Construye el prompt final con: Ponytail AGENTS.md + reglas del circuito
        + contexto Sourcebot + prompt del usuario."""
        sections: list[str] = []

        # 1) Identidad base
        if PONYTAIL_RULES:
            sections.append(PONYTAIL_RULES.strip())

        # 2) Reglas específicas del circuito
        sections.append(f"# Circuit: {circuit_cfg.id}\n{circuit_cfg.description}")
        sections.append(self._circuit_tool_list(circuit_cfg))

        # 3) Contexto de Sourcebot (RAG)
        if sourcebot_hits:
            sections.append("# Code Context (from Sourcebot)")
            for hit in sourcebot_hits[:5]:
                repo = hit.get("repo", "?")
                path = hit.get("path", "?")
                snippet = (hit.get("content") or hit.get("snippet") or "")[:400]
                sections.append(f"### {repo} :: {path}\n```\n{snippet}\n```")

        # 4) Prompt del usuario
        sections.append("# User Task")
        sections.append(user_prompt)

        return "\n\n---\n\n".join(sections)

    def _circuit_tool_list(self, cfg: Any) -> str:
        """Devuelve la lista compacta de tools disponibles para este circuito."""
        lines = ["## Tools disponibles en este circuito"]
        if cfg.allowed_tools_native:
            lines.append(f"- Nativas OpenHands: {', '.join(cfg.allowed_tools_native)}")
        else:
            lines.append(
                "- Nativas OpenHands: **NINGUNA** (este circuito no edita archivos)"
            )
        if cfg.allowed_mcp_categories:
            lines.append(f"- MCP categories: {', '.join(cfg.allowed_mcp_categories)}")
        lines.append(f"- Git action permitida: **{cfg.git_action}**")
        return "\n".join(lines)

    def _invoke_on_circuit(self, conv: Any, prompt: str) -> str:
        """Envía el prompt a la conversación persistente del circuito y
        devuelve el contenido del último mensaje del agente."""
        conv.send_message(prompt)
        conv.run()

        try:
            state = conv.state
            events = getattr(state, "events", []) or []
            # Buscar el último evento del agente que tenga contenido textual.
            # Orden de preferencia:
            #   1. MessageEvent del agente (llm_message.content: list[TextContent])
            #   2. ActionEvent con FinishAction (action.message)
            #   3. ActionEvent con reasoning_content (pensamiento)
            for ev in reversed(events):
                cls = type(ev).__name__
                src = getattr(ev, "source", None)
                # Solo eventos del agente
                if src not in ("agent", None):
                    continue
                if cls == "MessageEvent":
                    # El content vive en ev.llm_message.content (list[TextContent])
                    llm_msg = getattr(ev, "llm_message", None)
                    if llm_msg is not None:
                        content = getattr(llm_msg, "content", None)
                        text = self._extract_text(content)
                        if text:
                            return text
                    # Fallback a otros atributos
                    for attr in ("message", "content"):
                        v = getattr(ev, attr, None)
                        text = self._extract_text(v)
                        if text:
                            return text
                elif cls == "ActionEvent":
                    action = getattr(ev, "action", None)
                    if action is not None:
                        msg = getattr(action, "message", None)
                        if msg:
                            return str(msg)
                    reasoning = getattr(ev, "reasoning_content", None)
                    if reasoning:
                        return str(reasoning)
        except Exception as exc:
            log.debug("No se pudo extraer último mensaje del state: %s", exc)
        return f"[Circuito ejecutó el prompt pero no devolvió contenido. Conv ID: {conv.id}]"

    def _extract_text(self, v: Any) -> str:
        """Extrae texto de un campo que puede ser str, list[TextContent], etc."""
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, list):
            parts: list[str] = []
            for item in v:
                if isinstance(item, str):
                    parts.append(item)
                elif hasattr(item, "text"):
                    # TextContent (OpenHands SDK)
                    t = str(item.text)
                    if t:
                        parts.append(t)
                elif hasattr(item, "content"):
                    parts.append(str(item.content))
            if parts:
                return "\n".join(parts)
        return ""

    # ── streaming OpenAI-compatible ────────────────────────────

    async def stream_chat_completions(
        self, payload: dict, auth_header: str = ""
    ) -> AsyncIterator[bytes]:
        result = await asyncio.to_thread(self.run_task, payload)

        model_name = payload.get("model", "openhands-agent-v1")
        completion_id = result.get("id", f"chatcmpl-openhands-{int(time.time())}")
        content = ""
        if "choices" in result and result["choices"]:
            content = result["choices"][0].get("message", {}).get("content", "")
        elif "details" in result:
            content = f"[error] {result['details']}"

        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"


openhands_service = OpenHandsService()
