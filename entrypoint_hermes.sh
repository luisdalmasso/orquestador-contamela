#!/bin/bash
set -e

# ============================================================
#  entrypoint_hermes.sh - conti-backend con Hermes-Agent
#  Stack actual: FastAPI (MCP backend) + Hermes-Agent multi-perfil
#  Nota: Se eliminó por completo nanobot y los tenants legacy
#        (ver git log para el entrypoint anterior).
# ============================================================

LOG_DIR="/app/logs"
mkdir -p "$LOG_DIR"

CONTI_BACKEND_CONFIG="${CONTI_BACKEND_CONFIG:-/app/config/app_config.json}"
BACKEND_HOST="${CONTI_BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${CONTI_BACKEND_PORT:-9001}"
PROFILES_DIR="/app/hermes_profiles"
HERMES_HOME_CONTIHOME="${HERMES_HOME_CONTIHOME:-/app/hermes_profiles/contihome}"

# ── Silenciar loggers MCP ruidosos (~8.6k INFO/día por perfil) ──────
# Poniendo /app/_site al frente de PYTHONPATH, site.py carga automáticamente
# /app/_site/sitecustomize.py en CADA proceso Python (hermes, uvicorn, ...),
# bajando a WARNING los loggers MCP que Hermes v0.14.x no silencia por defecto.
mkdir -p /app/_site
if [ ! -f /app/_site/sitecustomize.py ]; then
    cp /app/hermes_logging_quiet.py /app/_site/sitecustomize.py 2>/dev/null || true
fi
export PYTHONPATH="/app/_site:${PYTHONPATH:-/app}"

echo "🚀 Iniciando Conti Backend + Hermes-Agent..."

# Verificar instalaciones
python3 -m uvicorn --help >/dev/null && hermes --version >/dev/null

# ── Backend FastAPI :9001 ───────────────────────────────────────────

echo "🧠 Conti Backend en http://${BACKEND_HOST}:${BACKEND_PORT}"
CONTI_BACKEND_CONFIG="${CONTI_BACKEND_CONFIG}" python3 -m uvicorn app.main:app \
    --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" \
    > "$LOG_DIR/fastapi.log" 2>&1 &
FASTAPI_PID=$!

# ── Esperar a que uvicorn y los endpoints MCP estén listos antes de lanzar los gateways ───
# Comprobamos tanto /v1/chat/health como /mcp/tools (reduce race condition
# en el que Hermes arranca y falla con Connection refused). Aumentamos el
# timeout para tolerar arranques más lentos.
echo "⏳ Esperando a que uvicorn y /mcp/tools estén listos en :${BACKEND_PORT}..."
MAX_WAIT=120
WAITED=0
check_ready() {
    # 1) health
    curl -sf "http://127.0.0.1:${BACKEND_PORT}/v1/chat/health" > /dev/null 2>&1 && return 0
    # 2) mcp tools via JSON-RPC POST to /mcp (method: tools/list)
    curl -sf -X POST "http://127.0.0.1:${BACKEND_PORT}/mcp" \
        -H 'Content-Type: application/json' \
        -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
        > /dev/null 2>&1 && return 0
    return 1
}
until check_ready; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "⚠️ Timeout esperando uvicorn/mcp (${MAX_WAIT}s) — continuando de todos modos..."
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done
echo "✅ uvicorn/mcp listo (esperados ${WAITED}s)"

# ── Hermes profile gateways ─────────────────────────────────────────

# Perfil católico con API Server en :8766
echo "⛪ Hermes gateway [católico] en http://0.0.0.0:8766"
HERMES_HOME="${HERMES_HOME_CONTIHOME}" hermes -p catolico gateway run --accept-hooks \
    > "$LOG_DIR/hermes_catolico_gateway.log" 2>&1 &
sleep 3

# Perfil resto con API Server en :8767
echo "🍽️ Hermes gateway [resto] en http://0.0.0.0:8767"
HERMES_HOME="${HERMES_HOME_CONTIHOME}" hermes -p resto gateway run --accept-hooks \
    > "$LOG_DIR/hermes_resto_gateway.log" 2>&1 &
sleep 3

# Perfil odoo con API Server en :8768 (agente ERP multi-tenant Odoo)
echo "🏢 Hermes gateway [odoo] en http://0.0.0.0:8768"
HERMES_HOME="${HERMES_HOME_CONTIHOME}" hermes -p odoo gateway run --accept-hooks \
    > "$LOG_DIR/hermes_odoo_gateway.log" 2>&1 &
sleep 3

# Perfil odoo-resto (Telegram dedicado, sin API Server)
echo "🍽️ Hermes gateway [odoo-resto] en Telegram"
HERMES_HOME="${HERMES_HOME_CONTIHOME}" hermes -p odoo-resto gateway run --accept-hooks \
    > "$LOG_DIR/hermes_odoo_resto_gateway.log" 2>&1 &
sleep 3

# Perfil odoo-nudo (Telegram dedicado, sin API Server)
echo "🍝 Hermes gateway [odoo-nudo] en Telegram"
HERMES_HOME="${HERMES_HOME_CONTIHOME}" hermes -p odoo-nudo gateway run --accept-hooks \
    > "$LOG_DIR/hermes_odoo_nudo_gateway.log" 2>&1 &
sleep 3

# Perfil odoo-mendoza (BACKEND staff franquicia Mendoza) :8769 API + Telegram
echo "🏔️ Hermes gateway [odoo-mendoza] en http://0.0.0.0:8769 + Telegram"
HERMES_HOME="${HERMES_HOME_CONTIHOME}" hermes -p odoo-mendoza gateway run --accept-hooks \
    > "$LOG_DIR/hermes_odoo_mendoza_gateway.log" 2>&1 &
sleep 3

# Perfil mendoza (FRONTEND clientes franquicia Mendoza) :8770 API + wppconnect
echo "🛍️ Hermes gateway [mendoza] en http://0.0.0.0:8770 + wppconnect (cliente OCRL Mendoza)"
HERMES_HOME="${HERMES_HOME_CONTIHOME}" hermes -p mendoza gateway run --accept-hooks \
    > "$LOG_DIR/hermes_mendoza_gateway.log" 2>&1 &
sleep 3

# ── Hermes default (contihome) ──────────────────────────────────────

# Hermes dashboard web :9119
echo "🌐 Hermes dashboard en :9119"
hermes dashboard --port 9119 --host 0.0.0.0 --insecure --no-open \
    > "$LOG_DIR/hermes_dashboard.log" 2>&1 &

# Hermes gateway default contihome (Telegram) :18791
echo "🤖 Hermes gateway contihome en :18791"
HERMES_HOME="${HERMES_HOME_CONTIHOME}" hermes gateway run --accept-hooks \
    > "$LOG_DIR/hermes_contihome_gateway.log" 2>&1 &
HERMES_GW_PID=$!

# ── OpenHands Agent Server (API REST) ─────────────────────────────────
# Arranca en :3000 dentro del contenedor (mapeado a :3011 en el host
# según docker-compose.conti.yml). Es solo API REST; la GUI textual
# de OpenHands se levanta aparte en :3001 con `openhands web`.
echo "🤖 OpenHands Agent Server en :3000"
OPENHANDS_SUPPRESS_BANNER=1 agent-server --host 0.0.0.0 --port 3000 \
    > "$LOG_DIR/openhands_agent_server.log" 2>&1 &
AGENT_SERVER_PID=$!

# ── OpenHands Agent Canvas (GUI web oficial) ─────────────────────────
# Paquete npm `@openhands/agent-canvas`. Es la GUI web completa de OpenHands
# (la que se ve en github.com/OpenHands/OpenHands). Conecta a nuestro
# agent-server local en :3000 vía `AGENT_SERVER_URL`.
echo "🌐 OpenHands Agent Canvas en :3012"
nohup agent-canvas \
    --host 0.0.0.0 --port 3012 \
    > "$LOG_DIR/agent_canvas.log" 2>&1 &
AGENT_CANVAS_PID=$!

# ────────────────────────────────────────────────────────────────────

echo "✅ Listo."
echo "  FastAPI              :${BACKEND_PORT}    PID=$FASTAPI_PID"
echo "  Hermes default       :Telegram (contihome) PID=$HERMES_GW_PID"
echo "  OpenHands Agent API  :3000      PID=$AGENT_SERVER_PID"
echo "  OpenHands Agent Canvas :3012    PID=$AGENT_CANVAS_PID"
echo "  Hermes católico :8766  (API Server)"
echo "  Hermes resto    :8767  (API Server)"
echo "  Hermes odoo     :8768  (API Server - ERP multi-tenant)"
echo "  Hermes odoo-resto: Telegram (tenant resto)"
echo "  Hermes odoo-nudo : Telegram (tenant nudo)"
echo "  Hermes odoo-mendoza :8769  (API Server + Telegram, staff OCRL Mendoza)"
echo "  Hermes mendoza      :8770  (API Server + wppconnect, cliente OCRL Mendoza)"
echo "  Hermes dashboard:9119"
echo "  Logs: $LOG_DIR/"

wait $FASTAPI_PID
