"""
ponytail_trace_tools.py
=======================

MCP tool `ponytail_record_trace` — persiste trazas de observabilidad
del agente a .ponytail/traces/<id>.md y las commitea al repo local
(NO push) en background thread con lock por circuit.

Flujo:
  1. Fase 1 (sync): escribir .md a .ponytail/traces/<YYYY-MM-DD>_<circuit>_<id>.md
  2. Fase 2 (async thread pool con lock por circuit): git add + commit
     - Si commit falla, retry x3 con backoff exponencial
     - Si branch está detached, log warning y skip commit (la trace queda
       en filesystem para commit manual)
  3. Return: dict con trace_id, file_path, commit_status

Sprint 4.3 / PLAN_3 §15.quinquies.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

log = logging.getLogger("conti.ponytail_trace_tools")

# Lazy-loaded circuit locks (singleton)
_locks_executor: ThreadPoolExecutor | None = None
_circuit_locks: dict[str, Any] = {}


def _get_executor() -> ThreadPoolExecutor:
    global _locks_executor
    if _locks_executor is None:
        _locks_executor = ThreadPoolExecutor(
            max_workers=int(os.getenv("PONYTAIL_THREAD_POOL", "2")),
            thread_name_prefix="ponytail-trace",
        )
    return _locks_executor


def _get_lock(circuit_id: str):
    """Devuelve un Lock dedicado por circuit. Lock por circuit permite
    paralelismo inter-circuit pero serializa commits del mismo circuit."""
    if circuit_id not in _circuit_locks:
        import threading

        _circuit_locks[circuit_id] = threading.Lock()
    return _circuit_locks[circuit_id]


# ─────────────────────────────────────────────────────────────────────
# MCP tool
# ─────────────────────────────────────────────────────────────────────


def _sanitize_trace_id(trace_id: str) -> str:
    """Sanitiza trace_id para usar como filename: solo [a-z0-9-_]."""
    return re.sub(r"[^a-z0-9\-_]", "", trace_id.lower())[:64] or "tr-unknown"


def _build_file_path(circuit_id: str, trace_id: str, base_dir: str) -> Path:
    """Path: <base_dir>/<YYYY-MM-DD>_<circuit>_<trace_id>.md"""
    date = time.strftime("%Y-%m-%d")
    safe_circuit = re.sub(r"[^a-z0-9\-_]", "", circuit_id.lower())[:32]
    safe_id = _sanitize_trace_id(trace_id)
    return Path(base_dir) / f"{date}_{safe_circuit}_{safe_id}.md"


def _find_git_root(start: Path) -> Path | None:
    """Busca el git root subiendo desde start. Retorna None si no hay."""
    cur = start.resolve()
    for _ in range(10):  # max 10 niveles
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def _git_commit_sync(file_path: Path, message: str) -> tuple[bool, str]:
    """Sincroniza git add + commit del trace. Retorna (success, error_msg).

    Encuentra el git root subiendo desde file_path (puede estar varios
    niveles arriba de file_path, ej: si file_path es
    /repo/.ponytail/traces/x.md, el root es /repo/).
    """
    git_root = _find_git_root(file_path.parent)
    if git_root is None:
        return False, "not_a_git_repo"
    try:
        # git add solo este archivo (no -A, para no contaminar con untracked)
        result = subprocess.run(
            ["git", "add", str(file_path)],
            cwd=str(git_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False, f"git add failed: {result.stderr[:200]}"
        # git commit
        result = subprocess.run(
            ["git", "commit", "-m", message, "--no-verify"],
            cwd=str(git_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False, f"git commit failed: {result.stderr[:200]}"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "git commit timeout"
    except Exception as exc:
        return False, f"git commit error: {exc}"


def _git_commit_with_retry(file_path: Path, message: str, max_retries: int = 3) -> dict:
    """Commit con retry + backoff exponencial. Retorna dict con status."""
    for attempt in range(max_retries):
        success, error = _git_commit_sync(file_path, message)
        if success:
            return {"committed": True, "attempt": attempt + 1, "error": None}
        log.warning(
            "[ponytail_trace] commit attempt %d/%d failed: %s",
            attempt + 1,
            max_retries,
            error,
        )
        if attempt < max_retries - 1:
            time.sleep(2**attempt)  # 1s, 2s, 4s
    return {"committed": False, "attempt": max_retries, "error": error}


def _git_push_sync(file_path: Path) -> tuple[bool, str]:
    """Push el commit al remote. Retorna (success, error_msg)."""
    git_root = _find_git_root(file_path.parent)
    if git_root is None:
        return False, "not_a_git_repo"
    try:
        result = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            cwd=str(git_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return False, f"git push failed: {result.stderr[:200]}"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "git push timeout"
    except Exception as exc:
        return False, f"git push error: {exc}"


def _git_push_with_retry(file_path: Path, max_retries: int = 2) -> dict:
    """Push con retry. Retorna {pushed: bool, error: str|None}."""
    for attempt in range(max_retries):
        success, error = _git_push_sync(file_path)
        if success:
            return {"pushed": True, "attempt": attempt + 1, "error": None}
        log.warning(
            "[ponytail_trace] push attempt %d/%d failed: %s",
            attempt + 1,
            max_retries,
            error,
        )
        if attempt < max_retries - 1:
            time.sleep(2**attempt)
    return {"pushed": False, "attempt": max_retries, "error": error}


def _get_trace_dir_for_circuit(circuit_id: str) -> Path:
    """Devuelve el directorio de trazas según el circuito.

    Reglas:
    - `produccion`: /compose/.ponytail/traces/ si hay cambios en /compose,
      sino /desarrollo/.ponytail/traces/.
    - `desarrollo`: /desarrollo/.ponytail/traces/
    - `backend`: /contenedores/conti-backend/.ponytail/traces/
    - `libre`: /tmp/free-agent/.ponytail/traces/
    """
    if circuit_id == "produccion":
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd="/compose",
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path("/compose/.ponytail/traces/")
        except Exception:
            pass
        return Path("/desarrollo/.ponytail/traces/")
    elif circuit_id == "desarrollo":
        return Path("/desarrollo/.ponytail/traces/")
    elif circuit_id == "backend":
        return Path("/contenedores/conti-backend/.ponytail/traces/")
    elif circuit_id == "libre":
        return Path("/tmp/free-agent/.ponytail/traces/")
    else:
        log.warning("[ponytail_trace] circuito desconocido: %s", circuit_id)
        return Path("/tmp/free-agent/.ponytail/traces/")


def ponytail_record_trace(config: Any, arguments: dict) -> dict[str, Any]:
    """MCP tool: persiste el trace a filesystem + commit async.

    Args (arguments):
        trace_id (str, REQUERIDO): UUID-like del trace.
        circuit (str, REQUERIDO): id del circuit (desarrollo, produccion, etc).
        markdown (str, REQUERIDO): cuerpo Markdown completo con
            YAML frontmatter + GFM body (generado por trace_serializer).
        auto_commit (bool, opcional, default=True): si True, hace git
            add + commit en background thread.

    Returns:
        {
          "status": "ok" | "error",
          "trace_id": str,
          "file_path": str (absolute path),
          "committed": bool,
          "commit_attempt": int,
          "commit_error": str | None,
        }
    """
    trace_id = arguments.get("trace_id", "").strip()
    circuit = arguments.get("circuit", "").strip()
    markdown = arguments.get("markdown", "")
    auto_commit = arguments.get("auto_commit", True)

    if not trace_id or not circuit or not markdown:
        return {
            "status": "error",
            "error": "Faltan parámetros requeridos: trace_id, circuit, markdown",
        }

    # Fase 1 (sync): determinar el directorio correcto según el circuito
    base_path = _get_trace_dir_for_circuit(circuit)

    # Si se proporciona session_dir, crear subcarpeta por sesión
    session_dir = arguments.get("session_dir", "")
    if session_dir:
        base_path = base_path / session_dir

    try:
        base_path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return {
            "status": "error",
            "error": f"No se pudo crear directorio {base_path}: {exc}",
        }

    file_path = _build_file_path(circuit, trace_id, str(base_path))
    commit_status = {"committed": False, "attempt": 0, "error": "no_commit_requested"}

    try:
        file_path.write_text(markdown, encoding="utf-8")
        log.info(
            "[ponytail_trace] wrote %s (%d bytes)",
            file_path,
            len(markdown),
        )
    except Exception as exc:
        return {
            "status": "error",
            "error": f"No se pudo escribir {file_path}: {exc}",
        }

    # Fase 2 (async): git add + commit en background
    if auto_commit and os.getenv("PONYTAIL_COMMIT_TRACES", "true").lower() in (
        "1",
        "true",
        "yes",
    ):
        # Verificar si estamos en un git repo
        try:
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(base_path),
                capture_output=True,
                timeout=5,
            )
        except Exception:
            log.warning(
                "[ponytail_trace] %s no está en un git repo, skip commit",
                base_path,
            )
            commit_status = {
                "committed": False,
                "attempt": 0,
                "error": "not_a_git_repo",
            }
        else:
            lock = _get_lock(circuit)
            # Si hay otro commit del mismo circuit corriendo, esperamos
            if lock.locked():
                log.info(
                    "[ponytail_trace] %s esperando lock de circuit %s",
                    trace_id,
                    circuit,
                )
            with lock:
                executor = _get_executor()
                commit_message = (
                    f"ponytail({circuit}): {trace_id} {time.strftime('%H:%M:%S')}"
                )
                # Submit y esperar resultado (sync porque la tool MCP
                # espera al cliente para retornar resultado)
                future = executor.submit(
                    _git_commit_with_retry, file_path, commit_message
                )
                commit_status = future.result(timeout=30)

                # Fase 2b (opcional): push a origin si PONYTAIL_PUSH_TRACES=true
                if commit_status.get("committed") and os.getenv(
                    "PONYTAIL_PUSH_TRACES", "false"
                ).lower() in ("1", "true", "yes"):
                    push_status = _git_push_with_retry(file_path)
                    commit_status["pushed"] = push_status.get("pushed", False)
                    commit_status["push_error"] = push_status.get("error")
                else:
                    commit_status["pushed"] = False
                    commit_status["push_error"] = "push_not_requested"

    return {
        "status": "ok",
        "trace_id": trace_id,
        "file_path": str(file_path),
        "committed": commit_status.get("committed", False),
        "commit_attempt": commit_status.get("attempt", 0),
        "commit_error": commit_status.get("error"),
    }


# ─────────────────────────────────────────────────────────────────────
# Helper: serializar traza JSON → Markdown con YAML frontmatter
# ─────────────────────────────────────────────────────────────────────


def trace_to_markdown(trace_id: str, circuit: str, trace_data: dict) -> str:
    """Convierte un trace dict (de PonytailTrace) a Markdown renderizable.

    Formato: YAML frontmatter + GFM body con diagrama Gantt de la
    secuencia de eventos + timeline detallado con duración por evento.
    """
    import datetime as _dt
    import os

    try:
        import zoneinfo

        _tz = zoneinfo.ZoneInfo(os.environ.get("TZ", "UTC"))
    except Exception:
        _tz = None

    def _ts_to_local(ts: float) -> str:
        if not ts:
            return ""
        dt = (
            _dt.datetime.fromtimestamp(ts, tz=_tz)
            if _tz
            else _dt.datetime.fromtimestamp(ts)
        )
        return dt.isoformat()

    def _ts_to_short(ts: float) -> str:
        if not ts:
            return ""
        dt = (
            _dt.datetime.fromtimestamp(ts, tz=_tz)
            if _tz
            else _dt.datetime.fromtimestamp(ts)
        )
        return dt.strftime("%H:%M:%S")

    def _trunc(s: str, n: int = 200) -> str:
        s = str(s).replace("\n", " ").strip()
        return s[:n] + ("...[truncated]" if len(s) > n else "")

    started = trace_data.get("started_at")
    ended = trace_data.get("ended_at")
    duration = round((ended - started), 3) if (started and ended) else 0
    started_iso = _ts_to_local(started) if started else ""
    ended_iso = _ts_to_local(ended) if ended else ""
    events = trace_data.get("events", [])

    # ── Tokens + tools + model + conversation_id ──────────────────
    total_input = 0
    total_output = 0
    total_reasoning = 0
    model_seen = set()
    tools_executed: dict[str, int] = {}
    conversation_id = ""
    response_text = ""
    prompt_injected = ""

    for ev in events:
        data = ev.get("data", {})
        if not isinstance(data, dict):
            continue

        etype = ev.get("event", "")

        # Tokens de omp_tokens event
        if etype == "omp_tokens":
            total_input += data.get("prompt_tokens", 0) or 0
            total_output += data.get("completion_tokens", 0) or 0
            total_reasoning += data.get("reasoning_tokens", 0) or 0
            model = data.get("model")
            if model:
                model_seen.add(model)

        # Tokens de usage en otros eventos
        usage = data.get("usage")
        if isinstance(usage, dict):
            total_input += usage.get("input_tokens", 0) or 0
            total_output += usage.get("output_tokens", 0) or 0

        model = data.get("model")
        if model and model != "?" and model != "omp_init":
            model_seen.add(model)

        if etype == "omp_tool_start":
            tool = data.get("tool", "?")
            tools_executed[tool] = tools_executed.get(tool, 0) + 1

        # conversation_id
        if etype == "conversation_created":
            conversation_id = data.get("conversation_id", "")

        # prompt_injected
        if etype == "prompt_injected":
            prompt_injected = data.get("prompt_full", "")

        # response (último openhands_orchestrator_end o último MessageEvent)
        if etype == "openhands_orchestrator_end":
            r = data.get("response", "")
            if r:
                response_text = r
        if etype == "omp_message_update":
            text = data.get("text", "")
            if text and len(text) > len(response_text):
                response_text = text

    # ── Frontmatter YAML ───────────────────────────────────────────
    fm = "---\n"
    fm += f"trace_id: {trace_id}\n"
    fm += f"circuit: {circuit}\n"
    fm += f"task_name: {_trunc(trace_data.get('task_name', ''), 200)}\n"
    if conversation_id:
        fm += f"conversation_id: {conversation_id}\n"
    fm += f"started_at: {started_iso}\n"
    fm += f"ended_at: {ended_iso}\n"
    fm += f"duration_s: {duration}\n"
    fm += f"events_count: {len(events)}\n"
    fm += f"workspace: {trace_data.get('workspace', '')}\n"
    if model_seen:
        fm += f"model: {', '.join(model_seen)}\n"
    fm += f"total_input_tokens: {total_input}\n"
    fm += f"total_output_tokens: {total_output}\n"
    fm += f"total_reasoning_tokens: {total_reasoning}\n"
    fm += f"total_tokens: {total_input + total_output}\n"
    if tools_executed:
        fm += "tools_executed:\n"
        for tname, tcount in sorted(tools_executed.items()):
            fm += f"  {tname}: {tcount}\n"
    fm += "---\n\n"

    body: list[str] = []
    body.append(f"# Traza: {_trunc(trace_data.get('task_name', trace_id), 100)}")
    body.append("")
    body.append(f"- **Circuito**: `{circuit}`")
    if conversation_id:
        body.append(
            f"- **Conversación OpenHands**: [`{conversation_id}`](http://localhost:3012/conversations/{conversation_id})"
        )
    body.append(f"- **Workspace**: `{trace_data.get('workspace', 'N/A')}`")
    body.append(f"- **Inicio**: {started_iso}")
    body.append(f"- **Fin**: {ended_iso}")
    body.append(f"- **Duración**: {duration}s")
    body.append(f"- **Eventos**: {len(events)}")
    body.append("")

    # ── Gantt timeline ──────────────────────────────────────────────
    body.append("## Timeline (Gantt)")
    body.append("")
    body.append("```mermaid")
    body.append("gantt")
    body.append(f"    title Ejecución - {circuit}")
    body.append("    dateFormat  HH:mm:ss")
    body.append("    axisFormat  %H:%M:%S")
    body.append("")
    body.append("    section Setup")
    body.append(f"    start           :{_ts_to_short(started or 0)}, 1s")

    tool_events = []
    for i, ev in enumerate(events):
        etype = ev.get("event", "")
        data = ev.get("data", {}) or {}
        ts = ev.get("ts", 0)
        if etype == "omp_tool_start":
            tool_events.append(
                {
                    "idx": i,
                    "tool": data.get("tool", "?"),
                    "start_ts": ts,
                    "args": data.get("args", {}),
                }
            )
        elif etype == "omp_tool_end":
            for te in reversed(tool_events):
                if te.get("end_ts") is None:
                    te["end_ts"] = ts
                    te["ok"] = data.get("ok", True)
                    te["result_preview"] = _trunc(data.get("result", ""), 80)
                    break
        elif etype == "governance_tool":
            tool_events.append(
                {
                    "idx": i,
                    "tool": f"governance:{data.get('tool', '?')}",
                    "start_ts": ts,
                    "end_ts": ts + 0.01,
                }
            )

    body.append("")
    body.append("    section Ejecución")
    for te in tool_events:
        tool = te.get("tool", "?")
        start_ts = te.get("start_ts", 0)
        end_ts = te.get("end_ts", start_ts + 1)
        dur = max(round(end_ts - start_ts, 1), 0.1)
        ok = te.get("ok", True)
        status = "done" if ok else "crit"
        label = f"{tool} ({dur}s)"
        body.append(f"    {label}  :{status}, {_ts_to_short(start_ts)}, {dur}s")

    body.append("")
    body.append("    section Dead Time")
    prev_end = started or 0
    for te in tool_events:
        tool_start = te.get("start_ts", 0)
        gap = round(tool_start - prev_end, 1)
        if gap > 2.0:
            body.append(f"    gap ({gap}s)  :active, {_ts_to_short(prev_end)}, {gap}s")
        prev_end = te.get("end_ts", tool_start + 1)

    body.append("```")
    body.append("")

    # ── Tabla resumen de tools ──────────────────────────────────────
    body.append("## Tools Ejecutadas")
    body.append("")
    body.append("| # | Tool | Inicio | Duración | OK | Args/Result |")
    body.append("|---|------|--------|----------|-----|-------------|")
    for i, te in enumerate(tool_events, 1):
        tool = te.get("tool", "?")
        start_ts = te.get("start_ts", 0)
        end_ts = te.get("end_ts", start_ts)
        dur = round(end_ts - start_ts, 1)
        ok = "✅" if te.get("ok", True) else "❌"
        args = te.get("args", {})
        result_preview = te.get("result_preview", "")
        detail = ""
        if isinstance(args, dict) and args:
            cmd = args.get("command", "")
            path = args.get("path", "")
            if cmd:
                detail = f"`{_trunc(cmd, 60)}`"
            elif path:
                detail = f"`{path}`"
        if not detail and result_preview:
            detail = _trunc(result_preview, 60)
        body.append(
            f"| {i} | `{tool}` | {_ts_to_short(start_ts)} | {dur}s | {ok} | {detail} |"
        )
    body.append("")

    # ── Reasoning del agente ────────────────────────────────────────
    body.append("## Reasoning del Agente")
    body.append("")
    for ev in events:
        if ev.get("event") == "omp_tool_start":
            data = ev.get("data", {}) or {}
            reasoning = data.get("reasoning", "")
            if reasoning:
                tool = data.get("tool", "?")
                body.append(f"### {_ts_to_short(ev.get('ts', 0))} → `{tool}`")
                body.append("")
                body.append(f"> {reasoning}")
                body.append("")

    # ── Prompt inyectado (governance + reglas + user) ───────────────
    if prompt_injected:
        body.append("## Prompt Inyectado (governance + reglas + user)")
        body.append("")
        body.append("```text")
        body.append(prompt_injected[:5000])
        body.append("```")
        body.append("")
    else:
        # Fallback: prompt del usuario
        start_ev = next((e for e in events if e.get("event") == "start"), None)
        if start_ev:
            full_task = (start_ev.get("data") or {}).get("task", "")
            if full_task:
                body.append("## Prompt Completo (input del usuario)")
                body.append("")
                body.append("```text")
                body.append(full_task)
                body.append("```")
                body.append("")

    # ── Response completa ──────────────────────────────────────────
    if response_text:
        body.append("## Response Completa (output del agente)")
        body.append("")
        body.append("```text")
        body.append(response_text[:5000])
        body.append("```")
        body.append("")

    return fm + "\n".join(body)
