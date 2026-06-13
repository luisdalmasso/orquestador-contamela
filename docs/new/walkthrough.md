# Walkthrough: Implementación Tenant Católico

## Archivos creados

### Nanobot Home del tenant (`/contenedores/tenants/catolico/`)

| Archivo | Propósito |
|---------|-----------|
| [config.json](file:///contenedores/tenants/catolico/.nanobot/config.json) | Provider Gemini 2.0 Flash, MCP tools (RAG), sin telegram/heartbeat |
| [SOUL.md](file:///contenedores/tenants/catolico/workspace/SOUL.md) | Identidad del asistente, regla de leer `context/` antes de responder |
| [AGENTS.md](file:///contenedores/tenants/catolico/workspace/AGENTS.md) | Solo agente "defaults", sin delegation |
| [USER.md](file:///contenedores/tenants/catolico/workspace/USER.md) | Público, servicios, fuentes RAG |
| [CONSTANTS.md](file:///contenedores/tenants/catolico/workspace/CONSTANTS.md) | Skills y restricciones |
| [TOOLS.md](file:///contenedores/tenants/catolico/workspace/TOOLS.md) | Notas de uso de MCP tools |
| [config.yaml](file:///contenedores/tenants/catolico/config.yaml) | Config FastAPI: strategy keyword, clasificación, instrucciones por intent |
| `context/state.json` | Estado inicial vacío |
| `context/history.md` | Historial inicial vacío |
| `context/rule_context.md` | Instrucción de saludo por defecto |
| `skills/` | Symlinks a rag-manager, voice-manager, gemini-vision |

### Módulos FastAPI (`/contenedores/conti-backend/app/`)

| Archivo | Propósito |
|---------|-----------|
| [tenants/base.py](file:///contenedores/conti-backend/app/tenants/base.py) | `TenantConfig` Pydantic model |
| [tenants/registry.py](file:///contenedores/conti-backend/app/tenants/registry.py) | Descubre y cachéa configs de `/tenants/` |
| [tenants/context_writer.py](file:///contenedores/conti-backend/app/tenants/context_writer.py) | Escribe state/history/rule en `context/` |
| [chat/memory.py](file:///contenedores/conti-backend/app/chat/memory.py) | `RedisSessionManager` (Redis DB 3) |
| [chat/orchestrator.py](file:///contenedores/conti-backend/app/chat/orchestrator.py) | Orquestador central: estado → classify → context → nanobot → save |
| [chat/router.py](file:///contenedores/conti-backend/app/chat/router.py) | POST `/v1/chat`, GET `/v1/chat/tenants`, GET `/v1/chat/health` |

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| [main.py](file:///contenedores/conti-backend/app/main.py) | Import + register `chat_router` |
| [requirements.txt](file:///contenedores/conti-backend/requirements.txt) | Agregado `redis>=5.0`, `pyyaml>=6.0` |
| [docker-compose.conti.yml](file:///contenedores/conti-backend/docker-compose.conti.yml) | Bind mount `/tenants`, puerto 8766 |
| [entrypoint.sh](file:///contenedores/conti-backend/entrypoint.sh) | Loop de arranque de nanobots por tenant |

### Chainlit (Django container)

| Archivo | Cambio |
|---------|--------|
| [app.py](file:///compose/odoo-django-api/django/chainlit_app/app.py) | `on_message` reemplazado: HTTP POST a `conti-backend:9001/v1/chat` con `tenant_id` = `client_id` de la URL |

**Flujo Chainlit → Backend:**
```
https://chatui.contamela.com/?client_id=catolico
  → Chainlit extrae client_id = "catolico"
  → on_message: POST http://conti-backend:9001/v1/chat
    { tenant_id: "catolico", session_id: thread_id, message: "..." }
  → Backend: Redis state → classify → write context → nanobot serve :8766 → response
  → Chainlit muestra la respuesta
```

## Pendiente

1. **Rebuild del contenedor** — para que las dependencias y el entrypoint tomen efecto
2. **Verificar arranque** del nanobot serve católico (paso 3)
3. **Pruebas de prompting** (paso 3.5) — testear manualmente cada intención
4. **Tests end-to-end** (paso 5) — curl al endpoint, verificar Redis
