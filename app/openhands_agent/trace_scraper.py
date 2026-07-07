"""
trace_scraper.py — Scrape incremental de conversaciones OpenHands.

Lee los eventos JSON persistidos en disco por el Agent Server
(/app/workspace/conversations/{conv_id}/events/event-NNNNN-*.json)
y genera secciones de traza Ponytail por turno.

Soporta multi-turn incremental: solo scrapea events nuevos (desde
last_event_num) y appenda a la traza MD existente sin perder datos.
"""

from __future__ import annotations

import glob
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("conti.trace_scraper")


# ─────────────────────────────────────────────────────────────────────
# 1. Scrape events from disk
# ─────────────────────────────────────────────────────────────────────


def scrape_conversation_events(
    conv_id: str, since_event: int = -1
) -> list[dict[str, Any]]:
    """Lee eventos del disco desde since_event+1.

    Lee /app/workspace/conversations/{conv_id_no_hyphens}/events/event-NNNNN-*.json
    Solo retorna eventos con número > since_event.
    Ordena por número de secuencia.
    """
    clean_id = conv_id.replace("-", "")
    events_dir = Path(f"/app/workspace/conversations/{clean_id}/events")
    if not events_dir.exists():
        log.warning("[trace_scraper] events dir not found: %s", events_dir)
        return []

    pattern = str(events_dir / "event-*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        return []

    result: list[dict[str, Any]] = []
    for fp in files:
        fname = Path(fp).name
        m = re.match(r"event-(\d+)-", fname)
        if not m:
            continue
        event_num = int(m.group(1))
        if event_num <= since_event:
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                ev = json.load(f)
            ev["_event_num"] = event_num
            result.append(ev)
        except Exception as exc:
            log.warning("[trace_scraper] error reading %s: %s", fp, exc)

    log.info(
        "[trace_scraper] scraped %d new events (since=%d) for conv %s",
        len(result),
        since_event,
        conv_id,
    )
    return result


# ─────────────────────────────────────────────────────────────────────
# 2. Convert Agent Server events → Ponytail events
# ─────────────────────────────────────────────────────────────────────


def events_to_ponytail(raw_events: list[dict]) -> list[dict[str, Any]]:
    """Mapea eventos del Agent Server a eventos Ponytail.

    Tipos de evento resultantes:
    - omp_tool_start: ActionEvent (tool ≠ finish)
    - omp_tool_end: ObservationEvent
    - omp_turn_complete: ActionEvent(finish) → respuesta del agente
    - omp_file_write: ActionEvent(write_file)
    - omp_file_edit: ActionEvent(file_editor, str_replace)
    - omp_agent_error: AgentErrorEvent
    - omp_tokens: ConversationStateUpdateEvent(key=stats)
    """
    ponytail_events: list[dict[str, Any]] = []

    for ev in raw_events:
        kind = ev.get("kind", "unknown")
        ts = ev.get("timestamp", "")
        event_num = ev.get("_event_num", -1)

        if kind == "ActionEvent":
            tool = ev.get("tool_name", "?")
            action = ev.get("action", {})
            reasoning = ev.get("reasoning_content", "")

            if tool == "finish":
                # Respuesta final del agente
                msg = action.get("message", "")
                ponytail_events.append(
                    {
                        "type": "omp_turn_complete",
                        "event_num": event_num,
                        "timestamp": ts,
                        "message": msg,
                        "reasoning": reasoning[:500] if reasoning else "",
                    }
                )
            elif tool == "write_file":
                path = action.get("file_path", action.get("path", ""))
                content = action.get("content", "")
                ponytail_events.append(
                    {
                        "type": "omp_file_write",
                        "event_num": event_num,
                        "timestamp": ts,
                        "path": path,
                        "content_len": len(content),
                    }
                )
            elif tool == "file_editor" and action.get("command") in (
                "write",
                "str_replace",
                "insert",
            ):
                path = action.get("path", action.get("file_path", ""))
                cmd = action.get("command", "")
                ponytail_events.append(
                    {
                        "type": "omp_file_edit",
                        "event_num": event_num,
                        "timestamp": ts,
                        "command": cmd,
                        "path": path,
                    }
                )
            else:
                # Tool genérica (terminal, read_file, glob, grep, etc.)
                command = action.get("command", "")
                path = action.get("path", "")
                args: dict[str, Any] = {}
                if command:
                    args["command"] = command
                if path:
                    args["path"] = path
                ponytail_events.append(
                    {
                        "type": "omp_tool_start",
                        "event_num": event_num,
                        "timestamp": ts,
                        "tool": tool,
                        "args": args,
                        "reasoning": reasoning[:500] if reasoning else "",
                    }
                )

        elif kind == "ObservationEvent":
            tool = ev.get("tool_name", "?")
            obs = ev.get("observation", {})
            content_list = obs.get("content", [])
            is_error = obs.get("is_error", False)
            result_text = ""
            if isinstance(content_list, list):
                for c in content_list:
                    if isinstance(c, dict) and c.get("type") == "text":
                        result_text += c.get("text", "")
            elif isinstance(content_list, str):
                result_text = content_list

            ponytail_events.append(
                {
                    "type": "omp_tool_end",
                    "event_num": event_num,
                    "timestamp": ts,
                    "tool": tool,
                    "result": result_text[:2000],
                    "ok": not is_error,
                    "exit_code": obs.get("exit_code"),
                }
            )

        elif kind == "MessageEvent":
            role = ev.get("role", "?")
            content_text = ""
            content = ev.get("content", [])
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        content_text += c.get("text", "")
            elif isinstance(content, str):
                content_text = content
            if content_text.strip():
                ponytail_events.append(
                    {
                        "type": "omp_message",
                        "event_num": event_num,
                        "timestamp": ts,
                        "role": role,
                        "text": content_text,
                    }
                )

        elif kind == "AgentErrorEvent":
            error_content = ev.get("content", ev.get("error", ""))
            if isinstance(error_content, list):
                texts = []
                for c in error_content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        texts.append(c.get("text", ""))
                error_content = " ".join(texts)
            ponytail_events.append(
                {
                    "type": "omp_agent_error",
                    "event_num": event_num,
                    "timestamp": ts,
                    "error": str(error_content)[:500],
                }
            )

        elif kind == "ConversationStateUpdateEvent":
            key = ev.get("key", "")
            value = ev.get("value", {})
            if key == "stats" and isinstance(value, dict):
                usage_metrics = value.get("usage_to_metrics", {})
                default_metrics = usage_metrics.get("default", {})
                token_usage = default_metrics.get("accumulated_token_usage", {})
                if token_usage:
                    ponytail_events.append(
                        {
                            "type": "omp_tokens",
                            "event_num": event_num,
                            "timestamp": ts,
                            "model": token_usage.get("model", "?"),
                            "prompt_tokens": token_usage.get("prompt_tokens", 0),
                            "completion_tokens": token_usage.get(
                                "completion_tokens", 0
                            ),
                            "reasoning_tokens": token_usage.get("reasoning_tokens", 0),
                            "cache_read_tokens": token_usage.get(
                                "cache_read_tokens", 0
                            ),
                            "cache_write_tokens": token_usage.get(
                                "cache_write_tokens", 0
                            ),
                            "per_turn_token": token_usage.get("per_turn_token", 0),
                        }
                    )

    return ponytail_events


# ─────────────────────────────────────────────────────────────────────
# 3. Build turn section markdown
# ─────────────────────────────────────────────────────────────────────


def _parse_ts(ts: str) -> datetime | None:
    """Parse ISO timestamp to datetime."""
    if not ts:
        return None
    try:
        # Handle both with and without timezone
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _fmt_ts(dt: datetime | None) -> str:
    """Format datetime to HH:MM:SS."""
    if dt is None:
        return "?"
    return dt.strftime("%H:%M:%S")


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}m {s:.0f}s"


def build_turn_section(
    ponytail_events: list[dict],
    turn_num: int,
    user_prompt: str,
    is_first_turn: bool,
    governance_text: str | None,
    circuit_id: str,
    conversation_id: str,
    workspace: str,
    started_at: str,
    ended_at: str,
    agent_response: str = "",
) -> tuple[str, dict]:
    """Genera el markdown de un turno. Returns (markdown, stats_dict).

    Template Turn 1: metadata + Prompt Inyectado + Gantt + Tools +
                     Respuesta + Archivos + Errores + Reasoning
    Template Turn 2+: metadata + Prompt Completo + Gantt + Tools +
                      Respuesta + Archivos + Errores + Reasoning
    """
    tool_starts = [e for e in ponytail_events if e["type"] == "omp_tool_start"]
    tool_ends = [e for e in ponytail_events if e["type"] == "omp_tool_end"]
    finishes = [e for e in ponytail_events if e["type"] == "omp_turn_complete"]
    file_writes = [e for e in ponytail_events if e["type"] == "omp_file_write"]
    file_edits = [e for e in ponytail_events if e["type"] == "omp_file_edit"]
    errors = [e for e in ponytail_events if e["type"] == "omp_agent_error"]
    obs_errors = [e for e in tool_ends if not e.get("ok", True)]
    token_events = [e for e in ponytail_events if e["type"] == "omp_tokens"]

    # Stats
    tool_counts: dict[str, int] = {}
    for e in tool_starts:
        t = e.get("tool", "?")
        tool_counts[t] = tool_counts.get(t, 0) + 1

    last_tokens = token_events[-1] if token_events else {}
    total_tool_calls = len(tool_starts)
    total_events = len(ponytail_events)

    dt_start = _parse_ts(started_at)
    dt_end = _parse_ts(ended_at)
    duration_s = 0.0
    if dt_start and dt_end:
        duration_s = (dt_end - dt_start).total_seconds()

    stats = {
        "total_events": total_events,
        "total_tool_calls": total_tool_calls,
        "tool_counts": tool_counts,
        "file_writes": len(file_writes),
        "file_edits": len(file_edits),
        "errors": len(errors) + len(obs_errors),
        "prompt_tokens": last_tokens.get("prompt_tokens", 0),
        "completion_tokens": last_tokens.get("completion_tokens", 0),
        "reasoning_tokens": last_tokens.get("reasoning_tokens", 0),
        "cache_read_tokens": last_tokens.get("cache_read_tokens", 0),
        "cache_write_tokens": last_tokens.get("cache_write_tokens", 0),
        "per_turn_token": last_tokens.get("per_turn_token", 0),
        "llm_calls": len(token_events),
        "duration_s": duration_s,
    }

    # ── Build markdown ──
    lines: list[str] = []
    prompt_short = user_prompt[:100] + ("..." if len(user_prompt) > 100 else "")

    lines.append(f"## Turn {turn_num}: {prompt_short}")
    lines.append("")
    lines.append(f"- **Circuito**: `{circuit_id}`")
    lines.append(
        f"- **Conversación OpenHands**: [`{conversation_id}`](http://localhost:3012/conversations/{conversation_id})"
    )
    lines.append(f"- **Workspace**: `{workspace}`")
    lines.append(f"- **Inicio**: {started_at}")
    lines.append(f"- **Fin**: {ended_at}")
    lines.append(f"- **Duración**: {_fmt_duration(duration_s)}")
    lines.append(f"- **Eventos**: {total_events}")
    lines.append("")

    # ── Prompt section ──
    if is_first_turn and governance_text:
        lines.append("## Prompt Inyectado (governance + reglas + user)")
        lines.append("")
        lines.append("```text")
        lines.append(governance_text[:5000])
        if len(governance_text) > 5000:
            lines.append("...[truncado para legibilidad]")
        lines.append("```")
    else:
        lines.append("## Prompt Completo")
        lines.append("")
        lines.append("```text")
        lines.append(user_prompt)
        lines.append("```")
    lines.append("")

    # ── Gantt chart ──
    lines.append("## Timeline (Gantt)")
    lines.append("")
    lines.append("```mermaid")
    lines.append("gantt")
    lines.append(f"    title Ejecución Turn {turn_num} - {circuit_id}")
    lines.append("    dateFormat  HH:mm:ss")
    lines.append("    axisFormat  %H:%M:%S")
    lines.append("")
    lines.append("    section Ejecución")

    paired_events = _pair_tool_events(ponytail_events)
    for pe in paired_events:
        t_start = _fmt_ts(_parse_ts(pe.get("start_ts", "")))
        dur = pe.get("duration", 0.1)
        tool = pe.get("tool", "?")
        ok = pe.get("ok", True)
        status = "crit" if not ok else "done"
        dur_str = f"{max(dur, 0.1):.1f}s"
        safe_tool = tool.replace(",", ";").replace('"', "'")[:30]
        lines.append(f"    {safe_tool} ({dur_str})  :{status}, {t_start}, {dur_str}")

    lines.append("```")
    lines.append("")

    # ── Tools table ──
    lines.append(f"## Tools Ejecutadas ({total_tool_calls})")
    lines.append("")
    lines.append("| # | Tool | Inicio | Duración | OK | Args/Result |")
    lines.append("|---|------|--------|----------|-----|-------------|")

    for idx, pe in enumerate(paired_events, 1):
        tool = pe.get("tool", "?")
        t_start = _fmt_ts(_parse_ts(pe.get("start_ts", "")))
        dur = pe.get("duration", 0.0)
        ok = pe.get("ok", True)
        args_str = pe.get("args_str", "")
        result_str = pe.get("result_str", "")
        display = args_str or result_str
        display = display[:120].replace("|", "\\|").replace("\n", " ")
        ok_icon = "✅" if ok else "❌"
        lines.append(
            f"| {idx} | `{tool}` | {t_start} | {_fmt_duration(dur)} | {ok_icon} | {display} |"
        )

    lines.append("")

    # ── Respuesta del Agente ──
    # Prioridad: omp_turn_complete event (from disk) → agent_response (from SSE)
    response_text = ""
    if finishes:
        response_text = finishes[-1].get("message", "")
    if not response_text.strip() and agent_response:
        response_text = agent_response
    if response_text.strip():
        lines.append("## Respuesta del Agente")
        lines.append("")
        lines.append(response_text)
        lines.append("")

    # ── Archivos Escritos ──
    if file_writes or file_edits:
        lines.append("## Archivos Escritos/Editados")
        lines.append("")
        lines.append("| Path | Método | Tamaño |")
        lines.append("|------|--------|--------|")
        for fw in file_writes:
            p = fw.get("path", "?")
            cl = fw.get("content_len", 0)
            lines.append(f"| `{p}` | write_file | {cl} chars |")
        for fe in file_edits:
            p = fe.get("path", "?")
            cmd = fe.get("command", "?")
            lines.append(f"| `{p}` | {cmd} | — |")
        lines.append("")

    # ── Errores ──
    all_errors = []
    for e in errors:
        all_errors.append({"tool": "agent_error", "error": e.get("error", "")})
    for e in obs_errors:
        all_errors.append(
            {"tool": e.get("tool", "?"), "error": e.get("result", "")[:200]}
        )
    if all_errors:
        lines.append("## Errores")
        lines.append("")
        lines.append("| # | Tool | Error |")
        lines.append("|---|------|-------|")
        for idx, err in enumerate(all_errors, 1):
            t = err["tool"]
            e_str = err["error"][:150].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {idx} | `{t}` | {e_str} |")
        lines.append("")

    # ── Tokens por Llamada LLM ──
    if token_events:
        lines.append("## Tokens por Llamada LLM")
        lines.append("")
        lines.append(
            "| # | Prompt | Cache Read | Cache % | Nuevos | Completion | Reasoning | Delta |"
        )
        lines.append(
            "|---|--------|------------|---------|--------|------------|-----------|-------|"
        )
        for idx, te in enumerate(token_events, 1):
            pt = te.get("prompt_tokens", 0)
            cr = te.get("cache_read_tokens", 0)
            ct = te.get("completion_tokens", 0)
            rt = te.get("reasoning_tokens", 0)
            delta = te.get("per_turn_token", 0)
            pct = f"{cr / pt * 100:.1f}%" if pt else "—"
            nuevos = max(pt - cr, 0)
            lines.append(
                f"| {idx} | {pt:,} | {cr:,} | {pct} | {nuevos:,} | {ct:,} | {rt:,} | {delta:,} |"
            )
        lines.append("")

    # ── Reasoning ──
    reasoning_items = [
        (e.get("tool", "?"), e.get("reasoning", ""), e.get("start_ts", ""))
        for e in paired_events
        if e.get("reasoning")
    ]
    if reasoning_items:
        lines.append("## Reasoning del Agente")
        lines.append("")
        for tool, reasoning, ts in reasoning_items:
            t_str = _fmt_ts(_parse_ts(ts))
            lines.append(f"### {t_str} → `{tool}`")
            lines.append("")
            lines.append(f"> {reasoning}")
            lines.append("")

    return "\n".join(lines), stats


def _pair_tool_events(ponytail_events: list[dict]) -> list[dict]:
    """Paira tool_start con su tool_end siguiente del mismo tool.

    Devuelve lista de dicts con: tool, start_ts, duration, ok, args_str, result_str, reasoning.
    """
    starts = [e for e in ponytail_events if e["type"] == "omp_tool_start"]
    ends = [e for e in ponytail_events if e["type"] == "omp_tool_end"]
    finishes = [e for e in ponytail_events if e["type"] == "omp_turn_complete"]

    # Index ends by event_num for fast lookup
    end_by_num: dict[int, dict] = {}
    for e in ends:
        # Find the end that follows this start
        pass

    # Simpler: sequential pairing
    paired: list[dict] = []
    end_idx = 0
    for start in starts:
        tool = start.get("tool", "?")
        start_ts = start.get("timestamp", "")
        start_dt = _parse_ts(start_ts)
        args = start.get("args", {})
        reasoning = start.get("reasoning", "")

        args_str = ""
        if args.get("command"):
            args_str = args["command"][:150]
        elif args.get("path"):
            args_str = args["path"]

        # Find matching end
        matched_end = None
        for i in range(end_idx, len(ends)):
            if ends[i].get("tool") == tool:
                matched_end = ends[i]
                end_idx = i + 1
                break

        duration = 0.1
        ok = True
        result_str = ""
        if matched_end:
            end_ts = matched_end.get("timestamp", "")
            end_dt = _parse_ts(end_ts)
            if start_dt and end_dt:
                duration = max((end_dt - start_dt).total_seconds(), 0.1)
            ok = matched_end.get("ok", True)
            result_str = matched_end.get("result", "")[:150]

        paired.append(
            {
                "tool": tool,
                "start_ts": start_ts,
                "duration": duration,
                "ok": ok,
                "args_str": args_str,
                "result_str": result_str,
                "reasoning": reasoning,
            }
        )

    return paired


# ─────────────────────────────────────────────────────────────────────
# 4. Frontmatter generation
# ─────────────────────────────────────────────────────────────────────


def build_frontmatter(
    trace_id: str,
    circuit_id: str,
    session_id: str,
    conversation_id: str,
    workspace: str,
    model: str,
    started_at: str,
    ended_at: str,
    turn_num: int,
    turn_stats: dict,
    all_stats: dict | None = None,
) -> str:
    """Genera YAML frontmatter. Si all_stats se provee, usa acumulados."""
    s = all_stats or turn_stats
    duration = s.get("duration_s", 0)
    prompt_tokens = s.get("prompt_tokens", 0)
    completion_tokens = s.get("completion_tokens", 0)
    reasoning_tokens = s.get("reasoning_tokens", 0)
    cache_read = s.get("cache_read_tokens", 0)
    cache_write = s.get("cache_write_tokens", 0)
    per_turn = s.get("per_turn_token", 0)
    llm_calls = s.get("llm_calls", 0)
    total_tokens = prompt_tokens + completion_tokens
    # Tokens realmente nuevos (sin cache)
    new_tokens = max(prompt_tokens - cache_read, 0)

    tools_lines = []
    for tool, count in sorted(s.get("tool_counts", {}).items()):
        tools_lines.append(f"  {tool}: {count}")
    tools_str = "\n".join(tools_lines) if tools_lines else "  (none)"

    return f"""---
trace_id: {trace_id}
circuit: {circuit_id}
session_id: {session_id}
conversation_id: {conversation_id}
turns: {turn_num}
workspace: {workspace}
model: {model}
started_at: {started_at}
ended_at: {ended_at}
duration_s: {duration:.1f}
events_count: {s.get("total_events", 0)}
tokens:
  prompt_acumulado: {prompt_tokens}
  cache_read: {cache_read}
  cache_hit_pct: {(cache_read / prompt_tokens * 100) if prompt_tokens else 0:.1f}%
  nuevos_procesados: {new_tokens}
  completion: {completion_tokens}
  reasoning: {reasoning_tokens}
  total: {total_tokens}
  ultimo_delta: {per_turn}
llm_calls: {llm_calls}
tools_executed:
{tools_str}
---"""


def merge_stats(all_stats: dict | None, turn_stats: dict) -> dict:
    """Merge turn stats into accumulated stats."""
    if all_stats is None:
        return dict(turn_stats)

    merged = dict(all_stats)
    merged["total_events"] = all_stats.get("total_events", 0) + turn_stats.get(
        "total_events", 0
    )
    merged["total_tool_calls"] = all_stats.get("total_tool_calls", 0) + turn_stats.get(
        "total_tool_calls", 0
    )
    merged["duration_s"] = all_stats.get("duration_s", 0) + turn_stats.get(
        "duration_s", 0
    )
    merged["file_writes"] = all_stats.get("file_writes", 0) + turn_stats.get(
        "file_writes", 0
    )
    merged["file_edits"] = all_stats.get("file_edits", 0) + turn_stats.get(
        "file_edits", 0
    )
    merged["errors"] = all_stats.get("errors", 0) + turn_stats.get("errors", 0)
    merged["prompt_tokens"] = all_stats.get("prompt_tokens", 0) + turn_stats.get(
        "prompt_tokens", 0
    )
    merged["completion_tokens"] = all_stats.get(
        "completion_tokens", 0
    ) + turn_stats.get("completion_tokens", 0)
    merged["reasoning_tokens"] = all_stats.get("reasoning_tokens", 0) + turn_stats.get(
        "reasoning_tokens", 0
    )
    merged["cache_read_tokens"] = all_stats.get(
        "cache_read_tokens", 0
    ) + turn_stats.get("cache_read_tokens", 0)
    merged["cache_write_tokens"] = all_stats.get(
        "cache_write_tokens", 0
    ) + turn_stats.get("cache_write_tokens", 0)
    merged["llm_calls"] = all_stats.get("llm_calls", 0) + turn_stats.get("llm_calls", 0)
    # per_turn_token: promedio ponderado o el del último turno
    merged["per_turn_token"] = turn_stats.get(
        "per_turn_token", all_stats.get("per_turn_token", 0)
    )

    # Merge tool counts
    tc = dict(all_stats.get("tool_counts", {}))
    for tool, count in turn_stats.get("tool_counts", {}).items():
        tc[tool] = tc.get(tool, 0) + count
    merged["tool_counts"] = tc

    return merged


# ─────────────────────────────────────────────────────────────────────
# 5. Persist turn to trace file
# ─────────────────────────────────────────────────────────────────────


def persist_turn(
    trace_path: str | None,
    turn_section: str,
    turn_num: int,
    turn_stats: dict,
    is_first_turn: bool,
    trace_id: str,
    circuit_id: str,
    session_id: str,
    conversation_id: str,
    workspace: str,
    model: str,
    started_at: str,
    ended_at: str,
) -> str:
    """Persiste un turno a la traza MD.

    Si is_first_turn o trace_path no existe: crea archivo nuevo.
    Si trace_path existe: lee archivo, actualiza frontmatter, append turno.

    Returns: path del archivo de traza.
    """
    if is_first_turn or not trace_path or not Path(trace_path).exists():
        # Crear archivo nuevo
        frontmatter = build_frontmatter(
            trace_id=trace_id,
            circuit_id=circuit_id,
            session_id=session_id,
            conversation_id=conversation_id,
            workspace=workspace,
            model=model,
            started_at=started_at,
            ended_at=ended_at,
            turn_num=turn_num,
            turn_stats=turn_stats,
        )
        content = frontmatter + "\n\n" + turn_section
        if trace_path:
            Path(trace_path).parent.mkdir(parents=True, exist_ok=True)
            Path(trace_path).write_text(content, encoding="utf-8")
            _git_commit_trace(trace_path, trace_id, circuit_id)
        return trace_path or ""

    # Append a traza existente
    existing = Path(trace_path).read_text(encoding="utf-8")

    # Extraer frontmatter existente para merge de stats
    existing_stats = _parse_frontmatter_stats(existing)

    # Merge stats acumulados
    merged = merge_stats(existing_stats, turn_stats)

    # Regenerar frontmatter con stats acumulados
    new_frontmatter = build_frontmatter(
        trace_id=trace_id,
        circuit_id=circuit_id,
        session_id=session_id,
        conversation_id=conversation_id,
        workspace=workspace,
        model=model,
        started_at=started_at,
        ended_at=ended_at,
        turn_num=turn_num,
        turn_stats=turn_stats,
        all_stats=merged,
    )

    # Extraer body existente (sin frontmatter)
    body = _strip_frontmatter(existing)

    # Reescribir: nuevo frontmatter + body existente + separador + nuevo turno
    content = new_frontmatter + "\n\n" + body + "\n\n---\n\n" + turn_section
    Path(trace_path).write_text(content, encoding="utf-8")

    _git_commit_trace(trace_path, trace_id, circuit_id)

    return trace_path


def _parse_frontmatter_stats(content: str) -> dict:
    """Extrae stats del frontmatter YAML existente."""
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    fm = m.group(1)
    stats: dict[str, Any] = {}
    for line in fm.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            try:
                stats[key] = int(val)
            except ValueError:
                try:
                    stats[key] = float(val)
                except ValueError:
                    stats[key] = val
    # Reconstruct tool_counts from tools_executed
    tc: dict[str, int] = {}
    in_tools = False
    for line in fm.split("\n"):
        stripped = line.strip()
        if stripped == "tools_executed:":
            in_tools = True
            continue
        if in_tools:
            if stripped and ":" in stripped and not stripped.startswith(" "):
                in_tools = False
            elif stripped.startswith("  ") and ":" in stripped:
                parts = stripped.split(":")
                if len(parts) == 2:
                    tool_name = parts[0].strip()
                    try:
                        tc[tool_name] = int(parts[1].strip())
                    except ValueError:
                        pass
    if tc:
        stats["tool_counts"] = tc
    return stats


def _strip_frontmatter(content: str) -> str:
    """Remueve el YAML frontmatter del contenido."""
    m = re.match(r"^---\n.*?\n---\n*", content, re.DOTALL)
    if m:
        return content[m.end() :]
    return content


def _git_commit_trace(trace_path: str, trace_id: str, circuit_id: str) -> None:
    """Git add + commit del archivo de traza. Non-blocking (thread pool)."""
    import subprocess
    from pathlib import Path

    p = Path(trace_path)
    if not p.exists():
        return

    # Determinar repo root según circuito
    repo_map = {
        "desarrollo": "/desarrollo",
        "produccion": "/compose",
        "backend": "/contenedores/conti-backend",
    }
    repo = repo_map.get(circuit_id)
    if not repo:
        return

    try:
        subprocess.run(
            ["git", "add", str(p)],
            cwd=repo,
            capture_output=True,
            timeout=10,
        )
        msg = f"ponytail({circuit_id}): {trace_id} {time.strftime('%H:%M:%S')}"
        subprocess.run(
            ["git", "commit", "-m", msg, "--no-verify"],
            cwd=repo,
            capture_output=True,
            timeout=15,
        )
        log.info("[trace_scraper] git committed: %s", p.name)
    except Exception as exc:
        log.warning("[trace_scraper] git commit failed: %s", exc)
