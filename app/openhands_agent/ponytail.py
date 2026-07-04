"""
ponytail.py
===========

Context manager de trazabilidad para el agente. Acumula todos los
eventos del flow (user_prompt, tool_calls, sourcebot_hits, omp events,
assistant_response, errors) y al `__exit__` los serializa a Markdown
hybrid (YAML + GFM + mermaid) y llama la tool MCP `ponytail_record_trace`
para persistirlo a .ponytail/traces/<id>.md.

Sprint 4.3 / PLAN_3 §15.quinquies.

API:
    with PonytailTrace(circuit, user_prompt, model) as trace:
        trace.record_sourcebot_hits(hits)
        trace.record_tool_call("run_salvar", args, result, latency_ms, status)
        trace.record_event("omp_message_update", {"text": "..."})
        trace.record_assistant_response("...")
    # __exit__ auto-serializa y llama la tool MCP
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

log = logging.getLogger("conti.ponytail")


class PonytailTrace:
    """Context manager que acumula eventos del flow y al exit persiste
    el trace via tool MCP `ponytail_record_trace`.

    Lifecycle:
        1. __init__: setup task_id, start time, event list
        2. __enter__: log start, return self
        3. (caller records events via record_* methods)
        4. __exit__: build trace_data dict, call TraceSerializer.to_markdown,
                      call mcp tool `ponytail_record_trace` (sync; tool hace
                      commit async en background).
    """

    def __init__(
        self,
        circuit: str,
        user_prompt: str = "",
        model: str = "",
    ) -> None:
        self.circuit = circuit
        self.user_prompt = user_prompt
        self.model = model
        self.task_id = f"tr-{uuid.uuid4().hex[:12]}"
        self.started_at = time.time()
        self.started_at_iso = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        # Accumulated state
        self.sourcebot_hits: list[dict] = []
        self.tool_calls: list[dict] = []
        self.events: list[dict] = []
        self.errors: list[str] = []
        self.tokens: dict[str, int] = {"input": 0, "output": 0, "total": 0}
        self.assistant_response: str = ""
        self.status: str = "success"  # success | error | timeout

    def __enter__(self) -> "PonytailTrace":
        log.info(
            "[ponytail] trace %s START circuit=%s model=%s",
            self.task_id,
            self.circuit,
            self.model,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ended_at = time.time()
        duration_ms = int((ended_at - self.started_at) * 1000)

        if exc_type is not None:
            self.status = "error"
            self.errors.append(f"{exc_type.__name__}: {exc_val}")

        log.info(
            "[ponytail] trace %s END duration=%dms status=%s tool_calls=%d errors=%d",
            self.task_id,
            duration_ms,
            self.status,
            len(self.tool_calls),
            len(self.errors),
        )

        # Build trace_data
        trace_data = {
            "trace_id": self.task_id,
            "timestamp": self.started_at_iso,
            "circuit": self.circuit,
            "model": self.model,
            "status": self.status,
            "duration_ms": duration_ms,
            "tokens_used": self.tokens,
            "tool_calls_count": len(self.tool_calls),
            "errors_count": len(self.errors),
            "sourcebot_hits": self.sourcebot_hits,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "user_prompt": self.user_prompt,
            "assistant_response": self.assistant_response,
        }

        # Serialize to markdown
        try:
            from app.openhands_agent.trace_serializer import TraceSerializer

            markdown = TraceSerializer.to_markdown(trace_data)
        except Exception as exc:
            log.error("[ponytail] serialization failed: %s", exc)
            return

        # Call MCP tool to persist
        self._call_record_trace(trace_data, markdown)

    def _call_record_trace(self, trace_data: dict, markdown: str) -> None:
        """Llama la tool MCP `ponytail_record_trace` via registry."""
        try:
            from app.services.registry_service import registry_service

            registry = registry_service()
            result = registry.call(
                "ponytail_record_trace",
                {
                    "trace_id": trace_data["trace_id"],
                    "circuit": trace_data["circuit"],
                    "markdown": markdown,
                    "auto_commit": os.getenv("PONYTAIL_COMMIT_TRACES", "true").lower()
                    in ("1", "true", "yes"),
                },
            )
            if result and isinstance(result, dict):
                log.info(
                    "[ponytail] trace %s persisted to %s (committed=%s)",
                    self.task_id,
                    result.get("file_path", "?"),
                    result.get("committed", False),
                )
            else:
                log.warning(
                    "[ponytail] trace %s persist returned: %s",
                    self.task_id,
                    result,
                )
        except Exception as exc:
            log.error(
                "[ponytail] trace %s persist failed: %s",
                self.task_id,
                exc,
            )

    # ── Recording methods (callable from service.py / OmpClient) ──

    def record_sourcebot_hits(self, hits: list[dict]) -> None:
        """Registra hits de sourcebot. hits = [{path, line}, ...]"""
        self.sourcebot_hits.extend(hits or [])

    def record_tool_call(
        self,
        name: str,
        args: Any,
        result: Any,
        latency_ms: int,
        status: str = "success",
    ) -> None:
        """Registra un tool call."""
        if isinstance(args, (dict, list)):
            import json

            args_str = json.dumps(args, ensure_ascii=False, default=str)
        else:
            args_str = str(args)
        if isinstance(result, (dict, list)):
            import json

            result_str = json.dumps(result, ensure_ascii=False, default=str)
        elif result is None:
            result_str = ""
        else:
            result_str = str(result)
        self.tool_calls.append(
            {
                "name": name,
                "args": args_str,
                "result": result_str,
                "latency_ms": latency_ms,
                "status": status,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
        )

    def record_event(self, event_type: str, data: dict | None = None) -> None:
        """Registra un evento del agente (omp_message_update, etc.)."""
        self.events.append(
            {
                "type": event_type,
                "timestamp": int(time.time() * 1000),
                "data": data or {},
            }
        )

    def record_assistant_response(self, response: str) -> None:
        self.assistant_response = response

    def record_tokens(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.tokens = {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        }

    def record_error(self, error_msg: str) -> None:
        self.errors.append(error_msg)
        self.status = "error"

    def mark_timeout(self) -> None:
        self.status = "timeout"
        self.errors.append("Request timed out")
