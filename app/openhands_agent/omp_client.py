# app/openhands_agent/omp_client.py
"""
OmpClient — wrapper Python sobre omp_rpc.RpcClient.

Habla con el subprocess `omp --mode rpc` dentro de conti-omp vía stdio
NDJSON sobre TCP socket :7891 (expuesto por socat en el container).

API drop-in replacement de OpenHands SDK Conversation:
  - prompt_and_wait(user_prompt, system_prompt) -> str

Diferencias vs OpenHands SDK Conversation:
  - No mantiene estado del agent loop internamente (cada prompt es
    independiente a nivel del wrapper, aunque omp --profile persiste
    session state en disco).
  - system_prompt se pasa como `append_system_prompt` al omp subprocess.
  - Mode "plan" agrega --plan flag al omp subprocess.

Usado por:
  - service.py::_invoke_on_circuit (cuando CONTI_USE_OMP_AGENT=true)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

log = logging.getLogger("conti.omp_client")

# ─────────────────────────────────────────────────────────────────────
# omp_rpc: cliente Python oficial de oh-my-pi.
# ─────────────────────────────────────────────────────────────────────

try:
    import omp_rpc  # type: ignore

    OMP_RPC_AVAILABLE = True
except Exception as _exc:  # pragma: no cover
    OMP_RPC_AVAILABLE = False
    log.warning("omp_rpc no disponible: %s", _exc)


class OmpClient:
    """Wrapper sobre omp_rpc.RpcClient con semántica de circuito Conti.

    Se conecta al bridge TCP de conti-omp (socat) y le pasa prompts NDJSON
    que omp --mode rpc procesa con su agent loop interno.

    Lifecycle:
        1. __init__: crea RpcClient con command=socat->TCP:conti-omp:7891.
           El `append_system_prompt` (reglas del circuito, Ponytail, etc.)
           se setea UNA SOLA VEZ al constructor — omp persiste esto en el
           prompt base del subprocess. Cambiarlo requiere recrear el
           RpcClient (lo cual CircuitManager hace cuando cambia el circuito).
        2. prompt_and_wait(): envía un prompt NDJSON, espera response,
           extrae el texto del último assistant message.
        3. close(): libera el RpcClient (cierra conexión TCP).

    Concurrencia:
        omp_rpc.RpcClient es "single-flight": un prompt a la vez. Para
        chats paralelos, cada uno necesita su propio OmpClient.
        CircuitManager mantiene un singleton por circuit_id.
    """

    def __init__(
        self,
        circuit_id: str,
        workspace_dir: str,
        omp_host: str = "conti-omp",
        omp_port: int = 7891,
        mode: str = "execute",  # "execute" | "plan"
        append_system_prompt: str = "",
        custom_tools: list | None = None,  # host_tool objects de omp_rpc
    ) -> None:
        self.circuit_id = circuit_id
        self.workspace_dir = workspace_dir
        self.omp_host = omp_host
        self.omp_port = omp_port
        self.mode = mode
        self._append_system_prompt = append_system_prompt
        self._custom_tools = custom_tools or []

        if not OMP_RPC_AVAILABLE:
            raise RuntimeError(
                "omp_rpc no instalado. `pip install omp_rpc` o usar OpenHands SDK fallback."
            )

        # socat hace de bridge: stdio del RpcClient <-> TCP:conti-omp:7891.
        # omp subprocess dentro de conti-omp corre --mode rpc y habla
        # NDJSON por stdio, que socat forwardea al socket.
        socat_cmd = ["socat", "-", f"TCP:{omp_host}:{omp_port}"]

        rpc_kwargs: dict[str, Any] = {
            "command": socat_cmd,
            "cwd": workspace_dir,
            "no_session": False,
            "env": {
                "OMP_CIRCUIT_CWD": str(workspace_dir),
                "OMP_MODEL": os.getenv("OMP_MODEL", "mistral/mistral-small-latest"),
                "OMP_API_KEY": os.getenv("OMP_API_KEY", ""),
                "OMP_PROFILE": os.getenv("OMP_PROFILE", "conti"),
                "OMP_PLAN": os.getenv("OMP_PLAN", "0"),
            },
        }
        if append_system_prompt:
            # append_system_prompt del RpcClient agrega texto al system
            # prompt base del subprocess omp. omp lo persiste en su config.
            rpc_kwargs["append_system_prompt"] = append_system_prompt

        self._rpc = omp_rpc.RpcClient(**rpc_kwargs)

        # omp_rpc.RpcClient requiere .start() explícito para spawn del
        # subprocess y esperar el ready signal. Hacemos start() en __init__
        # para que el usuario pueda usar el OmpClient directamente sin
        # context manager (como hacía CircuitManager con Conversation).
        try:
            self._rpc.start()
            log.info(
                "[omp:%s] client creado y started: socat -> %s:%d "
                "(cwd=%s, mode=%s, system_prompt=%d chars)",
                circuit_id,
                omp_host,
                omp_port,
                workspace_dir,
                mode,
                len(append_system_prompt),
            )
        except Exception as exc:
            log.error("[omp:%s] start() falló: %s", circuit_id, exc)
            raise RuntimeError(
                f"No se pudo iniciar omp subprocess para circuito {circuit_id}: {exc}"
            ) from exc

        # Custom tools: las MCP tools de Conti bridged via HTTP loopback
        # al :9001/mcp. omp las ve como si fueran built-in, pero el handler
        # Python hace JSON-RPC al MCP server. Sprint 4.2 / §15.quater.
        # IMPORTANTE: set_custom_tools() DEBE llamarse DESPUÉS de start()
        # porque internamente escribe al stdin del subprocess (que
        # antes de start() no existe → Broken pipe).
        if self._custom_tools:
            try:
                self._rpc.set_custom_tools(self._custom_tools)
                log.info(
                    "[omp:%s] %d custom_tools registradas (MCP bridge)",
                    circuit_id,
                    len(self._custom_tools),
                )
            except Exception as exc:
                log.error(
                    "[omp:%s] set_custom_tools falló: %s",
                    circuit_id,
                    exc,
                )

        # Agent event hooks (Sprint 4.3 / PLAN_3 §15.quater.2).
        # omp emite eventos durante su agent loop (text_delta, tool calls,
        # etc.). Los capturamos y los enviamos al PonytailTrace actual
        # (si está seteado vía set_trace()). El trace es por-request, no
        # por-singleton de OmpClient, así que los hooks solo forwardan
        # al self._trace que se actualiza por request.
        self._trace = None  # PonytailTrace activo (set_trace() antes de cada request)
        self._register_agent_hooks()

    def prompt_and_wait(self, user_prompt: str, system_prompt: str = "") -> str:
        """Envía un prompt a omp vía NDJSON y espera el response.

        Args:
            user_prompt: texto del usuario (lo que el LLM debe responder).
            system_prompt: IGNORADO en este nivel. omp_rpc.RpcClient solo
                acepta append_system_prompt en el constructor (no per-call).
                Use `append_system_prompt` del constructor para system
                prompt per-circuit. Si necesitas system prompt dinámico
                (ej. mode plan), recrea el OmpClient con `append_system_prompt`
                actualizado.

        Returns:
            Texto del último assistant message (lo que omp generó como
            respuesta final).
        """
        if system_prompt:
            log.warning(
                "[omp:%s] prompt_and_wait recibió system_prompt pero "
                "omp_rpc.RpcClient no soporta system_prompt per-call. "
                "Usá append_system_prompt del constructor (per-circuit).",
                self.circuit_id,
            )

        log.debug(
            "[omp:%s] prompt_and_wait len(user)=%d",
            self.circuit_id,
            len(user_prompt),
        )
        t0 = time.time()
        # Timeout alto para tool calls (run_salvar con prompt Mistral +
        # LLM thinking + git add + commit + push toma ~60-120s).
        # Default de omp_rpc.RpcClient es 30s, demasiado bajo.
        timeout = float(os.getenv("OMP_PROMPT_TIMEOUT", "600.0"))
        try:
            turn = self._rpc.prompt_and_wait(user_prompt, timeout=timeout)
            text = turn.require_assistant_text()

            # Extraer tokens del turn object (usage está en el turn, no en events)
            self._extract_turn_usage(turn)
        except Exception as exc:
            log.error(
                "[omp:%s] prompt_and_wait falló después de %.2fs: %s",
                self.circuit_id,
                time.time() - t0,
                exc,
            )
            raise
        log.info(
            "[omp:%s] prompt_and_wait OK en %.2fs (resp=%d chars)",
            self.circuit_id,
            time.time() - t0,
            len(text),
        )
        return text

    def _extract_turn_usage(self, turn) -> None:
        """Extrae tokens/model/provider del turn object y los registra en el trace.

        omp_rpc Turn tiene: .usage, .model, .provider (entre otros).
        Se ejecuta después de prompt_and_wait() para capturar el usage real.
        """
        trace = self._trace
        if trace is None:
            return

        try:
            # Extraer usage
            usage_raw = getattr(turn, "usage", None)
            usage_dict = self._extract_usage(usage_raw)

            # Extraer model/provider del turn
            model = getattr(turn, "model", None)
            provider = getattr(turn, "provider", None)

            # También buscar en el último assistant message del turn
            if not model or model == "?":
                messages = getattr(turn, "messages", []) or []
                for msg in reversed(messages):
                    if getattr(msg, "role", None) == "assistant":
                        model = getattr(msg, "model", None) or model
                        provider = getattr(msg, "provider", None) or provider
                        if model and model != "?":
                            break

            # Registrar evento de usage
            usage_event = {
                "model": model or "?",
                "provider": provider or "?",
                "usage": usage_dict,
            }
            trace.record_event("omp_usage", usage_event)

            # Actualizar tokens en el trace directamente
            if usage_dict:
                trace.total_input_tokens = getattr(
                    trace, "total_input_tokens", 0
                ) + usage_dict.get("input_tokens", 0)
                trace.total_output_tokens = getattr(
                    trace, "total_output_tokens", 0
                ) + usage_dict.get("output_tokens", 0)

            log.info(
                "[omp:%s] turn usage: model=%s provider=%s tokens=%s",
                self.circuit_id,
                model,
                provider,
                usage_dict,
            )
        except Exception as exc:
            log.debug("[omp:%s] _extract_turn_usage falló: %s", self.circuit_id, exc)

    # ── agent event hooks (Sprint 4.3 / §15.quater.2) ──────────────

    def set_trace(self, trace) -> None:
        """Setea el PonytailTrace activo. Llamado por service.py antes de
        cada request para que los hooks forwarden eventos al trace correcto.

        Args:
            trace: PonytailTrace instance o None para limpiar.
        """
        self._trace = trace
        if trace is not None:
            log.debug("[omp:%s] trace attached: %s", self.circuit_id, trace.task_id)

    def _register_agent_hooks(self) -> None:
        """Registra callbacks en el RpcClient para capturar eventos de omp
        durante su agent loop. Cada callback redirige al PonytailTrace
        activo (self._trace) que es por-request (no por-singleton).

        Si self._trace es None, los callbacks son no-ops.
        """
        # Hook: message updates (text_delta, etc.)
        try:
            self._rpc.on_message_update(self._on_message_update)
        except Exception as exc:
            log.warning(
                "[omp:%s] no pude registrar on_message_update: %s", self.circuit_id, exc
            )

        # Hook: tool execution start (omp invoca una tool)
        try:
            self._rpc.on_tool_execution_start(self._on_tool_start)
        except Exception as exc:
            log.warning(
                "[omp:%s] no pude registrar on_tool_execution_start: %s",
                self.circuit_id,
                exc,
            )

        # Hook: tool execution end (tool retorna resultado)
        try:
            self._rpc.on_tool_execution_end(self._on_tool_end)
        except Exception as exc:
            log.warning(
                "[omp:%s] no pude registrar on_tool_execution_end: %s",
                self.circuit_id,
                exc,
            )

        # Hook: turn end (con usage stats de tokens)
        try:
            self._rpc.on_turn_end(self._on_turn_end)
        except Exception as exc:
            log.warning(
                "[omp:%s] no pude registrar on_turn_end: %s", self.circuit_id, exc
            )

        # Hook: protocol errors (errores de NDJSON, formato, etc.)
        try:
            self._rpc.on_protocol_error(self._on_protocol_error)
        except Exception as exc:
            log.warning(
                "[omp:%s] no pude registrar on_protocol_error: %s", self.circuit_id, exc
            )

        log.info("[omp:%s] agent event hooks registrados", self.circuit_id)

    def _safe_event(self, hook_name: str, fn) -> None:
        """Llama fn(trace) si hay trace activo. Si no, no-op."""
        trace = self._trace
        if trace is None:
            return
        try:
            fn(trace)
        except Exception as exc:
            log.debug("[omp:%s] hook %s error: %s", self.circuit_id, hook_name, exc)

    def _resolve_event_name(self, event) -> str:
        """Mapea un event object al nombre del evento que vamos a loguear.

        Devuelve uno de: omp_message_update, omp_tool_start, omp_tool_end,
        omp_turn_start, omp_turn_end, omp_protocol_error.
        """
        event_type = getattr(event, "event_type", None)
        if event_type in ("text_delta", "text", "content_block_delta", "content"):
            return "omp_message_update"
        if event_type and "tool" in str(event_type).lower():
            return event_type  # ej: tool_execution_start, tool_execution_end
        if getattr(event, "tool_name", None) or getattr(event, "name", None):
            # Si tiene tool_name pero no event_type, inferir del estado
            if getattr(event, "tool_result", None) is not None or getattr(
                event, "tool_error", None
            ):
                return "omp_tool_end"
            return "omp_tool_start"
        if hasattr(event, "turn") or getattr(event, "finish_reason", None):
            return "omp_turn_end"
        if (
            hasattr(event, "error")
            or hasattr(event, "message")
            and getattr(event, "error", None)
        ):
            return "omp_protocol_error"
        return "omp_event"

    def _event_data(self, event) -> dict:
        """Extrae data serializable de un event object (pydantic, etc.).

        Maneja múltiples formatos de omp_rpc:
        - MessageUpdateEvent con .message, .event_type, .assistant_message_event
        - ToolExecutionEvent con .tool_name, .tool_args, .tool_result
        - TurnEndEvent con .usage, .turn, .finish_reason
        - Events genéricos con .model_dump() / .dict()

        Retorna SIEMPRE un dict con keys serializables.
        """
        try:
            # ── Caso 1: MessageUpdateEvent ──────────────────────────
            # Tiene .message (Message object), .event_type,
            # .assistant_message_event (para deltas)
            message = getattr(event, "message", None)
            event_type = getattr(event, "event_type", None)
            assistant_msg_ev = getattr(event, "assistant_message_event", None)

            if message is not None and not isinstance(message, str):
                # Extraer model, provider del message
                model = getattr(message, "model", None) or "?"
                provider = getattr(message, "provider", None) or "?"
                role = getattr(message, "role", "assistant")
                stop_reason = getattr(message, "stopReason", None) or getattr(
                    message, "stop_reason", None
                )

                # Extraer usage del message
                usage_raw = getattr(message, "usage", None)
                usage_dict = self._extract_usage(usage_raw)

                # Extraer texto: priorizar delta (texto incremental)
                text_delta = ""
                if assistant_msg_ev is not None:
                    delta = getattr(assistant_msg_ev, "delta", None)
                    if delta and isinstance(delta, str):
                        text_delta = delta
                    # También extraer content si existe
                    content_idx = getattr(assistant_msg_ev, "contentIndex", None)
                    # El texto completo puede estar en .content
                    full_text = getattr(assistant_msg_ev, "content", None)
                    if full_text and isinstance(full_text, str):
                        text_delta = full_text

                # Si no hay delta, extraer del message.content
                if not text_delta:
                    content = getattr(message, "content", None)
                    if isinstance(content, list) and content:
                        for item in content:
                            if isinstance(item, dict):
                                t = item.get("text", "")
                                if t:
                                    text_delta = t
                                    break
                            elif hasattr(item, "text"):
                                t = str(item.text)
                                if t:
                                    text_delta = t
                                    break
                    elif isinstance(content, str) and content:
                        text_delta = content

                # Solo registrar si hay contenido real (no init events vacíos)
                has_real_content = bool(text_delta and text_delta.strip())
                has_usage = usage_dict is not None
                has_stop = stop_reason is not None

                if not has_real_content and not has_usage and not has_stop:
                    # Init event sin contenido real - marcar como tal
                    return {
                        "event_type": "omp_init",
                        "model": model,
                        "provider": provider,
                    }

                return {
                    "event_type": event_type or "message_update",
                    "role": role,
                    "text": text_delta[:2000] if text_delta else "",
                    "model": model,
                    "provider": provider,
                    "stop_reason": stop_reason,
                    "usage": usage_dict,
                }

            # ── Caso 2: ToolExecutionEvent ──────────────────────────
            # Tiene .tool_name, .tool_args, .tool_result
            tool_name = getattr(event, "tool_name", None) or getattr(
                event, "name", None
            )
            if tool_name:
                tool_args = (
                    getattr(event, "tool_args", None)
                    or getattr(event, "args", None)
                    or {}
                )
                tool_result = getattr(event, "tool_result", None) or getattr(
                    event, "result", None
                )
                tool_error = getattr(event, "tool_error", None) or getattr(
                    event, "error", None
                )

                # Serializar args/result si son objetos
                if hasattr(tool_args, "model_dump"):
                    tool_args = tool_args.model_dump()
                elif hasattr(tool_args, "dict"):
                    tool_args = tool_args.dict()
                elif not isinstance(tool_args, dict):
                    tool_args = str(tool_args)[:1000]

                if hasattr(tool_result, "model_dump"):
                    tool_result = tool_result.model_dump()
                elif hasattr(tool_result, "dict"):
                    tool_result = tool_result.dict()
                elif tool_result is not None and not isinstance(
                    tool_result, (str, dict, list, int, float, bool)
                ):
                    tool_result = str(tool_result)[:2000]

                return {
                    "tool": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                    "error": str(tool_error)[:500] if tool_error else None,
                    "ok": tool_error is None,
                }

            # ── Caso 3: TurnEndEvent ────────────────────────────────
            # Tiene .usage, .turn, .finish_reason
            if hasattr(event, "turn") or hasattr(event, "finish_reason"):
                usage_raw = getattr(event, "usage", None)
                usage_dict = self._extract_usage(usage_raw)
                return {
                    "event_type": "turn_end",
                    "turn": getattr(event, "turn", None),
                    "finish_reason": getattr(event, "finish_reason", None),
                    "usage": usage_dict,
                }

            # ── Caso 4: ProtocolError ───────────────────────────────
            err = getattr(event, "error", None) or getattr(event, "message", None)
            if err:
                return {
                    "event_type": "protocol_error",
                    "error": str(err)[:500],
                }

            # ── Caso 5: Fallback genérico ───────────────────────────
            if hasattr(event, "model_dump"):
                return event.model_dump()
            if hasattr(event, "dict"):
                return event.dict()
            return {"raw": str(event)[:1000]}

        except Exception as exc:
            log.debug("[omp] _event_data falló: %s", exc)
            return {"raw": str(event)[:1000], "parse_error": str(exc)[:200]}

    @staticmethod
    def _extract_usage(usage_raw) -> dict | None:
        """Extrae usage normalizado de un objeto usage (pydantic, dict, etc.)."""
        if usage_raw is None:
            return None
        try:
            if hasattr(usage_raw, "model_dump"):
                d = usage_raw.model_dump()
            elif hasattr(usage_raw, "dict"):
                d = usage_raw.dict()
            elif isinstance(usage_raw, dict):
                d = usage_raw
            elif hasattr(usage_raw, "__dict__"):
                d = usage_raw.__dict__
            else:
                return None

            # Normalizar keys (omp usa distintos nombres)
            return {
                "input_tokens": d.get("input_tokens")
                or d.get("input")
                or d.get("promptTokens")
                or 0,
                "output_tokens": d.get("output_tokens")
                or d.get("output")
                or d.get("completionTokens")
                or 0,
                "total_tokens": d.get("total_tokens") or d.get("totalTokens") or 0,
                "cost": d.get("cost"),
            }
        except Exception:
            return None

    def _on_message_update(self, event) -> None:
        data = self._event_data(event)
        event_type = data.get("event_type", "omp_message_update")
        # Filtrar eventos init vacíos
        if event_type == "omp_init":
            return
        self._safe_event(
            "on_message_update",
            lambda t: t.record_event("omp_message_update", data),
        )

    def _on_tool_start(self, event) -> None:
        data = self._event_data(event)
        # Guardar args para asociarlos al tool_end correspondiente
        self._last_tool_args = data.get("args", {})
        self._last_tool_name = data.get("tool", "?")
        self._safe_event(
            "on_tool_execution_start",
            lambda t: (
                t.record_event("omp_tool_start", data),
                t.record_tool_call(
                    name=str(data.get("tool", "?")),
                    args=data.get("args", {}),
                    result="",
                    latency_ms=0,
                    status="in_progress",
                ),
            ),
        )

    def _on_tool_end(self, event) -> None:
        data = self._event_data(event)
        # Preservar los args del tool_start correspondiente
        if not data.get("args") and hasattr(self, "_last_tool_args"):
            data["args"] = self._last_tool_args
        if data.get("tool") == "?" and hasattr(self, "_last_tool_name"):
            data["tool"] = self._last_tool_name
        self._safe_event(
            "on_tool_execution_end",
            lambda t: (
                t.record_event("omp_tool_end", data),
                t.record_tool_call(
                    name=str(data.get("tool", "?")),
                    args=data.get("args", {}),
                    result=str(data.get("result", ""))[:5000],
                    latency_ms=0,
                    status="ok" if data.get("ok", True) else "error",
                ),
            ),
        )

    def _on_turn_end(self, event) -> None:
        data = self._event_data(event)
        # Forzar event_type a "turn_end" (no "message_update")
        data["event_type"] = "turn_end"
        # Capturar tokens si están en el event
        usage = data.get("usage", {}) or {}
        if isinstance(usage, dict):
            in_t = usage.get("input_tokens", 0)
            out_t = usage.get("output_tokens", 0)
            self._safe_event(
                "on_turn_end",
                lambda t: (
                    t.record_event("omp_turn_end", data),
                    t.record_tokens(input_tokens=in_t, output_tokens=out_t),
                ),
            )
        else:
            self._safe_event(
                "on_turn_end", lambda t: t.record_event("omp_turn_end", data)
            )

    def _on_protocol_error(self, event) -> None:
        data = self._event_data(event)
        self._safe_event(
            "on_protocol_error", lambda t: t.record_error(f"omp protocol error: {data}")
        )

    def close(self) -> None:
        """Libera el RpcClient (cierra el socat y por ende la conexión TCP
        al omp subprocess dentro de conti-omp)."""
        if hasattr(self, "_rpc") and self._rpc is not None:
            try:
                # RpcClient.stop() cierra el subprocess; usamos stop() en
                # lugar de close() porque es más explícito sobre recursos.
                self._rpc.stop()
            except Exception as exc:
                log.debug("[omp:%s] stop error (ignorable): %s", self.circuit_id, exc)
            self._rpc = None
            log.info("[omp:%s] client cerrado", self.circuit_id)

    # ── context manager support ────────────────────────────────

    def __enter__(self) -> "OmpClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"<OmpClient circuit={self.circuit_id} "
            f"omp={self.omp_host}:{self.omp_port} mode={self.mode}>"
        )


def is_omp_enabled() -> bool:
    """Feature flag: si CONTI_USE_OMP_AGENT=true, usar OmpClient en lugar
    de OpenHands SDK. Default false (mantiene status quo mientras validamos)."""
    return os.getenv("CONTI_USE_OMP_AGENT", "").lower() in ("1", "true", "yes", "on")


def make_omp_client_for_circuit(
    circuit_cfg: Any,
    append_system_prompt: str = "",
    custom_tools: list | None = None,
) -> OmpClient:
    """Factory: construye un OmpClient configurado para un CircuitConfig.

    Args:
        circuit_cfg: CircuitConfig con workspace_dir, id, etc.
        append_system_prompt: system prompt FIJO para el subprocess omp
            (reglas de Ponytail + reglas del circuito + tool list).
            Se setea UNA VEZ al constructor. Cambiarlo requiere recrear
            el OmpClient.
        custom_tools: lista de host_tool (omp_rpc) que omp puede invocar.
            Sprint 4.2: bridged MCP tools (run_salvar, odoo_*, etc.) que
            ejecutan via HTTP loopback al :9001/mcp.

    Returns:
        OmpClient listo para prompt_and_wait().

    Raises:
        RuntimeError si omp_rpc no está disponible.
    """
    return OmpClient(
        circuit_id=circuit_cfg.id,
        workspace_dir=circuit_cfg.workspace_dir,
        omp_host=os.getenv("OMP_HOST", "conti-omp"),
        omp_port=int(os.getenv("OMP_PORT", "7891")),
        mode="execute",  # plan mode se setea dinámicamente en service.py
        append_system_prompt=append_system_prompt,
        custom_tools=custom_tools,
    )
