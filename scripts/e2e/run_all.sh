#!/usr/bin/env bash
# Runner que ejecuta los 4 tests E2E de los flujos git + test de GUIs.
# Requiere: backend corriendo en $CONTI_HOST (default http://localhost:9001),
#           bind-mounts configurados en docker-compose.conti.yml.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "════════════════════════════════════════════════════════"
echo "  E2E suite: conti-backend (PLAN_3 §11)"
echo "════════════════════════════════════════════════════════"

PASS=0
FAIL=0

run_test() {
    local script=$1
    echo ""
    if bash "$SCRIPT_DIR/$script"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "  ✗ $script falló"
    fi
}

run_test "test_flujo_1_desarrollo.sh"
run_test "test_flujo_2_promover.sh"
run_test "test_flujo_3_hotfix_sync.sh"
run_test "test_flujo_4_backend.sh"
run_test "test_3_guis.sh"

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Resultados: $PASS OK, $FAIL FAIL"
echo "════════════════════════════════════════════════════════"

[ "$FAIL" -eq 0 ]