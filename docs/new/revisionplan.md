# Plan de Migración a Hermes-Agent — Revisión y Seguimiento

> **Sistema:** `conti-backend`  
> **Fecha:** 2026-05-16  
> **Fuentes verificadas:** `ESTADO_REAL.md`, `PLAN_03_MIGRACION_HERMES.md`, docs oficiales Hermes-Agent, Lushbinary guide (abril 2026)

---

## Resumen Ejecutivo

Migración gradual de `nanobot` a Hermes-Agent manteniendo todos los endpoints actuales. La estrategia se basa en perfiles Hermes como reemplazo 1-a-1 de los procesos nanobot existentes, con el FastAPI como facade sin cambios.

**Arquitectura actual (5 procesos):**
```
entrypoint.sh
├── FastAPI :9001          — facade REST/MCP (sin cambios)
├── nanobot gateway :18790 — Telegram (contihome)
├── nanobot serve :8765    — LLM general (contihome / IDE)
├── nanobot serve :8766    — LLM tenant católico
└── nanobot serve :8767    — LLM tenant resto
```

**Arquitectura target (4 procesos):**
```
entrypoint.sh
├── FastAPI :9001                       — facade REST/MCP (sin cambios)
├── hermes gateway --profile contihome  — Telegram + API Server :8765
├── hermes api-server --profile catolico --port 8766
└── hermes api-server --profile resto   --port 8767
```

---

## Verificación Arquitectónica — Multi-Agente en Hermes

**Multi-agente en Hermes = múltiples procesos separados, NO una sola instancia.**

Evidencia de la documentación oficial y Lushbinary (abril 2026):
- *"profile-based **multi-instance** deployment where each agent gets its own config, memory, skills"*
- *"**Separate gateway processes** — Run each profile's gateway as a separate systemd service"*
- *"Each profile is **fully independent**. Creating a profile sets up a new directory with its own config.yaml"*

**Costo de recursos:** Los perfiles Hermes son procesos Python ligeros — no cargan ningún modelo en memoria. El cuello de botella es la API externa (kilo.ai), no el proceso. Un VPS típico maneja 3-5 perfiles sin problema.

**Sobre el prefijo MCP (`mcp_contibackend_*`):** No es un problema. El prefijo es interno a Hermes — el LLM lo usa para enrutar la llamada al servidor MCP correcto. Todos los clientes externos (Kilocode, Cline, ChatOrchestrator) siguen usando el endpoint `/mcp` de FastAPI con los nombres originales de las tools. No se requiere ningún wrapper adicional.

---

## Tabla de Equivalencia

| Componente nanobot | Equivalente Hermes | Notas |
|---|---|---|
| `nanobot gateway :18790` (Telegram) | `hermes gateway --profile contihome` | Config en `gateway.yaml` del perfil |
| `nanobot serve :8765` (LLM general) | `hermes api-server --profile contihome --port 8765` | OpenAI-compatible nativo, misma interfaz |
| `nanobot serve :8766` (LLM católico) | `hermes api-server --profile catolico --port 8766` | Proceso separado, SOUL.md propio |
| `nanobot serve :8767` (LLM resto) | `hermes api-server --profile resto --port 8767` | Proceso separado |
| `.nanobot/config.json` providers | `config.yaml` + `.env` por perfil | Ver mapeo §Configuración LLM |
| `SOUL.md` (workspace) | `SOUL.md` en `$HERMES_HOME/SOUL.md` | Un archivo por perfil |
| Skills en `.nanobot/workspace/skills/` | Skills en `$HERMES_HOME/skills/` | Migración manual por valor |
| 43 tools MCP en FastAPI `/mcp` | Mismas 43 tools vía `http://localhost:9001/mcp/sse` | Hermes las consume como MCP server HTTP |

### Mapeo de Configuración nanobot → Hermes

| nanobot `config.json` | Hermes `config.yaml` | Hermes `.env` |
|---|---|---|
| `providers.openai.apiBase` | `model.base_url` | — |
| `providers.openai.apiKey` | — | `OPENAI_API_KEY` |
| `agents.defaults.model` | `model.model` | — |
| `channels.telegram.token` | `gateway.yaml: telegram.token` | o `TELEGRAM_TOKEN` |
| `channels.telegram.allowFrom` | `gateway.yaml: telegram.allow_from` | — |
| `gateway.port` | `--port` en comando de arranque | — |

---

## Estructura de Perfiles

```
/app/hermes_profiles/
├── contihome/
│   ├── config.yaml      ← LLM provider, MCP servers
│   ├── .env             ← secrets
│   ├── SOUL.md          ← personalidad Conti
│   ├── gateway.yaml     ← Telegram config
│   └── skills/
├── catolico/
│   ├── config.yaml
│   ├── .env
│   ├── SOUL.md          ← personalidad católico
│   └── skills/
└── resto/
    ├── config.yaml
    ├── .env
    ├── SOUL.md
    └── skills/
```

---

## Fases del Plan

### ✅ FASE 1 — Infraestructura
**Estado: COMPLETADA**

- [x] Agregar `hermes-agent` a `requirements.txt`
- [x] Crear estructura de directorios `/app/hermes_profiles/{contihome,catolico,resto}/`
- [x] Crear `config.yaml` base para cada perfil

---

### ✅ FASE 2 — Perfil `contihome`
**Estado: COMPLETADA**

- [x] Crear `SOUL.md` (migrado desde `conti_home/.nanobot/workspace/SOUL.md`)
- [x] Configurar `config.yaml` con kilo.ai como `custom` provider y MCP server HTTP
- [x] Configurar `gateway.yaml` con token de Telegram
- [x] Crear `config.yaml` + `SOUL.md` placeholder para perfiles `catolico` y `resto`

---

### ✅ FASE 3 — Entrypoint Hermes
**Estado: COMPLETADA**

- [x] Crear `entrypoint_hermes.sh` con procesos Hermes en lugar de nanobot
- [x] El `ChatOrchestrator` y el bridge de emulación LLM NO requieren cambios de código
- [x] Hermes API Server expone exactamente `/v1/chat/completions` — mismos puertos `:8765`, `:8766`, `:8767`

**Nota clave:** No hay cambios en `app/` — solo cambia quién escucha en los puertos LLM.

---

### ⏳ FASE 4 — Pruebas `contihome`
**Estado: PENDIENTE — Requiere `hermes-agent` instalado en el contenedor**

**Prerequisito:** Reconstruir imagen Docker con `hermes-agent` instalado.

**Prueba A — Telegram:**
```bash
HERMES_HOME=/app/hermes_profiles/contihome hermes gateway start
# Enviar mensaje desde Telegram como usuario luisdalmasso
# Verificar: responde en español, usa SOUL.md correcto
```

**Prueba B — Emulador LLM (IDE):**
```bash
curl http://localhost:8765/health
# Desde Kilocode/Cline: enviar prompt, verificar streaming
```

**Prueba C — MCP Tools:**
```bash
HERMES_HOME=/app/hermes_profiles/contihome hermes chat
# Prompt: "lista los containers docker disponibles"
# Verificar: invoca get_container_health vía MCP
```

---

### ⏳ FASE 5 — Perfil `catolico` (CLI aislada)
**Estado: PENDIENTE**

> ⚠️ FastAPI sigue usando nanobot serve :8766 hasta completar FASE 6.

```bash
HERMES_HOME=/app/hermes_profiles/catolico hermes chat
# Probar: "¿Cuál es el evangelio de hoy?"
# Probar: "Busca el salmo 23"
```

Antes de esta fase: actualizar `SOUL.md` de católico con la personalidad real
(fuente: `/tenants/catolico/.nanobot/` o equivalente).

---

### ⏳ FASE 6 — Integración FastAPI `catolico`
**Estado: PENDIENTE**

Una vez validada FASE 5, iniciar Hermes API server para católico:
```bash
HERMES_HOME=/app/hermes_profiles/catolico hermes api-server --port 8766
```

El `ChatOrchestrator` **NO requiere cambios** — sigue haciendo
`POST http://localhost:8766/v1/chat/completions`.

Prueba E2E: **Webchat → Superinterface → n8n → FastAPI → Hermes :8766**

---

### ⏳ FASE 7 — Perfil `resto`
**Estado: PENDIENTE**

Replicar FASE 5+6 para el tenant `resto` en puerto `:8767`.

---

### ⏳ FASE 8 — Limpieza y Consolidación
**Estado: PENDIENTE**

- [ ] Reemplazar `entrypoint.sh` con `entrypoint_hermes.sh`
- [ ] Remover `nanobot-ai` de `requirements.txt`
- [ ] Remover `nanobot` del `Dockerfile`
- [ ] Migrar skills valiosas de `.nanobot/workspace/skills/` a perfiles Hermes
- [ ] Actualizar healthcheck en `docker-compose.conti.yml`
- [ ] Archivar `/conti_home/.nanobot/` como backup

---

## Registro de Riesgos

| Riesgo | Prob | Impacto | Mitigación |
|--------|------|---------|------------|
| kilo.ai no acepta `base_url` custom en Hermes | Media | Alto | Validar en FASE 4; fallback: OpenRouter |
| Hermes API server no soporta `session_id` en payload | Baja | Medio | Hermes maneja sesiones por perfil nativamente |
| Streaming incompatible con cliente actual | Baja | Medio | Hermes `/v1/chat/completions` es spec-compatible |
| SOUL.md de católico/resto son placeholders | Alta | Bajo | Actualizar antes de FASE 5 con personalidades reales |

---

## Archivos Creados en Fases 1-3

```
/contenedores/conti-backend/
├── requirements.txt                     ← hermes-agent agregado
├── app/hermes_profiles/
│   ├── contihome/
│   │   ├── config.yaml
│   │   ├── .env
│   │   ├── SOUL.md
│   │   └── gateway.yaml
│   ├── catolico/
│   │   ├── config.yaml
│   │   ├── .env
│   │   └── SOUL.md
│   └── resto/
│       ├── config.yaml
│       ├── .env
│       └── SOUL.md
└── entrypoint_hermes.sh                 ← nuevo entrypoint con Hermes
```
