from __future__ import annotations

from functools import lru_cache

from app.config.loader import load_config
from app.core import categories, visibility
from app.core.tool_models import ToolDefinition
from app.core.tool_registry import ToolRegistry
from app.tools import (
    catolico_tools,
    code_edit_tools,
    config_tools,
    container_tools,
    document_tools,
    filesystem,
    git_tools,
    odoo_tools,
    ponytail_trace_tools,
    rag_search_tools,
    rag_tools,
    search_literal,
    sheet_tools,
    sourcebot_tools,
    system_status,
    translation_tools,
)


class RegistryService:
    def __init__(self) -> None:
        self._registry = ToolRegistry()
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._registry.register(
            ToolDefinition(
                name="list_files",
                description="Lista archivos y directorios bajo un root permitido.",
                category="filesystem",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
                visibility=visibility.PUBLIC,
                tags=["filesystem", "read-only"],
            ),
            lambda args: filesystem.list_files(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="read_file",
                description="Lee un archivo dentro de los roots permitidos.",
                category="filesystem",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                    },
                    "required": ["path"],
                },
                visibility=visibility.PUBLIC,
                tags=["filesystem", "read-only"],
            ),
            lambda args: filesystem.read_file(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="file_exists",
                description="Informa si un path permitido existe.",
                category="filesystem",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
                visibility=visibility.PUBLIC,
                tags=["filesystem", "read-only"],
            ),
            lambda args: filesystem.file_exists(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_code_context",
                description="Devuelve contexto alrededor de una línea de un archivo permitido.",
                category="filesystem",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "line": {"type": "integer"},
                        "context": {"type": "integer"},
                    },
                    "required": ["path"],
                },
                visibility=visibility.PUBLIC,
                tags=["filesystem", "code"],
            ),
            lambda args: filesystem.get_code_context(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="search_code_literal",
                description="Busca texto literal o regex dentro del repo de desarrollo.",
                category="filesystem",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["search", "code"],
            ),
            lambda args: search_literal.search_code_literal(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="search_docs_literal",
                description="Busca texto literal o regex dentro de la documentación del backend.",
                category="filesystem",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["search", "docs"],
            ),
            lambda args: search_literal.search_docs_literal(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="grep_workspace",
                description="Busca coincidencias dentro del workspace permitido.",
                category="filesystem",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["search", "workspace"],
            ),
            lambda args: search_literal.grep_workspace(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="health_check",
                description="Devuelve el estado actual del backend.",
                category="bootstrap",
                input_schema={"type": "object", "properties": {}},
                visibility=visibility.PUBLIC,
                tags=["system"],
            ),
            system_status.health_check,
        )
        self._registry.register(
            ToolDefinition(
                name="get_config",
                description="Devuelve la configuración efectiva redactada.",
                category="bootstrap",
                input_schema={"type": "object", "properties": {}},
                visibility=visibility.PUBLIC,
                tags=["config"],
            ),
            config_tools.get_config,
        )
        self._registry.register(
            ToolDefinition(
                name="reload_config",
                description="Recarga la configuración del backend.",
                category="bootstrap",
                input_schema={"type": "object", "properties": {}},
                visibility=visibility.INTERNAL,
                tags=["config"],
            ),
            system_status.reload_backend_config,
        )
        self._registry.register(
            ToolDefinition(
                name="get_onboarding",
                description="Devuelve el onboarding efectivo del backend.",
                category="bootstrap",
                input_schema={
                    "type": "object",
                    "properties": {"brief": {"type": "boolean"}},
                },
                visibility=visibility.PUBLIC,
                tags=["config", "onboarding"],
            ),
            config_tools.get_onboarding,
        )
        self._registry.register(
            ToolDefinition(
                name="get_rules",
                description="Devuelve las reglas efectivas del backend.",
                category="bootstrap",
                input_schema={"type": "object", "properties": {}},
                visibility=visibility.PUBLIC,
                tags=["config", "rules"],
            ),
            config_tools.get_rules,
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_test_connection",
                description="Prueba la conexión configurada contra Odoo y valida autenticación y acceso básico a productos.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {
                            "type": "string",
                            "description": "Perfil Odoo configurado, por ejemplo prod o dev.",
                        },
                        "db": {"type": "string"},
                        "url": {"type": "string"},
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "health", "read-only"],
            ),
            lambda args: odoo_tools.odoo_test_connection(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_list_products",
                description="Lista productos de Odoo con filtros de búsqueda, categoría, stock y rango de precios. Por rendimiento, el stock (qty_available) NO se incluye por defecto: pasar has_stock=true o include_stock=true para obtenerlo.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "search": {"type": "string"},
                        "producto": {"type": "string"},
                        "category_ids": {
                            "type": "string",
                            "description": "IDs separados por coma.",
                        },
                        "has_stock": {
                            "type": "boolean",
                            "description": "Filtra solo productos con stock > 0 (incluye qty_available). Computar stock es lento.",
                        },
                        "include_stock": {
                            "type": "boolean",
                            "description": "Incluye qty_available en la respuesta sin filtrar. Úsalo solo si necesitas stock; es costoso.",
                        },
                        "price_min": {"type": "number"},
                        "price_max": {"type": "number"},
                        "limit": {"type": "integer"},
                        "offset": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "products", "catalog", "read-only"],
            ),
            lambda args: odoo_tools.odoo_list_products(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_get_product_detail",
                description="Obtiene el detalle completo de un producto puntual desde Odoo.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "product_id": {"type": "integer"},
                    },
                    "required": ["product_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "products", "read-only"],
            ),
            lambda args: odoo_tools.odoo_get_product_detail(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_get_ai_context",
                description="Devuelve contexto comercial y de cliente desde Odoo para uso por agentes o asistentes.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "cuit_dni": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "context", "ai", "read-only"],
            ),
            lambda args: odoo_tools.odoo_get_ai_context(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_search_clients",
                description="Busca clientes en Odoo por CUIT/DNI o nombre y devuelve coincidencias normalizadas.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "cuit_dni": {"type": "string"},
                        "name": {"type": "string"},
                        "limit": {"type": "integer"},
                        "offset": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "clients", "read-only"],
            ),
            lambda args: odoo_tools.odoo_search_clients(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_list_clients",
                description="Lista clientes de Odoo con paginación y filtros opcionales por nombre o CUIT/DNI.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "cuit_dni": {"type": "string"},
                        "name": {"type": "string"},
                        "limit": {"type": "integer"},
                        "offset": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "clients", "read-only"],
            ),
            lambda args: odoo_tools.odoo_list_clients(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_create_client",
                description="Crea un cliente en Odoo con nombre, CUIT/DNI y datos de contacto básicos.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "name": {"type": "string"},
                        "cuit_dni": {"type": "string"},
                        "email": {"type": "string"},
                        "phone": {"type": "string"},
                    },
                    "required": ["name", "cuit_dni"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "clients", "write"],
            ),
            lambda args: odoo_tools.odoo_create_client(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_create_order",
                description="Crea un pedido de venta draft en Odoo para un cliente existente.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "client_id": {"type": "integer"},
                    },
                    "required": ["client_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "sales", "write"],
            ),
            lambda args: odoo_tools.odoo_create_order(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_create_cart",
                description="Busca un cliente por CUIT/DNI y crea un carrito/pedido draft asociado.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "cuit_dni": {"type": "string"},
                    },
                    "required": ["cuit_dni"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "sales", "cart", "write"],
            ),
            lambda args: odoo_tools.odoo_create_cart(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_add_item_to_cart",
                description="Agrega un producto a un carrito/pedido draft validando stock y límites por producto.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "order_id": {"type": "integer"},
                        "product_id": {"type": "integer"},
                        "quantity": {"type": "integer"},
                    },
                    "required": ["order_id", "product_id", "quantity"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "sales", "cart", "write"],
            ),
            lambda args: odoo_tools.odoo_add_item_to_cart(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_get_cart_summary",
                description="Devuelve el resumen de un carrito/pedido y valida que pertenezca al cliente indicado.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "order_id": {"type": "integer"},
                        "cuit_dni": {"type": "string"},
                    },
                    "required": ["order_id", "cuit_dni"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "sales", "cart", "read-only"],
            ),
            lambda args: odoo_tools.odoo_get_cart_summary(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_confirm_cart",
                description="Confirma un pedido draft y devuelve los totales resultantes en Odoo.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "order_id": {"type": "integer"},
                    },
                    "required": ["order_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "sales", "cart", "write"],
            ),
            lambda args: odoo_tools.odoo_confirm_cart(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_cancel_cart",
                description="Cancela un pedido siempre que no esté ya finalizado o cancelado.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "order_id": {"type": "integer"},
                    },
                    "required": ["order_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "sales", "cart", "write"],
            ),
            lambda args: odoo_tools.odoo_cancel_cart(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_create_invoice",
                description="Crea y publica una factura desde un pedido confirmado, validando titularidad del cliente.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "order_id": {"type": "integer"},
                        "cuit_dni": {"type": "string"},
                    },
                    "required": ["order_id", "cuit_dni"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "invoice", "write"],
            ),
            lambda args: odoo_tools.odoo_create_invoice(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_register_payment",
                description="Registra un pago sobre la factura publicada de un pedido y deja trazabilidad en el chatter.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "order_id": {"type": "integer"},
                        "payment_id": {"type": "string"},
                        "amount": {"type": "number"},
                        "payment_method": {"type": "string"},
                    },
                    "required": ["order_id", "payment_id", "amount"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "invoice", "payment", "write"],
            ),
            lambda args: odoo_tools.odoo_register_payment(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_upload_payment_proof",
                description="Adjunta un comprobante PDF a un pedido de venta y ejecuta OCR opcional.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "order_id": {"type": "integer"},
                        "cuit_dni": {"type": "string"},
                        "filename": {"type": "string"},
                        "file_path": {"type": "string"},
                        "file_base64": {"type": "string"},
                        "run_ocr": {"type": "boolean"},
                    },
                    "required": ["order_id", "cuit_dni"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "attachments", "payment-proof", "write"],
            ),
            lambda args: odoo_tools.odoo_upload_payment_proof(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_process_attachment_ocr",
                description="Procesa OCR o extracción de texto sobre un adjunto PDF existente en Odoo.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "attachment_id": {"type": "integer"},
                        "order_id": {"type": "integer"},
                    },
                    "required": ["attachment_id", "order_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "attachments", "ocr", "write"],
            ),
            lambda args: odoo_tools.odoo_process_attachment_ocr(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_process_pdf_document",
                description="Procesa un PDF general y devuelve texto extraído, imágenes embebidas y estadísticas.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "file_path": {"type": "string"},
                        "file_base64": {"type": "string"},
                        "include_images_data": {"type": "boolean"},
                        "max_images": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "pdf", "document", "read-only"],
            ),
            lambda args: odoo_tools.odoo_process_pdf_document(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_create_mercadopago_preference",
                description="Crea una preferencia de pago de MercadoPago para un pedido confirmado en Odoo.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "order_id": {"type": "integer"},
                        "cuit_dni": {"type": "string"},
                    },
                    "required": ["order_id", "cuit_dni"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "mercadopago", "payment", "write"],
            ),
            lambda args: odoo_tools.odoo_create_mercadopago_preference(
                load_config(), args
            ),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_get_invoice_status",
                description="Consulta el estado de facturación y cobranza de un pedido en Odoo.",
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "db": {"type": "string"},
                        "order_id": {"type": "integer"},
                        "cuit_dni": {"type": "string"},
                    },
                    "required": ["order_id", "cuit_dni"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "invoice", "read-only"],
            ),
            lambda args: odoo_tools.odoo_get_invoice_status(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="odoo_get_restaurant_menu",
                description=(
                    "Devuelve la carta del restaurante como una URL de descarga pública DIRECTA "
                    "(/web/content/<id>?access_token=...) que abre el PDF sin login. "
                    "El PDF se cachea: la primera vez puede tardar, las siguientes son instantáneas. "
                    "Usa SIEMPRE esta herramienta cuando pidan ver/mostrar/descargar la carta o el menú. "
                    "Devuelve 'download_url' y 'download_link' (Markdown listo para enviar al usuario). "
                    "Requiere 'tenant' (ej: 'resto')."
                ),
                category="odoo",
                input_schema={
                    "type": "object",
                    "properties": {
                        "tenant": {
                            "type": "string",
                            "description": "Nombre del tenant, ej: resto. Se usa como perfil de conexión, DB y para armar la URL https://{tenant}.contamela.com",
                        },
                        "include_pdf_base64": {
                            "type": "boolean",
                            "description": "Si true, descarga el PDF y lo devuelve en base64. Default false.",
                        },
                        "force_refresh": {
                            "type": "boolean",
                            "description": "Si true, regenera el PDF aunque exista una versión cacheada. Úsalo solo si la carta cambió y la versión cacheada está desactualizada. Default false.",
                        },
                    },
                    "required": ["tenant"],
                },
                visibility=visibility.PUBLIC,
                tags=["odoo", "restaurant", "menu", "pdf", "read-only"],
            ),
            lambda args: odoo_tools.odoo_get_restaurant_menu(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_git_status",
                description="Devuelve el estado Git local del repo de desarrollo.",
                category="gitops",
                input_schema={
                    "type": "object",
                    "properties": {"repo_path": {"type": "string"}},
                },
                visibility=visibility.PUBLIC,
                tags=["git", "read-only"],
            ),
            lambda args: git_tools.get_git_status(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_git_log",
                description="Devuelve el historial reciente del repo Git local.",
                category="gitops",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string"},
                        "n": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "read-only"],
            ),
            lambda args: git_tools.get_git_log(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="diff_with_develop",
                description="Compara el HEAD local contra develop remoto o local configurado.",
                category="gitops",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string"},
                        "remote": {"type": "string"},
                        "develop_branch": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "diff"],
            ),
            lambda args: git_tools.diff_with_develop(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_pipeline_summary",
                description="Resume el pipeline Git local: rama, estado, remotos y diff contra develop.",
                category="gitops",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string"},
                        "remote": {"type": "string"},
                        "develop_branch": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "pipeline", "read-only"],
            ),
            lambda args: git_tools.get_pipeline_summary(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_container_health",
                description="Resume estado y salud de contenedores Docker accesibles desde el backend.",
                category="stack",
                input_schema={
                    "type": "object",
                    "properties": {
                        "env": {
                            "type": "string",
                            "enum": ["local", "dev", "prod", "all"],
                        },
                        "container": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["docker", "containers", "read-only"],
            ),
            lambda args: container_tools.get_container_health(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_container_logs",
                description="Lee logs de un contenedor Docker local con filtros por tiempo, nivel y cantidad de líneas.",
                category="stack",
                input_schema={
                    "type": "object",
                    "properties": {
                        "container": {"type": "string"},
                        "lines": {"type": "integer"},
                        "since": {"type": "string"},
                        "level": {
                            "type": "string",
                            "enum": ["all", "error", "warning"],
                        },
                    },
                    "required": ["container"],
                },
                visibility=visibility.PUBLIC,
                tags=["docker", "logs", "read-only"],
            ),
            lambda args: container_tools.get_container_logs(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_vps_status",
                description="Da una vista consolidada del estado Docker local y del repo Git principal montado.",
                category="stack",
                input_schema={
                    "type": "object",
                    "properties": {
                        "env": {
                            "type": "string",
                            "enum": ["local", "dev", "prod", "all"],
                        },
                        "repo_path": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["docker", "git", "status", "read-only"],
            ),
            lambda args: container_tools.get_vps_status(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="run_salvar",
                description="Hace preview o ejecuta commit+push local. Por default target=develop; pasar force_branch='main' para commit directo en main (ej: circuito backend, hotfix).",
                category="gitops",
                input_schema={
                    "type": "object",
                    "properties": {
                        "confirm": {"type": "boolean"},
                        "summary": {"type": "string"},
                        "repo_path": {"type": "string"},
                        "remote": {"type": "string"},
                        "develop_branch": {"type": "string"},
                        "main_branch": {"type": "string"},
                        "force_branch": {
                            "type": "string",
                            "description": "Override del branch destino. 'main' para hotfix/circuito backend.",
                        },
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "write"],
            ),
            lambda args: git_tools.run_salvar(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="run_promover",
                description="Hace preview o ejecuta merge local develop -> main con push.",
                category="gitops",
                input_schema={
                    "type": "object",
                    "properties": {
                        "confirm": {"type": "boolean"},
                        "summary": {"type": "string"},
                        "repo_path": {"type": "string"},
                        "remote": {"type": "string"},
                        "develop_branch": {"type": "string"},
                        "main_branch": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "write", "promote"],
            ),
            lambda args: git_tools.run_promover(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="run_hotfix_sync",
                description="Sincroniza hotfix main→develop: pushea commits nuevos en /compose (main) y los mergea --no-ff en /desarrollo (develop). Usar tras editar /compose directamente. Requiere /compose limpio en main y /desarrollo limpio en develop.",
                category="gitops",
                input_schema={
                    "type": "object",
                    "properties": {
                        "confirm": {"type": "boolean"},
                        "summary": {"type": "string"},
                        "repo_path": {"type": "string"},
                        "remote": {"type": "string"},
                        "develop_branch": {"type": "string"},
                        "main_branch": {"type": "string"},
                        "compose_repo_path": {
                            "type": "string",
                            "description": "Override del path del repo origen (/compose por default).",
                        },
                        "desarrollo_repo_path": {
                            "type": "string",
                            "description": "Override del path del repo destino (/desarrollo por default).",
                        },
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "write", "hotfix", "sync"],
            ),
            lambda args: git_tools.run_hotfix_sync(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="start_markdown_translation",
                description="Inicia traducción de Markdown en background y devuelve job_id para seguimiento.",
                category="documents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "input_path": {"type": "string"},
                        "output_path": {"type": "string"},
                        "source_lang": {"type": "string"},
                        "target_lang": {"type": "string"},
                        "chunk_size": {"type": "integer"},
                        "retries": {"type": "integer"},
                        "overwrite": {"type": "boolean"},
                    },
                    "required": ["input_path"],
                },
                visibility=visibility.PUBLIC,
                tags=["translation", "background", "markdown"],
            ),
            lambda args: translation_tools.start_markdown_translation(
                load_config(), args
            ),
        )
        self._registry.register(
            ToolDefinition(
                name="get_translation_job",
                description="Consulta estado y progreso de un job de traducción.",
                category="documents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                    },
                    "required": ["job_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["translation", "status", "read-only"],
            ),
            lambda args: translation_tools.get_translation_job(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="list_translation_jobs",
                description="Lista jobs recientes de traducción y su estado.",
                category="documents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["translation", "status", "read-only"],
            ),
            lambda args: translation_tools.list_translation_jobs(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="start_pdf_to_markdown",
                description="Convierte un PDF (URL o ruta local) a Markdown en background y devuelve job_id. Si no se pasa output_path, guarda por defecto en /compose/documentos_listos/{store}/. Opcionalmente inicia traducción automática al terminar.",
                category="documents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "URL o ruta local al PDF/documento",
                        },
                        "store": {
                            "type": "string",
                            "description": "Store destino para output por defecto (default: config.rag.default_store)",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Ruta de salida del .md (opcional)",
                        },
                        "also_translate": {
                            "type": "boolean",
                            "description": "Si es true lanza traducción al terminar",
                        },
                        "target_lang": {
                            "type": "string",
                            "description": "Idioma destino si also_translate=true (default: en)",
                        },
                    },
                    "required": ["source"],
                },
                visibility=visibility.PUBLIC,
                tags=["document", "pdf", "markdown", "background"],
            ),
            lambda args: document_tools.start_pdf_to_markdown(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_md_conversion_job",
                description="Consulta estado de un job de conversión PDF/documento a Markdown.",
                category="documents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                    },
                    "required": ["job_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["document", "status", "read-only"],
            ),
            lambda args: document_tools.get_md_conversion_job(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="list_md_conversion_jobs",
                description="Lista jobs recientes de conversión PDF/documento a Markdown.",
                category="documents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["document", "status", "read-only"],
            ),
            lambda args: document_tools.list_md_conversion_jobs(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="start_rag_ingest",
                description=(
                    "Ingesta un documento (URL o ruta local) en el RAG Flamehaven. "
                    "Convierte a Markdown preservando el nombre original y lo sube a una colección (store). "
                    "Devuelve job_id inmediatamente; el proceso ocurre en background."
                ),
                category="rag",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "URL o ruta local al documento (PDF, DOCX, etc.)",
                        },
                        "store": {
                            "type": "string",
                            "description": "Colección destino en Flamehaven (default: config rag.default_store)",
                        },
                        "original_name": {
                            "type": "string",
                            "description": "Nombre descriptivo para identificar el doc en el índice",
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Si true y ya existe un doc con el mismo nombre, lo reemplaza. Si false (default) rechaza el duplicado informando el doc existente.",
                        },
                    },
                    "required": ["source"],
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "document", "ingest", "background"],
            ),
            lambda args: rag_tools.start_rag_ingest(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_rag_ingest_job",
                description="Consulta estado de un job de ingestión RAG en Flamehaven.",
                category="rag",
                input_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                    },
                    "required": ["job_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "status", "read-only"],
            ),
            lambda args: rag_tools.get_rag_ingest_job(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="list_rag_ingest_jobs",
                description="Lista jobs recientes de ingestión RAG en Flamehaven.",
                category="rag",
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "status", "read-only"],
            ),
            lambda args: rag_tools.list_rag_ingest_jobs(load_config(), args),
        )

        # ── Sourcebot (búsqueda de código en los 3 repos) ───────────
        # Sourcebot v5.0.4 indexa /desarrollo, /compose y
        # /contenedores/conti-backend (ver docker-compose.conti.yml).
        # A diferencia de las tools RAG (Flamehaven, documentos con LLM),
        # las Sourcebot tools son grep-semántico puro de código: snippets
        # con path + número de línea. Útiles para que el agent omp
        # busque patrones, funciones o símbolos en la codebase DURANTE
        # su trabajo (no solo pre-agent como _sourcebot_search en
        # service.py).
        self._registry.register(
            ToolDefinition(
                name="sourcebot_search",
                description=(
                    "Busca código en los 3 repos bind-mounted (/desarrollo, "
                    "/compose, /contenedores/conti-backend) usando el índice "
                    "de Sourcebot v5.0.4. Devuelve snippets con path absoluto "
                    "y número de línea. Usar cuando el agent necesita "
                    "ENCONTRAR un patrón, función o símbolo en la codebase "
                    "DURANTE su trabajo (no pre-agent). A diferencia de "
                    "search_rag (Flamehaven, RAG de documentos), Sourcebot "
                    "es búsqueda de código puro, sin LLM en el path."
                ),
                category="sourcebot",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Término o frase a buscar (búsqueda híbrida BM25+semántica)",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "Máximo de resultados (default 10)",
                        },
                        "repos": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filtrar por repos (default: todos los indexados)",
                        },
                    },
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["sourcebot", "code-search", "grep", "read-only"],
            ),
            lambda args: sourcebot_tools.sourcebot_search(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="sourcebot_list_repos",
                description=(
                    "Lista los repos que Sourcebot tiene indexados. Útil para "
                    "confirmar que el cwd actual del agent está scrapeado antes "
                    "de hacer sourcebot_search."
                ),
                category="sourcebot",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
                visibility=visibility.PUBLIC,
                tags=["sourcebot", "metadata", "read-only"],
            ),
            lambda args: sourcebot_tools.sourcebot_list_repos(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="sourcebot_get_doc",
                description=(
                    "Devuelve el contenido completo de un archivo indexado "
                    "por Sourcebot, por path absoluto (ej: /desarrollo/README.md). "
                    "Usar cuando sourcebot_search devuelve un path interesante "
                    "y se quiere ver el archivo entero."
                ),
                category="sourcebot",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path absoluto del archivo (ej: /desarrollo/app/main.py)",
                        },
                    },
                    "required": ["path"],
                },
                visibility=visibility.PUBLIC,
                tags=["sourcebot", "code-search", "read", "read-only"],
            ),
            lambda args: sourcebot_tools.sourcebot_get_doc(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="scan_documentos_nuevos",
                description=(
                    "Escanea /compose/documentos_nuevos/{store}/ y lanza un job de ingesta por cada archivo. "
                    "Los archivos se mueven a procesados/ al ser encolados. "
                    "Opcionalmente puede incluir archivos ya movidos en procesados/. "
                    "Usa store='all' para escanear todos los stores. "
                    "Usa dry_run=true para previsualizar sin ingestar. "
                    "Usa max_files para limitar cuántos archivos encola por request. "
                    "overwrite=false (default): rechaza documentos con nombre ya existente en el store. "
                    "overwrite=true: reemplaza el doc anterior."
                ),
                category="rag",
                input_schema={
                    "type": "object",
                    "properties": {
                        "store": {
                            "type": "string",
                            "description": "Store a escanear, o 'all' para todos (default: config.rag.default_store)",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Solo listar archivos sin ingestar",
                        },
                        "max_files": {
                            "type": "integer",
                            "description": "Límite de archivos por llamada para evitar timeout (ej: 25, 50, 100).",
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Si true reemplaza docs existentes con el mismo nombre. Default: false.",
                        },
                        "include_procesados": {
                            "type": "boolean",
                            "description": "Si true incluye tambien documentos_nuevos/{store}/procesados para auditoria o reingesta.",
                        },
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "ingest", "scan"],
            ),
            lambda args: rag_tools.scan_documentos_nuevos(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="search_rag",
                description=(
                    "Búsqueda completa en el RAG Flamehaven con respuesta generada por LLM (Gemini). "
                    "Soporta modos: hybrid (recomendado, fusiona BM25+semántico), semantic, keyword. "
                    "Usar cuando Conti necesita RESPONDER algo al usuario basándose en documentos. "
                    "Devuelve answer, sources, search_confidence [0-1] y low_confidence si los resultados son débiles."
                ),
                category="rag",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Pregunta o consulta a buscar",
                        },
                        "store": {
                            "type": "string",
                            "description": "Colección destino (default: config rag.default_store)",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["hybrid", "semantic", "keyword"],
                            "description": "Modo de búsqueda (default: hybrid)",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Número de resultados (default: 5)",
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Umbral de similitud [0-1]",
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "Máx tokens para la respuesta LLM",
                        },
                    },
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "search", "hybrid", "llm"],
            ),
            lambda args: rag_search_tools.search_rag(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="search_rag_quick",
                description=(
                    "Búsqueda rápida por keyword en Flamehaven SIN generar respuesta LLM. Solo devuelve sources y matched. "
                    "Usar cuando Conti necesita VERIFICAR si algo existe en el RAG o encadenar con otra tool. "
                    "No consume tokens de Gemini — instantáneo."
                ),
                category="rag",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Término o frase a buscar",
                        },
                        "store": {
                            "type": "string",
                            "description": "Colección destino (default: config rag.default_store)",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Número de resultados (default: 5)",
                        },
                    },
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "search", "keyword", "read-only"],
            ),
            lambda args: rag_search_tools.search_rag_quick(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="search_rag_semantic",
                description=(
                    "Búsqueda semántica en Flamehaven (DSP v2.0) con respuesta LLM. "
                    "Sin BM25 — usa únicamente vectores: ideal para queries conceptuales, sinónimos y paráfrasis. "
                    "Tolerante a typos. Usar cuando las palabras exactas no importan sino el concepto."
                ),
                category="rag",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Concepto o pregunta a buscar semánticamente",
                        },
                        "store": {
                            "type": "string",
                            "description": "Colección destino (default: config rag.default_store)",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Número de resultados (default: 5)",
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Umbral de similitud [0-1]",
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "Máx tokens para la respuesta LLM",
                        },
                    },
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "search", "semantic", "llm"],
            ),
            lambda args: rag_search_tools.search_rag_semantic(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="list_rag_store_docs",
                description=(
                    "Lista todos los documentos indexados en un store de Flamehaven. Sin búsqueda ni LLM. "
                    "Usar cuando Conti necesita saber QUÉ documentos hay guardados en el RAG (inventario). "
                    "Devuelve title, URI y metadata de cada doc."
                ),
                category="rag",
                input_schema={
                    "type": "object",
                    "properties": {
                        "store": {
                            "type": "string",
                            "description": "Colección a listar (default: config rag.default_store)",
                        },
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "status", "read-only"],
            ),
            lambda args: rag_search_tools.list_rag_store_docs(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="catolico_lecturas_dia",
                description="Obtiene las lecturas del día para la liturgia católica.",
                category="catolico",
                input_schema={
                    "type": "object",
                    "properties": {
                        "fecha": {
                            "type": "string",
                            "description": "Fecha de la cual extraer las lecturas (por defecto 'hoy')",
                        },
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["catolico", "api"],
            ),
            lambda args: catolico_tools.catolico_lecturas_dia(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="catolico_biblia_buscar",
                description="Busca citas bíblicas o versículos por palabras clave. Úsala EXCLUSIVAMENTE para referencias bíblicas.",
                category="catolico",
                input_schema={
                    "type": "object",
                    "properties": {
                        "modo": {
                            "type": "string",
                            "description": "Define si se busca una 'cita' específica o una 'busqueda' por texto.",
                        },
                        "libro": {
                            "type": "string",
                            "description": "Nombre del libro bíblico (ej: Mateo)",
                        },
                        "capitulo": {
                            "type": "number",
                            "description": "Número del capítulo. Requerido si modo='cita'",
                        },
                        "versiculo_inicio": {"type": "number"},
                        "versiculo_fin": {"type": "number"},
                        "texto": {
                            "type": "string",
                            "description": "Texto o frase a buscar. Requerido si modo='busqueda'",
                        },
                    },
                    "required": ["modo"],
                },
                visibility=visibility.PUBLIC,
                tags=["catolico", "biblia"],
            ),
            lambda args: catolico_tools.catolico_biblia_buscar(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="catolico_listar_titulos",
                description=(
                    "Lista todos los títulos y nombres de archivo de documentos ingestados "
                    "en el store católico del RAG. Lee el front-matter YAML de cada .md. "
                    "Usar para validar si un documento existe antes de resumirlo, "
                    "o para mostrar el catálogo de documentos disponibles al usuario."
                ),
                category="catolico",
                input_schema={
                    "type": "object",
                    "properties": {
                        "store": {
                            "type": "string",
                            "description": "Nombre del store RAG. Default: 'catolico'",
                            "default": "catolico",
                        }
                    },
                    "required": [],
                },
                visibility=visibility.PUBLIC,
                tags=["catolico", "rag", "titulos", "catalogo"],
            ),
            lambda args: catolico_tools.catolico_listar_titulos(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="catolico_leer_documento",
                description=(
                    "Lee el contenido completo de un documento del RAG católico. "
                    "Úsala si el usuario pide un resumen o leer un documento. "
                    "Dos modos: (1) por 'uri' exacta que devolvió search_rag — resuelve automáticamente el path real; "
                    "(2) por 'query' de búsqueda cuando no tenés URI o los resultados de search_rag fueron dudosos/múltiples — "
                    "busca internamente y devuelve el mejor documento. "
                    "Preferí el modo 'query' cuando la búsqueda devolvió más de 1 resultado o el título no coincide exactamente."
                ),
                category="catolico",
                input_schema={
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "URI exacta del documento (formato local://catolico/...) tal como la devuelve search_rag. Opcional si usás query.",
                        },
                        "query": {
                            "type": "string",
                            "description": "Texto de búsqueda para encontrar el documento. Usar cuando no tenés URI exacta o los resultados previos fueron dudosos.",
                        },
                        "store": {
                            "type": "string",
                            "description": "Nombre del store RAG. Default: 'catolico'",
                            "default": "catolico",
                        },
                    },
                    "required": [],
                },
                visibility=visibility.PUBLIC,
                tags=["catolico", "rag", "resumen"],
            ),
            lambda args: catolico_tools.catolico_leer_documento(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="catolico_resumir_documento",
                description=(
                    "Genera un resumen estructurado de un documento católico usando SpineDigest. "
                    "Pipeline de 3 etapas: chunking → grafo de conocimiento → defensa multi-agente. "
                    "Cachea el resultado para evitar re-procesar. "
                    "Usar cuando el usuario pide 'resumir', 'resumen de' o 'síntesis de' un documento."
                ),
                category="catolico",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Nombre o título del documento a resumir.",
                        },
                        "store": {
                            "type": "string",
                            "description": "Nombre del store. Default: 'catolico'",
                            "default": "catolico",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Instrucción de extracción para SpineDigest. Opcional.",
                        },
                    },
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["catolico", "rag", "resumen", "spinedigest"],
            ),
            lambda args: catolico_tools.catolico_resumir_documento(load_config(), args),
        )
        # --- OCRL Mendoza: Planilla de Google (Tier 2) ---
        self._registry.register(
            ToolDefinition(
                name="sheet_account_goes_to_sheet",
                description=(
                    "Indica si un codigo de cuenta OCRL debe resolverse en la "
                    "planilla de Google (prefijo CL*). Usar ANTES de buscar en "
                    "Odoo: si use_sheet=true, ir directo a sheet_lookup_partner."
                ),
                category="sheets",
                input_schema={
                    "type": "object",
                    "properties": {"account_code": {"type": "string"}},
                    "required": ["account_code"],
                },
                visibility=visibility.PUBLIC,
                tags=["ocrl", "sheet", "identity", "read-only"],
            ),
            lambda args: sheet_tools.sheet_account_goes_to_sheet(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="sheet_lookup_partner",
                description=(
                    "Busca un cliente OCRL en la planilla de Google por codigo "
                    "de cuenta, CUIT o identidad de chat (channel wa/lid/tg + "
                    "token). Fallback Tier 2: usar para cuentas CL* o cuando el "
                    "cliente NO se encontro en Odoo. Devuelve price_adjustment y "
                    "line_discount (=-price_adjustment)."
                ),
                category="sheets",
                input_schema={
                    "type": "object",
                    "properties": {
                        "account_code": {"type": "string"},
                        "cuit": {"type": "string"},
                        "channel": {"type": "string", "enum": ["wa", "lid", "tg"]},
                        "token": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["ocrl", "sheet", "identity", "read-only"],
            ),
            lambda args: sheet_tools.sheet_lookup_partner(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="sheet_register_partner",
                description=(
                    "Registra un cliente OCRL en la planilla de Google con "
                    "cuenta + CUIT + identidad del canal informado (guarda SOLO "
                    "el dato del canal: celular en telefono, lid en lid, username "
                    "en telegram). Requiere credenciales de escritura."
                ),
                category="sheets",
                input_schema={
                    "type": "object",
                    "properties": {
                        "account_code": {"type": "string"},
                        "cuit": {"type": "string"},
                        "channel": {"type": "string", "enum": ["wa", "lid", "tg"]},
                        "token": {"type": "string"},
                        "name": {"type": "string"},
                        "telegram_username": {"type": "string"},
                        "price_adjustment": {"type": "number"},
                    },
                    "required": ["account_code", "cuit"],
                },
                visibility=visibility.PUBLIC,
                tags=["ocrl", "sheet", "identity", "write"],
            ),
            lambda args: sheet_tools.sheet_register_partner(load_config(), args),
        )
        # ── CODE_EDIT tools (nuevas, Sprint 1.5 PLAN_3) ──────────────
        self._registry.register(
            ToolDefinition(
                name="validate_python_syntax",
                description="Valida la sintaxis Python de uno o más archivos vía ast.parse. No ejecuta el archivo. Usar antes de run_salvar en el circuito backend para evitar commits con syntax errors.",
                category="code_edit",
                input_schema={
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lista de paths absolutos a archivos .py",
                        }
                    },
                    "required": ["paths"],
                },
                visibility=visibility.PUBLIC,
                tags=["code-edit", "validation", "syntax", "pre-commit"],
            ),
            lambda args: code_edit_tools.validate_python_syntax(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="run_pytest",
                description="Corre pytest en el directorio del circuito activo (backend/desarrollo/etc). Usar tras editar código para validar antes de commitear.",
                category="code_edit",
                input_schema={
                    "type": "object",
                    "properties": {
                        "circuit": {
                            "type": "string",
                            "enum": ["desarrollo", "produccion", "backend", "libre"],
                            "description": "id del circuito. Si se omite, se detecta del cwd.",
                        },
                        "test_path": {
                            "type": "string",
                            "description": "Path específico (ej: 'tests/test_git_tools.py'). Default: toda la suite.",
                        },
                        "timeout": {"type": "integer", "default": 300},
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Argumentos extra para pytest",
                        },
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["code-edit", "tests", "validation"],
            ),
            lambda args: code_edit_tools.run_pytest(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="detect_circuit_from_path",
                description="Dado un path absoluto (o relativo a workspaces conocidos), devuelve qué circuito corresponde. Útil cuando el agente está en 'libre' y necesita saber a qué circuito mandar una edición.",
                category="code_edit",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path absoluto o relativo",
                        },
                    },
                    "required": ["path"],
                },
                visibility=visibility.PUBLIC,
                tags=["code-edit", "routing", "circuit-detection"],
            ),
            lambda args: code_edit_tools.detect_circuit_from_path(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="cross_repo_search",
                description="Busca un término en los 3 repos bind-mounted (/desarrollo, /compose, /contenedores/conti-backend) usando git grep en vivo. Complementa search_rag (Sourcebot) cuando el índice está desactualizado.",
                category="code_edit",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "include_globs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": ["*.py"],
                        },
                        "exclude_globs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "max_results": {"type": "integer", "default": 50},
                        "repos": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["desarrollo", "produccion", "backend"],
                            },
                            "description": "Subset de repos a buscar. Default: los 3.",
                        },
                    },
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["code-edit", "search", "codevibing", "cross-repo"],
            ),
            lambda args: code_edit_tools.cross_repo_search(load_config(), args),
        )

        # ── ponytail_record_trace (observability, Docs-as-Code) ────────
        # PLAN_3 §15.quinquies: persiste trace a .ponytail/traces/<id>.md
        # con formato Hybrid (YAML frontmatter + GFM body + mermaid). Hace
        # commit async al repo local (no push) en background thread.
        # Lock por circuit (no paralelismo intra-circuit).
        self._registry.register(
            ToolDefinition(
                name="ponytail_record_trace",
                description=(
                    "Persiste un trace de observabilidad a .ponytail/traces/<id>.md "
                    "con formato Hybrid (YAML Frontmatter + GitHub-Flavored Markdown + "
                    "mermaid sequenceDiagram). El __exit__ del PonytailTrace context "
                    "manager llama esta tool al final de cada request, con todos los "
                    "datos acumulados (prompt, response, tool_calls, sourcebot_hits, "
                    "events). Commit async al repo local con retry. NO push."
                ),
                category="observability",
                input_schema={
                    "type": "object",
                    "properties": {
                        "trace_id": {
                            "type": "string",
                            "description": "UUID del trace (generado por service.py).",
                        },
                        "circuit": {
                            "type": "string",
                            "description": "Id del circuit (desarrollo, produccion, etc).",
                        },
                        "markdown": {
                            "type": "string",
                            "description": "Cuerpo Markdown completo (YAML frontmatter + GFM body).",
                        },
                        "auto_commit": {
                            "type": "boolean",
                            "default": True,
                            "description": "Si true, hace git add + commit (no push) en background thread.",
                        },
                    },
                    "required": ["trace_id", "circuit", "markdown"],
                },
                visibility=visibility.PUBLIC,
                tags=["ponytail", "tracing", "observability", "docs-as-code", "git"],
            ),
            lambda args: ponytail_trace_tools.ponytail_record_trace(
                load_config(), args
            ),
        )

    def list_tools(self):
        return self._registry.list_tools()

    def call(self, tool_name: str, arguments: dict | None = None):
        return self._registry.call(tool_name, arguments)


@lru_cache(maxsize=1)
def registry_service() -> RegistryService:
    return RegistryService()
