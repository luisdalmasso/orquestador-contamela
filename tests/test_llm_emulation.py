import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.llm_emulation.nanobot_serve_bridge import LLMBridge, NanobotServeError
from app.services.nanobot_serve_service import NanobotServeService


client = TestClient(app)


def test_v1_root_reports_legacy_compatibility() -> None:
    response = client.get("/v1")
    assert response.status_code == 200
    payload = response.json()
    assert "openai-base-url" in payload["compatible_with"]
    assert payload["endpoints"]["models"] == "/v1/models"


def test_models_endpoint_proxies_nanobot_serve(monkeypatch) -> None:
    monkeypatch.setattr(NanobotServeService, "_bridge", lambda self: _StubBridge())

    response = client.get("/v1/models")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["id"] == "conti-default"


def test_chat_completions_proxies_payload(monkeypatch) -> None:
    monkeypatch.setattr(NanobotServeService, "_bridge", lambda self: _StubBridge())

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "conti-default",
            "messages": [{"role": "user", "content": "hola"}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "conti-default"
    assert payload["choices"][0]["message"]["content"] == "respuesta stub"


def test_responses_endpoint_adapts_chat_completion(monkeypatch) -> None:
    monkeypatch.setattr(NanobotServeService, "_bridge", lambda self: _StubBridge())

    response = client.post(
        "/v1/responses",
        json={
            "model": "conti-default",
            "input": "hola mundo",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "response"
    assert payload["output_text"] == "respuesta stub"


def test_streaming_chat_completions_passthrough(monkeypatch) -> None:
    monkeypatch.setattr(NanobotServeService, "_bridge", lambda self: _StubBridge())

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "conti-default",
            "messages": [{"role": "user", "content": "hola"}],
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
        assert "conti-default" in body


def test_streaming_chat_completions_returns_sse_error_instead_of_500(monkeypatch) -> None:
    monkeypatch.setattr(NanobotServeService, "_bridge", lambda self: _StreamingErrorBridge())

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "conti-default",
            "messages": [
                {"role": "system", "content": "reglas"},
                {"role": "user", "content": "hola"},
            ],
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
        assert "invalid_request_error" in body
        assert "Only a single user message is supported" in body
        assert "[DONE]" in body


def test_chat_payload_passes_through_untouched(monkeypatch) -> None:
    captured = {}

    class _CaptureBridge(_StubBridge):
        def chat_completion(self, payload):
            captured["payload"] = payload
            return super().chat_completion(payload)

    monkeypatch.setattr(NanobotServeService, "_bridge", lambda self: _CaptureBridge())

    client.post(
        "/v1/chat/completions",
        json={
            "model": "kilo-auto/free",
            "messages": [
                {"role": "system", "content": "reglas"},
                {"role": "user", "content": "hola"},
            ],
            "tools": [{"type": "function", "function": {"name": "bash", "description": "run bash"}}],
        },
    )

    msgs = captured["payload"]["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "tools" in captured["payload"]


def test_llm_backend_status_reports_reachability(monkeypatch) -> None:
    monkeypatch.setattr(NanobotServeService, "_bridge", lambda self: _StubBridge())
    import app.llm_emulation.nanobot_serve_bridge as _nb
    monkeypatch.setattr(_nb, "_read_nanobot_provider", lambda: ("https://api.kilo.ai", "test-key"))

    response = client.get("/llm/backend/status")
    assert response.status_code == 200
    payload = response.json()["backend"]
    assert payload["reachable"] is True
    assert payload["models"][0]["id"] == "conti-default"


class _StubBridge:
    def get_models(self):
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"id": "conti-default", "object": "model", "owned_by": "nanobot"}],
            },
            headers={"content-type": "application/json"},
        )

    def get_health(self):
        return httpx.Response(200, json={"status": "ok"}, headers={"content-type": "application/json"})

    def chat_completion(self, payload):
        model = payload.get("model", "conti-default")
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-stub",
                "object": "chat.completion",
                "created": 0,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "respuesta stub"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
            headers={"content-type": "application/json"},
        )

    def stream_chat_completion(self, payload):
        yield b"data: {\"id\":\"chatcmpl-stub\",\"object\":\"chat.completion.chunk\",\"model\":\"conti-default\",\"choices\":[{\"delta\":{\"content\":\"hola\"}}]}\n\n"
        yield b"data: [DONE]\n\n"


class _StreamingErrorBridge:
    def stream_chat_completion(self, payload):
        if False:
            yield b""
        raise NanobotServeError(400, {"error": {"message": "Only a single user message is supported"}})