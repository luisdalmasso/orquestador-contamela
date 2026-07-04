# Documentación de Herramientas MCP - Conti Backend

## Índice

1. [Introducción](#1-introducción)
2. [Endpoints Disponibles](#2-endpoints-disponibles)
3. [Categorías de Herramientas](#3-categorías-de-herramientas)
4. [Visibilidad](#4-visibilidad)
5. [Catálogo Completo de Herramientas](#5-catálogo-completo-de-herramientas-64-herramientas)
   - [5.1 Sistema de Archivos](#51-herramientas-de-sistema-de-archivos-filesystem)
   - [5.2 Búsqueda](#52-herramientas-de-búsqueda-search)
   - [5.3 Sistema](#53-herramientas-de-sistema-system)
   - [5.4 Odoo ERP](#54-herramientas-de-odoo-erp)
   - [5.5 Git](#55-herramientas-de-git)
   - [5.6 Docker](#56-herramientas-de-docker-y-contenedores)
   - [5.7 Traducción](#57-herramientas-de-traducción)
   - [5.8 Documentos](#58-herramientas-de-documentos)
   - [5.9 RAG](#59-herramientas-de-rag-retrieval-augmented-generation)
   - [5.10 Católicas](#510-herramientas-católicas)
   - [5.11 Google Sheets](#511-herramientas-de-google-sheets-ocrl)
6. [Ejemplo de Uso](#6-ejemplo-de-uso)
7. [Notas de Implementación](#7-notas-de-implementación)

---

## 1. Introducción

El endpoint `/mcp` implementa el protocolo **Model Context Protocol (MCP)** para exponer herramientas (tools) a clientes de IA como Hermes, Claude, VS Code MCP, Amazon Q, Kilocode y Cline. Este servidor MCP está integrado en el backend FastAPI de Conti y proporciona acceso a funcionalidades de Odoo ERP, sistema de archivos, búsqueda RAG, contenedores Docker, Git y más.

## 2. Endpoints Disponibles

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/mcp` | GET | Información del servidor MCP y capacidades |
| `/mcp/` | GET | Alias del endpoint raíz |
| `/mcp` | POST | Endpoint JSON-RPC 2.0 (Estándar MCP) |
| `/mcp/` | POST | Alias del endpoint JSON-RPC |
| `/mcp/tools` | GET | Listar todas las herramientas disponibles |
| `/mcp/call` | POST | Invocar herramienta vía REST |
| `/mcp/execute` | POST | Ejecutar herramienta (Legacy) |
| `/mcp/sse` | GET | Conexión Server-Sent Events (SSE) |
| `/mcp/sse/` | GET | Alias SSE |
| `/mcp/sse` | POST | Endpoint JSON-RPC via SSE transport |
| `/mcp/sse/` | POST | Alias SSE POST |

## 3. Categorías de Herramientas

Las herramientas están organizadas en las siguientes categorías:

- **filesystem**: Operaciones de lectura y exploración del sistema de archivos
- **search**: Búsqueda de texto literal, regex y semántica
- **system**: Herramientas de sistema, Odoo, Git, Docker, RAG, traducción
- **config**: Configuración y reglas del backend

## 4. Visibilidad

- **public**: Disponible para todos los clientes MCP
- **internal**: Solo para uso interno del sistema
- **admin**: Requiere permisos de administración

## 5. Catálogo Completo de Herramientas (64 herramientas)

### 5.1 Herramientas de Sistema de Archivos (filesystem)

#### `list_files`
- **Descripción**: Lista archivos y directorios bajo un root permitido
- **Visibilidad**: public
- **Tags**: filesystem, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "path": {"type": "string"}
    }
  }
  ```

#### `read_file`
- **Descripción**: Lee un archivo dentro de los roots permitidos
- **Visibilidad**: public
- **Tags**: filesystem, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "path": {"type": "string"},
      "start_line": {"type": "integer"},
      "end_line": {"type": "integer"}
    },
    "required": ["path"]
  }
  ```

#### `file_exists`
- **Descripción**: Informa si un path permitido existe
- **Visibilidad**: public
- **Tags**: filesystem, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "path": {"type": "string"}
    },
    "required": ["path"]
  }
  ```

#### `get_code_context`
- **Descripción**: Devuelve contexto alrededor de una línea de un archivo permitido
- **Visibilidad**: public
- **Tags**: filesystem, code
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "path": {"type": "string"},
      "line": {"type": "integer"},
      "context": {"type": "integer"}
    },
    "required": ["path"]
  }
  ```

### 5.2 Herramientas de Búsqueda (search)

#### `search_code_literal`
- **Descripción**: Busca texto literal o regex dentro del repo de desarrollo
- **Visibilidad**: public
- **Tags**: search, code
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "query": {"type": "string"}
    },
    "required": ["query"]
  }
  ```

#### `search_docs_literal`
- **Descripción**: Busca texto literal o regex dentro de la documentación del backend
- **Visibilidad**: public
- **Tags**: search, docs
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "query": {"type": "string"}
    },
    "required": ["query"]
  }
  ```

#### `grep_workspace`
- **Descripción**: Busca coincidencias dentro del workspace permitido
- **Visibilidad**: public
- **Tags**: search, workspace
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "query": {"type": "string"}
    },
    "required": ["query"]
  }
  ```

### 5.3 Herramientas de Sistema (system)

#### `health_check`
- **Descripción**: Devuelve el estado actual del backend
- **Visibilidad**: public
- **Tags**: system
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {}
  }
  ```

#### `get_config`
- **Descripción**: Devuelve la configuración efectiva redactada
- **Visibilidad**: public
- **Tags**: config
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {}
  }
  ```

#### `reload_config`
- **Descripción**: Recarga la configuración del backend
- **Visibilidad**: internal
- **Tags**: config
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {}
  }
  ```

#### `get_onboarding`
- **Descripción**: Devuelve el onboarding efectivo del backend
- **Visibilidad**: public
- **Tags**: config, onboarding
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "brief": {"type": "boolean"}
    }
  }
  ```

#### `get_rules`
- **Descripción**: Devuelve las reglas efectivas del backend
- **Visibilidad**: public
- **Tags**: config, rules
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {}
  }
  ```

### 5.4 Herramientas de Odoo ERP

#### `odoo_test_connection`
- **Descripción**: Prueba la conexión configurada contra Odoo y valida autenticación y acceso básico a productos
- **Visibilidad**: public
- **Tags**: odoo, health, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string", "description": "Perfil Odoo configurado, por ejemplo prod o dev."},
      "db": {"type": "string"},
      "url": {"type": "string"},
      "username": {"type": "string"},
      "password": {"type": "string"}
    }
  }
  ```

#### `odoo_list_products`
- **Descripción**: Lista productos de Odoo con filtros de búsqueda, categoría, stock y rango de precios. Por rendimiento, el stock (qty_available) NO se incluye por defecto: pasar has_stock=true o include_stock=true para obtenerlo
- **Visibilidad**: public
- **Tags**: odoo, products, catalog, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "search": {"type": "string"},
      "producto": {"type": "string"},
      "category_ids": {"type": "string", "description": "IDs separados por coma."},
      "has_stock": {"type": "boolean", "description": "Filtra solo productos con stock > 0 (incluye qty_available). Computar stock es lento."},
      "include_stock": {"type": "boolean", "description": "Incluye qty_available en la respuesta sin filtrar. Úsalo solo si necesitas stock; es costoso."},
      "price_min": {"type": "number"},
      "price_max": {"type": "number"},
      "limit": {"type": "integer"},
      "offset": {"type": "integer"}
    }
  }
  ```

#### `odoo_get_product_detail`
- **Descripción**: Obtiene el detalle completo de un producto puntual desde Odoo
- **Visibilidad**: public
- **Tags**: odoo, products, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "product_id": {"type": "integer"}
    },
    "required": ["product_id"]
  }
  ```

#### `odoo_get_ai_context`
- **Descripción**: Devuelve contexto comercial y de cliente desde Odoo para uso por agentes o asistentes
- **Visibilidad**: public
- **Tags**: odoo, context, ai, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "cuit_dni": {"type": "string"}
    }
  }
  ```

#### `odoo_search_clients`
- **Descripción**: Busca clientes en Odoo por CUIT/DNI o nombre y devuelve coincidencias normalizadas
- **Visibilidad**: public
- **Tags**: odoo, clients, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "cuit_dni": {"type": "string"},
      "name": {"type": "string"},
      "limit": {"type": "integer"},
      "offset": {"type": "integer"}
    }
  }
  ```

#### `odoo_list_clients`
- **Descripción**: Lista clientes de Odoo con paginación y filtros opcionales por nombre o CUIT/DNI
- **Visibilidad**: public
- **Tags**: odoo, clients, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "cuit_dni": {"type": "string"},
      "name": {"type": "string"},
      "limit": {"type": "integer"},
      "offset": {"type": "integer"}
    }
  }
  ```

#### `odoo_create_client`
- **Descripción**: Crea un cliente en Odoo con nombre, CUIT/DNI y datos de contacto básicos
- **Visibilidad**: public
- **Tags**: odoo, clients, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "name": {"type": "string"},
      "cuit_dni": {"type": "string"},
      "email": {"type": "string"},
      "phone": {"type": "string"}
    },
    "required": ["name", "cuit_dni"]
  }
  ```

#### `odoo_create_order`
- **Descripción**: Crea un pedido de venta draft en Odoo para un cliente existente
- **Visibilidad**: public
- **Tags**: odoo, sales, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "client_id": {"type": "integer"}
    },
    "required": ["client_id"]
  }
  ```

#### `odoo_create_cart`
- **Descripción**: Busca un cliente por CUIT/DNI y crea un carrito/pedido draft asociado
- **Visibilidad**: public
- **Tags**: odoo, sales, cart, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "cuit_dni": {"type": "string"}
    },
    "required": ["cuit_dni"]
  }
  ```

#### `odoo_add_item_to_cart`
- **Descripción**: Agrega un producto a un carrito/pedido draft validando stock y límites por producto
- **Visibilidad**: public
- **Tags**: odoo, sales, cart, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "order_id": {"type": "integer"},
      "product_id": {"type": "integer"},
      "quantity": {"type": "integer"}
    },
    "required": ["order_id", "product_id", "quantity"]
  }
  ```

#### `odoo_get_cart_summary`
- **Descripción**: Devuelve el resumen de un carrito/pedido y valida que pertenezca al cliente indicado
- **Visibilidad**: public
- **Tags**: odoo, sales, cart, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "order_id": {"type": "integer"},
      "cuit_dni": {"type": "string"}
    },
    "required": ["order_id", "cuit_dni"]
  }
  ```

#### `odoo_confirm_cart`
- **Descripción**: Confirma un pedido draft y devuelve los totales resultantes en Odoo
- **Visibilidad**: public
- **Tags**: odoo, sales, cart, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "order_id": {"type": "integer"}
    },
    "required": ["order_id"]
  }
  ```

#### `odoo_cancel_cart`
- **Descripción**: Cancela un pedido siempre que no esté ya finalizado o cancelado
- **Visibilidad**: public
- **Tags**: odoo, sales, cart, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "order_id": {"type": "integer"}
    },
    "required": ["order_id"]
  }
  ```

#### `odoo_create_invoice`
- **Descripción**: Crea y publica una factura desde un pedido confirmado, validando titularidad del cliente
- **Visibilidad**: public
- **Tags**: odoo, invoice, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "order_id": {"type": "integer"},
      "cuit_dni": {"type": "string"}
    },
    "required": ["order_id", "cuit_dni"]
  }
  ```

#### `odoo_register_payment`
- **Descripción**: Registra un pago sobre la factura publicada de un pedido y deja trazabilidad en el chatter
- **Visibilidad**: public
- **Tags**: odoo, payment, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "order_id": {"type": "integer"},
      "payment_id": {"type": "string"},
      "amount": {"type": "number"},
      "payment_method": {"type": "string"}
    },
    "required": ["order_id", "payment_id", "amount"]
  }
  ```

#### `odoo_create_mercadopago_preference`
- **Descripción**: Crea una preferencia de cobro en Mercado Pago para un pedido y devuelve la URL de pago
- **Visibilidad**: public
- **Tags**: odoo, payment, mercadopago, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "order_id": {"type": "integer"},
      "cuit_dni": {"type": "string"}
    },
    "required": ["order_id", "cuit_dni"]
  }
  ```

#### `odoo_upload_payment_proof`
- **Descripción**: Sube un comprobante de pago (imagen o PDF) a un pedido y lo asocia al chatter
- **Visibilidad**: public
- **Tags**: odoo, payment, attachment, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "order_id": {"type": "integer"},
      "file_name": {"type": "string"},
      "file_content": {"type": "string", "description": "Contenido del archivo en base64"},
      "mime_type": {"type": "string"}
    },
    "required": ["order_id", "file_name", "file_content"]
  }
  ```

#### `odoo_get_invoice_status`
- **Descripción**: Consulta el estado de la factura y pagos de un pedido
- **Visibilidad**: public
- **Tags**: odoo, invoice, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "order_id": {"type": "integer"},
      "cuit_dni": {"type": "string"}
    },
    "required": ["order_id", "cuit_dni"]
  }
  ```

#### `odoo_process_attachment_ocr`
- **Descripción**: Procesa una imagen o PDF adjunto mediante OCR y extrae datos relevantes (montos, fechas, referencias)
- **Visibilidad**: public
- **Tags**: odoo, ocr, attachment, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "file_name": {"type": "string"},
      "file_content": {"type": "string", "description": "Contenido del archivo en base64"},
      "mime_type": {"type": "string"}
    },
    "required": ["file_name", "file_content"]
  }
  ```

#### `odoo_process_pdf_document`
- **Descripción**: Procesa un documento PDF y extrae texto y metadatos relevantes
- **Visibilidad**: public
- **Tags**: odoo, pdf, document, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "connection": {"type": "string"},
      "db": {"type": "string"},
      "file_name": {"type": "string"},
      "file_content": {"type": "string", "description": "Contenido del archivo en base64"}
    },
    "required": ["file_name", "file_content"]
  }
  ```

#### `odoo_get_restaurant_menu`
- **Descripción**: Devuelve la carta del restaurante como una URL de descarga pública DIRECTA (/web/content/<id>?access_token=...) que abre el PDF sin login. El PDF se cachea: la primera vez puede tardar, las siguientes son instantáneas. Usa SIEMPRE esta herramienta cuando pidan ver/mostrar/descargar la carta o el menú. Devuelve 'download_url' y 'download_link' (Markdown listo para enviar al usuario). Requiere 'tenant' (ej: 'resto')
- **Visibilidad**: public
- **Tags**: odoo, restaurant, menu, pdf, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "tenant": {"type": "string", "description": "Nombre del tenant, ej: resto. Se usa como perfil de conexión, DB y para armar la URL https://{tenant}.contamela.com"},
      "include_pdf_base64": {"type": "boolean", "description": "Si true, descarga el PDF y lo devuelve en base64. Default false."},
      "force_refresh": {"type": "boolean", "description": "Si true, regenera el PDF aunque exista una versión cacheada. Úsalo solo si la carta cambió y la versión cacheada está desactualizada. Default false."}
    },
    "required": ["tenant"]
  }
  ```

### 5.5 Herramientas de Git

#### `get_git_status`
- **Descripción**: Devuelve el estado Git local del repo de desarrollo
- **Visibilidad**: public
- **Tags**: git, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "repo_path": {"type": "string"}
    }
  }
  ```

#### `get_git_log`
- **Descripción**: Devuelve el historial reciente del repo Git local
- **Visibilidad**: public
- **Tags**: git, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "repo_path": {"type": "string"},
      "n": {"type": "integer"}
    }
  }
  ```

#### `diff_with_develop`
- **Descripción**: Compara el HEAD local contra develop remoto o local configurado
- **Visibilidad**: public
- **Tags**: git, diff
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "repo_path": {"type": "string"},
      "remote": {"type": "string"},
      "develop_branch": {"type": "string"}
    }
  }
  ```

#### `get_pipeline_summary`
- **Descripción**: Resume el pipeline Git local: rama, estado, remotos y diff contra develop
- **Visibilidad**: public
- **Tags**: git, pipeline, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "repo_path": {"type": "string"},
      "remote": {"type": "string"},
      "develop_branch": {"type": "string"}
    }
  }
  ```

#### `run_salvar`
- **Descripción**: Hace preview o ejecuta commit+push local a develop
- **Visibilidad**: public
- **Tags**: git, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "confirm": {"type": "boolean"},
      "summary": {"type": "string"},
      "repo_path": {"type": "string"},
      "remote": {"type": "string"},
      "develop_branch": {"type": "string"}
    }
  }
  ```

#### `run_promover`
- **Descripción**: Hace preview o ejecuta merge local develop -> main con push
- **Visibilidad**: public
- **Tags**: git, write, promote
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "confirm": {"type": "boolean"},
      "summary": {"type": "string"},
      "repo_path": {"type": "string"},
      "remote": {"type": "string"},
      "develop_branch": {"type": "string"},
      "main_branch": {"type": "string"}
    }
  }
  ```

### 5.6 Herramientas de Docker y Contenedores

#### `get_container_health`
- **Descripción**: Resume estado y salud de contenedores Docker accesibles desde el backend
- **Visibilidad**: public
- **Tags**: docker, containers, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "env": {"type": "string", "enum": ["local", "dev", "prod", "all"]},
      "container": {"type": "string"}
    }
  }
  ```

#### `get_container_logs`
- **Descripción**: Lee logs de un contenedor Docker local con filtros por tiempo, nivel y cantidad de líneas
- **Visibilidad**: public
- **Tags**: docker, logs, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "container": {"type": "string"},
      "lines": {"type": "integer"},
      "since": {"type": "string"},
      "level": {"type": "string", "enum": ["all", "error", "warning"]}
    },
    "required": ["container"]
  }
  ```

#### `get_vps_status`
- **Descripción**: Da una vista consolidada del estado Docker local y del repo Git principal montado
- **Visibilidad**: public
- **Tags**: docker, git, status, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "env": {"type": "string", "enum": ["local", "dev", "prod", "all"]},
      "repo_path": {"type": "string"}
    }
  }
  ```

### 5.7 Herramientas de Traducción

#### `start_markdown_translation`
- **Descripción**: Inicia traducción de Markdown en background y devuelve job_id para seguimiento
- **Visibilidad**: public
- **Tags**: translation, background, markdown
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "input_path": {"type": "string"},
      "output_path": {"type": "string"},
      "source_lang": {"type": "string"},
      "target_lang": {"type": "string"},
      "chunk_size": {"type": "integer"},
      "retries": {"type": "integer"},
      "overwrite": {"type": "boolean"}
    },
    "required": ["input_path"]
  }
  ```

#### `get_translation_job`
- **Descripción**: Consulta estado y progreso de un job de traducción
- **Visibilidad**: public
- **Tags**: translation, status, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "job_id": {"type": "string"}
    },
    "required": ["job_id"]
  }
  ```

#### `list_translation_jobs`
- **Descripción**: Lista jobs recientes de traducción y su estado
- **Visibilidad**: public
- **Tags**: translation, status, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "limit": {"type": "integer"}
    }
  }
  ```

### 5.8 Herramientas de Documentos

#### `start_pdf_to_markdown`
- **Descripción**: Convierte un PDF (URL o ruta local) a Markdown en background y devuelve job_id. Si no se pasa output_path, guarda por defecto en /compose/documentos_listos/{store}/. Opcionalmente inicia traducción automática al terminar
- **Visibilidad**: public
- **Tags**: document, pdf, markdown, background
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "source": {"type": "string", "description": "URL o ruta local al PDF/documento"},
      "store": {"type": "string", "description": "Store destino para output por defecto (default: config.rag.default_store)"},
      "output_path": {"type": "string", "description": "Ruta de salida del .md (opcional)"},
      "also_translate": {"type": "boolean", "description": "Si es true lanza traducción al terminar"},
      "target_lang": {"type": "string", "description": "Idioma destino si also_translate=true (default: en)"}
    },
    "required": ["source"]
  }
  ```

#### `get_md_conversion_job`
- **Descripción**: Consulta estado de un job de conversión PDF/documento a Markdown
- **Visibilidad**: public
- **Tags**: document, status, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "job_id": {"type": "string"}
    },
    "required": ["job_id"]
  }
  ```

#### `list_md_conversion_jobs`
- **Descripción**: Lista jobs recientes de conversión PDF/documento a Markdown
- **Visibilidad**: public
- **Tags**: document, status, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "limit": {"type": "integer"}
    }
  }
  ```

### 5.9 Herramientas de RAG (Retrieval-Augmented Generation)

#### `start_rag_ingest`
- **Descripción**: Ingesta un documento (URL o ruta local) en el RAG Flamehaven. Convierte a Markdown preservando el nombre original y lo sube a una colección (store). Devuelve job_id inmediatamente; el proceso ocurre en background
- **Visibilidad**: public
- **Tags**: rag, document, ingest, background
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "source": {"type": "string", "description": "URL o ruta local al documento (PDF, DOCX, etc.)"},
      "store": {"type": "string", "description": "Colección destino en Flamehaven (default: config rag.default_store)"},
      "original_name": {"type": "string", "description": "Nombre descriptivo para identificar el doc en el índice"},
      "overwrite": {"type": "boolean", "description": "Si true y ya existe un doc con el mismo nombre, lo reemplaza. Si false (default) rechaza el duplicado informando el doc existente."}
    },
    "required": ["source"]
  }
  ```

#### `get_rag_ingest_job`
- **Descripción**: Consulta estado de un job de ingestión RAG en Flamehaven
- **Visibilidad**: public
- **Tags**: rag, status, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "job_id": {"type": "string"}
    },
    "required": ["job_id"]
  }
  ```

#### `list_rag_ingest_jobs`
- **Descripción**: Lista jobs recientes de ingestión RAG en Flamehaven
- **Visibilidad**: public
- **Tags**: rag, status, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "limit": {"type": "integer"}
    }
  }
  ```

#### `scan_documentos_nuevos`
- **Descripción**: Escanea /compose/documentos_nuevos/{store}/ y lanza un job de ingesta por cada archivo. Los archivos se mueven a procesados/ al ser encolados. Opcionalmente puede incluir archivos ya movidos en procesados/. Usa store='all' para escanear todos los stores. Usa dry_run=true para previsualizar sin ingestar. Usa max_files para limitar cuántos archivos encola por request. overwrite=false (default): rechaza documentos con nombre ya existente en el store. overwrite=true: reemplaza el doc anterior
- **Visibilidad**: public
- **Tags**: rag, ingest, scan
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {"type": "string", "description": "Store a escanear, o 'all' para todos (default: config.rag.default_store)"},
      "dry_run": {"type": "boolean", "description": "Solo listar archivos sin ingestar"},
      "max_files": {"type": "integer", "description": "Límite de archivos por llamada para evitar timeout (ej: 25, 50, 100)."},
      "overwrite": {"type": "boolean", "description": "Si true reemplaza docs existentes con el mismo nombre. Default: false."},
      "include_procesados": {"type": "boolean", "description": "Si true incluye tambien documentos_nuevos/{store}/procesados para auditoria o reingesta."}
    }
  }
  ```

#### `search_rag`
- **Descripción**: Búsqueda completa en el RAG Flamehaven con respuesta generada por LLM (Gemini). Soporta modos: hybrid (recomendado, fusiona BM25+semántico), semantic, keyword. Usar cuando Conti necesita RESPONDER algo al usuario basándose en documentos. Devuelve answer, sources, search_confidence [0-1] y low_confidence si los resultados son débiles
- **Visibilidad**: public
- **Tags**: rag, search, hybrid, llm
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Pregunta o consulta a buscar"},
      "store": {"type": "string", "description": "Colección destino (default: config rag.default_store)"},
      "mode": {"type": "string", "enum": ["hybrid", "semantic", "keyword"], "description": "Modo de búsqueda (default: hybrid)"},
      "top_k": {"type": "integer", "description": "Número de resultados (default: 5)"},
      "threshold": {"type": "number", "description": "Umbral de similitud [0-1]"},
      "max_tokens": {"type": "integer", "description": "Máx tokens para la respuesta LLM"}
    },
    "required": ["query"]
  }
  ```

#### `search_rag_quick`
- **Descripción**: Búsqueda rápida por keyword en Flamehaven SIN generar respuesta LLM. Solo devuelve sources y matched. Usar cuando Conti necesita VERIFICAR si algo existe en el RAG o encadenar con otra tool. No consume tokens de Gemini — instantáneo
- **Visibilidad**: public
- **Tags**: rag, search, keyword, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Término o frase a buscar"},
      "store": {"type": "string", "description": "Colección destino (default: config rag.default_store)"},
      "top_k": {"type": "integer", "description": "Número de resultados (default: 5)"}
    },
    "required": ["query"]
  }
  ```

#### `search_rag_semantic`
- **Descripción**: Búsqueda semántica en Flamehaven (DSP v2.0) con respuesta LLM. Sin BM25 — usa únicamente vectores: ideal para queries conceptuales, sinónimos y paráfrasis. Tolerante a typos. Usar cuando las palabras exactas no importan sino el concepto
- **Visibilidad**: public
- **Tags**: rag, search, semantic, llm
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Concepto o pregunta a buscar semánticamente"},
      "store": {"type": "string", "description": "Colección destino (default: config rag.default_store)"},
      "top_k": {"type": "integer", "description": "Número de resultados (default: 5)"},
      "threshold": {"type": "number", "description": "Umbral de similitud [0-1]"},
      "max_tokens": {"type": "integer", "description": "Máx tokens para la respuesta LLM"}
    },
    "required": ["query"]
  }
  ```

#### `list_rag_store_docs`
- **Descripción**: Lista todos los documentos indexados en un store de Flamehaven. Sin búsqueda ni LLM. Usar cuando Conti necesita saber QUÉ documentos hay guardados en el RAG (inventario). Devuelve title, URI y metadata de cada doc
- **Visibilidad**: public
- **Tags**: rag, status, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {"type": "string", "description": "Colección a listar (default: config rag.default_store)"}
    }
  }
  ```

### 5.10 Herramientas Católicas

#### `catolico_lecturas_dia`
- **Descripción**: Obtiene las lecturas del día para la liturgia católica
- **Visibilidad**: public
- **Tags**: catolico, api
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "fecha": {"type": "string", "description": "Fecha de la cual extraer las lecturas (por defecto 'hoy')"}
    }
  }
  ```

#### `catolico_biblia_buscar`
- **Descripción**: Busca citas bíblicas o versículos por palabras clave. Úsala EXCLUSIVAMENTE para referencias bíblicas
- **Visibilidad**: public
- **Tags**: catolico, biblia
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "modo": {"type": "string", "description": "Define si se busca una 'cita' específica o una 'busqueda' por texto."},
      "libro": {"type": "string", "description": "Nombre del libro bíblico (ej: Mateo)"},
      "capitulo": {"type": "number", "description": "Número del capítulo. Requerido si modo='cita'"},
      "versiculo_inicio": {"type": "number"},
      "versiculo_fin": {"type": "number"},
      "texto": {"type": "string", "description": "Texto o frase a buscar. Requerido si modo='busqueda'"}
    },
    "required": ["modo"]
  }
  ```

#### `catolico_listar_titulos`
- **Descripción**: Lista todos los títulos y nombres de archivo de documentos ingestados en el store católico del RAG. Lee el front-matter YAML de cada .md. Usar para validar si un documento existe antes de resumirlo, o para mostrar el catálogo de documentos disponibles al usuario
- **Visibilidad**: public
- **Tags**: catolico, rag, titulos, catalogo
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {"type": "string", "description": "Nombre del store RAG. Default: 'catolico'", "default": "catolico"}
    },
    "required": []
  }
  ```

#### `catolico_leer_documento`
- **Descripción**: Lee el contenido completo de un documento del RAG católico. Úsala si el usuario pide un resumen o leer un documento. Dos modos: (1) por 'uri' exacta que devolvió search_rag — resuelve automáticamente el path real; (2) por 'query' de búsqueda cuando no tenés URI o los resultados de search_rag fueron dudosos/múltiples — busca internamente y devuelve el mejor documento. Preferí el modo 'query' cuando la búsqueda devolvió más de 1 resultado o el título no coincide exactamente
- **Visibilidad**: public
- **Tags**: catolico, rag, resumen
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "uri": {"type": "string", "description": "URI exacta del documento (formato local://catolico/...) tal como la devuelve search_rag. Opcional si usás query."},
      "query": {"type": "string", "description": "Texto de búsqueda para encontrar el documento. Usar cuando no tenés URI exacta o los resultados previos fueron dudosos."},
      "store": {"type": "string", "description": "Nombre del store RAG. Default: 'catolico'", "default": "catolico"}
    },
    "required": []
  }
  ```

#### `catolico_resumir_documento`
- **Descripción**: Genera un resumen estructurado de un documento católico usando SpineDigest. Pipeline de 3 etapas: chunking → grafo de conocimiento → defensa multi-agente. Cachea el resultado para evitar re-procesar. Usar cuando el usuario pide 'resumir', 'resumen de' o 'síntesis de' un documento
- **Visibilidad**: public
- **Tags**: catolico, rag, resumen, spinedigest
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Nombre o título del documento a resumir."},
      "store": {"type": "string", "description": "Nombre del store. Default: 'catolico'", "default": "catolico"},
      "prompt": {"type": "string", "description": "Instrucción de extracción para SpineDigest. Opcional."}
    },
    "required": ["query"]
  }
  ```

### 5.11 Herramientas de Google Sheets (OCRL)

#### `sheet_account_goes_to_sheet`
- **Descripción**: Indica si un codigo de cuenta OCRL debe resolverse en la planilla de Google (prefijo CL*). Usar ANTES de buscar en Odoo: si use_sheet=true, ir directo a sheet_lookup_partner
- **Visibilidad**: public
- **Tags**: ocrl, sheet, identity, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "account_code": {"type": "string"}
    },
    "required": ["account_code"]
  }
  ```

#### `sheet_lookup_partner`
- **Descripción**: Busca un cliente OCRL en la planilla de Google por codigo de cuenta, CUIT o identidad de chat (channel wa/lid/tg + token). Fallback Tier 2: usar para cuentas CL* o cuando el cliente NO se encontro en Odoo. Devuelve price_adjustment y line_discount (=-price_adjustment)
- **Visibilidad**: public
- **Tags**: ocrl, sheet, identity, read-only
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "account_code": {"type": "string"},
      "cuit": {"type": "string"},
      "channel": {"type": "string", "enum": ["wa", "lid", "tg"]},
      "token": {"type": "string"}
    }
  }
  ```

#### `sheet_register_partner`
- **Descripción**: Registra un cliente OCRL en la planilla de Google con cuenta + CUIT + identidad del canal informado (guarda SOLO el dato del canal: celular en telefono, lid en lid, username en telegram). Requiere credenciales de escritura
- **Visibilidad**: public
- **Tags**: ocrl, sheet, identity, write
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "account_code": {"type": "string"},
      "cuit": {"type": "string"},
      "channel": {"type": "string", "enum": ["wa", "lid", "tg"]},
      "token": {"type": "string"},
      "name": {"type": "string"},
      "telegram_username": {"type": "string"},
      "price_adjustment": {"type": "number"}
    },
    "required": ["account_code", "cuit"]
  }
  ```

## 6. Ejemplo de Uso

### 6.1 Listar herramientas (JSON-RPC)
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

### 6.2 Invocar herramienta (JSON-RPC)
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "read_file",
    "arguments": {
      "path": "/contenedores/conti-backend/docs/rules.md",
      "start_line": 1,
      "end_line": 20
    }


---

## 8. Compatibilidad de Clientes MCP

El servidor MCP de Conti Backend es compatible con los siguientes clientes:

| Cliente | Transporte | Notas |
|---------|------------|-------|
| **Hermes Agent** | HTTP | Cliente principal, soporte completo |
| **VS Code MCP URL** | HTTP | Integración con VS Code |
| **Amazon Q** | HTTP | Compatible con herramientas públicas |
| **Kilocode** | HTTP | Soporte completo |
| **Cline** | HTTP | Soporte completo |
| **legacy-backend-ai** | HTTP | Retrocompatibilidad |

### Configuración en Clientes

Para configurar el servidor MCP en clientes compatibles, use la URL base:
```
http://<host>:<port>/mcp
```

**Ejemplo para Hermes:**
```yaml
mcp_servers:
  contibackend:
    transport: http
    url: http://conti-backend:8000/mcp
    headers:
      Accept: application/json
```

**Ejemplo para VS Code:**
```json
{
  "mcpServers": {
    "conti-backend": {
      "url": "http://localhost:8000/mcp",
      "transport": "http"
    }
  }
}
```

## 9. Diagnóstico y Solución de Problemas

### Problemas Comunes

1. **Error "Session required"**: El servidor MCP de Odoo requiere sesiones. Use el endpoint `/mcp` de Conti Backend que maneja sesiones automáticamente.

2. **Timeout en consultas**: Algunas herramientas como `odoo_list_products` con `has_stock=true` pueden tardar. Use `include_stock=true` solo cuando sea necesario.

3. **Error de permisos**: Las herramientas de sistema de archivos respetan allowlists. Verifique que la ruta esté dentro de los roots permitidos.

4. **Error de conexión a Odoo**: Verifique que el perfil de conexión (`connection`) sea válido y que Odoo esté accesible.

### Logs y Depuración

Para depurar problemas con el servidor MCP:
1. Verifique el estado con `GET /health`
2. Revise la configuración con `GET /config`
3. Consulte los logs del contenedor con `docker logs <container_name>`

## 10. Versión y Cambios

- **Versión actual**: 0.1.0
- **Protocolo MCP**: 2024-11-05
- **Última actualización**: Documentación generada automáticamente

### Historial de Cambios Recientes

- Implementación de herramientas de RAG con búsqueda híbrida y semántica
- Soporte para documentos católicos (lecturas, biblia, resúmenes)
- Integración con Google Sheets para OCRL
- Herramientas de traducción de Markdown
- Soporte para conversión PDF a Markdown

---

**Documentación generada automáticamente el 4 de julio de 2026**