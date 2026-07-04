#!/bin/sh
# entrypoint.sh — instala socat one-time y arranca socat TCP↔omp_bridge.
#
# Arquitectura:
#   - socat escucha en :7891 TCP
#   - por cada conexión entrante, fork+exec omp_bridge.py
#   - omp_bridge.py hace chdir al OMP_CIRCUIT_CWD y exec omp subprocess
#
# Multi-circuit: cada RpcClient en conti-backend setea su propio
# OMP_CIRCUIT_CWD via env={}. omp_bridge hereda el env del RpcClient
# subprocess (que es a su vez un hijo de socat). Por cada circuit,
# el cwd del omp subprocess será diferente.
#
# Cambiar modelo/provider: editar compose y `up -d conti-omp`. Sin rebuild.

set -eu

# ── Install socat one-time ─────────────────────────────────────
if ! command -v socat >/dev/null 2>&1; then
    echo "[entrypoint] Installing socat..."
    apt-get update
    apt-get install -y --no-install-recommends socat netcat-openbsd
    rm -rf /var/lib/apt/lists/*
    echo "[entrypoint] socat installed."
else
    echo "[entrypoint] socat already present: $(socat -V 2>&1 | head -1)"
fi

# ── Install socat one-time (para healthcheck netcat) ──────────
if ! command -v socat >/dev/null 2>&1; then
    echo "[entrypoint] Installing socat..."
    apt-get update
    apt-get install -y --no-install-recommends socat netcat-openbsd
    rm -rf /var/lib/apt/lists/*
    echo "[entrypoint] socat installed."
else
    echo "[entrypoint] socat already present: $(socat -V 2>&1 | head -1)"
fi

# ── Install codebase-memory-mcp + config MCP ──────────────────
# codebase-memory-mcp es un MCP server stdio que indexa repos como
# knowledge graph. omp lo descubre desde .omp/mcp.json del profile.
CBM_BIN="/home/conti/.local/bin/codebase-memory-mcp"
if [ ! -f "$CBM_BIN" ]; then
    echo "[entrypoint] Installing codebase-memory-mcp..."
    curl -fsSL "https://github.com/DeusData/codebase-memory-mcp/releases/latest/download/codebase-memory-mcp-linux-amd64-portable.tar.gz" -o /tmp/cbm.tar.gz
    cd /tmp && tar xzf cbm.tar.gz && cp codebase-memory-mcp "$CBM_BIN" && chmod +x "$CBM_BIN"
    rm -f /tmp/cbm.tar.gz /tmp/codebase-memory-mcp
    echo "[entrypoint] codebase-memory-mcp installed: $($CBM_BIN --version 2>&1)"
fi

# ── Configure models.yml for custom LLM provider ─────────────
# NOTA: Si el provider es built-in en omp (ej: xiaomi-token-plan-sgp),
# NO se necesita models.yml. La API key se pasa via env var
# (ej: XIAOMI_TOKEN_PLAN_SGP_API_KEY).
# Solo crear models.yml si se usa un provider custom no built-in.
if [ -n "${OMP_CUSTOM_PROVIDER:-}" ]; then
    PROVIDER_ID="${OMP_CUSTOM_PROVIDER}"
    PROVIDER_BASE_URL="${OMP_CUSTOM_BASE_URL:-}"
    PROVIDER_API_KEY="${OMP_CUSTOM_API_KEY:-}"
    MODEL_ID="${OMP_MODEL##*/}"
    mkdir -p /home/conti/.omp/agent
    cat > /home/conti/.omp/agent/models.yml << MODELSEOF
providers:
  ${PROVIDER_ID}:
    baseUrl: ${PROVIDER_BASE_URL}
    apiKey: ${PROVIDER_API_KEY}
    api: openai-completions
    models:
      - id: ${MODEL_ID}
        name: ${OMP_MODEL}
        api: openai-completions
        reasoning: true
        input: [text]
        contextWindow: 1048576
        maxTokens: 131072
MODELSEOF
    echo "[entrypoint] models.yml written: provider=${PROVIDER_ID} model=${MODEL_ID}"
else
    echo "[entrypoint] Using built-in provider (no models.yml needed)"
fi

OMP_PROFILE_DIR="/home/conti/.omp/profiles/${OMP_PROFILE:-conti}/agent"
mkdir -p "$OMP_PROFILE_DIR"
cat > "$OMP_PROFILE_DIR/mcp.json" << 'MCPEOF'
{
  "$schema": "https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/src/config/mcp-schema.json",
  "mcpServers": {
    "codebase-memory": {
      "command": "/home/conti/.local/bin/codebase-memory-mcp",
      "args": [],
      "enabled": true
    }
  }
}
MCPEOF
echo "[entrypoint] MCP config written to $OMP_PROFILE_DIR/mcp.json"

# ── Create skills for omp ──────────────────────────────────────
# Skills son markdown files que omp carga como instrucciones.
# Le dan a omp acceso a las MCP tools del backend y a codebase-memory-mcp
# sin depender del protocolo MCP nativo (que tiene issues de compatibilidad).
SKILLS_DIR="$OMP_PROFILE_DIR/skills"
mkdir -p "$SKILLS_DIR/mcp-backend-tools" "$SKILLS_DIR/codebase-memory"

# Skill: MCP Backend Tools (bash+curl a conti-backend:9001/mcp/call)
cat > "$SKILLS_DIR/mcp-backend-tools/SKILL.md" << 'SKILLEOF'
---
name: mcp-backend-tools
description: Acceso a las MCP tools del backend conti-backend vía bash+curl. Usar cuando necesites ejecutar tools MCP como run_salvar, sourcebot_search, get_config, get_rules, get_onboarding, validate_python_syntax, run_pytest, ponytail_record_trace, odoo_*, etc.
---

# MCP Backend Tools

El backend `conti-backend` expone 73 tools MCP en `http://conti-backend:9001/mcp`.
Para invocarlas, usá bash+curl con el endpoint REST `/mcp/call`.

```bash
curl -s -X POST http://conti-backend:9001/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"name": "TOOL_NAME", "arguments": {}}'
```

## Tools más usadas

### GitOps
- `run_salvar(summary="feat: descripción")` — Commit + push
- `run_promover(summary="sync: descripción")` — Merge develop → main

### Governance
- `get_config()` — Configuración del backend
- `get_onboarding()` — Workspace info
- `get_rules()` — Reglas operativas

### Code quality
- `validate_python_syntax(paths=["app/mcp/router.py"])` — Validar sintaxis
- `run_pytest(circuit="backend")` — Ejecutar tests

### Búsqueda
- `sourcebot_search(query="django views", limit=5)` — Buscar código

### Observabilidad
- `ponytail_record_trace(trace_id="tr-xxx", circuit="backend", markdown="...")` — Persistir traza
SKILLEOF

# Skill: Codebase Memory (knowledge graph via codebase-memory-mcp)
cat > "$SKILLS_DIR/codebase-memory/SKILL.md" << 'SKILLEOF'
---
name: codebase-memory
description: Knowledge graph de código vía codebase-memory-mcp. Usar para buscar funciones, clases, call paths, architecture overview, dead code detection sobre los repos indexados.
---

# Codebase Memory (Knowledge Graph)

Tenés acceso a `codebase-memory-mcp` (vía MCP stdio). Ya tiene indexados los 3 repos.

## Projects indexados
- `desarrollo` → /desarrollo (153K nodos, 561K edges)
- `compose` → /compose (134K nodos, 468K edges)
- `contenedores-conti-backend` → /contenedores/conti-backend (4.4K nodos, 8.6K edges)

## Tools principales
- `search_graph(name_pattern=".*router.*", project="contenedores-conti-backend")` — Buscar por nombre
- `get_architecture(project="contenedores-conti-backend")` — Overview del proyecto
- `trace_path(function_name="run_task", direction="both")` — Call graph
- `get_code_snippet(qualified_name="...")` — Leer source de una función
- `query_graph(query="MATCH (f:Function)-[:CALLS]->(g) RETURN g.name")` — Cypher queries
SKILLEOF

echo "[entrypoint] Skills created in $SKILLS_DIR"

# ── Skills por circuito ────────────────────────────────────────
mkdir -p "$SKILLS_DIR/circuit-desarrollo" "$SKILLS_DIR/circuit-produccion" "$SKILLS_DIR/circuit-backend"

cat > "$SKILLS_DIR/circuit-desarrollo/SKILL.md" << 'SKILLEOF'
---
name: circuit-desarrollo
description: Reglas y tools del circuito desarrollo (/desarrollo, rama develop). Usar cuando el circuito activo es desarrollo.
---
# Circuito: Desarrollo
**Workspace**: `/desarrollo` | **Rama**: `develop` | **Git**: `run_salvar`
## Reglas
1. Solo editá dentro de `/desarrollo`
2. ANTES de commitear: `validate_python_syntax(paths=[archivos])`
3. DESPUÉS de editar: `run_pytest(circuit="desarrollo")`
4. Si test falla → NO commitear, arreglar primero
5. `run_salvar(summary="feat: descripción")` para commitear
6. NO `run_promover` (eso es producción), NO `run_hotfix_sync`
## Tools MCP (bash+curl a http://conti-backend:9001/mcp/call)
- `run_salvar(summary="...")` — commit+push develop
- `validate_python_syntax(paths=[...])` — validar sintaxis
- `run_pytest(circuit="desarrollo")` — ejecutar tests
- `sourcebot_search(query="...", limit=5)` — buscar código
SKILLEOF

cat > "$SKILLS_DIR/circuit-produccion/SKILL.md" << 'SKILLEOF'
---
name: circuit-produccion
description: Reglas y tools del circuito produccion (/compose, rama main). Usar cuando el circuito activo es produccion.
---
# Circuito: Producción
**Workspace**: `/compose` (lectura) + `/desarrollo` (escritura) | **Rama**: `main` | **Git**: `run_promover`, `run_hotfix_sync`
## Reglas
1. `/compose` es read-only para código (NO editar directamente)
2. Para promover: `run_promover(summary="sync: descripción")`
3. Para hotfix: editar /compose → `run_hotfix_sync(summary="fix: descripción")`
4. DESPUÉS de promover: Luis corre `bash /compose/3-despliegue.sh`
5. SIEMPRE verificar `/desarrollo` limpio antes de promover
## Tools MCP (bash+curl a http://conti-backend:9001/mcp/call)
- `run_promover(summary="...")` — merge develop→main
- `run_hotfix_sync(summary="...")` — sync main→develop
- `get_container_health(container="chatui")` — estado de contenedor
SKILLEOF

cat > "$SKILLS_DIR/circuit-backend/SKILL.md" << 'SKILLEOF'
---
name: circuit-backend
description: Reglas y tools del circuito backend (/contenedores/conti-backend, rama main). Usar cuando el circuito activo es backend.
---
# Circuito: Backend
**Workspace**: `/contenedores/conti-backend` | **Rama**: `main` | **Git**: `run_salvar` directo a main
## Reglas
1. Solo editá dentro de `/contenedores/conti-backend`
2. **PRE-COMMIT OBLIGATORIO**:
   a) `validate_python_syntax(paths=[archivos])` → si falla, NO commitear
   b) `run_pytest(circuit="backend", test_path="tests/test_x.py")` → debe pasar
   c) `run_pytest(circuit="backend")` → suite completa antes del commit
3. `run_salvar(summary="feat: descripción")` para commitear
4. NO hay flujo develop↔main (solo main)
5. `run_promover` y `run_hotfix_sync` NO aplican
## Tools MCP (bash+curl a http://conti-backend:9001/mcp/call)
- `run_salvar(summary="...", force_branch="main")` — commit+push main
- `validate_python_syntax(paths=[...])` — validar sintaxis
- `run_pytest(circuit="backend")` — ejecutar tests
- `get_config()` — ver configuración
- `get_rules()` — ver reglas operativas
SKILLEOF

# ── Skills por categoría MCP ───────────────────────────────────
mkdir -p "$SKILLS_DIR/odoo-tools" "$SKILLS_DIR/gitops-tools" "$SKILLS_DIR/observability-tools"

cat > "$SKILLS_DIR/odoo-tools/SKILL.md" << 'SKILLEOF'
---
name: odoo-tools
description: Tools MCP para Odoo ERP (21 tools). Usar para consultar/crear/modificar productos, clientes, pedidos, facturas o pagos.
---
# Odoo Tools (21 tools MCP)
## Conexiones: prod (default), dev, resto
## Tools
- **Productos**: `odoo_list_products`, `odoo_get_product_detail`
- **Clientes**: `odoo_search_clients`, `odoo_list_clients`, `odoo_create_client`
- **Pedidos**: `odoo_create_order`, `odoo_create_cart`, `odoo_add_item_to_cart`, `odoo_get_cart_summary`, `odoo_confirm_cart`
- **Facturación**: `odoo_create_invoice`, `odoo_get_invoice_status`
- **Pagos**: `odoo_register_payment`, `odoo_upload_payment_proof`, `odoo_create_mercadopago_preference`
- **Contexto**: `odoo_get_ai_context`, `odoo_test_connection`
## Ejemplo
```bash
curl -s -X POST http://conti-backend:9001/mcp/call -H "Content-Type: application/json" -d '\''{"name": "odoo_list_products", "arguments": {"search": "aceite", "limit": 3}}'\''
```
SKILLEOF

cat > "$SKILLS_DIR/gitops-tools/SKILL.md" << 'SKILLEOF'
---
name: gitops-tools
description: Tools MCP para Git (commit, push, merge, hotfix). Usar para operaciones Git seguras.
---
# GitOps Tools
- `run_salvar(summary, confirm)` — commit+push
- `run_promover(summary, confirm)` — merge develop→main
- `run_hotfix_sync(summary, confirm)` — sync main→develop
- `get_git_status`, `get_git_log`, `diff_with_develop`, `get_pipeline_summary`
SKILLEOF

cat > "$SKILLS_DIR/observability-tools/SKILL.md" << 'SKILLEOF'
---
name: observability-tools
description: Tools MCP para trazas (Ponytail). Usar al final de cada tarea para persistir la traza.
---
# Observability Tools
- `ponytail_record_trace(trace_id, circuit, markdown, auto_commit)` — Persistir traza MD en .ponytail/traces/ del repo
SKILLEOF

echo "[entrypoint] All skills created in $SKILLS_DIR"

# ── Start omp_proxy (NDJSON proxy TCP ↔ omp subprocess) ───────
# omp_proxy.py reemplaza a omp_bridge.py + socat.
# Proxy NDJSON limpio: TCP→stdin de omp, stdout de omp→TCP.
# stderr va a pipe separado (logs, NO al socket).
echo "[entrypoint] Starting omp_proxy on :7891 (cwd=${OMP_CIRCUIT_CWD:-/desarrollo}, model=${OMP_MODEL:-?})"
exec python3 /usr/local/bin/omp_proxy.py