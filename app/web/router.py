from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config.loader import load_config
from app.services.health_service import HealthService
from app.services.nanobot_config_service import nanobot_config_service
from app.services.nanobot_serve_service import nanobot_serve_service
from app.services.onboarding_service import OnboardingService
from app.services.registry_service import registry_service
from app.services.rules_service import RulesService
from app.tools import git_tools


WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
router = APIRouter(tags=["web-ui"])


@router.get("/")
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/ui", status_code=307)


@router.get("/ui")
def ui_index(request: Request):
    context = _build_base_context(request)
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/ui/settings")
def ui_settings(request: Request):
    context = _build_base_context(request)
    context["config_json"] = json.dumps(context["config"], indent=2, ensure_ascii=False)
    context["paths_json"] = json.dumps(context["paths"], indent=2, ensure_ascii=False)
    return templates.TemplateResponse(request, "settings.html", context)


@router.get("/ui/tools")
def ui_tools(request: Request):
    context = _build_base_context(request)
    return templates.TemplateResponse(request, "tools.html", context)


@router.get("/ui/rules")
def ui_rules(request: Request):
    context = _build_base_context(request)
    return templates.TemplateResponse(request, "rules.html", context)


@router.get("/ui/nanobots")
def ui_nanobots(request: Request, saved: str | None = None):
    context = _build_base_context(request)
    context["gateway_config"] = nanobot_config_service.get_gateway_config()
    context["llm_config"] = nanobot_config_service.get_llm_config()
    context["save_result"] = saved
    return templates.TemplateResponse(request, "nanobots.html", context)


@router.post("/ui/nanobots/gateway")
def save_gateway_nanobot(
    model: str = Form(...),
    provider: str = Form(...),
    temperature: str = Form(...),
    maxToolIterations: str = Form(...),
    maxTokens: str = Form(...),
    contextWindowTokens: str = Form(...),
    api_base: str = Form(...),
    api_key: str = Form(...),
    telegram_token: str = Form(""),
    allowFrom: str = Form(""),
):
    nanobot_config_service.save_gateway_config(
        {
            "model": model,
            "provider": provider,
            "temperature": temperature,
            "maxToolIterations": maxToolIterations,
            "maxTokens": maxTokens,
            "contextWindowTokens": contextWindowTokens,
            "api_base": api_base,
            "api_key": api_key,
            "telegram_token": telegram_token,
            "allowFrom": allowFrom,
        }
    )
    return RedirectResponse(url="/ui/nanobots?saved=Gateway%20actualizado", status_code=303)


@router.post("/ui/nanobots/llm")
def save_llm_nanobot(
    model: str = Form(...),
    provider: str = Form(...),
    temperature: str = Form(...),
    maxToolIterations: str = Form(...),
    maxTokens: str = Form(...),
    contextWindowTokens: str = Form(...),
    api_base: str = Form(...),
    api_key: str = Form(...),
):
    nanobot_config_service.save_llm_config(
        {
            "model": model,
            "provider": provider,
            "temperature": temperature,
            "maxToolIterations": maxToolIterations,
            "maxTokens": maxTokens,
            "contextWindowTokens": contextWindowTokens,
            "api_base": api_base,
            "api_key": api_key,
        }
    )
    return RedirectResponse(url="/ui/nanobots?saved=LLM%20serve%20actualizado", status_code=303)


def _build_base_context(request: Request) -> dict:
    config = load_config()
    registry = registry_service()
    onboarding = OnboardingService().get_onboarding()
    onboarding_brief = OnboardingService().get_onboarding(brief=True)
    rules = RulesService().get_rules()
    health = HealthService(config).build_status()
    backend_status = nanobot_serve_service.backend_status()
    git_summary = _get_git_summary(config.paths.development_repo)
    tools = registry.list_tools()

    return {
        "request": request,
        "title": config.ui.title,
        "config": config.redacted_dict(),
        "paths": config.resolved_paths(),
        "health": health,
        "backend_status": backend_status,
        "tools": tools,
        "tools_count": len(tools),
        "onboarding": onboarding,
        "onboarding_brief": onboarding_brief,
        "rules": rules,
        "git_summary": git_summary,
        "nav_items": [
            {"href": "/ui", "label": "Estado"},
            {"href": "/ui/settings", "label": "Settings"},
            {"href": "/ui/tools", "label": "Tools"},
            {"href": "/ui/rules", "label": "Onboarding / Rules"},
            {"href": "/ui/nanobots", "label": "Nanobots"},
        ],
    }


def _get_git_summary(repo_path: str) -> dict:
    try:
        return git_tools.get_pipeline_summary(load_config(), {"repo_path": repo_path})
    except Exception as exc:
        return {"available": False, "error": str(exc), "repo_path": repo_path}
