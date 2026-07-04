"""
Tests para app.openhands_agent.tool_bridge.

Mockeamos httpx para no requerir el MCP server corriendo.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from dataclasses import dataclass, field

from app.openhands_agent.tool_bridge import (
    build_custom_tools_for_circuit,
    make_mcp_tool_handler,
)


class TestMakeMcpToolHandler:
    """Tests del factory make_mcp_tool_handler."""

    def test_handler_sends_correct_jsonrpc(self) -> None:
        """El handler arma correctamente el JSON-RPC request al MCP."""
        captured: dict = {}

        def mock_post(url, json):
            captured.update(url=url, payload=json)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "jsonrpc": "2.0",
                "id": json["id"],
                "result": {"content": [{"type": "text", "text": "committed abc123"}]},
            }
            return mock_resp

        with patch("app.openhands_agent.tool_bridge.httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post = mock_post
            handler = make_mcp_tool_handler("run_salvar", "http://mcp:9001/mcp")
            result = handler({"commit_message": "test"}, context=None)

        assert result == "committed abc123"
        assert captured["payload"]["method"] == "tools/call"
        assert captured["payload"]["params"]["name"] == "run_salvar"
        assert captured["payload"]["params"]["arguments"] == {"commit_message": "test"}
        assert captured["url"] == "http://mcp:9001/mcp"

    def test_handler_returns_error_string_on_mcp_error(self) -> None:
        """Si MCP devuelve error, el handler propaga el mensaje como string."""
        with patch("app.openhands_agent.tool_bridge.httpx.Client") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32602, "message": "branch mismatch"},
            }
            MockClient.return_value.__enter__.return_value.post = lambda *a, **kw: (
                mock_resp
            )

            handler = make_mcp_tool_handler("run_salvar", "http://mcp")
            result = handler({"commit_message": "test"}, context=None)

        assert result.startswith("ERROR (run_salvar):")
        assert "branch mismatch" in result

    def test_handler_returns_error_string_on_http_error(self) -> None:
        """Si HTTP no es 200, el handler devuelve error string."""
        with patch("app.openhands_agent.tool_bridge.httpx.Client") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"
            MockClient.return_value.__enter__.return_value.post = lambda *a, **kw: (
                mock_resp
            )

            handler = make_mcp_tool_handler("run_salvar", "http://mcp")
            result = handler({}, context=None)

        assert result.startswith("ERROR (run_salvar):")
        assert "HTTP 500" in result

    def test_handler_returns_error_string_on_timeout(self) -> None:
        """Si httpx lanza TimeoutException, el handler devuelve error."""
        import httpx

        with patch("app.openhands_agent.tool_bridge.httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post = MagicMock(
                side_effect=httpx.TimeoutException("timeout")
            )

            handler = make_mcp_tool_handler("run_salvar", "http://mcp", timeout=5.0)
            result = handler({}, context=None)

        assert result.startswith("ERROR (run_salvar):")
        assert "timeout" in result


@dataclass
class MockCfg:
    """Mock de CircuitConfig con allowed_mcp_categories."""

    id: str = "desarrollo"
    workspace_dir: str = "/desarrollo"
    allowed_mcp_categories: tuple = ()


class MockTool(dict):
    """Mock de una MCP tool. Subclass de dict para tener .get()."""

    def __init__(
        self,
        name: str,
        description: str = "",
        input_schema: dict = None,
        category: str = "",
    ):
        super().__init__(
            name=name,
            description=description,
            input_schema=input_schema or {"type": "object"},
            category=category,
        )


class MockRegistry:
    """Mock del registry_service."""

    def __init__(self, tools: list) -> None:
        self._tools = tools

    def list_tools(self) -> list:
        return self._tools


class TestBuildCustomToolsForCircuit:
    """Tests de build_custom_tools_for_circuit."""

    def test_filters_by_allowed_categories(self) -> None:
        """Solo tools del allowed_mcp_categories se incluyen."""
        with patch("omp_rpc.host_tool") as MockHostTool:
            tools = [
                MockTool("run_salvar", category="gitops"),
                MockTool("run_promover", category="gitops"),
                MockTool("odoo_get_invoice", category="odoo"),
                MockTool("catolico_lecturas", category="catolico"),
            ]
            registry = MockRegistry(tools)
            cfg = MockCfg(allowed_mcp_categories=("gitops",))

            result = build_custom_tools_for_circuit(cfg, registry, "http://mcp")

        # Solo run_salvar y run_promover (gitops).
        assert MockHostTool.call_count == 2

    def test_empty_categories_returns_empty_list(self) -> None:
        """Si allowed_mcp_categories está vacío, retorna []."""
        cfg = MockCfg(allowed_mcp_categories=())
        registry = MockRegistry(
            [
                MockTool("run_salvar", category="gitops"),
                MockTool("odoo_get_invoice", category="odoo"),
            ]
        )
        result = build_custom_tools_for_circuit(cfg, registry, "http://mcp")
        assert result == []

    def test_no_tools_match_returns_empty_list(self) -> None:
        """Si ninguna tool matchea la categoría, retorna []."""
        with patch("omp_rpc.host_tool") as MockHostTool:
            tools = [MockTool("odoo_get_invoice", category="odoo")]
            registry = MockRegistry(tools)
            cfg = MockCfg(allowed_mcp_categories=("gitops",))

            result = build_custom_tools_for_circuit(cfg, registry, "http://mcp")

        assert result == []
        assert MockHostTool.call_count == 0

    def test_handler_is_callable_with_correct_args(self) -> None:
        """El handler generado tiene closure sobre tool_name y mcp_url correctos."""
        with patch("omp_rpc.host_tool") as MockHostTool:
            tools = [
                MockTool("run_salvar", category="gitops", description="commit helper")
            ]
            registry = MockRegistry(tools)
            cfg = MockCfg(allowed_mcp_categories=("gitops",))

            build_custom_tools_for_circuit(cfg, registry, "http://custom-mcp")

        # Verificar que mock_omp_rpc.host_tool fue llamado con los args correctos.
        assert MockHostTool.call_count == 1
        call_kwargs = MockHostTool.call_args.kwargs
        assert call_kwargs["name"] == "run_salvar"
        assert call_kwargs["description"] == "commit helper"
        assert call_kwargs["parameters"] == {"type": "object"}
        assert callable(call_kwargs["execute"])
