"""Tools MCP del backend para la Planilla de Google (Tier 2) — OCRL Mendoza.

Reglas de ruteo (ver Documentacion/odoo/ocrl_mendoza.md):
  - Si el código de cuenta empieza por el prefijo (CL) → SIEMPRE planilla.
  - Si Odoo no encontró al cliente → buscar TAMBIÉN en planilla.

Estas tools son Tier 2 (fallback de datos) y conviven con las odoo_* (Tier 3).
"""

from __future__ import annotations

from typing import Any

from app.config.models import AppConfig
from app.services import gsheet_client


def sheet_account_goes_to_sheet(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    """Indica si un código de cuenta debe resolverse en la planilla (prefijo CL*)."""
    code = str(arguments.get("account_code") or "").strip()
    prefix = config.ocrl_sheet.account_sheet_prefix
    goes = bool(code) and code.upper().startswith(prefix.upper())
    return {"account_code": code, "prefix": prefix, "use_sheet": goes}


def sheet_lookup_partner(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    """Busca un cliente en la planilla por cuenta, CUIT o identidad de chat."""
    account_code = str(arguments.get("account_code") or "").strip()
    cuit = str(arguments.get("cuit") or "").strip()
    channel = str(arguments.get("channel") or "").strip()
    token = str(arguments.get("token") or "").strip()

    partner = None
    if account_code:
        partner = gsheet_client.lookup_by_account(config, account_code)
    if not partner and cuit:
        partner = gsheet_client.lookup_by_cuit(config, cuit)
    if not partner and channel and token:
        partner = gsheet_client.lookup_by_chat(config, channel, token)

    return {"found": bool(partner), "partner": partner}


def sheet_register_partner(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    """Registra un cliente en la planilla (cuenta + CUIT + identidad de canal).

    Guarda SOLO el dato del canal informado: lid en columna lid, celular en
    telefono, username en telegram (una identidad por canal).
    """
    account_code = str(arguments.get("account_code") or "").strip()
    cuit = str(arguments.get("cuit") or "").strip()
    if not account_code or not cuit:
        raise ValueError("Se requieren 'account_code' y 'cuit'.")

    channel = str(arguments.get("channel") or "").strip()
    token = str(arguments.get("token") or "").strip()
    row: dict[str, Any] = {
        "numero_cuenta": account_code,
        "cuit": cuit,
        "nombre": str(arguments.get("name") or "").strip(),
        "telefono": "",
        "lid": "",
        "telegram": str(arguments.get("telegram_username") or "").strip(),
        "precio": arguments.get("price_adjustment", ""),
    }
    # Una identidad por canal: solo se completa la columna del canal informado.
    if channel == "wa":
        row["telefono"] = token
    elif channel == "lid":
        row["lid"] = token
    elif channel == "tg":
        row["telegram"] = row["telegram"] or token

    return gsheet_client.register_row(config, row)
