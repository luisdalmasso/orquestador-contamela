from __future__ import annotations

import asyncio
import io
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from gtts import gTTS

try:
    import edge_tts
except Exception:  # pragma: no cover - dependencia opcional en runtime
    edge_tts = None


HERMES_ROOT = Path(__file__).resolve().parents[1] / "hermes_profiles" / "contihome"
GLOBAL_CONFIG_PATH = HERMES_ROOT / "config.yaml"
PROFILES_ROOT = HERMES_ROOT / "profiles"

DEFAULT_PROVIDER = "edge"
DEFAULT_VOICE = "es-AR-TomasNeural"
DEFAULT_LANGUAGE = "es"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class TTSService:
    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    @lru_cache(maxsize=32)
    def _profile_config(self, tenant_id: str) -> dict[str, Any]:
        global_config = self._load_yaml(GLOBAL_CONFIG_PATH)
        profile_config = self._load_yaml(PROFILES_ROOT / tenant_id / "config.yaml")
        return _deep_merge(global_config, profile_config)

    def _resolve_tts_config(self, tenant_id: str) -> dict[str, Any]:
        config = self._profile_config(tenant_id or "odoo")
        tts = config.get("tts") or {}
        stt = config.get("stt") or {}
        provider = tts.get("provider") or DEFAULT_PROVIDER
        edge = tts.get("edge") or {}
        language = ((stt.get("local") or {}).get("language") or DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE
        return {
            "provider": provider,
            "voice": edge.get("voice") or DEFAULT_VOICE,
            "language": language,
        }

    async def synthesize(self, text: str, tenant_id: str = "odoo") -> tuple[bytes, str]:
        clean_text = str(text or "").strip()
        if not clean_text:
            raise ValueError("El texto está vacío")
        cfg = self._resolve_tts_config(tenant_id)
        provider = cfg["provider"]
        if provider == "edge" and edge_tts is not None:
            return await self._synthesize_edge(clean_text, cfg["voice"]), "audio/mpeg"
        return self._synthesize_gtts(clean_text, cfg["language"]), "audio/mpeg"

    async def _synthesize_edge(self, text: str, voice: str) -> bytes:
        communicator = edge_tts.Communicate(text=text, voice=voice)
        chunks: list[bytes] = []
        async for chunk in communicator.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                chunks.append(chunk["data"])
        if not chunks:
            raise RuntimeError("edge-tts no devolvió audio")
        return b"".join(chunks)

    def _synthesize_gtts(self, text: str, language: str) -> bytes:
        buffer = io.BytesIO()
        gTTS(text=text, lang=language or DEFAULT_LANGUAGE).write_to_fp(buffer)
        return buffer.getvalue()


_tts_service: TTSService | None = None


def get_tts_service() -> TTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service