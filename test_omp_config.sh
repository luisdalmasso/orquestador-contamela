#!/bin/bash
# test_omp_config.sh — Verificar configuración de OMP
# Ejecutar después de recrear contenedores

echo "=== Verificación de configuración OMP ==="
echo ""

# 1. Verificar que los contenedores estén corriendo
echo "1. Estado de contenedores:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(conti-backend|conti-omp)" || echo "   ❌ Contenedores no encontrados"
echo ""

# 2. Verificar variables de entorno en conti-backend
echo "2. Variables de entorno en conti-backend:"
docker exec conti-backend env | grep -E "^(OMP_|XIAOMI_TOKEN|CONTI_USE_OMP)" | sort
echo ""

# 3. Verificar variables de entorno en conti-omp
echo "3. Variables de entorno en conti-omp:"
docker exec conti-omp env | grep -E "^(OMP_|XIAOMI_TOKEN)" | sort
echo ""

# 4. Verificar que OMP esté escuchando en :7891
echo "4. Verificando conexión OMP (:7891):"
docker exec conti-backend python3 -c "
import socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('conti-omp', 7891))
    sock.close()
    if result == 0:
        print('   ✅ OMP reachable en :7891')
    else:
        print('   ❌ OMP no reachable en :7891')
except Exception as e:
    print(f'   ❌ Error: {e}')
"
echo ""

# 5. Verificar MCP tools
echo "5. Verificando MCP tools:"
curl -s http://localhost:9001/mcp/tools | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    tools = data.get('tools', [])
    print(f'   ✅ {len(tools)} tools disponibles')
except:
    print('   ❌ No se pudieron listar tools')
" 2>/dev/null || echo "   ❌ No se pudo conectar a :9001"
echo ""

# 6. Verificar OpenHands Agent Server
echo "6. Verificando OpenHands Agent Server (:3000):"
curl -s http://localhost:3000/alive 2>/dev/null && echo "   ✅ OpenHands Agent Server OK" || echo "   ❌ OpenHands Agent Server no disponible"
echo ""

# 7. Verificar Hermes gateways
echo "7. Verificando Hermes gateways:"
for port in 8766 8767 8768 8769 8770 18791; do
    curl -s http://localhost:$port/health >/dev/null 2>&1 && echo "   ✅ :$port OK" || echo "   ⚠️  :$port no responde"
done
echo ""

echo "=== Verificación completada ==="
