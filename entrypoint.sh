#!/bin/bash
set -e

echo "🚀 Iniciando Conti Backend + ClawTeam + nanobot..."

# Verificar instalaciones
tmux -V && clawteam --help | head -1 && nanobot --help | head -1 && python3 -m uvicorn --help >/dev/null

# Crear sesión tmux para ClawTeam
tmux new-session -d -s clawteam 2>/dev/null || true

CONTI_BACKEND_CONFIG="${CONTI_BACKEND_CONFIG:-/app/config/app_config.json}"
GATEWAY_CONFIG="${GATEWAY_CONFIG:-/home/nanobot/.nanobot/config.json}"
NANOBOT_SERVE_CONFIG="${NANOBOT_SERVE_CONFIG:-/home/nanobot/llm_serve_config.json}"
LEGACY_SERVE_CONFIG="${LEGACY_SERVE_CONFIG:-/home/nanobot/.nanobot/nanobot/config.json}"
BACKEND_HOST="${CONTI_BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${CONTI_BACKEND_PORT:-9001}"
SERVE_HOST="${NANOBOT_SERVE_HOST:-0.0.0.0}"
SERVE_PORT="${NANOBOT_SERVE_PORT:-8765}"

if [ ! -f "${NANOBOT_SERVE_CONFIG}" ]; then
	if [ -f "${LEGACY_SERVE_CONFIG}" ]; then
		cp "${LEGACY_SERVE_CONFIG}" "${NANOBOT_SERVE_CONFIG}"
	elif [ -f "${GATEWAY_CONFIG}" ]; then
		cp "${GATEWAY_CONFIG}" "${NANOBOT_SERVE_CONFIG}"
	fi
fi

# Iniciar gateway de nanobot en puerto 18790
echo "🌐 Gateway nanobot en puerto ${GATEWAY_PORT:-18790}"
nanobot gateway --port ${GATEWAY_PORT:-18790} --config "${GATEWAY_CONFIG}" &

# Iniciar nanobot serve para emulación OpenAI-compatible
echo "🤖 nanobot serve en http://${SERVE_HOST}:${SERVE_PORT}"
nanobot serve --host "${SERVE_HOST}" --port "${SERVE_PORT}" --config "${NANOBOT_SERVE_CONFIG}" &

# Iniciar backend FastAPI propio
echo "🧠 Conti Backend en http://${BACKEND_HOST}:${BACKEND_PORT}"
CONTI_BACKEND_CONFIG="${CONTI_BACKEND_CONFIG}" python3 -m uvicorn app.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" --reload --reload-dir /app/app &

# Iniciar Web UI de ClawTeam
echo "🖥️ Web UI ClawTeam en http://localhost:8080"
clawteam board serve --port 8080 --host 0.0.0.0 &

echo "✅ Listo. Gateway:${GATEWAY_PORT:-18790} | Serve:${SERVE_PORT} | Backend:${BACKEND_PORT} | WebUI:8080"

# Mantener vivo
wait