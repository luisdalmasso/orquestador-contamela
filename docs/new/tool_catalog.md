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

## Grupo G: Traducción (3)

### `start_markdown_translation`
Inicia la traducción de un archivo Markdown en background (chunk a chunk via `deep_translator`). Devuelve `job_id` inmediatamente; el proceso continúa en un thread daemon.
- **Visibilidad**: `public` | **Tags**: `translation`, `background`, `markdown`
- **Argumentos**: `input_path` *(req)*, `output_path` *(opt)*, `source_lang` *(opt, default: `auto`)*, `target_lang` *(opt, default: `en`)*, `chunk_size` *(opt, default: 4000)*, `retries` *(opt, default: 3)*, `overwrite` *(opt, default: false)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "start_markdown_translation", "arguments": {"input_path": "/compose/docs/manual.md", "target_lang": "en"}}'
```

### `get_translation_job`
Consulta estado y progreso de un job de traducción por su `job_id`.
- **Visibilidad**: `public` | **Tags**: `translation`, `status`, `read-only`
- **Argumentos**: `job_id` *(req)*
- **Estados posibles**: `queued` → `running` → `completed` / `failed`
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_translation_job", "arguments": {"job_id": "trans_abc123"}}'
```

### `list_translation_jobs`
Lista jobs recientes de traducción con su estado y progreso.
- **Visibilidad**: `public` | **Tags**: `translation`, `status`, `read-only`
- **Argumentos**: `limit` *(opt, default: 20)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_translation_jobs", "arguments": {"limit": 10}}'
```

---

## Grupo H: Documentos & PDF (3)

### `start_pdf_to_markdown`
Convierte un PDF, DOCX u otro documento soportado (URL o ruta local) a Markdown en background usando `markitdown`. Opcionalmente encadena una traducción automática al terminar. Devuelve `job_id` inmediatamente.
- **Visibilidad**: `public` | **Tags**: `document`, `pdf`, `markdown`, `background`
- **Argumentos**: `source` *(req — URL o path)*, `store` *(opt, default: `config.rag.default_store`)*, `output_path` *(opt)*, `also_translate` *(opt, default: false)*, `target_lang` *(opt, default: `en`)*
- **Output por defecto**: si no se envía `output_path`, guarda en `/compose/documentos_listos/{store}/{nombre}.md`
- **Pipeline con `also_translate=true`**: conversión → crea `TranslationJob` → devuelve ambos IDs
```bash
# Solo conversión
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "start_pdf_to_markdown", "arguments": {"source": "https://example.com/doc.pdf"}}'

# Solo conversión al store contamela (output default en /compose/documentos_listos/contamela/)
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "start_pdf_to_markdown", "arguments": {"source": "https://example.com/doc.pdf", "store": "contamela"}}'

# Conversión + traducción al inglés
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "start_pdf_to_markdown", "arguments": {"source": "/compose/docs/manual.pdf", "also_translate": true, "target_lang": "en"}}'
```

### `get_md_conversion_job`
Consulta estado de un job de conversión PDF/documento a Markdown.
- **Visibilidad**: `public` | **Tags**: `document`, `status`, `read-only`
- **Argumentos**: `job_id` *(req)*
- **Estados posibles**: `queued` → `running` → `completed_translating` / `completed` / `failed`
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_md_conversion_job", "arguments": {"job_id": "md_abc123"}}'
```

### `list_md_conversion_jobs`
Lista jobs recientes de conversión PDF/documento a Markdown.
- **Visibilidad**: `public` | **Tags**: `document`, `status`, `read-only`
- **Argumentos**: `limit` *(opt, default: 20)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_md_conversion_jobs", "arguments": {}}'
```

---

## Grupo I: RAG Flamehaven (4)

> Flamehaven FileSearch corre en `http://flamehaven:8000` (internamente) / `http://127.0.0.1:8100` (host).
> Los **stores** son colecciones aisladas con índice BM25 + vectorial propio. Se crean automáticamente al subir el primer documento.

### `start_rag_ingest`
Ingesta un documento (URL o ruta local) en el RAG Flamehaven. El pipeline es: descarga → conversión a Markdown con `markitdown` (preservando el nombre original en metadata) → upload al store destino. Devuelve `job_id` inmediatamente; el proceso ocurre en background.
- **Visibilidad**: `public` | **Tags**: `rag`, `document`, `ingest`, `background`
- **Argumentos**: `source` *(req — URL o path local)*, `store` *(opt, default: `config.rag.default_store`)*, `original_name` *(opt — nombre descriptivo para el índice)*, `overwrite` *(opt, default: `false`)*
- **Control de duplicados**: la verificación siempre se hace dentro del mismo `store` usando el nombre final del documento `.md`; si ya existe y `overwrite=false`, la ingesta se rechaza con `status=skipped_duplicate`. Si `overwrite=true`, Flamehaven borra el anterior y sube el nuevo.
- **Config**: `FLAMEHAVEN_API_KEY` en env, `rag.base_url` y `rag.default_store` en `app_config.json`
```bash
# Ingestar PDF desde URL en store "contamela"
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "start_rag_ingest", "arguments": {"source": "https://example.com/politica.pdf", "store": "contamela", "original_name": "politica-vacaciones-2026"}}'

# Ingestar archivo local
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "start_rag_ingest", "arguments": {"source": "/app/docs/onboarding.md", "store": "contamela"}}'

# Reemplazar si ya existe en el mismo store
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "start_rag_ingest", "arguments": {"source": "/compose/documentos_listos/contamela/politica.md", "store": "contamela", "overwrite": true}}'
```

**Ejemplos reales de respuesta**:

```json
{
  "status": "skipped_duplicate",
  "error": "Ya existe un documento con el nombre 'overwrite_test.md' en el store 'contamela'. Usá overwrite=true para reemplazarlo.",
  "duplicate_info": {
    "title": "overwrite_test.md"
  }
}
```

```json
{
  "status": "completed",
  "rag_response": {
    "overwritten": true,
    "previous_uri": "local://contamela/%2Ftmp%2Ftmp95muzh63%2Foverwrite_test.md"
  }
}
```

### `get_rag_ingest_job`
Consulta estado de un job de ingestión RAG en Flamehaven.
- **Visibilidad**: `public` | **Tags**: `rag`, `status`, `read-only`
- **Argumentos**: `job_id` *(req)*
- **Estados posibles**: `queued` → `running` → `uploading` → `completed` / `skipped_duplicate` / `failed`
- **Respuesta incluye**: `store`, `original_name`, `overwrite`, `md_path`, `rag_response` y, si hubo duplicado, `duplicate_info`
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_rag_ingest_job", "arguments": {"job_id": "rag_abc123"}}'
```

### `list_rag_ingest_jobs`
Lista jobs recientes de ingestión RAG en Flamehaven.
- **Visibilidad**: `public` | **Tags**: `rag`, `status`, `read-only`
- **Argumentos**: `limit` *(opt, default: 20)*
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_rag_ingest_jobs", "arguments": {}}'
```

### `scan_documentos_nuevos`
Escanea `/compose/documentos_nuevos/{store}/`, mueve cada archivo a `procesados/` y lanza un job de ingesta por archivo aplicando automáticamente los 3 casos de RAG.
- **Visibilidad**: `public` | **Tags**: `rag`, `ingest`, `scan`
- **Argumentos**: `store` *(opt, default: `config.rag.default_store`, usar `all` para todos)*, `dry_run` *(opt, default: `false`)*, `overwrite` *(opt, default: `false`)*
- **Control de duplicados**: igual que `start_rag_ingest`; la comparación se hace siempre dentro del mismo `store`.
- **Nota**: si `dry_run=true`, no mueve ni ingesta archivos; solo devuelve preview.
```bash
# Preview sin ingestar
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "scan_documentos_nuevos", "arguments": {"store": "contamela", "dry_run": true}}'

# Escanear todos los stores y reemplazar duplicados si existen
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "scan_documentos_nuevos", "arguments": {"store": "all", "overwrite": true}}'
```

> **Stores disponibles en Flamehaven:**
> - `default` — documentos generales del sistema
> - `contamela` — docs internos de Contamela
> - Cualquier nombre nuevo se crea automáticamente al hacer el primer upload
> - Búsqueda por store: `POST http://flamehaven:8000/api/search` con `{"query": "...", "store_name": "contamela"}`

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
|-------|----------------|----------|
| Leer código | `read_file`, `get_code_context` | `cat` directo |
| Buscar en código | `search_code_literal`, `grep_workspace` | `grep -r` manual |
| Estado Docker | `get_container_health`, `get_vps_status` | `docker ps` directo |
| Logs de contenedores | `get_container_logs` | `docker logs` directo |
| Estado del repo | `get_git_status`, `get_pipeline_summary` | `git status` directo |
| Commit a develop | `run_salvar` | `git commit`, `git push` directo |
| Promover a main | `run_promover` | `git merge`, `git push` directo |
| Traducir Markdown | `start_markdown_translation` + `get_translation_job` | traducir inline sin job |
| Convertir PDF/doc a MD | `start_pdf_to_markdown` + `get_md_conversion_job` | conversión sin tracking |
| Ingestar doc en RAG | `start_rag_ingest` + `get_rag_ingest_job` | upload directo sin job ni MD |
