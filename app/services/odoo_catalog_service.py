from __future__ import annotations

from typing import Any

from app.config.models import AppConfig
from app.services.odoo_rpc import get_odoo_client


def odoo_test_connection(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    client = get_odoo_client(config, arguments)
    products = client.search_read("product.product", [("active", "=", True)], ["id", "name"], limit=1)
    return {
        "success": True,
        "connection": client.connection.name,
        "odoo_url": client.connection.url,
        "odoo_db": client.connection.db,
        "odoo_user": client.uid,
        "products_found": len(products),
    }


def odoo_list_products(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    search = str(arguments.get("search") or arguments.get("producto") or "").strip()
    category_ids_raw = str(arguments.get("category_ids") or "").strip()
    has_stock = _as_bool(arguments.get("has_stock", False))
    # `qty_available` es un campo COMPUTADO de stock: calcularlo sobre todo el
    # catálogo es muy lento (puede agotar el timeout de 120 s del MCP). Por eso
    # solo se incluye cuando el cliente lo pide explícitamente (has_stock o
    # include_stock) o filtra por stock disponible.
    include_stock = has_stock or _as_bool(arguments.get("include_stock", False))
    price_min = arguments.get("price_min")
    price_max = arguments.get("price_max")
    limit = _bounded_int(arguments.get("limit", 50), default=50, minimum=1, maximum=500)
    offset = _bounded_int(arguments.get("offset", 0), default=0, minimum=0, maximum=100000)

    domain: list[Any] = [("sale_ok", "=", True), ("active", "=", True)]
    if search:
        for term in search.split():
            terms = [term]
            if term.endswith("es") and len(term) > 4:
                terms.append(term[:-2])
            elif term.endswith("s") and len(term) > 3:
                terms.append(term[:-1])

            if len(terms) > 1:
                domain.append("|")
                domain.extend(["|", ("name", "ilike", terms[0]), ("default_code", "ilike", terms[0])])
                domain.extend(["|", ("name", "ilike", terms[1]), ("default_code", "ilike", terms[1])])
            else:
                domain.extend(["|", ("name", "ilike", term), ("default_code", "ilike", term)])

    category_ids = _parse_int_list(category_ids_raw)
    if category_ids:
        domain.append(("categ_id", "in", category_ids))
    if has_stock:
        domain.append(("qty_available", ">", 0))
    if price_min is not None and str(price_min).strip():
        domain.append(("list_price", ">=", float(price_min)))
    if price_max is not None and str(price_max).strip():
        domain.append(("list_price", "<=", float(price_max)))

    client = get_odoo_client(config, arguments)
    fields = ["id", "name", "default_code", "list_price", "categ_id", "description_sale"]
    if include_stock:
        fields.append("qty_available")
    products = client.search_read("product.template", domain, fields, limit=limit, offset=offset)
    total_products = client.search_count("product.template", domain)
    normalized = [_rename_id_product(product) for product in products]

    return {
        "success": True,
        "total": total_products,
        "products": normalized,
        "stock_included": include_stock,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(products)) < total_products,
        },
    }


def odoo_get_product_detail(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    product_id = _required_int(arguments, "product_id")
    client = get_odoo_client(config, arguments)
    products = client.search_read(
        "product.product",
        [("id", "=", product_id)],
        [
            "id",
            "name",
            "default_code",
            "barcode",
            "list_price",
            "standard_price",
            "qty_available",
            "virtual_available",
            "categ_id",
            "uom_id",
            "description",
            "description_sale",
            "weight",
            "volume",
            "active",
            "sale_ok",
            "purchase_ok",
        ],
        limit=1,
    )
    if not products:
        raise ValueError(f"Producto no encontrado: {product_id}")
    return {
        "success": True,
        "product": _rename_id_product(products[0]),
    }


def odoo_get_ai_context(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    cuit_dni = str(arguments.get("cuit_dni") or "").strip()
    client = get_odoo_client(config, arguments)
    user_context: dict[str, Any] = {}

    if cuit_dni:
        clients = client.search_read("res.partner", [("vat", "=", cuit_dni)], ["id", "name", "vat", "email", "phone"], limit=1)
        if clients:
            client_info = clients[0]
            partner_id = int(client_info["id"])
            user_context["client_info"] = client_info
            user_context["purchase_stats"] = _build_purchase_stats(client, partner_id)
        else:
            user_context["client_info"] = {
                "status": "not_found",
                "cuit_dni": cuit_dni,
                "message": "Cliente no encontrado en Odoo.",
            }
    else:
        user_context["client_info"] = {
            "status": "no_cuit_dni_provided",
            "message": "No se proporcionó CUIT/DNI para el contexto del cliente.",
        }

    top_products = client.search_read(
        "product.product",
        [("sale_ok", "=", True)],
        ["id", "name", "list_price", "qty_available"],
        limit=10,
        order="list_price DESC",
    )
    categories = client.search_read("product.category", [], ["id", "name", "parent_id"], limit=20)
    inventory_stats = client.search_read(
        "product.product",
        [("type", "in", ["product", "consu"])],
        ["qty_available", "virtual_available", "list_price"],
        limit=1000,
    )

    total_products = len(inventory_stats)
    products_with_stock = len([item for item in inventory_stats if item.get("qty_available", 0) > 0])
    total_stock_value = sum(
        item.get("qty_available", 0) * item.get("list_price", 0)
        for item in inventory_stats
        if item.get("qty_available", 0) > 0
    )
    positive_prices = [product.get("list_price", 0) for product in top_products if product.get("list_price", 0) > 0]

    return {
        "success": True,
        "user_context": user_context,
        "product_context": {
            "total_products": total_products,
            "products_with_stock": products_with_stock,
            "total_stock_value": total_stock_value,
            "top_products": top_products[:5],
            "categories": categories[:10],
        },
        "business_context": {
            "available_categories": [category["name"] for category in categories[:10]],
            "price_ranges": {
                "min": min(positive_prices or [0]),
                "max": max([product.get("list_price", 0) for product in top_products] or [0]),
            },
            "inventory_status": "Buen nivel de stock" if total_products and products_with_stock > total_products * 0.5 else "Stock bajo",
        },
    }


def _build_purchase_stats(client, partner_id: int) -> dict[str, Any]:
    purchase_stats: dict[str, Any] = {
        "last_purchase_date": None,
        "average_purchase_amount": 0,
        "average_units_per_order": 0,
        "total_orders": 0,
        "pending_api_orders": [],
        "pending_api_orders_process_payment": [],
    }
    historical_orders = client.search_read(
        "sale.order",
        [("partner_id", "=", partner_id), ("state", "in", ["sale", "done"])],
        ["date_order", "amount_total", "order_line"],
        order="date_order DESC",
    )
    if historical_orders:
        purchase_stats["last_purchase_date"] = historical_orders[0]["date_order"]
        historical_orders_count = len(historical_orders)
        total_amount = sum(order.get("amount_total", 0) for order in historical_orders)
        purchase_stats["average_purchase_amount"] = round(total_amount / historical_orders_count, 2) if historical_orders_count else 0
        line_ids = [line_id for order in historical_orders for line_id in order.get("order_line", [])]
        if line_ids:
            lines_data = client.read("sale.order.line", line_ids, ["product_uom_qty"])
            total_units = sum(line.get("product_uom_qty", 0) for line in lines_data)
            if total_units > 0:
                purchase_stats["average_units_per_order"] = round(total_units / historical_orders_count, 2)

    all_pending_orders = client.search_read(
        "sale.order",
        [("partner_id", "=", partner_id), ("state", "=", "sale"), ("invoice_status", "in", ["to invoice", "no"])],
        ["id", "name", "amount_total", "date_order"],
        limit=10,
        order="date_order DESC",
    )
    pending_api_orders: list[dict[str, Any]] = []
    pending_process_payment: list[dict[str, Any]] = []
    for order in all_pending_orders:
        attachments_count = client.search_count(
            "ir.attachment",
            [
                ("res_model", "=", "sale.order"),
                ("res_id", "=", order["id"]),
                "|",
                ("name", "ilike", "comprobante"),
                ("name", "ilike", "=document.pdf"),
            ],
        )
        if attachments_count == 0:
            if order.get("amount_total", 0) > 0:
                pending_api_orders.append(order)
        else:
            pending_process_payment.append(order)

    purchase_stats["pending_api_orders"] = pending_api_orders[:5]
    purchase_stats["pending_api_orders_process_payment"] = pending_process_payment[:5]
    purchase_stats["total_orders"] = len(pending_api_orders)

    pending_quotes = client.search_read(
        "sale.order",
        [("partner_id", "=", partner_id), ("state", "=", "draft"), ("state", "!=", "cancel")],
        ["id", "name", "amount_total", "date_order"],
        limit=1,
        order="date_order DESC",
    )
    purchase_stats["pending_carry"] = pending_quotes[0] if pending_quotes and pending_quotes[0].get("amount_total", 0) > 0 else None
    return purchase_stats


def _rename_id_product(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = payload.copy()
    if "id" in normalized:
        normalized["id_product"] = normalized.pop("id")
    return normalized


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "t", "yes", "y"}


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _parse_int_list(raw: str) -> list[int]:
    if not raw:
        return []
    return [int(item.strip()) for item in raw.split(",") if item.strip().isdigit()]


def _required_int(arguments: dict[str, Any], key: str) -> int:
    value = arguments.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Se requiere '{key}'")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{key}' debe ser entero") from exc
