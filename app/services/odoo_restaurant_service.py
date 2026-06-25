from __future__ import annotations

import base64
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any

import requests

from app.config.models import AppConfig
from app.services.odoo_rpc import OdooRPCClient, get_odoo_client

logger = logging.getLogger("conti.odoo.restaurant")

# report_name del QWeb de la carta (NO el action). Se usa para renderizar el PDF
# vía el endpoint /report/pdf/<report_name>/<id> autenticado.
_REPORT_NAME = "restaurant_menu_report.menu_report_template"

# Nombre fijo del attachment cacheado de la carta por pos.config.
_CACHE_ATTACHMENT_NAME = "Carta_del_Restaurante.pdf"

# Tiempo de validez del PDF cacheado. Pasado este lapso se regenera.
_CACHE_TTL_HOURS = 12


def odoo_get_restaurant_menu(config: AppConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    """Devuelve la carta del restaurante como una URL de descarga pública.

    Estrategia (definitiva):
    1. Localiza el pos.config activo del restaurante.
    2. Reutiliza un ir.attachment público cacheado (con access_token) si existe y
       es reciente → respuesta instantánea.
    3. Si no hay cache válida, renderiza el PDF una sola vez, lo guarda como
       attachment público con access_token y devuelve la URL `/web/content/...`.

    La URL `/web/content/<id>?access_token=<token>` SÍ funciona sin login, a
    diferencia de `/report/pdf/<action>/<id>` que exige sesión Odoo iniciada.
    """
    tenant = _required_str(arguments, "tenant")
    include_pdf = bool(arguments.get("include_pdf_base64", False))
    force_refresh = bool(arguments.get("force_refresh", False))

    # La conexión y DB se resuelven con el mismo nombre que el tenant
    args_with_connection = dict(arguments)
    args_with_connection.setdefault("connection", tenant)
    args_with_connection.setdefault("db", tenant)

    client = get_odoo_client(config, args_with_connection)

    # Buscar el pos.config activo del restaurante
    domain: list[Any] = [("active", "=", True), ("module_pos_restaurant", "=", True)]
    pos_configs = client.search_read(
        "pos.config",
        domain,
        ["id", "name"],
        limit=1,
    )
    if not pos_configs:
        raise ValueError(f"No se encontró ningún pos.config activo con módulo restaurante en la conexión '{tenant}'")

    pos_config = pos_configs[0]
    pos_config_id = pos_config["id"]
    pos_config_name = pos_config["name"]

    base_url = f"https://{tenant}.contamela.com"

    # 1) Intentar reutilizar attachment cacheado
    attachment = None
    if not force_refresh:
        attachment = _find_cached_attachment(client, pos_config_id)

    # 2) Regenerar si no hay cache válida
    if attachment is None:
        attachment = _build_cached_attachment(
            client=client,
            base_url=base_url,
            db=args_with_connection["db"],
            username=client.connection.username,
            password=client.connection.password,
            pos_config_id=pos_config_id,
        )

    download_url = (
        f"{base_url}/web/content/{attachment['id']}"
        f"?access_token={attachment['access_token']}&download=true"
    )

    result: dict[str, Any] = {
        "success": True,
        "tenant": tenant,
        "pos_config_id": pos_config_id,
        "pos_config_name": pos_config_name,
        # Mantener report_url por compatibilidad con consumidores previos
        "report_url": download_url,
        "download_url": download_url,
        "download_link": f"[📄 Carta del Restaurante]({download_url})",
        "attachment_id": attachment["id"],
        "cached": attachment.get("from_cache", False),
    }

    if include_pdf and attachment.get("pdf_bytes") is not None:
        pdf_bytes = attachment["pdf_bytes"]
        result["pdf_base64"] = base64.b64encode(pdf_bytes).decode("utf-8")
        result["pdf_size_kb"] = round(len(pdf_bytes) / 1024, 2)

    return result


def _find_cached_attachment(client: OdooRPCClient, pos_config_id: int) -> dict[str, Any] | None:
    """Busca un attachment de carta reciente y con access_token. Devuelve None si no aplica."""
    records = client.search_read(
        "ir.attachment",
        [
            ("name", "=", _CACHE_ATTACHMENT_NAME),
            ("res_model", "=", "pos.config"),
            ("res_id", "=", pos_config_id),
        ],
        ["id", "access_token", "write_date"],
        limit=1,
        order="write_date desc",
    )
    if not records:
        return None

    rec = records[0]
    if not rec.get("access_token"):
        return None

    write_date = rec.get("write_date")
    if write_date:
        try:
            ts = datetime.strptime(write_date, "%Y-%m-%d %H:%M:%S")
            if datetime.utcnow() - ts > timedelta(hours=_CACHE_TTL_HOURS):
                return None
        except (ValueError, TypeError):
            pass

    return {"id": rec["id"], "access_token": rec["access_token"], "from_cache": True}


def _build_cached_attachment(
    client: OdooRPCClient,
    base_url: str,
    db: str,
    username: str,
    password: str,
    pos_config_id: int,
) -> dict[str, Any]:
    """Renderiza el PDF de la carta y lo guarda como attachment público con token."""
    pdf_bytes = _render_menu_pdf(
        base_url=base_url,
        db=db,
        username=username,
        password=password,
        pos_config_id=pos_config_id,
    )

    token = secrets.token_urlsafe(32)
    att_vals: dict[str, Any] = {
        "name": _CACHE_ATTACHMENT_NAME,
        "datas": base64.b64encode(pdf_bytes).decode("utf-8"),
        "mimetype": "application/pdf",
        "res_model": "pos.config",
        "res_id": pos_config_id,
        "access_token": token,
        "public": True,
    }

    # Reutilizar el registro existente (aunque esté vencido) para no acumular basura
    existing = client.search_read(
        "ir.attachment",
        [
            ("name", "=", _CACHE_ATTACHMENT_NAME),
            ("res_model", "=", "pos.config"),
            ("res_id", "=", pos_config_id),
        ],
        ["id"],
        limit=1,
    )
    if existing:
        att_id = existing[0]["id"]
        client.write("ir.attachment", [att_id], att_vals)
    else:
        att_id = client.create("ir.attachment", att_vals)

    return {
        "id": att_id,
        "access_token": token,
        "from_cache": False,
        "pdf_bytes": pdf_bytes,
    }


def _render_menu_pdf(
    base_url: str,
    db: str,
    username: str,
    password: str,
    pos_config_id: int,
) -> bytes:
    """Renderiza el PDF de la carta vía el endpoint /report/pdf autenticado."""
    report_url = f"{base_url}/report/pdf/{_REPORT_NAME}/{pos_config_id}"
    session = requests.Session()

    auth_resp = session.post(
        f"{base_url}/web/session/authenticate",
        json={
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"db": db, "login": username, "password": password},
        },
        timeout=30,
    )
    auth_resp.raise_for_status()
    auth_data = auth_resp.json()
    if auth_data.get("error") or not auth_data.get("result", {}).get("uid"):
        raise ValueError(f"Autenticación HTTP fallida en {base_url}: {auth_data.get('error')}")

    # La primera generación compila los assets QWeb/wkhtmltopdf (~85s); luego ~3s.
    pdf_resp = session.get(report_url, timeout=180)
    pdf_resp.raise_for_status()

    if "application/pdf" not in pdf_resp.headers.get("Content-Type", ""):
        raise ValueError(
            f"La respuesta no es un PDF. Content-Type: {pdf_resp.headers.get('Content-Type')}"
        )

    return pdf_resp.content


def _required_str(arguments: dict[str, Any], key: str) -> str:
    value = str(arguments.get(key) or "").strip()
    if not value:
        raise ValueError(f"Se requiere '{key}'")
    return value
