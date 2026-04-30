# Planes Prioritarios para `conti-backend`

> Fecha: 2026-04-30  
> Prioridad actual: **iniciar por Plan 2**  
> Alcance de esta versión: definición técnica, fases, contratos, UI mínima, onboarding dinámico y reglas externas.  
> Fuera de alcance inmediato: Aider, Qdrant, automatización CI/CD compleja, dashboard grande, hardcodeo de prompts/reglas en Python.

---

# Resumen Ejecutivo

Este documento consolida los **dos planes prioritarios** para evolucionar `conti-backend` de forma incremental y controlada:

- **Plan 2**: envolver `conti-backend` como una plataforma `MCP + FastAPI`, con:
  - tools limpias y bien tipadas,
  - protocolo de **emulación de LLM** compatible con clientes estilo OpenAI,
  - onboarding externo y dinámico,
  - `rules.md` desacoplado del código,
  - UI web mínima para parámetros generales y exploración de tools MCP.
- **Plan 1**: ordenar la capa de **ClawTeam** para un equipo de 3 agentes (`Arquitecto`, `Desarrollador`, `DevOps`) con `profiles`, `presets`, `template TOML`, handoff y validación operativa.

La decisión estratégica es:

1. **No volver a reconstruir `backend-ai` completo**.
2. **No mezclar demasiadas responsabilidades en una sola capa**.
3. Construir una base liviana y extensible en `conti-backend`.
4. Dejar a futuro la incorporación opcional de un microservicio semántico adicional si hace falta.

---

# Principios Rectores

## 1. Nada crítico hardcodeado

Toda configuración sensible o variable debe vivir fuera del código Python:

- parámetros generales en archivo de configuración,
- onboarding en archivos Markdown/plantillas,
- reglas operativas en `rules.md`,
- tool schemas derivados del registro real,
- providers y endpoints en variables de entorno o config persistida.

## 2. El runtime debe ser observable y simple

El usuario debe poder entender el sistema desde:

- `health`,
- lista de tools MCP,
- configuración efectiva,
- reglas activas,
- onboarding cargado,
- proveedor/modelo/endpoint actualmente usados.

## 3. Búsqueda exacta y semántica no compiten

Para esta etapa base, el sistema debe quedar preparado para combinar:

- búsqueda exacta: `filesystem`, `read_file`, `ripgrep`, rutas, líneas, regex,
- recuperación semántica: futura o externa, no obligatoria para la primera implementación.

## 4. UI mínima, no un dashboard gigante

La UI web de esta fase debe servir solo para:

- cargar/editar parámetros generales,
- ver el estado del servidor,
- inspeccionar las tools MCP disponibles,
- ver onboarding y reglas cargadas,
- probar una tool con payload JSON simple.

## 5. Orquestación por capas

- capa 1: `nanobot` y gateway actual,
- capa 2: `FastAPI + MCP + emulación LLM`,
- capa 3: `ClawTeam` con 3 agentes,
- capa 4: microservicio semántico externo, si más adelante aporta valor real.

---

# PLAN 2 — Plataforma `MCP + FastAPI + Emulación LLM`

> **Este es el plan por el que se empieza.**  
> Objetivo: convertir `conti-backend` en una base limpia, extensible y operable para agentes y clientes externos.

---

## Objetivo del Plan 2

Construir dentro de `conti-backend` una capa `FastAPI` que unifique:

- exposición de tools MCP,
- API REST de operación,
- emulación de protocolo tipo OpenAI para clientes que no hablen MCP,
- entrega de prompts hacia un `nanobot` dedicado en modo `serve`,
- carga dinámica de onboarding y reglas,
- UI web mínima,
- configuración persistente y editable.

El resultado esperado es un servicio que pueda actuar como:

- backend de tools para `nanobot`,
- backend de tools para `ClawTeam`,
- punto de integración para IDEs o clientes que prefieren API tipo OpenAI,
- fachada de transporte delante de un `nanobot serve` especializado para responder como LLM del sistema,
- base para sumar luego RAG semántico sin reescribir la arquitectura.

---

## Resultado Esperado

Al finalizar el Plan 2, el proyecto debe ofrecer:

1. Un servidor `FastAPI` estable en un puerto dedicado.
2. Un registro de tools centralizado y tipado.
3. Endpoints MCP consistentes.
4. Endpoints de emulación OpenAI-style.
5. Carga de `onboarding` y `rules.md` desde archivos externos.
6. UI web mínima y limpia.
7. Configuración persistente sin valores sensibles hardcodeados.
8. Trazabilidad básica de requests, errores y configuración activa.
9. Un backend conversacional real basado en `nanobot serve`, separado del gateway.

---

## Alcance Funcional del Plan 2

### Incluye

- `FastAPI`
- registro de tools
- endpoints MCP básicos
- capa de emulación LLM compatible OpenAI-like
- bridge hacia `nanobot serve`
- onboarding externo
- reglas externas (`rules.md`)
- UI mínima
- configuración persistente
- herramientas base para filesystem, lectura, búsqueda literal, scraping y estado del sistema

### No incluye por ahora

- `Aider`
- `Qdrant`
- pipeline de deploy complejo
- dashboard grande tipo `backend-ai`
- protocolos múltiples avanzados si no son necesarios en la primera entrega
- automatización multiagente interna compleja dentro de esta misma capa

---

## Arquitectura Propuesta

## Topología Real que Debe Preservarse

La arquitectura del Plan 2 debe apoyarse en la topología real ya operativa del contenedor `clawteam-nanobot`, no en rutas abstractas nuevas.

### Bind mounts reales relevantes

- `/contenedores/conti_home -> /home/nanobot/`
- `/desarrollo -> /desarrollo`
- `/compose -> /compose:ro`
- `/contenedores/voice -> /code/voice`
- `./google-workspace -> /code/google-workspace`
- `./claw_data -> /app/data`
- `/desarrollo/config/team.toml -> /app/config/team.toml:ro`
- `/desarrollo/shared_skills -> /app/skills:ro`

### Implicancias para el diseño

1. El `HOME` bind-mounted de `/home/nanobot` se debe mantener intacto.
2. El repo de desarrollo en `/desarrollo` es el workspace modificable principal.
3. El repo de producción en `/compose` debe tratarse como fuente read-only.
4. El gateway actual y el futuro runtime `serve` deben compartir esta misma base.
5. La nueva capa `FastAPI` no debe reintroducir SSH ni workspaces artificiales para operar sobre esos repos.
6. La carpeta `apps`, si cuelga de estos roots operativos, no requiere una excepción especial en esta etapa.

### Visión General

```text
Cliente / IDE / Agente
        |
        |  (MCP o OpenAI-compatible)
        v
+-----------------------------+
| conti-backend FastAPI Core  |
|-----------------------------|
| - Config Loader             |
| - Tool Registry             |
| - MCP Router                |
| - LLM Emulation Router      |
| - Nanobot Serve Bridge      |
| - Onboarding Loader         |
| - Rules Loader              |
| - Minimal Web UI            |
+-----------------------------+
        |
        +--> Filesystem / Repo / Docs locales
        +--> Nanobot Gateway / perfiles
  +--> Nanobot dedicado en modo `serve`
        +--> Docker local (read-only al inicio)
        +--> Microservicios futuros opcionales
```

### Separación de capas internas

1. **Capa de Configuración**
   - carga de JSON/YAML/TOML del sistema,
   - resolución de variables de entorno,
   - validación de configuración.

2. **Capa de Dominio**
   - definición de tools,
   - schemas,
   - categorías,
   - políticas de visibilidad.

3. **Capa de Transporte**
   - `MCP` REST/JSON-RPC,
   - emulación `OpenAI-compatible`,
   - endpoints de UI.

4. **Capa de Backend Conversacional**
  - bridge a `nanobot serve`,
  - composición del contexto de sistema,
  - traducción entre contratos OpenAI-like y runtime `nanobot`.

5. **Capa de Presentación Web**
   - UI mínima.

6. **Capa de Integración**
   - acceso a filesystem,
   - `ripgrep`,
   - Docker local,
   - scraping,
   - futuro RAG externo.

---

## Tools MCP prioritarias de GitOps local

Además de filesystem, búsqueda literal y estado del sistema, la primera versión útil del backend debe incorporar desde el arranque estas tools MCP de GitOps local:

- `get_git_status`
- `get_git_log`
- `diff_with_develop`
- `get_pipeline_summary`
- `run_salvar`
- `run_promover`

### Criterio de migración

Estas tools se toman conceptualmente de `backend-ai`, pero en `conti-backend` deben reescribirse para operar **sin lógica SSH** y **sobre repos bind-mounted locales**.

### Reglas específicas para la migración

1. `run_salvar` debe trabajar sobre `/desarrollo` como repo editable principal.
2. `run_promover` debe promover desde el repo local ya montado, sin abrir sesión SSH al host.
3. `get_git_status` y `get_pipeline_summary` deben usar Git local del contenedor y reflejar branch, staged, modified y untracked.
4. `/compose` se considera referencia read-only y no destino de escritura directa.
5. La exportación o pasos auxiliares de n8n, si se preservan, deben hacerse contra contenedores/red local, nunca vía SSH.

## Backend Real de la Emulación LLM: `nanobot serve`

### Decisión de arquitectura

La emulación LLM del Plan 2 no debe resolver prompts directamente dentro del router `FastAPI`.  
Debe delegarlos a un **`nanobot` dedicado en modo `serve`**.

### Modelo de runtimes resultante

#### Runtime 1 — Gateway conti

- mantiene canales activos como Telegram,
- sigue siendo el punto de interacción operativo del bot principal,
- conserva acceso directo a `/desarrollo` y lectura de `/compose`.

#### Runtime 2 — LLM `serve`

- corre como backend conversacional para `POST /v1/chat/completions`,
- usa la misma base de configuración del gateway `conti`,
- comparte `HOME`, memoria y estructura persistida,
- no necesita canales externos habilitados,
- sirve como motor real detrás de la emulación OpenAI-like.

### Beneficio principal

Esto evita duplicar un segundo agente “falso” dentro de `FastAPI`: el servidor HTTP transporta y compone contexto, pero quien resuelve el prompt es un runtime real de `nanobot`.

---

## Estructura de Proyecto Propuesta

Dentro de `conti-backend`, la nueva capa debería vivir separada del runtime del `nanobot` upstream.

### Estructura sugerida

```text
/contenedores/conti-backend/
  app/
    main.py
    config/
      models.py
      loader.py
      defaults.py
    core/
      tool_registry.py
      tool_models.py
      categories.py
      visibility.py
    onboarding/
      loader.py
      templates/
        onboarding.md
        onboarding_brief.md
    rules/
      loader.py
      rules.md
      rules_clawteam.md
      rules_mcp.md
    mcp/
      router.py
      protocol.py
      schemas.py
    llm_emulation/
      router.py
      models.py
      streaming.py
      adapters.py
      nanobot_serve_bridge.py
    tools/
      filesystem.py
      search_literal.py
      code_context.py
      docs_search.py
      scraping.py
      system_status.py
      docker_tools.py
      config_tools.py
    web/
      router.py
      static/
      templates/
    services/
      settings_service.py
      onboarding_service.py
      rules_service.py
      llm_service.py
      nanobot_serve_service.py
      health_service.py
    utils/
      paths.py
      security.py
      logging.py
  config/
    app_config.json
    profiles.json
    ui_settings.json
  docs/
    onboarding.md
    rules.md
    tool_catalog.md
  tests/
    test_health.py
    test_mcp_tools.py
    test_llm_emulation.py
    test_config_loading.py
    test_rules_loader.py
    test_onboarding_loader.py
  README.md
```

---

## Protocolo de Emulación de LLM

Esta parte es clave porque permitirá conectar clientes que no usan MCP nativamente.

### Objetivo

Exponer una interfaz compatible con clientes estilo OpenAI para que puedan:

- listar modelos,
- pedir completions/chat,
- recibir respuestas estructuradas,
- usar tools indirectamente a través de prompts o funciones controladas,
- entregar el prompt resultante a un `nanobot` dedicado en modo `serve`.

### Backend de resolución

El backend principal de este protocolo debe ser `nanobot serve`. La capa `FastAPI` queda como:

- adaptador de protocolo,
- compositor de onboarding y reglas,
- resolvedor de perfil/modelo lógico,
- normalizador de respuesta.

### Endpoints mínimos recomendados

#### 1. `GET /v1/models`

Debe devolver los modelos disponibles de forma **dinámica**, tomando la configuración activa.

Ejemplo conceptual:

```json
{
  "object": "list",
  "data": [
    {
      "id": "conti-default",
      "object": "model",
      "owned_by": "conti-backend"
    },
    {
      "id": "conti-architect",
      "object": "model",
      "owned_by": "conti-backend"
    }
  ]
}
```

#### 2. `POST /v1/chat/completions`

Debe aceptar payload tipo OpenAI y resolverlo hacia:

- `nanobot serve`,
- provider configurado,
- o adaptador interno.

Debe soportar:

- `model`
- `messages`
- `temperature`
- `stream`
- `tools` o `functions` si se implementan después
- metadata opcional para trazabilidad

#### 3. `POST /v1/responses` (opcional pero recomendable)

Este endpoint mejora compatibilidad con clientes más nuevos.

#### 4. `GET /health`

Debe informar:

- estado del servidor,
- config cargada,
- onboarding activo,
- rules activas,
- tools registradas,
- provider/modelo activo,
- estado de integraciones opcionales,
- estado del backend `nanobot serve`.

### Modo de resolución recomendado

#### Modo principal — bridge a `nanobot serve`

La request que entra por emulación debe:

1. cargar configuración efectiva,
2. cargar onboarding efectivo,
3. cargar bloque de reglas efectivo,
4. componer el contexto del sistema,
5. entregar ese contexto al runtime `nanobot serve`,
6. normalizar la respuesta al contrato OpenAI-compatible.

#### Modo secundario — pass-through a provider configurado

Si el servidor está configurado con un provider compatible:

- `OpenAI-compatible`
- `Ollama`
- `Gemini`
- `Anthropic`

entonces la emulación despacha a ese provider.

Este modo debe quedar como fallback o modo de mantenimiento, no como camino principal.

### Perfil recomendado para el runtime `serve`

Conviene definir un perfil lógico específico, por ejemplo `conti-llm-serve`, que:

- herede la configuración general del gateway `conti`,
- conserve el mismo acceso a filesystem y repos bind-mounted,
- desactive canales no necesarios,
- sea el destino estable de la emulación LLM.

### Reglas de diseño para esta capa

- **Sin prompts hardcodeados** dentro del router.
- El router solo resuelve transporte y llama a servicios.
- El contenido de sistema se compone desde:
  - onboarding cargado,
  - `rules.md`,
  - perfil seleccionado,
  - parámetros efectivos.

  ### Entrega real del prompt

  El prompt final construido desde emulación debe entregarse al backend `serve`, no al gateway Telegram ni a lógica de negocio local del router.  
  Esa separación evita mezclar dos circuitos distintos:

  - circuito de mensajería del gateway,
  - circuito de inferencia/serve para clientes OpenAI-like.

### Streaming

Para compatibilidad futura, conviene prever `stream=true` con:

- `text/event-stream`,
- formato delta simple,
- cierre con mensaje final de terminación.

### Ventajas de esta capa

- permite usar IDEs que no soportan MCP,
- evita acoplar toda la experiencia a una sola interfaz,
- deja abierta la integración futura de microservicios semánticos,
- reutiliza el runtime real del proyecto en vez de inventar otra capa conversacional hardcodeada.

---

## Onboarding Dinámico

El onboarding debe dejar de estar incrustado en el código.

### Objetivo

Poder modificar contexto inicial del sistema sin tocar Python.

### Requisitos

- cargar desde archivo externo,
- soportar al menos versión `brief` y `full`,
- interpolar valores del entorno/config,
- ser visible desde la UI,
- permitir recarga sin rebuild.

### Archivos propuestos

```text
/docs/onboarding.md
/docs/onboarding_brief.md
```

### Contenido esperado del onboarding

- identidad del sistema,
- propósito general,
- árboles o rutas relevantes,
- reglas de uso de tools,
- límites de seguridad,
- flujo recomendado de trabajo,
- mención de integraciones activas.

### Variables interpolables

Ejemplos:

- `{workspace_root}`
- `{tools_count}`
- `{active_provider}`
- `{gateway_port}`
- `{web_ui_url}`

### Servicio de onboarding

El `onboarding_service` debe:

- leer archivo,
- validar existencia,
- interpolar variables,
- exponer versión efectiva,
- cachear y refrescar si cambia el archivo.

---

## `rules.md` Externo y No Hardcodeado

Esta es una pieza crítica.

### Objetivo

Las reglas operativas del sistema deben vivir en archivos versionados.

### Archivos propuestos

```text
/docs/rules.md
/docs/rules_clawteam.md
/docs/rules_mcp.md
```

### Principios

- `rules.md` es la fuente de verdad.
- El código solo lo carga y lo expone.
- Las reglas pueden combinarse por contexto.

### Tipos de reglas

#### Reglas globales

- seguridad,
- no destrucción,
- no hardcodeo,
- trabajo incremental,
- preferencia por inspección antes de modificación.

#### Reglas MCP

- usar solo tools registradas,
- no inventar tools,
- validar argumentos,
- respetar límites de lectura/escritura.

#### Reglas ClawTeam

- handoff por tasks,
- no ejecución fuera de rol,
- no mezclarse funciones entre arquitecto/dev/devops sin delegación explícita.

### Servicio de reglas

Debe poder:

- cargar uno o varios archivos,
- unirlos en un bloque final,
- exponerlos vía API,
- informar checksum/mtime,
- permitir recarga.

### Endpoints recomendados

- `GET /rules`
- `GET /rules/raw`
- `POST /rules/reload`

---

## UI Web Mínima

La UI debe ser muy limpia y chica.

### Objetivo

No recrear el dashboard de `backend-ai`, sino ofrecer una consola mínima.

### Pantallas recomendadas

#### 1. Home / Estado

Mostrar:

- nombre del sistema,
- versión,
- estado de salud,
- provider/modelo activo,
- onboarding cargado,
- rules cargadas,
- cantidad de tools registradas.

#### 2. Parámetros Generales

Formulario editable para:

- provider activo,
- modelo por defecto,
- endpoint base,
- flags de streaming,
- puertos,
- modo de onboarding,
- parámetros UI básicos,
- paths de docs/rules.

#### 3. Tools MCP

Tabla simple con:

- nombre,
- categoría,
- descripción,
- schema de entrada,
- estado (`enabled/disabled`),
- visibilidad (`public/internal/admin`).

#### 4. Inspector de Onboarding y Rules

Panel de solo lectura con:

- onboarding efectivo,
- rules efectivas,
- origen de archivos,
- botón de recarga.

#### 5. Ejecutor simple de Tool

Área para:

- elegir una tool,
- pegar JSON de argumentos,
- ejecutar,
- ver respuesta.

### Diseño visual

- fondo claro u oscuro neutro,
- sin animaciones innecesarias,
- layout de una sola columna o tabs simples,
- foco total en legibilidad.

### Tecnologías sugeridas

Para esta fase:

- HTML simple + JS liviano,
- o `Jinja2 + HTMX` si se quiere algo rápido,
- o mantener una SPA mínima si ya existe una base reutilizable.

**No conviene** una UI pesada para esta etapa.

---

## Registro de Tools MCP

### Objetivo

Definir un registro único de tools, con schemas y metadatos.

### Estructura por tool

Cada tool debería definir:

- `name`
- `description`
- `category`
- `input_schema`
- `visibility`
- `is_enabled`
- `handler`
- `tags`

### Categorías iniciales

- `filesystem`
- `search`
- `docs`
- `scraping`
- `system`
- `docker`
- `config`
- `agent-support`

### Visibilidad

- `public`: visible para clientes MCP y UI
- `internal`: usable por flujos internos
- `admin`: visible solo en UI/admin

### Tools mínimas recomendadas para la primera fase

#### Filesystem / lectura exacta

- `list_files`
- `read_file`
- `get_code_context`
- `file_exists`

#### Búsqueda literal

- `search_code_literal`
- `search_docs_literal`
- `grep_workspace`

#### Sistema

- `health_check`
- `get_config`
- `reload_config`
- `get_onboarding`
- `get_rules`

#### Docker / entorno

- `get_container_status`
- `get_container_logs`

#### Web / scraping

- `fetch_webpage_content`
- `extract_tables`
- `search_web` (opcional)

#### Futuro puente semántico

Reservar categorías para:

- `semantic_search_repo`
- `semantic_search_docs`
- `semantic_ingest`

pero no implementarlas todavía si el plan actual no las necesita.

---

## Configuración General

### Objetivo

Evitar configuración hardcodeada y permitir que la UI la edite.

### Archivo recomendado

```text
/config/app_config.json
```

### Bloques sugeridos

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 9001
  },
  "llm_emulation": {
    "enabled": true,
    "default_model": "conti-default",
    "streaming_enabled": true,
    "mode": "nanobot_serve",
    "serve_profile": "conti-llm-serve",
    "serve_base_url": "http://127.0.0.1:8765"
  },
  "providers": {
    "active": "openai_compatible",
    "openai_compatible": {
      "api_base": "${OPENAI_BASE_URL}",
      "api_key_env": "OPENAI_API_KEY"
    }
  },
  "paths": {
    "home_root": "/home/nanobot",
    "development_repo": "/desarrollo",
    "production_repo": "/compose",
    "onboarding_file": "/app/docs/onboarding.md",
    "onboarding_brief_file": "/app/docs/onboarding_brief.md",
    "rules_file": "/app/docs/rules.md"
  },
  "ui": {
    "enabled": true,
    "title": "Conti MCP Console"
  }
}
```

### Requisitos de configuración

- resolución de env vars,
- validación con Pydantic,
- persistencia tras edición desde UI,
- endpoint para ver configuración efectiva sin secretos,
- soporte explícito para declarar el backend `nanobot serve`.

### Parámetros de roots reales

La configuración efectiva debe mostrar de forma explícita:

- `/home/nanobot` como root persistente del usuario,
- `/desarrollo` como repo de trabajo modificable,
- `/compose` como repo de producción consultable en solo lectura.

La carpeta `apps` debe quedar cubierta por las reglas normales del root que la contenga, sin crear una vía separada salvo que aparezca una necesidad concreta más adelante.

---

## API y Contratos

### Endpoints recomendados

#### Sistema

- `GET /health`
- `GET /config`
- `PUT /config`
- `GET /onboarding`
- `POST /onboarding/reload`
- `GET /rules`
- `POST /rules/reload`

#### MCP

- `GET /mcp/tools`
- `POST /mcp/call`
- `POST /mcp/execute` (alias interno opcional)
- `POST /mcp` (JSON-RPC opcional si se decide soportarlo desde el inicio)

#### Emulación LLM

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses` (recomendado)
- `GET /llm/backend/status`
- `POST /llm/backend/reload`

#### UI

- `GET /ui`
- `GET /ui/tools`
- `GET /ui/settings`

---

## Seguridad del Plan 2

### Reglas mínimas

- sin escritura arbitraria en filesystem por defecto,
- herramientas mutativas desactivadas en la primera fase,
- allowlist de paths,
- ocultar secretos en `GET /config`,
- no exponer valores sensibles en UI,
- logs con request id y redacción de credenciales.

### Paths permitidos sugeridos

- `/home/nanobot`
- `/desarrollo`
- `/compose` (solo lectura)
- `/app/docs`
- `/app/skills`
- `/home/nanobot/.nanobot/workspace`

### Logs

- request id,
- endpoint,
- tool invocada,
- duración,
- estado,
- sin payloads sensibles completos.

---

## Estrategia de Implementación por Fases

### Fase 2.1 — Núcleo del servidor

Entregables:

- `FastAPI` base,
- `health`,
- carga de config,
- tool registry,
- endpoints MCP mínimos,
- modelado explícito del backend `nanobot serve`.

Criterio de aceptación:

- servidor levanta,
- responde `health`,
- lista tools,
- ejecuta una tool simple.

### Fase 2.2 — Onboarding y `rules.md`

Entregables:

- loader de onboarding,
- loader de rules,
- endpoints de consulta y recarga,
- interpolación dinámica.

Criterio de aceptación:

- cambiar `rules.md` no requiere editar Python,
- el sistema refleja la versión efectiva de onboarding y reglas.

### Fase 2.3 — Emulación LLM

Entregables:

- `GET /v1/models`,
- `POST /v1/chat/completions`,
- streaming básico opcional,
- bridge operativo a `nanobot serve`,
- health específico del backend `serve`.

Criterio de aceptación:

- cliente compatible puede usar el endpoint sin conocer MCP,
- el prompt se entrega efectivamente al runtime `nanobot serve` y no a lógica hardcodeada del router.

### Fase 2.4 — UI mínima

Entregables:

- pantalla estado,
- editor básico de parámetros,
- tabla de tools,
- visor de onboarding/rules,
- probador de tool.

Criterio de aceptación:

- la UI sirve realmente para operar el sistema sin necesidad de un dashboard complejo.

### Fase 2.5 — Endurecimiento

Entregables:

- tests,
- validaciones,
- sanitización de config,
- logs estructurados,
- documentación.

---

## Riesgos del Plan 2

### Riesgo 1 — volver a crecer como `backend-ai`

Mitigación:

- mantener el scope mínimo,
- no sumar dashboards grandes,
- no meter RAG pesado todavía.

### Riesgo 2 — acoplar emulación y MCP demasiado pronto

Mitigación:

- separar routers y servicios,
- compartir solo registry y config.

### Riesgo 3 — onboarding/rules derivados de strings internas

Mitigación:

- obligar por diseño a leer desde archivos.

### Riesgo 4 — UI sobredimensionada

Mitigación:

- restringir la UI a configuración y observación.

---

## Criterios de Aceptación del Plan 2

El Plan 2 se considera cumplido cuando:

1. Existe un `FastAPI` estable y autónomo dentro de `conti-nanobot`.
2. Las tools MCP están registradas y visibles desde API y UI.
3. El onboarding se carga desde archivos externos.
4. Las reglas se cargan desde `rules.md` y no están hardcodeadas.
5. La UI permite editar parámetros generales y ver tools MCP.
6. La emulación LLM responde con contrato tipo OpenAI-compatible.
7. El prompt de emulación se entrega a un `nanobot` dedicado en modo `serve`.
8. La topología real del contenedor se preserva: `HOME` bind-mounted, `/desarrollo` writable y `/compose` readonly.
9. La configuración efectiva puede inspeccionarse sin exponer secretos.

---

# PLAN 1 — Configuración de `ClawTeam` con 3 agentes

> Este plan se ejecuta después o en paralelo controlado con el Plan 2, pero apoyándose en la infraestructura que el Plan 2 deja ordenada.

---

## Objetivo del Plan 1

Configurar `ClawTeam` correctamente dentro de `conti-nanobot` para operar un equipo mínimo estable compuesto por:

- `Arquitecto`
- `Desarrollador`
- `DevOps`

con:

- `profiles` claros,
- `presets` reutilizables,
- template TOML correcto,
- roles bien definidos,
- ciclo de tareas y handoff reproducible.

---

## Problema actual a resolver

El estado actual muestra síntomas de configuración híbrida y no estándar:

- `team.toml` con sintaxis propia,
- templates locales no alineados con el formato upstream,
- `profiles` incompletos,
- `presets` vacíos,
- mezcla entre idea de equipo y realidad operativa del contenedor.

El Plan 1 debe corregir eso sin reescribir todo el proyecto.

---

## Resultado Esperado

1. `ClawTeam` usa `profiles` reales y persistidos.
2. Existe un template TOML válido para el equipo de 3 agentes.
3. Cada agente tiene rol, comando y parámetros claros.
4. La coordinación se hace con `team`, `task`, `inbox` y `board`, no por archivos ad hoc.
5. El equipo puede levantarse, verse en board y ejecutar un flujo básico de handoff.

---

## Roles del Equipo

### 1. Arquitecto

Responsabilidades:

- entender el objetivo,
- descomponer el problema,
- definir contratos de trabajo,
- decidir límites técnicos,
- derivar tareas al developer y al devops.

No debe:

- hacer cambios de infraestructura en caliente,
- reemplazar al developer,
- tomar tareas de ejecución prolongada salvo excepción.

### 2. Desarrollador

Responsabilidades:

- implementar cambios,
- leer y modificar código,
- validar consistencia técnica,
- producir entregables listos para revisión.

No debe:

- decidir arquitectura global sin validación del arquitecto,
- operar infraestructura crítica fuera de su alcance.

### 3. DevOps

Responsabilidades:

- revisar compose, puertos, variables y runtime,
- observar logs, salud y contenedores,
- preparar despliegues o rollbacks,
- verificar integraciones de entorno.

No debe:

- reescribir lógica de negocio,
- asumir tareas de arquitectura salvo validación.

---

## Profiles

### Objetivo

Tener perfiles reproducibles, no ad hoc.

### Profiles sugeridos

- `architect-nanobot`
- `developer-nanobot`
- `devops-nanobot`

### Parámetros por profile

Cada profile debe definir:

- `agent`
- `command`
- `args`
- `model`
- `base_url`
- `api_key_env`
- `env`
- `description`

### Recomendación

No definir manualmente un profile entero por cada caso si comparten runtime. Conviene:

- crear un `preset` común,
- derivar profiles específicos.

---

## Presets

### Objetivo

Evitar repetir endpoint, modelo y variables comunes.

### Preset sugerido

- `nanobot-openai-compatible`

### Qué debe concentrar

- endpoint base,
- api key env,
- defaults de command,
- variables comunes del runtime.

### Luego derivar

- `architect-nanobot`
- `developer-nanobot`
- `devops-nanobot`

con overrides pequeños.

---

## Template TOML del equipo

### Objetivo

Dejar un template compatible con `ClawTeam launch`.

### Estructura sugerida

```toml
[template]
name = "conti-core"
description = "Equipo base de 3 agentes para conti-nanobot"
command = ["nanobot", "agent"]
backend = "tmux"

[template.leader]
name = "architect"
type = "leader"
task = "Analizar el objetivo, generar plan y asignar tareas"

[[template.agents]]
name = "developer"
type = "executor"
task = "Implementar los cambios aprobados por arquitectura"

[[template.agents]]
name = "devops"
type = "executor"
task = "Validar entorno, runtime, contenedores y despliegue"

[[template.tasks]]
subject = "Diseño inicial"
description = "Arquitecto genera especificación y contratos"
owner = "architect"

[[template.tasks]]
subject = "Implementación"
description = "Developer ejecuta el plan definido"
owner = "developer"

[[template.tasks]]
subject = "Validación operativa"
description = "DevOps revisa salud, puertos, variables y ejecución"
owner = "devops"
```

---

## Flujo operativo recomendado

### Etapa 1 — creación del team

- crear el team,
- registrar líder,
- validar estado.

### Etapa 2 — spawn de agentes con profile

- levantar `architect`,
- levantar `developer`,
- levantar `devops`.

### Etapa 3 — board y tasks

- usar `board show` o `board serve`,
- verificar miembros,
- crear/actualizar tasks.

### Etapa 4 — handoff real

- `architect` redacta contrato,
- `developer` implementa,
- `devops` valida runtime.

### Etapa 5 — cierre

- tareas completadas,
- evidencia de ejecución,
- board consistente.

---

## Integración con el Plan 2

El Plan 1 debe usar la infraestructura del Plan 2:

- tools MCP visibles y tipadas,
- onboarding accesible,
- reglas externas,
- UI mínima de apoyo,
- emulación LLM lista para clientes externos.

### Sinergia buscada

- `ClawTeam` coordina,
- `MCP/FastAPI` provee herramientas,
- `nanobot` ejecuta,
- la UI deja ver qué herramientas y reglas están activas.

---

## Fases del Plan 1

### Fase 1.1 — sanear estado actual

- revisar mounts reales,
- revisar `HOME`,
- revisar `CLAWTEAM_DATA_DIR`,
- revisar `~/.clawteam/config.json`.

### Fase 1.2 — definir preset base

- consolidar endpoint/modelo/env.

### Fase 1.3 — crear profiles específicos

- arquitecto,
- developer,
- devops.

### Fase 1.4 — crear template TOML válido

- formato upstream,
- tareas base,
- roles coherentes.

### Fase 1.5 — prueba operativa controlada

- levantar el team,
- enviar tareas,
- revisar board,
- confirmar handoff.

---

## Riesgos del Plan 1

### Riesgo 1 — mezclar config vieja con nueva

Mitigación:

- migración explícita,
- backups,
- usar comandos oficiales.

### Riesgo 2 — perfiles sin separación real

Mitigación:

- descriptions claras,
- modelos/temperaturas diferenciadas,
- reglas por rol.

### Riesgo 3 — equipos lanzados sin task discipline

Mitigación:

- toda coordinación vía tasks e inbox,
- no por mensajes sueltos como única fuente de verdad.

---

## Criterios de Aceptación del Plan 1

1. Existen `profiles` funcionales para los 3 agentes.
2. Existe un `preset` reutilizable.
3. Existe un template TOML válido para `launch`.
4. El equipo aparece correctamente en `board`.
5. Un flujo simple `arquitecto -> developer -> devops` se ejecuta sin tocar archivos internos de estado a mano.

---

# Orden Recomendado de Ejecución

## Paso 1

Ejecutar **Plan 2 — Fase 2.1 y 2.2**:

- servidor,
- config,
- onboarding,
- rules.

## Paso 2

Ejecutar **Plan 2 — Fase 2.3 y 2.4**:

- emulación LLM,
- UI mínima,
- tools visibles.

## Paso 3

Ejecutar **Plan 1 — Fases 1.1 a 1.4**:

- preset,
- profiles,
- template.

## Paso 4

Prueba integrada:

- `ClawTeam` usa la capa MCP del Plan 2,
- el equipo de 3 agentes trabaja con tools reales y onboarding/rules externas.

---

# Decisión Final

Para esta etapa del proyecto:

- **Plan 2 es la base obligatoria**.
- **Plan 1 se apoya sobre Plan 2**.
- El sistema debe quedar preparado para sumar luego una capa semántica adicional sin rediseñar todo.
- Nada crítico debe depender de strings hardcodeadas dentro del código.

---

# Próximo Documento Recomendado

Una vez aprobado este documento, el siguiente entregable debería ser:

1. **Especificación de archivos concretos a crear para el Plan 2**.
2. **Contrato JSON de configuración**.
3. **Catálogo inicial de tools MCP**.
4. **Borrador de `rules.md` y `onboarding.md`**.
5. **Template TOML definitivo del equipo de 3 agentes**.
