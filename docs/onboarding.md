# Onboarding Conti Backend (actualizado PLAN_3 v1.5, 30/jun/2026)

## Stack

- Backend MCP/FastAPI para `conti-backend` (puerto `:9001`).
- OpenHands Agent Server REST API (puerto `:3011` → `:3000` interno).
- OpenHands Agent Canvas — GUI Next.js oficial (puerto `:3012` →
  `:3012` interno).
- OpenHands CLI textual embebido en web (puerto `:3013` → `:3001`
  interno, comando `openhands web`).
- Sourcebot v5.0.4 para RAG sobre código (puerto `:3010`).
- LLM activo: `mistral/mistral-small-latest` vía Mistral API.
- Redis: `redis_odoo:6379`, DB 14 asignada a Sourcebot.
- Postgres: `compose-db-1:5432`, DB `sourcebot`.

## Repos bind-mounted

| Path contenedor | Repo | Rama activa | Uso |
|-----------------|------|-------------|-----|
| `/desarrollo` | contamela-stack (dev) | `develop` | flujo normal |
| `/compose` | contamela-stack (prod) | `main` | hotfix + lectura pasiva |
| `/contenedores/conti-backend` | orquestrador-contamela | `main` | devops backend |
| `/home/nanobot` | (no es repo) | — | HOME persistente del agente |
| `/tmp/free-agent` | (no es repo) | — | workspace del circuito `libre` |

## Circuitos del agente (4)

| ID | Workspace | Branch | Git action permitida |
|----|-----------|--------|---------------------|
| `desarrollo` | `/desarrollo` | `develop` | `run_salvar` (commit + push develop) |
| `produccion` | `/compose` + `/desarrollo` | `main` en /compose, `develop` en /desarrollo | `run_promover` (develop→main+push) + `run_hotfix_sync` (main→develop) |
| `backend` | `/contenedores/conti-backend` | `main` | `run_salvar` directo a main (sin flujo develop↔main) |
| `libre` | `/tmp/free-agent` | — | ninguna (solo MCP de consulta) |

Cada circuito es una conversación persistente (`LocalConversation`) del
OpenHands SDK. Los 4 conviven en memoria del proceso uvicorn.

## Categorías MCP (filtrado real, Sprint 1.5)

Las MCP tools se filtran ahora por categoría al construir la conversación
de cada circuito. Categorías activas:

- **bootstrap**: `health_check`, `get_config`, `get_rules`, `get_onboarding`, `reload_config`
- **stack**: `get_container_health`, `get_container_logs`, `get_vps_status`
- **gitops**: `get_git_*`, `run_salvar`, `run_promover`, `run_hotfix_sync`, `get_pipeline_summary`
- **odoo**: 21 tools (`odoo_*`)
- **rag**: `search_rag*`, `start_rag_ingest*`, `scan_documentos_nuevos`, `list_rag_store_docs`
- **catolico**: 5 tools (`catolico_*`)
- **documents**: 6 tools (`start_markdown_translation`, etc.)
- **sheets**: 3 tools (`sheet_*`)
- **filesystem**: 7 tools (`list_files`, `read_file`, etc.)
- **code_edit** (nuevo): `validate_python_syntax`, `run_pytest`, `detect_circuit_from_path`, `cross_repo_search`

| Circuito | Categorías permitidas |
|----------|----------------------|
| `desarrollo` | todas (10 categorías, 69 tools) |
| `produccion` | todas (10 categorías, 69 tools) |
| `backend` | todas (10 categorías, 69 tools) |
| `libre` | bootstrap, rag, odoo, documents, sheets, catolico, filesystem (7 categorías, 55 tools — **NO** tiene gitops/stack/code_edit) |

## Flujos de git

### Flujo 1: dev → origin/develop (circuito `desarrollo`)

```
Luis edita /desarrollo
  → run_salvar(confirm=true, summary="...")
  → git add -A && git commit -m "..." && git push origin develop
```

### Flujo 2: origin/develop → origin/main (circuito `produccion`)

```
run_promover(confirm=true, summary="...")
  → cd /desarrollo, git checkout main, git pull
  → git merge --no-ff develop -m "merge: promoción..."
  → git push origin main
  → cd /desarrollo, git checkout develop
→ Luis corre bash /compose/3-despliegue.sh
```

### Flujo 3: hotfix main → develop sync (circuito `produccion`)

```
Luis edita /compose
  → git add -A && git commit -m "hotfix: ..."  (en /compose)
→ run_hotfix_sync(confirm=true, summary="...")
  → git push origin main                          (en /compose)
  → git fetch origin + merge --no-ff origin/main  (en /desarrollo)
  → git push origin develop                       (en /desarrollo)
```

### Flujo 4: commit directo a main en orquestador (circuito `backend`)

```
Luis edita /contenedores/conti-backend
  → run_salvar(force_branch="main", confirm=true, summary="...")
  → git add -A && git commit -m "..." && git push origin main
```

## Flujos de code editing por circuito (Sprint 1.5)

### Circuito `desarrollo` (rama develop de contamela-stack)

```
1. Luis (o agente) edita archivos en /desarrollo
2. Pre-commit (recomendado):
   - cross_repo_search(query=<función a cambiar>, repos=["desarrollo"])
     → ver qué otros lugares usan la misma función
   - validate_python_syntax(paths=[<archivos_editados>])
     → confirmar sintaxis antes de commitear
3. run_salvar(confirm=true, summary="<conventional commit>")
4. push a origin/develop vía run_salvar

Restricciones:
- Solo edita dentro de /desarrollo.
- run_promover NO está habilitado acá (debe ir a circuito `produccion`).
```

### Circuito `produccion` (rama main + hotfix)

```
Para promover develop→main:
  1. Luis pide al agente: "promové develop→main con run_promover"
  2. run_promover(confirm=true) hace el merge dance
  3. Luis corre 3-despliegue.sh manualmente

Para hotfix en /compose:
  1. Luis edita /compose directamente (vim, IDE, etc.)
  2. git add -A && git commit -m "hotfix: ..."
  3. Luis pide al agente: "sincronizá con run_hotfix_sync"
  4. run_hotfix_sync(confirm=true) cierra el ciclo main→develop

Restricciones:
- /compose es RW SOLO para git (no para edits de código, salvo hotfix).
- Cambios de código en producción normalmente van por develop→main.
- 3-despliegue.sh solo Luis.
```

### Circuito `backend` (orquestador-contamela, solo main)

```
1. Luis (o agente) edita archivos en /contenedores/conti-backend
2. Pre-commit OBLIGATORIO (recomendado):
   a) validate_python_syntax(paths=[<archivos_editados>])
      → si falla, NO commitear. Arreglar primero.
   b) run_pytest(circuit="backend", test_path="tests/test_<módulo>.py")
      → validar que el test suite sigue verde
   c) run_pytest(circuit="backend")  # suite completa, antes del commit final
3. run_salvar(force_branch="main", confirm=true, summary="<conventional commit>")
4. push a origin/main vía run_salvar

Restricciones:
- Solo edita dentro de /contenedores/conti-backend.
- No hay flujo develop↔main (este repo solo tiene main).
- run_hotfix_sync NO aplica (no hay develop).
- run_promover NO aplica.
```

### Circuito `libre` (sin git)

```
- Conversacional, sin acceso a git.
- No puede usar gitops tools (filtradas por categoría).
- Si Luis pasa una ruta del host (ej: /mnt/nuevo-repo), trabajar ahí sin tocar git.
- Si la tarea requiere editar archivos: detectar primero el circuito
  correcto vía detect_circuit_from_path(path=...).
  Si devuelve circuit=None, pedir credenciales a Luis.
```

## Code editing tools (categoría `code_edit`)

| Tool | Uso típico | Circuitos |
|------|------------|-----------|
| `validate_python_syntax` | Antes de `run_salvar` en backend: confirmar que no hay syntax errors | backend, desarrollo, produccion |
| `run_pytest` | Después de editar: validar que los tests siguen pasando | backend, desarrollo, produccion |
| `detect_circuit_from_path` | Desde circuito `libre`: saber a qué circuito mandar una edición | libre |
| `cross_repo_search` | Búsqueda en vivo (no RAG) sobre los 3 repos: cuando el índice de Sourcebot está desactualizado | todos |

---

## Codebase Memory (Knowledge Graph)

**Herramienta**: `codebase-memory-mcp` v0.8.1 — binario estático C, sin deps.
**Transporte**: MCP stdio (omp lo lanza como subprocess).
**Ubicación**: `/home/conti/.local/bin/codebase-memory-mcp` (en conti-omp).

### Projects indexados

| Project | Path | Nodos | Edges |
|---------|------|-------|-------|
| `desarrollo` | `/desarrollo` | 153,281 | 560,947 |
| `compose` | `/compose` | 133,693 | 468,366 |
| `contenedores-conti-backend` | `/contenedores/conti-backend` | 4,360 | 8,605 |

### Tools principales

| Tool | Descripción | Ejemplo |
|------|-------------|---------|
| `search_graph` | Buscar por nombre/patrón regex | `search_graph(name_pattern=".*router.*", project="contenedores-conti-backend")` |
| `get_architecture` | Overview: languages, packages, routes, hotspots | `get_architecture(project="desarrollo")` |
| `trace_path` | Call graph (quién llama a qué) | `trace_path(function_name="run_task", direction="both")` |
| `get_code_snippet` | Leer source de una función | `get_code_snippet(qualified_name="contenedores-conti-backend.app.main")` |
| `query_graph` | Cypher queries sobre el knowledge graph | `query_graph(query="MATCH (f:Function)-[:CALLS]->(g) RETURN g.name")` |
| `detect_changes` | Mapear git diff a symbols afectados | `detect_changes(project="desarrollo")` |
| `search_code` | Grep semántico | `search_code(query="def run_task", project="contenedores-conti-backend")` |

### Cuándo usar

- **Antes de editar código**: `search_graph` o `get_architecture` para entender la estructura
- **Para encontrar dónde está algo**: `search_graph` con patrón regex
- **Para entender dependencias**: `trace_path` para ver call chains
- **Para dead code detection**: `query_graph` con `WHERE NOT EXISTS { (f)<-[:CALLS]-() }`
- **Para revisar cambios**: `detect_changes` antes de commitear

---

## Skills de omp

omp tiene 8 skills configuradas en `/home/conti/.omp/profiles/conti/skills/`.
omp las carga automáticamente como instrucciones.

### Skills genéricas (siempre disponibles)

| Skill | Descripción | Cuándo usar |
|-------|-------------|-------------|
| `mcp-backend-tools` | Acceso a las 73 MCP tools del backend vía bash+curl | Cuando necesites invocar cualquier MCP tool |
| `codebase-memory` | Knowledge graph de los 3 repos vía codebase-memory-mcp | Para buscar funciones, clases, call paths, architecture |
| `odoo-tools` | 21 tools para Odoo ERP (productos, clientes, pedidos, facturas) | Cuando el usuario pida consultar/crear/modificar datos de Odoo |
| `gitops-tools` | Tools para Git (commit, push, merge, hotfix) | Para operaciones Git seguras |
| `observability-tools` | Tools para trazas (Ponytail) | Al final de cada tarea para persistir la traza |

### Skills por circuito (cargadas según el circuito activo)

| Skill | Circuito | Workspace | Git action |
|-------|----------|-----------|------------|
| `circuit-desarrollo` | desarrollo | `/desarrollo` | `run_salvar` (commit+push develop) |
| `circuit-produccion` | produccion | `/compose` | `run_promover` (develop→main), `run_hotfix_sync` (main→develop) |
| `circuit-backend` | backend | `/contenedores/conti-backend` | `run_salvar` (commit+push main) |

### Cómo invocar MCP tools desde skills

Todas las skills usan el mismo patrón para invocar MCP tools:

```bash
curl -s -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"name": "TOOL_NAME", "arguments": {}}'
```

---

## Trazas de Ponytail (observabilidad)

### Ubicación de las trazas

| Circuito | Directorio de trazas | Rama | Notas |
|----------|----------------------|------|-------|
| `desarrollo` | `/desarrollo/.ponytail/traces/` | `develop` | Trazas generadas durante el flujo normal de desarrollo |
| `produccion` | `/compose/.ponytail/traces/` | `main` | Trazas generadas si el usuario edita archivos directamente en `/compose` (hotfix) |
| `backend` | `/contenedores/conti-backend/.ponytail/traces/` | `main` | Trazas de cambios en el orquestador |
| `libre` | `/tmp/free-agent/.ponytail/traces/` | — | Trazas temporales (no persisten entre reinicios) |

### Formato de las trazas
- **Nombre del archivo**: `YYYY-MM-DD_<circuito>_tr-<hash>.md`
  Ejemplo: `2026-07-01_desarrollo_tr-3de52a35bffa.md`.
- **Contenido**:
  - Frontmatter YAML con metadatos (timestamp, circuito, modelo LLM, duración).
  - Cuerpo en GFM con:
    - Mensajes de usuario/asistente.
    - Llamadas a herramientas (MCP y built-in).
    - Resultados de Sourcebot.
    - Eventos de omp (si `CONTI_USE_OMP_AGENT=true`).
  - Diagrama Mermaid de secuencia de herramientas.

### Cómo recuperar trazas

```bash
# Listar trazas en /desarrollo:
ls -la /desarrollo/.ponytail/traces/

# Ver una traza específica:
cat /desarrollo/.ponytail/traces/2026-07-01_desarrollo_tr-3de52a35bffa.md

# Buscar trazas por circuito:
grep -l "circuito: desarrollo" /desarrollo/.ponytail/traces/*.md
```

### Limpieza de trazas antiguas

```bash
# Eliminar trazas con más de 90 días en /desarrollo:
find /desarrollo/.ponytail/traces -name "*.md" -mtime +90 -delete

# Eliminar trazas con más de 90 días en /compose:
find /compose/.ponytail/traces -name "*.md" -mtime +90 -delete
```

**Frecuencia recomendada**: Ejecutar semanalmente vía `cron`.

## Hermes (legacy, sigue activo)

- 5 API servers (8766-8770) requieren `Authorization: Bearer` con
  `API_SERVER_KEY`.
- Cada perfil tiene su `API_SERVER_KEY` en
  `/app/hermes_profiles/contihome/profiles/<perfil>/.env`.
- El LLM emulado en `:9001` ya NO redirige a Hermes (regla PLAN_LLM v4).

## Flujos de sincronización

### Sincronización de `/desarrollo` (develop) con `/compose` (main)

**Objetivo**: Mantener `develop` actualizado con los cambios de `main` (producción).

```bash
# Desde /desarrollo:
git fetch origin
git reset --hard origin/main  # Sobrescribe develop con main (¡cuidado con cambios locales!)
git push origin develop --force
```

**Cuándo usarlo**:
- Después de un hotfix en `/compose`.
- Para asegurar que `develop` tenga los últimos cambios de producción.

---

### Sincronización de `conti-backend` con `orquestador-contamela`

**Objetivo**: Mantener el repositorio remoto `orquestador-contamela` actualizado con los cambios locales.

```bash
# Desde /contenedores/conti-backend:
./sync_upstream.sh  # Script de automatización
```

**Detalles del script `sync_upstream.sh`**:
```bash
#!/bin/bash
cd /contenedores/conti-backend
git fetch upstream
git merge upstream/main --no-ff -m "sync: sincronizar con orquestador-contamela"
git push upstream main
```

**Cuándo usarlo**:
- Después de implementar nuevas features en `conti-backend`.
- Antes de cerrar un sprint o hacer un release.

---

## Reglas operativas

Ver `docs/rules.md`. Resumen crítico:

- No usar SSH para operar repos bind-mounted.
- Toda mutación git va por tools dedicadas (run_salvar / run_promover /
  run_hotfix_sync).
- Deploy solo Luis: `bash /compose/3-despliegue.sh`.
- Idioma: Español.