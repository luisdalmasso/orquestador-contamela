"""
Tests para app.openhands_agent.omp_client.

Mockeamos omp_rpc.RpcClient para no requerir conti-omp corriendo.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.openhands_agent.omp_client import OmpClient, is_omp_enabled


class TestOmpClientInit:
    """Tests del __init__ de OmpClient."""

    def test_creates_rpc_client_with_socat_command(self) -> None:
        """Verifica que el RpcClient se construye con `socat` como command."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            OmpClient(
                circuit_id="desarrollo",
                workspace_dir="/desarrollo",
                omp_host="conti-omp",
                omp_port=7891,
                append_system_prompt="Ponytail rules here",
            )

            call_kwargs = MockRpcClient.call_args.kwargs
            assert call_kwargs["command"] == [
                "socat",
                "-",
                "TCP:conti-omp:7891",
            ]
            assert call_kwargs["cwd"] == "/desarrollo"
            assert call_kwargs["no_session"] is False
            assert call_kwargs["append_system_prompt"] == "Ponytail rules here"

    def test_uses_env_vars(self) -> None:
        """OMP_HOST y OMP_PORT env vars sobrescriben defaults via make_omp_client_for_circuit."""
        from app.openhands_agent.omp_client import make_omp_client_for_circuit
        from dataclasses import dataclass

        @dataclass
        class MockCfg:
            id: str = "libre"
            workspace_dir: str = "/tmp/free-agent"

        env = {"OMP_HOST": "custom-omp", "OMP_PORT": "8888"}
        with patch.dict(os.environ, env, clear=False):
            with patch("omp_rpc.RpcClient") as MockRpcClient:
                make_omp_client_for_circuit(MockCfg(), append_system_prompt="sys")

                call_kwargs = MockRpcClient.call_args.kwargs
                assert call_kwargs["command"][-1] == "TCP:custom-omp:8888"
                assert call_kwargs["append_system_prompt"] == "sys"

    def test_raises_when_omp_rpc_unavailable(self) -> None:
        """Si omp_rpc no está instalado, RuntimeError al instanciar."""
        with patch("app.openhands_agent.omp_client.OMP_RPC_AVAILABLE", False):
            from app.openhands_agent.omp_client import OmpClient

            with pytest.raises(RuntimeError, match="omp_rpc no instalado"):
                OmpClient(
                    circuit_id="desarrollo",
                    workspace_dir="/desarrollo",
                )


class TestOmpClientPrompt:
    """Tests del método prompt_and_wait."""

    def test_calls_rpc_with_user_only(self) -> None:
        """Pasa solo user_prompt (system_prompt va al constructor)."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            mock_turn = MagicMock()
            mock_turn.require_assistant_text.return_value = "Response from omp"
            MockRpcClient.return_value.prompt_and_wait.return_value = mock_turn

            client = OmpClient(
                circuit_id="desarrollo",
                workspace_dir="/desarrollo",
                append_system_prompt="system prompt text",
            )
            result = client.prompt_and_wait(user_prompt="user prompt text")

            assert result == "Response from omp"
            # prompt_and_wait recibe solo user_prompt, sin kwargs.
            args = MockRpcClient.return_value.prompt_and_wait.call_args.args
            assert args[0] == "user prompt text"
            call_kwargs = MockRpcClient.return_value.prompt_and_wait.call_args.kwargs
            assert "append_system_prompt" not in call_kwargs

    def test_system_prompt_per_call_is_ignored(self) -> None:
        """system_prompt en prompt_and_wait() genera warning (no soportado)."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            mock_turn = MagicMock()
            mock_turn.require_assistant_text.return_value = "OK"
            MockRpcClient.return_value.prompt_and_wait.return_value = mock_turn

            client = OmpClient(
                circuit_id="libre",
                workspace_dir="/tmp",
                append_system_prompt="constructor system prompt",
            )
            # system_prompt per-call es ignorado (warning logged).
            client.prompt_and_wait("hello", system_prompt="per-call system prompt")

            # Pero el call a omp SÍ ocurre con solo el user_prompt.
            args = MockRpcClient.return_value.prompt_and_wait.call_args.args
            assert args[0] == "hello"


class TestOmpClientLifecycle:
    """Tests de close() y context manager."""

    def test_close_calls_rpc_stop(self) -> None:
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            client = OmpClient(circuit_id="desarrollo", workspace_dir="/desarrollo")
            client.close()
            MockRpcClient.return_value.stop.assert_called_once()

    def test_context_manager(self) -> None:
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            with OmpClient(circuit_id="libre", workspace_dir="/tmp") as client:
                assert client is not None
            MockRpcClient.return_value.stop.assert_called_once()

    def test_init_calls_start(self) -> None:
        """__init__ debe llamar start() para spawn del subprocess."""
        with patch("omp_rpc.RpcClient") as MockRpcClient:
            OmpClient(circuit_id="desarrollo", workspace_dir="/desarrollo")
            MockRpcClient.return_value.start.assert_called_once()


class TestIsOmpEnabled:
    """Tests del feature flag CONTI_USE_OMP_AGENT."""

    def test_default_off(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            from app.openhands_agent.omp_client import is_omp_enabled

            assert is_omp_enabled() is False

    def test_explicit_true(self) -> None:
        with patch.dict(os.environ, {"CONTI_USE_OMP_AGENT": "true"}):
            from app.openhands_agent.omp_client import is_omp_enabled

            assert is_omp_enabled() is True

    def test_explicit_1(self) -> None:
        with patch.dict(os.environ, {"CONTI_USE_OMP_AGENT": "1"}):
            from app.openhands_agent.omp_client import is_omp_enabled

            assert is_omp_enabled() is True

    def test_explicit_false(self) -> None:
        with patch.dict(os.environ, {"CONTI_USE_OMP_AGENT": "false"}):
            from app.openhands_agent.omp_client import is_omp_enabled

            assert is_omp_enabled() is False

    def test_yes_value(self) -> None:
        with patch.dict(os.environ, {"CONTI_USE_OMP_AGENT": "yes"}):
            from app.openhands_agent.omp_client import is_omp_enabled

            assert is_omp_enabled() is True


class TestServiceSplitPrompt:
    """Tests del helper _split_prompt que separa system vs user parts."""

    def test_split_prompt_with_marker(self) -> None:
        from app.openhands_agent.service import OpenHandsService

        svc = OpenHandsService()
        prompt = """# Ponytail rules

bla bla

---

# Circuit: desarrollo

circuit description

---

# Code Context

code

---

# User Task
esto es el user task
"""
        system, user = svc._split_prompt(prompt)
        assert "esto es el user task" in user
        assert "esto es el user task" not in system
        assert "# User Task" in system
        assert "# Circuit: desarrollo" in system
        assert "# Code Context" in system

    def test_split_prompt_without_marker(self) -> None:
        from app.openhands_agent.service import OpenHandsService

        svc = OpenHandsService()
        prompt = "no marker here, just text"
        system, user = svc._split_prompt(prompt)
        assert system == ""
        assert user == prompt

    def test_split_prompt_with_multiple_markers(self) -> None:
        """Usa el ÚLTIMO marker (no el primero)."""
        from app.openhands_agent.service import OpenHandsService

        svc = OpenHandsService()
        prompt = (
            "# User Task\n"
            "primer user task\n"
            "---\n"
            "# User Task\n"
            "segundo user task (este es el relevante)\n"
        )
        system, user = svc._split_prompt(prompt)
        assert "segundo user task" in user
        assert "primer user task" in system
