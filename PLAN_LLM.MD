# Plan de Transición a OpenHands (v4 - Plataforma de Emulación LLM Nativa)

## 1. Objetivo Estratégico

El objetivo es reemplazar toda la plataforma de **emulación LLM** expuesta en `:9001` (paths `/v1/chat/completions`, `/v1/models`, `/v1/responses`) por un stack moderno centrado en `OpenHands`, integrado nativamente dentro del framework **FastAPI** existente. Esto garantiza máxima eficiencia, coherencia arquitectónica y cero impacto en los demás servicios (incluido Hermes, que sigue funcionando con sus propios gateways por puerto).

**Principios Clave (finales):**
- **Disparador Universal:** **TODO** el tráfico que llega al puerto `:9001` con rutas de emulación LLM (`/v1/chat/completions`, `/v1/models`, `/v1/responses`) es atendido por el stack OpenHands. **No se redirige más a ningún gateway de Hermes** (ni siquiera al `resto:8767`).
- **Aislamiento:** El agente `resto` de Hermes en el puerto `:8767` permanece intacto y se sigue utilizando para otros flujos (UI, omnicanalidad, etc.). El router LLM de `:9001` ya **no** debe proxyar hacia él.
- **Integración Nativa (No más procesos):** El nuevo agente **no se ejecutará en un proceso separado**. Se integrará como un nuevo módulo y `APIRouter` dentro de la aplicación FastAPI principal.
- **Stack Enfocado:** La fase inicial se centra exclusivamente en el `codebiving` con el stack: `OpenHands`, `Sourcebot`, `Ponytail`, `oh-my-pi` y `MCP`.
- **Sourcebot aislado:** Sourcebot se ejecuta en un **contenedor separado** (`conti-sourcebot`) bajo `sourcebot/docker-compose.yml`. Comparte la red `compose_odoo-network` con el stack principal para reusar `compose-db-1` (Postgres) y `redis_odoo` (Redis) sin levantar duplicados. Se crea la DB `sourcebot` dentro del cluster Postgres compartido.
- **Trazabilidad Total:** Cada tarea ejecutada generará un informe de trazabilidad completo a través de `Ponytail`.

---

## 2. El Nuevo "Codebiving Stack"

La arquitectura de herramientas se mantiene, pero su invocación se simplifica:

- **Orquestador de Tools (`MCP`):** Se creará un "adaptador" que lea las `tools` del servidor `mcp` y las presente a `OpenHands` en un formato de `tool-calling` estándar.
- **Indexación de Contexto (`Sourcebot`):** Se invoca como un servicio HTTP externo en `http://conti-sourcebot:3000` (puerto host `3010`). Sourcebot corre en su propio contenedor con su propia DB (`sourcebot` en el Postgres compartido) y se invoca por API desde el endpoint de OpenHands. **No** se incluye en `docker-compose.conti.yml`; vive en `sourcebot/docker-compose.yml`.
- **Cliente LLM Optimizado (`oh-my-pi`):** Se utilizará como el cliente Python para todas las llamadas a la API del LLM.
- **Runtime de Ejecución (`OpenHands`):** Será llamado como una función Python desde el nuevo endpoint.
- **Wrapper de Trazabilidad (`Ponytail`):** Envolverá la lógica de ejecución principal dentro del endpoint para capturar y registrar toda la interacción.

---

## 3. Arquitectura y Flujo de Ejecución (v4)

1.  **Router LLM (`app/llm_emulation/router.py`)** recibe una solicitud en `:9001` con ruta `/v1/...`.
2.  **Lógica de Enrutamiento (v4):**
    - **SIEMPRE** que la ruta sea `/v1/chat/completions`, `/v1/models` o `/v1/responses`:
        - En lugar de reenviar la llamada a un gateway Hermes, **invoca directamente la nueva función de servicio** (ej. `openhands_service.run_task(request_body)`) o devuelve la lista de modelos gestionada por el stack OpenHands.
        - **No se realiza ninguna conexión HTTP saliente al puerto 8767 ni a ningún otro gateway de Hermes** desde este router.
    - El tráfico destinado a `resto:8767` o cualquier otro gateway Hermes **NO** entra por `:9001`. Esos servicios siguen accesibles directamente por su puerto.
3.  **Nuevo Endpoint (`/agent/v1/run_task`)**:
    - Un nuevo router en `app/openhands_agent/router.py` expone este endpoint.
    - La función del endpoint orquesta la ejecución:
        - Inicia la traza con **`Ponytail`**.
        - Prepara el contexto del código fuente con **`Sourcebot`**.
        - Llama al `runtime` de **`OpenHands`**, pasándole el prompt y el contexto.
        - Todas las llamadas al LLM que haga `OpenHands` pasarán por **`oh-my-pi`**.
        - **`Ponytail`** captura y guarda el log de la ejecución.
4.  El resultado final se devuelve a través de la cadena de llamadas internas hasta la solicitud original.

---

## 4. Plan de Implementación (Revisado con FastAPI)

### Fase 1: Preparación del Entorno y Módulo del Agente

1.  **Actualizar Dependencias:**
    - Añadir `openhands-agent`, `sourcebot-cli`, `ponytail-ai`, `oh-my-pi` al `requirements.txt`.
    - Modificar el `Dockerfile` si se requieren dependencias de sistema adicionales.
2.  **Crear el Módulo del Agente:**
    - Crear el directorio `app/openhands_agent/`.
    - Dentro, crear los archivos:
        - `router.py`: Contendrá el `APIRouter` de FastAPI con el endpoint `/v1/run_task`.
        - `service.py`: Contendrá la lógica principal que orquesta el stack (`Ponytail`, `Sourcebot`, `OpenHands`).
        - `__init__.py`: Para que sea un módulo Python.
3.  **Integrar el Nuevo Router:**
    - En `app/main.py`:
        - `from app.openhands_agent.router import router as openhands_router`
        - `app.include_router(openhands_router, prefix="/agent", tags=["agent"])`

### Fase 2: Implementación de la Lógica del Agente

1.  **Desarrollar el `service.py`:**
    - Crear la clase `OpenHandsService` con un método `run_task(payload: dict)`.
    - Este método implementará el flujo de ejecución:
        ```python
        def run_task(self, payload):
            # 1. Iniciar Ponytail
            with ponytail.trace(task_name=payload.get("task")):
                # 2. Preparar contexto con Sourcebot
                context = sourcebot.index_and_get_context(...)
                
                # 3. Configurar oh-my-pi como el cliente LLM
                llm_client = oh_my_pi.Client(...)
                
                # 4. Invocar OpenHands
                result = openhands.run(
                    prompt=payload.get("prompt"),
                    context=context,
                    llm_client=llm_client
                )
                
                # 5. Ponytail guarda el trace automáticamente
                return result
        ```
        *(Nota: El código es una simplificación conceptual)*
2.  **Desarrollar el `router.py`:**
    - El endpoint en el router recibirá la solicitud, la validará (usando modelos de Pydantic) y llamará al `OpenHandsService` para ejecutar la tarea.

### Fase 3: Activación del Enrutamiento y Pruebas

1.  **Modificar el Router LLM (`app/llm_emulation/router.py`):**
    - Importar el `OpenHandsService` (`from app.openhands_agent.service import openhands_service`).
    - **Eliminar completamente** la lógica de proxy a Hermes en `:8767` (y a cualquier otro gateway Hermes). Ya no debe existir `TENANT_TO_PORT`, `get_tenant_from_token`, ni lectura de `API_SERVER_KEY` de perfiles.
    - En `POST /v1/chat/completions`: llamar directamente a `openhands_service.run_task(body)` y devolver el resultado como respuesta OpenAI-compatible.
    - En `GET /v1/models`: invocar `openhands_service.list_models()` (o equivalente) para devolver los modelos soportados por el stack.
    - En `POST /v1/responses`: si se conserva, también debe enrutar al stack OpenHands.
2.  **Pruebas End-to-End:**
    - Realizar una solicitud `POST /v1/chat/completions` a `:9001` y verificar que la respuesta la genera OpenHands (no Hermes).
    - Verificar `GET /v1/models` y confirmar que lista modelos del stack OpenHands.
    - Confirmar que se genera un archivo de trazabilidad de `Ponytail` por cada ejecución.
    - Validar que `:8767` (Hermes resto) sigue respondiendo por su puerto como siempre.

---

## 5. Estrategia para Agentes Cliente (Futuro)

Se mantiene sin cambios como un proyecto futuro y separado, basado en `DeerFlow`.

