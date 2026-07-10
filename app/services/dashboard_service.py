"""Dashboard service — consolidated health view of all conti-backend services.

Gathers status from:
- FastAPI (self)
- OpenHands Agent Server
- OMP (conti-omp)
- Hermes gateways (7 profiles)
- MCP tools registry
- CircuitManager
- SessionStore
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger("conti.dashboard")


class DashboardService:
    """Consolidated dashboard for all services."""

    def __init__(self) -> None:
        self._start_time = time.time()

    def get_dashboard(self) -> dict[str, Any]:
        """Build full dashboard context."""
        return {
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self._start_time,
            "services": self._check_services(),
            "circuits": self._check_circuits(),
            "hermes_gateways": self._check_hermes_gateways(),
            "mcp_tools": self._check_mcp_tools(),
            "sessions": self._check_sessions(),
        }

    def _check_services(self) -> list[dict[str, Any]]:
        """Check core services health."""
        services = []

        # FastAPI (self)
        services.append({
            "name": "FastAPI",
            "port": 9001,
            "status": "healthy",
            "description": "MCP backend + chat completions + UI",
        })

        # OpenHands Agent Server
        oh_status = self._check_port("127.0.0.1", 3000)
        services.append({
            "name": "OpenHands Agent Server",
            "port": 3000,
            "status": oh_status,
            "description": "Orquestador de circuitos",
        })

        # OMP (conti-omp)
        omp_status = self._check_port("conti-omp", 7891)
        services.append({
            "name": "OMP (conti-omp)",
            "port": 7891,
            "status": omp_status,
            "description": "Runtime oh-my-pi",
        })

        # TraceUpdater
        services.append({
            "name": "TraceUpdater",
            "port": None,
            "status": "running",
            "description": "Background thread, actualiza trazas Ponytail",
        })

        return services

    def _check_circuits(self) -> list[dict[str, Any]]:
        """Check circuit status."""
        try:
            from app.openhands_agent.circuits import CIRCUITS, circuit_manager

            circuits = []
            for cid, cfg in CIRCUITS.items():
                status = circuit_manager.status()
                circuit_info = status.get("circuits", {}).get(cid, {})
                circuits.append({
                    "id": cid,
                    "workspace": cfg.workspace_dir,
                    "git_action": cfg.git_action,
                    "git_target": cfg.git_action_target,
                    "tools_native": list(cfg.allowed_tools_native),
                    "mcp_categories": list(cfg.allowed_mcp_categories),
                    "status": "active" if circuit_info.get("initialized") else "idle",
                    "sessions": circuit_info.get("sessions", 0),
                })
            return circuits
        except Exception as exc:
            log.warning("Failed to check circuits: %s", exc)
            return []

    def _check_hermes_gateways(self) -> list[dict[str, Any]]:
        """Check Hermes gateway health."""
        gateways = [
            {"name": "contihome", "port": 18791, "profile": "contihome", "platforms": ["telegram"]},
            {"name": "catolico", "port": 8766, "profile": "catolico", "platforms": ["telegram"]},
            {"name": "resto", "port": 8767, "profile": "resto", "platforms": ["telegram"]},
            {"name": "odoo", "port": 8768, "profile": "odoo", "platforms": ["api"]},
            {"name": "odoo-resto", "port": None, "profile": "odoo-resto", "platforms": ["telegram"]},
            {"name": "odoo-nudo", "port": None, "profile": "odoo-nudo", "platforms": ["telegram"]},
            {"name": "odoo-mendoza", "port": 8769, "profile": "odoo-mendoza", "platforms": ["api", "telegram"]},
            {"name": "mendoza", "port": 8770, "profile": "mendoza", "platforms": ["api", "wppconnect"]},
        ]

        for gw in gateways:
            if gw["port"]:
                gw["status"] = self._check_port("127.0.0.1", gw["port"])
            else:
                gw["status"] = "telegram-only"

        return gateways

    def _check_mcp_tools(self) -> dict[str, Any]:
        """Check MCP tools registry."""
        try:
            from app.services.registry_service import registry_service

            registry = registry_service()
            tools = registry.list_tools()

            # Count by category
            categories: dict[str, int] = {}
            for tool in tools:
                cat = tool.get("category", "unknown")
                categories[cat] = categories.get(cat, 0) + 1

            return {
                "total": len(tools),
                "categories": categories,
            }
        except Exception as exc:
            log.warning("Failed to check MCP tools: %s", exc)
            return {"total": 0, "categories": {}}

    def _check_sessions(self) -> dict[str, Any]:
        """Check active sessions."""
        try:
            from app.openhands_agent.session_store import SessionStore

            store = SessionStore.get_instance()
            sessions = store.list_sessions() if hasattr(store, "list_sessions") else []
            return {
                "active": len(sessions),
                "sessions": sessions[:10],  # Last 10
            }
        except Exception as exc:
            log.warning("Failed to check sessions: %s", exc)
            return {"active": 0, "sessions": []}

    def _check_port(self, host: str, port: int) -> str:
        """Check if a port is reachable."""
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"http://{host}:{port}/health", timeout=2.0)
                if resp.status_code == 200:
                    return "healthy"
                return "degraded"
        except Exception:
            # Try raw TCP connection
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    return "running"
                return "unreachable"
            except Exception:
                return "unreachable"


# Singleton
_dashboard_service: DashboardService | None = None


def get_dashboard_service() -> DashboardService:
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DashboardService()
    return _dashboard_service
