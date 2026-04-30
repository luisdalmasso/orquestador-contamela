# Conti Backend

Backend incremental para ejecutar el Plan 2 sobre `conti-backend`.

## Estado actual

Esta entrega implementa la base de Fase 0, Fase 1, Fase 2, Fase 3, Fase 4 completa y la base funcional de Fase 5:

- `FastAPI` mínimo en `app/`
- `GET /health`
- `GET /config`
- `GET /onboarding`
- `POST /onboarding/reload`
- `GET /rules`
- `GET /rules/raw`
- `POST /rules/reload`
- `GET /mcp/tools`
- `POST /mcp` (JSON-RPC 2.0 legacy para VS Code/Amazon Q)
- `POST /mcp/call`
- `GET /mcp`
- `POST /mcp/execute`
- `GET /mcp/sse` (SSE legacy para Kilocode/Cline)
- `GET /v1`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `GET /llm/backend/status`
- `POST /llm/backend/reload`
- `GET /ui`
- `GET /ui/settings`
- `GET /ui/tools`
- `GET /ui/rules`
- `GET /ui/nanobots`
- carga de configuración desde `config/app_config.json`
- carga externa de onboarding y reglas con fallback host/contenedor
- registro MCP centralizado con tools read-only
- tools Git read-only sobre `/desarrollo` (`get_git_status`, `get_git_log`, `diff_with_develop`, `get_pipeline_summary`)
- observabilidad Docker local (`get_container_health`, `get_container_logs`, `get_vps_status`) usando el socket Docker montado
- tools Git mutativas con preview+confirmación (`run_salvar`, `run_promover`)
- bridge HTTP hacia `nanobot serve` para emulación OpenAI-compatible
- adaptación de `/v1/responses` sobre `/v1/chat/completions`
- UI mínima operativa del backend en `app/web/`
- edición de config `gateway` y `llm serve` desde la pestaña `Nanobots`
- aliases MCP legacy para compatibilidad con el backend anterior
- `GET /mcp` devuelve `text/event-stream` cuando el cliente envía `Accept: text/event-stream`
- `POST /mcp` acepta `initialize`, `tools/list`, `tools/call` y `ping` en formato JSON-RPC 2.0
- test básico con `pytest`

## Estado de Fase 5

- La fachada OpenAI-compatible ya existe en `app/llm_emulation/`.
- `GET /v1/models` y `POST /v1/chat/completions` actúan como proxy hacia `nanobot serve`.
- `POST /v1/responses` se emula a partir de `chat completions` porque el `serve` inspeccionado no expone `/v1/responses` nativo.
- `stream=true` está soportado en `chat completions` y todavía no en `/v1/responses`.
- No se arrancó el backend real ni `nanobot serve` en esta etapa.

## Estado de Fase 6 y 7

- El backend ahora expone panel web propio en `http://127.0.0.1:9001/ui`.
- La UI muestra estado, settings, tools, onboarding/rules y estado Git básico.
- La pestaña `Nanobots` permite editar `/home/nanobot/.nanobot/config.json` para `gateway` y `/home/nanobot/llm_serve_config.json` para `nanobot serve`.
- El contenedor unificado expone `gateway`, `clawteam`, `FastAPI` y `nanobot serve`.
- El backend también queda publicado en `http://127.0.0.1:9007` para compatibilidad con clientes del backend anterior.
- La base OpenAI-compatible legacy queda disponible en `http://127.0.0.1:9007/v1`.
- `docker-compose.conti.yml` incluye un `healthcheck` que valida `9001/health` y `8765/health`.

## Ejecutar localmente

```bash
cd /contenedores/conti-backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9001
```

## Ejecutar tests

```bash
cd /contenedores/conti-backend
PYTHONPATH=/contenedores/conti-backend python3 -m pytest -q tests/test_health.py tests/test_mcp_tools.py tests/test_git_tools.py tests/test_llm_emulation.py

PYTHONPATH=/contenedores/conti-backend python3 -m pytest -q tests/test_config_loading.py tests/test_web_ui.py
```

La suite global del workspace incluye `nanobot/tests` upstream y hoy no es un criterio útil para este backend porque depende de módulos y extras no instalados en esta imagen.
