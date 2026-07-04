"""
open_hands_service.py — Servicio que usa OpenHands Agent Server como orquestador.

Reemplaza el código Python custom de service.py con la API nativa de OpenHands.
El Agent Server (puerto 3000) orquesta el flujo:
  1. Crea conversación con workspace del circuito
  2. Envía el prompt con governance injection
  3. El agente de OpenHands ejecuta tools y MCP nativamente
  4. Captura eventos para PonytailTrace

El Agent Server ya tiene:
  - LLM configurado (Mistral/Xiaomi via env vars)
  - Tools nativas (bash, file_editor, read_file, write_file, glob, grep)
  - MCP integration (se configura via mcp_config)
  - Event system para observabilidad
"""

import json
import logging
import os
import time
import uuid
from typing import Any

import httpx

log = logging.getLogger("conti.openhands_service")

AGENT_SERVER_URL = os.getenv("AGENT_SERVER_URL", "http://127.0.0.1:3000")
DEFAULT_TIMEOUT = float(os.getenv("OPENHANDS_TIMEOUT", "600"))

# Mapeo de circuitos a workspaces
CIRCUIT_WORKSPACES = {
    "desarrollo": "/desarrollo",
    "produccion": "/compose",
    "backend": "/contenedores/conti-backend",
    "libre": "/tmp/free-agent",
}


class OpenHandsOrchestrator:
    """Orquestador que usa OpenHands Agent Server para ejecutar prompts.

    Flujo:
    1. POST /api/conversations → crea conversación con workspace del circuito
    2. POST /api/conversations/{id}/goal → envía el prompt
    3. GET /api/conversations/{id}/events → espera resultados
    4. Extrae la respuesta final del agente
    """

    def __init__(self, base_url: str = AGENT_SERVER_URL):
        self.base_url = base_url
        self._client = httpx.Client(timeout=DEFAULT_TIMEOUT)

    def _wait_for_agent_server(self, timeout: float = 120.0) -> bool:
        """Espera a que el agent-server esté disponible."""
        import time as _time

        start = _time.time()
        attempt = 0
        while _time.time() - start < timeout:
            attempt += 1
            try:
                resp = self._client.get(f"{self.base_url}/alive", timeout=5)
                if resp.status_code == 200:
                    log.info(
                        "[openhands] agent-server available after %ds (attempt %d)",
                        int(_time.time() - start),
                        attempt,
                    )
                    return True
                log.warning(
                    "[openhands] agent-server returned %d (attempt %d)",
                    resp.status_code,
                    attempt,
                )
            except Exception as exc:
                log.warning(
                    "[openhands] agent-server connection failed (attempt %d): %s",
                    attempt,
                    exc,
                )
            _time.sleep(5)
        log.error(
            "[openhands] agent-server not available after %ds (%d attempts)",
            timeout,
            attempt,
        )
        return False

    def run_task(
        self,
        prompt: str,
        circuit_id: str = "libre",
        session_id: str | None = None,
        governance_context: str = "",
        trace: Any = None,
    ) -> dict:
        """Ejecuta un prompt usando OpenHands Agent Server.

        Args:
            prompt: El prompt del usuario
            circuit_id: ID del circuito (desarrollo, produccion, backend, libre)
            session_id: ID de sesión (para reutilizar conversación)
            governance_context: Contexto de governance (onboarding + rules + config)
            trace: PonytailTrace para logging de eventos

        Returns:
            dict con status, response, circuit, session_id
        """
        workspace = CIRCUIT_WORKSPACES.get(circuit_id, "/tmp/free-agent")
        # Si governance_context viene con contenido, SIEMPRE inyectarlo
        # (el caller ya determinó si es primera sesión o no)
        is_new_session = session_id is None
        has_governance = bool(
            governance_context and len(governance_context.strip()) > 50
        )

        if trace:
            trace._log(
                "openhands_orchestrator_start",
                {
                    "circuit": circuit_id,
                    "workspace": workspace,
                    "is_new_session": is_new_session,
                    "prompt_len": len(prompt),
                    "governance_len": len(governance_context),
                },
            )

        try:
            # 0) Esperar a que el agent-server esté disponible
            if not self._wait_for_agent_server():
                return {
                    "status": "error",
                    "details": "Agent server not available after timeout",
                    "circuit": circuit_id,
                    "session_id": session_id,
                }

            # 1) Crear conversación
            conv_id = self._create_conversation(
                workspace=workspace,
                circuit_id=circuit_id,
                session_id=session_id,
            )

            if trace:
                trace._log(
                    "conversation_created",
                    {
                        "conversation_id": conv_id,
                        "workspace": workspace,
                    },
                )

            # 2) Construir prompt final con governance
            #    SIEMPRE inyectar governance si viene con contenido
            final_prompt = self._build_prompt(
                prompt, governance_context, has_governance, circuit_id
            )

            if trace:
                trace._log(
                    "system_prompt",
                    {
                        "length": len(final_prompt),
                        "is_new_session": is_new_session,
                        "governance_chars": len(governance_context),
                        "circuit": circuit_id,
                        "workspace": workspace,
                    },
                )

            # 2b) Loggear el prompt completo inyectado (NUNCA truncar)
            if trace:
                trace._log(
                    "prompt_injected",
                    {
                        "prompt_full": final_prompt,
                        "governance_context": governance_context
                        if governance_context
                        else "",
                        "user_prompt": prompt,
                        "inject_governance": has_governance,
                        "governance_chars": len(governance_context)
                        if governance_context
                        else 0,
                    },
                )

            # 3) Enviar prompt como goal
            self._send_goal(conv_id, final_prompt)

            if trace:
                trace._log(
                    "goal_sent",
                    {
                        "conversation_id": conv_id,
                        "prompt_len": len(final_prompt),
                    },
                )

            # 4) Esperar resultado
            result = self._wait_for_result(conv_id, trace)

            if trace:
                trace._log(
                    "openhands_orchestrator_end",
                    {
                        "conversation_id": conv_id,
                        "response_len": len(result.get("response", "")),
                        "status": result.get("status"),
                    },
                )

            return {
                "status": "ok",
                "response": result.get("response", ""),
                "circuit": circuit_id,
                "session_id": conv_id,
                "conversation_id": conv_id,
            }

        except Exception as exc:
            log.error("[openhands] Error en run_task: %s", exc, exc_info=True)
            if trace:
                trace._log("error", {"exception": str(exc)})
            return {
                "status": "error",
                "details": str(exc),
                "circuit": circuit_id,
                "session_id": session_id,
            }

    def _create_conversation(
        self,
        workspace: str,
        circuit_id: str,
        session_id: str | None = None,
    ) -> str:
        """Crea una conversación en el Agent Server."""
        conv_id = session_id or str(uuid.uuid4())

        payload = {
            "workspace": {"type": "local", "working_dir": workspace},
            "persistence_dir": f"/app/workspace/conversations/{conv_id}",
            "agent_settings": {
                "agent_kind": "openhands",
                "agent": "CodeActAgent",
                "llm": {
                    "model": os.getenv("OPENHANDS_LLM_MODEL", "openai/mimo-v2.5-pro"),
                    "api_key": os.getenv(
                        "XIAOMI_TOKEN_PLAN_SGP_API_KEY",
                        "tp-sgiwk57kxh9bf20zopw6lprwgaco4wo6127vy6vbq5z69gvp",
                    ),
                    "base_url": os.getenv(
                        "OPENHANDS_LLM_BASE_URL",
                        "https://token-plan-sgp.xiaomimimo.com/v1",
                    ),
                },
                "tools": [
                    {"name": "terminal"},
                    {"name": "file_editor"},
                    {"name": "read_file"},
                    {"name": "write_file"},
                    {"name": "glob"},
                    {"name": "grep"},
                    {"name": "list_directory"},
                    {"name": "task_tracker"},
                ],
            },
        }

        # MCP config: conectar a conti-backend y codebase-memory
        mcp_config = self._build_mcp_config(circuit_id)
        if mcp_config:
            # NO sobrescribir agent_settings completo, solo agregar mcp_config
            payload["agent_settings"]["mcp_config"] = mcp_config

        resp = self._client.post(
            f"{self.base_url}/api/conversations",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("id", conv_id)

    def _build_mcp_config(self, circuit_id: str) -> dict | None:
        """Construye la configuración MCP para la conversación."""
        mcp_servers = {}

        # codebase-memory-mcp (knowledge graph via stdio)
        cbm_bin = "/home/conti/.local/bin/codebase-memory-mcp"
        if os.path.exists(cbm_bin):
            mcp_servers["codebase-memory"] = {
                "command": cbm_bin,
                "args": [],
            }

        if mcp_servers:
            return {"mcpServers": mcp_servers}
        return None

    def _send_goal(self, conv_id: str, prompt: str) -> None:
        """Envía el prompt como goal a la conversación."""
        resp = self._client.post(
            f"{self.base_url}/api/conversations/{conv_id}/goal",
            json={"objective": prompt, "max_iterations": 50},
        )
        resp.raise_for_status()

    def _wait_for_result(self, conv_id: str, trace: Any = None) -> dict:
        """Espera a que la conversación termine y extrae el resultado."""
        start = time.time()
        last_event_count = 0

        while time.time() - start < DEFAULT_TIMEOUT:
            # Obtener estado de la conversación
            try:
                resp = self._client.get(f"{self.base_url}/api/conversations/{conv_id}")
                if resp.status_code != 200:
                    time.sleep(0.5)
                    continue

                conv_info = resp.json()
                status = conv_info.get("execution_status", "unknown")

                if status in ("completed", "error", "stopped"):
                    break

            except Exception:
                pass

            # Obtener eventos nuevos (usar search endpoint)
            try:
                events_resp = self._client.get(
                    f"{self.base_url}/api/conversations/{conv_id}/events/search",
                    params={"limit": 50},
                )
                if events_resp.status_code == 200:
                    events_data = events_resp.json()
                    events = (
                        events_data.get("items", events_data)
                        if isinstance(events_data, dict)
                        else events_data
                    )
                    if isinstance(events, list) and len(events) > last_event_count:
                        new_events = events[last_event_count:]
                        last_event_count = len(events)

                        # Loggear eventos al trace
                        if trace:
                            for ev in new_events:
                                self._log_event_to_trace(ev, trace)

            except Exception:
                pass

            time.sleep(2)

        # Extraer respuesta final
        try:
            final_resp = self._client.get(
                f"{self.base_url}/api/conversations/{conv_id}/agent_final_response"
            )
            if final_resp.status_code == 200:
                data = final_resp.json()
                response_text = (
                    data.get("response")
                    or data.get("content")
                    or data.get("message")
                    or ""
                )
                if response_text and str(response_text).strip():
                    return {
                        "status": "ok",
                        "response": str(response_text),
                    }
        except Exception:
            pass

        # Fallback 1: extraer del último MessageEvent con role=assistant
        try:
            events_resp = self._client.get(
                f"{self.base_url}/api/conversations/{conv_id}/events/search",
                params={"limit": 50},
            )
            if events_resp.status_code == 200:
                events_data = events_resp.json()
                events = (
                    events_data.get("items", [])
                    if isinstance(events_data, dict)
                    else events_data
                )
                if isinstance(events, list):
                    # Buscar último MessageEvent del assistant
                    for ev in reversed(events):
                        if ev.get("kind") == "MessageEvent":
                            content = ev.get("content", [])
                            role = ev.get("role", "")
                            if isinstance(content, list):
                                for c in content:
                                    if isinstance(c, dict) and c.get("type") == "text":
                                        text = c.get("text", "")
                                        if text and len(text.strip()) > 5:
                                            return {"status": "ok", "response": text}
                    # Buscar último ObservationEvent con contenido
                    for ev in reversed(events):
                        if ev.get("kind") == "ObservationEvent":
                            obs = ev.get("observation", {})
                            content_list = obs.get("content", [])
                            if isinstance(content_list, list):
                                for c in content_list:
                                    if isinstance(c, dict) and c.get("type") == "text":
                                        text = c.get("text", "")
                                        if text and len(text.strip()) > 5:
                                            return {"status": "ok", "response": text}
        except Exception:
            pass

        # Fallback 2: extraer del último evento con contenido
        try:
            events_resp = self._client.get(
                f"{self.base_url}/api/conversations/{conv_id}/events/search",
                params={"limit": 10},
            )
            if events_resp.status_code == 200:
                events_data = events_resp.json()
                events = (
                    events_data.get("items", [])
                    if isinstance(events_data, dict)
                    else events_data
                )
                if isinstance(events, list):
                    for ev in reversed(events):
                        content = ev.get("content", "")
                        if content and isinstance(content, str) and len(content) > 10:
                            return {"status": "ok", "response": content}
        except Exception:
            pass

        return {"status": "timeout", "response": "[OpenHands timeout: no response]"}

    def _log_event_to_trace(self, event: dict, trace: Any) -> None:
        """Mapea eventos de OpenHands SDK v1.29 a PonytailTrace.

        Estructura real:
        - ActionEvent: tool_name, action.{command,kind}, reasoning_content en TOP LEVEL
        - ObservationEvent: tool_name, observation.{content,is_error} en TOP LEVEL
        - MessageEvent: content, role en TOP LEVEL
        - ConversationStateUpdateEvent: key, value en TOP LEVEL
        """
        event_kind = event.get("kind", "unknown")

        if event_kind == "ActionEvent":
            tool_name = event.get("tool_name", "?")
            action = event.get("action", {})
            command = action.get("command", "")
            reasoning = event.get("reasoning_content", "")
            args = {}
            if command:
                args["command"] = command
            if action.get("path"):
                args["path"] = action["path"]
            trace._log(
                "omp_tool_start",
                {
                    "tool": tool_name,
                    "args": args,
                    "reasoning": reasoning[:300] if reasoning else "",
                },
            )

        elif event_kind == "ObservationEvent":
            tool_name = event.get("tool_name", "?")
            obs = event.get("observation", {})
            content_list = obs.get("content", [])
            is_error = obs.get("is_error", False)
            result_text = ""
            if isinstance(content_list, list):
                for c in content_list:
                    if isinstance(c, dict) and c.get("type") == "text":
                        result_text += c.get("text", "")
            elif isinstance(content_list, str):
                result_text = content_list
            trace._log(
                "omp_tool_end",
                {
                    "tool": tool_name,
                    "result": result_text[:1000],
                    "ok": not is_error,
                    "exit_code": obs.get("exit_code"),
                },
            )

        elif event_kind == "MessageEvent":
            content = event.get("content", [])
            role = event.get("role", "?")
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        text = c.get("text", "")
                        if text:
                            trace._log(
                                "omp_message_update",
                                {
                                    "text": text[:1000],
                                    "role": role,
                                },
                            )
            elif isinstance(content, str) and content:
                trace._log(
                    "omp_message_update",
                    {
                        "text": content[:1000],
                        "role": role,
                    },
                )

        elif event_kind == "ConversationStateUpdateEvent":
            key = event.get("key", "")
            value = event.get("value", {})
            if key == "goal":
                status = (value or {}).get("status", "")
                if status == "complete":
                    trace._log(
                        "omp_turn_end",
                        {
                            "event_type": "turn_end",
                            "status": status,
                            "iteration": (value or {}).get("iteration"),
                        },
                    )
            elif key == "execution_status":
                trace._log(
                    "omp_execution_status",
                    {
                        "status": value if isinstance(value, str) else str(value),
                    },
                )
            elif key == "stats":
                # Extraer tokens del ConversationStateUpdateEvent key=stats
                # Formato: {usage_to_metrics: {default: {accumulated_token_usage: {...}}}}
                if isinstance(value, dict):
                    usage_metrics = value.get("usage_to_metrics", {})
                    default_metrics = usage_metrics.get("default", {})
                    token_usage = default_metrics.get("accumulated_token_usage", {})
                    if token_usage:
                        trace._log(
                            "omp_tokens",
                            {
                                "model": token_usage.get("model", "?"),
                                "prompt_tokens": token_usage.get("prompt_tokens", 0),
                                "completion_tokens": token_usage.get(
                                    "completion_tokens", 0
                                ),
                                "reasoning_tokens": token_usage.get(
                                    "reasoning_tokens", 0
                                ),
                                "cache_read_tokens": token_usage.get(
                                    "cache_read_tokens", 0
                                ),
                            },
                        )

    def _build_prompt(
        self,
        user_prompt: str,
        governance_context: str,
        inject_governance: bool,
        circuit_id: str,
    ) -> str:
        """Construye el prompt final para OpenHands.

        Si inject_governance=True, inyecta governance + reglas + info MCP.
        Si inject_governance=False, solo devuelve el user prompt (sesión continuada).
        """
        sections: list[str] = []

        if inject_governance:
            # Governance context (onboarding + rules + config)
            if governance_context:
                sections.append(governance_context)

            # Reglas del circuito
            sections.append(
                f"# Circuit: {circuit_id}\n"
                f"Workspace: {CIRCUIT_WORKSPACES.get(circuit_id, '?')}\n"
            )

            # Sourcebot info → reemplazado por codebase-memory-mcp
            sections.append(
                "# Búsqueda de código\n\n"
                "Tenés acceso a codebase-memory-mcp como MCP server.\n"
                "Herramientas: search_graph, get_architecture, trace_path, get_code_snippet, query_graph.\n"
                "Projects indexados: desarrollo (153K nodos), compose (134K), contenedores-conti-backend (4.4K).\n"
            )

            # User prompt
            sections.append("# User Task")
            sections.append(user_prompt)
        else:
            # Continuación de sesión: solo el user prompt
            sections.append(user_prompt)

        return "\n\n---\n\n".join(sections)

    def close(self) -> None:
        """Cierra el cliente HTTP."""
        self._client.close()
