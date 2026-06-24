"""Chat orchestrator — the central brain that ties everything together.

Flow:
  1. Act as a transparent proxy.
  2. Resolve tenant to find the correct nanobot port.
  3. Forward user message to nanobot serve keeping the session_id.
  4. Return response to n8n/Chainlit.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.tenants.base import TenantConfig
from app.tenants.registry import TenantRegistry, get_tenant_registry

log = logging.getLogger("conti.orchestrator")


class ChatOrchestrator:
    """Transparent proxy for tenant chat flow."""

    def __init__(
        self,
        registry: TenantRegistry | None = None,
    ):
        self.registry = registry or get_tenant_registry()

    async def process_message(
        self,
        tenant_id: str,
        session_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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

        log.info("[%s/%s] Proxying message=%.100s", tenant_id, session_id, message)

        # 2. Transparent proxy: Solo mandamos el mensaje del usuario. 
        # Nanobot ya tiene sus reglas en SOUL.md y su historial en sessions/
        user_content = message
        if metadata:
            mesaid = metadata.get("mesaid") or metadata.get("id_mesa")
            if mesaid:
                metadata["mesaid"] = mesaid
                metadata["id_mesa"] = mesaid
                user_content = f"[Contexto del sistema: Esta sesión corresponde a la Mesa ID: {mesaid}. Recuerda aislar todas las operaciones para esta mesa y tenant.]\n{message}"
            
        messages = [
            {"role": "user", "content": user_content}
        ]

        response_text = await self._call_nanobot(tenant, session_id, messages, metadata)

        return {
            "response": response_text,
            "intent": None,
            "tenant_id": tenant_id,
            "session_id": session_id,
        }

    async def _call_nanobot(
        self, tenant: TenantConfig, session_id: str, messages: list[dict], metadata: dict[str, Any] | None = None
    ) -> str:
        """Send messages to the tenant's nanobot serve instance."""
        base_url = tenant.nanobot_base_url.rstrip('/')
        
        # Leer el modelo directo del archivo físico de configuración del nanobot
        model_id = "default"
        try:
            config_path = Path(f"/tenants/{tenant.tenant_id}/.nanobot/config.json")
            if config_path.exists():
                disk_cfg = json.loads(config_path.read_text(encoding="utf-8"))
                model_id = disk_cfg.get("agents", {}).get("defaults", {}).get("model", "default")
        except Exception as exc:
            log.warning("[%s] Error leyendo config de disco en %s: %s", tenant.tenant_id, config_path, exc)

        url = f"{base_url}/v1/chat/completions"
        payload = {
            "model": model_id,
            "messages": messages,
            "session_id": session_id,
        }
        
        headers = {}
        if metadata and metadata.get("mesaid"):
            headers["X-Mesa-Id"] = str(metadata["mesaid"])
        headers["X-Tenant-Id"] = tenant.tenant_id

        try:
            fallback_triggered = False
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=payload, headers=headers)

                # Mecanismo de auto-recuperación si el modelo es rechazado
                if resp.status_code == 400 and "Only configured model" in resp.text:
                    import re
                    match = re.search(r"Only configured model '(.*?)'", resp.text)
                    if match:
                        payload["model"] = match.group(1)
                        resp = await client.post(url, json=payload, headers=headers)
                        fallback_triggered = True

            if resp.status_code != 200:
                log.error(
                    "[%s] Nanobot serve error %d: %s",
                    tenant.tenant_id, resp.status_code, resp.text[:500],
                )
                # DEVOLVEMOS EL ERROR EXACTO DEL NANOBOT A LA PANTALLA/CURL
                return f"⚠️ Error {resp.status_code} del Nanobot: {resp.text}"

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
