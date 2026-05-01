# Tool Catalog — conti-backend

**Base URL pública**: `https://ai.contamela.com` (via Cloudflare Tunnel → `http://conti-backend:9001`)  
**Base URL interna**: `http://conti-backend:9001`  
**Invocación MCP**: `POST /mcp/call` con body `{"tool": "nombre_tool", "arguments": {...}}`  
**Listado de tools**: `GET /mcp/tools`  
**Última actualización**: 2026-05-01  
**Total tools registradas**: 22

> Todas las tools se invocan vía `POST /mcp/call`. Los argumentos opcionales pueden omitirse.

---

## Grupo A: Filesystem (4)

### `list_files`
Lista archivos y directorios bajo un root permitido.
- **Visibilidad**: `public` | **Tags**: `filesystem`, `read-only`
- **Caso de uso**: Explorar la estructura del proyecto.
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_files", "arguments": {"path": "/app"}}'
```

### `read_file`
Lee el contenido de un archivo dentro de los roots permitidos. Soporta lectura parcial por rango de líneas.
- **Visibilidad**: `public` | **Tags**: `filesystem`, `read-only`
- **Argumentos**: `path` *(req)*, `start_line` *(opt)*, `end_line` *(opt)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "read_file", "arguments": {"path": "/app/app/main.py", "start_line": 1, "end_line": 50}}'
```

### `file_exists`
Informa si un path permitido existe en el filesystem.
- **Visibilidad**: `public` | **Tags**: `filesystem`, `read-only`
- **Argumentos**: `path` *(req)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "file_exists", "arguments": {"path": "/app/config/app_config.json"}}'
```

### `get_code_context`
Devuelve líneas de contexto alrededor de una línea específica de un archivo permitido.
- **Visibilidad**: `public` | **Tags**: `filesystem`, `code`
- **Argumentos**: `path` *(req)*, `line` *(opt)*, `context` *(opt: nro de líneas alrededor)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_code_context", "arguments": {"path": "/app/app/llm_emulation/adapters.py", "line": 45, "context": 10}}'
```

---

## Grupo B: Search (3)

### `search_code_literal`
Busca texto literal o regex dentro del repo de desarrollo. Devuelve coincidencias con nombre de archivo y número de línea.
- **Visibilidad**: `public` | **Tags**: `search`, `code`
- **Argumentos**: `query` *(req)*, `include_pattern` *(opt, ej: `*.py`)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "search_code_literal", "arguments": {"query": "normalize_chat_payload", "include_pattern": "*.py"}}'
```

### `search_docs_literal`
Busca texto literal o regex dentro de la documentación del backend (archivos `.md`).
- **Visibilidad**: `public` | **Tags**: `search`, `docs`
- **Argumentos**: `query` *(req)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "search_docs_literal", "arguments": {"query": "rollback"}}'
```

### `grep_workspace`
Busca coincidencias dentro del workspace completo permitido (código + docs).
- **Visibilidad**: `public` | **Tags**: `search`, `workspace`
- **Argumentos**: `query` *(req)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "grep_workspace", "arguments": {"query": "NanobotServeError"}}'
```

---

## Grupo C: Sistema & Health (3)

### `health_check`
Devuelve el estado actual del backend: versión, uptime, servicios internos activos.
- **Visibilidad**: `public` | **Tags**: `system`
- **Caso de uso**: Verificar que el backend levantó correctamente. También accesible via `GET /health`.
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "health_check", "arguments": {}}'

# Alternativa REST:
curl http://conti-backend:9001/health
```

### `get_vps_status`
Vista consolidada del estado Docker local y del repo Git principal. Combina `docker ps` con `git status`.
- **Visibilidad**: `public` | **Tags**: `docker`, `git`, `status`, `read-only`
- **Argumentos**: `env` *(opt: `local`|`dev`|`prod`|`all`)*, `repo_path` *(opt)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_vps_status", "arguments": {"env": "all"}}'
```

### `reload_config` 🔒 Internal
Recarga la configuración del backend desde disco sin reiniciar el proceso.
- **Visibilidad**: `internal` | **Tags**: `config`
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "reload_config", "arguments": {}}'
```

---

## Grupo D: Configuracion & Governance (3)

### `get_config`
Devuelve la configuración efectiva del backend con datos sensibles redactados.
- **Visibilidad**: `public` | **Tags**: `config`
- **Caso de uso**: Debugging — verificar qué rutas, modelos y límites están cargados en runtime.
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_config", "arguments": {}}'
```

### `get_onboarding`
Devuelve el contenido del archivo `onboarding.md` del backend. Soporta modo `brief` para obtener solo el resumen ejecutivo.
- **Visibilidad**: `public` | **Tags**: `config`, `onboarding`
- **Argumentos**: `brief` *(opt: true para solo sección [BRIEF])*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_onboarding", "arguments": {"brief": true}}'
```

### `get_rules`
Devuelve las reglas efectivas del backend (`rules.md`). Gobiernan el comportamiento del agente.
- **Visibilidad**: `public` | **Tags**: `config`, `rules`
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_rules", "arguments": {}}'
```

---

## Grupo E: CI/CD Git Local (6)

> **Regla de oro**: Usar siempre `confirm=false` primero para ver el preview antes de ejecutar escrituras.

### `get_git_status`
Estado del repo Git local: branch actual, archivos modificados, staged, untracked.
- **Visibilidad**: `public` | **Tags**: `git`, `read-only`
- **Argumentos**: `repo_path` *(opt)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_git_status", "arguments": {}}'
```

### `get_git_log`
Historial reciente de commits del repo local.
- **Visibilidad**: `public` | **Tags**: `git`, `read-only`
- **Argumentos**: `n` *(opt, default: 10)*, `repo_path` *(opt)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_git_log", "arguments": {"n": 10}}'
```

### `diff_with_develop`
Compara el HEAD local contra la rama `develop`. Ver exactamente qué cambió antes de salvar.
- **Visibilidad**: `public` | **Tags**: `git`, `diff`
- **Argumentos**: `repo_path` *(opt)*, `remote` *(opt)*, `develop_branch` *(opt)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "diff_with_develop", "arguments": {}}'
```

### `get_pipeline_summary` ⭐ Primer paso recomendado al retomar trabajo
Resume el pipeline Git local: rama actual, estado, remotos y diff contra develop.
- **Visibilidad**: `public` | **Tags**: `git`, `pipeline`, `read-only`
- **Argumentos**: `repo_path` *(opt)*, `remote` *(opt)*, `develop_branch` *(opt)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_pipeline_summary", "arguments": {}}'
```

### `run_salvar` ⚠️ Escritura — COMMIT a develop
Preview o ejecución de `git add + commit + push` a la rama `develop`.
- `confirm=false` → preview del diff y mensaje planificado, **no modifica el repo**
- `confirm=true` → ejecuta commit y push
- **Visibilidad**: `public` | **Tags**: `git`, `write`
- **Argumentos**: `confirm` *(opt, default false)*, `summary` *(opt)*, `repo_path`, `remote`, `develop_branch` *(opt)*
```bash
# Paso 1: preview
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "run_salvar", "arguments": {"confirm": false}}'

# Paso 2: ejecutar
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "run_salvar", "arguments": {"confirm": true, "summary": "fix: normalize payload nanobot"}}'
```

### `run_promover` ⚠️ Escritura — MERGE develop → main
Preview o ejecución de merge `develop` → `main` con push. Promueve a producción.
- `confirm=false` → preview con commits a promover y diff stat
- `confirm=true` → ejecuta merge + push
- **Visibilidad**: `public` | **Tags**: `git`, `write`, `promote`
- **Argumentos**: `confirm` *(opt)*, `summary` *(opt)*, `repo_path`, `remote`, `develop_branch`, `main_branch` *(opt)*
```bash
# Paso 1: preview
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "run_promover", "arguments": {"confirm": false}}'

# Paso 2: ejecutar
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "run_promover", "arguments": {"confirm": true, "summary": "Release v1.0.1: fix normalize payload"}}'
```

---

## Grupo F: Docker & Containers (2)

### `get_container_health`
Estado y salud de contenedores Docker via socket. Muestra nombre, estado, image, puertos y healthcheck.
- **Visibilidad**: `public` | **Tags**: `docker`, `containers`, `read-only`
- **Argumentos**: `env` *(opt: `local`|`dev`|`prod`|`all`)*, `container` *(opt: filtrar por nombre)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_container_health", "arguments": {"env": "all"}}'
```

### `get_container_logs`
Logs de un contenedor Docker local con filtros por tiempo, nivel y cantidad de líneas.
- **Visibilidad**: `public` | **Tags**: `docker`, `logs`, `read-only`
- **Argumentos**: `container` *(req)*, `lines` *(opt, default: 100)*, `since` *(opt, ej: `1h`, `30m`)*, `level` *(opt: `all`|`error`|`warning`)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_container_logs", "arguments": {"container": "conti-backend", "lines": 100, "since": "1h", "level": "error"}}'
```

---

## Endpoints REST complementarios

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | `GET` | Health check (equivalente a tool `health_check`) |
| `/mcp/tools` | `GET` | Lista completa de tools con schemas JSON |
| `/mcp/call` | `POST` | Invocar cualquier tool MCP |
| `/v1/chat/completions` | `POST` | Emulación OpenAI — enruta a nanobot serve (puerto 8765) |
| `/v1/models` | `GET` | Lista modelos disponibles (compatibilidad OpenAI) |
| `/docs` | `GET` | Swagger UI interactivo |

---

## Gobernanza — Priorización de tools

| Tarea | Tool mandatoria | Prohibido |
|-------|----------------|-----------|
| Leer código | `read_file`, `get_code_context` | `cat` directo |
| Buscar en código | `search_code_literal`, `grep_workspace` | `grep -r` manual |
| Estado Docker | `get_container_health`, `get_vps_status` | `docker ps` directo |
| Logs de contenedores | `get_container_logs` | `docker logs` directo |
| Estado del repo | `get_git_status`, `get_pipeline_summary` | `git status` directo |
| Commit a develop | `run_salvar` | `git commit`, `git push` directo |
| Promover a main | `run_promover` | `git merge`, `git push` directo |
