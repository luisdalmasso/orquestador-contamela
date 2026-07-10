# Session Context — Circuito Backend

> **Última actualización**: 2026-07-10
> **Propósito**: Evitar amnesia en nuevas sesiones del circuito backend

---

## 1. Identidad del circuito

| Campo | Valor |
|-------|-------|
| **Circuito** | `backend` |
| **Workspace** | `/contenedores/conti-backend` |
| **Rama** | `main` |
| **Repo** | `orquestador-contamela` |
| **Git action** | `run_salvar` → `main` |
| **Tools nativos** | terminal, file_editor, task_tracker |

---

## 2. MCP Backend — Cómo acceder a las 85 tools

### Endpoint
```
POST http://conti-backend:9001/mcp/call
Content-Type: application/json
```

### Formato
```bash
curl -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "NOMBRE_TOOL", "arguments": {...}}'
```

### Listar tools
```bash
curl http://conti-backend:9001/mcp/tools
```

---

## 3. Codebase Memory — Project parameter OBLIGATORIO

**⚠️ SIEMPRE usar `project: "contenedores-conti-backend"`**

### Tools disponibles (11)

| Tool | Uso |
|------|-----|
| `search_graph` | Buscar por pattern: `{"name_pattern": ".*router.*", "project": "contenedores-conti-backend"}` |
| `get_architecture` | Overview: `{"project": "contenedores-conti-backend"}` |
| `trace_path` | Call graph: `{"function_name": "run_task", "project": "contenedores-conti-backend"}` |
| `get_code_snippet` | Source: `{"qualified_name": "contenedores-conti-backend.app.módulo.Clase", "project": "contenedores-conti-backend"}` |
| `query_graph` | Cypher: `{"query": "MATCH ...", "project": "contenedores-conti-backend"}` |
| `get_graph_schema` | Schema: `{"project": "contenedores-conti-backend"}` |
| `list_projects` | Proyectos indexados |
| `index_repository` | Indexar repo |
| `index_status` | Estado de indexación |

### Projects indexados
- `contenedores-conti-backend` → 5,618 nodes, 10,242 edges
- `desarrollo` → 154,867 nodes, 574,516 edges
- `compose` → 134,335 nodes, 468,961 edges

---

## 4. Otras tools MCP importantes

### Bootstrap
```bash
# Health check
curl -d '{"tool": "health_check", "arguments": {}}'

# Config
curl -d '{"tool": "get_config", "arguments": {}}'

# Onboarding
curl -d '{"tool": "get_onboarding", "arguments": {"brief": true}}'
```

### GitOps
```bash
# Estado del repo
curl -d '{"tool": "get_git_status", "arguments": {}}'

# Guardar (preview)
curl -d '{"tool": "run_salvar", "arguments": {"summary": "msg", "confirm": false}}'
```

### Stack
```bash
# Estado de contenedores
curl -d '{"tool": "get_container_health", "arguments": {}}'
```

---

## 5. Variables de entorno críticas

```bash
# En .env del repo
KILOCODE_API_KEY=eyJhbGci...
DEEPSEEK_API_KEY=eyJhbGci...
XIAOMI_TOKEN_PLAN_SGP_API_KEY=tp-sghoyfyruw54cyfk9wi5zqfrzny5caqi69lq4d63ly14ee9s
FLAMEHAVEN_API_KEY=sk_live_80b128...
GEMINI_API_KEY=AIzaSyBoKn...
TELEGRAM_BOT_TOKEN=8217561599:AAH...

# OMP
CONTI_USE_OMP_AGENT=true
OMP_HOST=conti-omp
OMP_PORT=7891
```

---

## 6. Archivos importantes

| Archivo | Propósito |
|---------|-----------|
| `docker-compose.conti.yml` | Compose principal |
| `.env` | Secrets (NO commitear) |
| `.env.example` | Template de variables |
| `app/main.py` | FastAPI app |
| `app/openhands_agent/circuits.py` | 4 circuitos |
| `app/web/router.py` | UI routes |
| `app/services/registry_service.py` | 85 MCP tools |
| `app/tools/catolico_tools.py` | SpineDigest integration |
| `docker/conti-omp/entrypoint.sh` | Skills de OMP |

---

## 7. UI actual

- **Dashboard**: `/ui` → health consolidado
- **Tools**: `/ui/tools` → catálogo MCP
- **Nav**: Dashboard | Circuitos | Hermes | OMP | Tools | Tenants | Observabilidad | Servicios | Seguridad

---

## 8. Lecciones aprendidas

1. **Siempre usar project correcto**: `"contenedores-conti-backend"` (no `"conti-backend"`)
2. **Las MCP tools SÍ funcionan** via HTTP al backend
3. **Las skills de OMP** se crean en `entrypoint.sh` (codebase-memory, odoo-tools, git-workflow, observability-tools)
4. **SpineDigest** ahora lee de env vars (no hardcodeado)
5. **Los secrets** están en `.env` (no hardcodeados en compose)
6. **UI obsoleta** eliminada: index.html, settings.html, rules.html, nanobots.html

---

## 9. Para nueva sesión

Al inicio de nueva sesión, verificar:
```bash
# 1. Backend accesible
curl http://conti-backend:9001/health

# 2. MCP tools
curl http://conti-backend:9001/mcp/tools | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('tools',[])))"

# 3. Codebase memory
curl -X POST http://conti-backend:9001/mcp/call \
  -d '{"tool": "list_projects", "arguments": {}}'
```
