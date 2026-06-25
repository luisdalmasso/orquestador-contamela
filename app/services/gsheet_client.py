"""Cliente de la Planilla de Google (Tier 2) para identificación OCRL.

Lectura: export CSV público (no requiere credenciales).
Escritura: API Sheets v4 con service account (env OCRL_SHEET_CREDENTIALS_JSON).

Columnas esperadas (encabezados normalizados a snake_case, acentos removidos):
    numero_cuenta, cuit, nombre, apellido, telefono, lid, telegram, precio

Ver Documentacion/odoo/ocrl_mendoza.md.
"""

from __future__ import annotations

import csv
import io
import json
import os
import unicodedata
from typing import Any
from urllib.request import Request, urlopen

from app.config.models import AppConfig, OcrlSheetConfig

# Mapeo de alias de encabezados → nombre canónico.
_HEADER_ALIASES = {
    "numero_cuenta": "numero_cuenta",
    "numero_de_cuenta": "numero_cuenta",
    "nro_cuenta": "numero_cuenta",
    "cuenta": "numero_cuenta",
    "codigo": "numero_cuenta",
    "codigo_cuenta": "numero_cuenta",
    "cuit": "cuit",
    "cuit_dni": "cuit",
    "dni": "cuit",
    "nombre": "nombre",
    "apellido": "apellido",
    "correo_electronico": "email",
    "email": "email",
    "telefono": "telefono",
    "tel": "telefono",
    "celular": "telefono",
    "cel": "telefono",
    "lid": "lid",
    "telegram": "telegram",
    "telegran": "telegram",
    "telegram_username": "telegram",
    "usuario_telegram": "telegram",
    "ciudad": "ciudad",
    "pais": "pais",
    "precio": "precio",
    "precios": "precio",
    "ajuste": "precio",
    "ajuste_precio": "precio",
}


def _norm_header(raw: str) -> str:
    txt = unicodedata.normalize("NFKD", str(raw or "")).encode("ascii", "ignore").decode()
    txt = txt.strip().lower().replace(" ", "_").replace("-", "_")
    while "__" in txt:
        txt = txt.replace("__", "_")
    return _HEADER_ALIASES.get(txt, txt)


def _norm_digits(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _to_float(value: Any) -> float:
    raw = str(value or "").strip().replace("%", "").replace(",", ".")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _read_csv(cfg: OcrlSheetConfig) -> list[dict[str, str]]:
    req = Request(cfg.csv_url, headers={"User-Agent": "contamela-ocrl/1.0"})
    with urlopen(req, timeout=cfg.request_timeout_seconds) as resp:
        data = resp.read().decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(data))
    rows = list(reader)
    if not rows:
        return []
    headers = [_norm_header(h) for h in rows[0]]
    out: list[dict[str, str]] = []
    for raw in rows[1:]:
        if not any(c.strip() for c in raw):
            continue
        out.append({headers[i]: (raw[i] if i < len(raw) else "") for i in range(len(headers))})
    return out


def _row_to_partner(row: dict[str, str]) -> dict[str, Any]:
    nombre = " ".join(p for p in [row.get("nombre", ""), row.get("apellido", "")] if p).strip()
    return {
        "source": "sheet",
        "account_code": (row.get("numero_cuenta") or "").strip(),
        "cuit": (row.get("cuit") or "").strip(),
        "name": nombre or None,
        "phone": (row.get("telefono") or "").strip() or None,
        "lid": (row.get("lid") or "").strip() or None,
        "telegram_username": (row.get("telegram") or "").strip() or None,
        "price_adjustment": _to_float(row.get("precio")),
        # discount por línea = -price_adjustment (misma regla que Tier 1)
        "line_discount": -_to_float(row.get("precio")),
    }


# ----------------------------------------------------------------------
# Lookups
# ----------------------------------------------------------------------

def lookup_by_account(config: AppConfig, account_code: str) -> dict[str, Any] | None:
    target = (account_code or "").strip().lower()
    if not target:
        return None
    for row in _read_csv(config.ocrl_sheet):
        if (row.get("numero_cuenta") or "").strip().lower() == target:
            return _row_to_partner(row)
    return None


def lookup_by_cuit(config: AppConfig, cuit: str) -> dict[str, Any] | None:
    target = _norm_digits(cuit)
    if not target:
        return None
    for row in _read_csv(config.ocrl_sheet):
        if _norm_digits(row.get("cuit")) == target:
            return _row_to_partner(row)
    return None


def lookup_by_chat(config: AppConfig, channel: str, token: str) -> dict[str, Any] | None:
    raw = str(token or "").strip()
    if ":" in raw and raw.split(":", 1)[0] in ("wa", "lid", "tg"):
        raw = raw.split(":", 1)[1].strip()
    if not raw:
        return None
    for row in _read_csv(config.ocrl_sheet):
        if channel == "lid" and (row.get("lid") or "").strip() == raw:
            return _row_to_partner(row)
        if channel == "wa" and _norm_digits(row.get("telefono")) == _norm_digits(raw):
            return _row_to_partner(row)
        if channel == "tg":
            tg = (row.get("telegram") or "").strip().lstrip("@").lower()
            if tg and tg == raw.lstrip("@").lower():
                return _row_to_partner(row)
    return None


# ----------------------------------------------------------------------
# Escritura (API Sheets v4 con service account)
# ----------------------------------------------------------------------

def _load_credentials_info(cfg: OcrlSheetConfig) -> dict | None:
    raw = os.getenv(cfg.credentials_env, "").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        return json.loads(raw)
    # Si es una ruta a archivo JSON.
    if os.path.isfile(raw):
        with open(raw, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def register_row(config: AppConfig, partner: dict[str, Any]) -> dict[str, Any]:
    """Agrega una fila a la planilla. Requiere credenciales de service account.

    partner: {numero_cuenta, cuit, nombre, apellido?, telefono?, lid?, telegram?, precio?}
    """
    cfg = config.ocrl_sheet
    info = _load_credentials_info(cfg)
    if not info:
        return {
            "success": False,
            "error": (
                f"No hay credenciales de escritura (env {cfg.credentials_env}). "
                "La fila no se pudo registrar en la planilla."
            ),
        }
    try:
        from google.oauth2.service_account import Credentials  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        return {
            "success": False,
            "error": "Faltan dependencias google-api-python-client / google-auth.",
        }

    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    values = [[
        partner.get("numero_cuenta") or partner.get("account_code") or "",
        partner.get("cuit") or "",
        partner.get("nombre") or partner.get("name") or "",
        partner.get("apellido") or "",
        partner.get("telefono") or partner.get("phone") or "",
        partner.get("lid") or "",
        partner.get("telegram") or partner.get("telegram_username") or "",
        partner.get("precio") or partner.get("price_adjustment") or "",
    ]]
    result = service.spreadsheets().values().append(
        spreadsheetId=cfg.sheet_id,
        range="A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()
    return {"success": True, "updates": result.get("updates", {})}
