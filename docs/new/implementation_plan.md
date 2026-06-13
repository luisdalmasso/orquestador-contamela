# Plan de Migración: Arquitectura Nanobot por Tenant — DEFINITIVO

---

## Estructura de despliegue

```
/contenedores/
├── conti_home/              # HOME de Conti (admin/dev) — NO SE TOCA
│   ├── .nanobot/config.json
│   ├── llm_serve_config.json
│   └── workspace/
│       ├── SOUL.md, AGENTS.md, USER.md, ...
│       └── skills/ (25 skills)
│
├── tenants/                 # [NUEVO] Raíz de todos los tenants de chat
│   ├── catolico/            # HOME completo del nanobot "católico"
│   │   ├── .nanobot/
│   │   │   └── config.json
│   │   ├── workspace/
│   │   │   ├── SOUL.md
│   │   │   ├── AGENTS.md
│   │   │   ├── USER.md
│   │   │   ├── CONSTANTS.md
│   │   │   ├── TOOLS.md
│   │   │   ├── skills/
│   │   │   │   ├── rag-manager/    → symlink a conti_home
│   │   │   │   ├── voice-manager/  → symlink
│   │   │   │   └── gemini-vision/  → symlink
│   │   │   ├── documents/          # Docs de referencia del tenant
│   │   │   ├── memory/             # Memoria persistente del nanobot
│   │   │   └── sessions/           # Sesiones del nanobot
│   │   │
│   │   ├── context/                # [CLAVE] Archivos que FastAPI ESCRIBE
│   │   │   ├── state.json          # Estado actual de la sesión (flags)
│   │   │   ├── history.md          # Últimos N mensajes formateados
│   │   │   └── rule_context.md     # Regla activa + instrucciones del turno
│   │   │
│   │   └── config.yaml             # Config del tenant para FastAPI (strategy, rules, etc.)
│   │
│   ├── odoo_repuestos/      # HOME completo del nanobot "odoo" (futuro)
│   │   └── (misma estructura)
│   │
│   └── resto_mendoza/       # HOME completo del nanobot "resto" (futuro)
│       └── (misma estructura)
│
└── conti-backend/           # Código fuente del backend FastAPI + nanobot
    └── app/
```

### La carpeta `context/` — el puente entre FastAPI y nanobot

> [!IMPORTANT]
> FastAPI **escribe** archivos en `context/` antes de cada llamada al nanobot.
> El SOUL.md o CONSTANTS.md del nanobot le indica que **lea** esos archivos.
> Así nanobot conoce el estado actual sin que FastAPI tenga que inyectarlo en el prompt.

```python
# orchestrator.py — antes de llamar al nanobot
async def _prepare_context(self, tenant, session_id, state, history, rule):
    context_dir = f"/contenedores/tenants/{tenant.tenant_id}/context"
    
    # Escribir estado actual
    with open(f"{context_dir}/state.json", "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    
    # Escribir historial formateado
    with open(f"{context_dir}/history.md", "w") as f:
        for msg in history[-tenant.max_history:]:
            f.write(f"**{msg['role']}**: {msg['content']}\n\n")
    
    # Escribir contexto del turno (regla activa)
    with open(f"{context_dir}/rule_context.md", "w") as f:
        f.write(f"# Turno actual\n\n")
        f.write(f"**Session:** {session_id}\n")
        f.write(f"**Regla activa:** {rule.titulo}\n\n")
        f.write(rule.contenido)
```

Y en el SOUL.md del tenant:
```markdown
# SOUL.md — Asistente Católico

Soy un asistente teológico católico, servicial y amable.

## Regla Obligatoria
ANTES de responder, SIEMPRE lee estos archivos:
1. `/home/nanobot/context/rule_context.md` — Tu tarea para este turno
2. `/home/nanobot/context/state.json` — Estado de la sesión
3. `/home/nanobot/context/history.md` — Historial de la conversación

Sigue ESTRICTAMENTE la regla indicada en `rule_context.md`.
```

---

## Docker: bind mounts

```yaml
# docker-compose.yml (actualizado)
services:
  conti-backend:
    volumes:
      - /contenedores/conti_home:/home/nanobot/         # Conti (gateway + serve admin)
      - /contenedores/tenants:/tenants                   # Todos los homes de tenants
      - /desarrollo:/desarrollo
      - /compose:/compose:ro
```

En el entrypoint, cada nanobot serve del tenant se lanza con:
```bash
HOME="/tenants/catolico" nanobot serve \
    --host 0.0.0.0 --port 8766 \
    --config "/tenants/catolico/.nanobot/config.json" &
```

---

## Arquitectura FastAPI

```
conti-backend/app/
├── tenants/
│   ├── base.py               # TenantConfig (Pydantic): strategy, nanobot_port, rules
│   ├── registry.py            # Lee config.yaml de cada /tenants/<id>/config.yaml
│   └── context_writer.py      # Escribe state.json, history.md, rule_context.md
│
├── chat/
│   ├── memory.py              # RedisSessionManager (historial + state)
│   ├── rules_engine.py        # Evalúa reglas contra flags de estado
│   ├── orchestrator.py        # Estado → reglas → escribe context/ → llama nanobot → actualiza estado
│   └── router.py              # POST /v1/chat
│
├── tools/                     # MCP tools que nanobot consume como client
│   ├── rag_search_tools.py    # [EXISTENTE]
│   └── odoo_tools.py          # [NUEVO] Proxy a http://odoo18:8069/api/*
│
├── llm_emulation/
│   └── nanobot_serve_bridge.py # [MODIFICAR] Soportar endpoint por tenant
│
├── config/models.py           # [MODIFICAR] + RedisConfig
└── main.py                    # [MODIFICAR] + chat router
```

---

## Plan de Ejecución (9 Pasos)

### PASO 1: Infraestructura base
- Redis DB 3: `RedisSessionManager` (historial + state)
- `TenantConfig` Pydantic model (lee `/contenedores/tenants/<id>/config.yaml`)
- `TenantRegistry`: descubre tenants por carpetas existentes en `/contenedores/tenants/`
- `ContextWriter`: escribe `state.json`, `history.md`, `rule_context.md`

### PASO 2: Home del tenant católico
Crear `/contenedores/tenants/catolico/` con estructura completa:

**`.nanobot/config.json`**:
- Provider: Gemini 2.0 Flash
- Telegram: disabled
- Heartbeat: disabled
- MCP servers: flamehaven RAG (search_rag, search_rag_semantic)
- restrictToWorkspace: true
- Skills: rag-manager, voice-manager, gemini-vision (symlinks)

**`workspace/SOUL.md`**:
- Identidad: asistente teológico católico
- Regla: leer context/ antes de responder
- Idioma: español
- Restricciones: no inventar doctrina, citar fuentes

**`workspace/AGENTS.md`**:
- Solo "defaults" (Gemini Flash, temp 0.4)
- Sin delegation, sin sub-agentes

**`workspace/USER.md`**:
- Contexto: público católico, consultas sobre lecturas, biblia, doctrina
- URLs de servicios disponibles

**`workspace/CONSTANTS.md`**:
- Skills obligatorias por tipo de entrada (audio → voice-manager, imagen → gemini-vision)
- Tools MCP disponibles: search_rag, search_rag_semantic

**`config.yaml`** (para FastAPI):
```yaml
tenant_id: catolico
strategy: keyword
nanobot_port: 8766
chat_ttl: 1800
max_history: 30

keywords:
  lecturas: ["evangelio", "lectura", "primera lectura", "salmo"]
  biblia: ["versículo", "cita bíblica", "génesis", "mateo"]
  santoral: ["santo del día", "santoral", "festividad"]
  calendario: ["calendario litúrgico", "tiempo litúrgico"]
```

### PASO 3: Lanzar nanobot serve del tenant
- Modificar `entrypoint.sh`: iterar `/tenants/*/` y lanzar un serve por cada uno
- Verificar:
  - `HOME=/tenants/catolico nanobot serve --port 8766` arranca sin errores
  - SOUL.md se carga correctamente
  - MCP tools (RAG) se conectan
  - Skills (voice-manager, gemini-vision) se registran

### PASO 3.5: Pruebas de prompting 🧪

> [!IMPORTANT]
> **Antes de integrar con FastAPI**, probar directamente contra el nanobot serve del tenant que cada etapa del flujo se resuelve bien.

Escribir manualmente los archivos `context/` y enviar prompts al serve para verificar:

| Test | Archivo `rule_context.md` | Prompt del usuario | Resultado esperado |
|------|--------------------------|--------------------|--------------------|
| T1: Saludo | "Saluda al usuario, preséntate como asistente católico" | "Hola" | Saludo + presentación |
| T2: Lecturas | "El usuario quiere las lecturas del día. Usa la tool MCP search_rag" | "Evangelio de hoy" | Texto de las lecturas (vía RAG) |
| T3: Biblia | "El usuario pide un versículo. Búscalo" | "Juan 3:16" | Versículo correcto |
| T4: Doctrina | "El usuario pregunta doctrina. Usa RAG para buscar" | "¿Qué es la gracia?" | Respuesta con fuentes del RAG |
| T5: Imagen | "El usuario envió una imagen" | (imagen adjunta) | Skill gemini-vision describe la imagen |
| T6: Audio | "El usuario envió un audio" | (audio adjunto) | Skill voice-manager transcribe |
| T7: Fuera de tema | "Esto no es una consulta teológica, informar amablemente" | "¿Cuánto sale un iPhone?" | Respuesta acotada al rol |

**Método de prueba:**
```bash
# Escribir contexto manualmente
echo '{"session": "test1"}' > /tenants/catolico/context/state.json
echo "# Turno: Saludo inicial" > /tenants/catolico/context/rule_context.md

# Enviar prompt al serve
curl -X POST http://localhost:8766/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [{"role": "user", "content": "Hola, buenas tardes"}]
  }'
```

**Si falla**: ajustar SOUL.md, CONSTANTS.md, o skills del tenant. Iterar hasta que todos los tests pasen.

### PASO 4: Orquestador + endpoint
- `orchestrator.py`: 
  1. Redis → cargar state + history
  2. Classify (keyword para católico)
  3. ContextWriter → escribe context/ en el home del tenant
  4. LLMBridge → POST al nanobot serve del tenant (puerto de config.yaml)
  5. Parsear respuesta
  6. Redis → actualizar state + history
  7. Return respuesta
- `router.py`: POST /v1/chat
- `LLMBridge` modificado: acepta `port` como parámetro

### PASO 5: Tests end-to-end católico
- curl al endpoint FastAPI → respuesta del nanobot católico
- Verificar que context/ se escribe correctamente
- Verificar memoria Redis (historial persiste entre mensajes)
- Integrar con n8n: reemplazar AI Agent por HTTP Request a `/v1/chat`

### PASO 6: MCP tools de Odoo
- `odoo_tools.py`: MCP tools nativas que llaman a `http://odoo18:8069/api/*`
  - get_products, get_product_detail, search_client, create_client
  - create_cart, add_item, get_cart_summary, confirm_cart, cancel_cart
- Registrar en el MCP server de FastAPI

### PASO 7: Home del tenant Odoo + RulesEngine
- Crear `/contenedores/tenants/odoo_repuestos/`
- SOUL.md: asistente de ventas, lee context/ para regla y estado
- config.json: MCP servers = odoo + flamehaven
- Skills: odoo-manager, voice-manager, gemini-vision
- `rules_engine.py`: evalúa flags → regla activa
- `config.yaml` con reglas (migradas de tabla `reglas_ia`)

### PASO 7.5: Pruebas de prompting Odoo 🧪
Igual que 3.5 pero con el flujo completo de Odoo:
- T1: Saludo → pedir DNI
- T2: DNI proporcionado → buscar cliente con MCP tool
- T3: Cliente encontrado → ofrecer catálogo
- T4: Búsqueda de productos → mostrar resultados
- T5: Selección → crear carrito
- T6: Confirmar → confirmar orden
- Etc.

### PASO 8: Tests end-to-end Odoo
- Flujo completo: identificación → búsqueda → carrito → pago
- Verificar flags en Redis
- Integrar con n8n

---

## Dependencias

```
redis[hiredis]>=5.0
pyyaml
httpx          # ya existe
scrapling      # ya existe
```

> [!IMPORTANT]
> **¿Aprobás este plan?** Cambios respecto a la versión anterior:
> 1. **Tenants en `/contenedores/tenants/<id>/`** — separados de conti_home, misma estructura
> 2. **Carpeta `context/`** — FastAPI escribe state/history/rule ahí, nanobot los lee como archivos
> 3. **Paso 3.5 y 7.5** — pruebas de prompting por cada etapa antes de integrar
