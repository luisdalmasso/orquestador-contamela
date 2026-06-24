from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.utils.paths import resolve_runtime_path


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 9001
    reload: bool = False


class LLMEmulationConfig(BaseModel):
    enabled: bool = True
    default_model: str = "conti-default"
    streaming_enabled: bool = True
    mode: str = "nanobot_serve"
    serve_profile: str = "conti-llm-serve"
    serve_base_url: str = "http://127.0.0.1:8765"


class PathsConfig(BaseModel):
    home_root: str = "/home/nanobot"
    development_repo: str = "/desarrollo"
    production_repo: str = "/compose"
    onboarding_file: str = "/app/docs/onboarding.md"
    onboarding_brief_file: str = "/app/docs/onboarding_brief.md"
    rules_file: str = "/app/docs/rules.md"

    def as_dict(self) -> dict[str, str]:
        return {
            "home_root": self.home_root,
            "development_repo": self.development_repo,
            "production_repo": self.production_repo,
            "onboarding_file": self.onboarding_file,
            "onboarding_brief_file": self.onboarding_brief_file,
            "rules_file": self.rules_file,
        }


class UIConfig(BaseModel):
    enabled: bool = True
    title: str = "Conti MCP Console"


class ProvidersConfig(BaseModel):
    active: str = "openai_compatible"
    openai_compatible: dict[str, Any] = Field(default_factory=dict)


class RagConfig(BaseModel):
    base_url: str = "http://flamehaven:8000"
    api_key_env: str = "FLAMEHAVEN_API_KEY"
    default_store: str = "default"


class OdooConnectionConfig(BaseModel):
    url: str = "http://odoo18:8069"
    db: str = "demo"
    host_header: str | None = None
    username_env: str = "ODOO_USERNAME"
    password_env: str = "ODOO_PASSWORD"
    username_fallback_envs: list[str] = Field(default_factory=lambda: ["ODOO_USER", "ODOOUSER"])
    password_fallback_envs: list[str] = Field(default_factory=lambda: ["ODOOPASSWORD"])
    default_username: str = "demo"
    default_password: str = "demo"


class OdooConfig(BaseModel):
    default_connection: str = "prod"
    default_lang: str = "es_AR"
    default_tz: str = "America/Argentina/Buenos_Aires"
    connect_timeout_seconds: int = 30
    max_retries: int = 3
    ocr_enabled: bool = True
    payment_proof_max_mb: int = 1
    connections: dict[str, OdooConnectionConfig] = Field(
        default_factory=lambda: {
            "prod": OdooConnectionConfig(),
            "dev": OdooConnectionConfig(
                url="http://odoo18_dev:8069",
                username_env="ODOO_DEV_USERNAME",
                password_env="ODOO_DEV_PASSWORD",
                username_fallback_envs=["ODOO_DEV_USER"],
                password_fallback_envs=[],
            ),
        }
    )


class MercadoPagoConfig(BaseModel):
    access_token_env: str = "MERCADOPAGO_ACCESS_TOKEN"
    public_key_env: str = "MERCADOPAGO_PUBLIC_KEY"
    sandbox_env: str = "MERCADOPAGO_SANDBOX"
    api_base_url: str = "https://api.mercadopago.com"
    success_url: str = "http://localhost:9001/odoo/mercadopago/success"
    failure_url: str = "http://localhost:9001/odoo/mercadopago/failure"
    pending_url: str = "http://localhost:9001/odoo/mercadopago/pending"
    notification_url: str = "http://localhost:9001/odoo/mercadopago/webhook"
    request_timeout_seconds: int = 30


class OcrlSheetConfig(BaseModel):
    """Planilla de Google (Tier 2) para identificación de clientes OCRL.

    Ver Documentacion/odoo/ocrl_mendoza.md. La planilla tiene acceso público
    como editor, por lo que se puede leer (CSV export) y escribir (API Sheets).
    """

    sheet_id: str = "1x3I9EvplbIk4q-To0BBjdUdKJyoOYUWzVgo_MwC2z7k"
    # gid de la pestaña; 0 = primera hoja.
    gid: int = 0
    account_sheet_prefix: str = "CL"
    # Credenciales de service account para escritura (API Sheets v4).
    credentials_env: str = "OCRL_SHEET_CREDENTIALS_JSON"
    request_timeout_seconds: int = 30

    @property
    def csv_url(self) -> str:
        return (
            f"https://docs.google.com/spreadsheets/d/{self.sheet_id}"
            f"/export?format=csv&gid={self.gid}"
        )


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm_emulation: LLMEmulationConfig = Field(default_factory=LLMEmulationConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    rag: RagConfig = Field(default_factory=RagConfig)
    odoo: OdooConfig = Field(default_factory=OdooConfig)
    mercadopago: MercadoPagoConfig = Field(default_factory=MercadoPagoConfig)
    ocrl_sheet: OcrlSheetConfig = Field(default_factory=OcrlSheetConfig)

    def redacted_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        return _redact_sensitive_values(data)

    def resolved_paths(self) -> dict[str, dict[str, Any]]:
        path_map: dict[str, dict[str, Any]] = {}
        for key, value in self.paths.as_dict().items():
            path = resolve_runtime_path(value)
            path_map[key] = {
                "path": str(path),
                "exists": path.exists(),
                "is_dir": path.is_dir(),
                "is_file": path.is_file(),
            }
        return path_map


def _redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if any(token in lowered for token in ("key", "token", "secret", "password")):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = _redact_sensitive_values(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive_values(item) for item in value]
    return value
