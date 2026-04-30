from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("conti.llm_bridge")

NANOBOT_CONFIG_PATH = "/home/nanobot/.nanobot/config.json"


class NanobotServeError(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


def _read_nanobot_provider() -> tuple[str, str]:
    """Lee la config de nanobot y devuelve (api_base, api_key) del provider activo."""
    try:
        raw = Path(NANOBOT_CONFIG_PATH).read_text(encoding="utf-8")
        cfg = json.loads(raw)
        agents_defaults = cfg.get("agents", {}).get("defaults", {})
        provider_name = agents_defaults.get("provider", "openai")
        provider_cfg = cfg.get("providers", {}).get(provider_name, {})
        api_base = provider_cfg.get("apiBase", "").rstrip("/")
        api_key = provider_cfg.get("apiKey", "")
        log.debug("[BRIDGE] provider=%s api_base=%s", provider_name, api_base)
        return api_base, api_key
    except Exception as exc:
        log.warning("[BRIDGE] no se pudo leer config de nanobot: %s", exc)
        return "", ""


class LLMBridge:
    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout

    def _headers(self, api_key: str) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if api_key:
            h["Authorization"] = f"Bearer {api_key}"
        return h

    def _make_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout)

    def get_models(self) -> httpx.Response:
        api_base, api_key = _read_nanobot_provider()
        with self._make_client() as client:
            return client.get(f"{api_base}/v1/models", headers=self._headers(api_key))

    def chat_completion(self, payload: dict[str, Any]) -> httpx.Response:
        api_base, api_key = _read_nanobot_provider()
        log.debug(
            "[BRIDGE→LLM] POST %s/v1/chat/completions payload=%.500s",
            api_base,
            json.dumps(payload, ensure_ascii=False),
        )
        with self._make_client() as client:
            response = client.post(
                f"{api_base}/v1/chat/completions",
                json=payload,
                headers=self._headers(api_key),
            )
        log.debug("[BRIDGE←LLM] status=%s body=%.500s", response.status_code, response.text)
        return response

    def stream_chat_completion(self, payload: dict[str, Any]) -> Iterator[bytes]:
        api_base, api_key = _read_nanobot_provider()
        log.debug(
            "[BRIDGE→LLM][stream] POST %s/v1/chat/completions payload=%.500s",
            api_base,
            json.dumps(payload, ensure_ascii=False),
        )
        with self._make_client() as client:
            with client.stream(
                "POST",
                f"{api_base}/v1/chat/completions",
                json=payload,
                headers=self._headers(api_key),
            ) as response:
                log.debug("[BRIDGE←LLM][stream] status=%s", response.status_code)
                if not response.is_success:
                    detail: Any = response.text
                    try:
                        detail = response.json()
                    except Exception:
                        pass
                    log.warning("[BRIDGE←LLM][stream] error %s: %s", response.status_code, detail)
                    raise NanobotServeError(response.status_code, detail)
                for chunk in response.iter_bytes():
                    yield chunk


# Alias de compatibilidad para tests existentes
NanobotServeBridge = LLMBridge
