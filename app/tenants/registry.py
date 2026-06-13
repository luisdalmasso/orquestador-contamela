"""Tenant registry — discovers and caches tenant configs from /tenants/."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import yaml

from app.tenants.base import TenantConfig

log = logging.getLogger("conti.tenants")

TENANTS_ROOT = Path("/tenants")


class TenantRegistry:
    """Discovers tenant configs from filesystem and caches them."""

    def __init__(self, tenants_root: Path | None = None):
        self._root = tenants_root or TENANTS_ROOT
        self._cache: dict[str, TenantConfig] = {}
        self._loaded = False

    def _discover(self) -> None:
        """Scan /tenants/<id>/config.yaml and load all tenant configs."""
        self._cache.clear()
        if not self._root.exists():
            log.warning("Tenants root %s does not exist", self._root)
            self._loaded = True
            return

        for tenant_dir in sorted(self._root.iterdir()):
            config_file = tenant_dir / "config.yaml"
            if not config_file.exists():
                continue
            try:
                raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
                tenant = TenantConfig.model_validate(raw)
                self._cache[tenant.tenant_id] = tenant
                log.info("Loaded tenant: %s (strategy=%s, port=%d)",
                         tenant.tenant_id, tenant.strategy, tenant.nanobot_port)
            except Exception as exc:
                log.error("Failed to load tenant config %s: %s", config_file, exc)

        self._loaded = True
        log.info("Tenant registry: %d tenant(s) loaded", len(self._cache))

    def get(self, tenant_id: str) -> TenantConfig | None:
        """Get a tenant config by ID."""
        if not self._loaded:
            self._discover()
        return self._cache.get(tenant_id)

    def list_tenants(self) -> list[str]:
        """List all discovered tenant IDs."""
        if not self._loaded:
            self._discover()
        return list(self._cache.keys())

    def reload(self) -> None:
        """Force reload all tenant configs."""
        self._loaded = False
        self._discover()


# Singleton
_registry: TenantRegistry | None = None


def get_tenant_registry() -> TenantRegistry:
    """Get or create the global tenant registry."""
    global _registry
    if _registry is None:
        _registry = TenantRegistry()
    return _registry
