# Estado Real — conti-backend

> Generado por análisis directo del código fuente.  
> Fecha: 2026-05-  
> Fuente: `app/`, `config/`, `entrypoint.sh`, `docker-compose.conti.yml`, `requirements.txt`

---

## Resumen ejecutivo

El backend está completamente implementado y operativo. Cubre las Fases 0–7 del Plan 2 más una Fase 8 (tenant católico) no contemplada en el plan original. El total de tools MCP registradas es **43**.

---

## Estructura del proyecto

```
app/
  main.py              — FastAPI app, routers, endpoints raíz
  config/              — Carga y modelos de configuración (Pydantic)
  core/                — ToolRegistry, ToolDefinition, categorías, visibilidad
  mcp/                 — Router MCP (JSON-RPC 2.0, SSE, REST)
  llm_emulation/       — Proxy OpenAI-compatible hacia nanobot serve
  onboarding/          — Loader de onboarding.md con fallback
  rules/               — Loader de rules.md con fallback
  services/            — Servicios singleton (health, registry, llm, nanobot, config, onboarding, rules)
  tools/               — Implementaciones de todas las tools MCP
  tenants/             — Sistema multi-tenant (base, registry, context_writer)
  chat/                — Orquestador de chat, memoria Redis, router
  web/                 — UI web (Jinja2 + static)
  utils/               — Logging, paths, security
config/
  app_config.json      — Configuración principal del backend
docs/                  — Documentación (onboarding, rules, planes)
tests/                 — Suite de tests pytest
entrypoint.sh          — Arranque multi-proceso con tmux
docker-compose.conti.yml — Compose con healthcheck, puertos y volúmenes
requirements.txt       — Dependencias Python
```

---

## Endpoints REST implementados

### Raíz y configuración

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/health` | Estado del backend (versión, uptime, servicios) |
| `GET` | `/config` | Configuración efectiva con secretos redactados |
| `POST` | `/config/reload` | Recarga configuración desde disco |
| `GET` | `/onboarding` | Contenido de onboarding.md. `?brief=true` para resumen |
| `POST` | `/onboarding/reload` | Recarga onboarding desde disco |
| `GET` | `/rules` | Reglas efectivas con checksum y mtime |
| `GET` | `/rules/raw` | Reglas en texto plano |
| `POST` | `/rules/reload` | Recarga rules desde disco |

### MCP

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/mcp` | Info del servidor MCP (JSON) o SSE si `Accept: text/event-stream` |
| `POST` | `/mcp` | JSON-RPC 2.0: `initialize`, `tools/list`, `tools/call`, `ping`, `notifications/initialized` |
| `GET` | `/mcp/tools` | Lista completa de tools con schemas JSON |
| `POST` | `/mcp/call` | Invocar tool por nombre (REST simple) |
| `POST` | `/mcp/execute` | Alias de `/mcp/call` con formato alternativo |
| `GET` | `/mcp/sse` | SSE legacy para Kilocode/Cline |

### LLM Emulation (OpenAI-compatible)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/v1` | Info del endpoint OpenAI-compatible |
| `GET` | `/v1/models` | Lista modelos disponibles (proxy a nanobot serve) |
| `POST` | `/v1/chat/completions` | Chat completions con streaming opcional (proxy a nanobot serve :8765) |
| `POST` | `/v1/responses` | Emulación de Responses API sobre chat completions. Sin streaming |
| `GET` | `/llm/backend/status` | Estado del nanobot serve |
| `POST` | `/llm/backend/reload` | Recarga configuración del nanobot serve |

### Chat multi-tenant

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/v1/chat` | Procesa mensaje de chat para un tenant específico |
| `GET` | `/v1/chat/tenants` | Lista tenants disponibles |
| `GET` | `/v1/chat/health` | Estado de Redis para el sistema de chat |
| `DELETE` | `/v1/chat/{tenant_id}/{session_id}` | Limpia sesión de chat |

### UI Web

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Redirige a `/ui` |
| `GET` | `/ui` | Panel principal (estado, health, git) |
| `GET` | `/ui/settings` | Configuración activa redactada |
| `GET` | `/ui/tools` | Catálogo MCP con tool runner |
| `GET` | `/ui/rules` | Onboarding y rules efectivos |
| `GET` | `/ui/nanobots` | Editor de config gateway, llm serve y tenant católico |
| `POST` | `/ui/nanobots/gateway` | Guarda config del gateway nanobot |
| `POST` | `/ui/nanobots/llm` | Guarda config del nanobot serve |
| `POST` | `/ui/nanobots/tenant/catolico` | Guarda config del nanobot serve del tenant católico |

---

## Tools MCP registradas (43 total)

### Grupo A — Filesystem (4)

| Tool | Descripción |
|------|-------------|
| `list_files` | Lista archivos y directorios bajo un root permitido |
| `read_file` | Lee archivo con soporte de rango de líneas (`start_line`, `end_line`) |
| `file_exists` | Informa si un path existe, si es archivo o directorio |
| `get_code_context` | Devuelve N líneas de contexto alrededor de una línea específica |

### Grupo B — Búsqueda (3)

| Tool | Descripción |
|------|-------------|
| `search_code_literal` | Busca texto/regex en el repo de desarrollo (`/desarrollo`) |
| `search_docs_literal` | Busca texto/regex en `/app/docs` |
| `grep_workspace` | Busca en el workspace completo permitido |

### Grupo C — Sistema y Health (2)

| Tool | Descripción |
|------|-------------|
| `health_check` | Estado del backend (equivalente a `GET /health`) |
| `reload_config` | Recarga configuración desde disco (visibilidad: `internal`) |

### Grupo D — Configuración y Governance (3)

| Tool | Descripción |
|------|-------------|
| `get_config` | Configuración efectiva redactada |
| `get_onboarding` | Onboarding efectivo. `brief=true` para solo el resumen |
| `get_rules` | Reglas efectivas del backend |

### Grupo E — Git / CI-CD local (6)

| Tool | Descripción |
|------|-------------|
| `get_git_status` | Estado del repo: branch, staged, modified, untracked, ahead/behind |
| `get_git_log` | Historial de commits (default: 10) |
| `diff_with_develop` | Diff HEAD vs develop (remoto o local) con stat |
| `get_pipeline_summary` | Resumen completo: status + log + diff + remotos |
| `run_salvar` | `confirm=false` → preview. `confirm=true` → `git add -A + commit + push develop` |
| `run_promover` | `confirm=false` → preview. `confirm=true` → merge develop→main + push |

### Grupo F — Docker y Containers (3)

| Tool | Descripción |
|------|-------------|
| `get_container_health` | Estado de contenedores via Docker socket. Filtra por `env` o `container` |
| `get_container_logs` | Logs con filtros `lines`, `since` (ej: `1h`, `30m`), `level` (`all`/`error`/`warning`) |
| `get_vps_status` | Vista consolidada: Docker + Git pipeline en una sola llamada |

### Grupo G — Traducción (3)

| Tool | Descripción |
|------|-------------|
| `start_markdown_translation` | Traduce Markdown en background via `deep_translator`. Devuelve `job_id` |
| `get_translation_job` | Estado y progreso de un job de traducción |
| `list_translation_jobs` | Lista jobs recientes (default: 20) |

### Grupo H — Documentos y PDF (3)

| Tool | Descripción |
|------|-------------|
| `start_pdf_to_markdown` | Convierte PDF/DOCX a Markdown via `markitdown`. Guarda en `/compose/documentos_listos/{store}/`. Opcionalmente encadena traducción |
| `get_md_conversion_job` | Estado de un job de conversión |
| `list_md_conversion_jobs` | Lista jobs recientes |

### Grupo I — RAG Flamehaven — Ingestión (4)

| Tool | Descripción |
|------|-------------|
| `start_rag_ingest` | Ingesta documento en Flamehaven. Detecta automáticamente 3 casos (MD en listos / no-MD / MD fuera de listos). Control de duplicados con `overwrite` |
| `get_rag_ingest_job` | Estado de un job de ingestión |
| `list_rag_ingest_jobs` | Lista jobs recientes |
| `scan_documentos_nuevos` | Escanea `/compose/documentos_nuevos/{store}/`, mueve a `procesados/` y lanza ingesta. Soporta `dry_run`, `store=all`, `max_files`, `include_procesados` |

### Grupo J — RAG Flamehaven — Búsqueda (4)

| Tool | Descripción |
|------|-------------|
| `search_rag` | Búsqueda completa (hybrid/semantic/keyword) con respuesta LLM (Gemini). Devuelve `answer`, `sources`, `search_confidence`, `low_confidence` |
| `search_rag_quick` | Búsqueda keyword sin LLM. Solo `sources` y `matched`. Sin tokens Gemini |
| `search_rag_semantic` | Búsqueda semántica pura (DSP v2.0). Sin BM25. Tolerante a typos y sinónimos |
| `list_rag_store_docs` | Inventario de documentos indexados en un store |

### Grupo K — Católico (3)

| Tool | Descripción |
|------|-------------|
| `catolico_lecturas_dia` | Lecturas litúrgicas del día desde dominicos.org. Incluye video YouTube y audio SoundCloud si están disponibles. Consulta info litúrgica desde PostgreSQL si está disponible |
| `catolico_biblia_buscar` | Búsqueda de citas bíblicas. Implementación parcial (esqueleto funcional, sin fuente real) |
| `catolico_leer_documento` | Lee texto completo de un documento del RAG para resumir |

---

## Sistema multi-tenant (Fase 8 — no estaba en el plan original)

### Arquitectura

```
POST /v1/chat
  → ChatOrchestrator
      → TenantRegistry (descubre /tenants/<id>/config.yaml)
      → RedisSessionManager (DB 10, host: redis_odoo)
          → get_state + get_history
      → Clasificación por keywords (strategy=keyword)
      → ContextWriter → /tenants/<id>/context/{state.json, history.md, rule_context.md}
      → HTTP POST → nanobot serve del tenant (puerto configurable, default: 8766)
      → Guarda respuesta en Redis
```

### Componentes

- `app/tenants/base.py` — `TenantConfig` Pydantic: `tenant_id`, `strategy`, `nanobot_port`, `chat_ttl`, `max_history`, `rag_store`, `keywords`, `instructions`
- `app/tenants/registry.py` — Descubre configs desde `/tenants/<id>/config.yaml` (YAML). Singleton con lazy load
- `app/tenants/context_writer.py` — Escribe `state.json`, `history.md`, `rule_context.md` antes de cada llamada al nanobot
- `app/chat/memory.py` — `RedisSessionManager`: historial y estado por `tenant_id/session_id`. TTL configurable
- `app/chat/orchestrator.py` — Orquestador central. Extrae JSON embebido de respuestas nanobot si es necesario
- `app/chat/router.py` — Endpoints `/v1/chat`, `/v1/chat/tenants`, `/v1/chat/health`, `DELETE /v1/chat/{tenant}/{session}`

### Tenant implementado: `catolico`

- Config en `/tenants/catolico/config.yaml`
- Nanobot serve en puerto `8766`
- Strategy: `keyword`
- Nanobot home: `/tenants/catolico/`
- Integración con Chainlit en `chatui.contamela.com/?client_id=catolico`

---

## Runtime y despliegue

### Procesos en `entrypoint.sh`

1. `nanobot gateway` — puerto `18790`, config: `/home/nanobot/.nanobot/config.json`
2. `nanobot serve` — puerto `8765`, config: `/home/nanobot/llm_serve_config.json` (con bootstrap automático desde config legacy si no existe)
3. `uvicorn app.main:app` — puerto `9001`
4. `clawteam board serve` — puerto `8080`
5. `nanobot serve [catolico]` — puerto `8766`, home: `/tenants/catolico/`

### Puertos publicados (`docker-compose.conti.yml`)

| Puerto host | Puerto contenedor | Servicio |
|-------------|-------------------|---------|
| `9001` | `9001` | FastAPI backend (principal) |
| `9007` | `9001` | FastAPI backend (alias legacy) |
| `8765` | `8765` | nanobot serve (OpenAI-compatible) |
| `8766` | `8766` | nanobot serve tenant católico |
| `8080` | `8080` | ClawTeam board UI |
| `18790` | `18790` | nanobot gateway |

### Healthcheck

```yaml
test: wget -qO- http://127.0.0.1:9001/health && wget -qO- http://127.0.0.1:8765/health
interval: 30s / timeout: 10s / retries: 5 / start_period: 30s
```

### Volúmenes montados

| Path en contenedor | Origen | Modo |
|--------------------|--------|------|
| `/home/nanobot/` | `./conti_home` | rw |
| `/desarrollo` | `/desarrollo` | rw |
| `/compose` | `/compose` | ro |
| `/compose/documentos_listos` | `/compose/documentos_listos` | rw |
| `/compose/documentos_nuevos` | `/compose/documentos_nuevos` | rw |
| `/tenants` | `/contenedores/tenants` | rw |
| `/var/run/docker.sock` | `/var/run/docker.sock` | rw |
| `/app/app` | `./app` | rw (hot-reload) |
| `/app/config/team.toml` | `/desarrollo/config/team.toml` | ro |
| `/app/skills` | `/desarrollo/shared_skills` | ro |

---

## Configuración (`config/app_config.json`)

```json
{
  "server":         { "host": "0.0.0.0", "port": 9001 },
  "llm_emulation":  { "enabled": true, "serve_base_url": "http://127.0.0.1:8765", "streaming_enabled": true },
  "paths": {
    "home_root":          "/home/nanobot",
    "development_repo":   "/desarrollo",
    "production_repo":    "/compose",
    "onboarding_file":    "/app/docs/onboarding.md",
    "rules_file":         "/app/docs/rules.md"
  },
  "rag": {
    "base_url":       "http://flamehaven:8000",
    "api_key_env":    "FLAMEHAVEN_API_KEY",
    "default_store":  "default"
  },
  "ui": { "enabled": true, "title": "Conti MCP Console" }
}
```

---

## Dependencias clave (`requirements.txt`)

| Paquete | Uso |
|---------|-----|
| `fastapi`, `uvicorn[standard]` | Framework web |
| `pydantic-settings` | Modelos de config |
| `sse-starlette` | SSE para MCP |
| `httpx>=0.27.0` | Proxy HTTP (nanobot serve, Flamehaven) |
| `redis>=5.0` | Sesiones de chat multi-tenant |
| `pyyaml>=6.0` | Configs de tenants |
| `deep-translator` | Traducción de Markdown |
| `markitdown[pdf]==0.1.5` | Conversión PDF/DOCX a Markdown |
| `docker` | Observabilidad de contenedores via socket |
| `jinja2` | Templates UI web |
| `requests`, `beautifulsoup4` | Scraping lecturas católicas |
| `tiktoken` | Conteo de tokens |
| `faster-whisper`, `gTTS` | Voz (transcripción y síntesis) |
| `google-api-python-client` | Google Workspace |
| `python-telegram-bot` | Canal Telegram |

---

## Diferencias respecto al README y planes originales

### Implementado y no documentado en README

- Sistema multi-tenant completo (`app/chat/`, `app/tenants/`)
- Tenant `católico` con nanobot serve propio en puerto 8766
- Tools RAG de búsqueda: `search_rag`, `search_rag_quick`, `search_rag_semantic`, `list_rag_store_docs`
- Tools católico: `catolico_lecturas_dia`, `catolico_biblia_buscar`, `catolico_leer_documento`
- `scan_documentos_nuevos` con `include_procesados` y `max_files`
- `POST /config/reload` (el README solo menciona `POST /onboarding/reload`)
- `DELETE /v1/chat/{tenant_id}/{session_id}`
- Editor de config del tenant católico en `/ui/nanobots`
- Extracción de JSON embebido en respuestas del orquestador de chat

### Documentado en README pero con diferencias en implementación

- El README menciona "22 tools registradas" — el código registra **43**
- El README menciona `GET /ui/nanobots` — también existe `POST /ui/nanobots/tenant/catolico`
- `POST /v1/responses` no soporta `stream=true` (devuelve HTTP 400 explícito)
- `reload_config` tiene visibilidad `internal` (no aparece en listados públicos)

### Documentado en planes pero no implementado

- `supervisord` / `s6-overlay` para gestión de procesos (se usa `entrypoint.sh` con `wait`)
- `POST /v1/responses` con streaming
- `catolico_biblia_buscar` — implementado como esqueleto (devuelve datos simulados, sin fuente real)
- Tests de integración end-to-end para el sistema de chat multi-tenant

---

## Seguridad y allowlist de paths

Las tools de filesystem y búsqueda validan paths contra una allowlist definida en `app/utils/security.py`. Los roots permitidos son los configurados en `config.paths` (`/home/nanobot`, `/desarrollo`, `/compose`, `/app/docs`, `/app/skills`). Cualquier path fuera de esos roots lanza `ValueError`.

---

## Invocación MCP — referencia rápida

```bash
# Listar tools
curl http://localhost:9001/mcp/tools

# Invocar tool (REST)
curl -X POST http://localhost:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_pipeline_summary", "arguments": {}}'

# Invocar tool (JSON-RPC 2.0)
curl -X POST http://localhost:9001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"health_check","arguments":{}}}'

# Chat multi-tenant
curl -X POST http://localhost:9001/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"catolico","session_id":"test-1","message":"¿Cuál es el evangelio de hoy?"}'
```
