from __future__ import annotations

from fastapi import FastAPI
from fastapi import Query
from fastapi.staticfiles import StaticFiles

from app.chat.router import router as chat_router
from app.config.loader import load_config, reload_config
from app.llm_emulation.router import router as llm_router
from app.mcp.router import router as mcp_router
from app.services.health_service import HealthService
from app.services.onboarding_service import OnboardingService
from app.services.rules_service import RulesService
from app.utils.logging import add_request_id, configure_logging
from app.web.router import WEB_DIR, router as web_router

configure_logging()

app = FastAPI(title="Conti Backend", version="0.1.0")
onboarding_service = OnboardingService()
rules_service = RulesService()
app.middleware("http")(add_request_id)
app.mount("/ui/static", StaticFiles(directory=str(WEB_DIR / "static")), name="ui-static")
app.include_router(web_router)
app.include_router(mcp_router)
app.include_router(llm_router)
app.include_router(chat_router)


@app.get("/health")
def health() -> dict:
    config = load_config()
    service = HealthService(config)
    return service.build_status()


@app.get("/config")
def get_config() -> dict:
    config = load_config()
    return {
        "status": "ok",
        "config": config.redacted_dict(),
        "paths": config.resolved_paths(),
    }


@app.post("/config/reload")
def post_reload_config() -> dict:
    config = reload_config()
    return {
        "status": "reloaded",
        "config": config.redacted_dict(),
    }


@app.get("/onboarding")
def get_onboarding(brief: bool = Query(default=False)) -> dict:
    payload = onboarding_service.get_onboarding(brief=brief)
    return {
        "status": "ok",
        **payload,
    }


@app.post("/onboarding/reload")
def post_reload_onboarding(brief: bool = Query(default=False)) -> dict:
    payload = onboarding_service.reload(brief=brief)
    return {
        "status": "reloaded",
        **payload,
    }


@app.get("/rules")
def get_rules() -> dict:
    payload = rules_service.get_rules()
    return {
        "status": "ok",
        "configured_path": payload["configured_path"],
        "resolved_path": payload["resolved_path"],
        "source_paths": payload["source_paths"],
        "checksum": payload["checksum"],
        "mtime": payload["mtime"],
        "content": payload["content"],
    }


@app.get("/rules/raw")
def get_rules_raw() -> dict:
    payload = rules_service.get_rules()
    return {
        "status": "ok",
        "raw": payload["raw"],
        "source_paths": payload["source_paths"],
    }


@app.post("/rules/reload")
def post_reload_rules() -> dict:
    payload = rules_service.reload()
    return {
        "status": "reloaded",
        "configured_path": payload["configured_path"],
        "resolved_path": payload["resolved_path"],
        "source_paths": payload["source_paths"],
        "checksum": payload["checksum"],
        "mtime": payload["mtime"],
        "content": payload["content"],
    }
