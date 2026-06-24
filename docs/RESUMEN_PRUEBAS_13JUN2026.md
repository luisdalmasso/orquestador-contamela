# RESUMEN DE PRUEBAS - 13 de Junio de 2026

Documento: RESUMEN_PRUEBAS_13JUN2026.md
Fecha: 13 de Junio de 2026
Version: 1.1
Autor: Conti (Asistente IA)

---

## Resumen Ejecutivo

Este documento consolida los resultados de las pruebas de validacion realizadas el 13 de Junio de 2026 sobre la nueva logica de manejo de threads en ChatUI, disenada para prevenir la perdida de contexto en Hermes cuando cambia de comensal.

### Estado General
- Logica de threads CORREGIDA e IMPLEMENTADA
- Todos los tests unitarios PASARON
- Documentacion actualizada
- Pruebas end-to-end pendientes de validacion en produccion

---

## Detalles de la Implementacion

### Archivos Modificados

1. `/compose/chatui/src/app/api/chat/[tenant]/route.ts`
   - Funcion: shouldCreateNewThread()
   - Cambio: Eliminados todos los keywords para deteccion de pagos
   - Nueva logica: Basada EXCLUSIVAMENTE en estado real de pedidos en Odoo
   - Consulta: Endpoint /api/chat/[tenant]/order-status
   - Campos clave: has_order (true/false), last_order_id

2. `/compose/chatui/test-thread-logic.js`
   - Tests actualizados para validar nueva logica
   - 7 casos de prueba implementados
   - Todos pasando

3. `/contenedores/conti-backend/docs/hermes-mcp-diagnostico.md`
   - Version actualizada a 1.4
   - Documentacion de logica corregida

---

## Resultados de Pruebas Unitarias

Ejecucion: cd /compose/chatui && node test-thread-logic.js

Casos de Prueba:

1. Hay orden SIN COBRAR -> PRESERVAR -> PASS
2. Chat SI es del pedido cobrado (metadata) -> CREAR NUEVO -> PASS
3. Chat SI es del pedido cobrado (contenido) -> CREAR NUEVO -> PASS
4. Chat NO es del pedido cobrado -> PRESERVAR -> PASS
5. Thread vacio -> PRESERVAR -> PASS
6. Sin table_identifier -> PRESERVAR -> PASS
7. Mesa con otra orden sin cobrar -> PRESERVAR -> PASS

Resultado: 7/7 tests PASSED

---

## Logica de Decision Implementada

Regla de Negocio (Validada con usuario):

1. Si hay orden SIN COBRAR (estado draft en Odoo)
   -> PRESERVAR thread SIEMPRE

2. Si NO hay orden sin cobrar
   Y hay orden COBRADA
   Y el chat ES del pedido cobrado
   -> CREAR NUEVO THREAD

3. En todos los otros casos
   -> PRESERVAR thread

Mecanismo de Correlacion Chat-Pedido:
- Metadata del mensaje: order_id, pos_order_id, pedido_id
- Contenido del mensaje: patron regex /(?:pedido|orden|comanda|ticket|n|#)(\d+)/gi
- Comparacion contra last_order_id (pedido cobrado)

---

## Diferencias vs Version Anterior

Version 1.3 (DESCARTADA):
- Usaba KEYWORDS para detectar pagos
- Problemas: Falsos positivos/negativos, depende de texto

Version 1.4 (ACTUAL):
- Consulta ESTADO REAL de Odoo
- Correlacion por ID de pedido
- Mas preciso y confiable

---

## Proximos Pasos

Validacion en Produccion:
1. Prueba manual en entorno real
2. Monitoreo de logs: buscar [chatui thread-decision]
3. Validar con Hermes que contexto se preserva

Tareas Pendientes:
- Validar en produccion con datos reales
- Monitorear logs por 24-48 horas
- Ajustar timeout si es necesario

---

Historial:
13-Jun-2026 12:45 - Version 1.0 (keywords)
13-Jun-2026 15:30 - Version 1.1 (estado real Odoo)

Documento generado por Conti - Asistente IA
Ultima actualizacion: 13 de Junio de 2026, 15:30 ART
Version: 1.1
