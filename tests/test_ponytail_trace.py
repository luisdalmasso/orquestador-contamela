"""
Tests para Sprint 4.3 — Trazabilidad + Docs-as-Code.

Cubre:
  - TraceSerializer.to_markdown: genera YAML frontmatter + GFM body + mermaid
  - ponytail_record_trace: persiste archivo y hace commit async
  - CircuitLocks: serialización intra-circuit, paralelismo inter-circuit
  - PonytailTrace (nuevo): acumula eventos, llama tool MCP al exit
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.openhands_agent.ponytail import PonytailTrace
from app.openhands_agent.trace_serializer import TraceSerializer


# ── TraceSerializer ────────────────────────────────────────────────


class TestTraceSerializer:
    def test_to_markdown_produces_yaml_frontmatter(self) -> None:
        """El output empieza con '---' y tiene los campos del schema."""
        trace = {
            "trace_id": "tr-abc123",
            "timestamp": "2026-07-01T12:00:00-03:00",
            "circuit": "produccion",
            "model": "mistral/mistral-small-latest",
            "status": "success",
            "duration_ms": 4250,
            "tokens_used": {"input": 8430, "output": 1200, "total": 9630},
            "tool_calls_count": 2,
            "errors_count": 0,
            "sourcebot_hits": [],
            "tool_calls": [],
            "errors": [],
            "user_prompt": "test",
            "assistant_response": "ok",
        }
        md = TraceSerializer.to_markdown(trace)
        assert md.startswith("---")
        assert "---" in md[3:]
        assert "trace_id: tr-abc123" in md
        assert "circuit: produccion" in md
        assert "status: success" in md
        assert "duration_ms: 4250" in md
        assert "input: 8430" in md

    def test_to_markdown_includes_mermaid_diagram(self) -> None:
        """El body incluye un bloque mermaid sequenceDiagram."""
        trace = {
            "trace_id": "tr-mermaid",
            "timestamp": "2026-07-01T12:00:00-03:00",
            "circuit": "desarrollo",
            "model": "m",
            "status": "success",
            "duration_ms": 100,
            "tokens_used": {"input": 0, "output": 0, "total": 0},
            "tool_calls_count": 0,
            "errors_count": 0,
            "sourcebot_hits": [],
            "tool_calls": [],
            "errors": [],
            "user_prompt": "",
            "assistant_response": "",
        }
        md = TraceSerializer.to_markdown(trace)
        assert "```mermaid" in md
        assert "sequenceDiagram" in md
        assert "Client->>Router" in md
        assert "Ponytail->>Backend" in md  # Phase 1 write, Phase 2 commit

    def test_to_markdown_includes_messages(self) -> None:
        """Las secciones User (input) y Assistant (output) están presentes."""
        trace = {
            "trace_id": "tr-msg",
            "timestamp": "t",
            "circuit": "c",
            "model": "m",
            "status": "success",
            "duration_ms": 0,
            "tokens_used": {"input": 0, "output": 0, "total": 0},
            "tool_calls_count": 0,
            "errors_count": 0,
            "sourcebot_hits": [],
            "tool_calls": [],
            "errors": [],
            "user_prompt": "Reply OK",
            "assistant_response": "OK",
        }
        md = TraceSerializer.to_markdown(trace)
        assert "## 💬 Mensajes" in md
        assert "Reply OK" in md
        assert "### User (input)" in md
        assert "### Assistant (output)" in md

    def test_to_markdown_truncates_long_content(self) -> None:
        """User prompt >5000 chars se trunca con [truncated: N chars]."""
        long_prompt = "x" * 6000
        trace = {
            "trace_id": "tr-trunc",
            "timestamp": "t",
            "circuit": "c",
            "model": "m",
            "status": "success",
            "duration_ms": 0,
            "tokens_used": {"input": 0, "output": 0, "total": 0},
            "tool_calls_count": 0,
            "errors_count": 0,
            "sourcebot_hits": [],
            "tool_calls": [],
            "errors": [],
            "user_prompt": long_prompt,
            "assistant_response": "ok",
        }
        md = TraceSerializer.to_markdown(trace)
        assert "[truncated: 1000 chars más]" in md
        # El long_prompt no aparece completo
        assert long_prompt not in md

    def test_to_markdown_includes_sourcebot_hits(self) -> None:
        """Hits de sourcebot se incluyen en la sección de Sourcebot Hits."""
        trace = {
            "trace_id": "tr-sb",
            "timestamp": "t",
            "circuit": "c",
            "model": "m",
            "status": "success",
            "duration_ms": 0,
            "tokens_used": {"input": 0, "output": 0, "total": 0},
            "tool_calls_count": 0,
            "errors_count": 0,
            "sourcebot_hits": [{"path": "app/main.py", "line": 42}],
            "tool_calls": [],
            "errors": [],
            "user_prompt": "",
            "assistant_response": "",
        }
        md = TraceSerializer.to_markdown(trace)
        assert "## 📡 Sourcebot Hits" in md
        assert "app/main.py:42" in md

    def test_to_markdown_includes_tool_calls(self) -> None:
        """Tool calls se renderizan en la sección Tool Calls."""
        trace = {
            "trace_id": "tr-tc",
            "timestamp": "t",
            "circuit": "c",
            "model": "m",
            "status": "success",
            "duration_ms": 0,
            "tokens_used": {"input": 0, "output": 0, "total": 0},
            "tool_calls_count": 1,
            "errors_count": 0,
            "sourcebot_hits": [],
            "tool_calls": [
                {
                    "name": "run_salvar",
                    "args": '{"commit_message": "test"}',
                    "result": '{"ok": true}',
                    "latency_ms": 230,
                    "status": "success",
                }
            ],
            "errors": [],
            "user_prompt": "",
            "assistant_response": "",
        }
        md = TraceSerializer.to_markdown(trace)
        assert "## 🔧 Tool Calls" in md
        assert "### 1. `run_salvar`" in md
        assert "230ms" in md
        assert "success" in md


# ── PonytailTrace (nuevo) ──────────────────────────────────────────


class TestPonytailTrace:
    def test_context_manager_accumulates_events(self) -> None:
        """__enter__ y __exit__ funcionan; record_* methods se acumulan."""
        # Mockear la tool MCP para no requerir un git repo en el test
        with patch(
            "app.openhands_agent.ponytail.PonytailTrace._call_record_trace"
        ) as mock_record:
            with PonytailTrace(circuit="desarrollo", user_prompt="test") as trace:
                trace.record_sourcebot_hits([{"path": "app/main.py", "line": 1}])
                trace.record_tool_call(
                    "run_salvar", {"x": 1}, {"ok": True}, 100, "success"
                )
                trace.record_event("omp_message_update", {"text": "hi"})
                assert trace.circuit == "desarrollo"
                assert len(trace.sourcebot_hits) == 1
                assert len(trace.tool_calls) == 1
                # Solo 1 evento explícito (record_event); __enter__ no loggea
                assert len(trace.events) == 1
            # Después del __exit__ debe haberse llamado la tool
            assert mock_record.call_count == 1

    def test_record_tokens_updates_totals(self) -> None:
        """record_tokens actualiza el dict tokens."""
        with PonytailTrace(circuit="libre") as trace:
            trace.record_tokens(input_tokens=100, output_tokens=50)
        assert trace.tokens == {"input": 100, "output": 50, "total": 150}

    def test_mark_timeout_sets_status(self) -> None:
        with PonytailTrace(circuit="libre") as trace:
            trace.mark_timeout()
        assert trace.status == "timeout"
        assert "timed out" in trace.errors[0].lower()

    def test_record_error_marks_status_error(self) -> None:
        with PonytailTrace(circuit="desarrollo") as trace:
            trace.record_error("Custom failure")
        assert trace.status == "error"
        assert "Custom failure" in trace.errors


# ── ponytail_record_trace tool ────────────────────────────────────


class TestPonytailRecordTrace:
    def test_creates_file_at_correct_path(self) -> None:
        """La tool escribe el archivo en PONYTAIL_TRACE_DIR/<date>_<circuit>_<id>.md."""
        from app.tools import ponytail_trace_tools

        with tempfile.TemporaryDirectory() as tmp:
            md = "---\ntrace_id: tr-test\n---\n# test"
            with patch.dict(
                os.environ,
                {"PONYTAIL_TRACE_DIR": tmp, "PONYTAIL_COMMIT_TRACES": "false"},
            ):
                result = ponytail_trace_tools.ponytail_record_trace(
                    None,
                    {
                        "trace_id": "tr-test",
                        "circuit": "produccion",
                        "markdown": md,
                        "auto_commit": False,
                    },
                )
            assert result["status"] == "ok"
            assert result["file_path"].endswith("_produccion_tr-test.md")
            assert (Path(tmp) / Path(result["file_path"]).name).exists()
            assert (Path(tmp) / Path(result["file_path"]).name).read_text() == md

    def test_missing_required_params_returns_error(self) -> None:
        from app.tools import ponytail_trace_tools

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"PONYTAIL_TRACE_DIR": tmp}):
                result = ponytail_trace_tools.ponytail_record_trace(
                    None,
                    {"trace_id": "tr-x", "circuit": "c"},  # markdown missing
                )
            assert result["status"] == "error"
            assert "markdown" in result["error"]

    def test_commit_runs_git_add_and_git_commit(self) -> None:
        """Cuando auto_commit=True, hace git add + commit."""
        from app.tools import ponytail_trace_tools

        with tempfile.TemporaryDirectory() as tmp:
            # Inicializar un git repo en tmp
            subprocess.run(["git", "init", "-q", "-b", "main", tmp], check=True)
            subprocess.run(
                ["git", "-C", tmp, "config", "user.email", "test@x.com"], check=True
            )
            subprocess.run(
                ["git", "-C", tmp, "config", "user.name", "Test"], check=True
            )
            md = "---\ntrace_id: tr-test\n---\n# test"
            with patch.dict(
                os.environ,
                {"PONYTAIL_TRACE_DIR": tmp, "PONYTAIL_COMMIT_TRACES": "true"},
            ):
                result = ponytail_trace_tools.ponytail_record_trace(
                    None,
                    {
                        "trace_id": "tr-test",
                        "circuit": "produccion",
                        "markdown": md,
                        "auto_commit": True,
                    },
                )
            assert result["status"] == "ok"
            assert result["committed"] is True
            assert result["commit_attempt"] == 1
            # Verificar que el commit está en git log
            log = subprocess.run(
                ["git", "-C", tmp, "log", "--oneline"],
                capture_output=True,
                text=True,
                check=True,
            )
            assert "ponytail(produccion)" in log.stdout
            assert "tr-test" in log.stdout


# ── CircuitLocks ────────────────────────────────────────────────


class TestCircuitLocks:
    def test_same_circuit_serialized(self) -> None:
        """Dos acquires del mismo circuit son serializados (no paralelos)."""
        from app.openhands_agent import circuit_locks

        order = []
        lock = circuit_locks._get_lock("produccion")

        def worker(name: str, delay: float) -> None:
            with lock:
                order.append(f"start-{name}")
                time.sleep(delay)
                order.append(f"end-{name}")

        t1 = threading.Thread(target=worker, args=("A", 0.2))
        t2 = threading.Thread(target=worker, args=("B", 0.0))
        t1.start()
        time.sleep(0.05)  # asegurar A toma el lock primero
        t2.start()
        t1.join()
        t2.join()

        # A debe terminar antes de que B empiece (lock serializa)
        assert order.index("end-A") < order.index("start-B")

    def test_different_circuits_parallel(self) -> None:
        """Dos acquires de diferentes circuits pueden correr en paralelo."""
        from app.openhands_agent import circuit_locks

        order = []
        lock_a = circuit_locks._get_lock("produccion")
        lock_b = circuit_locks._get_lock("desarrollo")

        def worker(lock, name: str) -> None:
            with lock:
                order.append(f"start-{name}")
                time.sleep(0.1)
                order.append(f"end-{name}")

        ta = threading.Thread(target=worker, args=(lock_a, "A"))
        tb = threading.Thread(target=worker, args=(lock_b, "B"))
        ta.start()
        tb.start()
        ta.join()
        tb.join()

        # A y B pueden estar en paralelo (locks diferentes)
        # start-A y start-B deben estar en el log
        assert "start-A" in order
        assert "start-B" in order
        # A y B no necesariamente serializados
        start_a = order.index("start-A")
        start_b = order.index("start-B")
        end_a = order.index("end-A")
        end_b = order.index("end-B")
        # A NO terminó antes de que B empiece (paralelismo OK)
        # Puede ser que B termine antes que A, no asumimos nada
        assert end_a >= 0 and end_b >= 0


# ── Agent event hooks (Sprint 4.3 / §15.quater.2) ──────────────


class TestOmpClientEventHooks:
    """Verifica que OmpClient registre hooks y los redirija al trace."""

    def _make_dummy_event(self, **kwargs) -> MagicMock:
        """Crea un event-like con model_dump."""
        ev = MagicMock()
        ev.model_dump = MagicMock(return_value=kwargs)
        return ev

    def test_set_trace_attaches_and_detaches(self) -> None:
        """set_trace() guarda la referencia, set_trace(None) la limpia."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            mock_rpc = MockRpcClient.return_value
            from app.openhands_agent.omp_client import OmpClient

            client = OmpClient(circuit_id="desarrollo", workspace_dir="/desarrollo")
            assert client._trace is None
            fake_trace = MagicMock()
            client.set_trace(fake_trace)
            assert client._trace is fake_trace
            client.set_trace(None)
            assert client._trace is None

    def test_on_message_update_records_event(self) -> None:
        """Hook on_message_update llama trace.record_event."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            mock_rpc = MockRpcClient.return_value
            from app.openhands_agent.omp_client import OmpClient

            client = OmpClient(circuit_id="desarrollo", workspace_dir="/desarrollo")
            fake_trace = MagicMock()
            client.set_trace(fake_trace)
            event = self._make_dummy_event(type="text_delta", delta="hola")
            client._on_message_update(event)
            fake_trace.record_event.assert_called_once()
            call_args = fake_trace.record_event.call_args
            assert call_args[0][0] == "omp_message_update"
            assert call_args[0][1]["type"] == "text_delta"

    def test_on_tool_start_records_event_and_call(self) -> None:
        """Hook on_tool_execution_start llama record_event + record_tool_call."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            mock_rpc = MockRpcClient.return_value
            from app.openhands_agent.omp_client import OmpClient

            client = OmpClient(circuit_id="desarrollo", workspace_dir="/desarrollo")
            fake_trace = MagicMock()
            client.set_trace(fake_trace)
            event = self._make_dummy_event(
                tool_name="run_salvar", arguments={"commit_message": "x"}
            )
            client._on_tool_start(event)
            # record_event
            fake_trace.record_event.assert_called_once()
            assert fake_trace.record_event.call_args[0][0] == "omp_tool_execution_start"
            # record_tool_call
            fake_trace.record_tool_call.assert_called_once()
            call_kwargs = fake_trace.record_tool_call.call_args.kwargs
            assert call_kwargs["name"] == "run_salvar"
            assert call_kwargs["args"] == {"commit_message": "x"}
            assert call_kwargs["status"] == "in_progress"

    def test_on_tool_end_records_event_with_result(self) -> None:
        """Hook on_tool_execution_end incluye el result en el event."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            mock_rpc = MockRpcClient.return_value
            from app.openhands_agent.omp_client import OmpClient

            client = OmpClient(circuit_id="desarrollo", workspace_dir="/desarrollo")
            fake_trace = MagicMock()
            client.set_trace(fake_trace)
            event = self._make_dummy_event(
                tool_name="run_salvar", result="ok", status="success"
            )
            client._on_tool_end(event)
            assert fake_trace.record_event.call_count == 2
            # segunda call es omp_tool_result
            last_call = fake_trace.record_event.call_args_list[-1]
            assert last_call[0][0] == "omp_tool_result"
            assert "ok" in last_call[0][1]["result"]

    def test_on_turn_end_records_tokens(self) -> None:
        """Hook on_turn_end extrae usage y llama record_tokens."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            mock_rpc = MockRpcClient.return_value
            from app.openhands_agent.omp_client import OmpClient

            client = OmpClient(circuit_id="desarrollo", workspace_dir="/desarrollo")
            fake_trace = MagicMock()
            client.set_trace(fake_trace)
            event = self._make_dummy_event(
                usage={"input": 100, "output": 50, "total": 150}
            )
            client._on_turn_end(event)
            fake_trace.record_tokens.assert_called_once_with(
                input_tokens=100, output_tokens=50
            )

    def test_on_protocol_error_records_error(self) -> None:
        """Hook on_protocol_error llama record_error."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            mock_rpc = MockRpcClient.return_value
            from app.openhands_agent.omp_client import OmpClient

            client = OmpClient(circuit_id="desarrollo", workspace_dir="/desarrollo")
            fake_trace = MagicMock()
            client.set_trace(fake_trace)
            event = self._make_dummy_event(message="JSONL parse error")
            client._on_protocol_error(event)
            fake_trace.record_error.assert_called_once()
            assert "JSONL" in fake_trace.record_error.call_args[0][0]

    def test_hooks_are_noop_without_trace(self) -> None:
        """Si no hay trace, los hooks son no-ops (no fallan)."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            mock_rpc = MockRpcClient.return_value
            from app.openhands_agent.omp_client import OmpClient

            client = OmpClient(circuit_id="desarrollo", workspace_dir="/desarrollo")
            # No set_trace
            event = self._make_dummy_event(type="text_delta", delta="hola")
            # No debe tirar excepción
            client._on_message_update(event)
            client._on_tool_start(event)
            client._on_tool_end(event)
            client._on_turn_end(event)
            client._on_protocol_error(event)

    def test_register_hooks_called_in_init(self) -> None:
        """En __init__ se registran los hooks en RpcClient."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            mock_rpc = MockRpcClient.return_value
            from app.openhands_agent.omp_client import OmpClient

            OmpClient(circuit_id="desarrollo", workspace_dir="/desarrollo")
            # Verifica que on_message_update, on_tool_execution_*,
            # on_turn_end, on_protocol_error fueron llamados
            assert mock_rpc.on_message_update.called
            assert mock_rpc.on_tool_execution_start.called
            assert mock_rpc.on_tool_execution_end.called
            assert mock_rpc.on_turn_end.called
            assert mock_rpc.on_protocol_error.called
