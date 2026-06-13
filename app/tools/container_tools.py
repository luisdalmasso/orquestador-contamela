from __future__ import annotations

import json
import re as _re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config.models import AppConfig
from app.tools import git_tools


def get_container_health(config: AppConfig, args: dict[str, Any]) -> dict[str, Any]:
    requested_env = str(args.get("env", "local") or "local")
    container_name = str(args.get("container", "") or "").strip()
    containers = _docker_ps(container_name=container_name)
    summary = {
        "available": containers["success"],
        "env": requested_env,
        "docker_access": containers["success"],
        "containers": [],
        "count": 0,
    }
    if not containers["success"]:
        summary["error"] = containers["error"]
        return summary

    entries = []
    for container in containers["items"]:
        health = _docker_inspect_health(container["name"])
        entries.append(
            {
                "name": container["name"],
                "image": container.get("image", ""),
                "status": container.get("status", ""),
                "state": health.get("state", container.get("state", "unknown")),
                "health": health.get("health"),
                "ports": container.get("ports", ""),
                "running_for": container.get("running_for", ""),
            }
        )

    summary["containers"] = entries
    summary["count"] = len(entries)
    return summary


def get_container_logs(config: AppConfig, args: dict[str, Any]) -> dict[str, Any]:
    container = str(args.get("container", "") or "").strip()
    if not container:
        raise ValueError("container es requerido")

    lines = min(max(int(args.get("lines", 200) or 200), 1), 2000)
    since = str(args.get("since", "24h") or "24h").strip()
    level = str(args.get("level", "all") or "all").strip().lower()

    try:
        client = _docker_client()
    except Exception as exc:
        return {"available": False, "container": container, "error": str(exc)}

    env_summary = _build_environment_summary(client)

    try:
        container_ref = client.containers.get(container)
        # SDK docker-py: usar int (Unix timestamp) — datetime object cuelga el socket
        since_ts = _since_to_datetime(since)
        # Con filtro de nivel traer más líneas brutas (errores dispersos entre INFO)
        fetch_tail = 5000 if level != "all" else lines
        raw_logs = container_ref.logs(
            stdout=True, stderr=True, timestamps=True,
            tail=fetch_tail, since=since_ts,
        )
    except Exception as exc:
        if exc.__class__.__name__ == "NotFound":
            return {"available": False, "container": container, "error": f"Container no encontrado: {container}", "environment": env_summary}
        return {"available": False, "container": container, "error": str(exc), "environment": env_summary}

    raw_lines = [l for l in raw_logs.decode(errors="replace").splitlines() if l.strip()]
    filtered_lines = _filter_log_lines(raw_lines, level=level)
    return {
        "available": True,
        "environment": env_summary,
        "container": container,
        "since": since,
        "level": level,
        "requested_lines": lines,
        "returned_lines": len(filtered_lines[-lines:]),
        "logs": "\n".join(filtered_lines[-lines:]),
    }


def get_vps_status(config: AppConfig, args: dict[str, Any]) -> dict[str, Any]:
    container_health = get_container_health(config, {"env": args.get("env", "local")})
    git_summary = git_tools.get_pipeline_summary(config, {"repo_path": args.get("repo_path", config.paths.development_repo)})
    return {
        "available": container_health.get("available", False) or git_summary.get("available", False),
        "docker": container_health,
        "git": git_summary,
        "summary": {
            "containers_running": sum(1 for item in container_health.get("containers", []) if "Up" in item.get("status", "")),
            "containers_total": container_health.get("count", 0),
            "git_branch": git_summary.get("branch"),
            "git_clean": git_summary.get("is_clean"),
        },
    }


def _docker_ps(container_name: str = "") -> dict[str, Any]:
    try:
        client = _docker_client()
        containers = client.containers.list(all=False, filters={"name": container_name} if container_name else None)
    except Exception as exc:
        return {"success": False, "error": str(exc), "items": []}

    items = []
    for container in containers:
        attrs = container.attrs or {}
        items.append(
            {
                "id": container.short_id,
                "name": container.name,
                "image": _container_image(container),
                "status": attrs.get("State", {}).get("Status", container.status or "unknown"),
                "state": attrs.get("State", {}).get("Status", container.status or "unknown"),
                "ports": _format_ports(attrs.get("NetworkSettings", {}).get("Ports", {})),
                "running_for": attrs.get("State", {}).get("StartedAt", ""),
            }
        )
    return {"success": True, "items": items}


def _docker_inspect_health(container: str) -> dict[str, Any]:
    try:
        container_ref = _docker_client().containers.get(container)
    except Exception:
        return {"state": "unknown", "health": None}
    payload = container_ref.attrs.get("State", {})
    health = payload.get("Health") or {}
    return {
        "state": payload.get("Status", "unknown"),
        "health": health.get("Status") if isinstance(health, dict) else None,
    }


# Patrones compilados una vez — evitan falsos positivos en JSON de startup
_ERROR_RE = _re.compile(
    r'\bERROR\b'                        # log level token mayúscula (Odoo, Gunicorn, uvicorn)
    r'|\bCRITICAL\b'
    r'|\bFATAL\b'
    r'|"level"\s*:\s*"error"'           # JSON structured logging (n8n, etc.)
    r'|"level"\s*:\s*"critical"'
    r'|\[error\]|\[critical\]|\[fatal\]'  # bracket style
    r'|Traceback \(most recent call last\)'
    r'|\w+Error:'                        # PythonError: / ValueError: / etc.
)
_WARN_RE = _re.compile(
    r'\bWARNING\b'
    r'|\bWARN\b'
    r'|"level"\s*:\s*"warn(?:ing)?"'
    r'|\[warn(?:ing)?\]'
)


def _filter_log_lines(lines: list[str], level: str) -> list[str]:
    if level == "all":
        return lines
    pattern = {"error": _ERROR_RE, "warning": _WARN_RE}.get(level)
    if pattern is None:
        return lines
    # Quitar el prefijo de timestamp Docker antes de aplicar el regex
    # para no matchear texto dentro del JSON de arranque del servicio
    _ts_re = _re.compile(r'^\S+Z\s+')
    filtered = []
    for line in lines:
        content = _ts_re.sub("", line, count=1)
        # Saltar líneas que son claramente valores JSON de descripción
        # (comienzan con comillas o espacios+comillas tras el timestamp)
        stripped = content.lstrip()
        if stripped.startswith('"') or stripped.startswith("'"):
            continue
        if pattern.search(content):
            filtered.append(line)
    return filtered


def _build_environment_summary(client=None) -> dict[str, Any]:
    """Devuelve contenedores agrupados por red (producción / desarrollo / otros)."""

    # Lista canónica de contenedores esperados según USER.md
    EXPECTED = {
        "production": {
            "network": "compose_odoo-network",
            "containers": [
                "django-api", "odoo18", "evolution-api-server", "wppconnect-server",
                "n8n", "chatwoot_web", "chatwoot_worker", "portainer",
                "cloudflared-tunnel", "ollama", "compose-db-1", "redis_odoo",
            ],
        },
        "development": {
            "network": "desarrollo_odoo-network-dev",
            "containers": [
                "django-dev", "odoo_dev", "n8n_dev", "chatwoot_web_dev",
                "chatwoot_worker_dev", "cloudflare-tunnel-dev", "db_dev", "redis_odoo_dev",
                "conti-backend",
            ],
        },
    }

    try:
        if client is None:
            client = _docker_client()
        containers = client.containers.list(all=True)  # all=True para ver stopped también
    except Exception as exc:
        return {"available": False, "error": str(exc)}

    PROD_NET = EXPECTED["production"]["network"]
    DEV_NET = EXPECTED["development"]["network"]

    # Indexar por nombre
    running_by_name: dict[str, dict] = {}
    other = []
    for c in containers:
        nets_raw = (c.attrs or {}).get("NetworkSettings", {}).get("Networks", {})
        networks = list(nets_raw.keys()) if isinstance(nets_raw, dict) else []
        entry = {
            "name": c.name,
            "status": c.status,
            "image": _container_image(c),
            "networks": networks,
        }
        running_by_name[c.name] = entry
        if PROD_NET not in networks and DEV_NET not in networks:
            other.append(entry)

    def _build_group(group_key: str) -> dict[str, Any]:
        net = EXPECTED[group_key]["network"]
        expected_names = EXPECTED[group_key]["containers"]
        result_containers = []
        missing = []
        for name in expected_names:
            if name in running_by_name:
                result_containers.append(running_by_name[name])
            else:
                missing.append({"name": name, "status": "missing", "image": None, "networks": [net]})
        # Agregar contenedores en esa red que no están en la lista esperada (extras)
        for name, entry in running_by_name.items():
            if net in entry["networks"] and name not in expected_names:
                result_containers.append({**entry, "note": "unlisted_in_user_md"})
        return {
            "network": net,
            "containers": result_containers,
            "missing": missing,
            "count_running": sum(1 for c in result_containers if c.get("status") == "running"),
            "count_expected": len(expected_names),
        }

    return {
        "available": True,
        "production": _build_group("production"),
        "development": _build_group("development"),
        "other": other,
    }


def _docker_client():
    import docker
    return docker.DockerClient(base_url="unix:///var/run/docker.sock")


def _container_image(container) -> str:
    tags = getattr(container.image, "tags", None) or []
    if tags:
        return tags[0]
    return getattr(container.image, "short_id", "")


def _format_ports(ports: dict[str, Any]) -> str:
    formatted = []
    for container_port, mappings in (ports or {}).items():
        if not mappings:
            formatted.append(container_port)
            continue
        for mapping in mappings:
            host_ip = mapping.get("HostIp", "0.0.0.0")
            host_port = mapping.get("HostPort", "")
            formatted.append(f"{host_ip}:{host_port}->{container_port}")
    return ", ".join(formatted)


def _since_to_datetime(raw_value: str) -> int | None:
    """Devuelve Unix timestamp (int) — el SDK de docker-py cuelga con objetos datetime."""
    value = (raw_value or "").strip().lower()
    if not value:
        return None
    delta = None
    if value.endswith("m") and value[:-1].isdigit():
        delta = timedelta(minutes=int(value[:-1]))
    elif value.endswith("h") and value[:-1].isdigit():
        delta = timedelta(hours=int(value[:-1]))
    elif value.endswith("d") and value[:-1].isdigit():
        delta = timedelta(days=int(value[:-1]))
    if delta is None:
        return None
    return int((datetime.now(timezone.utc) - delta).timestamp())
    return None