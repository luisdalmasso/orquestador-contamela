from starlette.requests import Request

from fastapi.testclient import TestClient

from app.main import app
from app.mcp.router import get_mcp_root, get_mcp_sse


client = TestClient(app)


def test_mcp_tools_lists_catalog() -> None:
    response = client.get("/mcp/tools")
    assert response.status_code == 200
    payload = response.json()
    names = {tool["name"] for tool in payload["tools"]}
    assert "read_file" in names
    assert "search_code_literal" in names
    assert "get_rules" in names


def test_mcp_root_reports_legacy_compatibility() -> None:
    response = client.get("/mcp/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["endpoints"]["execute"] == "/mcp/execute"
    assert payload["endpoints"]["jsonrpc"] == "/mcp"


def test_mcp_execute_alias_runs_tool() -> None:
    response = client.post(
        "/mcp/execute",
        json={
            "tool_name": "get_git_status",
            "arguments": {"repo_path": "/desarrollo"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["branch"]


def _request(path: str, accept: str = "application/json") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [(b"accept", accept.encode())],
        }
    )


def test_mcp_sse_returns_event_stream() -> None:
    response = get_mcp_sse(_request("/mcp/sse", accept="text/event-stream"))
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"


def test_mcp_root_returns_event_stream_when_requested() -> None:
    response = get_mcp_root(_request("/mcp/", accept="text/event-stream"))
    assert response.media_type == "text/event-stream"


def test_mcp_jsonrpc_initialize() -> None:
    response = client.post(
        "/mcp/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["serverInfo"]["name"] == "conti-backend"


def test_mcp_jsonrpc_tools_list() -> None:
    response = client.post(
        "/mcp/",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    names = {tool["name"] for tool in payload["result"]["tools"]}
    assert "read_file" in names


def test_mcp_jsonrpc_tools_call() -> None:
    response = client.post(
        "/mcp/",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_git_status",
                "arguments": {"repo_path": "/desarrollo"},
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["isError"] is False
    assert payload["result"]["structuredContent"]["branch"]


def test_mcp_call_read_file_reads_allowed_file() -> None:
    response = client.post(
        "/mcp/call",
        json={
            "tool": "read_file",
            "arguments": {
                "path": "/contenedores/conti-backend/docs/rules.md",
                "start_line": 1,
                "end_line": 20,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "No usar SSH" in payload["result"]["content"]


def test_mcp_call_search_code_literal_finds_backend_text() -> None:
    response = client.post(
        "/mcp/call",
        json={
            "tool": "search_code_literal",
            "arguments": {
                "query": "No usar SSH",
                "path": "/contenedores/conti-backend/docs",
                "include": "*.md",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["count"] >= 1


def test_mcp_rejects_path_outside_allowlist() -> None:
    response = client.post(
        "/mcp/call",
        json={
            "tool": "read_file",
            "arguments": {
                "path": "/etc/passwd",
            },
        },
    )
    assert response.status_code == 400