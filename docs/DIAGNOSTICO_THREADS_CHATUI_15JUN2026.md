# DIAGNOSTICO COMPLETO: Problemas de Threads y Carga de Pedidos
**Fecha:** 15 de Junio de 2026  
**Hora:** 16:20 ART  
**Versión:** 1.0  
**Autor:** Conti (Asistente IA)  

---

## RESUMEN EJECUTIVO

### Problemas Identificados (Últimos 15 minutos)

| # | Problema | Gravedad | Estado | Impacto |
|---|----------|----------|--------|---------|
| 1 | **Hermes no puede cargar pedidos** | CRÍTICO | En investigación | Agente inutilizable para operaciones de POS |
| 2 | **ChatUI pierde historial al F5** | ALTO | Identificado | Experiencia de usuario rota |
| 3 | **Lógica de threads crea threads innecesarios** | MEDIO | Confirmado | Pérdida de contexto |

---

## PROBLEMA 1: Hermes Incapaz de Cargar Pedidos

### Síntomas (Logs de hermes_resto_gateway.log)
```
WARNING agent.tool_executor: Tool mcp_odoo_mcp_search_read returned error (0.05s): 
{"error": "Internal server error: Invalid field 'name' on 'restaurant.table'"}

WARNING tools.mcp_tool: MCP server 'contibackend' initial connection failed (attempt 1/3)
WARNING tools.mcp_tool: MCP server 'contibackend' failed initial connection after 3 attempts
WARNING tools.mcp_tool: Failed to connect to MCP server 'contibackend': 
All connection attempts failed; [Errno 111] Connect call failed ('::1', 9001, 0, 0); [Errno 111] Connect call failed ('127.0.0.1', 9001)
```

### Análisis de Causa Raíz

#### 1.1 Error de Conexión MCP
- **Error:** `Failed to connect to MCP server 'contibackend'`
- **Causa:** Hermes intenta conectarse a `contibackend` en `::1:9001` y `127.0.0.1:9001`
- **Problema:** El contenedor `conti-backend` está en una red Docker diferente
- **Solución:** Cambiar configuración para usar `http://conti-backend:9001`

#### 1.2 Error de Campo en Restaurant Table
- **Error:** `Invalid field 'name' on 'restaurant.table'`
- **Causa:** La herramienta `mcp_odoo_mcp_search_read` intenta acceder a un campo 'name' que no existe
- **Contexto:** Esto ocurre al buscar pedidos (pos.order)
- **Solución:** Verificar la definición de la herramienta en Odoo MCP

#### 1.3 Múltiples Intentos Fallidos
- **Patrón:** 3 intentos de conexión fallidos antes de rendirse
- **Impacto:** Hermes no puede acceder a herramientas MCP de Odoo
- **Resultado:** No puede ejecutar `pos.search_orders`, `pos.read_order`, etc.

---

## PROBLEMA 2: ChatUI Pierde Historial al Refrescar (F5)

### Síntomas (Logs de chatui)
```
[chatui POST] urlParams: {
  table_identifier: '3fd36a1a',
  has_active_order: 'false',
  id_mesa: '101'
}
[chatui thread-decision] Thread vacío - preservar para nuevo mensaje

[chatui POST] threadId: 'cf6ef293-2991-4cd8-8320-5ddfcc2869cc'
[chatui POST] thread-decision: No hay pedidos asociados a esta mesa - preservar thread
```

### Análisis de Causa Raíz

#### 2.1 has_active_order siempre es 'false'
- **Observación:** En los logs, `has_active_order: 'false'` aparece repetidamente
- **Problema:** El endpoint `/api/chat/[tenant]/order-status` no está detectando pedidos abiertos
- **Causa probable:** 
  - El endpoint consulta Odoo pero no encuentra pedidos con `table_identifier`
  - El `table_identifier` (`3fd36a1a`) no coincide con el formato esperado por Odoo

#### 2.2 Thread vacío al refrescar
- **Observación:** `Thread vacío - preservar para nuevo mensaje`
- **Causa:** Al refrescar, el frontend no envía el `threadId` correcto
- **Impacto:** Se crea un nuevo thread en lugar de usar el existente

#### 2.3 Frontend no preserva threadId
- **Problema:** El frontend de ChatUI no está guardando el threadId en el estado
- **Resultado:** Cada F5 genera un nuevo threadId

---

## PROBLEMA 3: Lógica de Threads Crea Threads Innecesarios

### Síntomas
```
[chatui thread-decision] No hay pedidos asociados a esta mesa - preservar thread
[chatui thread-decision] Thread vacío - preservar para nuevo mensaje
```

### Análisis de Causa Raíz

#### 3.1 La lógica NO debería crear nuevo thread si:
- Hay un pedido en curso (draft)
- El usuario está pidiendo más items

#### 3.2 La lógica SÍ debería crear nuevo thread SOLO si:
- NO hay pedidos sin cobrar (draft)
- Y hay un pedido COBRADO
- Y el chat es del pedido cobrado

#### 3.3 Problema actual:
La implementación actual **NO está usando correctamente el MCP de Odoo**
- Usa el endpoint `/api/chat/[tenant]/order-status` que devuelve datos incompletos
- No consultar directamente al MCP de Odoo: `http://odoo18:8072/mcp`

---

## DIAGNÓSTICO TÉCNICO DETALLADO

### Configuración Actual de Hermes RESTO

#### Perfil: resto (Puerto 8767)
```yaml
# De entrypoint_hermes.sh
HERMES_HOME="${HERMES_HOME_CONTIHOME}" hermes -p resto gateway run --accept-hooks
```

#### Configuración MCP (De mcp-local.md)
```yaml
odoo_mcp:
  command: python
  args:
    - -m
    - mcp_odoo.server
    - --odoo-url
    - http://odoo18:8069
    - --db-name
    - resto
  transport: http  # Cambiado de sse a http
  headers:
    Host: resto.contamela.com  # Requerido por dbfilter
```

### Problema de Conexión
Hermes intenta conectarse a:
1. `contibackend` en `::1:9001` → FAIL
2. `odoo_mcp` en `odoo18:8072` → ¿?

**El perfil resto NO está configurado para conectarse a odoo_mcp directamente**

---

## SOLUCIONES PROPUESTAS

### SOLUCIÓN 1: Corregir Conexión Hermes → Odoo MCP (CRÍTICO)

#### 1.1 Configurar perfil resto para usar odoo_mcp
**Archivo:** `/app/hermes_profiles/contihome/profiles/resto/config.yaml`

**Cambio requerido:**
```yaml
mcp_servers:
  odoo_mcp:
    url: http://odoo18:8072
    transport: http
    headers:
      Host: resto.contamela.com
```

**1.2 Verificar que el perfil resto tenga acceso a pos.search_orders**
```bash
docker exec conti-backend hermes -p resto mcp list-tools
```

**1.3 Probar conexión manualmente**
```bash
docker exec conti-backend curl -X POST http://odoo18:8072/mcp \
  -H "Content-Type: application/json" \
  -H "Host: resto.contamela.com" \
  -d '{"jsonrpc":"2.0","id":1,"method":"pos.search_orders","params":{}}'
```

### SOLUCIÓN 2: Corregir Lógica de Threads en ChatUI (ALTO)

#### 2.1 Cambiar a consulta DIRECTA a MCP de Odoo
**Archivo:** `/compose/chatui/src/app/api/chat/[tenant]/route.ts`

**Cambio en shouldCreateNewThread():**
```typescript
// REEMPLAZAR el endpoint de ChatUI por consulta directa a MCP
const mcpResponse = await fetch('http://odoo18:8072/mcp', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Host': 'resto.contamela.com'
  },
  body: JSON.stringify({
    jsonrpc: '2.0',
    id: 1,
    method: 'pos.search_orders',
    params: {
      table_identifier: tableIdentifier
    }
  })
})
```

**2.2 Validar que el campo para buscar por mesa sea correcto**
- Odoo usa `self_ordering_table_id` o `table_id`
- El `table_identifier` debe coincidir con el ID interno de Odoo

### SOLUCIÓN 3: Corregir Frontend ChatUI (MEDIO)

#### 3.1 Preservar threadId en el estado del frontend
**Archivo:** Frontend de ChatUI (probablemente React/Next.js)

**Problema:** Al refrescar, se pierde el `threadId`
**Solución:** Guardar en:
- localStorage: `chatui_thread_${tableIdentifier}`
- URL: `?threadId=xxx`
- Context API

#### 3.2 Verificar que table_identifier coincida con Odoo
**Problema:** `table_identifier: '3fd36a1a'` no coincide con ID de Odoo
**Solución:** Usar `id_mesa` directamente en la consulta a Odoo

---

## DIAGNÓSTICO DE LLAMADAS A TOOLS DE HERMES

### Tools que fallaron:
1. **mcp_odoo_mcp_search_read**
   - Error: Invalid field 'name' on 'restaurant.table'
   - Intentó buscar pedidos de restaurant.table
   - **Solución:** Verificar parámetros de la herramienta

2. **contibackend** (MCP local)
   - Error: Connection refused
   - No pudo conectarse en 3 intentos
   - **Solución:** Configurar URL correcta

### Tools que NO se ejecutaron:
- **pos.search_orders** (NO intenta ejecutarse)
- **pos.read_order** (NO intenta ejecutarse)

**Causa:** Hermes no puede conectarse a ningún servidor MCP

---

## CUÁNDO DEBE CREARSE NUEVO THREAD

### Regla CORRECTA (Basada en flujo real de restaurante):

```
FLUJO NORMAL DE UNA MESA:

1. [CLIENTE LLEGA] → Mesa vacía
   → CREAR NUEVO THREAD (no hay pedido)
   
2. [CLIENTE PIDE] → "Dame una coca"
   → Odoo: Crea pedido DRAFT (ID: 46)
   → PRESERVAR THREAD (hay pedido draft)
   
3. [CLIENTE PIDE MÁS] → "Agrega una pizza"
   → Odoo: Pedido 46 sigue siendo DRAFT
   → PRESERVAR THREAD (sigue siendo draft)
   
4. [PEDIDO A COCINA] → Estado: "En cocina"
   → Odoo: Pedido 46 sigue siendo DRAFT
   → PRESERVAR THREAD (sigue siendo draft)
   
5. [PEDIDO LISTO] → Estado: "Listo para servir"
   → Odoo: Pedido 46 sigue siendo DRAFT
   → PRESERVAR THREAD (sigue siendo draft)
   
6. [CLIENTE PAGA] → QR Mercado Pago
   → Odoo: Pedido 46 pasa a PAID/DONE
   → CREAR NUEVO THREAD (no hay draft + último chat era del pedido cobrado)
   
7. [NUEVO CLIENTE] → Mesa disponible
   → CREAR NUEVO THREAD (no hay pedidos)
```

### Regla IMPLEMENTADA vs Regla IDEAL:

| Escenario | Implementada | Ideal | Problema |
|-----------|-------------|-------|----------|
| Pedido DRAFT | ✅ PRESERVAR | ✅ PRESERVAR | OK |
| Pedido PAID + Chat de ese pedido | ✅ CREAR NUEVO | ✅ CREAR NUEVO | OK |
| Pedido PAID + Chat de otro tema | ✅ PRESERVAR | ✅ PRESERVAR | OK |
| **Al refrescar (F5)** | ❌ PIERDE HISTORIAL | ✅ PRESERVAR | **Frontend no guarda threadId** |
| **Pedro DRAFT existe pero no se detecta** | ❌ CREA NUEVO | ✅ PRESERVAR | **Endpoint order-status falla** |

---

## SOLUCIONES INMEDIATAS (Orden de Prioridad)

### PRIORIDAD 1: 🚨 Corregir Conexión Hermes → Odoo MCP
**Impacto:** Sin esto, Hermes no puede cargar pedidos
**Tiempo estimado:** 15 minutos

```bash
# 1. Verificar configuración actual
docker exec conti-backend cat /app/hermes_profiles/contihome/profiles/resto/config.yaml

# 2. Corregir URL de contibackend (si existe)
# Buscar: contibackend
# Cambiar por: http://conti-backend:9001

# 3. Asegurar que odoo_mcp esté accesible
docker exec conti-backend curl -v http://odoo18:8072/mcp

# 4. Reiniciar perfil resto
docker exec conti-backend pkill -f "hermes -p resto"
sleep 5
docker exec conti-backend HERMES_HOME=/app/hermes_profiles/contihome hermes -p resto gateway run --accept-hooks > /app/logs/hermes_resto_gateway.log 2>&1 &
```

### PRIORIDAD 2: 📱 Corregir Consulta de Pedidos en ChatUI
**Impacto:** Sin esto, la lógica de threads no funciona correctamente
**Tiempo estimado:** 10 minutos

**Cambio en route.ts:**
```typescript
// REEMPLAZAR
const orderStatusResponse = await fetch(
  `http://localhost:8877/api/chat/${tenant}/order-status?table_identifier=${encodeURIComponent(tableIdentifier)}`
)

// POR
const mcpResponse = await fetch('http://odoo18:8072/mcp', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Host': 'resto.contamela.com'
  },
  body: JSON.stringify({
    jsonrpc: '2.0',
    id: 1,
    method: 'pos.search_orders',
    params: {
      state: 'draft',
      table_id: parseInt(idMesa) || null,
      self_ordering_table_id: parseInt(idMesa) || null
    }
  })
})
```

### PRIORIDAD 3: 💾 Corregir Frontend para Preservar threadId
**Impacto:** Sin esto, los usuarios pierden el historial al refrescar
**Tiempo estimado:** 20 minutos

**Solución:**
1. Guardar threadId en localStorage:
   ```javascript
   localStorage.setItem(`chatui_thread_${tableIdentifier}`, threadId)
   ```
2. Recuperar al cargar:
   ```javascript
   const savedThreadId = localStorage.getItem(`chatui_thread_${tableIdentifier}`)
   ```
3. Pasar en todas las peticiones

---

## VERIFICACIÓN DE SOLUCIONES

### Prueba 1: Hermes puede cargar pedidos
```bash
# Probar conexión MCP
docker exec conti-backend curl -X POST http://odoo18:8072/mcp \
  -H "Content-Type: application/json" \
  -H "Host: resto.contamela.com" \
  -d '{"jsonrpc":"2.0","id":1,"method":"pos.search_orders","params":{"state":"draft"}}'

# Debería devolver: lista de pedidos draft
```

### Prueba 2: ChatUI detecta pedidos correctamente
1. Abrir ChatUI en mesa 101
2. Crear pedido (debería pasar a DRAFT en Odoo)
3. Enviar mensaje "dame una coca"
4. Verificar logs: `[chatui thread-decision] Hay orden SIN COBRAR - preservar thread`

### Prueba 3: Frontend preserva threadId
1. Abrir ChatUI en mesa 101
2. Enviar mensaje
3. Refrescar (F5)
4. Verificar que el historial aparece
5. Verificar que el threadId es el mismo

---

## RESUMEN DE ACCIONES REQUERIDAS

| # | Acción | Responsable | Tiempo | Prioridad |
|---|--------|-------------|-------|-----------|
| 1 | Configurar perfil resto para usar odoo_mcp | SysAdmin | 15 min | CRÍTICO |
| 2 | Corregir consulta a MCP en ChatUI | Desarrollador | 10 min | ALTO |
| 3 | Preservar threadId en frontend ChatUI | Desarrollador Frontend | 20 min | ALTO |
| 4 | Validar conexión Hermes → MCP | SysAdmin | 5 min | ALTO |
| 5 | Pruebas end-to-end | QA | 15 min | MEDIO |

---

## CONCLUSIÓN

**Problema principal:** Hermes no puede conectarse al MCP de Odoo, por lo que no puede ejecutar herramientas de POS. Esto causa que:
1. No pueda cargar pedidos
2. No pueda verificar estados
3. La lógica de threads en ChatUI no funciona correctamente por falta de datos

**Solución principal:** Configurar correctamente la conexión Hermes → MCP de Odoo y cambiar ChatUI para consultar directamente al MCP en lugar del endpoint local.

**Impacto esperado:**
- ✅ Hermes podrá cargar pedidos nuevamente
- ✅ ChatUI tomará decisiones correctas sobre threads
- ✅ No se perderá el historial al refrescar (con solución frontend)

---

**Documento generado por Conti - Asistente IA**  
**Fecha:** 15 de Junio de 2026, 16:20 ART  
**Versión:** 1.0
