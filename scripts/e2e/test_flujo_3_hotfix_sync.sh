#!/usr/bin/env bash
# Test E2E del flujo 3: hotfix main → develop sync (circuito produccion)
# Requisito: /compose en main con commits ahead de origin/main; /desarrollo limpio en develop.
set -euo pipefail

HOST="${CONTI_HOST:-http://localhost:9001}"
COMPOSE="${COMPOSE_REPO:-/compose}"
DESARROLLO="${DESARROLLO_REPO:-/desarrollo}"
TEST_LINE="hotfix-test-$(date +%s)"

echo "═══ Test Flujo 3: run_hotfix_sync (main → develop) ═══"

# 1. Setup: hotfix dummy en /compose (Luis edita in-place)
echo "→ Agregando línea hotfix en $COMPOSE/README.md"
echo "$TEST_LINE" >> "$COMPOSE/README.md"

cd "$COMPOSE"
git add -A
git commit -m "hotfix: test sync flow" --allow-empty
echo "→ Commit local creado en /compose (main)"

# 2. Verificar que /desarrollo NO tiene el cambio
cd "$DESARROLLO"
echo "→ /desarrollo antes del sync:"
git log --oneline -3

if git log --all --oneline | grep -q "hotfix: test sync flow"; then
    # Puede pasar si /desarrollo ya tenía el commit de un sync anterior
    echo "⚠ /desarrollo ya tiene un commit hotfix previo. Limpiá o usá TEST_LINE distinto."
fi

# 3. Ejecutar run_hotfix_sync via agente (preview primero)
echo "→ Pidiendo preview de run_hotfix_sync"
PREVIEW=$(curl -sX POST "$HOST/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d '{"circuit":"produccion","messages":[{"role":"user","content":"sincronizá los cambios de /compose a /desarrollo usando run_hotfix_sync, dame preview primero"}]}')

echo "$PREVIEW" | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
print(f\"Preview (primeros 400 chars): {content[:400]}\")
" 2>/dev/null || echo "$PREVIEW" | head -c 400

# 4. Confirmar
echo "→ Confirmando con run_hotfix_sync(confirm=true)"
EXEC=$(curl -sX POST "$HOST/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d '{"circuit":"produccion","messages":[{"role":"user","content":"confirmá run_hotfix_sync con confirm=true"}]}')

echo "$EXEC" | python3 -m json.tool 2>/dev/null | head -40 || echo "$EXEC" | head -c 500

# 5. Verificar
cd "$DESARROLLO"
echo "→ /desarrollo después del sync:"
git log --oneline -5

if git log --all --oneline | grep -q "$TEST_LINE"; then
    echo "✓ /desarrollo contiene la línea del hotfix"
else
    # El sync es del COMMIT, no necesariamente de la línea exacta en git log.
    # Verificar que el archivo tiene la línea.
    if grep -q "$TEST_LINE" README.md 2>/dev/null; then
        echo "✓ README.md en /desarrollo contiene la línea del hotfix"
    else
        echo "⚠ /desarrollo no refleja el hotfix. Revisá:"
        git status
        exit 1
    fi
fi

echo "✓ Flujo 3 OK"