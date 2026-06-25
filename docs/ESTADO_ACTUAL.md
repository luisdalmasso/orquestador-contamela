# Estado Actual — conti-backend

> Generado tras la refactorización arquitectónica a Proxy Stateless + n8n Omnicanal.  
> Fecha: Mayo 2026  
> Fuente: `app/chat/orchestrator.py`, `app/chat/router.py`, Chainlit `app.py`, n8n Workflows.

---

## Resumen Ejecutivo

El backend está completamente implementado y operativo con una nueva **Arquitectura Desacoplada**. Se ha abandonado el enfoque del orquestador stateful (que escribía archivos en disco y usaba Redis para el chat) en favor de un modelo de **Proxy Transparente** en FastAPI. 

La orquestación de UI y la omnicanalidad han sido delegadas a **n8n**, mientras que el renderizado rico (Markdown, PDF, HTML, Botones) se gestiona dinámicamente en **Chainlit** mediante directivas JSON. **Nanobot** asume el control total del razonamiento y la memoria de la sesión de manera nativa.

---

## Evolución Arquitectónica (Cambios Recientes)

1. **Eliminación de Cuellos de Botella I/O (Race Conditions):**
   - Se eliminó el `ContextWriter`. FastAPI ya no escribe `state.json`, `history.md` ni `rule_context.md` en disco por cada turno.
   - Se eliminó el uso de Redis (`RedisSessionManager`) para la memoria del chat.

2. **FastAPI como API Gateway (Stateless):**
   - El `ChatOrchestrator` ahora funciona como un proxy transparente. Solo evalúa el `tenant_id` (para saber a qué puerto interno llamar, ej. `8766`) y reenvía el `session_id` y el mensaje directamente al Nanobot.
   - Se resolvió el error 400 inyectando `"model": "default"` y usando `"session_id"` para que Nanobot asuma la carga del historial en su propia carpeta `.nanobot/workspace/sessions/`.

3. **n8n como Middleware Omnicanal (ESB):**
   - n8n recibe webhooks universales (`/webhook/chat`) desde cualquier canal (Chainlit, WhatsApp, etc.).
   - Estandariza variables, crea un objeto JSON nativo para evitar errores de parseo (400 Bad Request) y llama a FastAPI (`http://conti-backend:9001/v1/chat`).
   - Distribuye la respuesta estructurada al canal correspondiente.

4. **Chainlit como UI Dinámica (Cliente Tonto):**
   - Conectado directamente a n8n vía HTTP.
   - **Renderizado Dinámico:** Capaz de interceptar `ui_elements` y `actions` devueltos por el backend para dibujar:
     - **PDFs:** Visor nativo (`cl.Pdf`) en panel lateral + Botón de descarga (`cl.File`).
     - **Markdown:** Renderizado de texto rico en panel lateral (`cl.Text`) + Botón de descarga.
     - **HTML:** Botón de descarga seguro (`cl.File`) para evitar XSS.
     - **Botones Interactivos:** Clics simulados como respuestas de usuario (`cl.Action` con `payload`).
   - **Gestión de UX:** Destrucción activa de iframes anteriores para evitar solapamientos visuales. Manejo robusto de Avatares y Logos de Tenant (Branding) leyendo directo de PostgreSQL.
   - **Soporte de Adjuntos:** Extrae propiedades de archivos subidos por el usuario y los envía en el `metadata.attachments` a n8n.

---

## Endpoints REST Implementados

### Raíz y configuración
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/health` | Alias para `/v1/chat/health` (resuelve el 404 del healthcheck Docker) |
| `GET` | `/config` | Configuración efectiva con secretos redactados |
| `POST` | `/config/reload` | Recarga configuración desde disco |
| `GET` | `/onboarding` | Contenido de onboarding.md. |
| `GET` | `/rules` | Reglas efectivas con checksum y mtime |

### Chat Multi-Tenant
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/v1/chat` | Orquestador Proxy: Recibe `tenant_id`, `session_id`, `message`, `metadata`. Enruta al Nanobot correcto. Acepta mensajes vacíos si hay `attachments`. |
| `GET` | `/v1/chat/tenants` | Lista tenants disponibles |

### LLM Emulation (OpenAI-compatible para IDEs/ClawTeam)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/v1/models` | Lista modelos disponibles |
| `POST` | `/v1/chat/completions` | Proxy a nanobot serve del gateway :8765 |

*(Se preservan todos los endpoints MCP heredados del plan original para soporte de tools GitOps y Codevibing).*

---

## Sistema Multi-Tenant (Flujo Actualizado)

### Arquitectura de Petición
```text
[Usuario] -> [Chainlit UI] 
                | (Envía JSON: channel, tenant_id, session_id, message, attachments)
                v
            [n8n Webhook Universal]
                | (Estandariza payload, inyecta context)
                v
            [POST /v1/chat (FastAPI)]
                | (Lee tenant_id, busca puerto en registry, ej. 8766)
                v
            [POST /v1/chat/completions (Nanobot Serve Catolico)]
                | (Usa "session_id" para leer/escribir memoria nativa, ejecuta Tools)
                v
            [Devuelve JSON estructurado (texto, ui_elements, actions) -> n8n -> Chainlit]
```

### Componentes Clave
- `app/tenants/registry.py` — Descubre configs desde `/tenants/<id>/config.yaml`.
- `app/chat/orchestrator.py` — **(Refactorizado)** Orquestador Proxy. Reenvía tráfico directo, sin inyectar reglas ni clasificar intenciones.
- `app/chat/router.py` — Validación flexible para permitir payloads que solo contienen archivos o clicks en botones (sin texto).

---

## Estructura del Chainlit (Frontend)

- **Conexión DB:** Lee branding (logos, avatares, welcome messages) conectándose directamente a la DB Odoo (`DJANGO_DB_NAME`).
- **Fallback:** Usa cookies para recordar el `client_id` y evitar que el logo desaparezca en navegaciones subsecuentes.
- **Interfaz Dinámica (n8n JSON Support):**
  - Soporta `ui_elements`: `image`, `sidebar`, `pdf`, `markdown_file`, `html_file`.
  - Soporta `actions`: Botones interactivos que reinyectan el `value` en el flujo del chat.

---

## Runtime y Despliegue

### Procesos en `entrypoint.sh`
1. `nanobot gateway` — puerto `18790`
2. `nanobot serve` — puerto `8765` (emulación LLM base)
3. `uvicorn app.main:app` — puerto `9001` (FastAPI backend central)
4. `clawteam board serve` — puerto `8080`
5. `nanobot serve [catolico]` — puerto `8766`, home: `/tenants/catolico/`
6. *(Preparado para admitir más tenants en diferentes puertos de manera transparente).*

### Volúmenes Montados (Críticos para UI)
- `/compose/documentos_listos` (rw): Carpeta compartida donde el RAG Flamehaven o el Backend depositan PDFs y Markdowns generados, para que Chainlit los pueda leer de disco local y enviarlos a la UI en el panel lateral.

---

## Catálogo MCP (Destacados de Integración)
*(Se mantienen las 43 herramientas documentadas en ESTADO_REAL.md, pero estas cobran especial relevancia en la nueva arquitectura)*

- **Grupo I — RAG Flamehaven (Ingestión):** 
  - `start_rag_ingest`: Clave para procesar los `attachments` que Chainlit extrae y envía por n8n.
  - `scan_documentos_nuevos`: Escaneo de carpetas por tenant.

- **Grupo J — RAG Flamehaven (Búsqueda):** 
  - `search_rag`: Ahora es ejecutada autónomamente por el Nanobot, quien formatea la salida para sugerir a n8n/Chainlit cómo dibujar la UI.