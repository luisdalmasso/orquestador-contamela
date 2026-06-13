**Perfil del Usuario:** Luis Dalmasso (Solution Architect / Desarrollador).

**ENTORNO DE OPERACIÓN (contenedor `conti-backend` sobre VPS Linux Ubuntu, en la red de desarrollo):**
- **Usuario Host:** `admin_odoo`
- **Ruta Raíz del Proyecto en DESARROLLO:** `/desarrollo`
- **Ruta Raíz del Proyecto en PRODUCCIÓN:** `/compose` (`READ ONLY`)
- **HOME persistente del backend:** `/home/nanobot` (bind desde `/contenedores/conti_home`)

### 🌐 REGLA OPERATIVA DE ACCESO A CÓDIGO
- **No usar SSH** para leer o modificar repos ya bind-mounted en este contenedor.
- **Trabajar directo en `/desarrollo`** para cambios editables.
- **Consultar `/compose` solo en lectura** para referencia de producción.
- **Usar tools MCP de GitOps** para commit/promoción (`run_salvar`, `run_promover`) en vez de comandos Git manuales desde agentes.

### 🗺️ MAPA DE SERVICIOS Y TÚNELES (Cloudflared)
### CONTENEDORES DE PRODUCCIÓN

Red Docker: `compose_odoo-network`. Para conexiones directas entre contenedores, USA SUS NOMBRES (DNS interno).

Docker compose: `/compose/producion.yml`

| Servicio | Contenedor Interno | Puerto | Dominio Público (Túnel) | Ruta de Código/Volumen en Host |
| :--- | :--- | :--- | :--- | :--- |
| **Django API** | `django-api` | 8000 | `https://contamela.com` | `/compose/odoo-django-api/django` |
| **Odoo ERP** | `odoo18` | 8069, 8072 | `https://odoo.contamela.com` | `/compose/odoo18/addons` |
| **Evolution API**| `evolution-api-server` | 8080 | `https://webhook.contamela.com` | Volumen Docker: `evolution-api-data` |
| **WppConnect** | `wppconnect-server` | 21465| `https://wpp.contamela.com` | `/compose/images_wpp` |
| **n8n** | `n8n` | 5678 | `https://odoo-bot.contamela.com`| `/compose/n8n` |
| **Chatwoot Web** | `chatwoot_web` | 3000 | (Depende de FRONTEND_URL) | Volumen Docker: `chatwoot_data` |
| **Chatwoot Worker**| `chatwoot_worker`| N/A | Tareas en 2do plano | Volumen Docker: `chatwoot_data` |
| **Portainer** | `portainer` | 9000 | N/A (Solo red interna) | Volumen Docker: `portainer_data` |
| **Cloudflared** | `cloudflared-tunnel`| N/A | Enruta tráfico a dominios | N/A (Usa Token) |
| **Ollama (LLM)** | `ollama` | 11434| N/A (Solo red interna) | Volumen Docker: `ollama_data` |
| **Mixpost** | `mixpost-app` | 8001 | (Depende de APP_URL) | Volúmenes: `storage`, `logs` |
| **Netdata** | `monitor_netdata` | 19999| N/A (Solo red interna) | Volúmenes: `netdatalib`, `netdatacache` |
| **PostgreSQL** | `db` | 5432 | N/A (Solo red interna) | `/compose/postgresql.conf` |
| **Redis** | `redis_odoo` | 6379 | N/A (Solo red interna) | Volumen Docker: `redis_data` |

### CONTENEDORES DE DESARROLLO

Red Docker: `desarrollo_odoo-network-dev`. Para conexiones directas entre contenedores, USA SUS NOMBRES (DNS interno).

Docker compose: `/desarrollo/desarrollo.yml`

| Servicio | Contenedor Interno | Puerto | Dominio Público (Túnel) | Ruta de Código/Volumen en Host |
| :--- | :--- | :--- | :--- | :--- |
| **Django API** | `django-dev` | 8001:8000 | `https://dev.contamela.com` | `/desarrollo/odoo-django-api/django` |
| **Odoo ERP** | `odoo18_dev` | 8169:8069 8073:8072 | `https://dev.odoo.contamela.com` | `/desarrollo/odoo18/addons` |
| **n8n** | `n8n_dev` | 5680:5680 | `https://dev-webhook.contamela.com` | `/desarrollo/n8n` |
| **Chatwoot Web** | `chatwoot_web_dev` | 3001:3001 | (Depende de FRONTEND_URL) | Volumen Docker: `chatwoot_data` |
| **Chatwoot Worker** | `chatwoot_worker_dev` | N/A | Tareas en 2do plano | Volumen Docker: `chatwoot_data` |
| **Cloudflared** | `cloudflared-tunnel-dev` | N/A | Enruta tráfico a dominios | N/A (Usa Token) |
| **PostgreSQL** | `db_dev` | 5532:5532 | N/A (Solo red interna) | `/desarrollo/postgresql.conf` |
| **Redis** | `redis_odoo_dev` | 6380:6380 | N/A (Solo red interna) | Volumen Docker: `redis_data` |

**Ejemplos de Conexión Eficiente:**
- **Desde Conti a Base de Datos:** NO usar SSH. Ejecutar directo: `PGPASSWORD=... psql -h db -U odoo -d odoo -c "SELECT..."`
- **Desde Conti a Código Django en desarrollo:** leer directo en `/desarrollo/odoo-django-api/django`.
- **Desde Conti a código de producción:** inspeccionar directo en `/compose/odoo-django-api/django` sin escribir.


