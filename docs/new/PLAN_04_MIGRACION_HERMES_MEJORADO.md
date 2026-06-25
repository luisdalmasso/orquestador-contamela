# Plan 4 — Migración a Hermes-Agent (Arquitectura Stateless Proxy)

> **Fecha:** Mayo 2026
> **Objetivo:** Migrar el motor de razonamiento de Nanobot a Hermes-Agent, aprovechando la arquitectura actual de FastAPI como Proxy Transparente (Stateless) y la delegación omnicanal de n8n.
> **Estrategia:** Migración limpia, sin servidores de compatibilidad MCP innecesarios y con manejo de sesión 100% delegado al motor interno de Hermes.

---

## FASE 0: Preparación y Validación

1. **Verificación de Dependencias:**
   - Añadir `hermes-agent` a `requirements.txt`.
2. **Estructura de Perfiles de Hermes:**
   - Crear la carpeta `/app/hermes_profiles/`.
   - La configuración de cada tenant ahora vivirá como un "Perfil" de Hermes.

---

## FASE 1: Perfil `contiHome` (Emulador LLM y Telegram)

1. **Creación del Perfil:**
   - Directorio: `/app/hermes_profiles/contihome/`.
   - `personality.txt`: Mover el contenido actual de `SOUL.md`.
   - `config.yaml`: 
     - Configurar el proveedor LLM usando el estándar OpenAI apuntando a Kilo.ai:
       ```yaml
       model:
         provider: openai
         base_url: "https://api.kilo.ai/api/gateway"
         api_key: "${KILO_API_KEY}"
       ```
     - Activar el gateway nativo de Telegram con el token actual.
     - Conectar al servidor MCP local:
       ```yaml
       mcp_servers:
         conti_backend:
           type: sse
           url: "http://localhost:9001/mcp/sse"
       ```
2. **Apagado del Legacy:**
   - Apagar el proceso de `nanobot gateway` (puerto 18790) en `entrypoint.sh`. El bot de Codevibing en Telegram ahora es manejado íntegramente por Hermes.

---

## FASE 2: Adaptación del Proxy LLM en FastAPI

El objetivo es emular la API de OpenAI para IDEs (Cline, Kilocode) usando Hermes.

1. **Modificar `/v1/chat/completions`:**
   - En lugar de hacer proxy pass a `http://127.0.0.1:8765` (nanobot serve), FastAPI instanciará la API de Hermes.
   - Hermes posee nativamente un servidor API compatible con OpenAI. La ruta de FastAPI simplemente puede redirigir las peticiones HTTP directamente a la API interna de Hermes, o instanciar la clase `HermesAgent` y devolver los chunks (Streaming).
2. **Validación:**
   - Probar desde Cline/Kilocode que el autocompletado y el uso de tools siguen funcionando.
   - Apagar `nanobot serve` (puerto 8765).

---

## FASE 3: Migración del Tenant `Catolico` (Stateless)

Aprovechando que FastAPI ya no escribe archivos en disco (ContextWriter eliminado), el flujo se vuelve extremadamente limpio.

1. **Crear Perfil del Tenant:**
   - Directorio: `/app/hermes_profiles/catolico/`.
   - `personality.txt`: Reglas e identidad teológica (antiguo SOUL.md).
2. **Modificación del Orquestador (`app/chat/orchestrator.py`):**
   - Actualmente FastAPI recibe: `tenant_id`, `session_id`, `message`.
   - El nuevo flujo será:
     ```python
     # FastAPI actúa como cliente de la librería Hermes
     agent = HermesAgent(profile=tenant_id, session_id=session_id)
     response = await agent.chat(message)
     return response
     ```
   - **Magia Stateless:** Hermes buscará el `session_id` en su propia base de datos (SQLite/Postgres), recuperará el historial, inyectará el `personality.txt` de "catolico", utilizará las tools MCP a través del loop interno y devolverá la respuesta a FastAPI.
   - FastAPI reenvía la respuesta a n8n/Chainlit.

---

## FASE 4: Replicación y Limpieza Final

1. **Tenant `Resto` y futuros:**
   - Repetir el proceso de la Fase 3. Crear el directorio en `hermes_profiles` y listo. Cero configuración de puertos.
2. **Limpieza Absoluta:**
   - Eliminar todos los subprocesos de nanobot (`serve` por cada tenant) en `entrypoint.sh`.
   - Borrar las carpetas legacy `/contenedores/tenants/*/context/`.
   - Borrar `/contenedores/conti_home/.nanobot/workspace/`.

> **Resultado:** Un único proceso de FastAPI que invoca bajo demanda a Hermes-Agent. Reducción drástica del uso de RAM, latencia mínima y escalabilidad ilimitada para nuevos tenants.