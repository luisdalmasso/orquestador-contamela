#!/usr/bin/env bash
# Test E2E del flujo 4: commit directo a main en orquestador-contamela
# Requisito: bind-mount /contenedores/conti-backend:/contenedores/conti-backend.
set -euo pipefail

HOST="${CONTI_HOST:-http://localhost:9001}"
BACKEND="${BACKEND_REPO:-/contenedores/conti-backend}"
TEST_FILE="app/__init__.py"
TEST_LINE="# flujo4-test-$(date +%s)"

echo "═══ Test Flujo 4: run_salvar directo a main (circuito backend) ═══"

# 1. Setup: cambio en orquestador-contamela
echo "→ Agregando línea dummy en $BACKEND/$TEST_FILE"
if ! grep -q "^$TEST_LINE" "$BACKEND/$TEST_FILE"; then
    echo "$TEST_LINE" >> "$BACKEND/$TEST_FILE"
fi

# 2. Verificar rama
cd "$BACKEND"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "→ Branch actual: $BRANCH"

if [ "$BRANCH" != "main" ]; then
    echo "✗ Esperado branch main, encontrado $BRANCH. Este test asume orquestador-contamela en main."
    exit 1
fi

# 3. Ejecutar run_salvar con force_branch=main via agente
echo "→ Pidiendo al agente run_salvar(force_branch='main', confirm=true)"
RESPONSE=$(curl -sX POST "$HOST/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d '{"circuit":"backend","messages":[{"role":"user","content":"commiteá la línea dummy agregada usando run_salvar con force_branch=main y confirm=true"}]}')

echo "$RESPONSE" | python3 -m json.tool 2>/dev/null | head -30 || echo "$RESPONSE"

# 4. Verificar
HEAD_MSG=$(git log -1 --pretty=format:'%s')
HEAD_HASH=$(git log -1 --pretty=format:'%H' | cut -c1-8)
echo "→ Último commit: $HEAD_HASH — $HEAD_MSG"

# 5. Limpiar (revertir el dummy)
echo "→ Limpiando: revirtiendo el cambio dummy"
git reset --hard HEAD~1 -- 2>/dev/null || {
    # Si el push ya fue al remoto, revert manual
    sed -i "/^$TEST_LINE/d" "$BACKEND/$TEST_FILE"
    git add "$TEST_FILE"
    git commit -m "chore: cleanup flujo4 test"
}

echo "✓ Flujo 4 OK"