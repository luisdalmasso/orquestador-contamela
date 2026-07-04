"""
trace_serializer.py
==================

Serializa los datos acumulados del PonytailTrace a un Markdown con
formato Hybrid:
  - YAML Frontmatter (metadatos estructurados queryables)
  - GitHub-Flavored Markdown body (secciones, tablas, código)
  - Mermaid sequence diagram (renderiza automático en GitHub)

Salida final es un string que `ponytail_record_trace` tool persiste a
.ponytail/traces/<id>.md.

Schema del frontmatter (Sprint 4.3 / PLAN_3 §15.quinquies.3):

  ---
  trace_id: "tr-..."
  timestamp: "ISO-8601"
  circuit: "produccion|desarrollo|backend|libre"
  model: "mistral/..."
  status: "success|error|timeout"
  duration_ms: int
  tokens_used: {input, output, total}
  tool_calls_count: int
  errors_count: int
  sourcebot_hits: [{path, line}]
  tool_calls: [{name, args, result, latency_ms, status}]
  errors: [str]
  ---

  # 🔍 Traza Ponytail: `tr-...`
  ...
"""

from __future__ import annotations

import json
from typing import Any


def _yaml_value(v: Any) -> str:
    """Serializa un valor Python a YAML scalar/list."""
    if v is None or v == "":
        return '""'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        # Escape: use double-quoted if contains special chars
        if any(c in v for c in [":", "#", "\n", '"', "'"]):
            escaped = v.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return v
    if isinstance(v, list):
        if not v:
            return "[]"
        items = [f"      - {_yaml_value(item)}" for item in v]
        return "\n" + "\n".join(items)
    if isinstance(v, dict):
        if not v:
            return "{}"
        lines = []
        for k, val in v.items():
            lines.append(f"  {k}: {_yaml_value(val)}")
        return "\n" + "\n".join(lines)
    return str(v)


def _format_status_icon(status: str) -> str:
    return {
        "success": "🟢 **SUCCESS**",
        "error": "🔴 **ERROR**",
        "timeout": "🟡 **TIMEOUT**",
    }.get(status, status)


def _format_messages(user_prompt: str, assistant_response: str) -> str:
    lines = ["## 💬 Mensajes\n"]
    if user_prompt:
        lines.append("### User (input)")
        lines.append("```")
        lines.append(user_prompt[:5000])
        if len(user_prompt) > 5000:
            lines.append(f"\n[truncated: {len(user_prompt) - 5000} chars más]")
        lines.append("```")
        lines.append("")
    if assistant_response:
        lines.append("### Assistant (output)")
        lines.append("```")
        lines.append(assistant_response[:5000])
        if len(assistant_response) > 5000:
            lines.append(f"\n[truncated: {len(assistant_response) - 5000} chars más]")
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _format_sourcebot_hits(hits: list[dict]) -> str:
    if not hits:
        return ""
    lines = ["## 📡 Sourcebot Hits\n"]
    for h in hits:
        path = h.get("path", "?")
        line = h.get("line", "?")
        lines.append(f"- `{path}:{line}`")
    lines.append("")
    return "\n".join(lines)


def _format_tool_calls(calls: list[dict]) -> str:
    if not calls:
        return ""
    lines = [f"## 🔧 Tool Calls ({len(calls)})\n"]
    for i, call in enumerate(calls, 1):
        name = call.get("name", "?")
        status = call.get("status", "?")
        latency = call.get("latency_ms", "?")
        args = call.get("args", "{}")
        result = call.get("result", "")

        lines.append(f"### {i}. `{name}`")
        lines.append(f"- **status:** {status}")
        lines.append(f"- **latency:** {latency}ms")
        lines.append("- **args:**")
        lines.append("```json")
        if isinstance(args, str):
            lines.append(args[:2000])
            if len(args) > 2000:
                lines.append(f"\n[truncated: {len(args) - 2000} chars más]")
        else:
            args_str = json.dumps(args, ensure_ascii=False, indent=2)
            lines.append(args_str[:2000])
            if len(args_str) > 2000:
                lines.append(f"\n[truncated: {len(args_str) - 2000} chars más]")
        lines.append("```")
        if result:
            lines.append("- **result:**")
            lines.append("```json")
            result_str = (
                result
                if isinstance(result, str)
                else json.dumps(result, ensure_ascii=False, indent=2)
            )
            lines.append(result_str[:5000])
            if len(result_str) > 5000:
                lines.append(f"\n[truncated: {len(result_str) - 5000} chars más]")
            lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _format_errors(errors: list[str]) -> str:
    if not errors:
        return ""
    lines = ["## ❌ Errors\n"]
    for i, err in enumerate(errors, 1):
        lines.append(f"{i}. `{err}`")
    lines.append("")
    return "\n".join(lines)


def _format_mermaid(trace_data: dict) -> str:
    """Genera sequenceDiagram mermaid. Solo basic, sin loops por tool calls
    individuales (eso se ve en la tabla)."""
    circuit = trace_data.get("circuit", "?")
    tool_calls_count = len(trace_data.get("tool_calls", []))
    has_sourcebot = bool(trace_data.get("sourcebot_hits"))

    lines = [
        "```mermaid",
        "sequenceDiagram",
        "    autonumber",
        f"    Client->>Router: POST /v1/chat/completions (circuit: {circuit})",
        "    Router->>Ponytail: enter context",
    ]
    if has_sourcebot:
        lines.append("    par Context build")
        lines.append("        Ponytail->>Sourcebot: search (top-5)")
        lines.append("        Sourcebot-->>Ponytail: paths")
        lines.append("    end")
    else:
        lines.append("    Note over Router,Ponytail: no sourcebot pre-context")

    lines.append("    Ponytail->>Omp: append_system_prompt + user_task")
    lines.append("    Omp-->>Ponytail: turn_start")
    if tool_calls_count:
        lines.append(f"    loop {tool_calls_count} tool calls")
        lines.append("        Omp->>MCP: call tool (name, args)")
        lines.append("        MCP->>Backend: dispatch handler")
        lines.append("        Backend-->>MCP: result")
        lines.append("        MCP-->>Omp: result")
        lines.append("    end")
    lines.append("    Omp-->>Ponytail: agent_end (text)")
    lines.append("    Ponytail->>Backend: mcp_record_trace")
    lines.append("    Backend->>Backend: write .ponytail/traces/<id>.md")
    lines.append("    Backend->>Backend: git add + commit (async)")
    lines.append("    Ponytail-->>Client: OpenAI response")
    lines.append("```")
    return "\n".join(lines)


class TraceSerializer:
    """Serializa trace_data dict a Markdown hybrid (YAML + GFM)."""

    @staticmethod
    def to_markdown(trace_data: dict) -> str:
        """Genera el Markdown completo listo para escribir a .md.

        Args:
            trace_data: dict con los campos:
              - trace_id (str)
              - timestamp (str, ISO 8601)
              - circuit (str)
              - model (str)
              - status (str: success|error|timeout)
              - duration_ms (int)
              - tokens_used (dict: {input, output, total})
              - tool_calls_count (int)
              - errors_count (int)
              - sourcebot_hits (list[dict]: {path, line})
              - tool_calls (list[dict])
              - errors (list[str])
              - user_prompt (str)
              - assistant_response (str)

        Returns:
            str Markdown con YAML frontmatter + GFM body.
        """
        trace_id = trace_data.get("trace_id", "tr-unknown")
        timestamp = trace_data.get("timestamp", "")
        circuit = trace_data.get("circuit", "unknown")
        model = trace_data.get("model", "unknown")
        status = trace_data.get("status", "unknown")
        duration_ms = trace_data.get("duration_ms", 0)
        tokens = trace_data.get("tokens_used", {}) or {}
        tool_calls_count = trace_data.get("tool_calls_count", 0)
        errors_count = trace_data.get("errors_count", 0)
        sourcebot_hits = trace_data.get("sourcebot_hits", []) or []
        tool_calls = trace_data.get("tool_calls", []) or []
        errors = trace_data.get("errors", []) or []
        user_prompt = trace_data.get("user_prompt", "")
        assistant_response = trace_data.get("assistant_response", "")

        # ── Frontmatter ──
        fm_lines = ["---"]
        fm_lines.append(f"trace_id: {_yaml_value(trace_id)}")
        fm_lines.append(f"timestamp: {_yaml_value(timestamp)}")
        fm_lines.append(f"circuit: {_yaml_value(circuit)}")
        fm_lines.append(f"model: {_yaml_value(model)}")
        fm_lines.append(f"status: {_yaml_value(status)}")
        fm_lines.append(f"duration_ms: {_yaml_value(duration_ms)}")
        fm_lines.append("tokens_used:")
        fm_lines.append(f"  input: {_yaml_value(tokens.get('input', 0))}")
        fm_lines.append(f"  output: {_yaml_value(tokens.get('output', 0))}")
        fm_lines.append(f"  total: {_yaml_value(tokens.get('total', 0))}")
        fm_lines.append(f"tool_calls_count: {_yaml_value(tool_calls_count)}")
        fm_lines.append(f"errors_count: {_yaml_value(errors_count)}")
        if sourcebot_hits:
            fm_lines.append("sourcebot_hits:")
            for h in sourcebot_hits:
                fm_lines.append("  - path: " + _yaml_value(h.get("path", "")))
                fm_lines.append("    line: " + _yaml_value(h.get("line", "")))
        if tool_calls:
            fm_lines.append("tool_calls:")
            for c in tool_calls:
                fm_lines.append(f"  - name: {_yaml_value(c.get('name', ''))}")
                fm_lines.append(f"    status: {_yaml_value(c.get('status', ''))}")
                fm_lines.append(
                    f"    latency_ms: {_yaml_value(c.get('latency_ms', 0))}"
                )
        if errors:
            fm_lines.append("errors:")
            for e in errors:
                fm_lines.append(f"  - {_yaml_value(e)}")
        fm_lines.append("---")
        fm_lines.append("")
        frontmatter = "\n".join(fm_lines)

        # ── Body ──
        status_icon = _format_status_icon(status)
        body_lines = [
            f"# 🔍 Traza Ponytail: `{trace_id}`",
            "",
            f"Modo: `{circuit.upper()}` | Estado: {status_icon} | Fecha: `{timestamp}`",
            "",
            "## 🗺️ Flujo de Ejecución",
            "",
            "Este diagrama se renderiza automáticamente en GitHub:",
            "",
            _format_mermaid(trace_data),
            "",
        ]

        # Mensajes user/assistant
        body_lines.append(_format_messages(user_prompt, assistant_response))

        # Tool calls
        tool_section = _format_tool_calls(tool_calls)
        if tool_section:
            body_lines.append(tool_section)

        # Sourcebot hits
        sb_section = _format_sourcebot_hits(sourcebot_hits)
        if sb_section:
            body_lines.append(sb_section)

        # Errors
        err_section = _format_errors(errors)
        if err_section:
            body_lines.append(err_section)

        body = "\n".join(body_lines)

        return frontmatter + "\n" + body
