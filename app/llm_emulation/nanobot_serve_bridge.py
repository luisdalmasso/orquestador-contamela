from __future__ import annotations

import json
import logging
import re
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


def _read_serve_url() -> tuple[str, str]:
    """Devuelve (api_base, api_key) según app_config.json.
    Si mode=nanobot_serve usa serve_base_url local; si no, cae al gateway externo.
    """
    try:
        from app.config.loader import load_config
        cfg = load_config()
        mode = cfg.llm_emulation.mode
        if mode == "nanobot_serve":
            base = cfg.llm_emulation.serve_base_url.rstrip("/")
            log.debug("[BRIDGE] mode=nanobot_serve → base=%s", base)
            return base, ""
    except Exception as exc:
        log.warning("[BRIDGE] no se pudo leer app_config, usando gateway externo: %s", exc)
    return _read_nanobot_provider()


class LLMBridge:
    def __init__(self, timeout: float = 600.0) -> None:
        self.timeout = timeout

    def _response_ok(self, response: httpx.Response) -> bool:
        is_success = getattr(response, "is_success", None)
        if isinstance(is_success, bool):
            return is_success
        return 200 <= int(getattr(response, "status_code", 0) or 0) < 300

    def _sanitize_log_text(self, value: str, limit: int = 500) -> str:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value or "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:limit]

    def _headers(self, api_key: str) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if api_key:
            h["Authorization"] = f"Bearer {api_key}"
        return h

    def _make_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout)

    def get_models(self) -> httpx.Response:
        api_base, api_key = _read_serve_url()
        with self._make_client() as client:
            return client.get(f"{api_base}/v1/models", headers=self._headers(api_key))

    def chat_completion(self, payload: dict[str, Any]) -> httpx.Response:
        api_base, api_key = _read_serve_url()
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
        log.debug(
            "[BRIDGE←LLM] status=%s body=%s",
            response.status_code,
            self._sanitize_log_text(getattr(response, "text", "")),
        )
        return response

    def stream_chat_completion(self, payload: dict[str, Any]) -> Iterator[bytes]:
        api_base, api_key = _read_serve_url()
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
                if not self._response_ok(response):
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
