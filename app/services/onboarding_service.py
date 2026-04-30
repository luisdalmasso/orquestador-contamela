from __future__ import annotations

from app.config.loader import load_config, reload_config
from app.onboarding.loader import load_onboarding_text


class OnboardingService:
    def get_onboarding(self, brief: bool = False) -> dict[str, str | bool]:
        config = load_config()
        return load_onboarding_text(config, brief=brief)

    def reload(self, brief: bool = False) -> dict[str, str | bool]:
        config = reload_config()
        return load_onboarding_text(config, brief=brief)
