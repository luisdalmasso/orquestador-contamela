# Plan 3 — Migración Gradual a Hermes-Agent

> **Objetivo:** Reemplazar el motor de agentes `nanobot` por `Hermes-Agent` de forma paulatina. 
> **Estrategia:** Migrar primero el perfil `contiHome` (Telegram + Emulador LLM), luego aislar y probar el tenant `catolico` por CLI antes de enrutarlo en producción, y finalmente replicar para el tenant `resto`.

---

## FASE 1: Preparación del Contenedor e Infraestructura Hermes

1. **Dependencias:** Agregar `hermes-agent` al `requirements.txt` del contenedor `conti-backend`.
2. **Estructura de Directorios:** Crear la estructura base para los perfiles de Hermes:
   ```text
   /app/hermes_profiles/
     ├── contihome/
     ├── catolico/
     └── resto/
   ```
3. **Configuración Global:** Crear el `config.yaml` principal de Hermes, configurando FastAPI como servidor MCP cliente nativo (`http://localhost:9001/mcp/sse`).

---

## FASE 2: Perfil `contiHome` (Telegram y Emulador LLM)

1. **Migración de Personalidad y Habilidades:**
   - Mover el contenido del `SOUL.md` actual al archivo `personality.txt` dentro de `/app/hermes_profiles/contihome/`.
   - Configurar el `profile.yaml` del perfil apuntando al LLM adecuado (Kilo.ai).
2. **Activación del Canal Telegram:**
   - En la configuración de Hermes, habilitar el canal de Telegram (pasarela multiplataforma) con el token actual del bot.
   - Esto reemplazará la función del actual `nanobot gateway`.

---

## FASE 3: Modificación del Emulador LLM en FastAPI

Se debe modificar **únicamente** el puente que emula la API de OpenAI para clientes como Kilocode o Cline (`app/llm_emulation/nanobot_serve_bridge.py` o su respectivo router).

**Acción en Código:**
- **Comentar** la lógica actual que hace el proxy pass (el request HTTP hacia `http://127.0.0.1:8765`).
- **Agregar** la nueva llamada asíncrona hacia la instancia o API de `Hermes-Agent` usando el perfil `contihome`.
- Mantener intacta la lógica de streaming y formateo de salida (Chunks tipo OpenAI).

---

## FASE 4: Producción y Pruebas de `contiHome`

1. **Despliegue:** Reiniciar el contenedor aplicando los cambios.
2. **Escenario A (Telegram):** 
   - Interactuar con el bot de Telegram de Codevibing.
   - Verificar que responde con la personalidad correcta y ejecuta herramientas (Tools) vía MCP correctamente.
   - *Resultado esperado: OK.*
3. **Escenario B (Emulador LLM):**
   - Usar un IDE (Cline, Kilocode, Amazon Q).
   - Enviar prompts que requieran contexto de código o edición.
   - *Resultado esperado: OK (Streaming fluido y tool calling preciso).*

---

## FASE 5: Perfil `catolico` (Desarrollo y Prueba CLI aislada)

> ⚠️ **RESTRICCIÓN:** En esta fase **NO** se toca FastAPI. El endpoint actual de FastAPI sigue haciendo proxy al `nanobot serve` del puerto `8766` en producción.

1. **Configuración del Perfil:**
   - Poblar `/app/hermes_profiles/catolico/` con su `personality.txt` (antiguo SOUL).
   - Migrar la configuración de Tools permitidas para este tenant.
   - Configurar el RAG trasladando los documentos leídos a la función *Context Files* de Hermes.
2. **Pruebas por CLI:**
   - Entrar por terminal al contenedor y ejecutar: `hermes chat --profile catolico`
   - Probar escenarios de usuario: "¿Cuál es el evangelio de hoy?", "Busca esta cita bíblica", "Hazme un resumen del documento".
   - Validar que Hermes invoca correctamente las tools MCP de católico en el backend.
   - *Resultado esperado: OK.*

---

## FASE 6: Integración FastAPI para el Tenant `catolico`

Una vez validado el funcionamiento perfecto por CLI:
1. **Modificar FastAPI (`ChatOrchestrator`):**
   - Comentar el POST HTTP que apunta a `http://localhost:8766`.
   - Agregar la invocación a la API/Objeto de Hermes pasándole el `tenant_id="catolico"` y el `session_id`.
2. **Pruebas End-to-End (E2E):**
   - Probar el flujo completo en producción: **Webchat -> Superinterface -> n8n -> FastAPI -> Hermes**.
   - *Resultado esperado: OK.*

---

## FASE 7: Replicación para el Tenant `resto`

1. Crear el perfil `/app/hermes_profiles/resto/`.
2. Configurar personalidad y constraints de tools.
3. Probar exhaustivamente mediante CLI (`hermes chat --profile resto`).
4. Una vez aprobado en CLI, modificar el `ChatOrchestrator` en FastAPI para que los requests de este tenant apunten a Hermes.
5. Prueba E2E en flujo real.

---

## FASE 8: Limpieza Final (Cleanup)

Una vez que todos los flujos (Telegram, Emulador LLM, Tenants) operan al 100% sobre Hermes-Agent:
1. Eliminar de `entrypoint.sh` los sub-procesos de `nanobot` (puertos 18790, 8765, 8766...).
2. Limpiar el código comentado en FastAPI.
3. Eliminar las carpetas `.nanobot/` obsoletas de los tenants para liberar espacio.