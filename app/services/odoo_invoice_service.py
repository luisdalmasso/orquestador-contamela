from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config.models import AppConfig
from app.services.odoo_rpc import get_odoo_client


def odoo_create_invoice(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = _required_int(arguments, "order_id")
    cuit_dni = _required_str(arguments, "cuit_dni")

    client = get_odoo_client(config, arguments)
    order = _get_order(client, order_id)
    _ensure_order_belongs_to_client(client, order, cuit_dni)

    if order["state"] != "sale":
        raise ValueError(f'El pedido debe estar confirmado. Estado actual: {order["state"]}')

    existing_invoice = _find_invoice_for_order(client, order["name"])
    if order["invoice_status"] == "invoiced" and existing_invoice:
        return {
            "success": True,
            "message": "Factura ya existe",
            **_serialize_invoice(existing_invoice),
        }

    wizard_id = client.create(
        "sale.advance.payment.inv",
        {
            "advance_payment_method": "delivered",
            "sale_order_ids": [[6, 0, [order["id"]]]],
        },
        context={"active_model": "sale.order", "active_ids": [order["id"]]},
    )

    try:
        client.execute_method(
            "sale.advance.payment.inv",
            "create_invoices",
            [[wizard_id]],
            context={"active_model": "sale.order", "active_ids": [order["id"]]},
        )
    except Exception as exc:
        if "cannot marshal None" not in str(exc):
            raise

    invoice = _find_invoice_for_order(client, order["name"])
    if not invoice:
        raise RuntimeError("Factura creada pero no encontrada.")

    invoice = _ensure_invoice_posted(client, invoice["id"])
    return {
        "success": True,
        "message": "Factura creada y confirmada",
        **_serialize_invoice(invoice),
    }


def odoo_register_payment(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = _required_int(arguments, "order_id")
    payment_id = _required_str(arguments, "payment_id")
    payment_method = str(arguments.get("payment_method") or "mercadopago").strip() or "mercadopago"
    amount = _required_amount(arguments, "amount")

    client = get_odoo_client(config, arguments)
    order = _get_order(client, order_id)
    invoice = _find_posted_invoice_for_order(client, order["name"])
    if not invoice:
        raise ValueError(f'No se encontró factura confirmada para el pedido {order["name"]}')

    if invoice["payment_state"] in {"paid", "in_payment"}:
        return {
            "success": True,
            "message": "La factura ya está pagada",
            "invoice_id": invoice["id"],
            "payment_state": invoice["payment_state"],
        }

    journal = _find_payment_journal(client, payment_method)
    invoice_lines = client.search_read(
        "account.move.line",
        [("move_id", "=", invoice["id"]), ("account_type", "in", ["asset_receivable", "liability_payable"])],
        ["id"],
        limit=1,
    )
    if not invoice_lines:
        invoice_lines = client.search_read(
            "account.move.line",
            [("move_id", "=", invoice["id"]), ("display_type", "=", False)],
            ["id"],
            limit=1,
        )

    wizard_values = {
        "journal_id": journal["id"],
        "amount": amount,
        "payment_date": datetime.now().strftime("%Y-%m-%d"),
        "communication": f"{order['name']} (MP ID: {payment_id})",
    }
    if invoice_lines:
        wizard_values["line_ids"] = [[6, 0, [invoice_lines[0]["id"]]]]

    context = {"active_model": "account.move", "active_ids": [invoice["id"]]}
    wizard_id = client.create("account.payment.register", wizard_values, context=context)
    client.execute_method("account.payment.register", "action_create_payments", [[wizard_id]], context=context)

    updated_invoice = client.read("account.move", [invoice["id"]], ["payment_state", "amount_residual"])[0]
    message_body = (
        "<div><p><b>Pago API</b></p><ul>"
        f"<li>Método: {payment_method}</li>"
        f"<li>Ref: {payment_id}</li>"
        f"<li>Monto: ${amount}</li>"
        f"<li>Diario: {journal['name']}</li>"
        "</ul></div>"
    )
    client.post_message(
        model="account.move",
        record_id=invoice["id"],
        subject=f"Pago Registrado - {payment_method}",
        body=message_body,
        partner_ids=[],
    )

    return {
        "success": True,
        "message": "Pago registrado",
        "invoice_id": invoice["id"],
        "payment_state": updated_invoice["payment_state"],
        "amount_residual": updated_invoice["amount_residual"],
        "amount_paid": amount,
    }


def odoo_get_invoice_status(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = _required_int(arguments, "order_id")
    cuit_dni = _required_str(arguments, "cuit_dni")

    client = get_odoo_client(config, arguments)
    order = _get_order(client, order_id)
    _ensure_order_belongs_to_client(client, order, cuit_dni)

    invoice = _find_invoice_for_order(client, order["name"])
    response = {
        "success": True,
        "order_id": order["id"],
        "order_name": order["name"],
        "order_state": order["state"],
        "invoice_status": order["invoice_status"],
        "order_amount": order["amount_total"],
    }
    if invoice:
        response.update(
            {
                "has_invoice": True,
                **_serialize_invoice(invoice),
                "is_paid": invoice["payment_state"] == "paid",
            }
        )
    else:
        response.update({"has_invoice": False, "message": "Factura no creada aún"})
    return response


def _get_order(client: Any, order_id: int) -> dict[str, Any]:
    orders = client.search_read(
        "sale.order",
        [("id", "=", order_id)],
        ["id", "name", "partner_id", "state", "invoice_status", "amount_total"],
        limit=1,
    )
    if not orders:
        raise ValueError(f"Pedido no encontrado: {order_id}")
    return orders[0]


def _ensure_order_belongs_to_client(client: Any, order: dict[str, Any], cuit_dni: str) -> None:
    partner = client.read("res.partner", [order["partner_id"][0]], ["vat"])
    if not partner or partner[0].get("vat") != cuit_dni:
        raise ValueError("El pedido no pertenece al cliente indicado")


def _find_invoice_for_order(client: Any, order_name: str) -> dict[str, Any] | None:
    invoices = client.search_read(
        "account.move",
        [("invoice_origin", "=", order_name), ("move_type", "=", "out_invoice")],
        ["id", "name", "amount_total", "state", "payment_state", "amount_residual"],
        limit=1,
        order="id desc",
    )
    return invoices[0] if invoices else None


def _find_posted_invoice_for_order(client: Any, order_name: str) -> dict[str, Any] | None:
    invoices = client.search_read(
        "account.move",
        [("invoice_origin", "=", order_name), ("move_type", "=", "out_invoice"), ("state", "=", "posted")],
        ["id", "payment_state"],
        limit=1,
        order="id desc",
    )
    return invoices[0] if invoices else None


def _ensure_invoice_posted(client: Any, invoice_id: int) -> dict[str, Any]:
    invoice = client.read(
        "account.move",
        [invoice_id],
        ["id", "name", "amount_total", "state", "payment_state", "amount_residual", "l10n_latam_document_type_id"],
    )[0]
    if invoice["state"] != "draft":
        return invoice

    if not invoice.get("l10n_latam_document_type_id"):
        doc_types = client.search_read(
            "l10n_latam.document.type",
            [("internal_type", "=", "invoice"), ("country_id.code", "=", "AR")],
            ["id", "name"],
            limit=1,
            order="sequence asc",
        )
        if not doc_types:
            doc_types = client.search_read(
                "l10n_latam.document.type",
                [("internal_type", "=", "invoice")],
                ["id", "name"],
                limit=1,
                order="sequence asc",
            )
        if doc_types:
            client.write("account.move", [invoice_id], {"l10n_latam_document_type_id": doc_types[0]["id"]})

    client.execute_method("account.move", "action_post", [[invoice_id]])
    return client.read("account.move", [invoice_id], ["id", "name", "amount_total", "state", "payment_state", "amount_residual"])[0]


def _find_payment_journal(client: Any, payment_method: str) -> dict[str, Any]:
    journal_domain: list[Any] = [("type", "in", ["bank", "cash"])]
    if payment_method:
        journal_domain.append(("name", "ilike", payment_method))
    journals = client.search_read("account.journal", journal_domain, ["id", "name"], limit=1)
    if not journals:
        journals = client.search_read("account.journal", [("type", "in", ["bank", "cash"])], ["id", "name"], limit=1)
    if not journals:
        raise RuntimeError("No se encontró diario de pagos")
    return journals[0]


def _serialize_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    return {
        "invoice_id": invoice["id"],
        "invoice_name": invoice.get("name"),
        "invoice_amount": invoice["amount_total"],
        "invoice_state": invoice["state"],
        "payment_state": invoice["payment_state"],
        "amount_residual": invoice["amount_residual"],
    }


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


def _required_amount(arguments: dict[str, Any], key: str) -> float:
    value = arguments.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Se requiere '{key}'")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{key}' debe ser numérico") from exc
