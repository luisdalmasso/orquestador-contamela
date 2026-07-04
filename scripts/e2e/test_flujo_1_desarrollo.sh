#!/usr/bin/env bash
# Test E2E del flujo 1: commit local + push a develop (circuito desarrollo)
# Requisito: /desarrollo bind-mounted, rama develop activa, remoto origin configurado.
set -euo pipefail

HOST="${CONTI_HOST:-http://localhost:9001}"
REPO="${DESARROLLO_REPO:-/desarrollo}"
TEST_LINE="flujo1-test-$(date +%s)"

echo "═══ Test Flujo 1: run_salvar (commit + push a develop) ═══"

# 1. Setup: cambio en /desarrollo
echo "→ Creando cambio dummy en $REPO/README.md"
echo "$TEST_LINE" >> "$REPO/README.md"

# 2. Pedir al agente que commitee
echo "→ Pidiendo al agente que commitee con run_salvar"
RESPONSE=$(curl -sX POST "$HOST/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d "{\"circuit\":\"desarrollo\",\"messages\":[{\"role\":\"user\",\"content\":\"commiteá la línea agregada a README.md usando run_salvar(confirm=true, summary=\\\"test: flujo1\\\")\"}]}")

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# 3. Verificar que el commit existe en develop
echo "→ Verificando git log -1 en $REPO"
cd "$REPO"
HEAD_MSG=$(git log -1 --pretty=format:'%s')
HEAD_HASH=$(git log -1 --pretty=format:'%H' | cut -c1-8)

if echo "$HEAD_MSG" | grep -qi "test\|flujo"; then
    echo "✓ Commit creado: $HEAD_HASH — $HEAD_MSG"
else
    echo "✗ No se encontró el commit esperado. Head actual: $HEAD_MSG"
    exit 1
fi

echo "✓ Flujo 1 OK"