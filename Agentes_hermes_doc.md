# 📋 Reporte de Agentes Hermes - Conti Backend

> **Fecha de generación:** 2026-07-04  
> **Contenedor:** conti-backend  
> **Stack:** FastAPI (MCP backend) + Hermes-Agent multi-perfil + OpenHands

---

## 🎯 Resumen Ejecutivo

El contenedor `conti-backend` ejecuta una arquitectura de agentes basada en **Hermes-Agent** (framework de NousResearch) con múltiples perfiles especializados para diferentes dominios de negocio:

- **7 perfiles de agentes** activos con configuraciones independientes
- **Integración con Odoo** vía MCP (Model Context Protocol) para gestión ERP
- **Múltiples canales de comunicación**: Telegram, WhatsApp, Slack, Discord, API REST
- **Infraestructura Docker** con más de 10 servicios expuestos
- **OpenHands** como agente de desarrollo complementario

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONTI-BACKEND (Docker Container)                  │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │  FastAPI (9001)  │  │  OpenHands      │  │  Hermes         │     │
│  │  MCP Backend     │  │  Agent (3000)   │  │  Dashboard (9119)│     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              HERMES-AGENT PROFILES                           │   │
│  ├──────────┬──────────┬──────────┬──────────┬─────────────────┤   │
│  │ católico │  resto   │   odoo   │ mendoza  │   odoo-mendoza  │   │
│  │  (8766)  │  (8767)  │  (8768)  │  (8770)  │     (8769)      │   │
│  └──────────┴──────────┴──────────┴──────────┴─────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              MCP SERVERS                                      │   │
│  │  • contibackend (localhost:9001/mcp) - FastAPI MCP           │   │
│  │  • odoo_mcp (odoo18:8072/mcp) - Odoo ERP MCP               │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 👥 Perfiles de Agentes

### 1. 🍽️ **Resto** (Perfil Activo)

| Aspecto | Detalle |
|---------|---------|
| **Nombre** | Mesero Inteligente / Mozo Virtual |
| **Puerto API** | 8767 |
| **Tipo de Usuario** | Clientes finales (comensales) |
| **Idioma** | Español |
| **Modelo LLM** | `deepseek-v4-flash` (DeepSeek) |
| **Tono** | Cálido, cercano y respetuoso |
| **Transporte MCP** | HTTP |

**Propósito:** Asistente de pedidos para restaurantes que interactúa directamente con los comensales.

**Habilidades Principales:**
- Consultar la carta/menú del restaurante
- Tomar pedidos y agregar items a mesas
- Facturar y cobrar pedidos
- Mostrar estado de cocina
- Generar reportes de ventas

**Herramientas MCP Disponibles:**
- `search_read` - Consultar productos, pedidos, mesas
- `create_records` - Crear líneas de pedido
- `download_report` - Generar PDFs/cartas
- `kitchen_get_orders` - Ver pedidos en cocina
- `kitchen_mark_ready/done` - Cambiar estados de cocina

**Flujo de Trabajo:**
1. Identificar mesa desde metadata del mensaje
2. Verificar pedido activo en Odoo (`state = 'draft'`)
3. Ejecutar acción solicitada
4. Confirmar con dato clave (número, total, estado)

**Skills Especiales:**
- `buscar_presentar_productos` - Catálogo visual con imágenes
- `send-carta-pdf` - Envío de carta digital
- `gemini-vision` - Análisis de imágenes recibidas
- `voice-manager` - Transcripción de audio

---

### 2. ⛪ **Católico**

| Aspecto | Detalle |
|---------|---------|
| **Nombre** | Asistente Católico |
| **Puerto API** | 8766 |
| **Tipo de Usuario** | Fieles católicos |
| **Idioma** | Español |
| **Transporte MCP** | HTTP |

**Propósito:** Acompañamiento espiritual y consultas sobre fe católica.

**Habilidades Principales:**
- Lecturas litúrgicas del día
- Búsqueda de pasajes bíblicos
- Consulta de doctrina católica
- Santoral y calendario litúrgico
- Generación de infografías religiosas

**Herramientas MCP Disponibles (vía contibackend):**
- `search_rag` - Búsqueda semántica en base de conocimiento
- `search_rag_semantic` - Búsqueda conceptual avanzada
- `search_rag_quick` - Verificación rápida de documentos
- `catolico_biblia_buscar` - Búsqueda de pasajes bíblicos
- `catolico_lecturas_dia` - Lecturas del día
- `catolico_leer_documento` - Lectura de documentos extensos
- `analyze_image` - Análisis de imágenes con Gemini
- `ocr_image` - Extracción de texto de imágenes

**Alcance:**
- ✅ Lecturas litúrgicas, Biblia, doctrina católica, santoral
- ❌ Política, temas polémicos, comparaciones religiosas

---

### 3. 🏢 **Odoo** (ERP Multi-tenant)

| Aspecto | Detalle |
|---------|---------|
| **Nombre** | Conti ERP |
| **Puerto API** | 8768 |
| **Tipo de Usuario** | Personal interno del restaurante |
| **Idioma** | Español |
| **Transporte MCP** | HTTP |

**Propósito:** Asistente operativo interno para gestión del ERP Odoo.

**Habilidades Principales:**
- Gestión de pedidos y comandas
- Facturación y pagos
- Consulta de productos y carta
- Gestión de clientes
- Reportes de ventas y caja

**Reglas Críticas:**
1. **Tenant First:** Siempre verificar `tenant_id` antes de cualquier acción
2. **Aislamiento de Datos:** Datos de un tenant invisibles para otros
3. **Precisión Operativa:** Nunca inventar datos, siempre consultar Odoo

**Comandos de Lenguaje Natural:**
- "cargame una hamburguesa bacon en la mesa 109" → Crear línea de pedido
- "facturame la mesa 110" → Confirmar pedido + crear factura
- "sacame de cocina el pedido de la mesa 102" → Marcar como entregado
- "cuánto vendimos hoy" → Reporte de ventas del día

---

### 4. 🏔️ **Odoo-Mendoza** (Backend Staff)

| Aspecto | Detalle |
|---------|---------|
| **Nombre** | Conti ERP Mendoza |
| **Puerto API** | 8769 + Telegram |
| **Tipo de Usuario** | Personal interno OCRL Mendoza |
| **Idioma** | Español |
| **Transporte MCP** | HTTP |

**Propósito:** Asistente para la sucursal de OCRL Mendoza (distribución mayorista de tecnología).

**Habilidades Específicas:**
- Gestión de productos técnicos con multimedia (imágenes, datasheets PDF)
- Precios en USD con conversión por tipo de cambio
- Gestión de accesorios y productos opcionales
- RMA (Return Merchandise Authorization)
- Cotizaciones y ventas

**Skills Obligatorias:**
| Intención | Skill |
|-----------|-------|
| Alta producto, imágenes, datasheets | `productos-con-multimedia` |
| Tipo de cambio, USD | `tipo-cambio-usd` |
| Accesorios | `accesorios-producto` |
| RMA, devoluciones | `rma-mendoza` |
| SQL crudo | `db-manager` |
| Backup BD | `db-manager` |
| Restart/logs | `docker-manager` |
| Email | `email-manager` |
| Workflows n8n | `n8n-manager` |

---

### 5. 🍝 **Odoo-Nudo**

| Aspecto | Detalle |
|---------|---------|
| **Nombre** | Conti ERP |
| **Canal** | Telegram exclusivo |
| **Tipo de Usuario** | Personal interno |
| **Idioma** | Español |

**Propósito:** Similar al perfil Odoo, pero dedicado al tenant `nudo`.

**Características:**
- Misma estructura que el perfil Odoo
- Comparte `TOOLS.md` con el perfil Odoo (symlink)
- Configuración MCP específica para tenant `nudo`

---

### 6. 🍽️ **Odoo-Resto**

| Aspecto | Detalle |
|---------|---------|
| **Nombre** | Conti ERP |
| **Canal** | Telegram exclusivo |
| **Tipo de Usuario** | Personal interno del restaurante resto |
| **Idioma** | Español |

**Propósito:** Asistente ERP dedicado al tenant `resto` vía Telegram.

**Características:**
- Misma estructura que el perfil Odoo
- Comparte `TOOLS.md` con el perfil Odoo (symlink)
- Configuración MCP específica para tenant `resto`

---

### 7. 🛍️ **Mendoza** (Frontend Clientes)

| Aspecto | Detalle |
|---------|---------|
| **Nombre** | Conti ERP Mendoza |
| **Puerto API** | 8770 + WhatsApp |
| **Tipo de Usuario** | Clientes finales OCRL Mendoza |
| **Idioma** | Español |
| **Modelo LLM** | `kilo-auto/free` (Kilocode) |
| **Transporte MCP** | HTTP |

**Propósito:** Asistente para clientes de OCRL Mendoza vía WhatsApp.

**Características:**
- Integración con wppconnect para WhatsApp
- Mismo modelo de negocio que odoo-mendoza
- Enfoque en atención al cliente final

---

## ⚙️ Configuración Global (contihome)

### Modelo LLM por Defecto
```yaml
model:
  default: deepseek-v4-flash
  provider: deepseek
  api_mode: chat_completions
```

### Límites del Agente
```yaml
agent:
  max_turns: 90          # Máximo de turnos por conversación
  gateway_timeout: 1800   # Timeout del gateway (30 min)
  api_max_retries: 3      # Reintentos de API
```

### Terminal (Ejecución de Código)
```yaml
terminal:
  backend: local
  timeout: 180
  docker_image: nikolaik/python-nodejs:python3.11-nodejs20
  container_cpu: 1
  container_memory: 5120  # 5GB
  container_disk: 51200   # 50GB
```

### Compresión de Contexto
```yaml
compression:
  enabled: true
  threshold: 0.5
  target_ratio: 0.2
  protect_last_n: 20
  hygiene_hard_message_limit: 400
```

### MCP Servers Globales
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
```

---

## 🔧 Herramientas y Skills

### Herramientas MCP Principales

| Herramienta | Descripción | Uso |
|-------------|-------------|-----|
| `search_read` | Buscar y leer registros Odoo | Consultas generales |
| `create_records` | Crear nuevos registros | Altas de datos |
| `update_records` | Actualizar registros existentes | Modificaciones |
| `call_method` | Llamar métodos de negocio | Workflows Odoo |
| `download_report` | Generar reportes PDF/URL | Documentos para usuarios |
| `read_group` | Agrupar y agregar datos | Totales y estadísticas |

### Skills Disponibles

#### Cocina (Resto)
- `kitchen_get_orders` - Listar pedidos activos en cocina
- `kitchen_mark_ready` - Marcar pedido como listo
- `kitchen_mark_done` - Marcar pedido como completado

#### Productos (Mendoza)
- `productos-con-multimedia` - Gestión de productos técnicos
- `tipo-cambio-usd` - Conversión de moneda
- `accesorios-producto` - Gestión de accesorios
- `rma-mendoza` - Autorización de devoluciones

#### RAG (Católico)
- `search_rag` - Búsqueda semántica
- `catolico_biblia_buscar` - Búsqueda bíblica
- `catolico_lecturas_dia` - Lecturas litúrgicas

#### Sistema
- `db-manager` - Gestión de bases de datos
- `docker-manager` - Gestión de contenedores
- `django-manager` - Gestión Django
- `n8n-manager` - Automatización de workflows
- `rag-manager` - Gestión de RAG

---

## 📱 Integraciones de Plataforma

### Telegram
- **Perfiles activos:** odoo-resto, odoo-nudo, contihome
- **Configuración:** `platforms.telegram.enabled: true`
- **Política de grupos:** `mention` (responde solo si mencionan)
- **Usuarios permitidos:** Configurables por perfil

### WhatsApp
- **Perfiles activos:** mendoza
- **Tecnología:** wppconnect
- **Estado:** Configuración vacía (pendiente de setup)

### Slack/Discord/Mattermost
- **Configuración disponible** en todos los perfiles
- **Estado:** No activo por defecto
- **Características:** Requiere mención, hilos automáticos, historial

---

## 🌐 Infraestructura y Puertos

| Servicio | Puerto Interno | Puerto Externo | Descripción |
|----------|---------------|----------------|-------------|
| FastAPI MCP | 9001 | 9001/9007 | Backend principal |
| Hermes Católico | 8766 | 8766 | API católico |
| Hermes Resto | 8767 | 8767 | API restaurante |
| Hermes Odoo | 8768 | 8768 | API ERP multi-tenant |
| Hermes Odoo-Mendoza | 8769 | 8769 | API staff Mendoza |
| Hermes Mendoza | 8770 | 8770 | API clientes Mendoza |
| Hermes Dashboard | 9119 | 9119 | Panel de control |
| Hermes Default | 18791 | 18791 | Gateway contihome |
| OpenHands Agent | 3000 | 3011 | API OpenHands |
| OpenHands Canvas | 3012 | 3012 | GUI OpenHands |
| OpenHands CLI | 3001 | 3013 | Terminal web |

### Recursos del Contenedor
- **Memoria:** 24GB límite
- **CPU:** 4 cores
- **Redes:** desarrollo_odoo-network-dev, compose_odoo-network
- **Volúmenes:** Desarrollo, compose, hermes_profiles, etc.

---

## 🔐 Seguridad y Permisos

### Variables de Entorno Sensibles
- `CONTI_MCP_API_KEY` - API key para MCP Odoo
- `ODOO_TENANT_ID` - ID del tenant activo
- `TELEGRAM_BOT_TOKEN` - Token de Telegram
- `MERCADOPAGO_ACCESS_TOKEN` - Token de MercadoPago
- `GEMINI_API_KEY` - API key de Google Gemini
- `KILOCODE_API_KEY` - API key de Kilocode

### Reglas de Seguridad
1. **Redacción de secretos:** `redact_secrets: true`
2. **URLs privadas bloqueadas:** `allow_private_urls: false`
3. **Bloqueo de sitios:** Configurable por dominio
4. **Modo de aprobación:** `manual` (requiere confirmación)

---

## ⚠️ Problemas Conocidos

### Error de Conexión MCP (Perfil Resto)
**Documentado en:** `hermes-fix.md`

**Causas identificadas:**
1. **Filtro de BD de Odoo:** Cabecera `Host` incorrecta (`odoo18:8072` vs `resto.contamela.com`)
2. **Conflicto de Transporte:** Uso de `transport: sse` vs `transport: http`

**Solución recomendada:**
```yaml
odoo_mcp:
  url: http://odoo18:8072/mcp
  transport: http  # Cambiar de sse a http
  headers:
    Host: resto.contamela.com  # Corregir host
```

---

## 📊 Estado Actual

### Perfiles Activos
- ✅ `resto` (perfil activo por defecto)
- ✅ `catolico` (API en 8766)
- ✅ `odoo` (API en 8768)
- ✅ `odoo-mendoza` (API + Telegram en 8769)
- ✅ `mendoza` (API + WhatsApp en 8770)
- ✅ `odoo-resto` (Telegram)
- ✅ `odoo-nudo` (Telegram)

### Servicios en Ejecución
- ✅ FastAPI MCP Backend
- ✅ 7 Gateways de Hermes
- ✅ OpenHands Agent Server
- ✅ OpenHands Agent Canvas
- ✅ OpenHands CLI Web
- ✅ Hermes Dashboard

---

## 🚀 Comandos Útiles

### Reiniciar Servicios
```bash
docker compose -f docker-compose.conti.yml restart conti-backend
```

### Ver Logs
```bash
# Logs específicos
tail -f /app/logs/hermes_resto_gateway.log
tail -f /app/logs/hermes_catolico_gateway.log
tail -f /app/logs/fastapi.log

# Logs de todos los servicios
ls -la /app/logs/
```

### Cambiar Perfil Activo
```bash
# Dentro del contenedor
echo "mendoza" > /app/hermes_profiles/contihome/active_profile
```

### Verificar Estado de Gateways
```bash
# Health checks
curl http://localhost:8766/health
curl http://localhost:8767/health
curl http://localhost:8768/health
```

---

## 📚 Archivos de Configuración Importantes

| Archivo | Descripción |
|---------|-------------|
| `/app/hermes_profiles/contihome/config.yaml` | Configuración global |
| `/app/hermes_profiles/contihome/profiles/*/config.yaml` | Config por perfil |
| `/app/hermes_profiles/contihome/profiles/*/SOUL.md` | Personalidad y reglas |
| `/app/hermes_profiles/contihome/profiles/*/TOOLS.md` | Herramientas disponibles |
| `/app/hermes_profiles/contihome/profiles/*/CONSTANTS.md` | Constantes Odoo |
| `/app/hermes_profiles/contihome/profiles/*/AGENTS.md` | Instrucciones de agente |
| `entrypoint_hermes.sh` | Script de inicio |
| `docker-compose.conti.yml` | Configuración Docker |
| `hermes-fix.md` | Diagnóstico de problemas |

---

## 🔄 Actualizaciones y Mantenimiento

### Actualizar Hermes
```bash
hermes --version  # Verificar versión actual
hermes update     # Actualizar si disponible
```

### Backup de Configuración
```bash
# Backup de perfiles
tar -czf hermes_profiles_backup_$(date +%Y%m%d).tar.gz /app/hermes_profiles/
```

### Monitoreo
- **Dashboard:** http://localhost:9119
- **Logs:** /app/logs/
- **Health checks:** Puertos 8766-8770

---

*Reporte generado automáticamente el 2026-07-04*
*Contenedor: conti-backend*
*Stack: Hermes-Agent v0.14.x + FastAPI + OpenHands*