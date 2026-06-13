from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config.loader import load_config, reload_config
from app.llm_emulation.adapters import (
    chat_to_responses_payload,
    responses_to_chat_payload,
)
from app.llm_emulation.nanobot_serve_bridge import LLMBridge, _read_nanobot_provider

log = logging.getLogger("conti.llm_service")


class NanobotServeService:
    def _bridge(self) -> LLMBridge:
        return LLMBridge(timeout=600.0)

    def _response_ok(self, response: Any) -> bool:
        is_success = getattr(response, "is_success", None)
        if isinstance(is_success, bool):
            return is_success
        status_code = int(getattr(response, "status_code", 0) or 0)
        return 200 <= status_code < 300

    def backend_status(self) -> dict[str, Any]:
        api_base, api_key = _read_nanobot_provider()
        payload: dict[str, Any] = {
            "mode": "direct_llm_proxy",
            "api_base": api_base,
            "configured": bool(api_base),
            "reachable": False,
            "models": [],
        }
        if not api_base:
            return payload
        try:
            models = self._bridge().get_models()
            payload["reachable"] = self._response_ok(models)
            if payload["reachable"]:
                payload["models"] = models.json().get("data", [])
            return payload
        except Exception as exc:
            payload["error"] = str(exc)
            return payload

    def reload_backend(self) -> dict[str, Any]:
        reload_config()
        return self.backend_status()

    def list_models(self) -> dict[str, Any]:
        response = self._bridge().get_models()
        self._raise_for_error(response)
        return response.json()

    def _normalize_chat_response(self, payload: dict[str, Any], requested_model: str | None = None) -> dict[str, Any]:
        normalized = dict(payload)
        if requested_model:
            normalized["model"] = requested_model

        choices = normalized.get("choices")
        if not isinstance(choices, list):
            return normalized

        cleaned_choices: list[dict[str, Any]] = []
        for choice in choices:
            if not isinstance(choice, dict):
                cleaned_choices.append(choice)
                continue
            cleaned_choice = dict(choice)
            message = cleaned_choice.get("message")
            if isinstance(message, dict):
                cleaned_message = dict(message)
                cleaned_message.pop("reasoning", None)
                cleaned_message.pop("reasoning_details", None)
                cleaned_choice["message"] = cleaned_message
            cleaned_choice.pop("reasoning", None)
            cleaned_choice.pop("reasoning_details", None)
            cleaned_choices.append(cleaned_choice)
        normalized["choices"] = cleaned_choices
        return normalized

    def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        log.debug("[SERVICE] chat_completions payload=%.300s", json.dumps(payload, ensure_ascii=False))
        response = self._bridge().chat_completion(payload)
        self._raise_for_error(response)
        return self._normalize_chat_response(response.json(), requested_model=payload.get("model"))

    def stream_chat_completions(self, payload: dict[str, Any]):
        log.debug("[SERVICE][stream] stream_chat_completions payload=%.300s", json.dumps(payload, ensure_ascii=False))
        return self._bridge().stream_chat_completion(payload)

    def responses(self, payload: dict[str, Any]) -> dict[str, Any]:
        config = load_config()
        chat_payload = responses_to_chat_payload(payload, default_model=config.llm_emulation.default_model)
        chat_response = self.chat_completions(chat_payload)
        model = chat_response.get("model") or chat_payload["model"]
        return chat_to_responses_payload(chat_response, model=model)

    def _raise_for_error(self, response: httpx.Response) -> None:
        if self._response_ok(response):
            return
        detail = response.text
        try:
            detail = response.json()
        except Exception:
            pass
        raise ValueError(detail)


nanobot_serve_service = NanobotServeService()
