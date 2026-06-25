from __future__ import annotations

from typing import Any

from app.config.models import AppConfig
from app.services.odoo_rpc import get_odoo_client


def odoo_create_order(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    client_id = _required_int(arguments, "client_id")
    client = get_odoo_client(config, arguments)
    order_id = client.create("sale.order", {"partner_id": client_id})
    return {"success": True, "order_id": order_id}


def odoo_create_cart(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    cuit_dni = _required_str(arguments, "cuit_dni")
    client = get_odoo_client(config, arguments)
    partners = client.search_read("res.partner", [("vat", "=", cuit_dni)], ["id"], limit=1)
    if not partners:
        raise ValueError(f"Cliente '{cuit_dni}' no encontrado")
    order_id = client.create("sale.order", {"partner_id": partners[0]["id"]})
    return {"success": True, "order_id": order_id}


def odoo_add_item_to_cart(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = _required_int(arguments, "order_id")
    product_id = _required_int(arguments, "product_id")
    quantity = _required_int(arguments, "quantity")
    if not 1 <= quantity <= 20:
        raise ValueError("La cantidad debe estar entre 1 y 20")

    client = get_odoo_client(config, arguments)
    products = client.search_read("product.product", [("id", "=", product_id)], ["id", "qty_available", "uom_id"], limit=1)
    if not products:
        raise ValueError(f"Producto ID '{product_id}' no encontrado")
    product = products[0]

    existing_line = client.search_read(
        "sale.order.line",
        [("order_id", "=", order_id), ("product_id", "=", product_id)],
        ["id", "product_uom_qty"],
        limit=1,
    )
    if existing_line:
        new_total_qty = float(existing_line[0].get("product_uom_qty", 0.0)) + quantity
        if new_total_qty > 20:
            raise ValueError("Límite por producto excedido")
        if float(product.get("qty_available", 0.0)) < new_total_qty:
            raise ValueError("Stock insuficiente")
        client.write("sale.order.line", [existing_line[0]["id"]], {"product_uom_qty": new_total_qty})
        return {
            "success": True,
            "quantity_added": quantity,
            "new_total_qty": new_total_qty,
            "action": "updated",
            "line_id": existing_line[0]["id"],
        }

    if float(product.get("qty_available", 0.0)) < quantity:
        raise ValueError("Stock insuficiente")
    line_data = {"order_id": order_id, "product_id": product_id, "product_uom_qty": quantity}
    if product.get("uom_id"):
        line_data["product_uom_id"] = product["uom_id"][0]
    line_id = client.create("sale.order.line", line_data)
    return {
        "success": True,
        "quantity_added": quantity,
        "new_total_qty": quantity,
        "action": "created",
        "line_id": line_id,
    }


def odoo_get_cart_summary(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = _required_int(arguments, "order_id")
    cuit_dni = _required_str(arguments, "cuit_dni")
    client = get_odoo_client(config, arguments)
    orders = client.read("sale.order", [order_id], ["id", "name", "partner_id", "order_line", "amount_total", "state"])
    if not orders:
        raise ValueError(f"Pedido ID {order_id} no encontrado")
    order = orders[0]

    if not order.get("partner_id"):
        raise ValueError("El pedido no tiene partner asociado")
    partners = client.read("res.partner", [order["partner_id"][0]], ["vat"])
    if not partners or partners[0].get("vat") != cuit_dni:
        raise ValueError("El pedido no pertenece al cliente indicado")

    lines_data = client.read(
        "sale.order.line",
        order.get("order_line", []),
        ["product_id", "name", "product_uom_qty", "price_subtotal"],
    ) if order.get("order_line") else []
    return {
        "success": True,
        "summary": {
            "order_id": order["id"],
            "order_name": order["name"],
            "state": order["state"],
            "total_amount": order["amount_total"],
            "lines": lines_data,
        },
    }


def odoo_confirm_cart(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = _required_int(arguments, "order_id")
    client = get_odoo_client(config, arguments)
    orders = client.search_read("sale.order", [("id", "=", order_id)], ["id", "state"], limit=1)
    if not orders:
        raise ValueError(f"Pedido ID {order_id} no encontrado")
    if orders[0]["state"] != "draft":
        raise ValueError("El pedido no está en borrador")

    client.execute_method("sale.order", "action_confirm", [[order_id]])
    confirmed = client.read("sale.order", [order_id], ["amount_untaxed", "amount_tax", "amount_total", "state"])[0]
    return {
        "success": True,
        "message": "Pedido confirmado.",
        "state": confirmed["state"],
        "amount_untaxed": confirmed["amount_untaxed"],
        "amount_tax": confirmed["amount_tax"],
        "amount_total": confirmed["amount_total"],
    }


def odoo_cancel_cart(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = _required_int(arguments, "order_id")
    client = get_odoo_client(config, arguments)
    orders = client.search_read("sale.order", [("id", "=", order_id)], ["id", "state"], limit=1)
    if not orders:
        raise ValueError(f"Pedido ID {order_id} no encontrado")
    if orders[0]["state"] in ["done", "cancel"]:
        raise ValueError("El pedido no se puede cancelar")

    client.execute_method("sale.order", "action_cancel", [[order_id]])
    cancelled = client.read("sale.order", [order_id], ["state"])[0]
    return {"success": True, "message": "Pedido cancelado.", "state": cancelled["state"]}


def _required_int(arguments: dict[str, Any], key: str) -> int:
    value = arguments.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Se requiere '{key}'")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{key}' debe ser entero") from exc


def _required_str(arguments: dict[str, Any], key: str) -> str:
    value = str(arguments.get(key) or "").strip()
    if not value:
        raise ValueError(f"Se requiere '{key}'")
    return value
