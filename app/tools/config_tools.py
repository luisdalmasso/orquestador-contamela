from __future__ import annotations

from app.config.loader import load_config
from app.services.onboarding_service import OnboardingService
from app.services.rules_service import RulesService


def get_config(_: dict) -> dict:
    config = load_config()
    return {
        "config": config.redacted_dict(),
        "paths": config.resolved_paths(),
    }


def get_onboarding(arguments: dict) -> dict:
    brief = bool(arguments.get("brief", False))
    return OnboardingService().get_onboarding(brief=brief)


def get_rules(_: dict) -> dict:
    return RulesService().get_rules()
