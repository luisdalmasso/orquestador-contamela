# Odoo-Django-API - Documentación Completa

<div align="center">
  <img src="./readme/odoo_logo.png" alt="Odoo" width="200"/>
  <img src="./readme/django-logo.png" alt="Django" width="200"/>
</div>

## 📋 Resumen Ejecutivo

Sistema de **microservicios asíncrono** que actúa como backend alternativo para Odoo, especializado en:
- **Procesamiento OCR** (Reconocimiento Óptico de Caracteres)
- **API REST** para integración con sistemas externos
- **Gestión de catálogo de productos**
- **Procesamiento de pedidos de venta**
- **Integración bidireccional con Odoo**

## 🏗️ Arquitectura del Sistema

### Componentes Principales

| Componente | Tecnología | Puerto | Función |
|------------|------------|--------|---------|
| **Django REST API** | Django 4.2.7 + DRF 3.14.0 | 8080 | Servidor principal y APIs |
| **PostgreSQL** | PostGIS 12.1 | 5432 | Base de datos con soporte GIS |
| **Redis** | Redis Alpine | 6379 | Cache y broker de mensajes |
| **Celery Workers** | Celery 5.3.4 | - | Procesamiento asíncrono |
| **Nginx** | Nginx + uWSGI | 80→8080 | Proxy reverso |
| **Módulo Odoo** | Python | - | Extensión para Odoo 14+ |

### Aplicaciones Django

- **`documents`**: Gestión de documentos y procesamiento OCR
- **`odoo_integration`**: Integración bidireccional con Odoo
- **`rest`**: Configuración principal del proyecto

## 🔄 Flujos de Trabajo Principales

### 1. Flujo OCR Asíncrono
```mermaid
graph TD
    A[Usuario sube documento en Odoo] --> B[Cron job detecta documento]
    B --> C[Odoo envía a Django API]
    C --> D[Django almacena en PostgreSQL]
    D --> E[Celery procesa OCR]
    E --> F[Guarda texto extraído]
    F --> G[Envía resultado a Odoo]
    G --> H[Odoo actualiza campo ocr_text]
```

### 2. Flujo de Venta con IA
```mermaid
graph TD
    A[IA solicita contexto] --> B[IA crea carrito]
    B --> C[IA añade productos]
    C --> D[IA confirma pedido]
    D --> E[Sistema notifica equipo]
    E --> F[Cliente sube comprobante]
    F --> G[Sistema procesa pago]
```

## 📄 Funcionalidades Detalladas

### Subcarpeta `documents` - Gestión de Documentos y OCR

#### Modelos de Datos
```python
class Document:
    name = CharField(max_length=60)                    # Nombre del documento
    text = TextField(null=True, blank=True)            # Texto extraído por OCR
    file = FileField(blank=False, null=True)           # Archivo físico
    mimetype = CharField(max_length=60, null=True)     # Tipo MIME
    ocr_processed = BooleanField(default=False)        # Estado OCR
    res_model = CharField(max_length=60, null=True)    # Modelo vinculado
    res_id = IntegerField(default=0)                   # ID del registro
    odoo_sent = BooleanField(default=False)            # Enviado a Odoo
    odoo_id = IntegerField(default=0)                  # ID en Odoo
    created_by = ForeignKey(User)                      # Usuario creador

class Odoo:
    user = OneToOneField(User)                         # Usuario Django
    odoo_url = CharField(max_length=100)               # URL de Odoo
    odoo_user = CharField(max_length=30)               # Usuario Odoo
    odoo_password = CharField(max_length=30)           # Contraseña
    odoo_database = CharField(max_length=30)           # Base de datos
```

#### API REST de Documentos
- **Endpoint**: `/documents/`
- **Métodos**: GET, POST, PUT, DELETE
- **Autenticación**: Token-based authentication
- **Serialización**: DocumentSerializer con campos completos

#### Tareas Asíncronas (Celery)

**1. Procesamiento OCR** (`process_ocr`)
```python
@shared_task
def process_ocr():
    # Busca documentos no procesados
    docs = Document.objects.filter(ocr_processed=False)
    
    for doc in docs:
        # Soporte para PDF, JPEG, PNG
        if doc.mimetype == 'application/pdf':
            # Convierte PDF a imagen
            pages = convert_from_path(path, 500)
            for page in pages:
                # Procesa cada página con EasyOCR
                data = reader.readtext(buffer_image)
        elif doc.mimetype in ['image/jpeg', 'image/png']:
            # Procesa imagen directamente
            data = reader.readtext(path)
        
        # Guarda texto extraído
        doc.text = extracted_text
        doc.ocr_processed = True
        doc.save()
```

**2. Sincronización con Odoo** (`process_odoo`)
```python
@shared_task
def process_odoo():
    # Busca documentos procesados no enviados
    docs = Document.objects.filter(
        ocr_processed=True,
        odoo_sent=False,
        odoo_id__gt=0
    )
    
    for doc in docs:
        # Conecta con Odoo vía XML-RPC
        models.execute_kw(db, uid, password, 
            'documents.document', 'write', 
            [[doc.odoo_id], {'ocr_text': doc.text}]
        )
        doc.odoo_sent = True
        doc.save()
```

### Subcarpeta `odoo_integration` - Integración Bidireccional

#### Cliente Odoo Avanzado (`odoo_client.py`)

**Características**:
- **Conexión lazy**: Se conecta solo cuando es necesario
- **Reconexión automática**: Maneja timeouts y errores
- **Cache inteligente**: Optimiza consultas repetitivas

```python
class OdooClient:
    def _execute_kw_with_retry(self, model, method, args, kwargs=None):
        """Wrapper con reintento automático"""
        try:
            return self.models.execute_kw(self.db, self.uid, self.password, 
                                        model, method, args, kwargs)
        except (xmlrpc.client.ProtocolError, ConnectionRefusedError) as e:
            # Reconecta y reintenta
            self._connect()
            return self.models.execute_kw(self.db, self.uid, self.password, 
                                        model, method, args, kwargs)
    
    def get_product_catalog(self, filters=None, limit=100, offset=0):
        """Catálogo con filtros avanzados"""
        domain = [['active', '=', True], ['sale_ok', '=', True]]
        
        if filters:
            if filters.get('search'):
                # Búsqueda multi-campo con OR
                search_terms = filters['search'].split()
                for term in search_terms:
                    domain.extend([
                        '|', ('name', 'ilike', term),
                        '|', ('default_code', 'ilike', term),
                        '|', ('barcode', 'ilike', term),
                        ('description_sale', 'ilike', term)
                    ])
```

#### APIs de Integración Completas

**1. Catálogo de Productos** (`/api/products/`)
```python
class ProductCatalogView(APIView):
    def get(self, request):
        # Parámetros de consulta
        search = request.query_params.get('search', '')
        category_ids = request.query_params.getlist('category_ids', [])
        has_stock = request.query_params.get('has_stock', '').lower() == 'true'
        price_min = request.query_params.get('price_min')
        price_max = request.query_params.get('price_max')
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        
        # Cache inteligente por filtros
        cache_key = f"product_catalog_{hash(str(filters))}_{limit}_{offset}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return Response(cached_result)
        
        # Consulta a Odoo
        products = odoo_client.get_product_catalog(filters, limit, offset)
        
        # Cache por 5 minutos
        cache.set(cache_key, result, 300)
        
        return Response({
            'success': True,
            'total': len(products),
            'products': products,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'has_more': len(products) == limit
            }
        })
```

**2. Contexto de IA** (`/api/ai/context/`)
```python
class AIContextView(APIView):
    def get(self, request):
        cuit_dni = request.query_params.get('cuit_dni')
        
        context = {
            'user_context': {},
            'product_context': {
                'total_products': total_products,
                'products_with_stock': products_with_stock,
                'top_products': top_products[:5],
                'categories': categories[:10]
            },
            'business_context': {
                'available_categories': [cat['name'] for cat in categories],
                'price_ranges': {'min': min_price, 'max': max_price},
                'inventory_status': 'Buen nivel de stock'
            }
        }
        
        if cuit_dni:
            # Buscar cliente y estadísticas
            clients = odoo_client.search_read('res.partner', 
                                            [('vat', '=', cuit_dni)])
            if clients:
                # Estadísticas de compra
                historical_orders = odoo_client.search_read('sale.order',
                    [('partner_id', '=', partner_id), 
                     ('state', 'in', ['sale', 'done'])])
                
                context['user_context'] = {
                    'client_info': clients[0],
                    'purchase_stats': {
                        'total_orders': len(historical_orders),
                        'average_purchase_amount': avg_amount,
                        'last_purchase_date': last_date
                    }
                }
        
        return Response(context)
```

**3. Orquestador de Ventas** (`/api/ai/sales/orchestrate/`)
```python
class SalesOrchestratorView(APIView):
    def post(self, request):
        action = request.data.get('action')
        payload = request.data.get('payload', {})
        
        if action == 'create_cart':
            return self._create_cart(payload)
        elif action == 'add_item_to_cart':
            return self._add_item_to_cart(payload)
        elif action == 'confirm_cart':
            return self._confirm_cart(payload)
    
    def _create_cart(self, payload):
        cuit_dni = payload.get('cuit_dni')
        partners = odoo_client.search_read('res.partner', 
                                         [('vat', '=', cuit_dni)])
        if not partners:
            return Response({'success': False, 'error': 'Cliente no encontrado'})
        
        order_vals = {'partner_id': partners[0]['id']}
        new_order_id = odoo_client.create('sale.order', order_vals)
        
        return Response({'success': True, 'order_id': new_order_id})
    
    def _add_item_to_cart(self, payload):
        order_id = payload.get('order_id')
        product_id = int(payload.get('product_search'))
        quantity = int(payload.get('quantity'))
        
        # Validar stock
        product = odoo_client.read('product.product', [product_id], 
                                 ['qty_available', 'name'])[0]
        
        if product['qty_available'] < quantity:
            return Response({
                'success': False,
                'error': 'Stock insuficiente',
                'details': f"Disponible: {product['qty_available']}"
            })
        
        # Crear línea de pedido
        line_vals = {
            'order_id': order_id,
            'product_id': product_id,
            'product_uom_qty': quantity
        }
        line_id = odoo_client.create('sale.order.line', line_vals)
        
        return Response({'success': True, 'quantity_added': quantity})
    
    def _confirm_cart(self, payload):
        order_id = payload.get('order_id')
        
        # Confirmar pedido (draft → sale)
        odoo_client.execute_method('sale.order', 'action_confirm', 
                                 [[int(order_id)]])
        
        # Notificar equipo de ventas
        users_to_notify = settings.ODOO_NOTIFY_USERS
        partner_ids = odoo_client.get_partner_ids_from_logins(users_to_notify)
        
        odoo_client.post_message(
            model='sale.order',
            record_id=order_id,
            subject=f"Nuevo Pedido Confirmado",
            body=f"<p>Pedido confirmado vía API</p>",
            partner_ids=partner_ids
        )
        
        return Response({'success': True, 'message': 'Pedido confirmado'})
```

**4. Procesamiento de Pagos** (`/api/orders/{id}/payment/`)
```python
class PaymentView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, order_id):
        uploaded_file = request.FILES.get('file')
        cuit_dni = request.data.get('cuit_dni')
        
        # Validar pedido y propiedad
        orders = odoo_client.search_read('sale.order', 
                                       [['id', '=', order_id]])
        if not orders or orders[0]['state'] != 'sale':
            return Response({'success': False, 'error': 'Pedido inválido'})
        
        # Validar CUIT/DNI
        partner_id = orders[0]['partner_id'][0]
        partners = odoo_client.read('res.partner', [partner_id], ['vat'])
        if partners[0]['vat'] != cuit_dni:
            return Response({'success': False, 'error': 'No autorizado'})
        
        # Adjuntar archivo
        file_content = uploaded_file.read()
        attachment_id = odoo_client.create_attachment(
            model='sale.order',
            record_id=order_id,
            filename=uploaded_file.name,
            file_content=file_content
        )
        
        # Notificar en chatter
        odoo_client.post_message(
            model='sale.order',
            record_id=order_id,
            subject=f"Comprobante de pago recibido",
            body=f"<p>Archivo: <b>{uploaded_file.name}</b></p>",
            partner_ids=partner_ids_to_notify
        )
        
        return Response({
            'success': True,
            'message': 'Comprobante recibido y adjuntado',
            'attachment_id': attachment_id
        })
```

### Módulo Odoo (`document_ocr`)

#### Funcionalidades del Módulo
```python
class DocumentsDocument(models.Model):
    _inherit = 'documents.document'
    
    ocr_sent = fields.Boolean()      # Documento enviado a OCR
    ocr_text = fields.Text()         # Texto extraído por OCR
    
    def action_send(self):
        """Enviar documento al servicio OCR"""
        ocr_connector = self._get_default_connector()
        if ocr_connector:
            response = ocr_connector.sendDocument(self)
            if response:
                self.ocr_sent = True
                # Añadir tag de enviado
                tag_ids = [self.env.ref("document_ocr.documents_ocr_sent_tag").id]
                self._add_tags_to_document(tag_ids)
    
    @api.model
    def _send_to_ocr(self):
        """Método del cron job"""
        documents = self.search([
            ('ocr_sent', '=', False),
            ('mimetype', 'in', ('application/pdf', 'image/jpeg', 'image/png')),
            ('folder_id.ocr_sync', '=', True)
        ])
        
        for document in documents:
            document.action_send()
```

#### Configuración del Cron Job
```xml
<record id="ir_cron_send_documents_to_ocr" model="ir.cron">
    <field name="name">Send documents to OCR</field>
    <field name="model_id" ref="model_documents_document"/>
    <field name="state">code</field>
    <field name="code">model._send_to_ocr()</field>
    <field name="interval_number">2</field>
    <field name="interval_type">minutes</field>
    <field name="active" eval="True"/>
</record>
```

## ⚙️ Configuración del Sistema

### Variables de Entorno (`db.env`)
```bash
# Base de datos
POSTGRES_USER=rest_user
POSTGRES_PASSWORD=rest_password
POSTGRES_DB=rest_database

# Conexión Odoo
ODOO_URL=http://odoo18:8069
ODOO_DB=demo_ar
ODOO_USERNAME=luisdalmasso@gmail.com
ODOO_PASSWORD=123
```

### Configuración Django (`settings.py`)
```python
# Celery Configuration
CELERY_BROKER_URL = "redis://redis:6379"
CELERY_RESULT_BACKEND = "redis://redis:6379"
CELERY_BEAT_SCHEDULE = {
    'odoo': {
        'task': 'documents.tasks.process_odoo',
        'schedule': crontab(minute='*/2')  # Cada 2 minutos
    },
}

# Odoo Configuration
ODOO_URL = os.environ.get('ODOO_URL', 'http://odoo18:8069')
ODOO_DB = os.environ.get('ODOO_DB', 'demo')
ODOO_USERNAME = os.environ.get('ODOO_USERNAME', 'admin')
ODOO_PASSWORD = os.environ.get('ODOO_PASSWORD', 'admin')

# Notificaciones
ODOO_NOTIFY_USERS = ['luisdalmasso@gmail.com']

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5678",  # N8n
    "http://odoo18:8069",
]
```

### Docker Compose
```yaml
version: "3.3"

services:
  nginx:
    container_name: nginx
    build: ./nginx
    ports:
      - "8080:80"
    volumes:
      - ./django/rest/staticfiles:/static
      - ./django/rest/mediafiles:/media
    depends_on:
      - django

  db:
    container_name: postgres
    image: kartoza/postgis:12.1
    env_file: db.env
    volumes:
      - django-postgres:/var/lib/postgresql/data

  django:
    container_name: django
    build: ./django
    command: uwsgi --ini ./uwsgi/uwsgi.ini
    volumes:
      - ./django:/code
    depends_on:
      - db
    env_file: db.env

  redis:
    image: redis:alpine

  celery:
    build: ./django
    command: celery -A rest worker -l info -E
    volumes:
      - ./django:/code
    depends_on:
      - db
      - redis
      - django
    env_file: db.env

  celery-beat:
    build: ./django
    command: celery -A rest beat -l info
    volumes:
      - ./django:/code
    depends_on:
      - db
      - redis
      - django
    env_file: db.env
```

## 🚀 Instalación y Configuración

### 1. Requisitos Previos
```bash
# Instalar Docker y Docker Compose
docker --version
docker-compose --version

# Clonar repositorio
git clone <repository-url>
cd odoo-django-api
```

### 2. Configuración de Variables
```bash
# Editar archivo de configuración
cp db.env.example db.env
nano db.env

# Configurar variables según tu entorno
POSTGRES_USER=tu_usuario
POSTGRES_PASSWORD=tu_password
ODOO_URL=http://tu-odoo:8069
ODOO_USERNAME=tu_usuario_odoo
ODOO_PASSWORD=tu_password_odoo
```

### 3. Despliegue con Docker
```bash
# Construir y levantar servicios
docker-compose up --build

# En otra terminal, aplicar migraciones
docker exec -it django bash
python manage.py migrate
python manage.py createsuperuser

# Crear token para Odoo
python manage.py drf_create_token nombre_usuario_odoo
```

### 4. Configuración del Módulo Odoo
```bash
# Copiar módulo a addons
cp -r odoo/document_ocr /path/to/odoo/addons/

# En Odoo:
# 1. Actualizar lista de aplicaciones
# 2. Instalar módulo "Document OCR"
# 3. Configurar OCR Connector en Configuración General
# 4. Activar "OCR Sync" en Workspaces deseados
```

## 📊 APIs Disponibles

### Endpoints de Documentos
| Método | Endpoint | Descripción | Autenticación |
|--------|----------|-------------|---------------|
| GET | `/documents/` | Listar documentos | Token |
| POST | `/documents/` | Subir documento | Token |
| GET | `/documents/{id}/` | Detalle documento | Token |
| PUT | `/documents/{id}/` | Actualizar documento | Token |
| DELETE | `/documents/{id}/` | Eliminar documento | Token |

### Endpoints de Integración Odoo
| Método | Endpoint | Descripción | Autenticación |
|--------|----------|-------------|---------------|
| GET | `/api/products/` | Catálogo de productos | Pública |
| GET | `/api/products/{id}/` | Detalle de producto | Pública |
| GET | `/api/test-connection/` | Probar conexión Odoo | Pública |
| GET | `/api/ai/context/` | Contexto para IA | Pública |
| POST | `/api/clients/` | Buscar/crear clientes | Pública |
| POST | `/api/orders/` | Crear pedido | Pública |
| GET | `/api/orders/{id}/` | Detalle pedido | Pública |
| PATCH | `/api/orders/{id}/` | Confirmar pedido | Pública |
| POST | `/api/orders/{id}/payment/` | Procesar pago | Pública |
| POST | `/api/ai/sales/orchestrate/` | Orquestador ventas | Pública |

### Endpoints de Social Manager (Redes Sociales)

| Método | Endpoint | Descripción | Autenticación |
|--------|----------|-------------|---------------|
| GET | `/social/api/account-config/` | Obtener configuración de cuenta | Token |
| POST | `/social/api/instagram/publish/` | Publicar en Instagram | Token |
| POST | `/social/api/facebook/publish/` | Publicar en Facebook | Token |
| GET | `/social/api/instagram/preview/` | Listar posts de Instagram | Token |
| GET | `/social/api/facebook/preview/` | Listar posts de Facebook | Token |
| GET | `/social/api/instagram/get/` | Detalle de post Instagram | Token |
| GET | `/social/api/facebook/get/` | Detalle de post Facebook | Token |

---

## 📱 APIs de Social Manager - Documentación Detallada

### Autenticación para Social Manager

Todos los endpoints de Social Manager requieren autenticación mediante **Token Authentication** de Django REST Framework.

**Header requerido:**
```
Authorization: Token <tu_token>
```

**Obtener un token:**
```bash
# Desde Django shell
python manage.py shell
>>> from rest_framework.authtoken.models import Token
>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='tu_usuario')
>>> token, created = Token.objects.get_or_create(user=user)
>>> print(f"Token: {token.key}")
```

---

### 1. API: Configuración de Cuenta

**Endpoint:** `GET /social/api/account-config/`

**Descripción:** Consulta la configuración de cuentas de Instagram y Facebook para aplicaciones externas.

**Parámetros de Query:**

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `account_name` | string | Sí | Nombre de la cuenta (ej: "InfoMendoza") |

**Respuesta Exitosa (200):**
```json
{
  "account_name": "InfoMendoza",
  "access_token": "EAAMDwZBZC...",
  "instagram_business_id": "17841401234567890",
  "page_id": "123456789012345"
}
```

**Ejemplo curl:**
```bash
curl -H "Authorization: Token a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0" \
     "http://localhost:8000/social/api/account-config/?account_name=InfoMendoza"
```

**Ejemplo Python:**
```python
import requests

url = "http://localhost:8000/social/api/account-config/"
headers = {"Authorization": "Token a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"}
params = {"account_name": "InfoMendoza"}

response = requests.get(url, headers=headers, params=params)
if response.status_code == 200:
    data = response.json()
    print(f"Access Token: {data['access_token']}")
    print(f"Instagram Business ID: {data['instagram_business_id']}")
    print(f"Page ID: {data['page_id']}")
```

**Códigos de Error:**
- **400**: Falta parámetro `account_name`
- **401**: Token inválido o faltante
- **404**: Cuenta no encontrada
- **500**: Error interno del servidor

---

### 2. API: Instagram Publish

**Endpoint:** `POST /social/api/instagram/publish/`

**Descripción:** Publica o programa una publicación en Instagram.

**Parámetros (JSON Body):**

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `account_name` | string | Sí | Nombre de la cuenta |
| `tipo` | string | Sí | "FEED" o "STORY" |
| `titulo` | string | Sí | Título de la publicación |
| `texto` | string | Sí | Caption/texto de la publicación |
| `url_imagen` | string | Sí | URL de la imagen |
| `fecha_publicacion` | string | No | Fecha ISO 8601 para programar. Si se omite, se publica inmediatamente. |

**Respuesta Inmediata (sin fecha_publicacion):**
```json
{
  "status": "ok",
  "message": "Publicado exitosamente",
  "post_id": "17841401234567890",
  "db_id": 42
}
```

**Respuesta Programada (con fecha_publicacion):**
```json
{
  "status": "ok_programada",
  "message": "Publicación programada exitosamente",
  "scheduled_id": 42,
  "scheduled_time": "2026-01-15T10:00:00-03:00"
}
```

**Ejemplo curl - Publicación Inmediata:**
```bash
curl -X POST \
  -H "Authorization: Token 26b0e4ed39b477e429fa31a39978c8b5f68b1a17" \
  -H "Content-Type: application/json" \
  -d '{
    "account_name": "admin",
    "tipo": "FEED",
    "titulo": "Publicación de Prueba",
    "texto": "Esta es una publicación de prueba desde la API",
    "url_imagen": "https://contamela.com/media/test.jpg"
  }' \
  "http://django-api:8000/social/api/instagram/publish/"
```

**Ejemplo curl - Publicación Programada:**
```bash
curl -X POST \
  -H "Authorization: Token 26b0e4ed39b477e429fa31a39978c8b5f68b1a17" \
  -H "Content-Type: application/json" \
  -d '{
    "account_name": "admin",
    "tipo": "FEED",
    "titulo": "Publicación Programada",
    "texto": "Esta publicación se publicará mañana",
    "url_imagen": "https://contamela.com/media/test.jpg",
    "fecha_publicacion": "2026-01-15T10:00:00-03:00"
  }' \
  "http://django-api:8000/social/api/instagram/publish/"
```

**Ejemplo Python:**
```python
import requests

url = "http://django-api:8000/social/api/instagram/publish/"
headers = {
    "Authorization": "Token 26b0e4ed39b477e429fa31a39978c8b5f68b1a17",
    "Content-Type": "application/json"
}
data = {
    "account_name": "admin",
    "tipo": "FEED",
    "titulo": "Mi Publicación",
    "texto": "Texto de la publicación",
    "url_imagen": "https://contamela.com/media/image.jpg"
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

---

### 3. API: Facebook Publish

**Endpoint:** `POST /social/api/facebook/publish/`

**Descripción:** Publica o programa una publicación en Facebook.

### 4. API: Instagram Preview (Listar Posts)

**Endpoint:** `GET /social/api/instagram/preview/`

**Descripción:** Obtiene las últimas publicaciones de la cuenta de Instagram configurada. Soporta paginación mediante cursores.

**Parámetros de Query:**

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `account_name` | string | Sí | Nombre de la cuenta (ej: "admin") |
| `limit` | int | No | Cantidad de posts a traer (default: 20, max: 100) |
| `after` | string | No | Cursor de paginación para traer la siguiente página |

**Respuesta Exitosa (200):**
```json
{
  "status": "success",
  "account_info": {
    "name": "Nombre Cuenta",
    "followers_count": 1234,
    "media_count": 42,
    "profile_picture_url": "https://...",
    "reach": 5000,
    "impressions": 15000
  },
  "posts": [
    {
      "id": "178...",
      "titulo": "Caption del post...",
      "imagen": "https://...",
      "likes": 10,
      "comentarios": 2,
      "visualizaciones": 100,
      "fecha_publicacion": "2026-01-15T...",
      "tipo": "IMAGE",
      "permalink": "https://instagram.com/p/..."
    }
  ],
  "paging": {
    "cursors": {
      "before": "QVFI...",
      "after": "QVFI..."
    },
    "next": "https://graph.facebook.com/..."
  }
}
```

**Ejemplo curl:**
```bash
curl -H "Authorization: Token <token>" \
     "http://django-api:8000/social/api/instagram/preview/?account_name=admin&limit=50&after=QVFI..."
```

---

**Respuestas:** Mismo formato que Instagram Publish

**Ejemplo curl:**
```bash
curl -X POST \
  -H "Authorization: Token 26b0e4ed39b477e429fa31a39978c8b5f68b1a17" \
  -H "Content-Type: application/json" \
  -d '{
    "account_name": "admin",
    "tipo": "FEED",
    "titulo": "Post en Facebook",
    "texto": "Publicación en Facebook desde la API",
    "url_imagen": "https://contamela.com/media/test.jpg"
  }' \
  "http://django-api:8000/social/api/facebook/publish/"
```

---

### 4. API: Instagram Preview

**Endpoint:** `GET /social/api/instagram/preview/`

**Descripción:** Obtiene lista de publicaciones de Instagram con métricas (sin texto completo).

**Parámetros (Query String):**

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `account_name` | string | Sí | Nombre de la cuenta |
| `maxpub` | int | No | Máximo de publicaciones (0 = todas, default=20) |

**Respuesta:**
```json
{
  "status": "ok",
  "count": 15,
  "posts": [
    {
      "id": "17841401234567890",
      "titulo": "Título de la publicación (primeros 100 caracteres)",
      "imagen": "https://scontent.cdninstagram.com/...",
      "likes": 150,
      "comentarios": 23,
      "visualizaciones": 1200,
      "fecha_publicacion": "2026-01-13T10:00:00+00:00",
      "tipo": "IMAGE",
      "permalink": "https://www.instagram.com/p/..."
    }
  ]
}
```

**Ejemplo curl - Últimas 10 publicaciones:**
```bash
curl -H "Authorization: Token 26b0e4ed39b477e429fa31a39978c8b5f68b1a17" \
  "http://django-api:8000/social/api/instagram/preview/?account_name=admin&maxpub=10"
```

**Ejemplo curl - Todas las publicaciones:**
```bash
curl -H "Authorization: Token 26b0e4ed39b477e429fa31a39978c8b5f68b1a17" \
  "http://django-api:8000/social/api/instagram/preview/?account_name=admin&maxpub=0"
```

**Ejemplo Python:**
```python
import requests

url = "http://django-api:8000/social/api/instagram/preview/"
headers = {"Authorization": "Token 26b0e4ed39b477e429fa31a39978c8b5f68b1a17"}
params = {"account_name": "admin", "maxpub": 10}

response = requests.get(url, headers=headers, params=params)
data = response.json()

for post in data['posts']:
    print(f"{post['titulo']} - Likes: {post['likes']}")
```

---

### 5. API: Facebook Preview

**Endpoint:** `GET /social/api/facebook/preview/`

**Descripción:** Obtiene lista de publicaciones de Facebook con métricas (sin texto completo).

**Parámetros:** Idénticos a Instagram Preview

**Respuesta:**
```json
{
  "status": "ok",
  "count": 12,
  "posts": [
    {
      "id": "123456789_987654321",
      "titulo": "Título de la publicación (primeros 100 caracteres)",
      "imagen": "https://scontent.xx.fbcdn.net/...",
      "likes": 89,
      "comentarios": 12,
      "compartidos": 5,
      "visualizaciones": 0,
      "fecha_publicacion": "2026-01-13T09:00:00+00:00",
      "tipo": "FEED",
      "permalink": "https://www.facebook.com/..."
    }
  ]
}
```

**Ejemplo curl:**
```bash
curl -H "Authorization: Token 26b0e4ed39b477e429fa31a39978c8b5f68b1a17" \
  "http://django-api:8000/social/api/facebook/preview/?account_name=admin&maxpub=20"
```

---

### 6. API: Instagram Get

**Endpoint:** `GET /social/api/instagram/get/`

**Descripción:** Obtiene detalles completos de una publicación de Instagram incluyendo texto y comentarios.

**Parámetros (Query String):**

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `account_name` | string | Sí | Nombre de la cuenta |
| `post_id` | string | Sí | ID de la publicación |
| `tipo` | string | Sí | "FEED" o "STORY" |

**Respuesta:**
```json
{
  "status": "ok",
  "post": {
    "id": "17841401234567890",
    "titulo": "Título (primeros 100 caracteres)",
    "texto": "Caption completo de la publicación...",
    "imagen": "https://scontent.cdninstagram.com/...",
    "likes": 150,
    "comentarios": 23,
    "visualizaciones": 1200,
    "fecha_publicacion": "2026-01-13T10:00:00+00:00",
    "tipo": "IMAGE",
    "permalink": "https://www.instagram.com/p/...",
    "comments": [
      {
        "id": "17841401234567891",
        "username": "usuario1",
        "text": "¡Excelente post!",
        "timestamp": "2026-01-13T11:00:00+00:00"
      }
    ]
  }
}
```

**Ejemplo curl:**
```bash
curl -H "Authorization: Token 26b0e4ed39b477e429fa31a39978c8b5f68b1a17" \
  "http://django-api:8000/social/api/instagram/get/?account_name=admin&post_id=17841401234567890&tipo=FEED"
```

---

### 7. API: Facebook Get

**Endpoint:** `GET /social/api/facebook/get/`

**Descripción:** Obtiene detalles completos de una publicación de Facebook incluyendo texto, comentarios y reacciones.

**Parámetros:** Idénticos a Instagram Get

**Respuesta:**
```json
{
  "status": "ok",
  "post": {
    "id": "123456789_987654321",
    "titulo": "Título (primeros 100 caracteres)",
    "texto": "Texto completo de la publicación...",
    "imagen": "https://scontent.xx.fbcdn.net/...",
    "likes": 89,
    "comentarios": 12,
    "compartidos": 5,
    "visualizaciones": 0,
    "fecha_publicacion": "2026-01-13T09:00:00+00:00",
    "tipo": "FEED",
    "permalink": "https://www.facebook.com/...",
    "comments": [
      {
        "id": "987654321_111111111",
        "from": {
          "name": "Usuario Ejemplo",
          "id": "111111111"
        },
        "message": "Muy interesante!",
        "created_time": "2026-01-13T10:00:00+00:00"
      }
    ],
    "reactions": {
      "total": 89
    }
  }
}
```

**Ejemplo curl:**
```bash
curl -H "Authorization: Token 26b0e4ed39b477e429fa31a39978c8b5f68b1a17" \
  "http://django-api:8000/social/api/facebook/get/?account_name=admin&post_id=123456789_987654321&tipo=FEED"
```

---

### Notas Importantes - Social Manager APIs

> **⚠️ Publicaciones Programadas**
> - Las publicaciones programadas se guardan en la base de datos
> - Requieren un comando cron o tarea programada para ejecutarse
> - Usa el comando Django: `python manage.py check_scheduled_posts`

> **⚠️ Límites de la API de Meta**
> - Instagram Stories no soportan caption/texto
> - Facebook puede tener límites de rate limiting
> - Las métricas de visualizaciones pueden no estar disponibles inmediatamente

> **💡 Mejores Prácticas**
> - Usa URLs de imágenes públicamente accesibles
> - Verifica que las imágenes cumplan con los requisitos de Meta
> - Para Stories, usa imágenes en formato 9:16
> - Para Feed, usa imágenes cuadradas o 4:5

---

### Ejemplos de Uso

**Obtener catálogo con filtros:**
```bash
curl -X GET "http://localhost:8080/api/products/?search=laptop&category_ids=1,2&has_stock=true&limit=10"
```

**Crear carrito para cliente:**
```bash
curl -X POST "http://localhost:8080/api/ai/sales/orchestrate/" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "create_cart",
    "payload": {"cuit_dni": "20123456789"}
  }'
```

**Añadir producto al carrito:**
```bash
curl -X POST "http://localhost:8080/api/ai/sales/orchestrate/" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "add_item_to_cart",
    "payload": {
      "order_id": 123,
      "product_search": "456",
      "quantity": 2
    }
  }'
```

**Subir comprobante de pago:**
```bash
curl -X POST "http://localhost:8080/api/orders/123/payment/" \
  -F "file=@comprobante.pdf" \
  -F "cuit_dni=20123456789"
```

## 🔧 Características Técnicas Avanzadas

### Cache Inteligente
```python
# Cache por filtros de productos (5 minutos)
cache_key = f"product_catalog_{hash(str(filters))}_{limit}_{offset}"
cache.set(cache_key, result, 300)

# Cache por producto individual (10 minutos)
cache_key = f"product_detail_{product_id}"
cache.set(cache_key, result, 600)
```

### Manejo de Errores y Reconexión
```python
def _execute_kw_with_retry(self, model, method, args, kwargs=None):
    try:
        return self.models.execute_kw(self.db, self.uid, self.password, 
                                    model, method, args, kwargs)
    except (xmlrpc.client.ProtocolError, ConnectionRefusedError) as e:
        logger.warning(f"Error de conexión: {e}. Reconectando...")
        self._connect()  # Reconectar
        return self.models.execute_kw(self.db, self.uid, self.password, 
                                    model, method, args, kwargs)
```

### Sistema de Logging
```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
```

## 📈 Casos de Uso Principales

### 1. Digitalización Masiva de Documentos
- **Problema**: Empresas con grandes volúmenes de documentos escaneados
- **Solución**: Procesamiento OCR asíncrono sin afectar Odoo
- **Beneficios**: Extracción automática, indexación, búsqueda

### 2. E-commerce con Integración ERP
- **Problema**: Tiendas online necesitan catálogo actualizado
- **Solución**: API REST con cache inteligente
- **Beneficios**: Rendimiento optimizado, stock en tiempo real

### 3. Asistentes de IA para Ventas
- **Problema**: Chatbots necesitan contexto empresarial
- **Solución**: API de contexto con datos actualizados
- **Beneficios**: Respuestas precisas, procesamiento de pedidos

### 4. Automatización de Procesos de Venta
- **Problema**: Procesos manuales lentos y propensos a errores
- **Solución**: Orquestador de ventas con validaciones
- **Beneficios**: Automatización completa, notificaciones automáticas

## ⚠️ Consideraciones de Producción

### Seguridad
```python
# ❌ Desarrollo (inseguro)
CORS_ALLOW_ALL_ORIGINS = True
DEBUG = True

# ✅ Producción (seguro)
CORS_ALLOWED_ORIGINS = ["https://tu-dominio.com"]
DEBUG = False
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
```

### Rendimiento
```yaml
# Configuración para producción
services:
  django:
    deploy:
      replicas: 3
  
  celery:
    deploy:
      replicas: 5
  
  redis:
    image: redis:alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

### Monitoreo
```python
# Integración con Sentry
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn="https://tu-dsn@sentry.io/proyecto",
    integrations=[DjangoIntegration(), CeleryIntegration()],
    traces_sample_rate=0.1,
)
```

### Backup y Recuperación
```bash
# Backup automático PostgreSQL
docker exec postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d).sql

# Backup archivos media
tar -czf media_backup_$(date +%Y%m%d).tar.gz django/rest/mediafiles/

# Restauración
docker exec -i postgres psql -U $POSTGRES_USER $POSTGRES_DB < backup.sql
```

## 🎯 Ventajas del Sistema

### Técnicas
- ✅ **Desacoplamiento**: Tareas pesadas no afectan Odoo
- ✅ **Escalabilidad**: Microservicios independientes
- ✅ **Asíncrono**: Procesamiento no bloqueante
- ✅ **Cache inteligente**: Mejor rendimiento
- ✅ **Reconexión automática**: Alta disponibilidad

### Funcionales
- ✅ **OCR automático**: Procesamiento masivo de documentos
- ✅ **API moderna**: REST con JSON para cualquier frontend
- ✅ **Integración nativa**: Sincronización bidireccional con Odoo
- ✅ **Notificaciones**: Sistema automático de alertas
- ✅ **Validaciones**: Control de stock y permisos

### Operacionales
- ✅ **Docker**: Despliegue simplificado
- ✅ **Logging completo**: Debugging y monitoreo
- ✅ **Configuración flexible**: Variables de entorno
- ✅ **Backup automático**: Protección de datos

## 🔮 Roadmap y Mejoras Futuras

### Corto Plazo
- [ ] Integración con Amazon Textract para OCR avanzado
- [ ] Soporte para más idiomas en OCR
- [ ] Dashboard de monitoreo en tiempo real
- [ ] Tests automatizados completos

### Mediano Plazo
- [ ] Integración con servicios de IA (OpenAI, AWS Bedrock)
- [ ] Sistema de webhooks para notificaciones
- [ ] API GraphQL como alternativa a REST
- [ ] Soporte para múltiples instancias de Odoo

### Largo Plazo
- [ ] Machine Learning para clasificación automática de documentos
- [ ] Integración con blockchain para trazabilidad
- [ ] Soporte para Odoo Cloud
- [ ] Marketplace de conectores

## 📞 Soporte y Contribución

### Reportar Problemas
- **Issues**: Usar GitHub Issues para bugs y feature requests
- **Logs**: Incluir logs completos y pasos para reproducir
- **Versiones**: Especificar versiones de Docker, Odoo y Python

### Contribuir
```bash
# Fork del repositorio
git clone https://github.com/tu-usuario/odoo-django-api.git
cd odoo-django-api

# Crear rama para feature
git checkout -b feature/nueva-funcionalidad

# Hacer cambios y commit
git add .
git commit -m "feat: nueva funcionalidad"

# Push y crear Pull Request
git push origin feature/nueva-funcionalidad
```

### Desarrollo Local
```bash
# Entorno de desarrollo
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r django/requirements.txt

# Variables de entorno para desarrollo
export DJANGO_SETTINGS_MODULE=rest.settings
export ODOO_URL=http://localhost:8069
export ODOO_DB=test_db
```

## 📄 Licencia

Este proyecto está licenciado bajo AGPL-3.0 - ver el archivo [LICENSE](LICENSE) para detalles.

## 👥 Autores

- **Agustin Wisky** - *Desarrollo inicial* - [@awisky](https://github.com/awisky)

## 🙏 Agradecimientos

- Comunidad de Odoo por el framework base
- Django REST Framework por las APIs
- EasyOCR por el procesamiento de texto
- Docker por la containerización

---

<div align="center">
  <p><strong>¿Te gusta este proyecto? ⭐ Dale una estrella en GitHub!</strong></p>
  <p>Para más información, visita: <a href="https://github.com/awisky/odoo-django-api">https://github.com/awisky/odoo-django-api</a></p>
</div>