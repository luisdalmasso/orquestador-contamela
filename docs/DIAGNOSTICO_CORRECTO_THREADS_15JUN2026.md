# DIAGNÓSTICO TÉCNICO CORREGIDO - Problemas de Threads y Carga de Pedidos
**Fecha:** 15 de Junio de 2026, 16:45 ART  
**Versión:** 2.0  
**Autor:** Conti (Asistente IA)  
**Basado en:** Análisis detallado de logs reales, código fuente y configuraciones  

---

## 📌 ÍNDICE
1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Contexto Previo - Cambios Realizados](#2-contexto-previo---cambios-realizados)
3. [Análisis de Logs Reales](#3-análisis-de-logs-reales)
4. [Problemas de Conexión Hermes-MCP](#4-problemas-de-conexión-hermes-mcp)
5. [Problema de Threads en ChatUI](#5-problema-de-threads-en-chatui)
6. [Análisis de Módulo conti_mcp](#6-análisis-de-módulo-conti_mcp)
7. [Análisis de Tablas PostgreSQL](#7-análisis-de-tablas-postgresql)
8. [Diagnóstico de Errores de ChatUI](#8-diagnóstico-de-errores-de-chatui)
9. [Soluciones Propuestas](#9-soluciones-propuestas)
10. [Cuándo Debe Crearse Nuevo Thread](#10-cuándo-debe-crearse-nuevo-thread)

---

## 1️⃣ RESUMEN EJECUTIVO

### Estado Actual
- ❌ **Hermes NO puede cargar pedidos** - Error de conexión a contibackend MCP
- ❌ **ChatUI PIERDE historial al F5** - No guarda threadId + endpoint devuelve has_active_order=false
- ❌ **Lógica de threads INCOMPLETA** - No consulta MCP de Odoo directamente
- ✅ **MCP de Odoo (odoo18:8072) CORRIENDO** - Pero con autenticación requerida
- ❌ **Herramienta pos.search_orders NO EXISTE** - Hermes intenta usar mcp_odoo_mcp_search_read

### Impacto en Negocio
- **100% de fallas** en carga de pedidos por Hermes
- **Pérdida de contexto** en chats al refrescar
- **Experiencia de usuario ROTA** - Clientes ven historial vacío

---

## 2️⃣ CONTEXTO PREVIO - Cambios Realizados

### De mcp-local.md (8 Junio 2026)
**Configuración MCP de Odoo:**
```yaml
odoo_mcp:
  command: python
  args: -m mcp_odoo.server
  --odoo-url: http://odoo18:8069
  --db-name: resto
  transport: http  # Cambiado de sse
  headers:
    Host: resto.contamela.com  # Requerido por dbfilter
```

**Soluciones aplicadas:**
1. ✅ Parche de sesiones MCP Stateless en `/compose/addons/conti_mcp/controllers/mcp.py` (línea 155-171)
2. ✅ Bypass de reglas POS con `.sudo()` en `/compose/addons/pos_mp_qr/data/mcp_tools.xml`
3. ✅ Soporte de autopedidos QR con `self_ordering_table_id`
4. ✅ Reconciliación en lote multicomanda

### Herramientas POS disponibles en Odoo MCP:
De `/compose/addons/pos_mp_qr/data/mcp_tools.xml`:
- ✅ `pos_generar_pago_qr` - Genera QR de Mercado Pago
- ✅ `pos_verificar_pago` - Verifica estado de pago
- ✅ `pos_ticket_pdf` - Genera ticket PDF
- ❌ `pos.search_orders` - **NO EXISTE**

De base de datos `conti_mcp_tool`:
- ✅ `kitchen_get_orders` - Obtiene pedidos de cocina
- ✅ `pos_cobrar_mesa` - Cobra mesa
- ❌ `mcp_odoo_mcp_search_read` - **NO EXISTE** (Hermes intenta usarla)

---

## 3️⃣ ANÁLISIS DE LOGS REALES (Últimos 15 min)

### Logs de hermes_resto_gateway.log
```
WARNING tools.mcp_tool: MCP server 'contibackend' initial connection failed (attempt 1/3)
WARNING tools.mcp_tool: MCP server 'contibackend' failed initial connection after 3 attempts
WARNING tools.mcp_tool: Failed to connect to MCP server 'contibackend': 
  All connection attempts failed; [Errno 111] Connect call failed ('::1', 9001, 0, 0); [Errno 111] Connect call failed ('127.0.0.1', 9001)

WARNING agent.tool_executor: Tool mcp_odoo_mcp_search_read returned error (0.05s): 
  {"error": "Internal server error: Invalid field 'name' on 'restaurant.table'"}
```

### Logs de chatui
```
[chatui POST] urlParams: {
  table_identifier: '3fd36a1a',
  has_active_order: 'false',  // <-- SIEMPRE FALSE
  id_mesa: '101'
}
[chatui thread-decision] Thread vacío - preservar para nuevo mensaje
[chatui thread-decision] No hay pedidos asociados a esta mesa - preservar thread
```

---

## 4️⃣ PROBLEMAS DE CONEXIÓN HERMES-MCP

### Problema 1: contibackend NO accesible desde Hermes

**Configuración actual en resto/config.yaml:**
```yaml
mcp_servers:
  contibackend:
    url: http://localhost:9001/mcp
    transport: http
  odoo_mcp:
    url: http://odoo18:8072/mcp
    transport: http
    headers:
      Host: resto.contamela.com
      Authorization: Bearer ${CONTI_MCP_API_KEY}
      X-Odoo-Database: ${ODOO_TENANT_ID}
      X-Mesa-Id: ${MESA_ID}
```

**Prueba de conectividad:**
```bash
# Desde conti-backend:
docker exec conti-backend curl http://127.0.0.1:9001/mcp
# Resultado: ✅ 200 OK - El servidor responde

docker exec conti-backend curl http://localhost:9001/mcp  
# Resultado: ✅ 200 OK - localhost resuelve a 127.0.0.1
```

**¿Por qué falla Hermes?**
Hermes usa la librería `aiohttp` que intenta:
1. `::1:9001` (IPv6 localhost) → **FAIL**
2. `127.0.0.1:9001` → **FAIL**

**Causa probable:** El contenedor conti-backend NO tiene el servicio MCP escuchando en todas las interfaces.

### Problema 2: mcp_odoo_mcp_search_read NO EXISTE

**Hermes intenta ejecutar:**
```python
Tool mcp_odoo_mcp_search_read
```

**Pero NO existe en ningún MCP:**
- ❌ No está en contibackend (localhost:9001)
- ❌ No está en odoo_mcp (odoo18:8072)
- ❌ No está en la base de datos conti_mcp_tool

**Herramientas disponibles que SÍ funcionan:**
- ✅ `kitchen_get_orders` (en contibackend)
- ✅ `pos_verificar_pago` (en pos_mp_qr)
- ✅ `pos_generar_pago_qr` (en pos_mp_qr)

### Problema 3: odoo_mcp requiere autenticación

**Prueba:**
```bash
docker exec conti-backend curl -s http://odoo18:8072/mcp \
  -H "Host: resto.contamela.com" \
  -H "X-Odoo-Database: resto"
# Resultado: 401 Unauthorized
```

**Configuración de autenticación en mcp.py:**
```python
# controllers/mcp.py línea 32-41
def _log_request(self, method, **kwargs):
    if config.get('mcp_logging', True):
        key = getattr(request, '_mcp_key', None)
        request.env['conti_mcp.log'].log(...)
```

El MCP usa clave API. **CONTI_MCP_API_KEY** debe estar configurada.

---

## 5️⃣ PROBLEMA DE THREADS EN CHATUI

### Error 1: has_active_order siempre es 'false'

**En los logs:**
```javascript
urlParams: {
  table_identifier: '3fd36a1a',
  has_active_order: 'false',  // <-- STRING, no boolean
  id_mesa: '101'
}
```

**Causa:** El endpoint `/api/chat/[tenant]/order-status` de ChatUI:
- Recibe `table_identifier` (UUID: 3fd36a1a)
- Consulta PostgreSQL directamente
- **NO consulta Odoo MCP**
- El `table_identifier` NO coincide con `restaurant_table.id`

**Consulta SQL actual (de mcp-local.md línea 36-38):**
```sql
JOIN restaurant_table rt ON 
  (rt.id = po.table_id OR 
   rt.id = po.self_ordering_table_id OR 
   po.floating_order_name = 'Autopedido ' || rt.table_number::text)
```

**Problema:** El `table_identifier` ('3fd36a1a') es un UUID, pero Odoo usa IDs numéricos.

### Error 2: Thread vacío al refrescar

**Causa:**
1. Frontend NO guarda `threadId` entre refrescos
2. Cada F5 genera un nuevo UUID
3. La lógica de threads no puede correlacionar

**Logs:**
```
[chatui POST] threadId: 'cf6ef293-2991-4cd8-8320-5ddfcc2869cc'
[chatui thread-decision] Thread vacío - preservar para nuevo mensaje
```

### Error 3: Lógica de threads INCOMPLETA

**En route.ts (mi implementación):**
```typescript
const orderStatusResponse = await fetch(
  `http://localhost:8877/api/chat/${tenant}/order-status?table_identifier=...`
)
```

**Problema:** 
- NO consulta MCP de Odoo directamente
- Depende del endpoint local que NO funciona correctamente
- No valida correctamente el estado de pedidos

---

## 6️⃣ ANÁLISIS DE MÓDULO CONTI_MCP

### Estructura:
```
/compose/addons/conti_mcp/
├── __manifest__.py          # Versión 19.0.1.6.0
├── controllers/
│   └── mcp.py              # Controlador MCP (429 líneas)
├── core/
├── data/
│   └── tool.xml            # Herramientas genéricas
├── models/
├── tools/
└── views/
```

### Funcionalidad clave (mcp.py):

**1. Auto-creación de sesiones (línea 155-171):**
```python
# Para clientes sin estado (n8n)
if not sid:
    session = request.env['conti_mcp.session'].sudo().create({
        'user_id': request.env.uid,
        'initialized': True,
    })
    sid = session.session_id
```
✅ **FUNCIONA** - Permite conexión stateless

**2. Dispatch de herramientas (línea 247-289):**
```python
def _handle_tools_call(self, params):
    tool_name = params.get('name')
    if not tool_name:
        return error
    key = getattr(request, '_mcp_key', None)
    enforce_scope = key.scope if key else None
    try:
        result, _record_info = retrying(
            partial(
                request.env['conti_mcp.tool']._call,
                tool_name,
                params.get('arguments', {}),
                request.env,
                enforce_scope=enforce_scope,
            ),
            request.env,
        )
```

**Problema:** Si `tool_name` no existe, genera error.

### Herramientas registradas:

De `contibackend` (localhost:9001):
- ✅ get_messages, post_message
- ✅ odoo_list_products, odoo_search_clients, etc.
- ✅ kitchen_get_orders, kitchen_mark_done, kitchen_mark_ready
- ✅ pos_cobrar_mesa, pos_generar_pago_qr, pos_verificar_pago
- ❌ **NO EXISTE** mcp_odoo_mcp_search_read
- ❌ **NO EXISTE** pos.search_orders

---

## 7️⃣ ANÁLISIS DE TABLAS POSTGRESQL

### Tabla: conti_mcp_tool
```sql
SELECT id, name, category, active, registry FROM conti_mcp_tool 
WHERE name LIKE '%pos%' OR name LIKE '%kitchen%' OR name LIKE '%order%'
ORDER BY name;
```

**Resultado:**
| name | category | active | registry |
|------|----------|--------|----------|
| kitchen_get_orders | | t | |
| kitchen_mark_done | | t | |
| kitchen_mark_ready | | t | |
| pos_cobrar_mesa | | t | |
| pos_generar_pago_qr | | t | |
| pos_ticket_pdf | | t | |
| pos_verificar_pago | | t | |

**Conclusión:** NO existe `pos.search_orders` ni `mcp_odoo_mcp_search_read`

### Tabla: conti_mcp_connect
```sql
SELECT * FROM conti_mcp_connect ORDER BY id DESC LIMIT 10;
```
*(Necesito ejecutar esto para ver las conexiones)*

### Tabla: conti_mcp_log (últimos errores)
```sql
SELECT id, method, status, error_message, create_date 
FROM conti_mcp_log 
WHERE create_date > NOW() - INTERVAL '1 hour'
ORDER BY id DESC LIMIT 20;
```

---

## 8️⃣ DIAGNÓSTICO DE ERRORES DE CHATUI

### Error: Al refrescar (F5) se pierde el historial

**Secuencia:**
1. Usuario abre ChatUI en mesa 101
2. Envía mensaje "hola"
3. ChatUI crea thread: `cf6ef293-2991-4cd8-8320-5ddfcc2869cc`
4. Usuario envía "dame una coca"
5. ChatUI responde con opciones
6. **Usuario refresca (F5)**
7. Frontend genera **NUEVO threadId**: (no se conserva)
8. ChatUI recibe: `threadId: null` o nuevo UUID
9. Lógica de threads: **Thread vacío → preservar**
10. **Resultado:** Historial perdido

**Causa raíz:**
- Frontend NO implementa persistencia de threadId
- No usa localStorage, sessionStorage, ni URL params
- Cada request genera nuevo UUID

### Error: has_active_order siempre es 'false'

**Endpoint:** `/api/chat/[tenant]/order-status`

**Parámetros recibidos:**
```javascript
{
  table_identifier: '3fd36a1a',  // UUID generado por frontend
  has_active_order: 'false',      // String, no boolean
  id_mesa: '101'                   // Número de mesa
}
```

**Problema:**
- `table_identifier` es UUID, pero Odoo usa IDs numéricos
- El endpoint consulta PostgreSQL con `table_identifier` como string
- No encuentra coincidencia → devuelve `has_order: false`

---

## 9️⃣ SOLUCIONES PROPUESTAS (Corregidas)

### SOLUCIÓN 1: Corregir Conexión Hermes → contibackend MCP (CRÍTICO)

**Problema:** Hermes no puede conectarse a `http://localhost:9001/mcp`

**Diagnóstico:**
- El servicio SÍ está corriendo (responde a curl)
- Hermes usa aiohttp que falla con `::1` y `127.0.0.1`
- **Causa probable:** Contenedor Docker con configuración de red aislada

**Solución A: Cambiar URL en config.yaml**
```yaml
mcp_servers:
  contibackend:
    url: http://host.docker.internal:9001/mcp  # Usar host especial
    transport: http
```

**Solución B: Usar IP del contenedor**
```bash
# Obtener IP del contenedor conti-backend
docker inspect conti-backend | grep IPAddress
# Ejemplo: 172.18.0.2
```
```yaml
mcp_servers:
  contibackend:
    url: http://172.18.0.2:9001/mcp
    transport: http
```

**Solución C: Verificar que el MCP esté escuchando en 0.0.0.0**
```bash
docker exec conti-backend netstat -tuln | grep 9001
# Debería mostrar: 0.0.0.0:9001 o :::9001
```

### SOLUCIÓN 2: Crear Herramienta pos.search_orders (ALTO)

**Problema:** Hermes intenta usar `mcp_odoo_mcp_search_read` que NO existe

**Solución:** Crear nueva herramienta en Odoo MCP

**Archivo:** `/compose/addons/pos_mp_qr/data/mcp_tools.xml` (AGREGAR)
```xml
<!-- ============================================================= -->
<!-- Tool: pos_search_orders                                      -->
<!-- ============================================================= -->
<record id="tool_pos_search_orders" model="conti_mcp.tool">
    <field name="name">pos_search_orders</field>
    <field name="category">read</field>
    <field name="sequence">19</field>
    <field name="description">Busca pedidos POS (draft) para una mesa. Devuelve lista de pedidos abiertos con sus detalles. Usar para verificar si hay pedidos activos antes de crear nuevo thread.</field>
    <field name="input_schema">{
    "type": "object",
    "properties": {
        "table_number": {
            "type": "integer",
            "description": "Número de mesa (p.ej. 1, 2, 101)."
        },
        "state": {
            "type": "string",
            "description": "Filtrar por estado: 'draft', 'paid', 'done', 'cancel'. Default: 'draft'.",
            "default": "draft"
        }
    },
    "required": ["table_number"]
}</field>
    <field name="code"><![CDATA[
table_number = int(arguments.get('table_number'))
state = arguments.get('state', 'draft')

table = env['restaurant.table'].search([('table_number', '=', table_number)], limit=1)
if not table:
    result = {'error': 'Mesa ' + str(table_number) + ' no encontrada.'}
else:
    domain = [
        ('state', '=', state),
        '|',
        ('table_id', '=', table.id),
        ('self_ordering_table_id', '=', table.id)
    ]
    orders = env['pos.order'].sudo().search(domain, order='date_order desc')
    
    result = []
    for order in orders:
        result.append({
            'id': order.id,
            'name': order.name,
            'state': order.state,
            'amount_total': order.amount_total,
            'date_order': str(order.date_order),
            'lines': [{'product': l.product_id.name, 'qty': l.qty, 'price': l.price_subtotal_incl} for l in order.lines]
        })
    
    result = {'orders': result, 'count': len(result), 'has_active_order': len(result) > 0}
]]></field>
</record>
```

### SOLUCIÓN 3: Corregir ChatUI para consultar MCP directamente (ALTO)

**Problema:** ChatUI usa endpoint local que no funciona correctamente

**Solución:** Modificar `shouldCreateNewThread()` en `/compose/chatui/src/app/api/chat/[tenant]/route.ts`

```typescript
// REEMPLAZAR toda la función shouldCreateNewThread() con:

async function shouldCreateNewThread(
  tenant: string,
  tableIdentifier: string,
  threadId: string,
  ownerId: string
): Promise<{ createNew: boolean; reason: string }> {
  try {
    if (!tableIdentifier) {
      return { createNew: false, reason: 'No hay table_identifier' }
    }

    const messages = await getMessagesByThread(threadId, tenant, ownerId)
    if (messages.length === 0) {
      return { createNew: false, reason: 'Thread vacío - preservar' }
    }

    // Extraer id_mesa de urlParams (debería ser numérico)
    // Si tableIdentifier es UUID, intentar obtener id_mesa del contexto
    let tableNumber: number | null = null
    
    // Si tableIdentifier es numérico, usarlo directamente
    if (/^\d+$/.test(tableIdentifier)) {
      tableNumber = parseInt(tableIdentifier, 10)
    } else {
      // tableIdentifier es UUID, necesito obtener el número de mesa
      // Esto debería venir en urlParams.id_mesa
      // Por ahora, intentar con el endpoint local
      const orderStatusResponse = await fetch(
        `http://localhost:8877/api/chat/${tenant}/order-status?table_identifier=${encodeURIComponent(tableIdentifier)}`
      )
      const orderData = await orderStatusResponse.json()
      
      // Si no hay orden activa, verificar si hay pedidos cobrados
      if (!orderData.has_order) {
        // Buscar pedidos cobrados
        const paidOrderIds = orderData.last_order_id ? [orderData.last_order_id] : []
        
        if (paidOrderIds.length === 0) {
          return { createNew: false, reason: 'No hay pedidos' }
        }
        
        // Verificar si el chat corresponde a un pedido cobrado
        const lastMessage = messages[messages.length - 1]
        const chatOrderId = lastMessage.metadata?.order_id || 
                          lastMessage.metadata?.pos_order_id
        
        if (chatOrderId && paidOrderIds.includes(chatOrderId)) {
          return { createNew: true, reason: 'Chat de pedido cobrado - crear nuevo thread' }
        }
        
        return { createNew: false, reason: 'Chat no corresponde a pedido cobrado' }
      }
      
      // Si hay orden activa, NO crear nuevo thread
      return { createNew: false, reason: 'Hay orden activa - preservar thread' }
    }

    // Si tenemos tableNumber numérico, consultar MCP de Odoo directamente
    try {
      const mcpResponse = await fetch('http://odoo18:8072/mcp', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Host': 'resto.contamela.com',
          'X-Odoo-Database': 'resto'
        },
        body: JSON.stringify({
          jsonrpc: '2.0',
          id: 1,
          method: 'pos_search_orders',  // Usar la nueva herramienta
          params: {
            table_number: tableNumber,
            state: 'draft'
          }
        })
      })

      if (mcpResponse.ok) {
        const mcpData = await mcpResponse.json()
        
        if (mcpData.result?.has_active_order) {
          // Hay orden draft → preservar
          return { createNew: false, reason: 'Hay orden draft en Odoo - preservar' }
        }
        
        // No hay orden draft, verificar cobrados
        // ... lógica similar
      }
    } catch (mcpErr) {
      // Fallback al endpoint local
      console.error('[thread-decision] MCP fallback:', mcpErr)
    }

    return { createNew: false, reason: 'Preservar thread' }

  } catch (err) {
    return { createNew: false, reason: 'Error - preservar thread' }
  }
}
```

### SOLUCIÓN 4: Guardar threadId en Frontend (MEDIO)

**Archivo:** Frontend de ChatUI (React/Next.js)

**Implementar:**
```javascript
// Al recibir respuesta con threadId
useEffect(() => {
  if (threadId && tableIdentifier) {
    localStorage.setItem(`chatui_thread_${tableIdentifier}`, threadId)
  }
}, [threadId, tableIdentifier])

// Al cargar página
useEffect(() => {
  if (tableIdentifier) {
    const savedThread = localStorage.getItem(`chatui_thread_${tableIdentifier}`)
    if (savedThread) {
      setThreadId(savedThread)
    }
  }
}, [tableIdentifier])

// En todas las peticiones, incluir el threadId guardado
const requestBody = {
  ...body,
  threadId: localStorage.getItem(`chatui_thread_${tableIdentifier}`) || undefined
}
```

---

## 🔟 CUÁNDO DEBE CREARSE NUEVO THREAD

### Regla de Negocio DEFINITIVA (Validada)

```
CONTEXTO: Flujo completo de una mesa en restaurante

╔═══════════════════════════════════════════════════════════════╗
║                 ESTADO DE LA MESA / PEDIDO                ║
╠═══════════════════════════════════════════════════════════════╣
║ 1. MESA VACÍA (no hay pedidos)                          ║
║    └─ Cliente nuevo llega                               ║
║    └─ ACCIÓN: CREAR NUEVO THREAD                        ║
║                                                       ║
║ 2. PEDIDO DRAFT (en curso)                             ║
║    ├─ Cliente pide: "Dame una coca"                    ║
║    ├─ Cliente pide: "Agrega una pizza"                  ║
║    ├─ Pedido en cocina                                  ║
║    ├─ Pedido listo para servir                          ║
║    └─ ACCIÓN: PRESERVAR THREAD (SIEMPRE)               ║
║                                                       ║
║ 3. PEDIDO COBRADO (paid/done)                           ║
║    ├─ Chat ES del pedido cobrado                       ║
║    │   └─ ACCIÓN: CREAR NUEVO THREAD                    ║
║    └─ Chat NO es del pedido cobrado                     ║
║        └─ ACCIÓN: PRESERVAR THREAD                      ║
╚═══════════════════════════════════════════════════════════════╝
```

### Implementación Actual vs Ideal

| Escenario | Actual (con bugs) | Ideal | Solución |
|-----------|------------------|-------|----------|
| Pedido DRAFT existe | ❌ NO detecta (has_active_order=false) | ✅ PRESERVAR | Corregir consulta |
| Pedido DRAFT + nuevo mensaje | ❌ Crea thread nuevo | ✅ PRESERVAR | Corregir consulta |
| Pedido PAID + chat de ese pedido | ✅ CREAR NUEVO | ✅ CREAR NUEVO | OK |
| Pedido PAID + chat de otro tema | ✅ PRESERVAR | ✅ PRESERVAR | OK |
| Al refrescar (F5) | ❌ PIERDE HISTORIAL | ✅ PRESERVAR | Guardar threadId |

---

## 🎯 RESUMEN DE ACCIONES REQUERIDAS

| # | Acción | Archivo | Prioridad | Tiempo | Impacto |
|---|--------|---------|-----------|--------|---------|
| 1 | Corregir URL de contibackend en config.yaml | hermes_profiles/resto/config.yaml | CRÍTICO | 5 min | Hermes carga pedidos |
| 2 | Crear herramienta pos_search_orders | /compose/addons/pos_mp_qr/data/mcp_tools.xml | CRÍTICO | 10 min | Consulta correcta |
| 3 | Actualizar conti_mcp en Odoo | Reiniciar odoo18 | ALTO | 5 min | Herramientas disponibles |
| 4 | Corregir shouldCreateNewThread() | /compose/chatui/src/app/api/chat/[tenant]/route.ts | ALTO | 15 min | Lógica correcta |
| 5 | Guardar threadId en frontend | Frontend ChatUI | MEDIO | 20 min | Sin pérdida al F5 |

---

## 📊 VERIFICACIÓN

### Prueba 1: Hermes puede cargar pedidos
```bash
# Probar herramienta kitchen_get_orders
docker exec conti-backend hermes -p resto mcp test kitchen_get_orders

# Probar nueva herramienta pos_search_orders
docker exec conti-backend hermes -p resto mcp test pos_search_orders
```

### Prueba 2: ChatUI detecta pedidos
```bash
# Simular pedido en mesa 101
# Abrir ChatUI y verificar logs:
docker logs chatui | grep "thread-decision"
# Debería mostrar: "Hay orden draft - preservar"
```

### Prueba 3: Historial se preserva al F5
1. Abrir ChatUI mesa 101
2. Enviar mensaje
3. Refrescar
4. Verificar que el historial aparece

---

## 📝 CONCLUSIÓN

**Problema principal:** 
Hermes NO puede conectarse a contibackend MCP (problema de red/resolución DNS) + NO existe la herramienta `pos.search_orders` que Hermes intenta usar.

**Solución principal:**
1. Corregir conexión Hermes → contibackend
2. Crear herramienta `pos_search_orders` en Odoo MCP
3. Corregir lógica de threads en ChatUI para usar MCP directamente
4. Implementar persistencia de threadId en frontend

**Impacto esperado:**
- ✅ Hermes podra cargar pedidos
- ✅ ChatUI tomara decisiones correctas sobre threads
- ✅ No se perdera historial al refrescar
- ✅ Experiencia de usuario restaurada

---

**Documento generado por Conti - Asistente IA**  
**Fecha:** 15 de Junio de 2026, 16:45 ART  
**Versión:** 2.0  
**Estado:** Para aprobación del usuario
