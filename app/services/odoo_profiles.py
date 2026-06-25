from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from app.config.models import AppConfig, OdooConnectionConfig


@dataclass(frozen=True, slots=True)
class ResolvedOdooConnection:
    name: str
    url: str
    db: str
    host_header: str | None
    username: str
    password: str
    context: dict[str, str]


def resolve_odoo_connection(config: AppConfig, arguments: dict[str, Any] | None = None) -> ResolvedOdooConnection:
    args = arguments or {}
    connection_name = str(args.get("connection") or config.odoo.default_connection)
    profile = config.odoo.connections.get(connection_name)
    if profile is None:
        raise ValueError(f"Conexión Odoo no configurada: {connection_name}")

    url = str(args.get("url") or profile.url or "").rstrip("/")
    db = str(args.get("db") or profile.db or "").strip()
    if not url:
        raise ValueError(f"La conexión Odoo '{connection_name}' no tiene URL configurada")
    if not db:
        raise ValueError(f"La conexión Odoo '{connection_name}' no tiene DB configurada")

    username = _resolve_secret(
        explicit=args.get("username"),
        primary_env=profile.username_env,
        fallback_envs=profile.username_fallback_envs,
        default_value=profile.default_username,
    )
    password = _resolve_secret(
        explicit=args.get("password"),
        primary_env=profile.password_env,
        fallback_envs=profile.password_fallback_envs,
        default_value=profile.default_password,
    )

    return ResolvedOdooConnection(
        name=connection_name,
        url=url,
        db=db,
        host_header=args.get("host_header") or profile.host_header or None,
        username=username,
        password=password,
        context={
            "lang": config.odoo.default_lang,
            "tz": config.odoo.default_tz,
        },
    )


def _resolve_secret(
    explicit: Any,
    primary_env: str,
    fallback_envs: list[str],
    default_value: str,
) -> str:
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()

    env_names = [primary_env, *fallback_envs]
    for env_name in env_names:
        if not env_name:
            continue
        resolved = os.environ.get(env_name)
        if resolved:
            return resolved

    if default_value:
        return default_value
    raise ValueError(f"No se pudo resolver credencial requerida. Variables probadas: {env_names}")
