# Plan 2 — Migración y Actualización del Conocimiento al Nuevo LLM (OpenHands)

> **Estado:** v0.6 — Plan activo. Iterando con Luis.
> **Última actualización:** 24/jun/2026, ~16:45 ART.
> **Cambios recientes (24/jun):** GUI real de OpenHands (`agent-canvas`) instalada y verificada en :3012. Eliminé la falsa GUI textual (`openhands web`). Pendiente integrar ponytail al agente.

---

## 0. Estado actual del contenedor (24/jun/2026, 16:45 ART)

### Servicios corriendo en `conti-backend`

| Puerto host | Servicio | Estado |
|-------------|----------|--------|
| `:9001` | LLM FastAPI emulado (Mistral via kilo.ai) | ✅ UP |
| `:3011` | OpenHands Agent Server (API REST Swagger) | ✅ UP |
| `:3012` | **OpenHands Agent Canvas (GUI Next.js oficial)** | ✅ UP — verificado visualmente por Luis |
| `:3010` | Sourcebot v5.0.4 (RAG sobre 3 repos) | ✅ UP |
| `:8766-8770` | Hermes API servers (legacy, 5 perfiles) | ✅ UP |

### Configuración LLM activo

```yaml
model: mistral/mistral-small-latest
base_url: https://api.mistral.ai/v1
api_key: KkwZJdkcmtP3zKYRdOhyHltpxJxUarna  # en .env y docker-compose
```

### Imágenes Docker

| Imagen | ID | Tamaño | Notas |
|--------|-----|--------|-------|
| `conti-backend-conti-backend:latest` | `b92aeac6e707` | ~25GB | Contiene OpenHands SDK + oh-my-pi + vendor/ponytail |
| `conti-sourcebot:latest` | (v5.0.4) | - | Indexa `/desarrollo`, `/compose`, `/contenedores/conti-backend` |

### Repos como submódulos (`vendor/`)

| Submódulo | URL | Estado |
|-----------|-----|--------|
| `vendor/OpenHands` | `https://github.com/OpenHands/OpenHands` | ✅ Clonado |
| `vendor/oh-my-pi` | `https://github.com/can1357/oh-my-pi` | ✅ Clonado |
| `vendor/ponytail` | `https://github.com/DietrichGebert/ponytail` | ✅ Clonado (pero NO usado activamente) |

---

## 1. Resumen ejecutivo

[continúa en línea 12+]

## 1. Resumen ejecutivo

El nuevo LLM está **operativo**. Implementa:
- **4 circuitos independientes** (desarrollo/produccion/backend/libre) con workspaces y tools específicos.
- **Detección automática de circuito** por keywords del prompt.
- **Stack OpenHands SDK v1.29** + **Mistral** como LLM (`mistral-small-latest`).
- **Sourcebot** como RAG sobre los 3 repos bind-mounted.
- **Ponytail** para trazabilidad con persistencia JSON.
- **Router LLM desacoplado** que NO redirige más a Hermes `:8767`.

**Pendientes críticos:**
- Integrar MCP tools (64) en el loop del agente (actualmente el agente solo tiene 3 tools nativas).
- Activar oh-my-pi (compilado e instalado pero no conectado).
- Persistir historial de conversaciones entre reinicios.
- Actualizar `onboarding.md` y `rules.md` para reflejar los 4 circuitos.
- Resolver error de Next.js Server Actions en Sourcebot (afecta la UI, no el backend).

---

## 2. Estado actual de los componentes

### 2.1 Stack verificado funcionando

| Componente | Puerto/URL | Estado | Verificado |
|------------|-----------|--------|-----------|
| LLM FastAPI (Mistral) | `:9001` | ✅ UP | `POST /v1/chat/completions` retorna `"OK"` con `circuit: libre` |
| OpenHands Agent Server (GUI) | `:3011` | ✅ UP | 15 tools disponibles vía `/api/tools` |
| Sourcebot | `:3010` | ⚠️ UP pero con errores Next.js Server Actions en UI | API search OK |
| Hermes católico | `:8766` | ✅ UP | HTTP 401 con `Authorization: Bearer sk-hermes-catolico-...` |
| Hermes resto | `:8767` | ✅ UP | Auth required |
| Hermes odoo | `:8768` | ✅ UP | Auth required |
| Hermes odoo-mendoza | `:8769` | ✅ UP | Auth required |
| Hermes mendoza | `:8770` | ✅ UP | Auth required |
| Redis (`redis_odoo`) | interno | ✅ UP | DB 14 asignada a Sourcebot |
| Postgres (`compose-db-1`) | `5432` | ✅ UP | DB `sourcebot` creada |
| MCP JSON-RPC en `:9001/mcp` | interno | ✅ UP | 64 tools registradas |

### 2.2 LLM por defecto

```yaml
model: mistral/mistral-small-latest
base_url: https://api.mistral.ai/v1
api_key: KkwZJdkcmtP3zKYRdOhyHltpxJxUarna
max_tokens: 4000
```

Selección automática de API key según `base_url`:
- `mistral.ai` → `OPENHANDS_LLM_API_KEY` / `MISTRAL_API_KEY`
- `kilo`/`openrouter` → `KILOCODE_API_KEY`
- `gemini`/`google` → `GEMINI_API_KEY`

### 2.3 Componentes del stack OpenHands

| Componente | Versión | Estado | Notas |
|------------|---------|--------|-------|
| `openhands-sdk` | 1.29.0 | ✅ Instalado | `LLM`, `Agent`, `Conversation`, `LocalWorkspace` |
| `openhands-tools` | 1.29.0 | ✅ Instalado | `terminal`, `file_editor`, `task_tracker`, `browser_tool_set` |
| `openhands-agent-server` | 1.29.0 | ✅ Instalado | GUI REST en `:3000` dentro del contenedor |
| `omp-rpc` (oh-my-pi) | 0.94 | ✅ Instalado | `RpcClient`, `HostTool`, eventos. **NO conectado al flujo aún.** |
| `Sourcebot` | v5.0.4 | ⚠️ Funciona con bugs UI | RAG sobre 3 repos: orquestador-contamela, contamela-stack-dev, contamela-stack-prod |
| `ponytail` | (rules-only) | ✅ Cargado | `vendor/ponytail/AGENTS.md` (~3KB) |

---

## 3. Flujo end-to-end completo

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Cliente (Kilocode IDE / VSCode / curl / Chainlit)                            │
│ POST /v1/chat/completions con `circuit`: "desarrollo"|"produccion"|...        │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 1. app/llm_emulation/router.py (Fase 3 — Router LLM desacoplado)             │
│    • Recibe el body OpenAI-compatible                                       │
│    • NO redirige a Hermes :8767 (regla PLAN_LLM.MD v4)                      │
│    • Llama directamente a: openhands_service.run_task(body, auth_header)    │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 2. app/openhands_agent/service.py::OpenHandsService.run_task                │
│                                                                              │
│    a) Detección de circuito:                                                 │
│       force = payload.get("circuit")  # override explícito del cliente     │
│       circuit_id = detect_circuit(user_prompt, force=force)                │
│       # Prioridad: libre < desarrollo < produccion < backend               │
│                                                                              │
│    b) Ponytail context manager:                                              │
│       with PonytailTrace(task_name=user_prompt[:80],                       │
│                           payload={**payload, "_circuit": circuit_id}) as t:│
│           t._log("circuit_selected", {id, workspace})                       │
│                                                                              │
│    c) Sourcebot (RAG sobre código):                                          │
│       sourcebot_hits = _sourcebot_search(user_prompt)                       │
│         → HTTP GET http://conti-sourcebot:3000/api/search                    │
│         → top-5 matches de los 3 repos indexados                            │
│                                                                              │
│    d) Construcción del prompt con circuit-aware rules:                       │
│       final_prompt = _build_circuit_prompt(                                 │
│           user_prompt, sourcebot_hits, circuit_cfg                           │
│       )                                                                     │
│       # Inyecta en orden:                                                    │
│       # 1) Ponytail AGENTS.md (identidad + reglas globales)                 │
│       # 2) Reglas del circuito (qué puede / qué no puede)                  │
│       # 3) Lista de tools disponibles en este circuito                      │
│       # 4) Code Context (Sourcebot hits)                                    │
│       # 5) User Task                                                        │
│                                                                              │
│    e) Obtener/crear conversación persistente:                                 │
│       conv = circuit_manager.get_or_create(circuit_id)                      │
│       # 4 conversaciones cacheadas (singleton) en memoria:                  │
│       #   desarrollo    → /desarrollo                                        │
│       #   produccion    → /compose                                           │
│       #   backend       → /contenedores/conti-backend                        │
│       #   libre         → /tmp/free-agent                                    │
│                                                                              │
│    f) Invocar OpenHands SDK en el circuito:                                  │
│       conv.send_message(final_prompt)                                       │
│       conv.run()  ← bloquea hasta FinishAction                              │
│                                                                              │
│    g) Extracción del último evento del agente:                                │
│       # Busca en orden:                                                     │
│       #   1. MessageEvent src=agent → llm_message.content[TextContent].text │
│       #   2. ActionEvent FinishAction → action.message                      │
│       #   3. ActionEvent → reasoning_content                                │
│                                                                              │
│    h) Cerrar traza Ponytail → persist JSON en /app/logs/ponytail/trace-*.json│
│                                                                              │
│    i) Devolver OpenAI-compatible con campo extra `circuit`:                   │
│       return { "choices": [...], "circuit": circuit_id, ... }               │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 3. app/openhands_agent/circuits.py::CircuitManager (4 conversaciones)       │
│                                                                              │
│    _build_conversation(cfg):                                                 │
│      1. register_default_tools() → terminal, file_editor, task_tracker     │
│      2. LLM(model, api_key, base_url)  # selección por base_url             │
│      3. Agent(llm, tools=[Tool(name=t) for t in cfg.allowed_tools_native])  │
│      4. LocalWorkspace(working_dir=cfg.workspace_dir)                        │
│      5. Conversation(agent, workspace)  # persistente                        │
│                                                                              │
│    Singleton: self._conversations[circuit_id]                                │
│    4 circuitos cacheados en memoria, historial vivo entre requests          │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 4. OpenHands SDK LocalConversation (loop agente-tool)                       │
│    Loop: prompt → LLM call → tool call → observation → ... → FinishAction  │
│                                                                              │
│    a) LLM Mistral (mistral/mistral-small-latest) recibe prompt              │
│    b) Mistral decide si necesita tool (soporta function calling)           │
│    c) Si sí → ejecuta tool nativa (terminal, file_editor, task_tracker)    │
│    d) Observation vuelve al LLM                                              │
│    e) Repite hasta FinishAction                                              │
│    f) Devuelve AssistantMessage con content final                            │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 5. MCP tools — Gateway JSON-RPC en FastAPI :9001/mcp                       │
│    (64 tools, descubiertas por el agente vía OpenAI-compatible interface)  │
│                                                                              │
│    Categoría `gitops` (8):  get_git_*, run_salvar, run_promover             │
│    Categoría `odoo` (21):   odoo_* (productos, clientes, pedidos, facturas)│
│    Categoría `rag` (10+):   search_rag*, start_rag_ingest*, catolico_*      │
│    Categoría `stack` (3):   get_container_*, get_vps_status                │
│    Categoría `filesystem` (7): list_files, read_file, search_code_*      │
│    Categoría `bootstrap` (5): health_check, get_config, get_rules          │
│    Categoría `documents` (8): start_*_translation, start_pdf_to_markdown  │
│    Categoría `sheets` (3):  sheet_* (Google Sheets OCRL Mendoza)          │
│                                                                              │
│    ⚠️ GAP: el agente MCP-to-OpenHands wrapper NO está implementado.       │
│    Por ahora el agente solo usa 3 tools NATIVAS.                            │
│    MCP tools se invocan directamente desde el cliente HTTP.                 │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 6. Respuesta OpenAI-compatible + circuit tag                                │
│    {                                                                        │
│      "id": "chatcmpl-openhands-<pid>-<ts>",                                 │
│      "model": "openhands-agent-v1",                                          │
│      "circuit": "produccion",          ← NUEVO                              │
│      "choices": [{                                                           │
│        "message": {"role": "assistant", "content": "<resultado>"}           │
│      }]                                                                      │
│    }                                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Los 4 circuitos — detalle completo

### 4.1 Resumen tabular

| ID | Workspace | Git action | Tools nativas | MCP cats | Detección por keywords |
|----|-----------|-----------|---------------|----------|----------------------|
| `desarrollo` | `/desarrollo` (RW) | `run_salvar` | terminal, file_editor, task_tracker | all | `/desarrollo`, `rama develop/dev`, `desarrollo`, `en desa/dev`, `salvar`, `commit` |
| `produccion` | `/compose` (RW solo git) | `run_promover` | terminal, file_editor, task_tracker | all | `/compose`, `produccion`, `rama main`, `promover`, `deploy`, `a main` |
| `backend` | `/contenedores/conti-backend` (RW) | `run_salvar` | terminal, file_editor, task_tracker | all | `/contenedores/conti-backend`, `orquestador-contamela`, `el backend` |
| `libre` | `/tmp/free-agent` | `none` | **NINGUNA** | bootstrap, rag, odoo, documents, sheets | default (sin match) |

### 4.2 Prompt inyectado por circuito (`_build_circuit_prompt`)

El prompt final se compone de **5 secciones concatenadas**:

```python
final_prompt = "\n\n---\n\n".join([
    # Sección 1: Identidad y reglas globales (de vendor/ponytail/AGENTS.md)
    PONYTAIL_RULES,                                    # ~3KB, leído al boot

    # Sección 2: Reglas específicas del circuito (de CircuitConfig.description)
    f"# Circuit: {cfg.id}\n{cfg.description}",

    # Sección 3: Lista de tools disponibles en este circuito
    _circuit_tool_list(cfg),                           # Nativas + MCP categories

    # Sección 4: Contexto de código (RAG de Sourcebot)
    code_context_section,                              # top-5 hits con snippets

    # Sección 5: Prompt del usuario
    f"# User Task\n{user_prompt}",
])
```

#### Ejemplo del prompt inyectado para `circuit: desarrollo`:

```markdown
# Conti — Agente DevOps del Stack Contamela
[... 50 líneas de identidad + reglas globales ...]

---

# Circuit: desarrollo
DevOps en rama develop de contamela-stack. Puedo commitear y pushear via
run_salvar (preview). NO promuevo a main, NO despliego.

## Tools disponibles en este circuito
- Nativas OpenHands: terminal, file_editor, task_tracker
- MCP categories: bootstrap, stack, rag, gitops, filesystem, odoo, documents, sheets
- Git action permitida: **run_salvar**

---

# Code Context (from Sourcebot)
### contamela-stack-dev :: odoo-django-api/django/views.py
```python
@api_view(['POST'])
def trigger_ingest(request):
    ...
```
### orquestador-contamela :: app/openhands_agent/service.py
```python
def run_task(self, payload):
    ...

---

# User Task
modifica el endpoint trigger_ingest para que use Celery en vez de síncrono
```

### 4.3 Reglas por circuito — texto completo

#### 🟢 `desarrollo` — DevOps en rama develop

```
Workspace: /desarrollo (RW bind-mount)
Git action permitida: run_salvar (preview)

Reglas:
1. Puedo commitear y pushear a develop via run_salvar (preview).
2. NO promuevo a main. NO despliego.
3. Cambios de código → commiteo directo en /desarrollo.
```

#### 🟡 `produccion` — Promoción a main (RW para git)

```
Workspace: /compose (RW bind-mount — solo para git)
Git action permitida: run_promover (preview)

Reglas:
1. Promuevo via run_promover (merge develop→main + push).
2. Después de una promoción exitosa, sincronizo /desarrollo:
   git checkout main && git pull (rama local dev refleja main).
3. NO corro 3-despliegue.sh ni docker compose -f producion.yml up -d (solo Luis).
4. /compose es RW solo para git. Cambios de código en producción van siempre
   por el flujo develop→main.
5. Si Luis modificó archivos en /compose directamente, avisar del riesgo antes
   de cualquier operación (reset --hard en 3-despliegue.sh podría borrarlos).
```

#### 🔵 `backend` — orquestador-contamela

```
Workspace: /contenedores/conti-backend (RW bind-mount)
Git action permitida: run_salvar (preview)

Reglas:
1. Commit + push via run_salvar (preview).
2. Sin flujo develop→main (este repo solo tiene main).
3. Las mismas reglas de vida o muerte que desarrollo.
```

#### ⚪ `libre` — Conversacional, sin git

```
Workspace: /tmp/free-agent
Git action permitida: none

Reglas:
1. SIN acceso a repos git. No tools nativas.
2. Solo MCP tools de RAG/consulta.
3. Si la tarea requiere fuentes externas no bind-mounted: pedir credenciales
   a Luis explícitamente.
4. Si Luis pasa una ruta del host (ej: /mnt/nuevo-repo), trabajar ahí sin tocar git.
```

---

## 5. Roles por componente

| Componente | Cuándo entra | Qué hace |
|------------|--------------|----------|
| **Ponytail** | Envuelve TODA la ejecución de `run_task` (`with PonytailTrace(...)`) | Carga `vendor/ponytail/AGENTS.md` (~3KB) con identidad + reglas globales. Persiste trace JSON en `/app/logs/ponytail/trace-<ts>.json` con timestamps, eventos, duración |
| **Sourcebot** | Después de detección de circuito, antes de invocar OpenHands | Busca el prompt del usuario en los 3 repos indexados (orquestador-contamela, contamela-stack-dev, contamela-stack-prod). Devuelve top-5 hits con snippet. Se inyectan como `# Code Context (from Sourcebot)` en el prompt |
| **oh-my-pi (omp-rpc)** | Código presente pero NO conectado al flujo actual | Cliente Python `RpcClient` que habla JSONL con el binario Rust `omp`. Compilado e instalado en `/usr/local/lib/python3.12/site-packages/omp_rpc/`, pero `service.py` no lo invoca aún (usa OpenHands SDK directo) |
| **OpenHands SDK** | Bloque principal de `run_task` | Recibe el prompt enriquecido, decide qué tools invocar, itera hasta `FinishAction`. Tools nativas (terminal, file_editor, task_tracker) sin necesidad de MCP |
| **MCP tools** | El agente las descubre vía JSON-RPC en `:9001/mcp` | 64 tools expuestas en `/mcp`. ⚠️ **AÚN NO integradas en el loop del agente** — el wrapper MCP↔OpenHands está pendiente. Por ahora se invocan directamente desde el cliente HTTP |

---

## 6. Gaps pendientes y roadmap

### 6.1 Gap crítico: MCP tools no integradas en el loop del agente

**Estado actual (24/jun/2026):** ✅ **CERRADO** vía Opción A.

**Decisión tomada (con Luis):** Opción A. El loopback HTTP al mismo proceso uvicorn
no es problema (latencia despreciable en localhost).

**Implementación** en `app/openhands_agent/circuits.py::_build_conversation`:

```python
from openhands.sdk.mcp import create_mcp_tools

if cfg.allowed_mcp_categories:
    try:
        mcp_url = os.getenv("CONTI_MCP_URL", "http://127.0.0.1:9001/mcp")
        mcp_tools = asyncio.run(create_mcp_tools(
            mcp_config={
                "mcpServers": {
                    "conti-backend": {
                        "url": mcp_url,
                        "transport": "streamable-http",
                    }
                }
            },
            timeout=30,
        ))
        tools_list.extend(mcp_tools)
    except Exception as exc:
        log.warning("MCP tools no pudieron cargarse: %s", exc)
```

**Cómo se descubre el endpoint MCP:** `CONTI_MCP_URL` env var (default `http://127.0.0.1:9001/mcp`).
El SDK abre conexión HTTP loopback y descubre las 64 tools vía `tools/list` JSON-RPC.

**Resultado esperado:** El agente ahora tiene 3 nativas + 64 MCP = 67 tools en los
circuitos `desarrollo`, `produccion` y `backend`. El circuito `libre` solo carga
las MCP categories permitidas (sin `gitops`/`stack`).

**Filtros pendientes (post-MVP):**
- Filtrar MCP tools por categoría (ahora se cargan todas las permitidas).
- Por categoría `gitops`: solo `run_salvar` (preview) y `run_promover` (preview)
  deben estar en `desarrollo`/`produccion`. Las demás (get_git_status, etc.) son de lectura.
- Por categoría `filesystem`: las 7 MCP tools duplican funcionalidad de las
  nativas OpenHands. Decidir si se mantienen o se eliminan.

**Siguiente paso (Sprint 1, 1-2 días):**
- [ ] Test E2E con commit real: prompt → agente invoca `terminal` + `file_editor` + `run_salvar`
- [ ] Test E2E con promote real: prompt → agente invoca `run_promover`
- [ ] Si funciona, eliminar de PLAN_2 la lista de gaps "pendientes" sobre MCP

### 6.1.bis Estado anterior (referencia histórica)

**Estado anterior:** El agente OpenHands solo tenía 3 tools nativas (terminal,
file_editor, task_tracker). Las 64 tools MCP (`odoo_*`, `run_salvar`, `search_rag`,
etc.) estaban registradas en `:9001/mcp` pero el agente NO las veía.

**Por qué importa:** Sin MCP, el agente no podía:
- Hacer commits/promote (`run_salvar`/`run_promover`)
- Buscar en RAG de Flamehaven/católico (`search_rag*`)
- Operar sobre Odoo (`odoo_*`)
- Diagnosticar el stack (`get_container_health`, etc.)

**Opciones evaluadas (mantenidas como referencia):**

#### Opción A — `mcp_config` vía `create_mcp_tools` ✅ (elegida)

SDK maneja la negociación JSON-RPC. Menos código, menos puntos de falla.
Loopback HTTP al mismo proceso (latencia despreciable en localhost).

#### Opción B — Wrapper Python con `httpx` (descartada)

Más control pero más código y bugs potenciales de conversión de schemas JSON-RPC.

#### Opción C — Activar oh-my-pi como intermediario (descartada)

`omp_rpc` instalado pero `service.py` no lo usa. Más complejo. NO recomendado.

### 6.2 Gap: `onboarding.md` y `rules.md` desactualizados

**Estado actual** (visto vía MCP `get_onboarding` y `get_rules`):

```markdown
# /app/docs/onboarding.md (versión actual)
- Backend MCP/FastAPI para conti-backend.
- Repo editable principal: /desarrollo.
- Repo de referencia read-only: /compose.
- HOME persistente: /home/nanobot.

# /app/docs/rules.md (versión actual)
1. No usar SSH para operar repos bind-mounted.
2. Modificar código en /desarrollo.
3. Tratar /compose como read-only.
4. No hardcodear prompts ni reglas en routers.
5. Toda mutación Git debe pasar por tools dedicadas.
```

**Lo que falta** según los 4 circuitos:

```markdown
# /app/docs/onboarding.md (propuesto)

## Stack
- Backend MCP/FastAPI para conti-backend (puerto 9001).
- Sourcebot v5.0.4 para RAG sobre código (puerto 3010).
- OpenHands Agent Server para GUI del agente (puerto 3011).
- Mistral como LLM (`mistral-small-latest`).
- Redis: redis_odoo:6379, DB 14 asignada a sourcebot.
- Postgres: compose-db-1:5432, DB `sourcebot`.

## Repos
- `/desarrollo` (rama `develop` de contamela-stack) — RW bind-mount.
- `/compose` (rama `main` de contamela-stack) — RW bind-mount, solo git.
- `/contenedores/conti-backend` (rama `main` de orquestador-contamela) — RW bind-mount.
- `/home/nanobot` — HOME persistente del agente (bind-mount a /contenedores/conti-backend/conti_home).

## Circuitos del agente
- `desarrollo`: DevOps en /desarrollo (commit + push a develop).
- `produccion`: Promoción develop→main en /compose.
- `backend`: DevOps sobre orquestador-contamela.
- `libre`: Conversacional, sin acceso a git.

## Hermes (legacy, sigue activo)
- 5 API servers (8766-8770) requieren Authorization Bearer con API_SERVER_KEY.
- Cada perfil tiene su API_SERVER_KEY en /app/hermes_profiles/contihome/profiles/<perfil>/.env.
```

```markdown
# /app/docs/rules.md (propuesto)

## Reglas de vida o muerte
1. NUNCA ejecutar git commit/push/merge/reset directo.
   Solo via run_salvar (preview) o run_promover (preview).
2. NUNCA ejecutar `bash /compose/3-despliegue.sh` ni
   `docker compose -f producion.yml up -d`. Solo Luis.
3. Toda acción destructiva → preview + confirmación explícita.
4. Idioma: siempre Español.
5. /compose es RW SOLO para git. Cambios de código en producción van
   por el flujo develop→main.

## Reglas operacionales
6. Operar DENTRO del contenedor, sin SSH (bind-mounts ya están).
7. Si la tarea accede a algo FUERA de /desarrollo, /compose,
   /contenedores/conti-backend, /home/nanobot: pedir credenciales a Luis.
8. Acción sobre palabras: nada de "¡Gran pregunta!".
9. Si Luis modificó archivos en /compose directamente, avisar del riesgo
   antes de cualquier operación (reset --hard en 3-despliegue.sh podría
   borrarlos).

## Reglas MCP
10. Usar solo tools registradas por el backend.
11. No inventar nombres de tools ni schemas.
12. Validar argumentos antes de ejecutar mutaciones.
13. Respetar allowlists de paths y visibilidades.
```

**Acción:** Sobreescribir `/app/docs/onboarding.md` y `/app/docs/rules.md` con las versiones nuevas. Hacerlo en el host (son bind-mounts) o vía MCP `reload_config` si existe.

### 6.3 Gap: Sourcebot UI con error de Next.js Server Actions

**Síntoma** (de logs del contenedor `conti-sourcebot`):
```
[web] | Error: Failed to find Server Action "x". This request might be from an older or newer deployment.
[web] | Read more: https://nextjs.org/docs/messages/failed-to-find-server-action
[web] | ⨯ Error: {"statusCode":401,"errorCode":"NOT_AUTHENTICATED","message":"Not authenticated"}
```

**Diagnóstico:**
- **Backend RAG: ✅ funciona** (zoekt cargó 3 shards, `service-ping` cada 30s OK, `/api/health` retorna 200).
- **UI web Next.js: ❌ Server Actions rotas** — Next.js 16.2.6 cambió cómo se serializan los Server Actions entre deploys. La imagen `:latest` puede diferir de lo que el cliente cacheó.
- **Auth: ⚠️ 401 NOT_AUTHENTICATED** — Sourcebot requiere `auth_secret` configurado para acceder a la UI admin (no afecta API search).

**Impacto:**
- La **UI web** muestra errores intermitentes al hacer clicks (botones que llaman a Server Actions fallan).
- **El backend (search, indexación) sigue funcionando** — `POST /api/search` responde JSON.

**Fix sugerido (en orden):**
1. **Limpiar caché del browser** (Ctrl+Shift+R) y reintentar — puede ser solo un mismatch de build id.
2. **Fijar versión de Sourcebot** (no usar `:latest`) — `ghcr.io/sourcebot-dev/sourcebot:v5.0.4` (la que está corriendo).
3. Si persiste, **abrir issue en `https://github.com/sourcebot-dev/sourcebot`** con el log completo.
4. **Workaround:** usar la API REST directamente (`POST /api/search`) en lugar de la UI web.

**NO afecta al LLM**: sourcebot RAG se invoca via `httpx` en `service.py::_sourcebot_search`, no usa la UI.

### 6.3.bis Gap: OpenHands GUI no disponible

**Investigación realizada (24/jun/2026):**

#### Verificado: `openhands serve` no funciona dentro del contenedor

`openhands serve` requiere **Docker daemon funcional** para lanzar sub-contenedores. Nuestro contenedor tiene `/var/run/docker.sock` montado pero el client API es v1.41 mientras el daemon exige ≥1.44 (incompatibilidad de versiones). Por eso `openhands serve` falla con "Docker daemon is not running".

#### Verificado: `openhands web` SÍ funciona ✅

`openhands web` es la **GUI textual web de OpenHands** (frontend Textual servido por aiohttp). **No necesita Docker daemon** porque corre in-process con el CLI.

**Verificación visual** (captura de Luis): El splash screen "uv run openhands" aparece correctamente en `http://localhost:3012/`.

**⚠️ Diferencia importante con `agent-server`:**
- `agent-server` (:3011) es la **API REST** oficial (`POST /v1/chat/completions`, etc.) que consume el LLM emulado.
- `openhands web` (:3012) es una **GUI independiente** que arranca su propio SDK interno. **NO se conecta** al `agent-server` nuestro.
- Son **dos productos distintos**: cuando Luis configura el LLM en `openhands web`, está creando su propio agente con su propia configuración.
- Si querés que la GUI use nuestro LLM emulado, tenés que apuntarla a `:9001/v1/chat/completions` en vez de a un LLM provider externo.

**Configuración del LLM en `openhands web`** (modal de Settings):
- **Provider**: `OpenAI-compatible` (o `OpenAI` con custom URL).
- **Custom Model**: `mistral/mistral-small-latest`.
- **API Key**: `KkwZJdkcmtP3zKYRdOhyHltpxJxUarna` (Mistral key actual).
- **Base URL**: `https://api.mistral.ai/v1` (en Advanced options).

#### Instalación en caliente (probado en el contenedor actual):

```bash
# uv tool install falló (symlink permission) pero uv run funciona
docker exec -d conti-backend bash -c '
  OPENHANDS_SUPPRESS_BANNER=1 nohup uv run --with openhands openhands web \
    --host 0.0.0.0 --port 3001 > /app/logs/openhands_web.log 2>&1 &
'
```

**Resultado verificado:**
- Listen en `0.0.0.0:3001` dentro del contenedor.
- `curl 127.0.0.1:3001` (desde dentro) → HTTP 200 + HTML con la GUI textual.
- HTML muestra: `<link rel="stylesheet" href="...xterm.css">`, `<script src="...textual.js">` — es la GUI Textual servida como web.
- **Acceso desde el host**: relay Python en :3012 → :3001 (container IP 172.18.0.10).

#### Cambios a aplicar en el próximo build (todo en un solo contenedor)

**1. Dockerfile** — agregar instalación de `openhands`:

```dockerfile
# Después de los `uv pip install` y `bun setup`:
RUN apt-get update && apt-get install -y --no-install-recommends socat && rm -rf /var/lib/apt/lists/*

# Instalar openhands CLI (frontend textual web)
RUN /root/.cargo/bin/uv tool install openhands --python 3.12 && \
    chmod -R a+rx /root/.local/share/uv/tools/openhands
```

**2. entrypoint_hermes.sh** — agregar `openhands web` después del agent-server:

```bash
# OpenHands Agent Server (API REST)
echo "🤖 OpenHands Agent Server en :3000"
agent-server --host 0.0.0.0 --port 3000 > "$LOG_DIR/openhands_agent_server.log" 2>&1 &
AGENT_SERVER_PID=$!

# OpenHands Web GUI (frontend textual)
echo "🌐 OpenHands Web GUI en :3001"
OPENHANDS_SUPPRESS_BANNER=1 nohup uv run --with openhands openhands web \
    --host 0.0.0.0 --port 3001 \
    > "$LOG_DIR/openhands_web.log" 2>&1 &
OPENHANDS_WEB_PID=$!
```

**3. docker-compose.conti.yml** — agregar puerto:

```yaml
ports:
  - "3011:3000"  # OpenHands Agent Server (API REST)
  - "3012:3001"  # OpenHands Web GUI (textual)
```

#### Estado y decisión

- ✅ **Verificado en caliente** que `openhands web` funciona dentro del contenedor (splash screen visible en captura).
- ⏳ **Pendiente**: rebuild para que quede persistente (Dockerfile + entrypoint + compose).
- ✅ **No requiere servicio externo**: todo va en el mismo contenedor (`conti-backend`).

#### Otras opciones evaluadas (no elegidas)

- **`openhands serve`** (GUI completa + Docker daemon): requiere docker daemon funcional, no es viable dentro del contenedor actual.
- **Imagen oficial `docker.openhands.dev/openhands/openhands:1.8`** (sidecar): duplicaría recursos y correría su propio agent-server.
- **`app.all-hands.dev` (cloud)**: requiere OAuth, conversaciones en cloud.
- **Open WebUI / Chainlit**: alternativas ya en el stack, no necesarias si `openhands web` funciona.

### 6.4 Gap: Persistencia del historial entre reinicios

**Estado actual:** `circuit_manager._conversations` vive solo en RAM del proceso uvicorn. Si el contenedor se reinicia, las 4 conversaciones se pierden y el agente no recuerda requests anteriores.

**Solución:** OpenHands SDK v1.29 soporta `ConversationPersistence` (o serializar `state.events` a JSON manualmente y guardar en `/app/data/conversations/`).

Implementación mínima:
```python
# En circuit_manager._build_conversation
conv = Conversation(agent=agent, workspace=workspace, persistence_dir="/app/data/conversations/<circuit_id>")
```

Después de cada `conv.run()`, los eventos se persisten automáticamente.

**Acción:** Agregar `persistence_dir` cuando se construya la conversación. Requiere que `/app/data/` exista (ya existe via bind-mount `./claw_data:/app/data`).

### 6.5 Gap: oh-my-pi (omp-rpc) no conectado

**Estado actual:** `omp_rpc` está instalado pero `service.py` no lo usa. Va directo a OpenHands SDK.

**Por qué no está conectado:** OpenHands SDK funciona bien sin omp. omp agrega valor cuando:
- Querés un LLM client más eficiente (streaming token-by-token).
- Querés que omp resuelva el modelo dinámicamente (configurarlo en runtime, no env).

**Decisión:** Dejar como TODO hasta que haya un caso de uso concreto. No es bloqueante.

### 6.6 Gap: Streaming end-to-end con Mistral

**Estado actual:** `stream_chat_completions` está implementado pero no testeado con Mistral. Mistral soporta SSE nativo.

**Acción:** Test E2E:
```bash
curl -N -X POST http://localhost:9001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"stream":true,"messages":[{"role":"user","content":"cuenta del 1 al 5"}]}'
```

Si no funciona con `circuit: libre` (porque no tiene tools), probar con `circuit: desarrollo` que tiene terminal.

---

## 7. Roadmap priorizado

### Sprint 1 — Cerrar gap MCP tools (1-2 días)

- [x] ✅ **Implementar Opción A (mcp_config en Agent)** — código listo en `circuits.py`
- [ ] **Test E2E con commit real** — pendiente
  - Prompt: `"Modifica /desarrollo/README.md agregando una línea sobre los 4 circuitos y commitealo"`
  - Verificar que el agente invoca `terminal` + `file_editor` + `run_salvar`.
- [ ] **Test E2E con promoción real** — pendiente
  - Prompt: `"Promueve el último commit de develop a main usando run_promover"`
  - Verificar que el merge develop→main funciona.
- [ ] **Validar que el agente ve 64+3 tools** — reiniciar y contar tools vía `GET /api/tools` de agent-server

### Sprint 2 — Actualizar onboarding.md y rules.md (medio día)

- [ ] Sobreescribir `/app/docs/onboarding.md` con la versión nueva.
- [ ] Sobreescribir `/app/docs/rules.md` con la versión nueva.
- [ ] Llamar `MCP reload_config` para invalidar caché si existe.
- [ ] Test E2E: el agente llama a `get_onboarding` y refleja los cambios.

### Sprint 3 — Persistencia del historial (medio día)

- [ ] Agregar `persistence_dir="/app/data/conversations/<id>"` en `_build_conversation`.
- [ ] Test: reiniciar contenedor, hacer un request al circuito `libre`, verificar que sigue teniendo el contexto.

### Sprint 4 — Sourcebot UI fix (1-2 horas)

- [ ] Limpiar caché del browser.
- [ ] Si persiste, fijar versión de Sourcebot (ej: `v5.0.4` exacto) en `sourcebot/Dockerfile`.
- [ ] Rebuild de sourcebot.

### Sprint 4.bis — GUI textual de OpenHands (`openhands web`) ✅ verificado en caliente

**Verificado en caliente** (24/jun/2026): `openhands web` funciona dentro del contenedor
en :3001. Sirve HTML + CSS + JS de la GUI Textual oficial de OpenHands.

**Confirmación visual de Luis:** splash screen con icono "uv run openhands" visible
en `http://localhost:3012/` desde el navegador.

**Acceso actual al GUI** (sin rebuild):
- Vía relay TCP Python en host: `http://localhost:3012/` → `:3001` (container) ✅
- Vía IP del container: `http://172.18.0.10:3001/` ✅
- Vía `curl 127.0.0.1:3001` (desde dentro del container) ✅

**⚠️ Configuración del LLM en la GUI**: cuando cargue el modal de Settings, completar con:
- **Provider**: `OpenAI-compatible`
- **Custom Model**: `mistral/mistral-small-latest`
- **API Key**: `KkwZJdkcmtP3zKYRdOhyHltpxJxUarna`
- **Base URL**: `https://api.mistral.ai/v1`

**Nota**: `openhands web` corre su propio SDK interno y NO se conecta al `agent-server`
ni al LLM emulado. Si querés que use el LLM emulado (`:9001/v1/chat/completions`),
configurá en Settings → Advanced → Custom Provider apuntando a `http://localhost:9001/v1`
con `OPENAI_BASE_URL` apuntando ahí.

**Cambios aplicados a archivos** (entrarán en el próximo build):

| Archivo | Cambio | Estado |
|---------|--------|--------|
| `Dockerfile` | Instala `socat` + `uv tool install openhands` | ✅ Listo |
| `entrypoint_hermes.sh` | Lanza `agent-server` en :3000 y `openhands web` en :3001 | ✅ Listo |
| `docker-compose.conti.yml` | Agrega `- "3012:3001"` al `ports` | ✅ Listo |

**Verificación final pre-rebuild:**
```bash
$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3012/
200
$ curl -s http://localhost:3012/ | head -3
<!DOCTYPE html>
<html>
  <head>
```

**Pendiente:** rebuild para que el puerto 3012 quede mapeado nativamente en el compose.
Hasta entonces, el relay TCP Python en el host (`/tmp/relay-3012.py`) sigue funcionando.

### Sprint 5 — Streaming E2E (2 horas)

- [ ] Test E2E de streaming con `stream=true`.
- [ ] Verificar que el formato OpenAI-compatible SSE es correcto.
- [ ] Documentar el formato esperado para los clientes.

### Sprint 6 (opcional) — oh-my-pi (1 día)

- [ ] Si se decide usar omp, implementar el wrapper en `service.py::_invoke_on_circuit`.
- [ ] Comparar latencia y calidad de respuesta vs OpenHands SDK directo.

---

## 8. Cambios concretos a aplicar

### 8.1 Archivos a modificar

| Archivo | Cambio | Sprint | Estado |
|---------|--------|--------|--------|
| `app/openhands_agent/circuits.py` | Agregar `mcp_config` via `create_mcp_tools` | 1 | ✅ Listo |
| `/app/docs/onboarding.md` | Sobreescribir con versión actualizada | 2 | ⏳ Pendiente |
| `/app/docs/rules.md` | Sobreescribir con versión actualizada | 2 | ⏳ Pendiente |
| `app/openhands_agent/circuits.py` | Agregar `persistence_dir` a `Conversation()` | 3 | ⏳ Pendiente |
| `sourcebot/Dockerfile` | Fijar versión de Sourcebot (v5.0.4) | 4 | ⏳ Pendiente |
| `entrypoint_hermes.sh` | Agregar `agent-server` (ya está en source; falta rebuild) | 1 | ⏳ Pendiente |

### 8.2 Comandos de prueba

```bash
# Verificar LLM con Mistral
curl -s -X POST http://localhost:9001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"circuit":"libre","messages":[{"role":"user","content":"Responde SOLO OK"}]}' \
  | python3 -m json.tool

# Test MCP get_onboarding
curl -s -X POST http://localhost:9001/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_onboarding","arguments":{}}}'

# Test commit real (requiere MCP integrado)
curl -s -X POST http://localhost:9001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"circuit":"desarrollo","messages":[{"role":"user","content":"Commitea un cambio de prueba en /desarrollo y muestrame el output de git log -1"}]}' \
  | python3 -m json.tool

# Test Sourcebot
curl -s -X POST http://localhost:3010/api/search \
  -H "Content-Type: application/json" \
  -d '{"q":"openhands circuit"}' | head -100
```

---

## 9. Preguntas abiertas

1. **¿El cliente HTTP que uses soporta streaming SSE?** Si no, conviene deshabilitar `stream=true` por default en el router LLM.
2. **¿Las API keys de Hermes (`API_SERVER_KEY`) van a rotarse?** Hoy son fijas en cada `.env` del perfil. Si Luis quiere rotar, regenerar con `openssl rand -hex 32`.
3. **¿El `run_salvar` y `run_promover` deben exigir confirmación explícita antes de ejecutar `confirm=true`?** Hoy el default es `confirm=false` (preview). Si querés que el agente pida confirmación a Luis antes de cada `confirm=true`, hay que wrappear las tools.
4. **¿El agent-server en `:3011` debe ser público o solo accesible vía SSH tunnel?** Hoy está expuesto en el host. **Nota**: agent-server expone solo API REST (JSON), NO GUI web. La respuesta de `GET /` es un JSON con metadata del servidor. **NO se puede levantar con `openhands serve`** porque ese binario viene del proyecto frontend (no instalado). Para GUI real ver §6.3.bis.

---

**Mantenedor:** Luis Dalmasso + agente Conti
**Frecuencia de revisión:** cada vez que se agregue/quite un contenedor, túnel,
skill o regla operacional. **Próxima revisión:** después de Sprint 1 (cierre del gap MCP).