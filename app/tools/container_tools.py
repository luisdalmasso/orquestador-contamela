from __future__ import annotations

import json
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


def get_container_logs(_: AppConfig, args: dict[str, Any]) -> dict[str, Any]:
    container = str(args.get("container", "") or "").strip()
    if not container:
        raise ValueError("container es requerido")

    lines = min(max(int(args.get("lines", 200) or 200), 1), 2000)
    since = str(args.get("since", "24h") or "24h").strip()
    level = str(args.get("level", "all") or "all").strip().lower()

    try:
        client = _docker_client()
        container_ref = client.containers.get(container)
        raw_logs = container_ref.logs(
            stdout=True,
            stderr=True,
            timestamps=True,
            tail=lines,
            since=_since_to_datetime(since) if since else None,
        )
    except Exception as exc:
        if exc.__class__.__name__ == "NotFound":
            return {"available": False, "container": container, "error": f"Container no encontrado: {container}"}
        return {
            "available": False,
            "container": container,
            "error": str(exc),
        }

    raw_lines = [line for line in raw_logs.decode(errors="replace").splitlines() if line.strip()]
    filtered_lines = _filter_log_lines(raw_lines, level=level)
    return {
        "available": True,
        "container": container,
        "since": since,
        "level": level,
        "requested_lines": lines,
        "returned_lines": len(filtered_lines),
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


def _filter_log_lines(lines: list[str], level: str) -> list[str]:
    if level == "all":
        return lines

    keywords = {
        "error": ["error", "exception", "traceback", "fatal", "crit"],
        "warning": ["warn", "warning"],
    }.get(level, [])

    if not keywords:
        return lines
    filtered = []
    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in keywords):
            filtered.append(line)
    return filtered


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


def _since_to_datetime(raw_value: str) -> datetime | None:
    value = (raw_value or "").strip().lower()
    if not value:
        return None
    if value.endswith("m") and value[:-1].isdigit():
        return datetime.now(timezone.utc) - timedelta(minutes=int(value[:-1]))
    if value.endswith("h") and value[:-1].isdigit():
        return datetime.now(timezone.utc) - timedelta(hours=int(value[:-1]))
    if value.endswith("d") and value[:-1].isdigit():
        return datetime.now(timezone.utc) - timedelta(days=int(value[:-1]))
    return None