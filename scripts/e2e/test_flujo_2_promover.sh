#!/usr/bin/env bash
# Test E2E del flujo 2: merge develop→main + push (circuito produccion)
# Requisito: /desarrollo en develop con commits ahead de main.
set -euo pipefail

HOST="${CONTI_HOST:-http://localhost:9001}"
REPO="${DESARROLLO_REPO:-/desarrollo}"

echo "═══ Test Flujo 2: run_promover (merge develop → main + push) ═══"

cd "$REPO"

# 1. Verificar que develop está ahead de main
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
echo "→ Commits en develop ahead de origin/main: $AHEAD"

if [ "$AHEAD" -eq 0 ]; then
    echo "✗ No hay commits para promover. Corré primero test_flujo_1_desarrollo.sh"
    exit 1
fi

# 2. Pedir preview al agente
echo "→ Pidiendo preview de run_promover"
PREVIEW=$(curl -sX POST "$HOST/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d '{"circuit":"produccion","messages":[{"role":"user","content":"preview de run_promover"}]}')

echo "$PREVIEW" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Preview generado. requires_confirmation={data.get('choices', [{}])[0].get('message', {}).get('content', '')[:200]}\")
" 2>/dev/null || echo "$PREVIEW" | head -c 300

# 3. Confirmar
echo "→ Confirmando con run_promover(confirm=true)"
EXEC=$(curl -sX POST "$HOST/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d '{"circuit":"produccion","messages":[{"role":"user","content":"ejecutá run_promover con confirm=true y summary=test flujo 2"}]}')

echo "$EXEC" | python3 -m json.tool 2>/dev/null | head -30 || echo "$EXEC"

# 4. Verificar que origin/main tiene los nuevos commits
MAIN_HEAD=$(git rev-parse origin/main)
DEVELOP_HEAD=$(git rev-parse HEAD)
echo "→ origin/main HEAD: $(echo $MAIN_HEAD | cut -c1-8)"
echo "→ develop HEAD:    $(echo $DEVELOP_HEAD | cut -c1-8)"

if git merge-base --is-ancestor HEAD origin/main; then
    echo "✓ Los commits de develop están en origin/main"
else
    echo "✗ origin/main NO contiene los commits de develop"
    exit 1
fi

echo "✓ Flujo 2 OK"