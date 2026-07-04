#!/usr/bin/env bash
# Test E2E de las 3 GUIs del agente (agent-server, agent-canvas, openhands web).
set -euo pipefail

echo "═══ Test GUI: 3 interfaces del agente ═══"

check() {
    local name=$1 url=$2 expected=$3
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")
    if [ "$code" = "$expected" ]; then
        echo "✓ $name ($url) → HTTP $code"
    else
        echo "✗ $name ($url) → HTTP $code (esperado $expected)"
        return 1
    fi
}

check "agent-server REST API (host:3011)" "http://localhost:3011/" "200"
check "agent-canvas GUI Next.js (host:3012)" "http://localhost:3012/" "200"
check "openhands web CLI textual (host:3013)" "http://localhost:3013/" "200"

echo "✓ Las 3 GUIs responden HTTP 200"