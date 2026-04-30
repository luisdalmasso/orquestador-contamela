from __future__ import annotations

import time
import uuid
from typing import Any


def normalize_chat_payload(payload: dict[str, Any], default_model: str | None = None) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["messages"] = _normalize_messages(payload.get("messages"))
    if not normalized.get("model") and default_model:
        normalized["model"] = default_model
    normalized.pop("metadata", None)
    normalized.pop("tools", None)
    return normalized


def responses_to_chat_payload(payload: dict[str, Any], default_model: str) -> dict[str, Any]:
    model = payload.get("model") or default_model or "conti-default"
    stream = bool(payload.get("stream", False))
    user_input = payload.get("input", "")
    messages = _input_to_messages(user_input)
    return {
        "model": model,
        "messages": messages,
        "stream": stream,
    }


def chat_to_responses_payload(chat_response: dict[str, Any], model: str) -> dict[str, Any]:
    choices = chat_response.get("choices", [])
    message = choices[0].get("message", {}) if choices else {}
    text = message.get("content", "")
    usage = chat_response.get("usage", {})
    return {
        "id": f"resp_{uuid.uuid4().hex[:12]}",
        "object": "response",
        "created": int(time.time()),
        "model": model or "conti-default",
        "status": "completed",
        "output": [
            {
                "id": f"msg_{uuid.uuid4().hex[:12]}",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                        "annotations": [],
                    }
                ],
            }
        ],
        "output_text": text,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }


def _input_to_messages(user_input: Any) -> list[dict[str, Any]]:
    if isinstance(user_input, str):
        return [{"role": "user", "content": user_input}]
    if isinstance(user_input, list):
        messages: list[dict[str, Any]] = []
        for item in user_input:
            if isinstance(item, dict) and "role" in item and "content" in item:
                messages.append({"role": item["role"], "content": item["content"]})
                continue
            if isinstance(item, dict) and item.get("type") == "message":
                role = item.get("role", "user")
                content_parts = item.get("content", [])
                if isinstance(content_parts, list):
                    text = " ".join(
                        part.get("text", "") for part in content_parts if isinstance(part, dict)
                    ).strip()
                    messages.append({"role": role, "content": text})
        if messages:
            return messages
    raise ValueError("Formato de input no soportado para /v1/responses")


def _normalize_messages(messages: Any) -> list[dict[str, Any]]:
    """Extrae solo el último mensaje user para nanobot serve (solo acepta 1 user message)."""
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages debe contener al menos un mensaje")

    # Buscar el último mensaje con role "user"
    last_user: dict[str, Any] | None = None
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            last_user = message
            break

    if last_user is None:
        raise ValueError("messages no contiene ningún mensaje user")

    content = last_user.get("content")
    if not content:
        raise ValueError("El mensaje user no tiene contenido")

    # Normalizar content si es lista (multimodal) a texto plano
    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        content = "\n\n".join(p for p in text_parts if p).strip()
        if not content:
            raise ValueError("El mensaje user no tiene contenido de texto")

    return [{"role": "user", "content": content}]
