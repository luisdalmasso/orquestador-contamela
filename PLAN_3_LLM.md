# PLAN_3_LLM.md — Plan Integrado OpenHands + Hotfix Bidireccional + oh-my-pi

> **Estado:** v3.2 — Plan único vigente (reemplaza a `PLAN_2_LLM.md`).
> **Reemplazo completo:** este documento NO es un diff sobre `PLAN_2`. Lo
> unifica, lo actualiza al 30/jun/2026, e incorpora:
>   - flujo bidireccional main→develop (hotfix sync)
>   - Sprint 1.5: categorías MCP + code_edit tools
>   - **Sprint 4 (30/jun)**: oh-my-pi como agent runtime alternativo (vía `CONTI_USE_OMP_AGENT=true`)
> **Mantenedor:** Luis Dalmasso + agente Conti.
> **Frecuencia de revisión:** cada vez que se agregue/quite contenedor,
> túnel, skill o regla operacional. **Próxima revisión:** después de cerrar
> los pendientes §15.quater (Tool bridging + Ponytail hooks).

---

## 0. Estado actual del contenedor (30/jun/2026, ~19:25 ART)

### Servicios corriendo en `conti-backend`

| Puerto host | Servicio | Estado |
|-------------|----------|--------|
| `:9001` | LLM FastAPI emulado (`/v1/chat/completions` OpenAI-compatible) | ✅ UP |
| `:7891` | **`conti-omp`** (oh-my-pi `--mode rpc` + socat TCP↔stdio) | ✅ UP + healthy |
| `:3010` | Sourcebot v5.0.4 (RAG sobre 3 repos) | ✅ UP |
| `:3011` | OpenHands Agent Server (API REST) | ✅ UP |
| `:3012` | OpenHands Agent Canvas (GUI Next.js) | ✅ UP |
| `:3013` | OpenHands CLI textual embebido en web | ✅ UP |
| `:8642`, `:8766-8770`, `:18791`, `:9119` | Hermes API servers + dashboard | ✅ UP |

### Containers activos (`docker ps`)

| Container | Image | Status | Rol |
|-----------|-------|--------|-----|
| `conti-backend` | `conti-backend-conti-backend` | Up + healthy | FastAPI + MCP + Hermes |
| `conti-omp` | `conti-omp:v16.2.9` | Up + healthy | oh-my-pi agent runtime (Sprint 4) |
| `conti-sourcebot` | `conti-sourcebot:latest` | Up 6 days | RAG sobre código |

### Configuración LLM activo (Mistral)

```yaml
model: mistral/mistral-small-latest
base_url: https://api.mistral.ai/v1
api_key: KkwZJdkcmtP3zKYRdOhyHltpxJxUarna  # en .env y docker-compose
# Provider alternativo (cambiar sin rebuild):
# OMP_MODEL=anthropic/claude-sonnet-4.5 OMP_API_KEY=sk-ant-... docker compose up -d conti-omp
```

### Repos como bind-mounts

| Path contenedor | Repo | Rama activa | Uso |
|-----------------|------|-------------|-----|
| `/desarrollo` | contamela-stack (dev) | `develop` | flujo normal |
| `/compose` | contamela-stack (prod) | `main` | hotfix + lectura pasiva |
| `/contenedores/conti-backend` | orquestrador-contamela | `main` | devops backend (solo main) |
| `/home/nanobot` | (no es repo) | — | HOME persistente del agente |

### Imágenes Docker (Sprint 4 finalizado)

| Imagen | Tamaño | Notas |
|--------|--------|-------|
| `conti-backend:latest` | ~25 GB | OpenHands SDK + oh-my-pi + vendor/ponytail + omp_client.py |
| `conti-omp-base:v16.2.9` | ~4.4 GB | Dockerfile oficial upstream (can1357/oh-my-pi) sin modificar |
| `conti-omp:v16.2.9` | ~4.4 GB | Thin layer sobre conti-omp-base: instala socat + entrypoint.sh |
| `conti-sourcebot:latest` | v5.0.4 | indexa `/desarrollo`, `/compose`, `/contenedores/conti-backend` |

### Vendor (submódulos locales)

| Vendor | Estado |
|--------|--------|
| `vendor/OpenHands` | ✅ clonado, integrado (runtime legacy con `CONTI_USE_OMP_AGENT=false`) |
| `vendor/oh-my-pi` | ✅ clonado, **integrado** (runtime nuevo con `CONTI_USE_OMP_AGENT=true`) |
| `vendor/ponytail` | ✅ clonado (rules-only: ~3 KB `AGENTS.md`) |

### Feature flag activo: `CONTI_USE_OMP_AGENT`

```bash
# Default: false (OpenHands SDK legacy)
docker compose -f docker-compose.conti.yml up -d conti-backend

# Sprint 4: true (oh-my-pi vía conti-omp:7891)
CONTI_USE_OMP_AGENT=true docker compose -f docker-compose.conti.yml up -d conti-backend
```

Validado E2E: `POST /v1/chat/completions` con `runtime: "omp"` en la respuesta.

---

## 1. Resumen ejecutivo

El LLM emulado (`conti-backend:9001/v1/chat/completions`) está operativo y
atendido por el stack OpenHands (NO redirige más a Hermes `:8767`).

Implementa:

- **4 circuitos independientes** (`desarrollo`, `produccion`, `backend`,
  `libre`) con workspaces, tools y ramas git específicas.
- **Detección automática de circuito** por keywords del prompt + override
  explícito `payload.circuit`.
- **Stack OpenHands SDK v1.29** + Mistral (`mistral-small-latest`).
- **Sourcebot** v5.0.4 como RAG sobre los 3 repos bind-mounted.
- **Ponytail** para trazabilidad (`/app/logs/ponytail/trace-*.json`).
- **Router LLM desacoplado** de Hermes (`/v1/chat/completions` ya no es
  proxy a `:8767`).
- **MCP tools integradas** en el loop del agente vía `create_mcp_tools`
  (Opción A de §6 de PLAN_2, ya implementada en `circuits.py`).
- **🆕 Hotfix sync** `main → develop`: nuevo `run_hotfix_sync` que commitea
  en `/compose` (main) y sincroniza `/desarrollo` (develop). Cierra el gap
  histórico de no tener flujo bidireccional.

**Cambios estructurales nuevos (vs PLAN_2):**

1. `LocalGitOps` extiende con `target_branch` + `force_branch` para
   destrabar los commits en `main` (era el bug del check duro en línea
   194 de `git_tools.py` original).
2. `CircuitConfig` extiende con `git_action_target` y `git_action_options`
   para que el backend y el hotfix sean ciudadanos de primera.
3. `entrypoint_hermes.sh` arranca **tres** procesos OpenHands en paralelo:
   `agent-server` (`:3000`), `agent-canvas` (`:3012`) y `openhands web`
   (`:3001`, CLI textual embebido).
4. `docker-compose.conti.yml` agrega `3013:3001` y bind-mount
   `/contenedores/conti-backend:/contenedores/conti-backend`.

**Pendientes críticos (consolidados de PLAN_2 + nuevos):**

- [ ] Implementar `run_hotfix_sync` + refactor de `LocalGitOps` (Sprint 1)
- [ ] Aplicar los 3 fixes del `docker-compose.conti.yml` (Sprint 0, hoy)
- [ ] Añadir `openhands web` al `entrypoint_hermes.sh` (Sprint 0, hoy)
- [ ] Tests E2E de los 4 flujos git (Sprint 1)
- [ ] Persistir historial de conversaciones entre reinicios (Sprint 2)
- [ ] Actualizar `docs/rules.md` y `docs/onboarding.md` con las 4 circuitos
      + reglas del hotfix (Sprint 2)
- [ ] Resolver bug de Next.js Server Actions en Sourcebot UI (Sprint 3)
- [ ] Activar oh-my-pi (`omp_rpc`) — opcional (Sprint 4)
- [ ] Streaming E2E con Mistral (Sprint 5)

---

## 2. Estado actual de los componentes

### 2.1 Stack verificado funcionando

| Componente | Puerto/URL | Estado | Verificado |
|------------|-----------|--------|------------|
| LLM FastAPI (Mistral) | `:9001` | ✅ UP | `POST /v1/chat/completions` retorna `"OK"` con `circuit: libre` |
| OpenHands Agent Server (GUI REST) | `:3011` | ✅ UP | 15 tools vía `/api/tools` (más MCP) |
| OpenHands Agent Canvas (Next.js) | `:3012` | ✅ UP | splash screen oficial verificado |
| OpenHands CLI textual web | `:3013 → :3001` | ⏳ Sprint 0 | falta entrypoint |
| Sourcebot | `:3010` | ⚠️ UP con bugs | API search OK; UI Next.js con Server Actions rotas |
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
| `openhands-tools` | 1.29.0 | ✅ Instalado | `terminal`, `file_editor`, `task_tracker` |
| `openhands-agent-server` | 1.29.0 | ✅ Instalado | REST en `:3000` dentro del contenedor |
| `agent-canvas` (npm) | (latest) | ✅ Instalado | GUI Next.js oficial en `:3012` |
| `openhands` CLI | (uv tool) | ⏳ Sprint 0 | instalar `uv tool install openhands` |
| `omp-rpc` (oh-my-pi) | 0.94 | ⚠️ Instalado, **NO se invoca en el código actual** (código muerto: solo import + flag). Ver §5.1 para arquitectura. Queda como Sprint 4 opcional si se decide reemplazar OpenHands SDK como agent runtime. |
| `Sourcebot` | v5.0.4 | ⚠️ funciona con bugs UI | backend OK |
| `ponytail` | (rules-only) | ✅ Cargado | `vendor/ponytail/AGENTS.md` (~3 KB) |
| **code_edit_tools** (nuevo Sprint 1.5) | - | ✅ Implementado | `validate_python_syntax`, `run_pytest`, `detect_circuit_from_path`, `cross_repo_search` |

### 2.4 Tres formas de inspeccionar el agente (interfaz humana)

| Interfaz | Puerto host | Interno | Notas |
|----------|-------------|---------|-------|
| API REST del agente | `:3011` | `:3000` | `agent-server`, JSON |
| GUI web oficial (Canvas) | `:3012` | `:3012` | Next.js, completa |
| CLI textual embebido en web | `:3013` | `:3001` | `openhands web`, terminal-style |

Los tres coexisten y arrancan en paralelo desde `entrypoint_hermes.sh`.

---

## 3. Flujo end-to-end completo

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Cliente (Kilocode IDE / VSCode / curl / Chainlit / OpenHands Canvas)         │
│ POST /v1/chat/completions con `circuit`: "desarrollo"|"produccion"|...        │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 1. app/llm_emulation/router.py                                               │
│    • Recibe body OpenAI-compatible                                           │
│    • NO redirige a Hermes :8767 (regla PLAN_LLM.MD v4)                      │
│    • Llama directamente a: openhands_service.run_task(body)                  │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 2. app/openhands_agent/service.py::OpenHandsService.run_task                 │
│                                                                              │
│    a) Detección de circuito:                                                 │
│       force = payload.get("circuit")                                         │
│       circuit_id = detect_circuit(user_prompt, force=force)                  │
│       Prioridad: libre < desarrollo < produccion < backend                   │
│                                                                              │
│    b) Ponytail context manager (PonytailTrace):                              │
│       with PonytailTrace(task_name, payload={"_circuit": id}) as t:          │
│           t._log("circuit_selected", {id, workspace, branch})                │
│                                                                              │
│    c) Sourcebot (RAG sobre código):                                          │
│       sourcebot_hits = _sourcebot_search(user_prompt)  → top-5 hits          │
│                                                                              │
│    d) Construcción del prompt con circuit-aware rules:                       │
│       final_prompt = _build_circuit_prompt(                                  │
│           user_prompt, sourcebot_hits, circuit_cfg                           │
│       )                                                                      │
│       Inyecta en orden:                                                      │
│         1) Ponytail AGENTS.md (identidad + reglas globales)                  │
│         2) Reglas del circuito (qué puede / qué no puede)                   │
│         3) Lista de tools disponibles en este circuito                       │
│         4) Code Context (Sourcebot hits)                                     │
│         5) User Task                                                         │
│                                                                              │
│    e) Obtener/crear conversación persistente:                                │
│       conv = circuit_manager.get_or_create(circuit_id)                       │
│                                                                              │
│    f) Invocar OpenHands SDK en el circuito:                                  │
│       conv.send_message(final_prompt)                                       │
│       conv.run()  ← bloquea hasta FinishAction                               │
│                                                                              │
│    g) Extracción del último evento del agente                                │
│                                                                              │
│    h) Cerrar traza Ponytail → persist JSON en /app/logs/ponytail/            │
│                                                                              │
│    i) Devolver OpenAI-compatible con campo extra `circuit`:                  │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 3. app/openhands_agent/circuits.py::CircuitManager (4 conversaciones)        │
│                                                                              │
│    _build_conversation(cfg):                                                 │
│      1. register_default_tools() → terminal, file_editor, task_tracker       │
│      2. LLM(model, api_key, base_url)  # selección por base_url              │
│      3. Agent(llm, tools=[Tool(name=t) for t in cfg.allowed_tools_native])   │
│      4. (opcional) MCP tools via create_mcp_tools() si hay categorías        │
│      5. LocalWorkspace(working_dir=cfg.workspace_dir)                        │
│      6. Conversation(agent, workspace)  # persistente                        │
│                                                                              │
│    Singleton: self._conversations[circuit_id]                                │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 4. OpenHands SDK LocalConversation (loop agente-tool)                        │
│    Loop: prompt → LLM call → tool call → observation → ... → FinishAction    │
│    LLM Mistral recibe prompt, decide tools, ejecuta tool, repite.            │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 5. MCP tools — Gateway JSON-RPC en FastAPI :9001/mcp                         │
│    64 tools, descubiertas vía SDK create_mcp_tools (loopback HTTP).           │
│    Categorías: gitops (8), odoo (21), rag (10+), stack (3),                  │
│                filesystem (7), bootstrap (5), documents (8), sheets (3)      │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 6. Respuesta OpenAI-compatible + circuit tag                                │
│    { "id": "...", "model": "openhands-agent-v1", "circuit": "...",          │
│      "choices": [{"message": {"role": "assistant", "content": "..."}}] }    │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Los 4 circuitos — detalle completo

### 4.1 Tabla resumen (actualizada con `git_action_target` + categorías MCP)

| ID | Workspace | Branch activa | git_action | git_action_target | git_action_options | MCP cats (filtrado real) |
|----|-----------|---------------|------------|-------------------|---------------------|----------|
| `desarrollo` | `/desarrollo` (RW) | `develop` | `run_salvar` | `develop` | — | todas (10) |
| `produccion` | `/compose` (RW solo git) + `/desarrollo` (operativa) | `main` en /compose, `develop` en /desarrollo | `run_promover` | `develop` | `run_hotfix_sync` | todas (10) |
| `backend` | `/contenedores/conti-backend` (RW) | `main` | `run_salvar` | `main` | — | todas (10) |
| `libre` | `/tmp/free-agent` | n/a | `none` | — | — | bootstrap, rag, odoo, documents, sheets, catolico, filesystem (7, **sin gitops/stack/code_edit**) |

**Sprint 1.5 — categorías MCP**: ver §14. Antes el filtro era decorativo;
ahora el `_build_conversation` consulta el registry y filtra mcp_tools
por nombre según `cfg.allowed_mcp_categories`.

### 4.2 Prompt inyectado por circuito (`_build_circuit_prompt`)

El prompt final se compone de **5 secciones concatenadas**:

```python
final_prompt = "\n\n---\n\n".join([
    PONYTAIL_RULES,                                    # ~3 KB, identidad + reglas globales
    f"# Circuit: {cfg.id}\n{cfg.description}",         # reglas del circuito
    _circuit_tool_list(cfg),                           # tools disponibles
    code_context_section,                              # Sourcebot hits
    f"# User Task\n{user_prompt}",                     # prompt del usuario
])
```

### 4.3 Reglas por circuito (texto completo, actualizado)

#### 🟢 `desarrollo` — DevOps en rama develop

```
Workspace: /desarrollo (RW bind-mount)
Branch activa: develop
Git action permitida: run_salvar (preview) → target = develop

Reglas:
1. Puedo commitear y pushear a develop via run_salvar (preview).
2. NO promuevo a main. NO despliego.
3. Cambios de código → commiteo directo en /desarrollo (rama develop).
```

#### 🟡 `produccion` — Promoción a main + hotfix sync

```
Workspace: /compose (RW solo git) + /desarrollo (RW operativa)
Branch activa: develop en /desarrollo (donde corren las ops)
Git action permitida: run_promover (preview) → develop→main+push
Git action adicional: run_hotfix_sync (preview) → main→develop

Reglas:
1. Promuevo develop→main via run_promover (merge --no-ff + push main).
2. Después de una promoción exitosa, /compose se actualiza via git pull
   que corre dentro de bash /compose/3-despliegue.sh (solo Luis).
3. NO corro 3-despliegue.sh ni docker compose -f producion.yml up -d.
   Solo Luis puede deployar.
4. /compose es RW SOLO para git. Cambios de código en producción
   normalmente van por el flujo develop→main.
5. Si Luis modificó archivos en /compose directamente (hotfix en main),
   puedo sincronizarlos hacia /desarrollo (develop) usando run_hotfix_sync
   (preview). Esto evita que develop quede desfasado.
6. Si Luis modificó archivos en /compose directamente, avisar del riesgo
   antes de cualquier operación (reset --hard en 3-despliegue.sh podría
   borrarlos si todavía no están commiteados).
```

#### 🔵 `backend` — orquestador-contamela (solo main)

```
Workspace: /contenedores/conti-backend (RW bind-mount, REQUERIDO)
Branch activa: main
Git action permitida: run_salvar (preview) → target = main

Reglas:
1. Commit + push directo a main via run_salvar(force_branch="main").
   Este repo solo tiene main; no hay flujo develop↔main.
2. Sin gatekeeper de promoción (no hay develop que promover).
3. run_hotfix_sync NO aplica (no hay develop que sincronizar).
4. Las mismas reglas de vida o muerte que desarrollo.
```

#### ⚪ `libre` — Conversacional, sin git

```
Workspace: /tmp/free-agent
Git action: none

Reglas:
1. SIN acceso a repos git. No tools nativas.
2. Solo MCP tools de RAG/consulta.
3. Si la tarea requiere fuentes externas no bind-mounted: pedir credenciales
   a Luis explícitamente.
4. Si Luis pasa una ruta del host (ej: /mnt/nuevo-repo), trabajar ahí sin
   tocar git.
```

### 4.4 Keywords de detección (`CIRCUIT_KEYWORDS`)

Orden importa: lo más específico primero.

```python
CIRCUIT_KEYWORDS = [
    ("produccion", (
        "/compose", "produccion", "producción", "rama main", "promover",
        "promocion", "promoción", "merge a main", "deploy", "desplegar",
        "despliegue", "en producción", "en produccion", "a main",
        # NUEVO hotfix:
        "hotfix", "sync main", "main a develop", "sincronizar main",
        "sincronizá main", "pull de main",
    )),
    ("backend", (
        "/contenedores/conti-backend", "orquestador-contamela",
        "conti-backend", "el backend", "este repo", "orquestador",
    )),
    ("desarrollo", (
        "/desarrollo", "rama develop", "rama dev", "desarrollo",
        "en desa", "en dev", "salvar", "commitea", "commit",
        "develop branch",
    )),
]
# default si no hay match: "libre"
```

---

## 5. Roles por componente

| Componente | Cuándo entra | Qué hace |
|------------|--------------|----------|
| **Ponytail** | Envuelve TODA `run_task` (`with PonytailTrace(...)`) | Carga `vendor/ponytail/AGENTS.md`. Persiste trace JSON en `/app/logs/ponytail/trace-<ts>.json`. |
| **Sourcebot** | Después de detección de circuito, antes de OpenHands | Busca el prompt en los 3 repos indexados. Devuelve top-5 hits. Inyecta como `# Code Context`. |
| **oh-my-pi (omp-rpc)** | **NO se invoca en el flujo actual** (código muerto). Ver §5.1. | Cliente Python `RpcClient` que habla JSONL con binario Rust `omp`. Instalado en `/usr/local/lib/python3.12/site-packages/omp_rpc/`. Pendiente Sprint 4 si se decide activarlo. |
| **OpenHands SDK** | **Agent runtime activo** en `run_task` (`Conversation.run()`) | Recibe prompt enriquecido, decide qué tools invocar, itera hasta `FinishAction`. Es EL agente hoy. |
| **MCP tools** | Vía `create_mcp_tools` en `_build_conversation` | 64 tools descubiertas via JSON-RPC en `:9001/mcp`. Integradas en el loop. |
| **Hermes (legacy)** | NO entra al flujo LLM | Sigue activo en `:8766-8770` para omnicanalidad, Chainlit, UI. No es tocado por `run_task`. |

### 5.1 Aclaración arquitectónica: OpenHands SDK vs oh-my-pi

**Estado real del código (verificado el 30/jun/2026)**:

- **El agent runtime activo es OpenHands SDK**. En `app/openhands_agent/service.py:438`:
  ```python
  def _invoke_on_circuit(self, conv: Any, prompt: str) -> str:
      conv.send_message(prompt)
      conv.run()  # ← este es el agent loop real
  ```
  `Conversation` y `Agent` se construyen en `circuits.py:_build_conversation` (líneas 365-372) con `LLM(llm)`, `Agent(llm, tools)` y `LocalWorkspace`.

- **oh-my-pi NO está conectado al flujo Python**. Su única aparición en código es en `service.py:48-55`:
  ```python
  try:
      import omp_rpc
      OMP_AVAILABLE = True
  except Exception:
      OMP_AVAILABLE = False
  ```
  Es un import + flag. `OMP_AVAILABLE` se loggea en `backend_status()` pero nunca se usa para branching.

- **oh-my-pi SÍ es un agent runtime completo por diseño** (en su propio repo):
  - `vendor/oh-my-pi/AGENTS.md` declara:
    - `packages/coding-agent` = CLI application
    - `packages/agent` = "Agent runtime with tool calling and state management"
  - `vendor/oh-my-pi/python/omp-rpc/README.md`: "Typed Python bindings for the `omp --mode rpc` protocol used by the coding agent."
  - Si se invocara `omp --mode rpc` desde Python vía `RpcClient`, **oh-my-pi pasaría a ser el agent runtime** y OpenHands SDK quedaría como proveedor de LLM client únicamente.

**Por qué NO se usa oh-my-pi como agent hoy**:

1. PLAN_2 §3 decía que oh-my-pi era "Cliente LLM Optimizado" (cliente para la API Mistral), no el agent. Esa intención nunca se materializó en código.
2. OpenHands SDK ya cumple el rol de agent + LLM client en un solo paquete, sin necesidad de un subprocess adicional.
3. Activar oh-my-pi como agent implicaría:
   - Lanzar `omp --mode rpc` como subprocess desde uvicorn.
   - Mantener un `RpcClient` por circuito (4 subprocess simultáneos).
   - Mapear MCP tools + circuit rules al formato JSON Schema de `host_tool()`.
   - Reescribir `_invoke_on_circuit` para usar `prompt_and_wait()` en lugar de `conv.run()`.

**Decisión actual**: OpenHands SDK es el agent runtime. Sprint 4 (opcional) puede reevaluar si oh-my-pi aporta valor (streaming token-by-token, configuración de modelo en runtime via omp, modelos custom del catálogo `packages/catalog`).

**Si en algún momento se quiere activar**: el punto de entrada es `app/openhands_agent/service.py::_invoke_on_circuit`. Reemplazar el bloque `conv.send_message() + conv.run()` por un `RpcClient.prompt_and_wait()` con el system prompt inyectado vía `append_system_prompt=final_prompt`.

---

## 6. Hard checks de git_tools.py — issue de la línea 194

### 6.1 El problema original

`app/tools/git_tools.py` línea 194:

```python
if status.get("branch") != self.develop_branch:
    return {"success": False, "error": f"run_salvar requiere estar en la rama {self.develop_branch}"}
```

Este check es **duro**, no decorativo. Idem línea 270 en `run_promover`.

### 6.2 Impacto en los 4 flujos

| Flujo | Working tree | Branch | Bloqueado por línea 194 | Estado pre-rediseño |
|-------|--------------|--------|-------------------------|---------------------|
| 1. dev → origin/develop | `/desarrollo` | `develop` | NO | ✅ funciona |
| 2. promote develop → main | `/desarrollo` | `develop` arranca | NO | ✅ funciona |
| 3. hotfix main → develop sync | `/compose` (commit) + `/desarrollo` (merge) | `main` en /compose | **SÍ** | ❌ bloqueado |
| 4. commit directo a main (orquestador) | `/contenedores/conti-backend` | `main` | **SÍ** | ❌ bloqueado |

### 6.3 Rediseño: `target_branch` + `force_branch`

```python
class LocalGitOps:
    def __init__(self, repo_path, remote="origin",
                 develop_branch="develop", main_branch="main",
                 target_branch: str | None = None):
        ...
        self.target_branch = target_branch or develop_branch

    def run_salvar(self, confirm=False, summary="", force_branch: str | None = None):
        expected = force_branch or self.target_branch
        ...
        if status.get("branch") != expected:
            return {"success": False, "error": f"run_salvar requiere estar en {expected}"}
        ...
        push_result = self._run_git("push", self.remote, expected)
```

Esto destraba:

- Flujo 4 (backend): `LocalGitOps(target_branch="main")` + `run_salvar(force_branch="main")`.
- Flujo 3 (hotfix): se compone con dos `LocalGitOps`, uno por working tree.

### 6.4 Implicancia arquitectural: `run_promover` opera en `/desarrollo`, no en `/compose`

`run_promover` hace el merge dance **dentro del working tree donde se
invoca** (default `/desarrollo` vía `config.paths.development_repo`):

```python
# git_tools.py:284-305
original_branch = current_branch            # develop
checkout_main = self._checkout_main_branch() # checks out main IN /desarrollo
merge_result = self._run_git("merge", "--no-ff", self.develop_branch, ...)  # merge IN /desarrollo
push_result = self._run_git("push", self.remote, self.main_branch)          # push main
self._run_git("checkout", original_branch)  # vuelve a develop
```

**Implicancia**: si `/desarrollo` y `/compose` son clones separados del
mismo `origin`, después de `run_promover` el push a `origin/main` se hizo,
pero el working tree de `/compose` queda desfasado hasta que alguien corra
`git pull` ahí (lo hace `bash /compose/3-despliegue.sh`).

El `circuit: produccion` **NO opera git directamente sobre `/compose`** —
opera sobre `/desarrollo` (donde está instanciado `LocalGitOps` por default)
y deja que el deploy step haga `git pull` en `/compose`.

`/compose` queda como checkout pasivo de `main` que el agente:

- puede `git pull` (vía `terminal` nativa) si se lo pedís.
- puede commitear en main si es un hotfix (vía `run_salvar(force_branch="main")`).

---

## 7. 🆕 Flujo Hotfix Sync: main → develop

### 7.1 Motivación

`/compose` ahora es RW para permitir ediciones in-place de archivos
(caso hotfix / bug urgente). Pero cada commit directo en `main` deja
a `develop` desfasado. Necesitamos una **tercera tool git** (paralela
a `run_salvar` y `run_promover`) que cierre el ciclo: `main → develop`.

### 7.2 Decisión de diseño

**Opción elegida:** extender el circuito `produccion` con la tool nueva
`run_hotfix_sync` (en lugar de crear un circuito `hotfix` aparte).

Razones:

- El circuito `produccion` ya tiene `/compose` como workspace y las
  keywords de producción.
- Es una operación sobre producción (origen `main`).
- Mantiene 4 circuitos limpios.

### 7.3 Nueva tool: `run_hotfix_sync`

| Campo | Valor |
|-------|-------|
| Nombre | `run_hotfix_sync` |
| Categoría MCP | `gitops` |
| Default | `confirm=false` (preview) |
| Parámetros | `summary: str`, `confirm: bool = False` |

**Algoritmo:**

```
1. cd /compose && git status
   - falla si hay cambios uncommitted que NO son del hotfix
2. cd /compose && git log origin/main..HEAD --oneline
   - lista commits que se promueven a origin/main
3. cd /compose && git push origin main              (si confirm=True)
4. cd /desarrollo && git fetch origin
5. cd /desarrollo && git checkout develop
6. cd /desarrollo && git merge origin/main --no-ff -m "hotfix: <summary>"
   - si hay conflictos → abortar, devolver reporte, NO forzar
7. cd /desarrollo && git push origin develop         (si confirm=True)
8. Devuelve log de cada paso con exit codes
```

**Implementación en `git_tools.py`:**

```python
def run_hotfix_sync(self, confirm=False, summary=""):
    compose_ops = LocalGitOps(
        repo_path="/compose",
        remote=self.remote,
        develop_branch=self.develop_branch,
        main_branch=self.main_branch,
        target_branch=self.main_branch,   # commit en main
    )
    desarrollo_ops = LocalGitOps(
        repo_path="/desarrollo",
        remote=self.remote,
        develop_branch=self.develop_branch,
        main_branch=self.main_branch,
        target_branch=self.develop_branch,  # default develop
    )

    preview = {
        "step_1": compose_ops.run_salvar(confirm=False, summary=summary,
                                          force_branch=self.main_branch),
        "step_2_preview": desarrollo_ops._run_git("log", "--oneline",
                                                   f"origin/{self.main_branch}..HEAD"),
        "step_3_preview": desarrollo_ops._run_git("diff", "--stat",
                                                   f"origin/{self.main_branch}..HEAD"),
    }
    if not confirm:
        return preview

    # Step 1: commit+push main en /compose
    r1 = compose_ops.run_salvar(confirm=True, summary=summary,
                                 force_branch=self.main_branch)
    if not r1["success"]:
        return {"success": False, "step": "compose_commit", **r1}

    # Step 2: merge main → develop en /desarrollo
    r2 = desarrollo_ops._run_git("fetch", "origin")
    if not r2["success"]:
        return {"success": False, "step": "fetch", "error": r2["stderr"]}

    merge_msg = f"hotfix: {self._sanitize_summary(summary) or 'sync main → develop'}"
    r3 = desarrollo_ops._run_git("merge", "--no-ff",
                                  f"origin/{self.main_branch}",
                                  "-m", merge_msg)
    if not r3["success"]:
        desarrollo_ops._run_git("merge", "--abort")
        return {"success": False, "step": "merge", "error": r3["stderr"],
                "merge_message": merge_msg}

    r4 = desarrollo_ops._run_git("push", "origin", self.develop_branch)
    return {
        "success": r4["success"],
        "step": "all",
        "compose_commit_hash": r1.get("commit_hash"),
        "develop_merge_result": r3,
        "develop_push_result": r4,
    }
```

### 7.4 Reglas nuevas globales

```markdown
14. El flujo normal sigue siendo develop → main (run_salvar → run_promover).
    El flujo inverso main → develop (run_hotfix_sync) es SOLO para casos
    donde Luis editó archivos directamente en /compose.
15. NUNCA correr run_hotfix_sync si /desarrollo tiene commits locales no
    pusheados que conflictúan con main. El merge aborta y reporta.
16. Si 3-despliegue.sh corre entre el push a main y el merge a develop,
    no hay problema (los commits ya están en origin/main). Si corre ANTES
    del push a main, los cambios uncommitted se pierden.
    Orden obligatorio: commit+push main → THEN run_hotfix_sync → THEN deploy.
17. Si /compose tiene cambios uncommitted mezclados con el hotfix, el
    agente debe pedir commit explícito antes de continuar.
```

### 7.5 Riesgos documentados

| Riesgo | Mitigación |
|--------|------------|
| Merge conflict en /desarrollo | `git merge --abort` + reporte. NO forzar. |
| Cambios uncommitted mezclados en /compose | `git status` falla el flujo si hay uncommitted. |
| Orden vs deploy | Regla 16: commit+push primero, sync después, deploy al final. |
| Idempotencia | Si main ya está en develop, merge es no-op. Detectar con `git log origin/main..develop --oneline` vacío. |

---

## 8. CLI textual + Canvas coexistiendo

### 8.1 Por qué los tres

| Puerto host | Servicio | Caso de uso |
|-------------|----------|-------------|
| `:3011` | agent-server (REST API) | Integración programática con IDEs, scripts, Chainlit |
| `:3012` | agent-canvas (Next.js GUI oficial) | Inspección visual completa del agente (events, settings, etc.) |
| `:3013` | openhands web (CLI textual Textual) | Inspección estilo terminal embebido en HTML |

Las tres interfaces son **read-only respecto al agente lógico**: el
agente real vive en el `LocalConversation` de OpenHands SDK. Las GUIs
son frontends distintos sobre el mismo backend.

### 8.2 Cambios al `entrypoint_hermes.sh`

Bloque nuevo a agregar (después de `agent-canvas`):

```bash
# ── OpenHands CLI textual embebido en web (frontend Textual) ─────────
# Sirve la GUI textual oficial de OpenHands vía `openhands web`.
# Diferencia con agent-canvas: agent-canvas es Next.js completa;
# openhands web es un frontend estilo terminal servido por aiohttp.
# No necesita Docker daemon (corre in-process con el CLI).
echo "💻 OpenHands CLI Web en :3001"
OPENHANDS_SUPPRESS_BANNER=1 nohup uv run --with openhands openhands web \
  --host 0.0.0.0 --port 3001 \
  > "$LOG_DIR/openhands_web.log" 2>&1 &
OPENHANDS_WEB_PID=$!
```

### 8.3 Cambios al `docker-compose.conti.yml`

```yaml
ports:
  # ... existentes ...
  - "3011:3000"   # agent-server (REST API)
  - "3012:3012"   # agent-canvas (GUI Next.js oficial)   ← CAMBIO: 3001 → 3012
  - "3013:3001"   # openhands web (CLI textual embebido)  ← NUEVO
```

Y agregar bind-mount del backend (faltaba, requerido para circuito `backend`):

```yaml
volumes:
  # ... existentes ...
  - /contenedores/conti-backend:/contenedores/conti-backend  # ← NUEVO (circuito backend)
```

### 8.4 Instalación de `openhands` CLI en el Dockerfile

```dockerfile
# Después de los `uv pip install` y `bun setup`:
RUN apt-get update && apt-get install -y --no-install-recommends socat && rm -rf /var/lib/apt/lists/*
RUN /root/.cargo/bin/uv tool install openhands --python 3.12 && \
    chmod -R a+rx /root/.local/share/uv/tools/openhands
```

---

## 9. Gaps cerrados + roadmap (consolidado)

### 9.1 ✅ Gaps cerrados

| Gap | Estado | Cómo se cerró |
|-----|--------|---------------|
| LLM emulado NO redirige a Hermes | ✅ | `app/llm_emulation/router.py` ya no proxy a `:8767` |
| OpenHands SDK integrado | ✅ | `service.py` usa `LLM`, `Agent`, `LocalConversation` |
| 4 circuitos definidos | ✅ | `circuits.py::CIRCUITS` |
| Sourcebot como RAG | ✅ | `_sourcebot_search` en `service.py` |
| Ponytail para trazabilidad | ✅ | `PonytailTrace` en `service.py`, persiste JSON |
| MCP tools en el loop del agente | ✅ | `create_mcp_tools` en `circuits.py` |
| agent-canvas GUI oficial | ✅ | entrypoint `_hermes.sh` línea 141 |
| Stack OpenHands aislado del legacy Hermes | ✅ | |

### 9.2 🆕 Gaps nuevos (vs PLAN_2)

| Gap | Sprint | Estado |
|-----|--------|--------|
| `LocalGitOps` línea 194 bloquea commits en main | 1 | ✅ cerrado en Sprint 1 |
| `run_hotfix_sync` no existe | 1 | ✅ cerrado en Sprint 1 |
| Circuito `backend` no puede commitear | 1 | ✅ cerrado en Sprint 1 |
| `docker-compose.conti.yml` puerto 3012 mal mapeado | 0 | ✅ cerrado |
| Bind-mount `/contenedores/conti-backend` falta | 0 | ✅ cerrado |
| `openhands web` no en entrypoint | 0 | ✅ cerrado |
| **Categorías MCP enum incompleto** (8 categorías usadas en circuits.py no existían) | 1.5 | ✅ cerrado en §14 |
| **Filtro MCP decorativo** (cargaba 64 tools siempre, ignoraba `allowed_mcp_categories`) | 1.5 | ✅ cerrado en §14 |
| **No había herramientas de code editing** (sin `validate_python_syntax`, `run_pytest`, etc.) | 1.5 | ✅ cerrado en §14 |
| **oh-my-pi como agent runtime alternativo** | 4 | ✅ cerrado en §15 + §15.bis |
| **conti-omp container** (socat + omp subprocess bridge) | 4 | ✅ cerrado en §15.bis |
| **OmpClient Python wrapper** (`app/openhands_agent/omp_client.py`) | 4.1 | ✅ cerrado en §15 |
| **Feature flag `CONTI_USE_OMP_AGENT`** en service.py | 4.1 | ✅ cerrado en §15 |

### 9.3 ⏳ Gaps pendientes (ordenados por prioridad — Luis 30/jun)

| # | Gap | Sprint | Acción |
|---|-----|--------|--------|
| **1** | **Tool bridging: omp no puede invocar tools custom (run_salvar, odoo_*, etc.)** | 4.2 | Registrar MCP tools como `custom_tools` en `OmpClient.__init__`. Cada tool handler hace `httpx POST :9001/mcp` (JSON-RPC loopback). Ver §15.quater. |
| **2** | **Ponytail hooks: capturar eventos del omp subprocess** | 4.3 | Hookear `omp_rpc.RpcClient.on_message_update`, `.on_tool_execution_*`, `.on_protocol_error` → persistir a `/app/logs/ponytail/`. Ver §15.quater. |
| 3 | Streaming SSE | 5 | Test con `stream=true`. Bridge de eventos omp → OpenAI SSE chunks. |
| 4 | Persistencia del historial entre reinicios | 2 | `Conversation(persistence_dir=...)` o `omp --profile persist` |
| 5 | Sourcebot UI con bug Next.js Server Actions | 3 | Hard reload + fijar versión `:v5.0.4` exacto |
| 6 | Streaming E2E con Mistral | 5 | Test con `stream=true` |
| ~~7~~ | ~~Filtros por categoría MCP~~ | post-MVP | ✅ cerrado en Sprint 1.5 |

---

## 10. Cambios concretos a aplicar (status al 30/jun)

### 10.1 Sprint 0 — fixes de compose + entrypoint ✅ CERRADO

| Archivo | Cambio | Líneas |
|---------|--------|--------|
| `docker-compose.conti.yml` | `3012:3001` → `3012:3012` | 1 |
| `docker-compose.conti.yml` | agregar `- "3013:3001"` | 1 |
| `docker-compose.conti.yml` | agregar `- /contenedores/conti-backend:/contenedores/conti-backend` | 1 |
| `entrypoint_hermes.sh` | agregar bloque `openhands web` en `:3001` | ~8 |
| `Dockerfile` | agregar `uv tool install openhands` | ~3 |

### 10.2 Sprint 1 — refactor git_tools.py + circuits.py ✅ CERRADO

| Archivo | Cambio | Líneas |
|---------|--------|--------|
| `app/tools/git_tools.py` | `target_branch` en `LocalGitOps.__init__` | ~3 |
| `app/tools/git_tools.py` | `force_branch` en `run_salvar` | ~6 |
| `app/tools/git_tools.py` | nuevo método `run_hotfix_sync` | ~50 |
| `app/tools/git_tools.py` | nueva función módulo `run_hotfix_sync(config, args)` | ~3 |
| `app/openhands_agent/circuits.py` | agregar `git_action_target` + `git_action_options` a `CircuitConfig` | ~4 |
| `app/openhands_agent/circuits.py` | actualizar `CIRCUITS["produccion"]` con `git_action_options=("run_hotfix_sync",)` | ~2 |
| `app/openhands_agent/circuits.py` | actualizar `CIRCUITS["backend"]` con `git_action_target="main"` | ~1 |
| `app/openhands_agent/circuits.py` | actualizar descripción `backend` | ~2 |
| `app/openhands_agent/circuits.py` | agregar keywords hotfix a `produccion` | ~5 |
| `app/openhands_agent/circuits.py` | actualizar `_build_conversation` para instanciar `LocalGitOps` con `target_branch` | ~5 |

### 10.2.bis Sprint 1.5 — categorías MCP + code_edit tools ✅ CERRADO

| Archivo | Cambio | Líneas |
|---------|--------|--------|
| `app/core/categories.py` | expandir enum con BOOTSTRAP/STACK/RAG/GITOPS/ODOO/DOCUMENTS/SHEETS/CATOLICO/CODE_EDIT | ~30 |
| `app/services/registry_service.py` | recategorizar 65 tools existentes (65 líneas modificadas) + registrar 4 tools nuevas | ~150 |
| `app/tools/code_edit_tools.py` (nuevo) | `validate_python_syntax`, `run_pytest`, `detect_circuit_from_path`, `cross_repo_search` | ~390 |
| `app/openhands_agent/circuits.py` | usar `mcp_categories.X` constants (en lugar de strings hardcoded) | ~12 |
| `app/openhands_agent/circuits.py` | implementar filtro real en `_build_conversation` (consulta registry por categoría) | ~15 |
| `tests/test_code_edit_tools.py` (nuevo) | 16 tests para las 4 tools nuevas | ~190 |
| `docs/onboarding.md` | reescrito: 10 categorías MCP + flujos de code editing por circuito | +90 líneas |
| `docs/rules.md` | reescrito: 27 reglas (vs 21 anteriores) + reglas de code editing | +35 líneas |

### 10.3 Sprint 4 — oh-my-pi como agent runtime alternativo ✅ CERRADO

| Archivo | Cambio | Líneas | Estado |
|---------|--------|--------|--------|
| `docker/conti-omp/Dockerfile` (nuevo) | thin layer sobre `conti-omp-base` (oficial sin modificar). Instala socat + netcat, copia entrypoint.sh. | ~60 | ✅ |
| `docker/conti-omp/entrypoint.sh` (nuevo) | script bash: install socat (idempotente), detect provider por prefijo modelo, exec `socat TCP-LISTEN:7891,fork EXEC:omp --mode=rpc ...` | ~50 | ✅ |
| `docker-compose.conti.yml` | agregar servicio `conti-omp` (single service con override entrypoint). Build-arg `OMP_VERSION`. Env vars `OMP_MODEL`, `OMP_API_KEY`, `OMP_BASE_URL`, `OMP_PROFILE`, `OMP_PLAN`. Bind-mount de los 3 repos + volúmenes `omp_home`, `omp_data`. | ~80 | ✅ |
| `app/openhands_agent/omp_client.py` (nuevo) | `OmpClient` wrapper sobre `omp_rpc.RpcClient`. Constructor con `command=["socat","-","TCP:conti-omp:7891"]` + `append_system_prompt`. Método `prompt_and_wait(user_prompt)`. `make_omp_client_for_circuit(cfg, append_system_prompt)` factory. `is_omp_enabled()` feature flag. | ~220 | ✅ |
| `app/openhands_agent/circuits.py` | `_build_omp_client(cfg)` factory. `CircuitManager` mantiene `_omp_clients: dict[str, OmpClient]` paralelo a `_conversations`. `get_or_create` decide según feature flag. `is_omp_client(circuit_id)` helper. `status()` incluye campo `runtime`. `_build_omp_system_prompt(cfg)` construye Ponytail + circuit description. | ~50 | ✅ |
| `app/openhands_agent/service.py` | `_invoke_on_circuit(runtime, final_prompt, circuit_id)` dispatcha según `isinstance(runtime, OmpClient)`. Si omp: split prompt + `prompt_and_wait(user_part)`. Si OpenHands SDK: `send_message + run` legacy. `_split_prompt` helper. | ~30 | ✅ |
| `tests/test_omp_client.py` (nuevo) | 16 tests: `__init__` (socat command, env vars, OMP_RPC_AVAILABLE), `prompt_and_wait` (con/sin system_prompt per-call), lifecycle (close, context_manager, start()). 5 tests feature flag. 3 tests `_split_prompt`. | ~280 | ✅ 16/16 passing |

### 10.4 Sprint 4.2 (PRIORITARIO 1) — Tool bridging MCP loopback ✅ CERRADO

| Archivo | Cambio | Estado |
|---------|--------|--------|
| `app/openhands_agent/tool_bridge.py` (nuevo) | `make_mcp_tool_handler(tool_name, mcp_url)` factory que crea handlers para `omp_rpc.host_tool(name, description, schema, execute)`. Cada handler hace `httpx POST :9001/mcp` con JSON-RPC. `build_custom_tools_for_circuit(cfg, registry, mcp_url)` filtra registry por `allowed_mcp_categories` y construye lista de `host_tool`. | ✅ |
| `app/openhands_agent/omp_client.py` | Parámetro `custom_tools: list \| None = None` agregado a `__init__`. Se pasa a `RpcClient(custom_tools=...)` DESPUÉS de `start()`. `make_omp_client_for_circuit` también acepta `custom_tools`. | ✅ |
| `app/openhands_agent/circuits.py` | `_build_omp_client(cfg)` ahora consulta `registry_service()`, invoca `build_custom_tools_for_circuit(cfg, registry, mcp_url)`, y pasa los custom_tools al factory. | ✅ |
| `tests/test_tool_bridge.py` (nuevo) | 8 tests: 4 del handler (JSON-RPC, error MCP, HTTP error, timeout), 4 del factory (filtro por categoría, categorías vacías, no match, args correctos de host_tool). | ✅ 8/8 passing |
| `docker/conti-omp/entrypoint.sh` | **(FIX E2E 30/jun)** Hacer `(cd /desarrollo && exec socat ...)` para forzar cwd correcto en el omp subprocess. Sin esto, omp corría en `/pi` (WORKDIR del Dockerfile oficial) y las tools built-in (bash, git status) operaban en el path equivocado, lo que rompía el flow de tool bridging — omp decidía no ejecutar run_salvar al ver "no Git repo en /pi". | ✅ |

**Validación E2E**: omp invocó `run_salvar` vía tool bridge. Commit creado en `/desarrollo` con mensaje "feat: test tool bridge e2e". Tiempo total ~73s (incluye latencia del LLM + tool calls).

**Limitaciones conocidas**:
- **`WORKDIR=/desarrollo` solo soporta el circuit `desarrollo`**. Para `produccion` (`/compose`) y `backend` (`/contenedores/conti-backend`) hace falta `cd` diferente en entrypoint.sh, lo que implica UN container conti-omp POR circuit. Esto se implementará en Sprint 5+ (múltiples containers conti-omp-desarrollo, conti-omp-produccion, etc.).

**Bugs encontrados durante Sprint 4.2** (todos corregidos):
1. **`omp subprocess cwd=/pi` (el bug que reportó Luis el 30/jun)** — `entrypoint.sh` ahora hace `cd` antes de exec socat.
2. **`Broken pipe` al llamar `set_custom_tools` antes de `start()`** — el orden en `OmpClient.__init__` ahora es: constructor → start() → set_custom_tools.</newString>

### 10.5 Sprint 4.3 (PRIORITARIO 2) — Ponytail hooks 🟡 PENDIENTE

| Archivo | Cambio |
|---------|--------|
| `app/openhands_agent/omp_client.py` | En `__init__`, registrar hooks en `self._rpc`: `on_message_update`, `on_tool_execution_start`, `on_tool_execution_end`, `on_protocol_error`, `on_listener_error`. Cada hook llama `PonytailTrace.event(container="conti-omp", event_type=..., payload=...)`. |
| `app/openhands_agent/service.py` | En `run_task`, pasar `trace` (PonytailTrace instance) al constructor de OmpClient para que los hooks tengan acceso al trace activo. |
| `docs/onboarding.md` | Documentar el formato de trace de omp (NDJSON events). |

**Ver §15.quater** para diseño detallado.

### 10.6 Sprint 5 — streaming E2E ⏳ PENDIENTE

| Acción |
|--------|
| Test con `stream=true` |
| Documentar formato OpenAI-compatible SSE |

---

## 11. Testing E2E

### 11.0 Suite implementada

**Tests pytest standalone** (`tests/test_git_tools_localops.py`, 7 tests, todos PASSING):

- `test_default_target_branch_is_develop` — default sin override.
- `test_target_branch_override_main` — circuito backend con `target_branch=main`.
- `test_run_salvar_blocks_when_branch_mismatch` — check de línea 194 sigue funcionando cuando corresponde.
- `test_run_hotfix_sync_full_flow` — happy path del hotfix sync.
- `test_run_hotfix_sync_aborts_on_dirty_compose` — abort con cambios uncommitted.
- `test_run_hotfix_sync_aborts_on_wrong_branch` — abort si /compose no está en main.
- `test_run_hotfix_sync_preview_mode` — preview sin ejecutar.

**Tests pytest code_edit_tools** (`tests/test_code_edit_tools.py`, 16 tests, todos PASSING — Sprint 1.5):

- 5 tests para `validate_python_syntax` (ok, syntax_error, missing, non_py, empty).
- 4 tests para `_circuit_for_path` (desarrollo, produccion, backend, unknown).
- 2 tests para `detect_circuit_from_path` (absolute match, unknown path).
- 2 tests para `run_pytest` (backend circuit, invalid circuit).
- 3 tests para `cross_repo_search` (finds marker, max_results, no matches).

**Tests pytest MCP layer** (`tests/test_git_tools.py`, 5 existentes + 3 nuevos):

- Existentes: `test_get_git_status_on_local_fixture_repo`, `test_get_git_log_and_pipeline_summary`, `test_diff_with_develop_returns_stat`, `test_run_salvar_preview_and_execute`, `test_run_promover_preview_and_execute`.
- Nuevos: `test_run_salvar_force_branch_main_backend_circuit`, `test_run_hotfix_sync_main_to_develop`, `test_run_hotfix_sync_aborts_on_dirty_compose`.

**Total tests Sprint 1.5**: 7 (git) + 16 (code_edit) + 8 (MCP git) = **31 tests** (todos PASSING).

**Scripts bash E2E** (`scripts/e2e/`):

- `test_flujo_1_desarrollo.sh` — flujo 1 vía HTTP al LLM.
- `test_flujo_2_promover.sh` — flujo 2 con preview + confirm.
- `test_flujo_3_hotfix_sync.sh` — flujo 3 hotfix end-to-end.
- `test_flujo_4_backend.sh` — flujo 4 commit directo a main.
- `test_3_guis.sh` — verifica HTTP 200 en :3011, :3012, :3013.
- `run_all.sh` — runner que ejecuta los 5 tests.

### 11.1 Test flujo 1 (run_salvar en /desarrollo)

### 11.1 Test flujo 1 (run_salvar en /desarrollo)

```bash
cd /desarrollo
echo "test-flujo-1" >> README.md

curl -sX POST http://localhost:9001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"circuit":"desarrollo","messages":[{"role":"user","content":"commiteá el cambio en /desarrollo/README.md con run_salvar"}]}' \
  | python3 -m json.tool

# Verificar
cd /desarrollo && git log -1 --oneline
```

### 11.2 Test flujo 2 (run_promover develop→main)

```bash
curl -sX POST http://localhost:9001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"circuit":"produccion","messages":[{"role":"user","content":"promové develop→main con run_promover (preview primero)"}]}' \
  | python3 -m json.tool

# Confirmar
curl -sX POST http://localhost:9001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"circuit":"produccion","messages":[{"role":"user","content":"confirmá la promoción con confirm=true"}]}' \
  | python3 -m json.tool
```

### 11.3 Test flujo 3 (run_hotfix_sync main→develop)

```bash
# Setup: hotfix dummy en /compose
echo "hotfix-test-$(date)" >> /compose/README.md
cd /compose && git add -A && git commit -m "hotfix: test sync flow"

# Verificar /desarrollo NO tiene el cambio
cd /desarrollo && ! grep "hotfix-test" README.md && echo "NOT YET (correcto)"

# Preview
curl -sX POST http://localhost:9001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"circuit":"produccion","messages":[{"role":"user","content":"sincronizá los cambios de /compose a /desarrollo usando run_hotfix_sync en preview"}]}' \
  | python3 -m json.tool

# Confirm
curl -sX POST http://localhost:9001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"circuit":"produccion","messages":[{"role":"user","content":"confirmá con confirm=true"}]}' \
  | python3 -m json.tool

# Verificar
cd /desarrollo && git log -1 --oneline && grep "hotfix-test" README.md && echo "SYNC OK"
```

### 11.4 Test flujo 4 (commit directo a main en orquestador)

```bash
cd /contenedores/conti-backend
echo "test-flujo-4" >> app/main.py  # o algún archivo del repo

curl -sX POST http://localhost:9001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"circuit":"backend","messages":[{"role":"user","content":"commiteá el cambio en app/main.py con run_salvar"}]}' \
  | python3 -m json.tool

# Verificar
cd /contenedores/conti-backend && git log -1 --oneline
```

### 11.5 Test de las 3 GUIs del agente

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3011/    # 200 (REST)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3012/    # 200 (canvas)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3013/    # 200 (cli web)
```

### 11.6 Test del filtro MCP por categoría (Sprint 1.5)

```python
# Verificación programática (ya cubierto por tests/test_code_edit_tools.py
# y por la lógica en circuits.py::_build_conversation).
from app.services.registry_service import registry_service
from app.openhands_agent.circuits import CIRCUITS

registry = registry_service()
for cid in ("desarrollo", "produccion", "backend", "libre"):
    cfg = CIRCUITS[cid]
    allowed = {t["name"] for t in registry.list_tools()
               if t.get("category") in cfg.allowed_mcp_categories}
    print(f"{cid}: {len(allowed)} tools permitidas")
# Esperado: desarrollo=69, produccion=69, backend=69, libre=55
```

```bash
# Verificación via /mcp/tools: contar tools y verificar nombres por categoría
curl -s http://localhost:9001/mcp/tools | python3 -c "
import json, sys
from collections import Counter
data = json.load(sys.stdin)
cats = Counter(t['category'] for t in data['tools'])
print(f'Total: {len(data[\"tools\"])}')
for c, n in sorted(cats.items(), key=lambda x: -x[1]):
    print(f'  {c}: {n}')
"
```

---

## 12. Preguntas abiertas

1. **¿El cliente HTTP soporta streaming SSE?** Si no, conviene deshabilitar
   `stream=true` por default en el router LLM.
2. **¿Las API keys de Hermes (`API_SERVER_KEY`) se van a rotar?** Hoy son
   fijas en cada `.env` del perfil.
3. **¿`run_salvar` y `run_promover` deben exigir confirmación explícita
   antes de `confirm=true`?** Hoy el default es `confirm=false` (preview).
4. **¿`run_hotfix_sync` debe pedir confirmación explícita a Luis antes de
   `confirm=true`?** Si Luis lo pide, wrappear para forzar `confirm=true`
   solo después de input del usuario.
5. **¿El agent-server en `:3011` debe ser público o solo vía SSH tunnel?**
   Hoy está expuesto en el host.

---

## 14. Sprint 1.5 — Categorías MCP + code_edit tools (30/jun/2026)

### 14.1 Motivación

Verificación del endpoint `/mcp` (29/jun) reveló:

1. El enum `app/core/categories.py` solo tenía 4 categorías
   (`FILESYSTEM`, `SEARCH`, `SYSTEM`, `CONFIG`) pero `circuits.py`
   referenciaba 8 (`bootstrap`, `stack`, `rag`, `gitops`, `filesystem`,
   `odoo`, `documents`, `sheets`).
2. El filtro `if cfg.allowed_mcp_categories:` en `_build_conversation`
   NO filtraba realmente — cargaba todas las tools al agente.
3. No había herramientas de code editing (`validate_python_syntax`,
   `run_pytest`, etc.) — solo `filesystem` y `git_tools`.
4. Los docs (`onboarding.md`, `rules.md`) no tenían flujos de code
   editing por circuito.

### 14.2 Cambios aplicados

#### 14.2.1 Enum `categories.py` expandido

```python
# app/core/categories.py — 9 categorías alineadas con circuits.py
FILESYSTEM = "filesystem"
SEARCH = "search"
SYSTEM = "system"          # legacy catch-all
CONFIG = "config"          # legacy
BOOTSTRAP = "bootstrap"
STACK = "stack"
RAG = "rag"
GITOPS = "gitops"
ODOO = "odoo"
DOCUMENTS = "documents"
SHEETS = "sheets"
CATOLICO = "catolico"
CODE_EDIT = "code_edit"
```

#### 14.2.2 Recategorización de las 65 tools existentes

Distribución final:

| Categoría | Tools |
|-----------|-------|
| `odoo` | 21 |
| `rag` | 8 |
| `filesystem` | 7 |
| `gitops` | 7 (get_git_status, get_git_log, diff_with_develop, get_pipeline_summary, run_salvar, run_promover, run_hotfix_sync) |
| `documents` | 6 |
| `bootstrap` | 5 (health_check, get_config, get_rules, get_onboarding, reload_config) |
| `catolico` | 5 |
| `code_edit` | 4 (nuevas) |
| `stack` | 3 (get_container_health, get_container_logs, get_vps_status) |
| `sheets` | 3 |
| **Total** | **69** |

#### 14.2.3 4 tools nuevas (`category: code_edit`)

| Tool | Propósito | Circuitos |
|------|-----------|-----------|
| `validate_python_syntax` | `ast.parse` sobre archivos .py; pre-commit check | backend, desarrollo, produccion |
| `run_pytest` | Ejecuta pytest en el workspace del circuito activo | backend, desarrollo, produccion |
| `detect_circuit_from_path` | Mapea path absoluto/relativo a circuito | libre (principal), otros |
| `cross_repo_search` | `git grep` en vivo sobre los 3 repos | todos |

#### 14.2.4 Filtro MCP real (`circuits.py::_build_conversation`)

```python
# Antes (decorativo):
# tools_list.extend(mcp_tools)  ← cargaba TODAS

# Ahora (Sprint 1.5):
allowed_names = set()
for tool_def in registry.list_tools():
    if tool_def.get("category") in cfg.allowed_mcp_categories:
        allowed_names.add(tool_def["name"])

filtered_mcp_tools = [
    t for t in mcp_tools
    if getattr(t, "name", None) in allowed_names
]
tools_list.extend(filtered_mcp_tools)
```

Resultado verificado programáticamente:

| Circuito | Categorías permitidas | Tools cargadas |
|----------|----------------------|----------------|
| `desarrollo` | 10 (todas) | 69 |
| `produccion` | 10 (todas) | 69 |
| `backend` | 10 (todas) | 69 |
| `libre` | 7 (sin gitops/stack/code_edit) | 55 |

#### 14.2.5 Docs (`onboarding.md`, `rules.md`)

- **`onboarding.md`**: agregada tabla de las 10 categorías MCP, columna
  "Categorías permitidas por circuito", sección "Flujos de code editing
  por circuito" (workflows detallados para desarrollo/produccion/backend/libre).
- **`rules.md`**: 27 reglas (vs 21 originales). Las nuevas son las
  reglas 22-27 de code editing pre-flight, cross-circuit file movement,
  y restricciones por circuito.

### 14.3 Tests agregados (Sprint 1.5)

`tests/test_code_edit_tools.py` — 16 tests, todos PASSING:

- 5 × `validate_python_syntax` (ok, syntax_error, missing, non_py, empty)
- 4 × `_circuit_for_path` (desarrollo, produccion, backend, unknown)
- 2 × `detect_circuit_from_path` (absolute match, unknown path)
- 2 × `run_pytest` (backend circuit integration, invalid circuit raises)
- 3 × `cross_repo_search` (finds marker, max_results cap, no matches con UUID aleatorio)

**Total tests Sprint 1.5**: 7 (git standalone) + 16 (code_edit) + 8 (MCP git layer) = **31 tests**.

### 14.4 Pendientes Sprint 2+ (no bloqueante para Sprint 1.5)

- Validación real con OpenHands SDK ejecutándose (necesita `openhands`
  instalado, hoy no disponible en este container).
- Persistencia de conversaciones entre reinicios (ya mencionado en §9.3).
- Tests de integración end-to-end con el agente ejecutando las 4 tools
  nuevas dentro de cada circuito.

---

## 15. Sprint 4 — oh-my-pi como agent runtime (30/jun/2026)

### 15.1 Motivación

Hoy el agent runtime es OpenHands SDK (`Conversation.run()` in-process). oh-my-pi
está instalado (`omp_rpc` Python) pero NO se invoca. El usuario decide activar
oh-my-pi como agent real.

**Hallazgo crítico del upstream (30/jun/2026, vs local v16.1.16 vs main
con 11,484 commits, 1,108 commits nuevos)**: oh-my-pi ya NO es un CLI
simple. Es ahora **"a coding agent with the IDE wired in"** con:

| Feature | Beneficio para Conti |
|---|---|
| **32 built-in tools** (read, edit, ast_edit, ast_grep, search, bash, lsp, debug DAP, eval Python/JS, task subagents, web_search, github, generate_image, etc.) | Reemplaza varias MCP tools nuestras. Menos código Python. |
| **14 LSP ops + 28 DAP ops** | IntelliSense real para Python/JS/TS/Rust/Go durante la edición. Debugging attachable a procesos. |
| **40+ LLM providers** (incluido Mistral, Anthropic, OpenAI, Gemini, xAI, Groq, Ollama local) | Switch de modelo en runtime. Mistral ya soportado. |
| **Subagents con worktrees aislados** | Cada subagente tiene su propia copia del repo. Sin conflicts entre siblings. |
| **Advisors** (segundo modelo vigilando cada turn) | Quality control: el modelo A hace, modelo B revisa. Captura errores antes del commit. |
| **Hindsight memory** (retain/recall/reflect) | Memoria persistente del proyecto entre sesiones. "El agente recuerda tu codebase". |
| **18 web_search providers** (perplexity, gemini, arxiv, github, stack overflow) | Codevibing real. Si el modelo duda, busca docs/web. |
| **Stream rules time-traveling** | Aborta stream mid-token, inyecta rule, retry. "Sin context tax en cada turn". |
| **Real browser via Puppeteer** (stealth on) | Visitar URLs reales sin ser detectado como bot. Útil para docs. |
| **Hashline edits** | Edits by content hash anchor. 61% menos tokens en Grok 4 Fast. |
| **ACP (Agent Client Protocol)** | Editor integration (Zed). Plan futuro. |
| **Inherits configs de otros tools** (Cursor MDC, Cline rules, Codex AGENTS.md) | Ponytail AGENTS.md ya se hereda automáticamente. |
| **40+ providers + models.yml custom** | Modelos custom definibles por proyecto. |
| **omp commit** (atomic splits, validated messages) | `run_salvar` reemplazado por `omp commit` — hace split atómico de cambios no relacionados. |
| **Conflict resolution URL-based** | `conflict://1` con `@theirs/@ours/@base`. Bulk `conflict://*`. |
| **Collab sessions** (shared links, QR, read-only view) | Pair programming entre Luis y agentes. |

**Implicancia**: integrar omp no es solo "reemplazar el agent loop" — es
**subir de nivel el agente entero**. Pasamos de un orquestrador con
69 MCP tools artesanales a un agente con 32 tools de grado industrial
+ 14 LSP + 28 DAP + subagents + advisors + memory.

**Decisión arquitectónica revisada** (vs PLAN_3 v0):
- omp NO corre como subprocess dentro de conti-backend.
- omp corre como **contenedor separado** (servicio `conti-omp` en
  docker-compose) — más limpio, escalable, aislado.
- conti-backend habla con conti-omp vía `omp_rpc.RpcClient` (loopback
  HTTP o socket, no subprocess).
- omp tiene su propio ciclo de vida (restart, persistencia de sesión
  en `.omp/sessions/`).

### 15.2 Arquitectura propuesta

```
                    uvicorn (FastAPI)
                          │
                          ▼
                app/openhands_agent/service.py
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
   Ponytail (trace)             CircuitManager
   sourcebot (RAG)                     │
            │                          ▼
            └──────► 4 × OmpClient (subprocess)
                          │   ┌──────────┐
                          ▼   ▼          │
              omp --mode rpc (Rust)       │
              │  LLM call                 │
              │  tool call ─────► host_tool handler (Python)
              │                         │   httpx POST
              │                         └─► :9001/mcp → MCP tools
              │
              └─► response → service.py → OpenAI-compat JSON
```

**OpenHands SDK deja de ser agent runtime**. Queda solo como proveedor de
`LLM` client si omp necesita un wrapper; en la práctica omp habla directo
con Mistral via OpenAI-compatible provider.

### 15.3 Decisiones arquitectónicas

| ID | Decisión | Razón |
|----|----------|-------|
| D1 | **Subprocess persistente** (1 por circuito = 4 totales) | omp startup toma 2-3s; per-request sería intolerable. |
| D2 | **Bridge MCP via httpx loopback** a `:9001/mcp` | Cada `host_tool.execute()` invoca la tool original. Latencia ~5ms en localhost. |
| D3 | **`append_system_prompt` por request** (no global) | Circuit prompt es dinámico (Ponytail rules + descripción + tools + Sourcebot). |
| D4 | **Provider `openai` con `base_url=https://api.mistral.ai/v1`** | Mistral es OpenAI-compatible. **Verificar empíricamente Fase 0.** |
| D5 | **Streaming via `on_message_update`** bridged a SSE OpenAI-compat | omp emite `text_delta` events; convertimos a `data: {...}\n\n`. |
| D6 | **Watchdog + auto-restart** si subprocess muere | Log a Ponytail, re-spawn transparente, re-registrar tools. |

### 15.4 Plan de implementación (8 fases)

#### Fase 0 — Verificación del entorno (completada 30/jun/2026, **✅ EXITOSA**)

**Objetivo**: confirmar que `omp` arranca, acepta Mistral via OpenAI-compat,
y responde al schema JSONL esperado.

**Resultados (30/jun/2026)**:

| Check | Resultado |
|---|---|
| Binario `omp` pre-construido en `vendor/oh-my-pi/target/release/` | ❌ no existe |
| Rust toolchain (`cargo`, `rustc`) | ✓ **instalado via rustup user mode** (1.96.1) |
| `omp_rpc` Python module | ✓ **instalado** (`pip install vendor/oh-my-pi/python/omp-rpc`) |
| Bun runtime | ✓ **instalado** (1.3.14) |
| `bun install --omit=optional --omit=peer` | ✓ 269 paquetes instalados |
| Artifact `tool-views.generated.js` | ✓ **generado** |
| `pi_natives.linux-x64-modern.node` (Rust addon, 132MB) | ✓ **compilado en background** (4min 13s) |
| `omp --version` | ✓ **`omp/16.1.16`** |
| `omp --help` | ✓ **funciona**, expone CLI completa (32 tools, 40+ providers) |
| Schema JSONL RPC | ✓ documentado en `vendor/oh-my-pi/python/omp-rpc/README.md` |

**Build chain exitosa**:

```bash
# 1. Launched in background (PID 3884200):
nohup bash -c '
  source "$HOME/.cargo/env"
  cd /contenedores/conti-backend/vendor/oh-my-pi
  TARGET_VARIANT=modern bun --cwd=packages/natives run build
' > /tmp/omp-native-build.log 2>&1 &
# Build took 4min 13s (mucho más rápido que lo estimado gracias a nohup)

# 2. Output:
#    Finished `local` profile [optimized] target(s) in 4m 13s
#    Normalizing native addon filename: pi_natives.linux-x64-gnu.node → pi_natives.linux-x64-modern.node
#    Generated 60 explicit ESM exports in index.js
#    Build complete.
#    Exit code: 0
```

**omp ahora es funcional**. Probar `omp --mode rpc` para validar la integración.

#### Fase 1 — Diseño del bridge `OmpClient`

**Objetivo**: archivo `app/openhands_agent/omp_client.py` que envuelva
`RpcClient` con semántica de circuito Conti.

**API objetivo**:

```python
class OmpClient:
    def __init__(self, circuit_id, workspace_dir, provider, model,
                 api_key, base_url, mcp_url): ...
    def register_tools(self, mcp_tools: list[dict]) -> None: ...
    def prompt_and_wait(self, user_prompt: str, system_prompt: str = "") -> str: ...
    async def stream_prompt(self, user_prompt: str, system_prompt: str = ""): ...
    def close(self) -> None: ...
    def health(self) -> dict: ...
    def _ensure_alive(self) -> None: ...  # watchdog Fase 5
```

**Estimación**: ~150 líneas.

#### Fase 2 — `CircuitManager` reescrito

**Objetivo**: `circuits.py::CircuitManager.get_or_create(circuit_id)` ahora
devuelve un `OmpClient` con tools filtradas ya registradas.

**Cambios**:

- `_build_conversation(cfg)` → `_build_omp_client(cfg)`.
- Singleton `self._omp_clients: dict[str, OmpClient]`.
- Filter MCP tools por `cfg.allowed_mcp_categories` antes de
  `register_tools()`.

**Estimación**: ~30 líneas modificadas.

#### Fase 3 — `service.py::_invoke_on_circuit` adaptado

**Cambio mínimo**: `conv.send_message(); conv.run()` →
`omp_client.prompt_and_wait(user_prompt, system_prompt=final_prompt)`.

```python
def _invoke_on_circuit(self, omp_client, user_prompt, system_prompt) -> str:
    return omp_client.prompt_and_wait(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
    )
```

**Estimación**: ~50 líneas modificadas.

#### Fase 4 — Streaming bridge

**Objetivo**: `stream_chat_completions` itera `on_message_update` y emite
chunks OpenAI-compatible SSE.

```python
async def stream_chat_completions(self, payload, auth_header=""):
    omp_client = circuit_manager.get_or_create(detect_circuit(payload))
    chunks_buffer = []
    
    @self._rpc.on_message_update
    def on_update(event):
        if event.assistant_message_event.get("type") == "text_delta":
            chunks_buffer.append(event.assistant_message_event["delta"])
    
    async def run_prompt():
        return omp_client.prompt_and_wait(
            user_prompt=user_prompt,
            system_prompt=final_prompt,
        )
    
    task = asyncio.create_task(asyncio.to_thread(run_prompt))
    sent_count = 0
    while not task.done() or sent_count < len(chunks_buffer):
        await asyncio.sleep(0.05)
        while sent_count < len(chunks_buffer):
            delta = chunks_buffer[sent_count]
            sent_count += 1
            chunk = {
                "id": f"chatcmpl-omp-{int(time.time())}",
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"content": delta}}],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode()
    yield b"data: [DONE]\n\n"
```

**Estimación**: ~40 líneas.

#### Fase 5 — Watchdog + auto-restart

```python
def _ensure_alive(self):
    if self._rpc.process and self._rpc.process.poll() is not None:
        log.warning(f"[omp:{self.circuit_id}] subprocess died, restarting")
        self._rpc.__exit__(None, None, None)
        self._rpc.__enter__()
        self.register_tools(self._last_registered_tools)
        # Log a Ponytail
```

Llamado al inicio de cada `prompt_and_wait` (bajo `with self._lock`).

**Estimación**: ~20 líneas.

#### Fase 6 — Tests

| Archivo | Tests | Tipo |
|---|---|---|
| `tests/test_omp_client.py` | 4 (init, register_tools, health, close) | unit con `RpcClient` mockeado |
| `tests/test_tool_bridge.py` | 3 (handler happy path, error path, schema translation) | unit con httpx mockeado |
| `tests/test_omp_integration.py` | 2 (per-circuit singleton, filter por categoría) | integration con subprocess real |

**Total**: 9 tests nuevos. Estimación: ~260 líneas.

**Adicional**: script bash manual `scripts/e2e/test_omp_subprocess.sh` que
arranca omp real y verifica handshake.

#### Fase 7 — Feature flag + cutover gradual

```python
# service.py
USE_OMP_AS_AGENT = os.getenv("CONTI_USE_OMP_AGENT", "false").lower() == "true"

def run_task(self, payload):
    if USE_OMP_AS_AGENT:
        return self._run_task_with_omp(payload)
    return self._run_task_with_openhands(payload)  # legacy
```

**Rollout**:

1. `CONTI_USE_OMP_AGENT=false` (default) → solo OpenHands SDK.
2. Día 1 dev: `true`, monitorear 24h.
3. Si OK: mantener dual-stack.
4. Sprint 5: default `true`, OpenHands queda como fallback.

**Estimación**: ~30 líneas + 1 env var.

#### Fase 8 — Docs y migración

- PLAN_3 §15 (esta sección).
- `docs/onboarding.md`: actualizar §5 (roles por componente) + agregar
  subsección sobre subprocess omp y watchdog.
- `docs/rules.md`: regla 28 sobre qué hacer si omp subprocess muere.
- `docker-compose.conti.yml`: agregar `restart: on-failure` al servicio
  `conti-backend` (para recovery del watchdog).
- `entrypoint_hermes.sh`: loggear pid de cada omp subprocess al startup.

**Estimación**: ~50 líneas modificadas.

### 15.5 Riesgos y mitigaciones

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | `omp` no acepta `base_url` custom para provider `openai` | Alta | Bloqueante | Fase 0 verifica. Si falla: fork omp o usar mini-omp Python. |
| R2 | Mistral no soporta function calling nativo en formato OpenAI | Baja | Medio | Mistral soporta `tools` estándar. Verificar E2E. |
| R3 | omp subprocess muere con archivos grandes | Media | Alto | Watchdog auto-restart (Fase 5). |
| R4 | Latencia MCP loopback > 100ms | Baja | Bajo | Loopback localhost ~5ms. Monitorear. |
| R5 | omp no soporta `append_system_prompt` por request | Media | Medio | Setear via env en subprocess spawn. |
| R6 | Tools JSON Schema incompatibles (omp vs MCP) | Baja | Bajo | Validar unit test en Fase 6. |
| R7 | Single-flight de omp bloquea requests concurrentes | Alta | Medio | Un `RpcClient` por request concurrente (pool), o queue. |

### 15.6 Entregables totales (status al 30/jun)

| Archivo | Tipo | Líneas | Estado |
|---------|------|--------|--------|
| `app/openhands_agent/omp_client.py` | nuevo | ~220 | ✅ cerrado |
| `app/openhands_agent/tool_bridge.py` | nuevo | ~80 | 🔴 Sprint 4.2 (PRIORITARIO 1) |
| `app/openhands_agent/circuits.py` | modificar | +50 | ✅ cerrado |
| `app/openhands_agent/service.py` | modificar | +30 | ✅ cerrado |
| `docker/conti-omp/Dockerfile` | nuevo | ~60 | ✅ cerrado |
| `docker/conti-omp/entrypoint.sh` | nuevo | ~50 | ✅ cerrado |
| `docker-compose.conti.yml` | modificar | +80 | ✅ cerrado |
| `tests/test_omp_client.py` | nuevo | ~280 (16 tests) | ✅ 16/16 passing |
| `tests/test_tool_bridge.py` | nuevo | ~100 (4 tests) | 🔴 Sprint 4.2 |
| `tests/test_omp_ponytail.py` | nuevo | ~100 (4 tests) | 🟡 Sprint 4.3 (PRIORITARIO 2) |
| `docs/onboarding.md` + `docs/rules.md` | modificar | ~30 | 🔴 Sprint 5 (post-Ponytail) |

**Total cerrado hasta ahora**: ~770 líneas (Sprint 4.1).
**Total Sprint 4 completo (objetivo)**: ~1050 líneas.

### 15.7 Rollback plan

Si Fase 7 muestra que omp es inestable en producción:

```bash
# Apagar omp y volver a OpenHands
export CONTI_USE_OMP_AGENT=false
docker compose up -d --build conti-backend
```

El código legacy (`_run_task_with_openhands`) se mantiene hasta Sprint 5
cuando se confirma estabilidad.

### 15.8 Estado de implementación (vivo, actualizar al cerrar cada fase)

| Fase | Estado | Notas |
|---|---|---|
| Fase 0 | ✅ completada — **bloqueada** | omp no funcional: vendor incompleto (faltan artifacts, Rust toolchain no instalado, bun install con fallos de extracción). Ver diagnóstico arriba. **Esperando decisión Luis: A / B / C.** |
| Fase 1 | ⬜ | Bloqueada hasta decisión de Fase 0 |
| Fase 2 | ⬜ | |
| Fase 3 | ⬜ | |
| Fase 4 | ⬜ | |
| Fase 5 | ⬜ | |
| Fase 6 | ⬜ | |
| Fase 7 | ⬜ | |
| Fase 8 | ⬜ | |
| **§15.bis** conti-omp container | ✅ **runtime OK** | Imagen built + container up + socat TCP↔stdio funciona end-to-end. Smoke test con prompt "Reply with just OK" → response "OK" desde Mistral. |
| **§15 Fase 1** OmpClient + feature flag | ✅ **CERRADO** | `app/openhands_agent/omp_client.py` implementado (~220 líneas). 16 tests passing. E2E verificado con `CONTI_USE_OMP_AGENT=true` → `runtime: "omp"` en response. |
| **§15 Fase 2** Tool bridging MCP loopback | ✅ **CERRADO** | `app/openhands_agent/tool_bridge.py` (~210 líneas) + `OmpClient.__init__(custom_tools=...)` + `circuits.py::_build_omp_client` invoca `build_custom_tools_for_circuit`. 8 tests passing (`tests/test_tool_bridge.py`). E2E validado: omp invoca `run_salvar` vía tool bridge y registra commit en /desarrollo y /compose. |
| **§15 Fase 3** Ponytail hooks (Sprint 4.3) | ✅ **CERRADO** | `app/tools/ponytail_trace_tools.py` (MCP tool) + `app/openhands_agent/trace_serializer.py` (YAML+GFM+mermaid) + `app/openhands_agent/ponytail.py` (PonytailTrace refactorizado) + `app/openhands_agent/circuit_locks.py` (Lock por circuit) + `OBSERVABILITY` category agregada. 15 tests passing (`tests/test_ponytail_trace.py`). E2E validado: trace file creado en `.ponytail/traces/2026-07-01_desarrollo_tr-3de52a35bffa.md`, commit `a3e46eb2 ponytail(desarrollo): tr-3de52a35bffa 16:12:50`. |

### 15.bis Contenedor separado `conti-omp` (30/jun/2026, 16:05 ART)

**Estado**: implementación parcial. Dockerfiles y compose listos. Falta
código Python (Fase 1 del Sprint 4 original).

### 15.ter Modo Plan / Execute (30/jun/2026)

> **NOTA sobre protocolo del agente**: Sprint 4 Fase 1 usa **`omp --mode
> rpc`** (NDJSON sobre stdio, vía socat) por simplicidad. ACP (`omp acp`)
> es una **opción futura** documentada en §15.bis.bis: si Luis quiere
> integrar VSCode/Zed directamente al agente (editor-driven mode sin
> FastAPI en el medio), o si necesitamos permission gates nativos. La
> migración es trivial: cambiar `command=["socat", "-", "TCP:conti-omp:7891"]`
> por un Python ACP client. El resto (circuitos, Ponytail, MCP) no se toca.

**Motivación**: ambos stacks (OpenHands SDK + oh-my-pi) deben soportar
`/plan` para que el cliente (VSCode, Cursor, Continue, etc.) pueda pedir
un plan antes de ejecutar cambios destructivos. El flujo:

```
VSCode: "/plan refactorizar X a async"
  ↓ POST /v1/chat/completions
conti-backend:
  1. detect_circuit("...plan...") → circuito X
  2. Detecta keyword "/plan" en user_prompt → mode = "plan"
  3. Inyecta al system_prompt:
     "Mode: PLAN. Respond with structured plan only.
      Do NOT execute tools. Do NOT make file edits.
      Format: 1. Step 2. Files 3. Expected diffs."
  4. omp_client.prompt_and_wait(mode="plan")
     ↓ env var OMP_PLAN=1 → wrapper script agrega --plan
conti-omp (oh-my-pi --plan):
  1. omp detecta --plan → usa role "plan" (modelo fuerte: o1, claude-opus)
  2. omp NO ejecuta tools (read/edit/bash/etc.)
  3. omp produce plan estructurado
     ↓
conti-backend:
  1. Registra en Ponytail: {mode:"plan", circuit:X, plan_length:N}
  2. Devuelve plan a VSCode
     ↓
VSCode muestra plan, user aprueba/rechaza
     ↓
VSCode: "OK procedé" (sin /plan)
  ↓ POST /v1/chat/completions
conti-backend: mode="execute" → omp_client.prompt_and_wait() normal
conti-omp: ejecuta tools, run_salvar, etc.
```

#### Soporte por capa

| Capa | Soporte | Cómo |
|---|---|---|
| **oh-my-pi** | ✅ nativo | `--plan` flag, `plan` role (modelo dedicado), `/plan` comando slash, `--slow`/`--smol` para variantes |
| **OpenHands SDK** | ⚠️ no nativo | System prompt injection: "respond with plan only, do not execute tools" |
| **conti-backend** (nuestra capa) | ❌ no implementado | Detector de keywords + switch mode + threading al omp subprocess |

#### Keywords para CIRCUIT_KEYWORDS (Fase 1 implementación)

```python
# Agregar a "produccion" y "desarrollo" (los dos que más sentido tienen para plan):
PLAN_KEYWORDS = (
    "/plan", "plan mode", "planea", "plan this",
    "make a plan", "dame un plan", "qué haría falta para",
    "qué cambios requiere", "analiza antes de",
)

EXECUTE_KEYWORDS = (
    "aplicá el plan", "ejecutá el plan", "aplicar plan",
    "proceed", "go ahead", "OK procedé", "dale",
    "implementá", "hacé el cambio",
)
```

#### Cambios a `OmpClient`

```python
class OmpClient:
    def prompt_and_wait(
        self,
        user_prompt: str,
        system_prompt: str = "",
        mode: str = "execute",  # ← NUEVO: "execute" | "plan"
    ) -> str:
        env_overrides = {}
        if mode == "plan":
            env_overrides["OMP_PLAN"] = "1"
        # ... existing logic, passing env_overrides to subprocess ...
```

#### Cambios al wrapper `omp-server.sh`

```bash
# Detecta OMP_PLAN env var y agrega --plan flag
PLAN_FLAG=""
if [ -n "${OMP_PLAN:-}" ]; then
    PLAN_FLAG="--plan"
fi
exec socat TCP-LISTEN:7891,fork,reuseaddr \
    "EXEC:/usr/local/bin/omp --mode=rpc \
        --profile=${OMP_PROFILE} \
        --no-skills --no-rules --no-title \
        ${PROVIDER_FLAG} \
        --model=${OMP_MODEL} \
        --api-key=${OMP_API_KEY} \
        ${PLAN_FLAG}"
```

#### Limitaciones y workarounds

| Limitación | Workaround |
|---|---|
| OpenHands SDK no tiene `plan` role nativo | System prompt injection + tool filter (mode=plan → filtrar run_salvar/promover/hotfix_sync) |
| omp `--plan` usa modelo dedicado (ej. o1) | `OMP_PLAN_MODEL=o1` env var cuando mode=plan, default `OMP_MODEL` cuando execute |
| LLM puede "escapar" del plan mode y ejecutar tools | OpenHands filtra tools disponibles según mode; omp también con `--no-tools` + plan response |
| Sin preview visual de diffs | omp tiene `ast_edit --preview` que podría usarse en plan mode (Fase futura) |

#### Configuración recomendada de modelos para plan vs execute

```yaml
# env vars en docker-compose.conti.yml
environment:
  # Execute mode (default): modelo rápido
  - OMP_MODEL=mistral/mistral-small-latest
  
  # Plan mode (cuando se detecta /plan): modelo fuerte de razonamiento
  - OMP_PLAN_MODEL=${OMP_PLAN_MODEL:-anthropic/claude-opus-4.5}
  
  # Fallback si OMP_PLAN_MODEL no está configurado
  # (usar el mismo modelo de execute, o un local como ollama/llama3.3:70b)
```

#### Tests E2E del plan mode

```bash
# 1. Enviar mensaje con /plan:
curl -X POST http://localhost:9001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "circuit":"desarrollo",
    "messages":[{"role":"user","content":"/plan refactorizar el método run_salvar para usar context managers"}]
  }'

# 2. Verificar que la respuesta contiene un plan (no cambios aplicados):
#    - Respuesta tiene estructura: 1. Step, 2. Files, 3. Diffs
#    - NO hay commit en /desarrollo
#    - NO hay edits en archivos

# 3. Aprobar el plan:
curl -X POST http://localhost:9001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "circuit":"desarrollo",
    "messages":[
      {"role":"user","content":"/plan refactorizar run_salvar"},
      {"role":"assistant","content":"<plan anterior>"},
      {"role":"user","content":"OK procedé"}
    ]
  }'

# 4. Verificar que AHORA sí hay commit:
cd /desarrollo && git log -1 --oneline
```

#### Estado de implementación

- [ ] Agregar keywords a `CIRCUIT_KEYWORDS` en `circuits.py`.
- [ ] Implementar `mode` param en `OmpClient.prompt_and_wait`.
- [ ] Wrapper `omp-server.sh` con detección de `OMP_PLAN`.
- [ ] Tool filter en OpenHands cuando mode=plan.
- [ ] Tests E2E (ver arriba).
- [ ] Documentar en `docs/onboarding.md` y `docs/rules.md` (regla sobre cuándo usar plan mode).

### 15.bis.bis ACP como opción futura (30/jun/2026)

**Estado**: descartado para Sprint 4 Fase 1 por simplicidad. Documentado
para referencia futura.

**Por qué NO ahora**:
- VSCode (Kilocode) ya habla `/v1/chat/completions` via custom provider.
- Cline (futuro) sigue el mismo patrón.
- ACP es un protocolo editor↔agente; nuestra capa FastAPI ya abstrae
  eso para todos los clientes externos.
- Implementar ACP client en Python suma complejidad sin beneficio
  inmediato en el flow actual.

**Cuándo SÍ migrar a ACP** (Fase futura):
- Luis quiere integrar VSCode/Zed **directamente** al agente sin pasar
  por FastAPI (editor-driven mode).
- Necesitamos `session/request_permission` nativo para tools destructivas
  (reemplaza el flow manual de preview+confirm).
- omp expone features nuevas solo-vía-ACP.

**Cómo migrar** (cambio mínimo):
1. Cambiar `command=["socat", "-", "TCP:conti-omp:7891"]` en
   `OmpClient` por un Python ACP client
   (`agent-client-protocol` SDK, paquete pip oficial).
2. Cambiar entrypoint de `conti-omp` a `omp acp` (en lugar de
   `omp --mode rpc`).
3. Reemplazar `prompt_and_wait()` por métodos ACP
   (`session.prompt`, `session.cancel`, etc.).
4. Mantener `OMP_PLAN` env var (flag `--plan` es compatible con ambos modos).

**Estado del entorno**: ACP ya está disponible (verificado en vendor/):
- oh-my-pi: `packages/coding-agent/src/modes/acp/{acp-agent,acp-client-bridge,acp-event-mapper}.ts` (3,593 líneas totales).
- OpenHands SDK: `vendor/OpenHands/openhands/app_server/web_client/`.
- Python SDK: instalable via `pip install agent-client-protocol` (no instalado aún).

**Decisión arquitectónica**: Sprint 4 Fase 1 va con `omp --mode rpc` (NDJSON).
Sprint futuro evalúa ACP cuando haya caso de uso concreto (editor-driven
mode, permission gates nativos).

#### Arquitectura final (mismo compose, contenedor adicional)

```
┌──────────────────────────────────────────────────────────────────────┐
│ docker-compose.conti.yml                                            │
│                                                                      │
│  ┌──────────────────────────────┐  socat STDIO↔TCP   ┌──────────┐  │
│  │ conti-backend (Python)       │◄──────────────────►│conti-omp │  │
│  │                              │  :7891 NDJSON      │          │  │
│  │ omp_rpc.RpcClient(           │                    │  omp     │  │
│  │   command=["socat","-",      │                    │  --mode  │  │
│  │     "TCP:conti-omp:7891"],   │                    │  rpc     │  │
│  │   custom_tools=[MCP tools],  │                    │          │  │
│  │ )                            │                    │  v16.2.9 │  │
│  │                              │                    │  Mistral │  │
│  │ Maneja:                      │                    │ Maneja:  │  │
│  │  • 4 circuitos                │                    │  • LLM   │  │
│  │  • Ponytail (ambos!)         │                    │  • tool  │  │
│  │  • Sourcebot RAG             │                    │    loop  │  │
│  │  • MCP loopback              │                    │  • LSP   │  │
│  │  • system_prompt per circuit │                    │  • DAP   │  │
│  │                              │                    │  • sub-   │  │
│  │                              │                    │    agents │  │
│  │                              │                    │  • memory │  │
│  └──────────────────────────────┘                    └──────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

#### Tool bridging strategy (qué usa cada uno)

**omp built-in (delegamos al nativo, sin bridge)**: 32 tools + 14 LSP +
28 DAP. Más ricos que nuestros MCP artesanales. omp usa:
- `read`, `edit`, `write` (con hashline anchors)
- `bash` (PTY + sesiones persistentes)
- `ast_edit`, `ast_grep` (tree-sitter 50+ grammars)
- `lsp` (LSP real — Python/JS/TS/Rust/Go/etc)
- `debug` (DAP — lldb, dlv, debugpy)
- `task` (subagents con worktrees aislados)
- `web_search` (18 providers — perplexity, gemini, arxiv, github, etc.)
- `eval` (Python+JS persistente con re-entry a tools)
- `generate_image`, `tts`, `inspect_image`
- `omp commit` (atomic splits con validación)

**MCP tools (bridged via `custom_tools` en RpcClient)**: solo lo que es
**regla custom de Conti** o **integración domain-specific**:

| Categoría MCP | Razón de bridge |
|---|---|
| `gitops` (run_salvar, run_promover, run_hotfix_sync) | **Reglas de seguridad custom**: target_branch check, force_branch, abort si /compose dirty. omp NO conoce nuestras reglas de circuitos. |
| `odoo` (21 tools) | **Integración domain-specific**: conti-backend tiene AppConfig con URLs/keys de Odoo (resto, odoo, mendoza). omp no. |
| `code_edit` (validate_python_syntax, run_pytest, detect_circuit_from_path, cross_repo_search) | **Circuit-aware**: detect_circuit_from_path solo funciona con nuestro mapa de paths. |
| `catolico` (5 tools) | **Integración domain-specific**: API Catholic church. |
| `sheets` (3 tools) | **Integración OCRL**: identity lookup para clientes Mendoza. |
| `documents` (6 tools) | **Traducción PDF/MD**: Flamehaven + SpineDigest. |
| `rag` (search_rag, etc.) | **Sourcebot**: nuestro RAG indexa los 3 repos. omp tiene web_search pero no Sourcebot. |
| `bootstrap`, `stack`, `system_status` | Infra checks (health, container status). |

**Cómo funciona el bridge** (en `omp_client.py`):

```python
def make_mcp_tool_handler(tool_name: str, mcp_url: str):
    def handler(args: dict, context) -> str:
        log.info(f"[omp:{circuit_id}] MCP tool call: {tool_name}({args})")
        resp = httpx.post(mcp_url, json={
            "jsonrpc": "2.0", "id": time.time_ns(),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        }, timeout=30)
        return json.dumps(resp.json().get("result", {}))
    return handler

# Filtrar MCP tools por categoría del circuito
mcp_tools_for_circuit = [
    t for t in registry.list_tools()
    if t["category"] in circuit.allowed_mcp_categories
]

host_tools = [
    host_tool(name=t["name"], description=t["description"],
              parameters=t["input_schema"],
              execute=make_mcp_tool_handler(t["name"], MCP_URL))
    for t in mcp_tools_for_circuit
]

omp_client = RpcClient(
    command=["socat", "-", "TCP:conti-omp:7891"],
    custom_tools=host_tools,
    ...
)
```

Cuando el LLM en omp decide usar `run_salvar`, omp emite un JSONL
`tool_call` event que viaja por socat a conti-backend. Python ejecuta
el handler (httpx POST a `:9001/mcp`). Resultado vuelve por JSONL a omp.
omp continúa su loop.

#### Ponytail integración (trazabilidad de AMBOS contenedores)

`Ponytail` envuelve `service.py::run_task` con un context manager. Para
capturar también la actividad del **subprocess omp** (en conti-omp),
hookeamos los eventos del `RpcClient`:

```python
class OmpClient:
    def __init__(self, ...):
        self._rpc.on_message_update(self._on_message_update)
        self._rpc.on_protocol_error(self._on_protocol_error)
        self._rpc.on_listener_error(self._on_listener_error)
    
    def _on_message_update(self, event):
        """Cada text_delta / tool_call del LLM omp → Ponytail."""
        ponytail.event(
            container="conti-omp",
            circuit=self.circuit_id,
            event_type="omp_message_update",
            payload=event.model_dump(),
        )
```

Ponytail escribe localmente en conti-backend (`/app/logs/ponytail/`).
Los eventos del omp subprocess vienen por JSONL → conti-backend los
captura → escribe a Ponytail. Vista unificada de la corrida entera.

#### Dockerfile.omp (resumen)

- **Stage 1 (builder)**: clona `OMP_VERSION` de GitHub, `bun install
  --omit=optional`, genera tool-views, compila pi-natives (Rust),
  linkea omp.
- **Stage 2 (runtime)**: copia binarios, instala socat + netcat, agrega
  wrapper script `/usr/local/bin/omp-server.sh` que lee env vars
  dinámicamente (modelo, API key, base URL).
- **Healthcheck**: `nc -z 127.0.0.1 7891`.
- **CMD**: `["/usr/local/bin/omp-server.sh"]`.

**Versión**: build-arg `OMP_VERSION` (default `v16.2.9`). Luis puede bumpear:
```bash
docker compose build --build-arg OMP_VERSION=v16.3.0 conti-omp
docker compose up -d conti-omp
```

**LLM config 100% env-driven** vía `OMP_MODEL`, `OMP_API_KEY`,
`OMP_BASE_URL`, `OMP_PROFILE`. Sin defaults hardcoded en Dockerfile.
Cambiar de Mistral a Anthropic = editar compose y `up -d`, sin rebuild.

#### Docker compose (servicio `conti-omp`)

```yaml
conti-omp:
  build:
    context: .
    dockerfile: Dockerfile.omp
    args:
      OMP_VERSION: ${OMP_VERSION:-v16.2.9}
  image: conti-omp:${OMP_VERSION:-v16.2.9}
  container_name: conti-omp
  environment:
    - OMP_PROFILE=conti
    - OMP_MODEL=${OMP_MODEL:-mistral/mistral-small-latest}
    - OMP_API_KEY=${OMP_API_KEY:-KkwZJdkcmtP3zKYRdOhyHltpxJxUarna}
    - OMP_BASE_URL=${OMP_BASE_URL:-https://api.mistral.ai/v1}
    - PI_COMPILED=1
  volumes:
    - /desarrollo:/desarrollo
    - /compose:/compose
    - /contenedores/conti-backend:/contenedores/conti-backend
    - omp_home:/home/conti
    - omp_data:/data
  ports:
    - "7891:7891"
```

#### Pendiente (Fase 1 código Python)

- [ ] `app/openhands_agent/omp_client.py` — wrapper con tool bridging
      + Ponytail hooks.
- [ ] `app/openhands_agent/circuits.py` — `CircuitManager.get_or_create()`
      devuelve `OmpClient` (en lugar de OpenHands `Conversation`).
- [ ] `app/openhands_agent/service.py::_invoke_on_circuit` —
      `omp_client.prompt_and_wait()` con `append_system_prompt=final_prompt`.
- [ ] Tests pytest con mock del RpcClient.
- [ ] Feature flag `CONTI_USE_OMP_AGENT` (default `false`).
- [ ] Tests E2E reales con conti-omp corriendo (Luis corre en VPS).

#### Workflow de actualización (Luis)

El submodule `vendor/oh-my-pi` está actualmente en v16.1.16 (snapshot
inicial). Para actualizar a v16.2.9 (o cualquier otra versión):

```bash
# 1. Update submodule a la versión deseada:
cd /contenedores/conti-backend/vendor/oh-my-pi
git fetch --tags
git checkout v16.2.9
cd ../..

# 2. Rebuild imagen conti-omp:
docker compose -f docker-compose.conti.yml build conti-omp
# Build ~5-10 min (Rust + Bun deps).

# 3. Up:
docker compose -f docker-compose.conti.yml up -d conti-omp

# 4. Verificar:
docker logs -f conti-omp
nc -zv conti-omp 7891
```

Cambiar de modelo LLM (sin rebuild):

```bash
# Editar docker-compose.conti.yml sección conti-omp.environment
# o pasar env vars al up:
OMP_MODEL="anthropic/claude-sonnet-4.5" \
OMP_API_KEY="sk-ant-..." \
OMP_BASE_URL="" \
docker compose -f docker-compose.conti.yml up -d conti-omp
```

Cambiar la versión de omp (build-arg):

```bash
docker compose build --build-arg OMP_VERSION=v16.3.0 conti-omp
docker compose up -d conti-omp
```

### 15.9 Lecciones aprendidas (cerrar al final del Sprint)

_(se llena retrospectivamente al cerrar el sprint — ver §15.quater.4)_

### 15.10 Multi-circuit omp + Sourcebot access (30/jun/2026) ✅ CERRADO

**Contexto (post-mortem Sprint 4.2)**: Luis señaló el 30/jun que:
1. **El `cd /desarrollo` hardcoded** en `entrypoint.sh` solo sirve al circuit
   `desarrollo`. Los circuits `produccion` (`/compose`) y `backend`
   (`/contenedores/conti-backend`) requieren su propio cwd.
2. **Libre NO usa git** (correcto, ya está implementado en `circuits.py`).
3. **omp debe tener acceso a Sourcebot DURANTE su trabajo** (no solo pre-agent).

#### 15.10.0 Corrección sobre Sourcebot (post-mortem Luis)

**Estaba alucinando**. Las tools `search_rag*` (rag_search_tools.py) hablan
con **Flamehaven** (otro container, RAG de documentos con LLM), NO con
Sourcebot. **Ningún archivo en `app/tools/` hablaba con Sourcebot** antes
del 30/jun. Sourcebot solo se usaba en el helper pre-agent
`_sourcebot_search` de `service.py`.

**Fix aplicado 30/jun**: creado `app/tools/sourcebot_tools.py` con 3 tools
MCP que sí wrappean la REST API de Sourcebot:
- `sourcebot_search` — búsqueda de código en repos indexados.
- `sourcebot_list_repos` — lista repos indexados.
- `sourcebot_get_doc` — devuelve el contenido de un archivo por path.

Registradas en `registry_service.py` con `category="sourcebot"`. El
agent omp ahora PUEDE buscar código en Sourcebot durante su trabajo vía
tool bridge. Agregada `mcp_categories.SOURCEBOT` a `app/core/categories.py`
y a `MCP_CATEGORIES_ALL` y `MCP_CATEGORIES_LIBRE` en `circuits.py`.

#### 15.10.1 Solución al cwd multi-circuit (30/jun, IMPLEMENTADO)

**Approach elegido**: omp_bridge.py — un mini server TCP+spawn Python
que reemplaza socat. Acepta conexiones TCP en :7891, hace fork+exec
de omp subprocess, y respeta `OMP_CIRCUIT_CWD` del env (que omp_rpc.RpcClient
pasa al subprocess via `env={...}`).

**Archivos nuevos**:
- `docker/conti-omp/omp_bridge.py` (~110 líneas) — server TCP Python que
  escucha en :7891, fork+exec omp con cwd=OMP_CIRCUIT_CWD, forwarda
  stdin/stdout/stderr entre la conexión TCP y omp.
- `docker/conti-omp/entrypoint.sh` (actualizado) — invoca omp_bridge.py
  en lugar de socat (eliminado del path crítico, sigue instalado para
  healthcheck con nc).

**omp_client.py** (modificado): pasa `env={OMP_CIRCUIT_CWD: ...}` al
constructor de `omp_rpc.RpcClient`. El subprocess (omp_bridge.py) lee esa
env var via `os.environ` y hace `chdir()` antes de `exec omp`.

**Test E2E verificado 1 jul 2026 (con restart limpio de conti-omp y conti-backend)**:

| Circuit | cwd | Resultado | Tiempo |
|---------|-----|-----------|--------|
| `libre` | /desarrollo (default entrypoint) | `LIBRE-OK` ✅ | 7.2s |
| `desarrollo` | /desarrollo | `DESA-OK` ✅ | 7.1s |
| `backend` | /contenedores/conti-backend | `BACK-OK` ✅ | 24.5s |
| `produccion` | /compose | `PROD-OK` ✅ | 16.6s |

**4/4 circuits verificados con cwd correcto** via `OMP_CIRCUIT_CWD` pasado
por env de RpcClient a omp_bridge. Confirmado que omp corre en el
workspace correcto de cada circuit. El timeout de produccion del primer
intento fue un issue transitorio (sesión colgada de tests anteriores
del desarrollo). Después de restart limpio, los 4 funcionan.

**Limitaciones conocidas**:
- **Single-process bridge**: este bridge setea cwd al startup. Para
  multi-circuit SIMULTÁNEO (no secuencial), hace falta multi-container
  omp (un container por circuit con su cwd fijo en entrypoint).
  Documentado como Sprint 5.
- **No parallel requests**: el bridge usa fork (no threads), así que
  cada request es un proceso independiente.omp subprocess corre solo
  durante la conexión TCP. Para multi-turn chats, conti-backend debe
  mantener la conexión abierta (ya lo hace omp_rpc.RpcClient).
- **`OMP_CIRCUIT_CWD` es per-subprocess, no per-request**: omp_bridge.py
  lee la env al inicio y la usa para todos los requests que maneje. Si
  conti-backend tiene un OmpClient por circuit, cada uno con su
  `OMP_CIRCUIT_CWD` distinto, y los requests son secuenciales (no
  paralelos), entonces el bridge funciona. Para paralelismo, multi-container.

#### 15.10.2 Acceso a Sourcebot (FLAMEHAVEN vs Sourcebot)

**Categorización clara** (verificada leyendo el código):

| Tool | Habla con | Tecnología |
|------|-----------|------------|
| `search_rag`, `search_rag_quick`, `search_rag_semantic`, `list_rag_store_docs`, `get_rag_ingest_job`, `start_rag_ingest`, `scan_documentos_nuevos` | **Flamehaven** (REST API) | RAG de documentos (PDFs, MDs) con LLM |
| `sourcebot_search`, `sourcebot_list_repos`, `sourcebot_get_doc` (nuevas) | **Sourcebot** (REST API :3010) | grep-semántico de código |

**Sourcebot NO expone MCP**, solo REST API en :3010. Por eso el bridge
MCP es necesario: omp invoca la custom tool → bridge hace POST al MCP
del backend → MCP handler hace HTTP a Sourcebot.

**Sourcebot indexa los 3 repos** (ver `docker-compose.conti.yml`):
- `/desarrollo` (contamela-stack dev)
- `/compose` (contamela-stack prod)
- `/contenedores/conti-backend` (orquestador-contamela)

Agent omp que corre en cualquiera de esos 3 cwds puede usar
`sourcebot_search` para buscar código en TODOS los 3 repos (no solo el
del cwd actual).



### 15.quater Sprint 4.2 + 4.3 — Tool bridging + Ponytail hooks (30/jun/2026)

**Estado**: pendiente (priorizado por Luis el 30/jun). Tool bridging es
**indispensable**; Ponytail hooks son necesarios para trazabilidad
completa de conti-omp.

#### 15.quater.1 Tool bridging (PRIORITARIO 1)

**Motivación**: `OmpClient` actualmente solo expone las 32 tools built-in
de oh-my-pi. **Falta exponer las MCP tools custom de Conti** (run_salvar,
odoo_*, catolico_*, sheets_*, etc.) que son las que aplican las **reglas
de seguridad custom** (target_branch check, force_branch, git safety).
Sin tool bridging, omp puede escribir archivos libremente sin pasar por
nuestras reglas.

**Diseño**:

```python
# app/openhands_agent/tool_bridge.py
import httpx
from omp_rpc import host_tool

def make_mcp_tool_handler(tool_name: str, mcp_url: str, timeout: float = 30.0):
    """Crea un handler Python para una MCP tool. Cuando omp la invoca,
    el handler hace JSON-RPC loopback a :9001/mcp."""

    def handler(args: dict, context) -> str:
        # Log a tracing (Ponytail hook aquí en Sprint 4.3)
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    mcp_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": time.time_ns(),
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": args},
                    },
                )
            data = resp.json()
            if "error" in data:
                return f"ERROR ({tool_name}): {data['error'].get('message', data['error'])}"
            result = data.get("result", {})
            # omp espera string como return; serializar structured content.
            if isinstance(result, dict):
                content = result.get("content", [])
                if content and isinstance(content, list):
                    return content[0].get("text", json.dumps(result, ensure_ascii=False))
            return json.dumps(result, ensure_ascii=False) if result else "(empty result)"
        except Exception as exc:
            return f"ERROR ({tool_name}): {type(exc).__name__}: {exc}"

    return handler


def build_custom_tools_for_circuit(
    circuit_cfg,
    registry,
    mcp_url: str,
) -> list:
    """Construye la lista de custom_tools para omp_rpc.RpcClient.

    Filtra el registry por cfg.allowed_mcp_categories y crea un
    host_tool() por cada MCP tool del circuito.
    """
    from omp_rpc import host_tool

    allowed_names = {
        t["name"]
        for t in registry.list_tools()
        if t.get("category") in circuit_cfg.allowed_mcp_categories
    }
    tools = []
    for t in registry.list_tools():
        if t["name"] not in allowed_names:
            continue
        ht = host_tool(
            name=t["name"],
            description=t.get("description", ""),
            parameters=t.get("input_schema", {"type": "object", "properties": {}}),
            execute=make_mcp_tool_handler(t["name"], mcp_url),
        )
        tools.append(ht)
    return tools
```

**Integración en `OmpClient`**:

```python
# app/openhands_agent/omp_client.py (modificaciones)
def __init__(
    self,
    circuit_id: str,
    workspace_dir: str,
    omp_host: str = "conti-omp",
    omp_port: int = 7891,
    mode: str = "execute",
    append_system_prompt: str = "",
    custom_tools: list | None = None,  # ← NUEVO
):
    rpc_kwargs = {
        "command": socat_cmd,
        "cwd": workspace_dir,
        "no_session": False,
    }
    if append_system_prompt:
        rpc_kwargs["append_system_prompt"] = append_system_prompt
    if custom_tools:
        rpc_kwargs["custom_tools"] = custom_tools  # ← NUEVO

    self._rpc = omp_rpc.RpcClient(**rpc_kwargs)
```

**Integración en `circuits.py::_build_omp_client`**:

```python
def _build_omp_client(self, cfg: CircuitConfig) -> Any:
    from app.openhands_agent.omp_client import make_omp_client_for_circuit
    from app.openhands_agent.tool_bridge import build_custom_tools_for_circuit
    from app.services.registry_service import registry_service

    Path(cfg.workspace_dir).mkdir(parents=True, exist_ok=True)

    # Construir custom_tools (MCP loopback filtrado por categoría).
    registry = registry_service()
    mcp_url = os.getenv("CONTI_MCP_URL", "http://127.0.0.1:9001/mcp")
    custom_tools = build_custom_tools_for_circuit(cfg, registry, mcp_url)

    system_prompt = self._build_omp_system_prompt(cfg)

    return make_omp_client_for_circuit(
        cfg,
        append_system_prompt=system_prompt,
        custom_tools=custom_tools,
    )
```

**Tests** (`tests/test_tool_bridge.py`):

```python
def test_make_mcp_tool_handler_sends_jsonrpc():
    """El handler arma correctamente el JSON-RPC request."""
    captured = {}
    def mock_post(url, json):
        captured.update(url=url, payload=json)
        return MagicMock(json=lambda: {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
    with patch("app.openhands_agent.tool_bridge.httpx.Client") as MockClient:
        MockClient.return_value.__enter__.return_value.post = mock_post
        handler = make_mcp_tool_handler("run_salvar", "http://mcp")
        result = handler({"commit_message": "test"}, context=None)
        assert captured["payload"]["method"] == "tools/call"
        assert captured["payload"]["params"]["name"] == "run_salvar"

def test_build_custom_tools_filters_by_category():
    """Solo tools del allowed_mcp_categories del circuit se incluyen."""
    ...

def test_handler_handles_error_response():
    """Si MCP devuelve error, el handler propaga el mensaje."""
    ...
```

**Decisión de scope**: el tool bridging se hace vía HTTP loopback al
**mismo proceso** uvicorn (no docker exec). Latencia despreciable en
localhost (~5ms). Soporta naturalmente:
- Streaming si MCP lo soporta (Sprint 5).
- Permissions: cada tool MCP puede tener sus propias reglas de safety
  (run_salvar exige `confirm=true`, etc.).
- Tracing: hook de cada tool call (ver §15.quater.2).

#### 15.quater.2 Ponytail hooks (PRIORITARIO 2)

**Motivación**: actualmente `_invoke_on_circuit` para omp retorna solo el
texto final. **Falta capturar los eventos intermedios** del omp subprocess
(text_delta, tool_call, tool_result, protocol_error, etc.) para que
Ponytail tenga trazabilidad completa de lo que pasó dentro de conti-omp.

**Diseño**:

`omp_rpc.RpcClient` expone **callbacks** que se pueden registrar:

```python
# Métodos disponibles en omp_rpc.RpcClient (verificado):
# on_message_update(listener)
# on_message_start(listener)
# on_message_end(listener)
# on_tool_execution_start(listener)
# on_tool_execution_end(listener)
# on_turn_start(listener)
# on_turn_end(listener)
# on_protocol_error(listener)
# on_listener_error(listener)
# on_agent_start(listener)
# on_agent_end(listener)
```

**Integración en `OmpClient.__init__`**:

```python
# app/openhands_agent/omp_client.py (modificaciones)
class OmpClient:
    def __init__(self, ..., ponytail_trace=None):
        self._trace = ponytail_trace  # Optional PonytailTrace instance
        ...
        self._rpc = omp_rpc.RpcClient(**rpc_kwargs)
        self._rpc.start()

        # Registrar hooks (solo si hay trace)
        if self._trace is not None:
            self._register_ponytail_hooks()

    def _register_ponytail_hooks(self):
        """Conecta eventos del omp subprocess al PonytailTrace activo."""
        self._rpc.on_message_update(self._on_message_update)
        self._rpc.on_tool_execution_start(self._on_tool_start)
        self._rpc.on_tool_execution_end(self._on_tool_end)
        self._rpc.on_protocol_error(self._on_protocol_error)
        self._rpc.on_listener_error(self._on_listener_error)
        self._rpc.on_turn_start(self._on_turn_start)
        self._rpc.on_turn_end(self._on_turn_end)

    def _on_message_update(self, event):
        """text_delta / text_start / text_end del assistant."""
        self._trace._log(
            "omp_message_update",
            {"event_type": getattr(event, "type", "unknown"), "payload": str(event)},
        )

    def _on_tool_start(self, event):
        self._trace._log(
            "omp_tool_start",
            {"tool": getattr(event, "tool_name", "?"), "args": getattr(event, "arguments", {})},
        )

    def _on_tool_end(self, event):
        self._trace._log(
            "omp_tool_end",
            {"tool": getattr(event, "tool_name", "?"), "ok": getattr(event, "success", None)},
        )

    def _on_protocol_error(self, event):
        self._trace._log(
            "omp_protocol_error",
            {"payload": str(event)},
        )

    def _on_listener_error(self, event):
        self._trace._log(
            "omp_listener_error",
            {"payload": str(event)},
        )

    def _on_turn_start(self, event):
        self._trace._log("omp_turn_start", {})

    def _on_turn_end(self, event):
        self._trace._log(
            "omp_turn_end",
            {"usage": getattr(event, "usage", None)},
        )
```

**Integración en `service.py::run_task`**:

```python
def run_task(self, payload):
    ...
    with PonytailTrace(task_name=user_prompt[:80], payload={**payload, "_circuit": circuit_id}) as trace:
        ...
        # Antes de invocar el runtime:
        runtime = circuit_manager.get_or_create(circuit_id)

        # Si es OmpClient, pasar el trace al constructor para que pueda
        # registrar hooks. Pero como OmpClient ya está creado (singleton),
        # necesitamos otro approach: set_trace() post-construction.
        if isinstance(runtime, OmpClient):
            runtime.set_trace(trace)
            result_text = self._invoke_on_circuit(runtime, final_prompt, circuit_id)
            runtime.set_trace(None)  # Cleanup post-call
        else:
            result_text = self._invoke_on_circuit(runtime, final_prompt, circuit_id)
        ...
```

**Modificación en `OmpClient`**:

```python
class OmpClient:
    def set_trace(self, trace):
        """Setter para el trace (usado por service.py). Registra/desregistra hooks."""
        if self._trace is not None:
            # Desregistrar hooks previos
            self._unregister_ponytail_hooks()
        self._trace = trace
        if trace is not None:
            self._register_ponytail_hooks()

    def _unregister_ponytail_hooks(self):
        # omp_rpc.RpcClient no expone unregister; los hooks siguen activos
        # pero verifican self._trace is not None antes de loggear.
        pass
```

**Output en Ponytail JSON** (`/app/logs/ponytail/trace-<ts>.json`):

```json
{
  "task_id": "trace-1782860000",
  "task_name": "Commit change",
  "started_at": 1782860000.0,
  "events": [
    {"event": "start", "ts": 1782860000.0, "data": {"task": "...", "payload_keys": ["messages", "circuit"]}},
    {"event": "circuit_selected", "ts": ..., "data": {"id": "desarrollo", "workspace": "/desarrollo"}},
    {"event": "sourcebot_search", "ts": ..., "data": {"hits": 3}},
    {"event": "runtime_invoke", "ts": ..., "data": {"circuit": "desarrollo", "runtime": "omp", "len": 0}},
    {"event": "omp_turn_start", "ts": ..., "data": {}},
    {"event": "omp_message_update", "ts": ..., "data": {"event_type": "text_delta", "delta": "Voy a..."}},
    {"event": "omp_tool_start", "ts": ..., "data": {"tool": "run_salvar", "args": {"commit_message": "..."}}},
    {"event": "omp_tool_end", "ts": ..., "data": {"tool": "run_salvar", "ok": true}},
    {"event": "omp_turn_end", "ts": ..., "data": {"usage": {"input": 27356, "output": 15}}},
    {"event": "end", "ts": ..., "data": {"duration_s": 4.32}}
  ]
}
```

**Tests** (`tests/test_omp_ponytail.py`):

```python
def test_ponytail_hook_receives_message_update():
    """Cuando omp emite message_update, el hook loggea al PonytailTrace."""
    fake_trace = MagicMock()
    with patch("omp_rpc.RpcClient") as MockRpcClient:
        client = OmpClient(circuit_id="test", workspace_dir="/tmp")
        client.set_trace(fake_trace)

        # Simular que omp llama el hook
        client._on_message_update(MagicMock(type="text_delta"))

        fake_trace._log.assert_called_with(
            "omp_message_update",
            {"event_type": "text_delta", "payload": "..."},
        )

def test_set_trace_none_unregisters_hooks():
    ...
```

#### 15.quater.3 Plan de implementación

| Fase | Acción | Estado |
|------|--------|--------|
| 4.2.1 | Crear `app/openhands_agent/tool_bridge.py` con `make_mcp_tool_handler` y `build_custom_tools_for_circuit` | ✅ cerrado |
| 4.2.2 | Modificar `OmpClient.__init__` para aceptar `custom_tools=[]` | ✅ cerrado |
| 4.2.3 | Modificar `circuits.py::_build_omp_client` para invocar `build_custom_tools_for_circuit` y pasarlos al factory | ✅ cerrado |
| 4.2.4 | Tests `tests/test_tool_bridge.py` (8 tests: 4 handler + 4 factory) | ✅ 8/8 passing |
| 4.2.5 | Smoke test E2E: omp puede invocar `run_salvar` y registrar commit | ✅ E2E validado (4/4 circuits + run_salvar en /compose con commit real) |
| 4.3.1 | Modificar `OmpClient` con `set_trace()`, `_register_ponytail_hooks`, `_on_*` handlers | 🟡 pendiente (PRIORITARIO 2) |
| 4.3.2 | Modificar `service.py::run_task` para pasar trace a OmpClient | 🟡 pendiente |
| 4.3.3 | Tests `tests/test_omp_ponytail.py` (3-4 tests) | 🟡 pendiente |
| 4.3.4 | Verificar que `/app/logs/ponytail/trace-*.json` incluye eventos omp | 🟡 pendiente |

**Total Sprint 4.2 cerrado**: 4/4 sub-fases ✅. ~250 líneas de código + tests.
**Total Sprint 4.3 pendiente**: 4 sub-fases. ~150 líneas estimadas.

### 15.quinquies Sprint 4.3 — Trazabilidad + Docs-as-Code (1 jul 2026)

**Motivación (idea de Luis)**: tener trazabilidad y observabilidad con la
mayor información posible — prompt del usuario, detalle de cada paso
del circuit (incluido sourcebot, ponytail, cada tool de oh-my-pi).
Generar un archivo Markdown con formato Hybrid (YAML Frontmatter +
GitHub-Flavored Markdown) en `.ponytail/traces/<id>.md`, commiteado
async al repo. GitHub renderiza mermaid nativo. Análisis de código/IA
pueden leer el YAML como dict estructurado.

#### 15.quinquies.1 Decisiones cerradas (1 jul 2026)

| Decisión | Valor | Razón |
|----------|-------|-------|
| Storage | Sub-directorio en main con path `.ponytail/traces/` | PR-review friendly; no contamina historia con branch dedicado |
| Visibilidad | Pública (sin redactor) | Repo privado asumido; redactor en Sprint 5+ |
| Tool call content | Metadata + result completo (sin truncar) | Mejor debugging; asume volumen bajo (~5 trazas/día) |
| Concurrencia | Lock por circuit (sin paralelismo al mismo circuit) | Balance: serialización intra-circuit, paralelismo inter-circuit |
| Push | Local + commit; push periódico (cron) | No bloquea request; GitHub se actualiza async |

#### 15.quinquies.2 Arquitectura

```
PonytailTrace.__exit__()
  │
  │ 1. Build trace_data dict con todos los campos
  │    (prompt, response, tool_calls, sourcebot_hits, events, etc.)
  │
  │ 2. Serializar a Markdown:
  │    TraceSerializer.to_markdown(trace_data) → str
  │    (YAML frontmatter + GFM body + mermaid sequenceDiagram)
  │
  │ 3. Emitir llamada a tool MCP:
  │    await mcp_client.call_tool("ponytail_record_trace", {
  │      "trace_data": trace_data,
  │      "markdown": markdown_str,
  │    })
  │
  ▼
MCP server: ponytail_record_trace(trace_data, markdown)
  │
  │ Fase 1 (sync): escribir archivo a .ponytail/traces/<id>.md
  │ Fase 2 (async thread pool): git add + commit (NO push)
  │   - Si commit falla, retry x3 con backoff
  │   - Si branch está detached, log warning y skip commit
  │
  ▼
Background thread: persiste el trace, hace commit local
```

#### 15.quinquies.3 Schema del trace (YAML frontmatter)

```yaml
---
trace_id: "tr-89a2b4cd"
timestamp: "2026-07-01T12:39:29-03:00"
circuit: "produccion"
model: "mistral/mistral-small-latest"
status: "success"               # success | error | timeout
duration_ms: 4250
tokens_used:
  input: 8430
  output: 1200
  total: 9630
tool_calls_count: 5
errors_count: 0
sourcebot_hits:
  - path: "app/models/odoo_sync.py"
    line: 42
  - path: "config/docker-compose.yml"
    line: 8
tool_calls:
  - name: "run_salvar"
    args: '{"commit_message": "..."}'
    result: '{"ok": true, "commit_hash": "..."}'
    latency_ms: 230
    status: "success"
    timestamp: "2026-07-01T12:39:25-03:00"
errors: []
events:                            # eventos omp crudos (on_message_update, etc.)
  - type: "omp_message_update"
    timestamp: 1782865620
    data: {...}
---

# 🔍 Traza Ponytail: `tr-89a2b4cd`
Modo: `PRODUCCIÓN` | Estado: 🟢 **SUCCESS** | Fecha: `2026-07-01 12:39:29`

## 🗺️ Flujo de Ejecución
```mermaid
sequenceDiagram
    autonumber
    Client->>Router: POST /v1/chat/completions
    Router->>Ponytail: enter context (circuit: produccion)
    par Context build
        Ponytail->>Sourcebot: search (top-5)
        Sourcebot-->>Ponytail: 5 paths
    end
    Ponytail->>Omp: append_system_prompt + user_task
    Omp-->>Ponytail: turn_start
    loop tool calls (N=5)
        Omp->>MCP: call tool (run_salvar)
        MCP->>Backend: dispatch handler
        Backend-->>MCP: result
        MCP-->>Omp: result
    end
    Omp-->>Ponytail: agent_end (text: "PROD-OK")
    Ponytail->>Backend: mcp_record_trace
    Backend->>Backend: write .ponytail/traces/<id>.md
    Backend->>Backend: git add + commit (async)
    Ponytail-->>Client: OpenAI response
```

## 💬 Mensajes

### User (input)
```
Reply DESA-OK
```

### Assistant (output)
```
PROD-OK
```

## 🔧 Tool Calls (5)

### 1. run_salvar
- **args:** `{"commit_message": "..."}`
- **result:** `{"ok": true, "commit_hash": "..."}`
- **latency:** 230ms
- **status:** success

### 2. odoo_get_invoice
...
```

## 📡 Sourcebot Hits
- `app/models/odoo_sync.py:42`
- `config/docker-compose.yml:8`

## 📋 Omp Events
| timestamp | type | data |
|-----------|------|------|
| 1782865620 | omp_message_update | `{...}` |
| ... | ... | ... |
```

#### 15.quinquies.4 Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `app/core/categories.py` | Agregar `OBSERVABILITY = "observability"` |
| `app/services/registry_service.py` | Registrar `ponytail_record_trace` con `category="observability"` |
| `app/openhands_agent/circuits.py` | Agregar `OBSERVABILITY` a `MCP_CATEGORIES_ALL` y `MCP_CATEGORIES_LIBRE` |
| `app/tools/ponytail_trace_tools.py` (nuevo) | `ponytail_record_trace(trace_data, markdown, auto_commit=True)`. Fase 1 sync (write file), Fase 2 async (git add + commit + retry) |
| `app/openhands_agent/trace_serializer.py` (nuevo) | `TraceSerializer.to_markdown(trace_data: dict) -> str`. Genera YAML frontmatter + GFM body + mermaid |
| `app/openhands_agent/ponytail.py` (nuevo) | Refactor de `PonytailTrace` (extraído de `service.py`): acumula eventos con métodos `record_message_update`, `record_tool_call`, `record_sourcebot_hit`, `record_error`. En `__exit__` serializa + llama tool MCP |
| `app/openhands_agent/circuit_locks.py` (nuevo) | `CircuitLocks` con `threading.Lock` por circuit. `get_lock(circuit_id) -> Lock`. Usado por `ponytail_record_trace` para serializar commits del mismo circuit |
| `app/openhands_agent/service.py` | Reemplazar `PonytailTrace` actual con import de `app.openhands_agent.ponytail.PonytailTrace`. Modificar `__exit__` para que llame a tool MCP |
| `tests/test_ponytail_trace.py` (nuevo) | 8-10 tests: serializador, tool MCP, locks, context manager |
| `docker-compose.conti.yml` | Env vars: `PONYTAIL_TRACE_DIR=.ponytail/traces/`, `PONYTAIL_COMMIT_TRACES=true`, `PONYTAIL_TRACE_RETENTION_DAYS=90` |

#### 15.quinquies.5 Optimizaciones implementadas

| Optimización | Implementación |
|--------------|-----------------|
| **Lock por circuit** | `CircuitLocks.get_lock(circuit_id)` en commit. Thread-safe. |
| **Persistencia en fases** | Sync (write file) + Async (git add + commit). Commit failure NO pierde la trace. |
| **Retry con backoff** | 3 intentos, 1s/2s/4s delays. Log cada retry. |
| **Metadata completa (sin truncar)** | Asume ~5 trazas/día × ~20KB = ~100KB/día. Truncar en Sprint 5+ si crece. |
| **Mermaid sequence diagram** | Renderiza automáticamente en GitHub. Visibilidad visual instantánea. |
| **YAML frontmatter parseable** | Herramientas externas (analytics, log search) pueden parsear como dict sin NLP. |
| **MCP tool categorization** | `category="observability"` (no `gitops`). Semánticamente correcto. |
| **Sin redactor** | Público. Redactor en Sprint 5+ si Luis decide. |

#### 15.quinquies.6 Tests E2E (8-10)

```python
def test_trace_serializer_produces_valid_yaml_and_mermaid():
    """El output del serializador es parseable como YAML y contiene mermaid."""
    ...

def test_ponytail_record_trace_writes_file():
    """La tool MCP escribe el archivo a .ponytail/traces/<id>.md."""
    ...

def test_ponytail_record_trace_commits_async():
    """Tras commit, git log incluye el trace."""
    ...

def test_ponytail_record_trace_retries_on_failure():
    """Si git commit falla, retry x3 con backoff."""
    ...

def test_circuit_locks_serialize_same_circuit():
    """Dos commits del mismo circuit no corren en paralelo."""
    ...

def test_circuit_locks_parallel_different_circuits():
    """Commits de diferentes circuits pueden correr en paralelo."""
    ...

def test_ponytail_trace_context_manager_emits_at_exit():
    """El __exit__ del ContextManager serializa + llama tool MCP."""
    ...

def test_ponytail_trace_includes_omp_events():
    """Los eventos on_message_update, on_tool_execution_* se acumulan en el trace."""
    ...

def test_e2e_real_request_creates_trace_file():
    """Request real POST /v1/chat/completions genera un .md en .ponytail/traces/."""
    ...
```

#### 15.quinquies.7 Plan de implementación

| Fase | Acción | Líneas | Tiempo |
|------|--------|--------|--------|
| 4.3.1 | Agregar `OBSERVABILITY` a `app/core/categories.py` | 5 | 5 min |
| 4.3.2 | Crear `app/tools/ponytail_trace_tools.py` (con phase 1 + 2 + retry) | 80 | 20 min |
| 4.3.3 | Registrar `ponytail_record_trace` en `app/services/registry_service.py` | 25 | 5 min |
| 4.3.4 | Agregar `OBSERVABILITY` a `MCP_CATEGORIES_ALL` y `LIBRE` en `circuits.py` | 10 | 5 min |
| 4.3.5 | Crear `app/openhands_agent/trace_serializer.py` (YAML + GFM + mermaid) | 120 | 30 min |
| 4.3.6 | Crear `app/openhands_agent/circuit_locks.py` (Lock por circuit) | 30 | 10 min |
| 4.3.7 | Refactor `PonytailTrace` en `app/openhands_agent/ponytail.py` (acumula eventos + emit) | 80 | 25 min |
| 4.3.8 | Modificar `service.py` para usar el nuevo `PonytailTrace` y `OmpClient.set_trace()` | 30 | 10 min |
| 4.3.9 | Tests `tests/test_ponytail_trace.py` (8-10 tests) | 250 | 30 min |
| 4.3.10 | E2E: ejecutar request, verificar trace file + git commit | 20 | 15 min |

**Total**: ~650 líneas. **Tiempo**: 2.5-3 horas.

#### 15.quinquies.8 Limitaciones conocidas (Sprint 5+)

- **Sin redactor de secrets** (Luis decidió público; Sprint 5+ si cambia).
- **Sin push automático** (cron separado; Sprint 5+).
- **Sin streaming** (la trace solo se cierra al final del turn; Sprint 5+ para streaming tokens).
- **Sin endpoint MCP para recuperar traces** (`ponytail_get_trace`, `ponytail_list_traces`; Sprint 5+).
- **Sin métricas agregadas** (latencia P50/P95, error rate, etc.; Sprint 5+).
- **Sin cleanup automático** (traces > 90 días; Sprint 5+ vía cron).

#### 15.quater.4 Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Tool handler falla → MCP no responde | Try/except en handler → return string `ERROR (...)`. omp continúa con el error message. |
| Tool handler timeout (MCP colgado) | `httpx.Timeout(30.0)`. Si se excede, return error string. omp puede abortar con `abort_bash()` si es necesario. |
| Hook spam (muchos text_delta por stream) | `PonytailTrace._log` ya hace append a in-memory list; persist al final. No hay problema de I/O. |
| Trace file gigante | Rotación: si el trace excede 10MB, dividir. (Post-MVP) |
| omp_rpc no expone unregister de hooks | Aceptable: hooks verifican `self._trace is not None` antes de loggear. Si trace es None, no loggean. |

#### 15.quater.5 Verificación E2E post-implementación

```bash
# 1. Tool bridging: omp puede invocar run_salvar
curl -X POST http://localhost:9001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "circuit":"desarrollo",
    "messages":[{"role":"user","content":"Commiteá el README con un mensaje corto"}]
  }'

# Verificar:
# - Response 200 con content del agente
# - /desarrollo tiene un nuevo commit
cd /desarrollo && git log -1 --oneline

# 2. Ponytail: trace contiene eventos omp
ls /app/logs/ponytail/trace-*.json | tail -1 | xargs cat | python3 -m json.tool
# Debe incluir eventos: circuit_selected, runtime_invoke, omp_turn_start,
#                       omp_message_update, omp_tool_start, omp_tool_end, omp_turn_end, end
```

---

## 13. Anexo: trazabilidad histórica

### 13.1 De PLAN_2 a PLAN_3 — qué se reemplazó

`PLAN_2_LLM.md` quedó **superseded** por este documento. La información
de PLAN_2 fue:

- ✅ **Incorporada tal cual**: §0 (estado), §2 (componentes), §3 (flujo
  end-to-end), §4 (los 4 circuitos), §5 (roles), §9 (gaps cerrados MCP).
- 🔄 **Actualizada**: §1 (resumen ejecutivo con nuevos pendientes),
  §4 (descripciones con `git_action_target`), §8 (CLI + Canvas, antes
  era "OpenHands GUI no disponible" en §6.3.bis).
- ➕ **Nueva**: §6 (hard check de git_tools.py), §7 (hotfix sync),
  §10 (cambios consolidados), §11 (testing E2E).

### 13.2 Línea de tiempo

| Fecha | Evento |
|-------|--------|
| 2026-05 | PLAN_LLM.MD v4: plan original de transición a OpenHands |
| 2026-06-24 | PLAN_2_LLM.md v0.6: GUI real OpenHands, base del agente |
| 2026-06-29 | **PLAN_3_LLM.md (este doc)**: bug de línea 194 descubierto, hotfix sync agregado |

### 13.3 Versiones previas de planes

- `PLAN_LLM.MD` — v4 original (reemplazado por PLAN_2).
- `PLAN_2_LLM.md` — v0.6 (reemplazado por PLAN_3).
- `PLAN_3_LLM.md` — v3.0 (vigente).

---

## 16. Sprint 4.3 — Observabilidad Completa + Sourcebot + Session Management (2 jul 2026)

**Estado**: ✅ **CERRADO** (con pendientes documentados).
**Duración**: ~8 horas de trabajo intensivo.
**Resultado**: Sistema funcional end-to-end con trazas Markdown, Sourcebot
operativo, session management y governance injection.

### 16.1 Resumen Ejecutivo

Sprint 4.3 cerró la brecha entre el "esqueleto" de observabilidad
(Sprint 4.2) y un sistema de trazabilidad **realmente útil** para
debugging y auditoría. Los cambios principales:

1. **Trazas Markdown renderizables** en `.ponytail/traces/` de cada repo
   (YAML frontmatter + GFM + Mermaid sequenceDiagram).
2. **Sourcebot operativo** (auth deshabilitada, keyword extraction,
   metadata enrichment en trazas).
3. **Session management** (X-Session-ID header, governance injection
   solo en primer mensaje).
4. **omp hooks conectados** (on_message_update, on_tool_execution_start/end,
   on_turn_end → PonytailTrace).
5. **Push automático a GitHub** (PONYTAIL_PUSH_TRACES=true).
6. **Sincronización de repos** (/desarrollo ↔ /compose ↔
   orquestador-contamela).

### 16.2 Archivos Creados

| Archivo | Líneas | Descripción |
|---------|--------|-------------|
| `app/tools/ponytail_trace_tools.py` | ~350 | MCP tool `ponytail_record_trace` + `trace_to_markdown()` + git commit/push retry |
| `app/openhands_agent/trace_serializer.py` | ~200 | YAML frontmatter + GFM body + Mermaid sequenceDiagram |
| `app/openhands_agent/ponytail.py` | ~150 | PonytailTrace context manager con `record_event()`, `record_tool_call()`, `record_tokens()` |
| `app/openhands_agent/circuit_locks.py` | ~40 | Lock por circuito (threading.Lock) |
| `app/tools/sourcebot_tools.py` | ~120 | 3 MCP tools: `sourcebot_search`, `sourcebot_list_repos`, `sourcebot_get_doc` |
| `tests/test_ponytail_trace.py` | ~250 | 15 tests (serializador, tool MCP, locks, context manager) |
| `tests/test_tool_bridge.py` | ~150 | 8 tests (handler, factory, circuit filtering) |
| `tests/test_omp_client.py` | ~150 | 8 tests (OmpClient, hooks, session) |
| `docker/conti-omp/omp_bridge.py` | ~140 | Mini server TCP + fork+exec omp con cwd=OMP_CIRCUIT_CWD |
| `docker/conti-omp/entrypoint.sh` | ~50 | Instala socat + ejecuta omp_bridge.py |

### 16.3 Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `app/openhands_agent/service.py` | - `PonytailTrace` inline reescrito con session management, `_fetch_governance()`, `_build_session_prompt()`, `_enrich_sourcebot_hit()`, `_extract_search_keywords()` |
| | - `run_task()` reescrito: session management (X-Session-ID), governance injection (primer mensaje), eliminación de Sourcebot pre-search |
| | - `_invoke_on_circuit()` reescrito: detección OmpClient vs OpenHands SDK, fallback para respuesta vacía |
| | - `PonytailTrace.__init__`: +`session_id`, `total_input_tokens`, `total_output_tokens` |
| | - `PonytailTrace._resolve_traces_dir`: +subcarpeta por sesión |
| | - `PonytailTrace.__exit__`: +`_persist_markdown_trace()` que llama `ponytail_record_trace` |
| | - Sourcebot: API corregida (GET→POST, formato v5.0.4), keyword extraction, metadata enrichment |
| | - TZ-aware timestamps (America/Argentina/Mendoza) |
| `app/openhands_agent/omp_client.py` | - `_event_data()` reescrito: maneja MessageUpdateEvent, ToolExecutionEvent, TurnEndEvent, ProtocolError |
| | - `_extract_usage()`: extrae tokens normalizados de cualquier formato de usage |
| | - `_extract_turn_usage()`: extrae model/provider/usage del turn object después de prompt_and_wait |
| | - `_on_message_update`: filtra eventos `omp_init` vacíos |
| | - `_on_tool_start/end`: preserva args del tool_start en tool_end |
| | - `_on_turn_end`: fuerza `event_type="turn_end"` |
| | - Timeout: 180→240→360→600s |
| `app/openhands_agent/circuits.py` | - `_build_omp_system_prompt()`: +MCP tools list (nombres agrupados por categoría) + bash+curl instructions + Sourcebot info + reglas de operación por circuito |
| `app/llm_emulation/router.py` | - +`X-Session-ID` header → `body["session_id"]` |
| `app/tools/sourcebot_tools.py` | - API corregida: GET→POST, formato `{query, matches}`, respuesta `{files: [...]}` |
| `docker-compose.conti.yml` | - `CONTI_USE_OMP_AGENT=true` (forzado) |
| | - `PONYTAIL_PUSH_TRACES=${...:-true}` |
| | - `OMP_PROMPT_TIMEOUT=${...:-360}` |
| | - `TZ=America/Argentina/Mendoza` |
| `docker/conti-omp/omp_bridge.py` | - `--tools=read,write,bash,glob,eval,search_tool_bm25` (deshabilita MCP tools nativas que timeout) |
| `docker/conti-omp/entrypoint.sh` | - +creación de `mcp.json` en profile de omp (luego revertido por incompatibilidad MCP) |

### 16.4 Cambios en Sourcebot

| Cambio | Detalle |
|--------|---------|
| **Auth deshabilitada** | `Org.isAnonymousAccessEnabled=true` en DB PostgreSQL de Sourcebot |
| **API corregida** | `sourcebot_tools.py`: GET→POST, formato `{query, matches}`, respuesta `{files: [{fileName, chunks, language, webUrl}]}` |
| **Keyword extraction** | `_extract_search_keywords()`: extrae 1-3 keywords técnicas de prompts largos (ej: "Explicame la app website del contenedor django" → "django website") |
| **Metadata enrichment** | `_enrich_sourcebot_hit()`: devuelve `{repo, fileName, language, line, branches, snippet, webUrl}` |

### 16.5 Session Management

**Implementación**:
- `X-Session-ID` header en router.py → `body["session_id"]`
- Si no hay session_id → nueva sesión (UUID generado)
- Si hay session_id → reutilizar sesión existente

**Governance injection** (solo primer mensaje):
1. `get_onboarding()`: workspace info, MCP tools, circuitos
2. `get_rules()`: reglas operativas del agente
3. `get_config()`: configuración del backend (redactada)

**Mensajes siguientes**: solo el user prompt (omp ya tiene el contexto
en su historial de sesión).

### 16.6 Trazas Markdown

**Formato** (ejemplo real):
```yaml
---
trace_id: trace-1783045281909
circuit: backend
task_name: Analiza el endpoint /mcp del contenedor conti-backend...
started_at: 2026-07-02T23:21:21.909256-03:00
ended_at: 2026-07-02T23:24:07.182285-03:00
duration_s: 165.273
events_count: 23
workspace: /contenedores/conti-backend
total_input_tokens: 0
total_output_tokens: 0
total_tokens: 0
tools_executed:
  get_config: 1
  health_check: 1
  write: 1
---
```

**Contenido del MD**:
- Diagrama Mermaid sequenceDiagram (6 actores: U, R, P, S, O, T)
- Eventos detallados con timestamps en TZ local (-03:00)
- Prompt completo (sin truncar)
- Sourcebot search results con metadata

### 16.7 Tests E2E Reales

| Test | Prompt | Circuito | Duración | Resultado | Archivo creado |
|------|--------|----------|----------|-----------|----------------|
| 1 | "Explicame la app website del contenedor django..." | desarrollo | 244s | ✅ OK (74 events) | — |
| 2 | "Analiza el contenedor chatui con definicion en producion.yml..." | produccion | 65s | ⚠️ Parcial ("Prompt completed without text") | — |
| 3 | "Analiza el endpoint /mcp del contenedor conti-backend..." | backend | 165s | ✅ OK (63 events) | `mcp_tools_doc.md` (46 KB) |

**Test 3 (backend) — resultado verificado**:
- Archivo: `/desarrollo/mcp_tools_doc.md` (46,483 bytes, 1156 líneas)
- Contenido: 43 tools MCP documentadas por categoría
- Traza: `2026-07-02_backend_trace-1783045281909.md` (23 events)
- Commit: `cf86fb5 ponytail(backend): trace-1783045281909 23:24:07`

### 16.8 Sincronización de Repos

| Repo | Rama | Estado | Commits ponytail |
|------|------|--------|------------------|
| `/desarrollo` (contamela-stack) | `develop` | ✅ Sincronizado | 5+ commits |
| `/compose` (contamela-stack) | `main` | ✅ Sincronizado | 5+ commits |
| `/contenedores/conti-backend` (orquestador-contamela) | `main` | ✅ Sincronizado | 5+ commits |

**Push automático**: `PONYTAIL_PUSH_TRACES=true` (configurado en
docker-compose). Requiere SSH key en el contenedor (ya verificada).

**Script de sync**: `sync_upstream.sh` en `/contenedores/conti-backend/`.

### 16.9 Problemas Encontrados y Resueltos

| Problema | Causa | Solución |
|----------|-------|----------|
| Sourcebot devuelve 0 hits | Auth habilitada (401) | `Org.isAnonymousAccessEnabled=true` en DB |
| Sourcebot devuelve archivo irrelevante | Keyword extraction no funcionaba | `_extract_search_keywords()` con known_concepts |
| omp no llama MCP tools | Protocolo MCP incompatible (SSE vs HTTP) | Revertido: omp usa tools nativas + bash+curl |
| MCP tools timeout (30s) | omp intenta conectar al MCP server vía SSE | `--tools=read,write,bash,glob,eval` en omp_bridge |
| Tokens en 0 | `omp_rpc` no expone usage en hooks | `_extract_turn_usage()` después de `prompt_and_wait` (parcial) |
| TZ incorrecta (UTC en vez de GMT-3) | `datetime.fromtimestamp()` sin TZ | `zoneinfo.ZoneInfo("America/Argentina/Mendoza")` |
| System prompt demasiado grande (19KB) | MCP tools con descripciones completas | Formato compacto (solo nombres agrupados) |
| Prompt truncado en traza | `user_prompt[:80]` | Eliminado: prompt completo en traza |
| Push automático no funciona | SSH key no configurada en contenedor | Verificada: SSH key existe, push manual funciona |

### 16.10 Pendientes (Sprint 5+)

| Pendiente | Prioridad | Descripción |
|-----------|-----------|-------------|
| **Tokens tracking** | 🟡 Media | `omp_rpc` no expone usage en los hooks de eventos. `_extract_turn_usage()` funciona parcialmente. Requiere investigación profunda del SDK omp_rpc o workaround (leer usage del turn object). |
| **MCP tools para omp** | 🟡 Media | Protocolo MCP de conti-backend (Streamable HTTP) incompatible con cliente MCP de omp (SSE). Opciones: (a) implementar SSE en conti-backend, (b) usar bash+curl como workaround, (c) investigar omp MCP client. |
| **Trazas por sesión en subcarpetas** | 🟢 Baja | Implementado (`_resolve_traces_dir` con session_id) pero no verificado E2E. Las trazas van directo a `.ponytail/traces/<circuit>/`. |
| **Sourcebot como RAG real** | 🟢 Baja | Sourcebot indexa los 3 repos pero el pre-search fue eliminado. omp puede usarlo via bash+curl. Futuro: integrar como MCP tool nativa. |
| **Plan mode** | 🟢 Baja | §15.ter documentado pero no implementado. Keywords `/plan` + mode="plan" en OmpClient. |
| **Cleanup automático de trazas** | 🟢 Baja | Script cron para eliminar trazas >90 días. |
| **Redactor de secrets** | 🟢 Baja | Actualmente las trazas son públicas (repo privado). Sprint 5+ si se necesita. |
| **Endpoint MCP para recuperar traces** | 🟢 Baja | `ponytail_get_trace`, `ponytail_list_traces` (Sprint 5+). |
| **OpenHands como orquestador visible** | 🟡 Media | La orquestación actual es código Python custom. Para que sea visible en la web GUI de OpenHands, necesitaríamos migrar al agent loop nativo de OpenHands (re-escritura profunda). |

### 16.11 Lecciones Aprendidas

1. **Sourcebot auth**: La instancia de Sourcebot tiene auth habilitada por
   default. Para uso interno (Docker network), deshabilitar auth via DB.

2. **omp MCP client**: El cliente MCP de omp espera SSE puro, pero
   conti-backend usa Streamable HTTP (SSE + POST). Son protocolos
   incompatibles. Workaround: bash+curl.

3. **Governance tools**: `get_onboarding`, `get_rules`, `get_config`
   deben inyectarse SOLO en el primer mensaje de sesión. omp conserva
   el contexto en su historial.

4. **Keyword extraction**: Sourcebot funciona mejor con 1-3 keywords
   técnicas que con prompts largos en español. `_extract_search_keywords()`
   filtra stopwords y prioriza conceptos conocidos del stack.

5. **Timeout de omp**: omp pierde ~90-120s en MCP tools que timeout.
   Aumentar `OMP_PROMPT_TIMEOUT` a 600s es la solución pragmática.

6. **Push automático**: La SSH key del contenedor permite push a GitHub.
   `PONYTAIL_PUSH_TRACES=true` funciona después de recrear el contenedor.

### 16.12 Línea de Tiempo Actualizada

| Fecha | Evento |
|-------|--------|
| 2026-05 | PLAN_LLM.MD v4: plan original de transición a OpenHands |
| 2026-06-24 | PLAN_2_LLM.md v0.6: GUI real OpenHands, base del agente |
| 2026-06-29 | PLAN_3_LLM.md v3.0: bug de línea 194 descubierto, hotfix sync agregado |
| 2026-06-30 | Sprint 4.0-4.1: oh-my-pi runtime (conti-omp container, OmpClient, feature flag) |
| 2026-06-30 | Sprint 4.2: Tool bridging + cwd multi-circuit (omp_bridge.py, tool_bridge.py) |
| 2026-07-01 | Sprint 4.3: Ponytail hooks + docs-as-Code (trace_serializer, ponytail.py, circuit_locks) |
| 2026-07-02 | **Sprint 4.3 extendido**: Observabilidad completa, Sourcebot, session management, governance injection |
| 2026-07-03 | **Sprint 4.4**: codebase-memory-mcp + skills de omp + MCP stdio verification |

---

## 17. Sprint 4.4 — codebase-memory-mcp + Skills de omp (3 jul 2026)

**Estado**: ✅ **CERRADO** (con pendientes documentados).
**Duración**: ~3 horas.
**Resultado**: omp se comunica correctamente con MCP servers via stdio.
Skills configuradas para acceso a MCP tools del backend y knowledge graph.

### 17.1 Resumen Ejecutivo

Sprint 4.4 resolvió el problema de compatibilidad MCP entre omp y los
MCP servers. Hallazgo clave: **omp SÍ puede hablar MCP stdio** (el
problema era con HTTP/SSE de conti-backend, no con omp).

Solución implementada:
1. **codebase-memory-mcp** como MCP server stdio para knowledge graph
2. **Skills de omp** como alternativa al protocolo MCP nativo para
   las MCP tools del backend (bash+curl en vez de MCP HTTP)
3. **2 skills genéricas** + **3 skills por circuito** para guiar a omp

### 17.2 codebase-memory-mcp

**Qué es**: Binario estático C (266MB) que indexa repos como knowledge
graph usando tree-sitter (158 lenguajes). Queries en <1ms.

**Instalación**:
- Binario: `/home/conti/.local/bin/codebase-memory-mcp` (en conti-omp)
- Config: `/home/conti/.omp/profiles/conti/agent/mcp.json` (stdio MCP)
- Persistencia: `entrypoint.sh` instala el binario y crea el mcp.json

**Projects indexados**:

| Project | Path | Nodos | Edges | Tiempo |
|---------|------|-------|-------|--------|
| `desarrollo` | `/desarrollo` | 153,281 | 560,947 | 97s |
| `compose` | `/compose` | 133,693 | 468,366 | 88s |
| `contenedores-conti-backend` | `/contenedores/conti-backend` | 4,360 | 8,605 | 6s |

**Test E2E verificado**: omp invoca `mcp__codebase_memory_search_code`
3 veces via stdio MCP. Protocolo funciona correctamente.

### 17.3 Skills de omp

**Qué son**: Markdown files con frontmatter YAML que omp carga
automáticamente como instrucciones. NO dependen del protocolo MCP.

**Ubicación**: `/home/conti/.omp/profiles/conti/skills/`

#### Skills genéricas (siempre disponibles)

| Skill | Descripción | Tools MCP que expone |
|-------|-------------|---------------------|
| `mcp-backend-tools` | Acceso a las 73 MCP tools del backend vía bash+curl | Todas (run_salvar, get_config, odoo_*, etc.) |
| `codebase-memory` | Knowledge graph de los 3 repos vía codebase-memory-mcp | search_graph, get_architecture, trace_path, query_graph, etc. |

#### Skills por circuito (cargadas según el circuito activo)

| Skill | Circuito | Descripción |
|-------|----------|-------------|
| `circuit-desarrollo` | desarrollo | Reglas, tools permitidas, flujo git develop |
| `circuit-produccion` | produccion | Reglas, tools permitidas, flujo git main+hotfix |
| `circuit-backend` | backend | Reglas, tools permitidas, pre-commit checks |

### 17.4 Cómo omp accede a las MCP tools del backend

**Dos caminos** (ambos verificados):

1. **MCP stdio** (codebase-memory-mcp): omp lanza el binario como
   subprocess y habla JSON-RPC por stdin/stdout. Funciona nativamente
   con el cliente MCP de omp.

2. **Skills + bash+curl** (MCP tools del backend): omp lee la skill
   como instrucciones y usa `curl -X POST http://conti-backend:9001/mcp/call`
   para invocar tools. Latencia ~5ms por call.

**Por qué NO usamos MCP HTTP para conti-backend**:
- omp hace GET `/mcp` → recibe SSE data → intenta parsear como JSON → error
- El protocolo SSE de conti-backend (Streamable HTTP) es incompatible
  con el cliente MCP de omp (espera SSE puro)
- Workaround: skills + bash+curl (funciona siempre)

### 17.5 Archivos creados/modificados

| Archivo | Acción |
|---------|--------|
| `docker/conti-omp/entrypoint.sh` | +instalación de codebase-memory-mcp + mcp.json + skills |
| `docs/onboarding.md` | +sección "Codebase Memory" + skills |
| `PLAN_3_LLM.md` | +este documento (§17) |

### 17.6 Pendientes

| Pendiente | Prioridad | Descripción |
|-----------|-----------|-------------|
| **Persistir índices de codebase-memory-mcp** | 🟡 Media | Los índices se pierden al reiniciar conti-omp. Opción: bind-mount `~/.cache/codebase-memory-mcp/` o re-indexar en entrypoint. |
| **Skills por categoría MCP** | 🟢 Baja | Skills específicas para odoo (21 tools), catolico (5), sheets (3), documents (6). |
| **MCP proxy stdio→HTTP** | 🟢 Baja | Si necesitamos streaming MCP o reducir latencia de bash+curl. |
| **Mejorar prompting de skills** | 🟡 Media | omp usó `search_code` en vez de `search_graph`. Mejorar instrucciones en skills. |

---

**Próximo paso:** crear skills específicas por circuito y por categoría
MCP, ejecutar los 3 tests de circuito, evaluar calidad de respuestas.

---

## 18. Sprint 5.0 — OpenHands como Orquestador (3-4 jul 2026)

**Estado**: ✅ **FUNCIONANDO** (con pendientes menores).
**Duración**: ~12 horas (investigación + implementación + debug).
**Resultado**: OpenHands Agent Server orquesta conversaciones con
Xiaomi mimo-v2.5-pro como LLM. Trazas se generan en subcarpetas
por sesión con naming correcto. codebase-memory-mcp instalado en omp.

### 18.1 Arquitectura final

```
HTTP → conti-backend:9001/v1/chat/completions
  → service.py::run_task()
    → PonytailTrace (traza MD)
    → Governance injection (solo primer mensaje)
      → get_onboarding() + get_rules() + get_config()
    → OpenHandsOrchestrator
      → POST /api/conversations (Agent Server :3001)
        → agent_settings con tools: [terminal, file_editor, read_file, write_file, glob, grep, list_directory, task_tracker]
        → LLM: openai/mimo-v2.5-pro via Xiaomi Token Plan SGP
      → POST /api/conversations/{id}/goal
      → GET /api/conversations/{id}/agent_final_response
      → Eventos → PonytailTrace
    → Persistir traza MD en .ponytail/traces/<circuit>/<session>/
    → Git commit automático
  → Respuesta OpenAI-compatible
```

### 18.2 Componentes implementados

| Componente | Archivo | Estado |
|------------|---------|--------|
| OpenHandsOrchestrator | `app/openhands_agent/open_hands_service.py` | ✅ |
| service.py (delega a orchestrator) | `app/openhands_agent/service.py` | ✅ |
| PonytailTrace (session subdirs) | `app/openhands_agent/service.py` | ✅ |
| trace_serializer (Gantt + duración) | `app/tools/ponytail_trace_tools.py` | ✅ |
| Event parser OpenHands | `open_hands_service.py::_log_event_to_trace` | ✅ |
| Response capture (fallbacks) | `open_hands_service.py::_wait_for_result` | ✅ |
| codebase-memory-mcp | `/home/conti/.local/bin/codebase-memory-mcp` | ✅ (v0.8.1) |
| Skills de omp (8 skills) | `/home/conti/.omp/profiles/conti/skills/` | ✅ |
| LLM profile (Xiaomi) | `/home/conti/.openhands/profiles/default.json` | ✅ |
| agent_settings con tools | En `open_hands_service.py::_create_conversation` | ✅ |
| TZ America/Argentina/Mendoza | `docker-compose.conti.yml` | ✅ |
| OMP_PROMPT_TIMEOUT=600 | `docker-compose.conti.yml` | ✅ |

### 18.3 Bugs fixes acumulados

| Bug | Fix | Estado |
|-----|-----|--------|
| CodeActAgent usa `bash` pero solo `terminal` | `agent_settings` con tools lowercase explícitas | ✅ |
| `PONYTAIL_TRACES_DIR` override ignora subcarpetas | Priorizar circuito+sesión sobre env var | ✅ |
| `_get_trace_dir_for_circuit` no importable | Mover a nivel de módulo | ✅ |
| `agent_final_response` vacío | Fallback: buscar último MessageEvent/ObservationEvent | ✅ |
| Reasoning truncado a mitad de frase | Límite 300→2000 chars | ✅ |
| Result truncado sin indicador | Agregar `...[truncated]` | ✅ |
| Mermaid sequenceDiagram no refleja loops | Reemplazado por Gantt timeline | ✅ |
| Sin duración por evento | Agregado `duration_ms` por tool call | ✅ |
| Sin dead time visible | Sección "Dead Time" en Gantt | ✅ |
| Tokens siempre en 0 | Parser de usage corregido | 🔄 |
| Sourcebot 0 hits | Reemplazado por codebase-memory-mcp | ✅ |
| OpenHands events parser usa `value` en vez de top level | Corregido: datos en top level | ✅ |
| LLM profile usa Mistral | Cambiado a Xiaomi `openai/mimo-v2.5-pro` | ✅ |
| `LocalWorkspace` necesita `working_dir` | Cambiado de `path` | ✅ |
| `persistence_dir` Permission denied | Path absoluto `/app/workspace/conversations/{id}` | ✅ |
| Sourcebot pre-search inútil | Eliminado, reemplazado por codebase-memory-mcp | ✅ |

### 18.4 Tests E2E reales (con Xiaomi mimo-v2.5-pro)

| Test | Circuito | Prompt | Response | Archivo | Traza |
|------|----------|--------|----------|---------|-------|
| 1 | desarrollo | "Explicame la app website..." | ✅ 4191 chars | No (solo explicación) | ✅ Subcarpeta |
| 2 | produccion | "Analiza el contenedor chatui..." | ✅ 335 chars | No (solo explicación) | ✅ Subcarpeta |
| 3 | backend | "Analiza el endpoint /mcp..." | ✅ 2836 chars | ✅ `mcp_tools_doc.md` (50KB) | ✅ Subcarpeta |

### 18.5 Pendientes

| Pendiente | Prioridad | Descripción |
|-----------|-----------|-------------|
| **Tokens en 0** | 🟡 Media | El parser de usage necesita extraer de ConversationStateUpdateEvent key=stats |
| **codebase-memory-mcp índices vacíos** | 🟡 Media | Volumen Docker con permisos root, no se puede escribir como uid=1000. Fix: recrear volumen o bind-mount |
| **Orchestrator timeout antes que agente** | 🟡 Media | Agente tarda ~5min pero DEFAULT_TIMEOUT=300s. Fix: aumentar a 600s o async |
| **Response vacía en orchestrator_end** | 🟢 Baja | Ya fixeado con fallbacks, pero el evento sigue mostrando response_len=0 |
| **Push automático a GitHub** | 🟢 Baja | SSH key configurada pero push no funciona desde orchestrator. Push manual funciona |

### 18.6 Documentación actualizada

- `docs/onboarding.md`: +sección codebase-memory-mcp + skills de omp
- `docker-compose.conti.yml`: +OMP_PROVIDER, +XIAOMI_TOKEN_PLAN_SGP_API_KEY, +TZ, +OMP_PROMPT_TIMEOUT=600
- `docker/conti-omp/entrypoint.sh`: +instalación codebase-memory-mcp + mcp.json + skills (8)
- `app/openhands_agent/open_hands_service.py`: NUEVO orchestrator
- `app/openhands_agent/service.py`: reescrito para delegar a orchestrator
- `app/tools/ponytail_trace_tools.py`: Gantt timeline + duración + tokens + truncado

---

## 19. Sprint 5.1 — Fixes de Observabilidad + GUI (4 jul 2026)

**Estado**: 🔄 **EN PROGRESO**.
**Duración**: ~2 horas.
**Resultado**: Fixes de observabilidad, GUI conectada, tokens en trazas.

### 19.1 Problemas identificados del Sprint 5.0

| # | Problema | Impacto |
|---|----------|---------|
| 1 | Missing prompt injection en traza | No se ve qué contexto recibió omp |
| 2 | Dead time polling ~27% | 80s de 300s son gaps de 4s |
| 3 | governance:get_onboarding error | Bug de parser Cypher |
| 4 | MCP tools no registradas | omp no usa tools del backend |
| 5 | Tokens en 0 | Parser no extrae usage |
| 6 | GUI no muestra conversaciones | Ingress apunta a :18000 en vez de :3000 |
| 7 | Timeout 300s insuficiente | Agente no termina tareas complejas |

### 19.2 Fixes implementados

| Fix | Archivo | Cambio |
|-----|---------|--------|
| Timeout 600s | `open_hands_service.py` | `DEFAULT_TIMEOUT=600` |
| Prompt injected event | `open_hands_service.py` | +`prompt_injected` con prompt completo |
| Polling 0.5s | `open_hands_service.py` | `time.sleep(0.5)` en vez de `time.sleep(2)` |
| Governance error filter | `service.py` | Filtrar errores Cypher `'(f)<-'` |
| MCP tools en agent_settings | `open_hands_service.py` | `mcp_config` merge en vez de sobrescribir |
| Tokens de stats | `open_hands_service.py` | +`omp_tokens` event de `ConversationStateUpdateEvent key=stats` |
| GUI ingress fix | `entrypoint_hermes.sh` | Ingress apunta a :3000 en vez de :18000 |
| Entrypoint rebuild | Dockerfile | Rebuild con entrypoint fixeado |

### 19.3 Estado de los puertos

| Puerto | Servicio | Estado |
|--------|----------|--------|
| 9001 | FastAPI (emulador LLM) | ✅ |
| 3000 | Agent Server (OpenHands) | ✅ |
| 3011 | Agent Server (host mapping) | ✅ |
| 3012 | Agent Canvas GUI | ✅ |
| 7891 | omp bridge (TCP) | ✅ |
| 8766-8770 | Hermes gateways | ✅ |
| 9119 | Hermes dashboard | ✅ |

### 19.4 Flujo de circuito documentado

```
HTTP → conti-backend:9001/v1/chat/completions
  → router.py (extrae circuit de X-Circuit-ID header)
  → service.py::run_task()
    → PonytailTrace (context manager, subcarpeta por sesión)
    → _fetch_governance() → llama get_onboarding/get_rules/get_config via MCP
    → _build_session_prompt() → construye prompt con governance + user prompt
    → OpenHandsOrchestrator
      → POST :18000/api/conversations (Agent Server)
        → agent_settings con tools nativas + mcp_config
        → LLM: openai/mimo-v2.5-pro via Xiaomi Token Plan SGP
      → POST :18000/api/conversations/{id}/goal
      → Polling GET /events/search cada 0.5s
      → GET /agent_final_response
    → _log_event_to_trace() → registra eventos en PonytailTrace
    → _persist_markdown_trace() → genera MD + commit git
  → Respuesta OpenAI-compatible
```

### 19.5 GUI de OpenHands

- **URL**: http://212.56.42.231:3012
- **Muestra**: Conversaciones creadas por el orchestrator
- **Ingress**: Redirige /api → :3000 (Agent Server)
- **Persistencia**: Conversaciones en /app/workspace/conversations/

---

**Próximo paso:** ejecutar test 3 (backend) con timeout 600s y verificar
que la traza tiene tokens, prompt_injected, y que la GUI muestra la conversación.