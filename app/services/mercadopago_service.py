from __future__ import annotations

import os
from typing import Any

import requests

from app.config.models import AppConfig
from app.services import odoo_invoice_service
from app.services.odoo_rpc import get_odoo_client


def odoo_create_mercadopago_preference(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = _required_int(arguments, "order_id")
    cuit_dni = _required_str(arguments, "cuit_dni")
    access_token = _mercadopago_access_token(config)

    client = get_odoo_client(config, arguments)
    orders = client.search_read(
        "sale.order",
        [("id", "=", order_id)],
        ["id", "name", "partner_id", "amount_total", "state", "order_line"],
        limit=1,
    )
    if not orders:
        raise ValueError(f"Pedido {order_id} no encontrado")

    order = orders[0]
    if order["state"] != "sale":
        raise ValueError(f'El pedido debe estar confirmado. Estado actual: {order["state"]}')

    partners = client.read("res.partner", [order["partner_id"][0]], ["vat", "name", "email"])
    if not partners or partners[0].get("vat") != cuit_dni:
        raise ValueError("El pedido no pertenece al cliente")
    partner = partners[0]

    lines_data = client.read(
        "sale.order.line",
        order.get("order_line", []),
        ["product_id", "name", "product_uom_qty", "price_unit"],
    )
    if not lines_data:
        raise ValueError("El pedido no tiene líneas de productos")

    preference_data = {
        "items": [
            {
                "id": str(line["product_id"][0]),
                "title": str(line["name"])[:256],
                "quantity": int(line["product_uom_qty"]),
                "unit_price": float(line["price_unit"]),
                "currency_id": "ARS",
            }
            for line in lines_data
        ],
        "payer": {
            "name": str(partner.get("name") or "Cliente")[:256],
            "email": partner.get("email") or "cliente@test.com",
            "identification": {
                "type": "CUIT" if len(cuit_dni) == 11 else "DNI",
                "number": cuit_dni,
            },
        },
        "back_urls": {
            "success": _mercadopago_url("MERCADOPAGO_SUCCESS_URL", config.mercadopago.success_url),
            "failure": _mercadopago_url("MERCADOPAGO_FAILURE_URL", config.mercadopago.failure_url),
            "pending": _mercadopago_url("MERCADOPAGO_PENDING_URL", config.mercadopago.pending_url),
        },
        "notification_url": _mercadopago_url("MERCADOPAGO_NOTIFICATION_URL", config.mercadopago.notification_url),
        "external_reference": str(order_id),
    }

    response = _mercadopago_request(
        config,
        "POST",
        "/checkout/preferences",
        access_token=access_token,
        json_payload=preference_data,
    )
    preference_id = response["id"]
    client.write("sale.order", [order_id], {"client_order_ref": preference_id})

    init_point = response["init_point"]
    if _mercadopago_is_sandbox(config):
        init_point = response.get("sandbox_init_point") or init_point.replace(
            "www.mercadopago.com.ar",
            "sandbox.mercadopago.com.ar",
        )

    return {
        "success": True,
        "preference_id": preference_id,
        "init_point": init_point,
        "sandbox_init_point": response.get("sandbox_init_point", init_point),
        "order_id": order_id,
        "amount": order["amount_total"],
        "is_sandbox": _mercadopago_is_sandbox(config),
    }


def process_mercadopago_webhook(
    config: AppConfig,
    payload: dict[str, Any],
    headers: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = payload or {}
    query = query_params or {}

    if data.get("type") == "test":
        return {"status": "test_ok", "message": "Webhook funcionando"}

    notification_type = data.get("type") or query.get("type") or query.get("topic")
    if notification_type != "payment":
        return {"status": "ok", "processed": False, "message": "Notificación ignorada"}

    payment_id = data.get("data", {}).get("id") or query.get("id") or query.get("data.id")
    if not payment_id:
        return {"status": "ok", "processed": False, "message": "Notificación sin payment_id"}

    access_token = _mercadopago_access_token(config)
    payment_info = _mercadopago_request(
        config,
        "GET",
        f"/v1/payments/{payment_id}",
        access_token=access_token,
    )

    external_reference = payment_info.get("external_reference")
    payment_status = payment_info.get("status")
    amount = float(payment_info.get("transaction_amount") or 0.0)
    method_name = payment_info.get("payment_method_id", "N/A")

    result: dict[str, Any] = {
        "status": "ok",
        "processed": True,
        "payment_id": str(payment_id),
        "payment_status": payment_status,
        "external_reference": external_reference,
    }
    if not external_reference:
        return result

    order_id = int(external_reference)
    client = get_odoo_client(config, arguments)
    client.post_message(
        model="sale.order",
        record_id=order_id,
        subject=f"Webhook MP - {payment_status}",
        body=(
            "<div><p><b>Webhook MercadoPago</b></p><ul>"
            f"<li><b>ID:</b> {payment_id}</li>"
            f"<li><b>Estado:</b> {payment_status}</li>"
            f"<li><b>Monto:</b> ${amount}</li>"
            f"<li><b>Método:</b> {method_name}</li>"
            "</ul></div>"
        ),
        partner_ids=[],
    )

    if payment_status == "approved":
        payment_result = odoo_invoice_service.odoo_register_payment(
            config,
            {
                **(arguments or {}),
                "order_id": order_id,
                "payment_id": str(payment_id),
                "amount": amount,
                "payment_method": f"MercadoPago - {method_name}",
            },
        )
        result["payment_registration"] = payment_result

    return result


def mercadopago_return_payload(status: str, query_params: dict[str, Any]) -> dict[str, Any]:
    success = status != "failure"
    messages = {
        "success": "Pago procesado",
        "failure": "Pago no procesado",
        "pending": "Pago pendiente",
    }
    return {
        "success": success,
        "message": messages[status],
        "collection_id": query_params.get("collection_id"),
        "status": query_params.get("collection_status") or status,
        "order_id": query_params.get("external_reference"),
        "preference_id": query_params.get("preference_id"),
    }


def _mercadopago_request(
    config: AppConfig,
    method: str,
    path: str,
    access_token: str,
    json_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = requests.request(
        method=method,
        url=f"{config.mercadopago.api_base_url.rstrip('/')}{path}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=json_payload,
        timeout=config.mercadopago.request_timeout_seconds,
    )
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"MercadoPago error {response.status_code}: {response.text}")
    return response.json()


def _mercadopago_access_token(config: AppConfig) -> str:
    access_token = os.getenv(config.mercadopago.access_token_env, "").strip()
    if not access_token:
        raise ValueError("Configuración de MercadoPago incompleta: access token ausente")
    return access_token


def _mercadopago_url(env_name: str, default_value: str) -> str:
    return os.getenv(env_name, "").strip() or default_value


def _mercadopago_is_sandbox(config: AppConfig) -> bool:
    raw = os.getenv(config.mercadopago.sandbox_env, "false").strip().lower()
    return raw in {"true", "1", "t", "yes"}


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
