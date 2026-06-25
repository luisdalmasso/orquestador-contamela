from __future__ import annotations

from typing import Any

from app.config.models import AppConfig
from app.services.odoo_rpc import get_odoo_client


def odoo_search_clients(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    cuit_dni = str(arguments.get("cuit_dni") or "").strip()
    name = str(arguments.get("name") or "").strip()
    if not cuit_dni and not name:
        raise ValueError("Se requiere 'cuit_dni' o 'name' para buscar clientes")
    return _query_clients(config, arguments, cuit_dni=cuit_dni, name=name)


def odoo_list_clients(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    return _query_clients(
        config,
        arguments,
        cuit_dni=str(arguments.get("cuit_dni") or "").strip(),
        name=str(arguments.get("name") or "").strip(),
    )


def odoo_create_client(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    name = str(arguments.get("name") or "").strip()
    cuit_dni = str(arguments.get("cuit_dni") or "").strip()
    email = str(arguments.get("email") or "").strip() or None
    phone = str(arguments.get("phone") or "").strip() or None
    if not name or not cuit_dni:
        raise ValueError("Se requieren 'name' y 'cuit_dni'")

    client = get_odoo_client(config, arguments)
    client_id = client.create(
        "res.partner",
        {
            "name": name,
            "vat": cuit_dni,
            "email": email,
            "phone": phone,
            "company_type": "person",
            "customer_rank": 1,
        },
    )
    return {
        "success": True,
        "client_id": client_id,
        "data": {
            "name": name,
            "cuit_dni": cuit_dni,
            "email": email,
            "phone": phone,
        },
    }


def _query_clients(config: AppConfig, arguments: dict[str, Any], cuit_dni: str, name: str) -> dict[str, Any]:
    limit = _bounded_int(arguments.get("limit", 50), default=50, minimum=1, maximum=500)
    offset = _bounded_int(arguments.get("offset", 0), default=0, minimum=0, maximum=100000)
    domain = _build_client_domain(cuit_dni, name)

    client = get_odoo_client(config, arguments)
    clients = client.search_read("res.partner", domain, ["id", "name", "vat", "email", "phone"], limit=limit, offset=offset)
    normalized = [_normalize_client(item) for item in clients]

    return {
        "success": True,
        "found": bool(normalized),
        "message": "No se encontraron clientes." if not normalized else None,
        "clients": normalized,
        "pagination": {"limit": limit, "offset": offset, "count": len(normalized)},
    }


def _build_client_domain(cuit_dni: str, name: str) -> list[Any]:
    if cuit_dni and name:
        return ["|", "|", ("vat", "=", cuit_dni), ("name", "ilike", cuit_dni), ("name", "ilike", name)]
    if cuit_dni:
        return ["|", ("vat", "=", cuit_dni), ("name", "ilike", cuit_dni)]
    if name:
        return [("name", "ilike", name)]
    return []


def _normalize_client(client: dict[str, Any]) -> dict[str, Any]:
    normalized = client.copy()
    if "vat" in normalized:
        normalized["cuit_dni"] = normalized.pop("vat")
    return normalized


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))
