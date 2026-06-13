# Plan 2 — Implementación Total en `conti-backend`

> Fecha: 2026-04-30
> Estado base: `conti-backend` es hoy un clon operativo de `conti-nanobot`, con `HOME` dedicado en `/contenedores/conti_home` y repos bind-mounted en `/desarrollo` y `/compose:ro`.
> Objetivo: ejecutar el Plan 2 completo sin romper el gateway actual, reemplazando progresivamente la capa improvisada por una plataforma propia `FastAPI + MCP + Emulación LLM + GitOps local`.

---

## Resultado final buscado

Al cerrar el Plan 2, `conti-backend` debe tener simultáneamente:

1. Un servicio `FastAPI` propio y estable.
2. Un catálogo MCP tipado y visible.
3. Tools locales de filesystem, búsqueda, sistema y GitOps.
4. Emulación OpenAI-compatible delegada a un `nanobot serve` dedicado.
5. `rules.md` y `onboarding` externos y recargables.
6. UI mínima para estado, settings y tools.
7. Sin SSH para operar los repos montados.
8. `/desarrollo` como repo writable principal.
9. `/compose` solo como referencia read-only.
10. Convivencia segura con el gateway actual mientras se migra.

---

## Hallazgos reales del estado actual

### Lo que ya existe y sirve

- Docker base funcional con Python, `tmux`, `git`, `node`, `nanobot` y `ClawTeam` instalados.
- `entrypoint.sh` ya levanta:
  - `nanobot gateway`
  - `clawteam board serve`
- `conti-backend` ya tiene bind mounts correctos hacia:
  - `/home/nanobot`
  - `/desarrollo`
  - `/compose:ro`
- La documentación maestra del plan ya está en `docs/PLAN_01_02_CONTI_NANOBOT.md`.

### Lo que falta para ejecutar Plan 2 de verdad

- No existe todavía una app propia `FastAPI` dentro de `conti-backend`.
- No existe un paquete Python raíz para esa app.
- El `requirements.txt` actual no declara explícitamente `fastapi`, `uvicorn` ni dependencias de UI/API.
- El `entrypoint.sh` actual no levanta:
  - servicio `FastAPI`
  - `nanobot serve` dedicado
- El `Dockerfile` raíz copia un `pyproject.toml` que no existe en la raíz del proyecto actual, por lo que antes de consolidar build conviene normalizar empaquetado.
- No existe todavía el registro MCP local ni los wrappers GitOps reescritos sin SSH.

---

## Estrategia óptima de ejecución

La implementación óptima no es construir todo junto. Hay que hacerlo en este orden:

1. **Normalizar build y runtime base.**
2. **Agregar el backend `FastAPI` mínimo sin tocar el gateway actual.**
3. **Agregar config, onboarding y rules externos.**
4. **Montar el registro MCP y las tools read-only.**
5. **Migrar GitOps local (`run_salvar`, `run_promover`, `get_git_status`, `get_pipeline_summary`).**
6. **Agregar el bridge a `nanobot serve`.**
7. **Exponer emulación OpenAI-compatible.**
8. **Agregar UI mínima.**
9. **Endurecer, testear y recién después unificar el arranque.**

Este orden minimiza riesgo porque deja la parte más invasiva (`serve` y GitOps mutativo) para cuando la base ya sea observable y testeable.

---

## Fase 0 — Saneamiento técnico previo

### Objetivo

Dejar listo el proyecto para que pueda hospedar una app Python propia sin ambigüedad entre runtime actual y backend nuevo.

### Decisiones recomendadas

#### 0.1 Crear un paquete Python propio para el backend

La app nueva debe vivir en una carpeta separada del upstream de `nanobot`.

Estructura objetivo:

```text
/contenedores/conti-backend/
  app/
    __init__.py
    main.py
    config/
    core/
    mcp/
    llm_emulation/
    onboarding/
    rules/
    services/
    tools/
    web/
    utils/
```

#### 0.2 Elegir una única estrategia de dependencias

La opción más simple para esta etapa es:

- mantener `requirements.txt` como manifiesto operativo del contenedor,
- agregar allí dependencias del backend nuevo,
- dejar una migración a `pyproject.toml` raíz para una etapa posterior.

Dependencias a sumar:

- `fastapi`
- `uvicorn[standard]`
- `jinja2`
- `python-multipart`
- `orjson`
- `sse-starlette`
- `pydantic-settings`

#### 0.3 Corregir el camino de build

Como el `Dockerfile` actual referencia un `pyproject.toml` inexistente en raíz, hay dos caminos posibles:

- **Camino recomendado inmediato:** no depender todavía de ese empaquetado para el backend nuevo; instalar el backend con `requirements.txt` + código copiado.
- **Camino posterior:** crear `pyproject.toml` raíz y empaquetar `app` formalmente.

### Criterio de cierre de Fase 0

- existe `app/`
- el proyecto puede importar `app.main`
- las dependencias de `FastAPI` están declaradas
- el contenedor puede construir sin depender de archivos inexistentes

---

## Fase 1 — Bootstrap del backend `FastAPI`

### Objetivo

Levantar un backend mínimo autónomo sin interferir con `nanobot gateway` ni `ClawTeam board`.

### Archivos a crear

```text
app/main.py
app/config/models.py
app/config/loader.py
app/services/health_service.py
app/utils/logging.py
config/app_config.json
tests/test_health.py
README.md
```

### Endpoints mínimos

- `GET /health`
- `GET /config`

### Contenido funcional mínimo

- cargar configuración con `Pydantic`
- exponer estado del backend
- mostrar roots reales:
  - `/home/nanobot`
  - `/desarrollo`
  - `/compose`
- reportar si el backend `serve` está o no configurado

### Arranque recomendado

No mezclar todavía todo en el mismo proceso. En esta fase conviene levantar el backend aparte, en otro puerto, por ejemplo `9001`.

### Comando esperado al terminar esta fase

```bash
uvicorn app.main:app --host 0.0.0.0 --port 9001
```

### Criterio de cierre

- el backend responde `200` en `/health`
- `GET /config` devuelve configuración efectiva redactando secretos
- el gateway actual sigue intacto

---

## Fase 2 — Configuración, onboarding y reglas externas

### Objetivo

Eliminar cualquier dependencia de prompts o políticas hardcodeadas.

### Archivos a crear

```text
config/app_config.json
config/profiles.json
docs/onboarding.md
docs/onboarding_brief.md
docs/rules.md
docs/rules_mcp.md
docs/tool_catalog.md
app/onboarding/loader.py
app/rules/loader.py
app/services/onboarding_service.py
app/services/rules_service.py
tests/test_onboarding_loader.py
tests/test_rules_loader.py
```

### Endpoints

- `GET /onboarding`
- `POST /onboarding/reload`
- `GET /rules`
- `GET /rules/raw`
- `POST /rules/reload`

### Reglas de implementación

- `rules.md` es la fuente de verdad.
- El backend solo carga, compone y expone.
- El onboarding se interpola con variables reales de config.
- No debe haber strings de sistema hardcodeadas dentro del router de emulación.

### Criterio de cierre

- editar `docs/rules.md` cambia la respuesta de `/rules` sin tocar Python
- `/onboarding` refleja la versión efectiva de onboarding

---

## Fase 3 — Registro MCP y tools read-only

### Objetivo

Construir el núcleo útil del backend antes de tocar GitOps mutativo.

### Archivos a crear

```text
app/core/tool_models.py
app/core/tool_registry.py
app/core/categories.py
app/core/visibility.py
app/mcp/router.py
app/mcp/schemas.py
app/tools/filesystem.py
app/tools/search_literal.py
app/tools/code_context.py
app/tools/system_status.py
app/tools/config_tools.py
tests/test_mcp_tools.py
```

### Tools iniciales obligatorias

#### Filesystem

- `list_files`
- `read_file`
- `file_exists`
- `get_code_context`

#### Búsqueda

- `search_code_literal`
- `search_docs_literal`
- `grep_workspace`

#### Sistema

- `health_check`
- `get_config`
- `reload_config`
- `get_onboarding`
- `get_rules`

### Endpoints

- `GET /mcp/tools`
- `POST /mcp/call`

### Regla de seguridad

Estas tools deben limitarse a:

- `/home/nanobot`
- `/desarrollo`
- `/compose` en lectura
- `/app/docs`
- `/app/skills`

### Criterio de cierre

- `/mcp/tools` lista schemas y metadatos
- se puede ejecutar `read_file` y `search_code_literal`
- la UI futura ya puede consumir el catálogo

---

## Fase 4 — GitOps local sin SSH

### Objetivo

Traer las tools que pediste como parte central del backend nuevo, pero reescritas para operar localmente sobre `/desarrollo`.

### Base a reutilizar conceptualmente

- `/contenedores/backend-ai/llamaindex/pipeline/git_ops.py`
- `/contenedores/backend-ai/llamaindex/pipeline/deploy.py`

### Qué migrar primero

#### Read-only

- `get_git_status`
- `get_git_log`
- `diff_with_develop`
- `get_pipeline_summary`

#### Mutativas con confirmación

- `run_salvar`
- `run_promover`

### Archivos a crear

```text
app/tools/git_tools.py
app/services/git_service.py
app/services/pipeline_service.py
tests/test_git_tools.py
```

### Reglas obligatorias

1. `run_salvar` opera sobre `/desarrollo`.
2. `run_promover` promueve desde el repo local montado.
3. No abrir SSH al host.
4. No escribir nunca en `/compose`.
5. `confirm=false` debe ser preview, nunca mutación.
6. Las validaciones previas deben ejecutar Git local, no shell remota.

### Secuencia recomendada

#### 4.1 Implementar primero solo lectura

- `get_git_status`
- `get_git_log`
- `diff_with_develop`
- `get_pipeline_summary`

#### 4.2 Implementar `run_salvar`

Debe hacer:

- preview de estado
- validación de repo y branch
- stage controlado
- commit generado desde `summary`
- push a `develop`

#### 4.3 Implementar `run_promover`

Debe hacer:

- preview de commits a promover
- diff `develop -> main`
- confirmación explícita
- merge y push

### Criterio de cierre

- `get_git_status` y `get_pipeline_summary` son consumibles desde MCP y UI
- `run_salvar(confirm=false)` no modifica nada
- `run_promover(confirm=false)` devuelve preview real
- mutaciones solo ocurren con confirmación explícita

---

## Fase 5 — Backend real de emulación con `nanobot serve`

> Estado actual: implementada la fachada y los tests unitarios del bridge. Falta validación contra un `nanobot serve` real en ejecución, que se hará cuando autorices arrancar el backend.

### Objetivo

Interponer `FastAPI` como fachada, pero delegando la resolución a un runtime real `nanobot serve`.

### Archivos a crear

```text
app/llm_emulation/models.py
app/llm_emulation/router.py
app/llm_emulation/streaming.py
app/llm_emulation/adapters.py
app/llm_emulation/nanobot_serve_bridge.py
app/services/llm_service.py
app/services/nanobot_serve_service.py
tests/test_llm_emulation.py
```

### Diseño obligatorio

- `FastAPI` compone onboarding + rules + perfil lógico.
- El prompt final viaja al runtime `serve`.
- El router no resuelve conversación por sí mismo.

### Endpoints

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `GET /llm/backend/status`
- `POST /llm/backend/reload`

### Runtime recomendado

Definir un perfil lógico estable, por ejemplo `conti-llm-serve`, basado en la misma configuración general del gateway, pero sin canales externos.

### Criterio de cierre

- un cliente OpenAI-compatible recibe respuesta válida
- el backend puede probar conectividad real hacia `nanobot serve`
- el prompt no se resuelve dentro del router

### Avance implementado

- `app/llm_emulation/router.py` expone `GET /v1/models`, `POST /v1/chat/completions`, `POST /v1/responses`, `GET /llm/backend/status` y `POST /llm/backend/reload`.
- `app/llm_emulation/nanobot_serve_bridge.py` encapsula el proxy HTTP hacia `nanobot serve`.
- `app/services/nanobot_serve_service.py` resuelve estado, modelos, completions y adaptación de `responses`.
- `tests/test_llm_emulation.py` valida proxy, adaptación y estado con stubs sin arrancar procesos reales.
- `POST /v1/responses` se implementa como compatibilidad sobre `POST /v1/chat/completions` porque el `nanobot serve` inspeccionado no expone `/v1/responses` nativo.

---

## Fase 6 — UI mínima operativa

> Estado actual: implementada.

### Objetivo

Dar observabilidad y operación básica, sin caer en un dashboard pesado.

### Archivos a crear

```text
app/web/router.py
app/web/templates/base.html
app/web/templates/index.html
app/web/templates/tools.html
app/web/templates/settings.html
app/web/templates/rules.html
app/web/static/app.css
app/web/static/app.js
```

### Pantallas mínimas

- Home/Estado
- Settings
- Tools MCP
- Onboarding/Rules
- Tool runner

### Datos que debe mostrar

- salud del backend
- estado del `nanobot serve`
- config activa redactada
- tools registradas
- onboarding efectivo
- rules efectivas
- estado Git básico

### Criterio de cierre

- un operador puede revisar estado, reglas y tools sin entrar al código

### Avance implementado

- `app/web/router.py` expone `GET /`, `GET /ui`, `GET /ui/settings`, `GET /ui/tools` y `GET /ui/rules`.
- Se agregaron templates y assets mínimos en `app/web/templates/` y `app/web/static/`.
- La UI muestra salud del backend, estado de `nanobot serve`, config redactada, catálogo MCP, onboarding, rules y estado Git básico.
- `Tool runner` permite invocar `POST /mcp/call` desde la UI.
- La pestaña `Nanobots` permite editar el perfil `defaults` y el provider activo para `gateway` y para un config dedicado de `nanobot serve`.

---

## Fase 7 — Unificación del runtime

> Estado actual: implementada con `entrypoint.sh` + `healthcheck` de compose.

### Objetivo

Recién cuando todo esté validado por separado, unificar el arranque del stack completo del nuevo backend.

### Procesos que deben convivir

1. `nanobot gateway`
2. `clawteam board serve`
3. `FastAPI` backend
4. `nanobot serve`

### Recomendación operativa

Mantener un `entrypoint.sh` con procesos en background es aceptable al principio, pero la versión más robusta debería evolucionar a:

- `supervisord`, o
- un `tmux` controlado, o
- `s6-overlay`

Para la primera entrega completa, un `entrypoint.sh` bien controlado con healthchecks alcanza.

### Criterio de cierre

- el contenedor levanta los cuatro procesos esperados
- hay healthchecks visibles para backend y `serve`

### Avance implementado

- `entrypoint.sh` levanta `nanobot gateway`, `nanobot serve`, `FastAPI` backend y `clawteam board serve`.
- `gateway` usa `/home/nanobot/config.json` y `nanobot serve` usa `/home/nanobot/llm_serve_config.json` con bootstrap automático desde la config legacy si hace falta.
- `docker-compose.conti.yml` publica `8080`, `8765`, `9001` y `18790`.
- `docker-compose.conti.yml` incorpora `healthcheck` para `http://127.0.0.1:9001/health` y `http://127.0.0.1:8765/health`.

---

## Fase 8 — Tests, endurecimiento y cierre

### Tests mínimos obligatorios

- `test_health.py`
- `test_config_loading.py`
- `test_rules_loader.py`
- `test_onboarding_loader.py`
- `test_mcp_tools.py`
- `test_git_tools.py`
- `test_llm_emulation.py`

### Endurecimiento mínimo

- redactar secretos en `/config`
- allowlist de paths
- logs estructurados con request id
- timeouts para tools y bridge
- validación fuerte de payloads
- `confirm` obligatorio en tools mutativas

### Criterio de cierre del Plan 2

El Plan 2 está completo cuando:

1. `FastAPI` existe y es autónomo.
2. MCP lista y ejecuta tools reales.
3. `rules.md` y onboarding son externos.
4. GitOps local funciona sin SSH.
5. `run_salvar` y `run_promover` están disponibles con preview + confirmación.
6. La emulación OpenAI-compatible usa `nanobot serve` real.
7. La UI mínima opera el backend.
8. La topología real se preserva intacta.

---

## Orden exacto recomendado de ejecución

### Semana técnica 1

1. Fase 0
2. Fase 1
3. Fase 2

### Semana técnica 2

4. Fase 3
5. Fase 4 read-only
6. Fase 4 mutativa (`run_salvar`)

### Semana técnica 3

7. Fase 4 mutativa (`run_promover`)
8. Fase 5 (`nanobot serve`)
9. Fase 6 (UI)

### Semana técnica 4

10. Fase 7
11. Fase 8
12. hardening y smoke test final

---

## Archivos que conviene crear primero

Si hay que arrancar ya mismo, el mejor primer lote es:

```text
app/main.py
app/config/models.py
app/config/loader.py
app/core/tool_registry.py
app/mcp/router.py
app/tools/filesystem.py
app/services/health_service.py
config/app_config.json
docs/rules.md
docs/onboarding.md
tests/test_health.py
```

Ese lote deja listo el esqueleto que habilita todo lo demás.

---

## Qué no hacer durante la implementación

- No revivir `backend-ai` entero.
- No reintroducir SSH para operar repos montados.
- No meter Qdrant ni Aider en esta etapa.
- No construir un dashboard grande.
- No mezclar la lógica del gateway con la de `nanobot serve`.
- No empezar por `run_promover` antes de que exista observabilidad Git local.

---

## Próxima ejecución recomendada

El siguiente paso óptimo, concreto y ejecutable, es:

1. crear el esqueleto `app/`
2. agregar dependencias de `FastAPI`
3. levantar `GET /health` y `GET /config`
4. crear `rules.md` y `onboarding.md`
5. montar el `tool_registry`

Ese es el punto exacto donde Plan 2 deja de ser diseño y pasa a implementación real.
