from __future__ import annotations

from app.services.nanobot_serve_service import nanobot_serve_service


class LLMService:
    def get_models(self):
        return nanobot_serve_service.list_models()

    def chat_completions(self, payload: dict):
        return nanobot_serve_service.chat_completions(payload)

    def stream_chat_completions(self, payload: dict):
        return nanobot_serve_service.stream_chat_completions(payload)

    def responses(self, payload: dict):
        return nanobot_serve_service.responses(payload)


llm_service = LLMService()
