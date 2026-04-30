from __future__ import annotations

from app.config.loader import load_config, reload_config
from app.rules.loader import load_rules_bundle


class RulesService:
    def get_rules(self) -> dict[str, object]:
        config = load_config()
        return load_rules_bundle(config)

    def reload(self) -> dict[str, object]:
        config = reload_config()
        return load_rules_bundle(config)
