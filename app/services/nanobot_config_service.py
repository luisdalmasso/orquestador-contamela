from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GATEWAY_CONFIG_PATH = Path("/home/nanobot/.nanobot/config.json")
LEGACY_GATEWAY_CONFIG_PATH = Path("/home/nanobot/config.json")
LLM_SERVE_CONFIG_PATH = Path("/home/nanobot/llm_serve_config.json")
LEGACY_SERVE_CONFIG_PATH = Path("/home/nanobot/.nanobot/nanobot/config.json")


@dataclass(frozen=True)
class NanobotEditableConfig:
    model: str
    provider: str
    temperature: float
    max_tool_iterations: int
    max_tokens: int
    context_window_tokens: int
    api_base: str
    api_key: str
    telegram_token: str = ""
    allow_from: list[str] | None = None


class NanobotConfigService:
    def get_gateway_config(self) -> dict[str, Any]:
        payload = self._load_json(GATEWAY_CONFIG_PATH, fallback=LEGACY_GATEWAY_CONFIG_PATH)
        return self._build_payload("gateway", GATEWAY_CONFIG_PATH, payload, include_telegram=True)

    def get_llm_config(self) -> dict[str, Any]:
        payload = self._load_json(LLM_SERVE_CONFIG_PATH, fallback=LEGACY_SERVE_CONFIG_PATH)
        return self._build_payload("llm", self._resolve_llm_path(), payload, include_telegram=False)

    def save_gateway_config(self, form_data: dict[str, str]) -> dict[str, Any]:
        config = self._load_json(GATEWAY_CONFIG_PATH, fallback=LEGACY_GATEWAY_CONFIG_PATH)
        updated = self._apply_form(config, form_data, include_telegram=True)
        self._write_json(GATEWAY_CONFIG_PATH, updated)
        return self.get_gateway_config()

    def save_llm_config(self, form_data: dict[str, str]) -> dict[str, Any]:
        config_path = self._resolve_llm_path(create_if_missing=True)
        config = self._load_json(config_path, fallback=LEGACY_SERVE_CONFIG_PATH)
        updated = self._apply_form(config, form_data, include_telegram=False)
        self._write_json(config_path, updated)
        return self.get_llm_config()

    def ensure_llm_config(self) -> Path:
        return self._resolve_llm_path(create_if_missing=True)

    def _resolve_llm_path(self, create_if_missing: bool = False) -> Path:
        if LLM_SERVE_CONFIG_PATH.exists():
            return LLM_SERVE_CONFIG_PATH

        if create_if_missing:
            seed = self._load_json(LEGACY_SERVE_CONFIG_PATH, fallback=GATEWAY_CONFIG_PATH)
            self._write_json(LLM_SERVE_CONFIG_PATH, seed)
            return LLM_SERVE_CONFIG_PATH

        if LEGACY_SERVE_CONFIG_PATH.exists():
            return LLM_SERVE_CONFIG_PATH

        return LLM_SERVE_CONFIG_PATH

    def _build_payload(
        self,
        target: str,
        path: Path,
        config: dict[str, Any],
        *,
        include_telegram: bool,
    ) -> dict[str, Any]:
        providers = config.get("providers", {})
        defaults = config.get("agents", {}).get("defaults", {})
        provider_name = defaults.get("provider", "")
        provider_config = providers.get(provider_name, {}) if isinstance(providers, dict) else {}
        telegram = config.get("channels", {}).get("telegram", {}) if include_telegram else {}
        allow_from = telegram.get("allowFrom", []) if include_telegram else []

        editable = NanobotEditableConfig(
            model=self._normalize_model_name(
                str(provider_name),
                str(defaults.get("model", "")),
            ),
            provider=str(provider_name),
            temperature=float(defaults.get("temperature", 0.2) or 0.2),
            max_tool_iterations=int(defaults.get("maxToolIterations", 10) or 10),
            max_tokens=int(defaults.get("maxTokens", 8192) or 8192),
            context_window_tokens=int(defaults.get("contextWindowTokens", 65536) or 65536),
            api_base=str(provider_config.get("apiBase", "")),
            api_key=str(provider_config.get("apiKey", "")),
            telegram_token=str(telegram.get("token", "")) if include_telegram else "",
            allow_from=allow_from if isinstance(allow_from, list) else [],
        )

        return {
            "target": target,
            "path": str(path),
            "exists": path.exists(),
            "provider_options": sorted(providers.keys()),
            "editable": {
                "model": editable.model,
                "provider": editable.provider,
                "temperature": editable.temperature,
                "maxToolIterations": editable.max_tool_iterations,
                "maxTokens": editable.max_tokens,
                "contextWindowTokens": editable.context_window_tokens,
                "api_base": editable.api_base,
                "api_key": editable.api_key,
                "telegram_token": editable.telegram_token,
                "allowFrom": editable.allow_from or [],
                "allowFromText": ", ".join(editable.allow_from or []),
            },
        }

    def _apply_form(
        self,
        base_config: dict[str, Any],
        form_data: dict[str, str],
        *,
        include_telegram: bool,
    ) -> dict[str, Any]:
        config = deepcopy(base_config)
        config.setdefault("agents", {}).setdefault("defaults", {})
        config.setdefault("providers", {})
        defaults = config["agents"]["defaults"]

        provider_name = form_data["provider"].strip()
        config["providers"].setdefault(provider_name, {})

        defaults["model"] = self._normalize_model_name(provider_name, form_data["model"].strip())
        defaults["provider"] = provider_name
        defaults["temperature"] = float(form_data["temperature"])
        defaults["maxToolIterations"] = int(form_data["maxToolIterations"])
        defaults["maxTokens"] = int(form_data["maxTokens"])
        defaults["contextWindowTokens"] = int(form_data["contextWindowTokens"])

        config["providers"][provider_name]["apiBase"] = form_data["api_base"].strip()
        config["providers"][provider_name]["apiKey"] = form_data["api_key"].strip()

        if include_telegram:
            config.setdefault("channels", {}).setdefault("telegram", {})
            config["channels"]["telegram"]["token"] = form_data.get("telegram_token", "").strip()
            allow_from_raw = form_data.get("allowFrom", "")
            allow_from = [item.strip() for item in allow_from_raw.replace("\n", ",").split(",") if item.strip()]
            config["channels"]["telegram"]["allowFrom"] = allow_from

        return config

    def _normalize_model_name(self, provider_name: str, model_name: str) -> str:
        normalized_provider = provider_name.strip().lower()
        normalized_model = model_name.strip()
        if normalized_provider == "openai" and normalized_model.startswith("openai/"):
            return normalized_model.removeprefix("openai/")
        return normalized_model

    def _load_json(self, primary_path: Path, fallback: Path | None) -> dict[str, Any]:
        if primary_path.exists():
            return json.loads(primary_path.read_text(encoding="utf-8"))
        if fallback and fallback.exists():
            return json.loads(fallback.read_text(encoding="utf-8"))
        return {}

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


nanobot_config_service = NanobotConfigService()
