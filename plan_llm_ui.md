# Plan: Actualización UI + Compose de conti-backend

> **Fecha**: 2026-07-10
> **Estado**: borrador
> **Objetivo**: Documentar la arquitectura real, diagnóstico completo, y plan de actualización del docker-compose y la UI `/ui`.

## Estado de implementación

| Fase | Estado | Notas |
|------|--------|-------|
| **Fase 1**: Compose Cleanup | ✅ COMPLETADA + VERIFICADA | .env.example creado, secrets movidos a ${VAR}, validación pasada |
| **Fase 2**: Dashboard UI | ✅ COMPLETADA | DashboardService, dashboard.html, nav actualizado |
| **Fase 3**: Circuitos | ⏳ PENDIENTE | |
| **Fase 4**: Hermes Profiles | ⏳ PENDIENTE | |
| **Fase 5**: OMP Runtime | ⏳ PENDIENTE | |
| **Fase 6**: MCP Tools (mejora) | ⏳ PENDIENTE | |
| **Fase 7**: Tenants | ⏳ PENDIENTE | |
| **Fase 8**: Observabilidad | ⏳ PENDIENTE | |
| **Fase 9**: Servicios | ⏳ PENDIENTE | |
| **Fase 10**: Seguridad | ⏳ PENDIENTE | |

### Archivos creados/modificados en Fase 1-2

- `docker-compose.conti.yml` — secrets hardcodeados reemplazados por ${VAR}
- `.env.example` — template con todas las variables de entorno
- `.env` — archivo de entorno con valores reales (NO commitear a git)
- `app/services/dashboard_service.py` — NUEVO: servicio de dashboard
- `app/web/templates/dashboard.html` — NUEVO: template de dashboard
- `app/web/templates/base.html` — actualizado nav y descripción
- `app/web/router.py` — route /ui actualizada para dashboard
- `app/web/templates/index.html` — ELIMINADO (obsoleto)
- `app/web/templates/settings.html` — ELIMINADO (obsoleto)
- `app/web/templates/rules.html` — ELIMINADO (obsoleto)
- `app/web/templates/nanobots.html` — ELIMINADO (obsoleto)

---

## 1. Arquitectura real del contenedor

### 1.1 Procesos que corren dentro de conti-backend

El `entrypoint_hermes.sh` levanta **9 procesos**:

```
PID  Proceso                          Puerto    Propósito
───  ───────────────────────────────  ────────  ──────────────────────────────────────────
1    FastAPI (uvicorn)                :9001     MCP backend + chat completions emulator + UI
2    TraceUpdater (Python)            —         Background thread, actualiza trazas Ponytail
3    Hermes gateway [católico]        :8766     API Server, chatbot católico
4    Hermes gateway [resto]           :8767     API Server, restaurante
5    Hermes gateway [odoo]            :8768     API Server, ERP multi-tenant
6    Hermes gateway [odoo-resto]      —         Telegram only (sin API Server)
7    Hermes gateway [odoo-nudo]       —         Telegram only (sin API Server)
8    Hermes gateway [odoo-mendoza]    :8769     API Server + Telegram, staff OCRL Mendoza
9    Hermes gateway [mendoza]         :8770     API Server + wppconnect, clientes OCRL Mendoza
10   Hermes gateway [contihome]       :18791    Telegram default
11   Hermes dashboard                 :9119     Web dashboard Hermes
12   OpenHands Agent Server           :3000     Orquestador de circuitos
13   OpenHands Agent Canvas (ingress) :3012     GUI web oficial OpenHands
14   OpenHands CLI Web                :3001     GUI textual OpenHands (aiohttp)
15   codebase-memory-mcp reindex      —         Background, re-indexa knowledge graph
```

### 1.2 Los 2 caminos de routing en :9001

```
Request entrante → FastAPI :9001
    │
    ├─ POST /v1/chat/completions ──────────────────────────────────────┐
    │   Ruta: OpenHands Circuit System                                 │
    │                                                                   │
    │   1. parse body, extraer messages                                │
    │   2. detect_circuit(prompt, force) por keywords                  │
    │      - "produccion", "deploy", "promover" → circuito produccion  │
    │      - "conti-backend", "orquestador" → circuito backend         │
    │      - "desarrollo", "commit", "salvar" → circuito desarrollo    │
    │      - default → circuito libre                                  │
    │   3. governance injection (Layer 0, solo 1er mensaje de sesión)  │
    │   4. OpenHands Agent Server :3000                                │
    │      └─ ACP via omp_rpc → conti-omp :7891                       │
    │         └─ oh-my-pi runtime (ejecuta tools + MCP)                │
    │   5. respuesta OpenAI-compatible                                 │
    │                                                                   │
    │   Headers relevantes:                                            │
    │   - X-Circuit-ID: fuerza circuito (opcional)                     │
    │   - X-Session-ID: reutiliza sesión (opcional)                    │
    │   - Authorization: auth del cliente                              │
    │                                                                   │
    │   Soporta: stream=true (SSE) y sync (JSON)                      │
    └───────────────────────────────────────────────────────────────────┘
    │
    ├─ POST /v1/chat ─────────────────────────────────────────────────┐
    │   Ruta: Chat Router → Hermes Gateways                           │
    │                                                                   │
    │   1. Parse ChatRequest (tenant_id, session_id, message)          │
    │   2. resolve tenant → TenantConfig (nanobot_port)               │
    │   3. proxy a http://127.0.0.1:{port}/v1/chat/completions        │
    │      (el gateway Hermes responde en formato OpenAI)              │
    │                                                                   │
    │   Tenant → Port mapping:                                         │
    │   - catolico → :8766                                             │
    │   - resto → :8767                                                │
    │   - odoo → :8768                                                 │
    │   - odoo-mendoza → :8769                                         │
    │   - mendoza → :8770                                              │
    │                                                                   │
    │   Headers relevantes:                                            │
    │   - X-Mesa-Id: ID de mesa (resto)                               │
    │   - X-Tenant-Id: tenant ID                                      │
    └───────────────────────────────────────────────────────────────────┘
    │
    ├─ /mcp/* ────────────────────────────────────────────────────────┐
    │   MCP Tools: 84 tools, 12 categorías                           │
    │   (filesystem, bootstrap, odoo, gitops, stack, documents,       │
    │    rag, catolico, sheets, code_edit, codebase_memory,           │
    │    observability)                                               │
    └───────────────────────────────────────────────────────────────────┘
    │
    ├─ /ui/* → Web UI (Jinja2 templates)
    ├─ /health, /config, /onboarding, /rules → Admin endpoints
    └─ /v1/models, /llm/backend/* → LLM emulation endpoints
```

### 1.3 Los 4 circuitos OpenHands

Definidos en `app/openhands_agent/circuits.py`:

| Circuito | Workspace | Git Action | Target | Tools nativos | MCP categories |
|----------|-----------|------------|--------|---------------|----------------|
| `desarrollo` | /desarrollo | `run_salvar` | develop | terminal, file_editor, task_tracker | TODAS |
| `produccion` | /compose | `run_promover` | develop→main | terminal, file_editor, task_tracker | TODAS + hotfix |
| `backend` | /contenedores/conti-backend | `run_salvar` | main | terminal, file_editor, task_tracker | TODAS |
| `libre` | /tmp/free-agent | none | — | none | solo MCP (sin git/editor) |

**Detección de circuito** (`detect_circuit()`):
- Palabras clave en `CIRCUIT_KEYWORDS` (case-insensitive)
- Primer match gana (orden: produccion > backend > desarrollo)
- Default: `libre`
- Override: header `X-Circuit-ID` o campo `circuit` en body

**CircuitConfig dataclass**:
```python
@dataclass(frozen=True)
class CircuitConfig:
    id: str
    workspace_dir: str
    description: str
    allowed_tools_native: tuple[str, ...]
    allowed_mcp_categories: tuple[str, ...]
    git_action: str                    # "run_salvar" | "run_promover" | "none"
    git_action_target: str = "develop" # rama destino
    git_action_options: tuple[str, ...] = ()  # ej: ("run_hotfix_sync",)
    llm_model_override: str | None = None
```

### 1.4 Los 7 perfiles Hermes

Cada perfil vive en `hermes_profiles/contihome/profiles/{nombre}/` y tiene:

| Archivo | Propósito |
|---------|-----------|
| `config.yaml` | Config completa del perfil (model, agent, terminal, browser, TTS, delegation, kanban, MCP, platforms) |
| `SOUL.md` | Personalidad del agente |
| `AGENTS.md` | Definición de agentes |
| `TOOLS.md` | Herramientas disponibles |
| `CONSTANTS.md` | Constantes |
| `gateway.yaml` | Config de Telegram (token, allow_from, group_policy) |
| `skills/` | Skills bundled (erp, email, research, devops, etc.) |
| `sessions/` | Historial de conversaciones |
| `state.db` | Estado persistente (SQLite) |
| `memories/` | Memoria del agente (MEMORY.md, USER.md) |
| `cron/` | Tareas programadas |
| `logs/` | Logs (agent.log, gateway.log, errors.log) |

**Perfiles activos**:

| Perfil | Puerto | Modelo | Rol | Plataformas |
|--------|--------|--------|-----|-------------|
| **contihome** (default) | :18791 | deepseek-v4-flash | Telegram general | Telegram |
| **catolico** | :8766 | stepfun/step-3.7-flash | Chatbot católico | Telegram |
| **resto** | :8767 | deepseek-v4-flash | Restaurante | Telegram |
| **odoo** | :8768 | — | ERP multi-tenant | API |
| **odoo-resto** | — | — | Tenant resto Telegram | Telegram |
| **odoo-nudo** | — | — | Tenant nudo Telegram | Telegram |
| **odoo-mendoza** | :8769 | — | Staff OCRL Mendoza | API + Telegram |
| **mendoza** | :8770 | — | Clientes OCRL Mendoza | API + wppconnect |

**Estructura de `config.yaml` (campos principales)**:

```yaml
model:
  default: deepseek-v4-flash          # modelo activo
  provider: deepseek                  # proveedor
  base_url: ''                        # URL base (vacio = provider default)
  api_mode: chat_completions          # modo de API
  api_key: eyJ...                     # API key
providers:
  kilocode:
    api: https://api.kilo.ai/api/gateway
agent:
  max_turns: 90                       # max giros de conversación
  gateway_timeout: 1800               # timeout del gateway (seg)
  tool_use_enforcement: auto          # auto|strict|off
  task_completion_guidance: true
  environment_probe: true
  image_input_mode: auto
terminal:
  backend: local                      # local|docker|singularity|modal|daytona
  timeout: 180
  docker_image: nikolaik/python-nodejs:python3.11-nodejs20
  container_memory: 5120              # MB
  persistent_shell: true
browser:
  engine: auto                        # auto|chromium|firefox
  inactivity_timeout: 120
  allow_private_urls: false
delegation:
  model: ''
  max_iterations: 50
  max_concurrent_children: 3
  orchestrator_enabled: true
kanban:
  dispatch_interval_seconds: 60
  auto_decompose: true
  max_in_progress_per_profile: null
mcp_servers:
  contibackend:
    url: http://localhost:9001/mcp
    transport: http
  odoo_mcp:
    url: http://odoo18:8072/mcp
    transport: http
    headers:
      Host: resto.contamela.com
      Authorization: Bearer ${CONTI_MCP_API_KEY}
      X-Odoo-Database: ${ODOO_TENANT_ID}
platforms:
  telegram:
    enabled: true
    token: 8217561599:AAH...
    allowed_users: [luisdalmasso]
    group_policy: mention
    send_progress: true
tts:
  provider: edge
  edge:
    voice: en-US-AriaNeural
stt:
  enabled: true
  provider: local
  local:
    model: base
```

### 1.5 OMP Runtime (oh-my-pi)

- **Contenedor**: `conti-omp` (:7891)
- **Runtime**: oh-my-pi con profile `conti`
- **Modelo**: xiaomi-token-plan-sgp/mimo-v2.5-pro
- **Comunicación**: NDJSON over TCP via socat
- **MCP servers** (configurados en `mcp.json`):
  - `conti-backend`: http://localhost:9001/mcp (84 tools)
  - `codebase-memory-mcp`: stdio (knowledge graph)
- **Skills**: codebase-memory, odoo-tools, git-workflow, observability-tools
- **Feature flag**: `CONTI_USE_OMP_AGENT=true` (usa OmpClient) / `false` (usa OpenHands SDK legacy)

### 1.6 MCP Tools (84 tools, 12 categorías)

| Categoría | # Tools | Descripción |
|-----------|---------|-------------|
| `filesystem` | 7 | list_files, read_file, file_exists, get_context, search_development, search_docs, search_workspace |
| `bootstrap` | 5 | system_status, get_config, reload_config, get_onboarding, get_rules |
| `odoo` | 18+ | test_connection, list_products, get_product, get_client_context, search_clients, list_clients, create_client, create_sale_order, create_cart, add_to_cart, get_cart_summary, confirm_sale_order, cancel_sale_order, create_invoice, register_payment, attach_comprobante, process_ocr, process_pdf, create_mercadopago_preference, get_billing_status, get_sales_report |
| `gitops` | 7 | git_status, git_log, git_diff, run_salvar, run_promover, run_hotfix_sync, get_pipeline_summary |
| `stack` | 3 | container_status, docker_logs, docker_status |
| `documents` | 6 | translate_markdown, get_translation_status, list_translations, convert_pdf, get_conversion_status, list_conversions |
| `rag` | 6+ | search_rag, ingest_document, get_ingestion_status, list_ingestion_jobs, search_rag_advanced, get_store_stats |
| `catolico` | 5 | get_liturgia, search_bible, get_saint_of_day, get_prayer, get_catechism |
| `sheets` | 3 | get_account_balance, get_sheet_data, update_sheet_cell |
| `code_edit` | 4 | validate_python_syntax, run_pytest, circuit_of_path, cross_repo_search |
| `codebase_memory` | 14 | search_graph, get_architecture, trace_path, get_code_snippet, query_graph, etc. |
| `observability` | 2 | ponytail_record_trace, ponytail_summarize_traces |

---

## 2. Diagnóstico: qué está obsoleto y qué falta

### 2.1 Secrets hardcodeados en docker-compose

**Problema**: 7 API keys están en texto plano en `docker-compose.conti.yml`:

| Variable | Valor hardcodeado | Riesgo |
|----------|-------------------|--------|
| `KILOCODE_API_KEY` | `eyJhbGci...` (JWT) | Expuesto en git |
| `DEEPSEEK_API_KEY` | `eyJhbGci...` (JWT) | Expuesto en git |
| `FLAMEHAVEN_API_KEY` | `sk_live_80b128...` | Expuesto en git |
| `GEMINI_API_KEY` | `AIzaSyBoKn...` | Expuesto en git |
| `SPINEDIGEST_LLM_API_KEY` | `AIzaSyBoKn...` (mismo que Gemini) | Expuesto en git |
| `CONTI_MCP_API_KEY` | `sk-conti-mcp-write` | Expuesto en git |
| Telegram token (en gateway.yaml) | `8217561599:AAH...` | Expuesto en git |

**Solución**: Mover todas a `.env` con `${VAR}` en el compose.

### 2.2 UI actual — páginas obsoletas

| Página | Estado actual | Problema |
|--------|---------------|----------|
| `/ui` (Estado) | Health + git + nanobot serve status | No muestra circuitos, no muestra hermes gateways, no muestra sesiones activas |
| `/ui/settings` | Volcado JSON crudo de config | Sin edición, sin filtros, sin valor operativo |
| `/ui/tools` | Catálogo MCP + tool runner | Sin filtro por categoría, sin validación de schema |
| `/ui/rules` | Render de .md como HTML | Sin interacción, redundante con `GET /onboarding` y `GET /rules` |
| `/ui/nanobots` | Edit NanobotConfigService | NO edita hermes profiles, NO edita circuitos, NO edita OMP. Legacy desde Sprint 4 |

### 2.3 UI actual — lo que falta

| Sección | Prioridad | Descripción |
|---------|-----------|-------------|
| **Dashboard** | ALTA | Estado consolidado de todos los servicios |
| **Circuitos** | ALTA | Edición de circuitos y governance |
| **Hermes Profiles** | ALTA | Edición de los 7 perfiles Hermes |
| **OMP Runtime** | MEDIA | Config de OMP y skills |
| **MCP Tools (mejora)** | MEDIA | Filtros y validación |
| **Tenants** | MEDIA | Edición de tenant configs |
| **Servicios** | BAJA | Odoo, RAG, Sheets, MercadoPago |
| **Seguridad** | BAJA | API keys, allow_from, policies |
| **Observabilidad** | ALTA | Sesiones, traces, logs |

---

## 3. Plan de actualización

### Fase 1: Compose Cleanup (seguridad) ✅ COMPLETADA

**Objetivo**: Secretar todas las API keys hardcodeadas.

**Acciones**:
1. Crear `/contenedores/conti-backend/.env.example` con todas las variables
2. Mover las 7 API keys hardcodeadas a `.env` (agregar a `.gitignore`)
3. Reemplazar valores hardcodeados en `docker-compose.conti.yml` con `${VAR}`
4. Verificar que el compose sigue funcionando con `docker compose config`

**Variables a mover a .env**:
```
KILOCODE_API_KEY=eyJhbGci...
DEEPSEEK_API_KEY=eyJhbGci...
FLAMEHAVEN_API_KEY=sk_live_80b128...
GEMINI_API_KEY=AIzaSyBoKn...
SPINEDIGEST_LLM_API_KEY=AIzaSyBoKn...
CONTI_MCP_API_KEY=sk-conti-mcp-write
TELEGRAM_BOT_TOKEN=8217561599:AAH...
XIAOMI_TOKEN_PLAN_SGP_API_KEY=tp-sghoyfyruw54cyfk9wi5zqfrzny5caqi69lq4d63ly14ee9s
MERCADOPAGO_ACCESS_TOKEN=...
MERCADOPAGO_PUBLIC_KEY=...
MERCADOPAGO_SANDBOX=...
MERCADOPAGO_SUCCESS_URL=...
MERCADOPAGO_FAILURE_URL=...
MERCADOPAGO_PENDING_URL=...
MERCADOPAGO_NOTIFICATION_URL=...
```

### Fase 2: UI — Dashboard (reemplaza `/ui` actual) ✅ COMPLETADA

**Objetivo**: Vista consolidada del estado de TODOS los servicios.

**Contenido**:

```
┌─────────────────────────────────────────────────────────────────┐
│  CONTI BACKEND — DASHBOARD                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ SERVICIOS CORE ─────────────────────────────────────────┐  │
│  │ FastAPI :9001        ✅ healthy    uptime: 2d 4h          │  │
│  │ OpenHands :3000      ✅ healthy    PID: 1234              │  │
│  │ OMP (conti-omp)      ✅ healthy    model: mimo-v2.5-pro   │  │
│  │ TraceUpdater         ✅ running    interval: 60s          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ CIRCUITOS (OpenHands) ──────────────────────────────────┐  │
│  │ desarrollo    ✅ active   workspace: /desarrollo          │  │
│  │                git: run_salvar → develop                  │  │
│  │                sesiones: 2  último uso: hace 15min        │  │
│  │                                                           │  │
│  │ produccion    ✅ active   workspace: /compose             │  │
│  │                git: run_promover develop→main             │  │
│  │                sesiones: 0  último uso: hace 2h           │  │
│  │                                                           │  │
│  │ backend       ✅ active   workspace: /contenedores/...    │  │
│  │                git: run_salvar → main                     │  │
│  │                sesiones: 1  último uso: hace 5min         │  │
│  │                                                           │  │
│  │ libre         ✅ active   workspace: /tmp/free-agent      │  │
│  │                git: none                                  │  │
│  │                sesiones: 0  último uso: hace 1d           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ HERMES GATEWAYS ────────────────────────────────────────┐  │
│  │ contihome  :18791  ✅ running  model: deepseek-v4-flash  │  │
│  │ catolico   :8766   ✅ running  model: stepfun/step-3.7   │  │
│  │ resto      :8767   ✅ running  model: deepseek-v4-flash  │  │
│  │ odoo       :8768   ✅ running  model: —                  │  │
│  │ odoo-resto TG       ✅ running  Telegram only             │  │
│  │ odoo-nudo  TG       ✅ running  Telegram only             │  │
│  │ odoo-mendoza :8769  ✅ running  API + Telegram            │  │
│  │ mendoza    :8770    ✅ running  API + wppconnect          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ MCP TOOLS ──────────────────────────────────────────────┐  │
│  │ Total: 84 tools  |  Categorías: 12                       │  │
│  │ filesystem: 7  bootstrap: 5  odoo: 18  gitops: 7         │  │
│  │ stack: 3  documents: 6  rag: 6  catolico: 5              │  │
│  │ sheets: 3  code_edit: 4  codebase_memory: 14  obs: 2     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ SESIONES RECIENTES ─────────────────────────────────────┐  │
│  │ circuito: backend  sesiones: 3  trazas: 47                │  │
│  │ circuito: desarrollo sesiones: 1  trazas: 12              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  [Circuitos] [Hermes] [OMP] [Tools] [Tenants] [Observability]  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementación**:
- **Route**: `GET /ui` (reemplaza la actual)
- **Template**: `app/web/templates/dashboard.html`
- **Backend**: `_build_dashboard_context()` que agrega:
  - Health de FastAPI, OpenHands, OMP
  - Estado de los 4 circuitos (desde `CircuitManager.status()`)
  - Estado de los 7 hermes gateways (health check por puerto)
  - Conteo de MCP tools por categoría
  - Sesiones recientes (desde `SessionStore`)
  - Últimas trazas Ponytail

### Fase 3: UI — Circuitos (NUEVA)

**Objetivo**: Editar la configuración de los 4 circuitos OpenHands.

**Contenido**:

```
┌─────────────────────────────────────────────────────────────────┐
│  CIRCUITOS — CONFIGURACIÓN                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ CIRCUIT: DESARROLLO ────────────────────────────────────┐  │
│  │                                                           │  │
│  │ Workspace:     /desarrollo                               │  │
│  │ Git Action:    run_salvar                                │  │
│  │ Git Target:    develop                                    │  │
│  │ Tools Nativos: terminal, file_editor, task_tracker        │  │
│  │ MCP Cats:      TODAS (12)                                │  │
│  │                                                           │  │
│  │ Palabras clave de detección:                              │  │
│  │   /desarrollo, rama develop, desarrollo, salvar,          │  │
│  │   commit, develop branch                                  │  │
│  │                                                           │  │
│  │ Governance: governance-layer0-desarrollo.md               │  │
│  │ [Editar governance] [Ver trazas] [Logs]                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ CIRCUIT: PRODUCCION ────────────────────────────────────┐  │
│  │ ...                                                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ CIRCUIT: BACKEND ───────────────────────────────────────┐  │
│  │ ...                                                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ CIRCUIT: LIBRE ─────────────────────────────────────────┐  │
│  │ ...                                                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementación**:
- **Routes**:
  - `GET /ui/circuits` — lista de circuitos
  - `GET /ui/circuits/{id}` — detalle de un circuito
  - `POST /ui/circuits/{id}` — actualizar circuito
  - `GET /ui/circuits/{id}/governance` — editar governance file
  - `POST /ui/circuits/{id}/governance` — guardar governance file
- **Templates**: `circuits.html`, `circuit_detail.html`, `circuit_governance.html`
- **Backend**: `CircuitService` que lee/escribe `circuits.py` y governance files

**Parámetros editables por circuito**:

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `id` | string (readonly) | Identificador del circuito |
| `workspace_dir` | string | Directorio de trabajo |
| `description` | text | Descripción del circuito |
| `allowed_tools_native` | multiselect | terminal, file_editor, task_tracker |
| `allowed_mcp_categories` | multiselect | Las 12 categorías MCP |
| `git_action` | select | run_salvar, run_promover, none |
| `git_action_target` | string | Rama destino (develop, main) |
| `git_action_options` | multiselect | run_hotfix_sync |
| `llm_model_override` | string | Modelo LLM override (opcional) |
| `circuit_keywords` | textarea | Palabras clave para detección |
| `governance_file` | textarea | Contenido de governance-layer0-{id}.md |

### Fase 4: UI — Hermes Profiles (NUEVA)

**Objetivo**: Editar la configuración de los 7 perfiles Hermes.

**Contenido**:

```
┌─────────────────────────────────────────────────────────────────┐
│  HERMES PROFILES — CONFIGURACIÓN                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Perfiles: [contihome] [catolico] [resto] [odoo]                │
│            [odoo-resto] [odoo-nudo] [odoo-mendoza] [mendoza]    │
│                                                                  │
│  ┌─ PERFIL: CATOLICO (:8766) ──────────────────────────────┐  │
│  │                                                           │  │
│  │ ── MODEL ──                                               │  │
│  │ Model:       stepfun/step-3.7-flash:free                  │  │
│  │ Provider:    kilocode                                     │  │
│  │ Base URL:    https://api.kilo.ai/api/gateway              │  │
│  │ API Mode:    chat_completions                             │  │
│  │ API Key:     •••••••••••• (redacted)  [Revelar]           │  │
│  │                                                           │  │
│  │ ── AGENT ──                                               │  │
│  │ Max Turns:   90                                          │  │
│  │ Gateway Timeout: 1800s                                   │  │
│  │ Tool Use Enforcement: auto                               │  │
│  │ Task Completion Guidance: ✅                             │  │
│  │ Image Input Mode: auto                                   │  │
│  │                                                           │  │
│  │ ── TERMINAL ──                                            │  │
│  │ Backend:     local                                       │  │
│  │ Timeout:     180s                                        │  │
│  │ Docker Image: nikolaik/python-nodejs:python3.11-nodejs20 │  │
│  │ Container Memory: 5120 MB                                │  │
│  │ Persistent Shell: ✅                                     │  │
│  │                                                           │  │
│  │ ── BROWSER ──                                             │  │
│  │ Engine:      auto                                        │  │
│  │ Inactivity Timeout: 120s                                 │  │
│  │ Allow Private URLs: ❌                                   │  │
│  │                                                           │  │
│  │ ── DELEGATION ──                                          │  │
│  │ Max Iterations: 50                                       │  │
│  │ Max Concurrent Children: 3                               │  │
│  │ Orchestrator Enabled: ✅                                 │  │
│  │                                                           │  │
│  │ ── KANBAN ──                                              │  │
│  │ Dispatch Interval: 60s                                   │  │
│  │ Auto Decompose: ✅                                       │  │
│  │                                                           │  │
│  │ ── MCP SERVERS ──                                         │  │
│  │ contibackend: http://localhost:9001/mcp (HTTP)           │  │
│  │ odoo_mcp: http://odoo18:8072/mcp (HTTP)                 │  │
│  │                                                           │  │
│  │ ── PLATFORM: TELEGRAM ──                                  │  │
│  │ Token:       •••••••••••• (redacted)  [Revelar]           │  │
│  │ Allow From:  luisdalmasso                                │  │
│  │ Group Policy: mention                                    │  │
│  │ Send Progress: ✅                                        │  │
│  │                                                           │  │
│  │ ── TTS/STT ──                                             │  │
│  │ TTS Provider: edge                                       │  │
│  │ TTS Voice:    en-US-AriaNeural                           │  │
│  │ STT Enabled:  ✅                                         │  │
│  │ STT Provider: local                                      │  │
│  │                                                           │  │
│  │ ── SOUL.MD ──                                             │  │
│  │ [Editar personalidad]                                    │  │
│  │                                                           │  │
│  │ ── SKILLS ──                                              │  │
│  │ erp ✅  email ✅  research ✅  devops ✅  creative ✅    │  │
│  │ social-media ✅  catolico ✅  documentos-doctrinales ✅   │  │
│  │                                                           │  │
│  │ [Guardar] [Reiniciar gateway] [Ver logs]                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementación**:
- **Routes**:
  - `GET /ui/hermes` — lista de perfiles
  - `GET /ui/hermes/{profile}` — detalle de un perfil
  - `POST /ui/hermes/{profile}` — actualizar config.yaml
  - `GET /ui/hermes/{profile}/soul` — editar SOUL.md
  - `POST /ui/hermes/{profile}/soul` — guardar SOUL.md
  - `GET /ui/hermes/{profile}/agents` — editar AGENTS.md
  - `POST /ui/hermes/{profile}/agents` — guardar AGENTS.md
  - `POST /ui/hermes/{profile}/restart` — reiniciar gateway
- **Templates**: `hermes.html`, `hermes_profile.html`, `hermes_soul.html`
- **Backend**: `HermesProfileService` que lee/escribe `config.yaml`, `SOUL.md`, `AGENTS.md`

**Parámetros editables por perfil** (agrupados):

#### Model
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `model.default` | string | Modelo activo |
| `model.provider` | select | Proveedor (deepseek, kilocode, openai, etc.) |
| `model.base_url` | string | URL base del proveedor |
| `model.api_key` | password | API key (redactada) |
| `model.api_mode` | select | chat_completions, responses |

#### Agent
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `agent.max_turns` | number | Max giros de conversación |
| `agent.gateway_timeout` | number | Timeout del gateway (seg) |
| `agent.tool_use_enforcement` | select | auto, strict, off |
| `agent.task_completion_guidance` | boolean | Guía de completación |
| `agent.image_input_mode` | select | auto, never, always |

#### Terminal
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `terminal.backend` | select | local, docker, singularity, modal, daytona |
| `terminal.timeout` | number | Timeout de comandos (seg) |
| `terminal.docker_image` | string | Imagen Docker para sandbox |
| `terminal.container_memory` | number | Memoria del contenedor (MB) |
| `terminal.persistent_shell` | boolean | Shell persistente |

#### Browser
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `browser.engine` | select | auto, chromium, firefox |
| `browser.inactivity_timeout` | number | Timeout de inactividad (seg) |
| `browser.allow_private_urls` | boolean | Permitir URLs privadas |

#### Delegation
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `delegation.max_iterations` | number | Max iteraciones de sub-agente |
| `delegation.max_concurrent_children` | number | Max hijos concurrentes |
| `delegation.orchestrator_enabled` | boolean | Habilitar orquestador |

#### Kanban
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `kanban.dispatch_interval_seconds` | number | Intervalo de dispatch |
| `kanban.auto_decompose` | boolean | Auto-descomponer tareas |

#### MCP Servers
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `mcp_servers.{name}.url` | string | URL del MCP server |
| `mcp_servers.{name}.transport` | select | http, stdio |
| `mcp_servers.{name}.headers` | json | Headers HTTP |

#### Platform (Telegram)
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `platforms.telegram.enabled` | boolean | Habilitado |
| `platforms.telegram.token` | password | Token del bot |
| `platforms.telegram.allowed_users` | list | Usuarios permitidos |
| `platforms.telegram.group_policy` | select | mention, always, never |
| `platforms.telegram.send_progress` | boolean | Enviar progreso |

#### TTS/STT
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `tts.provider` | select | edge, openai, elevenlabs, xai, mistral |
| `tts.edge.voice` | string | Voz de Edge TTS |
| `stt.enabled` | boolean | Habilitado |
| `stt.provider` | select | local, openai, mistral |

#### SOUL.md / AGENTS.md
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `SOUL.md` | textarea (markdown) | Personalidad del agente |
| `AGENTS.md` | textarea (markdown) | Definición de agentes |

### Fase 5: UI — OMP Runtime (NUEVA)

**Objetivo**: Configurar el runtime de oh-my-pi.

**Contenido**:

```
┌─────────────────────────────────────────────────────────────────┐
│  OMP RUNTIME — CONFIGURACIÓN                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ ESTADO ─────────────────────────────────────────────────┐  │
│  │ Contenedor:    conti-omp                                 │  │
│  │ Puerto:        :7891                                     │  │
│  │ Profile:       conti                                     │  │
│  │ Modelo:        xiaomi-token-plan-sgp/mimo-v2.5-pro       │  │
│  │ Provider:      xiaomi-token-plan-sgp                     │  │
│  │ Mode:          execute                                   │  │
│  │ Status:        ✅ healthy                                │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ MODELO ─────────────────────────────────────────────────┐  │
│  │ Model:    xiaomi-token-plan-sgp/mimo-v2.5-pro            │  │
│  │ Smol:     xiaomi-token-plan-sgp/mimo-v2.5               │  │
│  │ Slow:     (none)                                         │  │
│  │ [Cambiar modelo]                                         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ MCP SERVERS (OMP) ──────────────────────────────────────┐  │
│  │ conti-backend:     http://localhost:9001/mcp  [HTTP]     │  │
│  │ codebase-memory:   stdio (codebase-memory-mcp)           │  │
│  │ [Agregar MCP server] [Eliminar]                          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ SKILLS ─────────────────────────────────────────────────┐  │
│  │ codebase-memory   ✅  Knowledge graph via MCP            │  │
│  │ odoo-tools        ✅  Herramientas Odoo                  │  │
│  │ git-workflow      ✅  Flujo git (run_salvar, etc.)       │  │
│  │ observability     ✅  Ponytail traces                    │  │
│  │ [Crear skill] [Editar] [Eliminar]                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  [Reiniciar OMP] [Ver logs] [Ver MCP config]                   │
└─────────────────────────────────────────────────────────────────┘
```

**Implementación**:
- **Routes**:
  - `GET /ui/omp` — estado y configuración
  - `POST /ui/omp/model` — cambiar modelo
  - `GET /ui/omp/mcp` — listar MCP servers
  - `POST /ui/omp/mcp` — agregar/editar MCP server
  - `DELETE /ui/omp/mcp/{name}` — eliminar MCP server
  - `GET /ui/omp/skills` — listar skills
  - `POST /ui/omp/skills` — crear/editar skill
  - `DELETE /ui/omp/skills/{name}` — eliminar skill
  - `POST /ui/omp/restart` — reiniciar contenedor
- **Templates**: `omp.html`
- **Backend**: `OMPConfigService` que lee/escribe `mcp.json`, skills, y controla el contenedor

### Fase 6: UI — MCP Tools (mejora)

**Objetivo**: Mejorar la página actual con filtros y validación.

**Mejoras**:
1. **Filtro por categoría**: dropdown con las 12 categorías
2. **Filtro por visibilidad**: PUBLIC / INTERNAL / ALL
3. **Búsqueda**: campo de texto para filtrar por nombre/descripción
4. **Conteo**: mostrar count de tools filtradas
5. **Ejecución**: validación de schema antes de enviar
6. **Resultado**: formateo con syntax highlighting para JSON
7. **Documentación**: expandir descripción de cada tool

**Implementación**:
- **Route**: `GET /ui/tools` (misma, con query params)
- **Template**: `tools.html` (actualizado)
- **Backend**: `registry_service.list_tools()` ya existe, agregar filtros

### Fase 7: UI — Tenants (NUEVA)

**Objetivo**: Editar la configuración de tenants para el chat router.

**Contenido**:

```
┌─────────────────────────────────────────────────────────────────┐
│  TENANTS — CONFIGURACIÓN                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Tenants descubiertos: /tenants/*/config.yaml                   │
│                                                                  │
│  ┌─ TENANT: CATOLICO ───────────────────────────────────────┐  │
│  │ Tenant ID:      catolico                                  │  │
│  │ Strategy:       keyword                                   │  │
│  │ Nanobot Port:   8766                                      │  │
│  │ Chat TTL:       1800s                                     │  │
│  │ Max History:    30                                        │  │
│  │ RAG Store:      default                                   │  │
│  │                                                           │  │
│  │ Keywords:                                                │  │
│  │   liturgia: [misa, liturgia, oracion, rezar]             │  │
│  │   doctrina: [dogma,教义, catecismo]                       │  │
│  │                                                           │  │
│  │ Instructions:                                            │  │
│  │   liturgia: "Responde con las lecturas del día..."       │  │
│  │   doctrina: "Consulta el catecismo..."                   │  │
│  │                                                           │  │
│  │ [Guardar] [Ver gateway]                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ TENANT: RESTO ──────────────────────────────────────────┐  │
│  │ ...                                                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementación**:
- **Routes**:
  - `GET /ui/tenants` — listar tenants
  - `GET /ui/tenants/{id}` — detalle
  - `POST /ui/tenants/{id}` — actualizar
- **Templates**: `tenants.html`, `tenant_detail.html`
- **Backend**: `TenantConfigService` que lee/escribe `/tenants/*/config.yaml`

### Fase 8: UI — Observabilidad (NUEVA)

**Objetivo**: Monitoreo de sesiones, trazas y logs.

**Contenido**:

```
┌─────────────────────────────────────────────────────────────────┐
│  OBSERVABILIDAD                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ SESIONES ACTIVAS ───────────────────────────────────────┐  │
│  │ Sesión          Circuito     Último uso      Tokens      │  │
│  │ abc123          backend      hace 5min       12,450      │  │
│  │ def456          desarrollo   hace 15min       8,200      │  │
│  │ ghi789          backend      hace 2h         45,100      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ TRAZAS PONYTAIL ────────────────────────────────────────┐  │
│  │ Circuito: [desarrollo ▾]  Fecha: [2026-07-10]           │  │
│  │                                                           │  │
│  │ Trace ID        Tarea           Duración    Tokens        │  │
│  │ trace-1783...   "analizar ui"   12.3s       8,450        │  │
│  │ trace-1783...   "fix compose"   5.1s        3,200        │  │
│  │ trace-1783...   "test pytest"   8.7s        5,100        │  │
│  │                                                           │  │
│  │ [Ver detalle] [Exportar]                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ LOGS ───────────────────────────────────────────────────┐  │
│  │ Perfil: [contihome ▾]  Líneas: [100 ▾]                  │  │
│  │                                                           │  │
│  │ 2026-07-10 14:32:01 [agent] INFO: Processing message...  │  │
│  │ 2026-07-10 14:32:02 [gateway] INFO: Sending response...  │  │
│  │ 2026-07-10 14:32:03 [agent] WARN: Slow tool call...      │  │
│  │                                                           │  │
│  │ [Refrescar] [Download full log]                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ HEALTHCHECKS ───────────────────────────────────────────┐  │
│  │ Servicio          Status    Last check    Uptime         │  │
│  │ FastAPI :9001     ✅ OK     5s ago        2d 4h          │  │
│  │ OpenHands :3000   ✅ OK     5s ago        2d 4h          │  │
│  │ OMP :7891         ✅ OK     5s ago        2d 4h          │  │
│  │ Hermes :8766      ✅ OK     5s ago        2d 4h          │  │
│  │ Hermes :8767      ✅ OK     5s ago        2d 4h          │  │
│  │ ...                                                     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementación**:
- **Routes**:
  - `GET /ui/observability` — dashboard de observabilidad
  - `GET /ui/observability/sessions` — sesiones activas
  - `GET /ui/observability/traces` — trazas Ponytail
  - `GET /ui/observability/traces/{id}` — detalle de traza
  - `GET /ui/observability/logs` — logs por perfil
  - `GET /ui/observability/health` — healthchecks
- **Templates**: `observability.html`, `sessions.html`, `traces.html`, `logs.html`
- **Backend**: `ObservabilityService` que consulta SessionStore, PonytailTrace, y logs

### Fase 9: UI — Servicios (NUEVA)

**Objetivo**: Configurar servicios externos.

**Contenido**:

```
┌─────────────────────────────────────────────────────────────────┐
│  SERVICIOS — CONFIGURACIÓN                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ ODOO ───────────────────────────────────────────────────┐  │
│  │ URL:           http://odoo18:8069                        │  │
│  │ Database:      resto                                     │  │
│  │ User:          admin                                     │  │
│  │ Password:      •••••••• (redacted)                       │  │
│  │ Timeout:       30s                                       │  │
│  │ Max Retries:   3                                         │  │
│  │ OCR Enabled:   ✅                                        │  │
│  │ [Test Connection]                                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ RAG (FLAMEHAVEN) ───────────────────────────────────────┐  │
│  │ Base URL:      http://flamehaven:8000                    │  │
│  │ API Key:       •••••••• (redacted)                       │  │
│  │ Default Store: default                                   │  │
│  │ Stores:        [default, catolico, odoo]                 │  │
│  │ [Test Connection] [List Ingestion Jobs]                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ GOOGLE SHEETS ──────────────────────────────────────────┐  │
│  │ Credentials:   /code/google-workspace/credentials.json   │  │
│  │ Token:         /code/google-workspace/token.json         │  │
│  │ Planilla OCRL: [ID de planilla]                          │  │
│  │ [Test Connection]                                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ MERCADOPAGO ────────────────────────────────────────────┐  │
│  │ Access Token:  •••••••• (redacted)                       │  │
│  │ Public Key:    •••••••• (redacted)                       │  │
│  │ Sandbox:       ✅                                        │  │
│  │ Success URL:   https://...                               │  │
│  │ Failure URL:   https://...                               │  │
│  │ Pending URL:   https://...                               │  │
│  │ Notification:  https://...                               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ CODEBASE MEMORY MCP ────────────────────────────────────┐  │
│  │ Repos indexados:                                         │  │
│  │   - contenedores-conti-backend (4.4K nodos)             │  │
│  │   - desarrollo (153K nodos)                              │  │
│  │   - compose (134K nodos)                                │  │
│  │ [Re-indexar] [Ver stats]                                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementación**:
- **Routes**:
  - `GET /ui/services` — dashboard de servicios
  - `GET /ui/services/odoo` — config Odoo
  - `POST /ui/services/odoo` — guardar config
  - `POST /ui/services/odoo/test` — test connection
  - `GET /ui/services/rag` — config RAG
  - `POST /ui/services/rag` — guardar config
  - `GET /ui/services/sheets` — config Google Sheets
  - `POST /ui/services/sheets` — guardar config
  - `GET /ui/services/mercadopago` — config MercadoPago
  - `POST /ui/services/mercadopago` — guardar config
  - `GET /ui/services/cbm` — estado codebase-memory
  - `POST /ui/services/cbm/reindex` — re-indexar
- **Templates**: `services.html`, `service_odoo.html`, `service_rag.html`, etc.
- **Backend**: `ServicesConfigService` que lee/escribe `app_config.json` y kontrola servicios

### Fase 10: UI — Seguridad (NUEVA)

**Objetivo**: Gestionar API keys y políticas de acceso.

**Contenido**:

```
┌─────────────────────────────────────────────────────────────────┐
│  SEGURIDAD — CONFIGURACIÓN                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ API KEYS ───────────────────────────────────────────────┐  │
│  │ Variable                   Valor                         │  │
│  │ KILOCODE_API_KEY           ••••••••••••  [Revelar]       │  │
│  │ DEEPSEEK_API_KEY           ••••••••••••  [Revelar]       │  │
│  │ FLAMEHAVEN_API_KEY         ••••••••••••  [Revelar]       │  │
│  │ GEMINI_API_KEY             ••••••••••••  [Revelar]       │  │
│  │ CONTI_MCP_API_KEY          ••••••••••••  [Revelar]       │  │
│  │ TELEGRAM_BOT_TOKEN         ••••••••••••  [Revelar]       │  │
│  │ XIAOMI_TOKEN_PLAN_SGP      ••••••••••••  [Revelar]       │  │
│  │                                                           │  │
│  │ [Actualizar .env]                                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ APPROVALS ──────────────────────────────────────────────┐  │
│  │ Mode:             auto                                  │  │
│  │ Timeout:          60s                                   │  │
│  │ Cron Mode:        deny                                  │  │
│  │ MCP Reload Confirm: ✅                                  │  │
│  │ Destructive Slash Confirm: ✅                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ SECURITY ───────────────────────────────────────────────┐  │
│  │ Allow Private URLs: ❌                                  │  │
│  │ Redact Secrets:     ✅                                  │  │
│  │ Tirith Enabled:     ✅                                  │  │
│  │ Allow Lazy Installs: ✅                                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementación**:
- **Routes**:
  - `GET /ui/security` — dashboard de seguridad
  - `GET /ui/security/keys` — listar API keys (redactadas)
  - `POST /ui/security/keys` — actualizar API key
  - `GET /ui/security/approvals` — config de approvals
  - `POST /ui/security/approvals` — guardar config
  - `GET /ui/security/policies` — políticas de seguridad
  - `POST /ui/security/policies` — guardar config
- **Templates**: `security.html`
- **Backend**: `SecurityConfigService` que lee `.env` y config de Hermes

---

## 4. Estructura de archivos propuesta

### Templates (app/web/templates/)

```
app/web/templates/
├── base.html                    # Layout base (actual, mantener)
├── dashboard.html               # NUEVO: Dashboard principal
├── circuits.html                # NUEVO: Lista de circuitos
├── circuit_detail.html          # NUEVO: Detalle de circuito
├── circuit_governance.html      # NUEVO: Editor de governance
├── hermes.html                  # NUEVO: Lista de perfiles Hermes
├── hermes_profile.html          # NUEVO: Detalle de perfil
├── hermes_soul.html             # NUEVO: Editor de SOUL.md
├── omp.html                     # NUEVO: Config OMP
├── tools.html                   # ACTUALIZAR: Filtros y búsqueda
├── tenants.html                 # NUEVO: Lista de tenants
├── tenant_detail.html           # NUEVO: Detalle de tenant
├── observability.html           # NUEVO: Dashboard de observabilidad
├── sessions.html                # NUEVO: Sesiones activas
├── traces.html                  # NUEVO: Trazas Ponytail
├── logs.html                    # NUEVO: Logs por perfil
├── services.html                # NUEVO: Dashboard de servicios
├── service_odoo.html            # NUEVO: Config Odoo
├── service_rag.html             # NUEVO: Config RAG
├── service_sheets.html          # NUEVO: Config Google Sheets
├── service_mercadopago.html     # NUEVO: Config MercadoPago
├── security.html                # NUEVO: Seguridad
├── index.html                   # ELIMINAR (reemplazado por dashboard.html)
├── settings.html                # ELIMINAR (reemplazado por services.html)
├── rules.html                   # ELIMINAR (reemplazado por observability.html)
└── nanobots.html                # ELIMINAR (reemplazado por hermes.html)
```

### Routes (app/web/router.py)

```python
# NUEVAS routes
@router.get("/ui/circuits")
@router.get("/ui/circuits/{circuit_id}")
@router.post("/ui/circuits/{circuit_id}")
@router.get("/ui/circuits/{circuit_id}/governance")
@router.post("/ui/circuits/{circuit_id}/governance")

@router.get("/ui/hermes")
@router.get("/ui/hermes/{profile}")
@router.post("/ui/hermes/{profile}")
@router.get("/ui/hermes/{profile}/soul")
@router.post("/ui/hermes/{profile}/soul")
@router.post("/ui/hermes/{profile}/restart")

@router.get("/ui/omp")
@router.post("/ui/omp/model")
@router.get("/ui/omp/mcp")
@router.post("/ui/omp/mcp")
@router.delete("/ui/omp/mcp/{name}")
@router.get("/ui/omp/skills")
@router.post("/ui/omp/skills")
@router.delete("/ui/omp/skills/{name}")
@router.post("/ui/omp/restart")

@router.get("/ui/tenants")
@router.get("/ui/tenants/{tenant_id}")
@router.post("/ui/tenants/{tenant_id}")

@router.get("/ui/observability")
@router.get("/ui/observability/sessions")
@router.get("/ui/observability/traces")
@router.get("/ui/observability/traces/{trace_id}")
@router.get("/ui/observability/logs")
@router.get("/ui/observability/health")

@router.get("/ui/services")
@router.get("/ui/services/odoo")
@router.post("/ui/services/odoo")
@router.post("/ui/services/odoo/test")
@router.get("/ui/services/rag")
@router.post("/ui/services/rag")
@router.get("/ui/services/sheets")
@router.post("/ui/services/sheets")
@router.get("/ui/services/mercadopago")
@router.post("/ui/services/mercadopago")
@router.get("/ui/services/cbm")
@router.post("/ui/services/cbm/reindex")

@router.get("/ui/security")
@router.get("/ui/security/keys")
@router.post("/ui/security/keys")
@router.get("/ui/security/approvals")
@router.post("/ui/security/approvals")
@router.get("/ui/security/policies")
@router.post("/ui/security/policies")
```

### Services (app/services/)

```python
# NUEVOS services
app/services/circuit_service.py        # Edición de circuitos
app/services/hermes_profile_service.py # Edición de perfiles Hermes
app/services/omp_config_service.py     # Config de OMP
app/services/observability_service.py  # Sesiones, traces, logs
app/services/services_config_service.py # Odoo, RAG, Sheets, MercadoPago
app/services/security_config_service.py # API keys, approvals, policies
```

### Static (app/web/static/)

```
app/web/static/
├── app.css                       # ACTUALIZAR: estilos para nuevas páginas
├── app.js                        # ACTUALIZAR: JS para formularios y filtros
└── ...
```

---

## 5. Orden de implementación

| Fase | Dependencias | Esfuerzo estimado |
|------|--------------|-------------------|
| **Fase 1**: Compose Cleanup | Ninguna | 1h |
| **Fase 2**: Dashboard | Ninguna | 4h |
| **Fase 3**: Circuitos | Fase 2 | 6h |
| **Fase 4**: Hermes Profiles | Fase 2 | 8h |
| **Fase 5**: OMP Runtime | Fase 2 | 4h |
| **Fase 6**: MCP Tools (mejora) | Ninguna | 3h |
| **Fase 7**: Tenants | Fase 2 | 4h |
| **Fase 8**: Observabilidad | Fase 2, 3 | 6h |
| **Fase 9**: Servicios | Fase 2 | 4h |
| **Fase 10**: Seguridad | Fase 2 | 3h |

**Total estimado**: ~43h

**Orden recomendado**:
1. Fase 1 (Compose Cleanup) — prioridad seguridad
2. Fase 2 (Dashboard) — base para todo
3. Fase 3 (Circuitos) — alta prioridad
4. Fase 4 (Hermes Profiles) — alta prioridad
5. Fase 8 (Observabilidad) — alta prioridad
6. Fase 6 (MCP Tools) — mejora rápida
7. Fase 5 (OMP Runtime) — media prioridad
8. Fase 7 (Tenants) — media prioridad
9. Fase 9 (Servicios) — baja prioridad
10. Fase 10 (Seguridad) — baja prioridad

---

## 6. Parámetros que DEBEN estar en el compose (versión final)

```yaml
services:
  conti-backend:
    environment:
      # ── Core ──
      - PYTHONUNBUFFERED=1
      - CONTI_BACKEND_CONFIG=/app/config/app_config.json
      - HERMES_HOME=/app/hermes_profiles/contihome
      - TZ=America/Argentina/Mendoza

      # ── OpenHands Agent Server (orquestador de circuitos) ──
      - OPENHANDS_LLM_MODEL=${OPENHANDS_LLM_MODEL:-openai/mimo-v2.5-pro}
      - OPENHANDS_LLM_BASE_URL=${OPENHANDS_LLM_BASE_URL:-https://token-plan-sgp.xiaomimimo.com/v1}
      - OPENHANDS_LLM_API_KEY=${OPENHANDS_LLM_API_KEY:-${XIAOMI_TOKEN_PLAN_SGP_API_KEY}}
      - OPENHANDS_LLM_MAX_TOKENS=${OPENHANDS_LLM_MAX_TOKENS:-4000}
      - OPENHANDS_TIMEOUT=${OPENHANDS_TIMEOUT:-600}
      - AGENT_SERVER_URL=http://127.0.0.1:3000

      # ── OMP Runtime (oh-my-pi via conti-omp) ──
      - CONTI_USE_OMP_AGENT=true
      - OMP_HOST=${OMP_HOST:-conti-omp}
      - OMP_PORT=${OMP_PORT:-7891}
      - OMP_PROMPT_TIMEOUT=${OMP_PROMPT_TIMEOUT:-360}

      # ── MCP Odoo ──
      - CONTI_MCP_API_KEY=${CONTI_MCP_API_KEY}
      - ODOO_TENANT_ID=${ODOO_TENANT_ID:-resto}
      - MESA_ID=${MESA_ID:-1}

      # ── Docker ──
      - DOCKER_API_VERSION=1.44

      # ── Secrets (via .env, NUNCA hardcodeados) ──
      - KILOCODE_API_KEY=${KILOCODE_API_KEY}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - FLAMEHAVEN_API_KEY=${FLAMEHAVEN_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - SPINEDIGEST_LLM_API_KEY=${SPINEDIGEST_LLM_API_KEY:-${GEMINI_API_KEY}}
      - MERCADOPAGO_ACCESS_TOKEN=${MERCADOPAGO_ACCESS_TOKEN}
      - MERCADOPAGO_PUBLIC_KEY=${MERCADOPAGO_PUBLIC_KEY}
      - MERCADOPAGO_SANDBOX=${MERCADOPAGO_SANDBOX}
      - MERCADOPAGO_SUCCESS_URL=${MERCADOPAGO_SUCCESS_URL}
      - MERCADOPAGO_FAILURE_URL=${MERCADOPAGO_FAILURE_URL}
      - MERCADOPAGO_PENDING_URL=${MERCADOPAGO_PENDING_URL}
      - MERCADOPAGO_NOTIFICATION_URL=${MERCADOPAGO_NOTIFICATION_URL}
      - XIAOMI_TOKEN_PLAN_SGP_API_KEY=${XIAOMI_TOKEN_PLAN_SGP_API_KEY}

      # ── Tracing (Ponytail) ──
      - PONYTAIL_TRACE_DIR=${PONYTAIL_TRACE_DIR:-.ponytail/traces/}
      - PONYTAIL_COMMIT_TRACES=${PONYTAIL_COMMIT_TRACES:-true}
      - PONYTAIL_PUSH_TRACES=${PONYTAIL_PUSH_TRACES:-true}
      - PONYTAIL_TRACE_RETENTION_DAYS=${PONYTAIL_TRACE_RETENTION_DAYS:-90}

    volumes:
      # ── Git repos (RW para circuitos) ──
      - /desarrollo:/desarrollo
      - /compose:/compose
      - /contenedores/conti-backend:/contenedores/conti-backend
      # ── App hot-reload ──
      - ./app:/app/app
      - ./docs:/app/docs
      - ./app/hermes_profiles:/app/hermes_profiles
      - ./config/team.toml:/app/config/team.toml
      - /desarrollo/shared_skills:/app/skills
      # ── Docker socket ──
      - /var/run/docker.sock:/var/run/docker.sock
      # ── Data ──
      - ./claw_data:/app/data
      - openhands_workspace:/app/workspace
      # ── codebase-memory-mcp cache ──
      - /home/admin_odoo/cbm_cache:/home/conti/.cache/codebase-memory-mcp
      - /var/lib/docker/volumes/conti-backend_omp_home/_data/.local/bin/codebase-memory-mcp:/usr/local/bin/codebase-memory-mcp:ro
      # ── Google Workspace (si Hermes lo necesita) ──
      - ./google-workspace:/code/google-workspace
      # ── Voice (si Hermes TTS/STT lo necesita) ──
      - ./voice:/code/voice

    ports:
      - "9001:9001"     # MCP + chat completions + UI + admin
      - "9007:9001"     # MCP backup
      - "3011:3000"     # OpenHands Agent Server
      - "3012:3012"     # OpenHands Agent Canvas
      - "3013:3001"     # OpenHands CLI
      - "8642:8642"     # Hermes API default (contihome)
      - "8766:8766"     # Hermes católico
      - "8767:8767"     # Hermes resto
      - "8768:8768"     # Hermes odoo
      - "8769:8769"     # Hermes odoo-mendoza
      - "8770:8770"     # Hermes mendoza
      - "18791:18791"   # Hermes gateway contihome
      - "9119:9119"     # Hermes dashboard

    mem_limit: 24g  # necesario por OpenHands + 7 Hermes gateways + OMP client
    cpus: 4
```

---

## 7. Notas de implementación

### 7.1 Nav actualizado

```python
nav_items = [
    {"href": "/ui", "label": "Dashboard"},
    {"href": "/ui/circuits", "label": "Circuitos"},
    {"href": "/ui/hermes", "label": "Hermes"},
    {"href": "/ui/omp", "label": "OMP"},
    {"href": "/ui/tools", "label": "Tools"},
    {"href": "/ui/tenants", "label": "Tenants"},
    {"href": "/ui/observability", "label": "Observabilidad"},
    {"href": "/ui/services", "label": "Servicios"},
    {"href": "/ui/security", "label": "Seguridad"},
]
```

### 7.2 CSS

Mantener el CSS actual (`app.css`) y agregar estilos para:
- Cards de dashboard
- Tablas con filtros
- Formularios de edición
- Badges de estado (✅/❌/⚠️)
- Code blocks para SOUL.md/AGENTS.md
- Toggle switches para booleanos
- Password fields con botón "Revelar"

### 7.3 JS

Agregar a `app.js`:
- Filtros de tablas (por categoría, visibilidad, nombre)
- Toggle de revelar API keys
- Form submission con confirmación
- Auto-refresh de logs
- WebSocket para logs en tiempo real (opcional)

### 7.4 Seguridad de la UI

- **NUNCA** exponer API keys completas en la UI (siempre redactadas)
- **NUNCA** permitir ejecución de comandos peligrosos sin confirmación
- **SIEMPRE** validar inputs antes de escribir archivos
- **SIEMPRE** hacer backup antes de modificar config.yaml
- **USAR** `GET` para lectura, `POST` para escritura (nunca `GET` con side effects)
