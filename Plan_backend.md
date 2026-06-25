# Plan de Arquitectura de Agentes - Análisis Estratégico

## 1. Diagnóstico de la Situación Actual

### Problemas Identificados
- **Acoplamiento excesivo**: Un único perfil de Hermes maneja tanto desarrollo como atención al cliente
- **Falta de trazabilidad**: No hay registro de decisiones técnicas ni evolución de proyectos
- **Inestabilidad de agentes clientes**: Dependencia de prompts estocásticos en lugar de flujos deterministas
- **Gestión de tokens**: Costos elevados al procesar repositorios extensos
- **Canal WhatsApp**: Necesidad de integración estable con Baileys

---

## 2. Análisis Detallado de Herramientas

### 2.1 bytedance/UI-TARS

| Característica | Detalle |
|---------------|---------|
| **Propósito** | Agente de interfaz gráfica (GUI Agent) que puede ver y operar en interfaces visuales como un humano |
| **Madurez** | Proyecto reciente (2024), con demostraciones activas pero en fase de investigación |
| **Fortalezas** | - Interacción con navegadores y aplicaciones visuales<br>- Útil para automatización de tareas en UI<br>- Integración con modelos multimodales |
| **Debilidades** | - Requiere entorno gráfico/X11<br>- Alto consumo de recursos (modelos vision)<br>- No especializado en backend/dev |
| **Requisitos** | - Modelo multimodal (GPT-4V, Qwen-VL)<br>- Entorno gráfico o virtual<br>- Sistema de coordenadas y captura de pantalla |
| **Costos/Latencia** | Alto - cada interacción implica procesamiento de imágenes |
| **Encaje Codevibing** | ⭐⭐ - Solo útil para tareas de automatización web (ej. publicación en redes) |
| **Encaje Marketing** | ⭐⭐⭐⭐ - Automatización de publicaciones, interacción con plataformas |
| **Encaje Agentes Clientes** | ⭐ - No aplica |
| **Riesgo Complejidad** | Medio - requiere infraestructura gráfica adicional |
| **Recomendación** | **COMPLEMENTAR** - Solo para casos específicos de automatización visual |

---

### 2.2 coze-dev/coze-studio y coze-dev/coze-loop

| Característica | Detalle |
|---------------|---------|
| **Propósito** | Plataforma de desarrollo de agentes conversacionales con flujos visuales y gestión de proyectos |
| **Madurez** | Producción - plataforma comercial de ByteDance |
| **Fortalezas** | - Interfaz visual para crear flujos de conversación<br>- Gestión de proyectos integrada<br>- Plugins y extensiones<br>- Multi-canal (Telegram, Web, etc.) |
| **Debilidades** | - Enfocado en chatbots, no en desarrollo de software<br>- No soporta Baileys/WhatsApp directamente<br>- Arquitectura cerrada |
| **Requisitos** | - Cuenta en plataforma Coze<br>- API keys<br>- Infraestructura cloud |
| **Costos/Latencia** | Pago por uso - depende del volumen de mensajes |
| **Encaje Codevibing** | ⭐⭐ - Limitado, no está diseñado para tareas de desarrollo |
| **Encaje Marketing** | ⭐⭐⭐⭐ - Muy bueno para flujos de campañas y nurturing |
| **Encaje Agentes Clientes** | ⭐⭐⭐ - Bueno para flujos pero sin WhatsApp |
| **Riesgo Complejidad** | Bajo - plataforma gestionada |
| **Recomendación** | **EXCLUIR** - No aporta valor único sobre Deer-Flow + Baileys custom |

---

### 2.3 bytedance/deer-flow

| Característica | Detalle |
|---------------|---------|
| **Propósito** | Framework de agentes basado en LangChain con grafos de estado (DAGs) y observabilidad |
| **Madurez** | Activo, basado en LangChain (estándar de la industria) |
| **Fortalezas** | - Grafos de estado deterministas (elimina "discolia")<br>- Integración con LangSmith y Langfuse<br>- Soporte Telegram nativo<br>- Arquitectura modular<br>- Buenas prácticas de ingeniería |
| **Debilidades** | - No tiene soporte Baileys/WhatsApp nativo<br>- Curva de aprendizaje de LangChain<br>- Requiere adaptación del bridge actual |
| **Requisitos** | - Python 3.9+<br>- LangChain<br>- LangSmith/Langfuse (opcional)<br>- Servidor MCP existente |
| **Costos/Latencia** | Bajo - framework open source |
| **Encaje Codevibing** | ⭐⭐⭐ - Útil para flujos de trabajo pero no para ejecución directa |
| **Encaje Marketing** | ⭐⭐⭐⭐ - Excelente para workflows de contenido y campañas |
| **Encaje Agentes Clientes** | ⭐⭐⭐⭐⭐ - **IDEAL** - Control de estados, trazabilidad, previsibilidad |
| **Riesgo Complejidad** | Medio - requiere adaptación del bridge de WhatsApp |
| **Recomendación** | **ADOPTAR** - Núcleo para agentes clientes, con adaptación Baileys |

---

### 2.4 HKUDS/DeepCode

| Característica | Detalle |
|---------------|---------|
| **Propósito** | Sistema de análisis estático de código con IA para detección de bugs y vulnerabilidades |
| **Madurez** | Investigación académica, repositorio con demostraciones |
| **Fortalezas** | - Análisis profundo de código<br>- Detección de bugs complejos<br>- Integración con LLMs |
| **Debilidades** | - Enfocado en análisis, no en ejecución<br>- No es un agente autónomo<br>- Requiere integración manual |
| **Requisitos** | - Modelos LLM especializados<br>- Integración con pipeline CI/CD |
| **Costos/Latencias** | Medio - análisis intensivo de código |
| **Encaje Codevibing** | ⭐⭐⭐⭐ - Complemento para calidad de código |
| **Encaje Marketing** | ⭐ - No aplica |
| **Encaje Agentes Clientes** | ⭐ - No aplica |
| **Riesgo Complejidad** | Bajo - herramienta de análisis puntual |
| **Recomendación** | **COMPLEMENTAR** - Integrar como paso de validación en el flujo de desarrollo |

---

### 2.5 can1357/oh-my-pi

| Característica | Detalle |
|---------------|---------|
| **Propósito** | Optimización de tokens y gestión de ventana de contexto para LLMs |
| **Madurez** | Activo, solución comunitaria |
| **Fortalezas** | - Reducción drástica de costos de tokens<br>- Filtrado inteligente de contexto<br>- Integración con sistemas existentes<br>- Estrategia RAG dinámico |
| **Debilidades** | - Requiere configuración fina<br>- Puede omitir contexto relevante si mal configurado |
| **Requisitos** | - Integración con pipeline LLM<br>- Configuración de reglas de filtrado |
| **Costos/Latencia** | Muy bajo - ahorro de tokens |
| **Encaje Codevibing** | ⭐⭐⭐⭐⭐ - **ESencial** - Optimización de costos |
| **Encaje Marketing** | ⭐⭐⭐ - Útil para contexto de marcas |
| **Encaje Agentes Clientes** | ⭐⭐ - Menos crítico |
| **Riesgo Complejidad** | Bajo - middleware de optimización |
| **Recomendación** | **ADOPTAR** - Capa de optimización obligatoria |

---

### 2.6 crewAIInc/crewAI

| Característica | Detalle |
|---------------|---------|
| **Propósito** | Framework de agentes múltiples con roles y tareas colaborativas |
| **Madurez** | Producción - amplia adopción comunitaria |
| **Fortalezas** | - Roles predefinidos (analista, redactor, etc.)<br>- Flujos colaborativos<br>- Integración con herramientas existentes<br>- Menos burocrático que Paperclip |
| **Debilidades** | - No tiene control de estados estricto como Deer-Flow<br>- Puede ser caótico sin buenas definiciones de roles |
| **Requisitos** | - Python<br>- LLM API keys<br>- Definición de agentes y tareas |
| **Costos/Latencia** | Bajo - framework open source |
| **Encaje Codevibing** | ⭐⭐⭐⭐ - **IDEAL** - Roles especializados para tareas de desarrollo |
| **Encaje Marketing** | ⭐⭐⭐⭐⭐ - **IDEAL** - Equipo de agentes para campañas |
| **Encaje Agentes Clientes** | ⭐⭐ - No recomendado, falta control de estados |
| **Riesgo Complejidad** | Bajo - framework estable |
| **Recomendación** | **ADOPTAR** - Núcleo para marketing y codebiving |

---

### 2.7 EveryInc/compound-engineering-plugin

| Característica | Detalle |
|---------------|---------|
| **Propósito** | Plugin que añade rigor de ingeniería a agentes LLM (ciclo Plan-Implement-Test-Document) |
| **Madurez** | Activo, solución emergente |
| **Fortalezas** | - Obliga a flujo estructurado de trabajo<br>- Evita improvisación del LLM<br>- Integración con sistemas existentes<br>- Documentación automática |
| **Debilidades** | - Requiere adaptación<br>- Puede ser restrictivo en creatividad |
| **Requisitos** | - Integración con agente<br>- Definición de workflows |
| **Costos/Latencia** | Muy bajo - middleware de orquestación |
| **Encaje Codevibing** | ⭐⭐⭐⭐⭐ - **ESencial** - Rigor en desarrollo |
| **Encaje Marketing** | ⭐⭐⭐ - Útil para estructura de campañas |
| **Encaje Agentes Clientes** | ⭐ - No aplica |
| **Riesgo Complejidad** | Bajo - plugin de workflow |
| **Recomendación** | **ADOPTAR** - Capa de rigor para codebiving |

---

### 2.8 agent-infra/sandbox

| Característica | Detalle |
|---------------|---------|
| **Propósito** | Entorno aislado y seguro para ejecución de código de agentes |
| **Madurez** | Activo, solución de infraestructura |
| **Fortalezas** | - Seguridad en ejecución<br>- Aislamiento de procesos<br>- Control de recursos |
| **Debilidades** | - Añade complejidad operativa<br>- Puede impactar rendimiento |
| **Requisitos** | - Docker/containerización<br>- Configuración de permisos |
| **Costos/Latencia** | Bajo - infraestructura existente |
| **Encaje Codevibing** | ⭐⭐⭐⭐ - Útil para ejecución segura |
| **Encaje Marketing** | ⭐⭐ - Menos crítico |
| **Encaje Agentes Clientes** | ⭐⭐⭐ - Seguridad en operaciones |
| **Riesgo Complejidad** | Medio - infraestructura adicional |
| **Recomendación** | **COMPLEMENTAR** - Para entornos de producción |

---

### 2.9 Hyperion-GPU/ProofFlow-v0.1

| Característica | Detalle |
|---------------|---------|
| **Propósito** | Framework de verificación y prueba de código con LLMs |
| **Madurez** | v0.1 - fase experimental |
| **Fortalezas** | - Enfoque en tests automáticos usando LLMs<br>- Generación de casos de prueba y verificación de regresiones |
| **Debilidades** | - Incipiente, cobertura limitada<br>- Requiere integración con pipelines de CI |
| **Requisitos** | - Acceso a LLMs para generar/validar tests<br>- Integración con repositorios y runners |
| **Costos/Latencia** | Medio - depende del tamaño del código a verificar |
| **Encaje Codevibing** | ⭐⭐⭐ - Útil para pruebas automatizadas de entregables |
| **Encaje Marketing** | ⭐ - No aplica |
| **Encaje Agentes Clientes** | ⭐ - No aplica |
| **Riesgo Complejidad** | Bajo - experimental pero manejable |
| **Recomendación** | **COMPLEMENTAR** - Usar en pipelines de QA para validar entregas |

--- 

## 3. Inventario detallado del contenedor

- **Archivo**: `docker-compose.conti.yml`
- **Servicio**: `conti-backend`
- **Montajes**: `./app/hermes_profiles` (perfiles persistentes), `./conti_home`, `./google-workspace`, `./voice`
- **Puertos expuestos**: `9001` (FastAPI/LMM), `8766-8770` (gateways por perfil), `8642`, `18791`, `9119` (dashboard)
- **Recursos**: `mem_limit: 24g`, `cpus: 4`

- **Archivo**: `entrypoint_hermes.sh`
- **Comportamiento**: Inicia `uvicorn` en `:9001`, espera el endpoint `/health` y `/mcp` y luego lanza gateways Hermes por perfil:
	- `catolico`: puerto `8766`
	- `resto`: puerto `8767`
	- `odoo`: puerto `8768`
	- `odoo-resto`: Telegram only
	- `odoo-nudo`: Telegram only
	- `odoo-mendoza`: puerto `8769` + Telegram
	- `mendoza`: puerto `8770` + WhatsApp (wppconnect)
	- `contihome`: puerto `18791` (default) y `9119` (dashboard)

- **Perfiles inspectados**: `resto`, `odoo-resto`, `mendoza`, `odoo-mendoza`, `odoo-nudo`, `odoo`, `catolico`
- **Artefactos persistentes por perfil**: `config.yaml`, `skills/`, `memories/`, `state.db`, `auth.json`, `hooks/`, `response_store.db` (en `mendoza`)

## 4. Checklist de migración inmediata

1. Confirmar adaptador WhatsApp en `mendoza` (`auth.json` y `hooks/`) — wppconnect vs Baileys.
2. Crear `migration_manifest/` con:
	 - `config.yaml` por perfil
	 - lista de `skills/` y `hooks/`
	 - mapping de canales y puertos
3. Realizar backups comprimidos por perfil en `./compose/documentos_listos/migration_backups/`.
4. Preparar PoC: DeerFlow + adaptación Baileys para WhatsApp bridge.
5. Integrar `oh-my-pi` como capa de optimización de tokens.
6. Preparar sandbox para Codevibing (CrewAI + compound-engineering-plugin).

## 5. Próximos pasos

- Crear `migration_manifest/` y backups por perfil (requiere tu confirmación).
- Auditar `mendoza` hooks y `auth.json` para confirmar estrategia WhatsApp.
- Planificar PoC de DeerFlow + Baileys y un PoC separado para Codevibing con CrewAI.

## 6. Inventario por perfil (detallado)

Nota: para cada perfil indico la ruta base, artefactos persistentes detectados y observaciones operativas relevantes para la migración.

- **`catolico`** (`app/hermes_profiles/contihome/profiles/catolico`)
	- Artefactos: `.env`, `AGENTS.md`, `auth.json`, `config.yaml` (+bak), `skills/`, `memories/`, `response_store.db`, `state.db`, `hooks/`, `sessions/`, `workspace/`
	- Canales: `config.yaml` muestra plataformas (telegram configurado en otros perfiles); revisar `config.yaml` para token y puertos si se requiere gateway dedicado.
	- Acción migración: exportar `config.yaml`, `auth.json`, `skills/`, `memories/`, `hooks/`, `state.db`.

- **`resto`** (`app/hermes_profiles/contihome/profiles/resto`)
	- Artefactos: `.env`, `AGENTS.md`, `auth.json`, `config.yaml`, `skills/`, `memories/`, `response_store.db`, `state.db`, `hooks/`, `sessions/`
	- Canales: `config.yaml` tiene `telegram: false` y `whatsapp: {}` — sugiere uso de WhatsApp (bridge central o local). Revisar `auth.json` y `channel_directory.json` para mapping de canales.
	- Acción migración: exportar el contenido listado y generar tests de integración (simular mensajes WhatsApp y Telegram según corresponda).

- **`odoo-resto`** (`.../odoo-resto`)
	- Artefactos: `.env`, `auth.json`, `config.yaml`, `skills/`, `memories/`, `state.db`, `hooks/`.
	- Observación: perfil orientado a integraciones Odoo + Telegram; mantener mapeo MCP y cabeceras `X-Odoo-Database` en `config.yaml`.

- **`odoo`** (`.../odoo`)
	- Artefactos: `.env`, `.skills_prompt_snapshot.json`, `auth.json`, `config.yaml`, `skills/`, `memories/`, `response_store.db`, `state.db`, `hooks/`.
	- Observación: contiene plantillas y snapshots de skills — asegurar export de `.skills_prompt_snapshot.json` para preservar prompts y frontmatter.

- **`odoo-mendoza`** (`.../odoo-mendoza`)
	- Artefactos: `config.yaml`, `profile.yaml`, `skills/`, `memories/`, `state.db`, `response_store.db`, `hooks/`.
	- Observación: cliente híbrido Odoo + Mendoza; verificar `profile.yaml` y `config.yaml` para puertos y MCP.

- **`odoo-nudo`** (`.../odoo-nudo`)
	- Artefactos: `.env`, `auth.json`, `config.yaml`, `skills/`, `memories/`, `state.db`, `hooks/`.

- **`mendoza`** (`.../mendoza`) — perfil crítico (FRONTEND clientes)
	- Artefactos detectados: `.env`, `config.yaml`, `profile.yaml`, `gateway_state.json`, `channel_directory.json`, `response_store.db`, `state.db`, `skills/`, `memories/`, `sessions/`, `pairing/`, `bin/tirith` (binario)
	- Observación clave: `./mendoza/.env` contiene el comentario operativo "WhatsApp: se integra externamente vía wppconnect → llama al API Server :8770" — por lo tanto en despliegue actual `mendoza` usa `wppconnect-server` (contenedor) para WhatsApp. Sin embargo:
		- Hay artefactos y documentación (ej. `CHAT.MD`, `.skills_prompt_snapshot.json`, y otros perfiles) que mencionan **Baileys** y un "whatsapp-bridge" en Hermes.
		- En `mendoza/bin` hay un archivo binario `tirith` (probable bridge/cliente empaquetado). El binario no puede leerse directamente desde el repo; requiere inspección con `strings` o ejecutar `file`/`ldd` dentro del contenedor para identificar su función.
	- Recomendación inmediata para `mendoza` (checklist meticulosa)

	1) Objetivo
	 - Determinar de forma inequívoca si WhatsApp en `mendoza` está gestionado por:
	   a) un bridge local empaquetado (`bin/tirith`) que usa Baileys/Node u otra librería, o
	   b) un servicio externo/central como `wppconnect-server` (contenedor) al que `mendoza` llama por HTTP.

	2) Salida esperada
	 - Un `migration_manifest/mendoza/manifest.yaml` con: detección del motor WhatsApp (`baileys` | `wppconnect` | `unknown`), lista de artefactos a exportar, comandos/archivos de evidencia guardados en `migration_manifest/mendoza/evidence/`.

	3) Pasos exactos (ejecutar en host, requiere Docker Compose activo)

	- Comprobar servicios Docker (identificar `wppconnect` si existe):

	```bash
	# desde la raíz del repo
	docker compose -f docker-compose.conti.yml ps
	```

	- Volcar `gateway_state.json` y revisar estado declarado:

	```bash
	docker compose -f docker-compose.conti.yml exec conti-backend \
	  bash -lc 'cat app/hermes_profiles/contihome/profiles/mendoza/gateway_state.json' \
	  > migration_manifest/mendoza/evidence/gateway_state.json || true
	```

	- Listar y inspeccionar el binario `tirith` (si existe):

	```bash
	docker compose -f docker-compose.conti.yml exec conti-backend \
	  bash -lc 'ls -la app/hermes_profiles/contihome/profiles/mendoza/bin || true'

	# inspección básica de tipo y texto incrustado
	docker compose -f docker-compose.conti.yml exec conti-backend \
	  bash -lc 'file app/hermes_profiles/contihome/profiles/mendoza/bin/tirith 2>/dev/null || true' \
	  > migration_manifest/mendoza/evidence/tirith_file.txt || true

	docker compose -f docker-compose.conti.yml exec conti-backend \
	  bash -lc 'strings app/hermes_profiles/contihome/profiles/mendoza/bin/tirith | head -n 200' \
	  > migration_manifest/mendoza/evidence/tirith_strings_head.txt || true
	```

	- Marcar patrones esperados en `tirith_strings_head.txt`:
	  - Indicadores de Node/packager: `node`, `v8`, `node_modules`, `pkg`, `nexe`.
	  - Indicadores Baileys/WhatsApp: `Baileys`, `whatsapp`, `wa-`, `conn.on`, `auth.json`, `session`, `pairing`.

	- Inspeccionar `mendoza` logs y archivos de pairing/auth:

	```bash
	docker compose -f docker-compose.conti.yml exec conti-backend \
	  bash -lc 'ls -la app/hermes_profiles/contihome/profiles/mendoza || true'

	# copiar logs y auth para evidencia
	docker compose -f docker-compose.conti.yml exec conti-backend \
	  bash -lc 'grep -i "wppconnect\|baileys\|whatsapp" -R --binary-files=text app/hermes_profiles/contohome/profiles/mendoza || true' \
	  > migration_manifest/mendoza/evidence/mendoza_grep_wa.txt || true

	docker compose -f docker-compose.conti.yml exec conti-backend \
	  bash -lc 'cat app/hermes_profiles/contihome/profiles/mendoza/auth.json 2>/dev/null || true' \
	  > migration_manifest/mendoza/evidence/auth.json || true
	```

	- Verificar referencias en `mendoza/.env` y `config.yaml` (puertos/ENDPOINTS):

	```bash
	docker compose -f docker-compose.conti.yml exec conti-backend \
	  bash -lc 'cat app/hermes_profiles/contihome/profiles/mendoza/.env 2>/dev/null || true' \
	  > migration_manifest/mendoza/evidence/mendoza_env.txt || true

	docker compose -f docker-compose.conti.yml exec conti-backend \
	  bash -lc 'cat app/hermes_profiles/contihome/profiles/mendoza/config.yaml 2>/dev/null || true' \
	  > migration_manifest/mendoza/evidence/mendoza_config.yaml || true
	```

	- Si `docker compose ps` muestra un servicio `wppconnect` o similar, volcar su imagen/versión:

	```bash
	# buscar contenedor wppconnect
	docker ps --format '{{.Names}} {{.Image}}' | grep -i wppconnect || true
	```

	- Copiar salida y preparar `migration_manifest/mendoza/manifest.yaml` (plantilla abajo).

	4) Criterios y pasos decisorios

	- Si `tirith_file.txt` y `tirith_strings_head.txt` contienen cadenas relacionadas con Node/Baileys o `node_modules`, marcar `engine: baileys-local`.
	  - Acción: añadir a `migration_manifest/mendoza/` los siguientes artefactos a exportar: `bin/tirith`, `pairing/`, `auth.json`, `hooks/`, `state.db`, `response_store.db`, `skills/`, `memories/`, `sessions/`. Documentar cómo se ejecuta (`env vars`, comando exacto en `entrypoint_hermes.sh` o systemd/launch scripts).

	- Si no hay evidencia de Node/Baileys en `tirith` y `gateway_state.json` / logs muestran llamadas a `http://<host>:21465` o similar, marcar `engine: wppconnect-central`.
	  - Acción: documentar la imagen y versión del contenedor `wppconnect`, endpoints (puerto, rutas), tokens/secret names (no exponer secretos en repo — almacenar en `migration_manifest/mendoza/evidence/secret_refs.txt` con instrucciones para extracción segura), y planificar mantenerlo centralizado o sustituirlo por Baileys local (coste/operación).

	- Si no se puede decidir, marcar `engine: unknown` y adjuntar toda la evidencia recogida en `migration_manifest/mendoza/evidence/` para análisis forense.

	5) Plantilla mínima para `migration_manifest/mendoza/manifest.yaml`

	```yaml
	profile: mendoza
	engine: baileys-local  #| wppconnect-central | unknown
	evidence:
	  - gateway_state: evidence/gateway_state.json
	  - tirith_file: evidence/tirith_file.txt
	  - tirith_strings: evidence/tirith_strings_head.txt
	  - auth: evidence/auth.json
	  - env: evidence/mendoza_env.txt
	artifacts_to_export:
	  - bin/tirith
	  - pairing/
	  - auth.json
	  - hooks/
	  - state.db
	  - response_store.db
	  - skills/
	  - memories/
	  - sessions/
	notes: |
	  Añadir instrucciones para extracción segura de secretos y pasos para reproducir el arranque del bridge local.
	```

	6) Backups (comando sugerido — ejecutar solo con permiso)

	```bash
	mkdir -p ./compose/documentos_listos/migration_backups/mendoza
	docker compose -f docker-compose.conti.yml exec conti-backend \
	  bash -lc 'tar -czf /tmp/mendoza_backup.tgz -C app/hermes_profiles/contihome/profiles/mendoza config.yaml auth.json skills memories sessions pairing bin state.db response_store.db || true'
	docker cp $(docker compose -f docker-compose.conti.yml ps -q conti-backend):/tmp/mendoza_backup.tgz ./compose/documentos_listos/migration_backups/mendoza/mendoza_backup.tgz || true
	```

	7) Resultado final y seguimiento

	- Subir `migration_manifest/mendoza/manifest.yaml` y todo `migration_manifest/mendoza/evidence/` al repo (sin secretos). En el plan registrar resultados:
	  - `engine` detectado
	  - acciones recomendadas (mantener wppconnect vs migrar a Baileys)
	  - lista final de artefactos exportados y verificados

	- Si deseas, procedo a ejecutar los comandos anteriores (auditoría y creación de backups). Requiere tu confirmación explícita para ejecutar comandos en los contenedores y crear los tar.gz en `./compose/documentos_listos/migration_backups/`.

- **`contihome` (gateway/sandbox)**
	- Artefactos: `AGENTS.md`, `SOUL.md`, `TOOLS.md`, `memories/`, `sessions/` y snapshots. Actúa como área de trabajo compartida y contiene _skills snapshot_ y memoria general.
	- Acción migración: exportar `memories/`, `sessions/` y `.skills_prompt_snapshot.json` para preservar conocimiento de Codevibing y plantillas.

## 7. Inventario específico para Codevibing (nanobots)
## 7. Inventario específico para Codevibing (Codevibing / contihome)

- Corrección importante (verificada): no hay evidencia en el repositorio de que exista un runtime global en `/home/nanobot` ni de ficheros obligatorios en `/home/nanobot/.nanobot/`.
- Ubicación real y verificada de los artefactos de Codevibing:
	- Raíz de la instancia Codevibing: `app/hermes_profiles/contihome/`.
	- Archivos relevantes dentro del perfil `contihome`: `config.yaml`, `.skills_prompt_snapshot.json`, `skills/`, `memories/`, `sessions/`, `workspace/`.
	- Componentes de emulación/puente LLM local: `app/llm_emulation/` (ej.: `router.py`, `nanobot_serve_bridge.py`) — aquí se implementa la lógica de proxy/emulación del LLM usada por las solicitudes internas.

- Observaciones operativas (aclaradas):
	- No existe en el despliegue actual un par de roles "nanobot: gateway" vs "nanobot: llm serve" como entidades con rutas en `/home/nanobot`. Lo que sí ocurre es:
		- El `entrypoint_hermes.sh` arranca el servidor LLM-proxy (uvicorn en `:9001`) y, por separado, lanza los gateways Hermes por perfil (puertos 8766–8770 y 18791 para `contihome`). Son procesos distintos pero gestionados desde el entrypoint.
		- La lógica de enrutado de peticiones LLM con tokens `sk-hermes-` está en `app/llm_emulation/router.py`: el router detecta tokens hermes y reenvía/conecta (incluyendo streaming) a los puertos de gateway por perfil (TENANT→PORT). Esto es el punto clave del "LLM emulation" del sistema.

- Dónde residen los skills en la práctica:
	- En tiempo de ejecución los skills y snapshots que pertenecen a Codevibing están en `app/hermes_profiles/contihome/` y en los sub-perfiles bajo `app/hermes_profiles/contihome/profiles/`.
	- No se debe asumir la presencia de `~/.nanobot/workspace/skills/` salvo en despliegues/contendores muy personalizados; el repo y el deploy actual usan rutas dentro de `app/hermes_profiles/`.

- Implicaciones para la migración:
	- Exportar/respaldar `app/hermes_profiles/contihome/.skills_prompt_snapshot.json`, `skills/`, `memories/`, `sessions/` y `config.yaml` preserva el estado de Codevibing.
	- Para cualquier trabajo sobre la capa LLM-emulada, revisar y documentar `app/llm_emulation/router.py` y `nanobot_serve_bridge.py` para entender la forma en que se transforman y reenvían los requests (headers, streaming, rewrites de modelo).

- Paso de verificación realizado (hecho):
	- He leído `app/llm_emulation/router.py` y `entrypoint_hermes.sh` y confirmé el comportamiento descrito arriba; por tanto se actualizó el plan para eliminar las rutas `/home/nanobot/*` y sustituirlas por las rutas reales del repo.

## 8. Acciones recomendadas (priorizadas y concretas)

1. Confirmación técnica (rápida, 15-30 min)
	 - Ejecutar `strings bin/tirith | head -n 200` (o `file bin/tirith`) dentro del contenedor `conti-backend` para identificar si es Baileys/Node o binario empaquetado.
	 - Revisar `gateway_state.json` y `logs/` de `mendoza` para identificar qué servicio gestiona sesiones WhatsApp.
2. Exportes (por perfil)
	 - Generar `migration_manifest/<perfil>/` con: `config.yaml`, `profile.yaml` (si existe), `auth.json`, lista de `skills/` (archivos), `hooks/`, `memories/`, `state.db`, `response_store.db`.
3. Codevibing (nanobots)
	 - Extraer `/home/nanobot/.nanobot/config.json` y `/home/nanobot/llm_serve_config.json` del contenedor y volcarlos en `migration_manifest/nanobots/`.
	 - Documentar el flujo exacto: qué recibe el gateway antes de enviar al nanobot (headers, streaming, MCP calls). Añadir ejemplos de requests/responses en `migration_manifest/nanobots/README.md`.
4. Bridge WhatsApp
	 - Si `Baileys` está embebido en el repo o en binarios: documentar su interfaz y preferir implementar un `Deer-Flow-Baileys-Connector` que re-use la lógica existente.
	 - Si `wppconnect-server` es el motor en producción: documentar cómo se invocan sus endpoints desde `mendoza` (API Server :8770) y decidir mantenerlo o migrar a Baileys por perfil.

## 9. Producción del Plan final

- Tras tu confirmación, generaré automáticamente (A) `migration_manifest/` con estructura por perfil y (B) backups tar.gz por perfil en `./compose/documentos_listos/migration_backups/` y (C) actualizaré `Plan_backend.md` insertando el inventario por perfil y checklist detallado (este bloque ya se guardará en el documento).

``` 