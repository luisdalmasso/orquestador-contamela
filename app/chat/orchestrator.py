"""Chat orchestrator — the central brain that ties everything together.

Flow:
  1. Load state + history from Redis
  2. Classify intent (keyword strategy for católico)
  3. Build instruction for the nanobot
  4. Write context files (state.json, history.md, rule_context.md)
  5. Send message to tenant's nanobot serve
  6. Save response to Redis
  7. Return response
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.chat.memory import RedisSessionManager, get_session_manager
from app.tenants.base import TenantConfig
from app.tenants.context_writer import ContextWriter
from app.tenants.registry import TenantRegistry, get_tenant_registry

log = logging.getLogger("conti.orchestrator")


class ChatOrchestrator:
    """Orchestrates chat flow per tenant."""

    def __init__(
        self,
        memory: RedisSessionManager | None = None,
        registry: TenantRegistry | None = None,
        context_writer: ContextWriter | None = None,
    ):
        self.memory = memory or get_session_manager()
        self.registry = registry or get_tenant_registry()
        self.context_writer = context_writer or ContextWriter()

    async def process_message(
        self,
        tenant_id: str,
        session_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process an incoming chat message and return the response.

        Returns:
            {
                "response": str,           # The assistant's text response
                "intent": str | None,      # Detected intent (keyword strategy)
                "tenant_id": str,
                "session_id": str,
            }
        """
        # 1. Resolve tenant
        tenant = self.registry.get(tenant_id)
        if tenant is None:
            log.error("Unknown tenant: %s", tenant_id)
            return {
                "response": f"Error: tenant '{tenant_id}' no encontrado.",
                "intent": None,
                "tenant_id": tenant_id,
                "session_id": session_id,
            }

        # 2. Load state + history from Redis
        state = self.memory.get_state(tenant_id, session_id)
        history = self.memory.get_history(tenant_id, session_id, tenant.max_history)

        # 3. Classify intent and build instruction
        if tenant.strategy == "keyword":
            intent = self._classify_by_keywords(message, tenant.keywords)
            instruction = tenant.instructions.get(
                intent, tenant.instructions.get("general", "Responde al usuario.")
            )
        else:
            # Future: rules_engine strategy
            intent = None
            instruction = "Responde al usuario."

        log.info(
            "[%s/%s] intent=%s message=%.100s",
            tenant_id, session_id, intent, message,
        )

        # 4. Write context files for nanobot to read
        self.context_writer.write_all(
            tenant_id=tenant_id,
            state=state,
            history=history,
            instruction=instruction,
        )

        # 5. Build messages and call nanobot serve
        # Enviamos SOLO el mensaje actual porque nanobot serve (OpenAI-compatible) 
        # en esta implementación estricta solo acepta un mensaje y mantiene el historial 
        # localmente según el session_id.
        messages = [{"role": "user", "content": message}]

        response_text = await self._call_nanobot(tenant, session_id, messages)

        # 6. Save to Redis
        self.memory.append_message(
            tenant_id, session_id, "user", message, ttl=tenant.chat_ttl
        )
        self.memory.append_message(
            tenant_id, session_id, "assistant", response_text, ttl=tenant.chat_ttl
        )

        return {
            "response": response_text,
            "intent": intent,
            "tenant_id": tenant_id,
            "session_id": session_id,
        }

    def _classify_by_keywords(
        self, message: str, keywords: dict[str, list[str]]
    ) -> str:
        """Classify message intent by keyword matching.

        Returns the intent name, or 'general' if no match.
        """
        msg_lower = message.lower().strip()
        best_intent = "general"
        best_score = 0

        for intent, kw_list in keywords.items():
            score = 0
            for kw in kw_list:
                if kw.lower() in msg_lower:
                    # Longer keywords score higher (more specific)
                    score += len(kw)
            if score > best_score:
                best_score = score
                best_intent = intent

        return best_intent

    async def _call_nanobot(
        self, tenant: TenantConfig, session_id: str, messages: list[dict]
    ) -> str:
        """Send messages to the tenant's nanobot serve instance."""
        url = f"{tenant.nanobot_base_url}/v1/chat/completions"
        payload = {
            "messages": messages,
            "session_id": session_id,
            "temperature": 0.4,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=payload)

            if resp.status_code != 200:
                log.error(
                    "[%s] Nanobot serve error %d: %s",
                    tenant.tenant_id, resp.status_code, resp.text[:500],
                )
                return f"Error al comunicarse con el asistente (HTTP {resp.status_code})."

            data = resp.json()

            # Extract response text from OpenAI-compatible format
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "Sin respuesta.")
                
                # DEBUG: Log the raw content to detect embedded JSON
                log.debug("[%s] Raw nanobot response content: %s (type: %s)", 
                         tenant.tenant_id, repr(content)[:200], type(content).__name__)
                
                # Check if content is a JSON string that needs parsing
                if isinstance(content, str) and content.strip().startswith('{') and content.strip().endswith('}'):
                    try:
                        import json
                        parsed = json.loads(content)
                        # If it's a structured response with a 'response' field, use that
                        if isinstance(parsed, dict) and 'response' in parsed:
                            log.info("[%s] Extracted response from embedded JSON", tenant.tenant_id)
                            return str(parsed['response'])
                        # If it's a structured response with 'content' or 'text' fields
                        elif isinstance(parsed, dict) and 'content' in parsed:
                            log.info("[%s] Extracted content from embedded JSON", tenant.tenant_id)
                            return str(parsed['content'])
                        elif isinstance(parsed, dict) and 'text' in parsed:
                            log.info("[%s] Extracted text from embedded JSON", tenant.tenant_id)
                            return str(parsed['text'])
                        else:
                            # If we can't find a suitable field, return the whole JSON as string
                            log.warning("[%s] Could not extract response field from JSON, returning full JSON", tenant.tenant_id)
                            return json.dumps(parsed, ensure_ascii=False)
                    except json.JSONDecodeError:
                        # If it's not valid JSON, return as-is
                        log.debug("[%s] Content is not valid JSON, returning as-is", tenant.tenant_id)
                        pass
                    except Exception as exc:
                        log.warning("[%s] Error parsing embedded JSON: %s", tenant.tenant_id, exc)
                
                return content

            return "Sin respuesta del asistente."

        except httpx.TimeoutException:
            log.error("[%s] Nanobot serve timeout", tenant.tenant_id)
            return "El asistente tardó demasiado en responder. Intenta de nuevo."
        except httpx.ConnectError:
            log.error("[%s] Cannot connect to nanobot serve at %s",
                      tenant.tenant_id, tenant.nanobot_base_url)
            return "El asistente no está disponible en este momento."
        except Exception as exc:
            log.exception("[%s] Unexpected error calling nanobot: %s",
                          tenant.tenant_id, exc)
            return "Error interno del asistente."


# Singleton
_orchestrator: ChatOrchestrator | None = None


def get_orchestrator() -> ChatOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ChatOrchestrator()
    return _orchestrator
