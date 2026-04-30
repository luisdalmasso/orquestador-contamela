# Inventario de tools del backend anterior vs `conti-backend`

- Fuente comparada: `/contenedores/backend-ai/llamaindex/mcp/tool_registry.py`
- Total tools públicas legacy: **55**
- Total tools internas legacy: **4**
- Estado actual estimado en `conti-backend`: **10 migradas**, **13 parciales**, **36 no migradas**

## Criterio usado

- **Migrada**: existe hoy en `conti-backend` con capacidad equivalente y usable.
- **Parcial**: existe una capacidad cercana, pero no el mismo contrato, wrapper o nivel de automatización.
- **No**: no existe aún una migración utilizable en el backend nuevo.

## Code Intelligence

| Tool legacy | Descripción | Estado | Equivalente actual | Qué faltaría para cerrarla | Complejidad |
| --- | --- | --- | --- | --- | --- |
| `index_workspace` | Indexa un workspace de código en Qdrant con análisis AST. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `search_code` | Búsqueda semántica en el código indexado. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `hybrid_search` | Búsqueda híbrida: combina similitud semántica con búsqueda léxica. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `get_symbol_details` | Retorna detalles completos de una función, método o clase: signature, docstring, código fuente y ubicación exacta. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `find_type_definition` | Localiza la definición de un tipo, clase, interfaz o modelo. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `find_implementations` | Encuentra implementaciones de una interfaz o subclases de una clase base. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `list_package_exports` | Lista todos los símbolos exportados/públicos de un paquete o módulo. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `get_code_context` | Lee líneas específicas de un archivo directamente, sin necesidad de índice. | Parcial | `get_code_context` + `read_file` | La capacidad existe, pero no replica exactamente el contrato viejo (`file_path`, `start_line`, `end_line`). | Baja |
| `search_docs` | Busca en la documentación del proyecto (.md, .rst, .txt). | Parcial | `search_docs_literal` | Hoy es búsqueda literal/regex; faltaría ranking semántico o embeddings de docs. | Media |

## Governance

| Tool legacy | Descripción | Estado | Equivalente actual | Qué faltaría para cerrarla | Complejidad |
| --- | --- | --- | --- | --- | --- |
| `get_project_rules` | Retorna las reglas generales del proyecto: arquitectura, workflow, normas de código y pipeline de deploy. | Parcial | `get_rules`, `/rules`, `/onboarding` | Existe la fuente externa de reglas, pero no el alias exacto de tool legacy. | Baja |
| `get_coding_standards` | Retorna los estándares de código del proyecto: linting, formatting, naming conventions y reglas específicas del stack. | No | — | Requiere exponer wrappers o endpoints específicos sobre documentación/reglas internas. | Baja |
| `get_architecture_doc` | Retorna la documentación completa de arquitectura del stack (equivalent al stack-contamela.md). | Parcial | Documentación en `docs/` | Falta una tool dedicada que devuelva la doc de arquitectura consolidada. | Baja |
| `validate_diff` | Valida un diff de código contra las normas del proyecto. | No | — | Requiere exponer wrappers o endpoints específicos sobre documentación/reglas internas. | Baja |
| `check_stack_compliance` | Verifica si un cambio propuesto respeta el stack tecnológico aprobado del proyecto. | No | — | Requiere exponer wrappers o endpoints específicos sobre documentación/reglas internas. | Baja |
| `get_agent_rules` | Retorna las reglas específicas para el agente/IDE que llama. | No | — | Requiere exponer wrappers o endpoints específicos sobre documentación/reglas internas. | Baja |

## CI/CD

| Tool legacy | Descripción | Estado | Equivalente actual | Qué faltaría para cerrarla | Complejidad |
| --- | --- | --- | --- | --- | --- |
| `get_git_status` | Estado actual del repositorio local: rama, archivos modificados, staged y untracked. | Migrada | `get_git_status` | Ya disponible sobre `/desarrollo` con Git local, sin SSH. | Baja |
| `get_git_log` | Historial de commits recientes del repositorio. | Migrada | `get_git_log` | Ya disponible sobre repos montados localmente. | Baja |
| `diff_with_develop` | Muestra el diff entre el estado local y la rama develop. | Migrada | `diff_with_develop` | Ya disponible con Git local. | Baja |

## Sistema

| Tool legacy | Descripción | Estado | Equivalente actual | Qué faltaría para cerrarla | Complejidad |
| --- | --- | --- | --- | --- | --- |
| `health_check` | Verifica el estado de todos los servicios del stack: Qdrant, LLM y Embeddings. | Migrada | `health_check` | Ya disponible en MCP y `/health`. | Baja |
| `list_indexed_workspaces` | Lista todos los workspaces de código indexados en Qdrant con sus lenguajes. | No | — | Requiere reinstalar la capa de indexación/Qdrant o agregar wrappers dedicados. | Media |
| `reindex_workspace` | Fuerza la re-indexación completa de un workspace específico. | No | — | Requiere reinstalar la capa de indexación/Qdrant o agregar wrappers dedicados. | Media |

## VPS/Docker

| Tool legacy | Descripción | Estado | Equivalente actual | Qué faltaría para cerrarla | Complejidad |
| --- | --- | --- | --- | --- | --- |
| `get_vps_status` | Estado completo del VPS de producción: contenedores Docker corriendo, rama git actual, último commit. | Migrada | `get_vps_status` | Ya disponible con Docker local + Git montado; reemplaza SSH por socket Docker. | Media |
| `get_vps_diff_stat` | Muestra el diff --stat entre develop y main en el VPS. | Parcial | `diff_with_develop` | Falta una comparación explícita `develop -> main` y/o un target configurable de promoción. | Baja |
| `get_pipeline_summary` | Reorientación rápida del pipeline CI/CD. | Migrada | `get_pipeline_summary` | Ya disponible con pipeline local sobre `/desarrollo`. | Baja |
| `run_salvar` | Paso 1 del CI/CD: exporta workflows n8n modificados (delta) via SSH y hace commit + push a develop en GitHub. | Migrada | `run_salvar` | Ya disponible con preview + confirmación y push local. | Media |
| `run_promover` | Paso 2 del CI/CD: merge develop → main + push a GitHub, todo via SSH. | Migrada | `run_promover` | Ya disponible con preview + confirmación y merge local. | Media |
| `get_deploy_instructions` | Retorna las instrucciones para el deploy de producción (3-despliegue.sh). | No | — | Requiere portar el wrapper legacy específico y definir si opera por mounts locales o por Docker/SSH. | Media |
| `get_container_health` | Resumen de salud de TODOS los containers de un entorno (dev/prod/all). | Migrada | `get_container_health` | Ya disponible con SDK Docker sobre `/var/run/docker.sock`. | Media |
| `get_container_logs` | Lee los logs de cualquier container del VPS via SSH. | Migrada | `get_container_logs` | Ya disponible con filtros `container`, `since`, `lines`, `level`. | Media |
| `get_odoo_errors` | Shortcut de debugging para Odoo. | Parcial | `get_container_logs` | Falta el wrapper específico que agregue heurísticas y filtros de ruido para Odoo. | Baja |
| `get_django_errors` | Shortcut de debugging para Django API y Celery. | Parcial | `get_container_logs` | Falta el shortcut especializado para Django/Celery con filtros 5xx y Traceback. | Baja |
| `get_n8n_errors` | Shortcut de debugging para n8n. | Parcial | `get_container_logs` | Falta el shortcut especializado para ejecuciones fallidas y errores de nodos. | Baja |
| `get_wppconnect_errors` | Shortcut de debugging para wppconnect-server (WhatsApp Web API). | Parcial | `get_container_logs` | Falta el shortcut especializado para WhatsApp/WPPConnect. | Baja |

## Aider/Remote

| Tool legacy | Descripción | Estado | Equivalente actual | Qué faltaría para cerrarla | Complejidad |
| --- | --- | --- | --- | --- | --- |
| `execute_aider_task` | Ejecuta Aider en el VPS para modificar código según un prompt en lenguaje natural. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `lint_and_fix` | Ejecuta Aider en modo lint sobre un archivo del VPS. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `check_work_location` | Verifica si una ruta es válida para trabajar (en el VPS) o está prohibida (local). | Parcial | Allowlist local de paths | Ya hay validación de roots permitidos; falta exponerlo como tool legacy con mensajes guiados. | Baja |
| `run_remote_command` | Ejecuta un comando de validación en el VPS (/desarrollo) via SSH. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `get_remote_file` | Lee el contenido de un archivo del VPS directamente via SSH. | Parcial | `read_file` | Existe lectura local sobre mounts; falta la semántica remota/SSH del backend anterior. | Baja |

## Orquestación

| Tool legacy | Descripción | Estado | Equivalente actual | Qué faltaría para cerrarla | Complejidad |
| --- | --- | --- | --- | --- | --- |
| `write_dynamic_tool` | Permite a un Nanobot escribir su propia herramienta en Python si le falta una capacidad. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `delegate_task_to_orchestrator` | DELEGA una tarea compleja al Orquestador LlamaIndex. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `call_architect` | Delega una tarea de orquestación al architect_bot (gateway persistente, puerto 9111). | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `spawn_gateway` | Inicia el gateway persistente de un nanobot (canal Telegram activo). | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `kill_gateway` | Detiene el gateway persistente de un nanobot. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `spawn_nanobot` | Lanza un agente especialista con una tarea de dominio específica. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `get_agent_status` | Consulta el estado de una tarea asíncrona lanzada anteriormente mediante el agent_id. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `get_agent_report` | Obtiene el reporte detallado (stdout/stderr) de una tarea finalizada o en curso. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `set_mode` | ⚠️ EXCLUSIVA del architect_bot. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |

## Multimedia

| Tool legacy | Descripción | Estado | Equivalente actual | Qué faltaría para cerrarla | Complejidad |
| --- | --- | --- | --- | --- | --- |
| `transcribe_audio` | Transcribe audio a texto usando faster-whisper (modelo local, sin costo). | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `ocr_image` | Extrae texto de imágenes usando OCR local (pytesseract). | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `analyze_image` | Analiza y describe imágenes usando Replicate (Gemini Flash 2.0). | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `analyze_video` | Analiza videos usando Replicate (Gemini Flash 2.0). | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |

## Web Scraping

| Tool legacy | Descripción | Estado | Equivalente actual | Qué faltaría para cerrarla | Complejidad |
| --- | --- | --- | --- | --- | --- |
| `fetch_webpage_content` | Obtiene el contenido textual limpio de una URL (httpx + BeautifulSoup). | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `scrape_with_browser` | Scraping con playwright (Chromium headless) para páginas con JavaScript pesado. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `search_web` | Búsqueda web usando DuckDuckGo (sin API key). | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |
| `extract_tables` | Extrae tablas HTML de una URL y las convierte a JSON estructurado. | No | — | Requiere migrar handlers, dependencias y/o servicios auxiliares del `backend-ai` original. | Alta |

## Internas

| Tool legacy | Descripción | Estado | Equivalente actual | Qué faltaría para cerrarla | Complejidad |
| --- | --- | --- | --- | --- | --- |
| `propose_commit` | [INTERNO] Propone un commit para validación por el Gatekeeper. | No | — | Requiere exponer wrappers o endpoints específicos sobre documentación/reglas internas. | Baja |
| `get_pending_proposals` | [INTERNO] Lista propuestas de commit pendientes. | No | — | Requiere exponer wrappers o endpoints específicos sobre documentación/reglas internas. | Baja |
| `commit_to_develop` | [INTERNO] Ejecuta git add + commit + push a develop. | Parcial | `run_salvar` | La operación existe, pero el flujo legacy de propuestas internas no fue migrado. | Media |
| `promote_to_production` | [INTERNO] Merge develop → main + push (legado). | Parcial | `run_promover` | La promoción existe, pero no el nombre/contrato interno legado. | Media |

