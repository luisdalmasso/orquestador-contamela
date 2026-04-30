from __future__ import annotations

from functools import lru_cache

from app.config.loader import load_config
from app.core import categories, visibility
from app.core.tool_models import ToolDefinition
from app.core.tool_registry import ToolRegistry
from app.tools import config_tools, container_tools, filesystem, git_tools, search_literal, system_status


class RegistryService:
    def __init__(self) -> None:
        self._registry = ToolRegistry()
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._registry.register(
            ToolDefinition(
                name="list_files",
                description="Lista archivos y directorios bajo un root permitido.",
                category=categories.FILESYSTEM,
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                visibility=visibility.PUBLIC,
                tags=["filesystem", "read-only"],
            ),
            lambda args: filesystem.list_files(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="read_file",
                description="Lee un archivo dentro de los roots permitidos.",
                category=categories.FILESYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                    },
                    "required": ["path"],
                },
                visibility=visibility.PUBLIC,
                tags=["filesystem", "read-only"],
            ),
            lambda args: filesystem.read_file(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="file_exists",
                description="Informa si un path permitido existe.",
                category=categories.FILESYSTEM,
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
                visibility=visibility.PUBLIC,
                tags=["filesystem", "read-only"],
            ),
            lambda args: filesystem.file_exists(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_code_context",
                description="Devuelve contexto alrededor de una línea de un archivo permitido.",
                category=categories.FILESYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "line": {"type": "integer"},
                        "context": {"type": "integer"},
                    },
                    "required": ["path"],
                },
                visibility=visibility.PUBLIC,
                tags=["filesystem", "code"],
            ),
            lambda args: filesystem.get_code_context(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="search_code_literal",
                description="Busca texto literal o regex dentro del repo de desarrollo.",
                category=categories.SEARCH,
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                visibility=visibility.PUBLIC,
                tags=["search", "code"],
            ),
            lambda args: search_literal.search_code_literal(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="search_docs_literal",
                description="Busca texto literal o regex dentro de la documentación del backend.",
                category=categories.SEARCH,
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                visibility=visibility.PUBLIC,
                tags=["search", "docs"],
            ),
            lambda args: search_literal.search_docs_literal(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="grep_workspace",
                description="Busca coincidencias dentro del workspace permitido.",
                category=categories.SEARCH,
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                visibility=visibility.PUBLIC,
                tags=["search", "workspace"],
            ),
            lambda args: search_literal.grep_workspace(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="health_check",
                description="Devuelve el estado actual del backend.",
                category=categories.SYSTEM,
                input_schema={"type": "object", "properties": {}},
                visibility=visibility.PUBLIC,
                tags=["system"],
            ),
            system_status.health_check,
        )
        self._registry.register(
            ToolDefinition(
                name="get_config",
                description="Devuelve la configuración efectiva redactada.",
                category=categories.CONFIG,
                input_schema={"type": "object", "properties": {}},
                visibility=visibility.PUBLIC,
                tags=["config"],
            ),
            config_tools.get_config,
        )
        self._registry.register(
            ToolDefinition(
                name="reload_config",
                description="Recarga la configuración del backend.",
                category=categories.CONFIG,
                input_schema={"type": "object", "properties": {}},
                visibility=visibility.INTERNAL,
                tags=["config"],
            ),
            system_status.reload_backend_config,
        )
        self._registry.register(
            ToolDefinition(
                name="get_onboarding",
                description="Devuelve el onboarding efectivo del backend.",
                category=categories.CONFIG,
                input_schema={"type": "object", "properties": {"brief": {"type": "boolean"}}},
                visibility=visibility.PUBLIC,
                tags=["config", "onboarding"],
            ),
            config_tools.get_onboarding,
        )
        self._registry.register(
            ToolDefinition(
                name="get_rules",
                description="Devuelve las reglas efectivas del backend.",
                category=categories.CONFIG,
                input_schema={"type": "object", "properties": {}},
                visibility=visibility.PUBLIC,
                tags=["config", "rules"],
            ),
            config_tools.get_rules,
        )
        self._registry.register(
            ToolDefinition(
                name="get_git_status",
                description="Devuelve el estado Git local del repo de desarrollo.",
                category=categories.SYSTEM,
                input_schema={"type": "object", "properties": {"repo_path": {"type": "string"}}},
                visibility=visibility.PUBLIC,
                tags=["git", "read-only"],
            ),
            lambda args: git_tools.get_git_status(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_git_log",
                description="Devuelve el historial reciente del repo Git local.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string"},
                        "n": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "read-only"],
            ),
            lambda args: git_tools.get_git_log(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="diff_with_develop",
                description="Compara el HEAD local contra develop remoto o local configurado.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string"},
                        "remote": {"type": "string"},
                        "develop_branch": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "diff"],
            ),
            lambda args: git_tools.diff_with_develop(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_pipeline_summary",
                description="Resume el pipeline Git local: rama, estado, remotos y diff contra develop.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string"},
                        "remote": {"type": "string"},
                        "develop_branch": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "pipeline", "read-only"],
            ),
            lambda args: git_tools.get_pipeline_summary(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_container_health",
                description="Resume estado y salud de contenedores Docker accesibles desde el backend.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "env": {"type": "string", "enum": ["local", "dev", "prod", "all"]},
                        "container": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["docker", "containers", "read-only"],
            ),
            lambda args: container_tools.get_container_health(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_container_logs",
                description="Lee logs de un contenedor Docker local con filtros por tiempo, nivel y cantidad de líneas.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "container": {"type": "string"},
                        "lines": {"type": "integer"},
                        "since": {"type": "string"},
                        "level": {"type": "string", "enum": ["all", "error", "warning"]},
                    },
                    "required": ["container"],
                },
                visibility=visibility.PUBLIC,
                tags=["docker", "logs", "read-only"],
            ),
            lambda args: container_tools.get_container_logs(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_vps_status",
                description="Da una vista consolidada del estado Docker local y del repo Git principal montado.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "env": {"type": "string", "enum": ["local", "dev", "prod", "all"]},
                        "repo_path": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["docker", "git", "status", "read-only"],
            ),
            lambda args: container_tools.get_vps_status(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="run_salvar",
                description="Hace preview o ejecuta commit+push local a develop.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "confirm": {"type": "boolean"},
                        "summary": {"type": "string"},
                        "repo_path": {"type": "string"},
                        "remote": {"type": "string"},
                        "develop_branch": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "write"],
            ),
            lambda args: git_tools.run_salvar(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="run_promover",
                description="Hace preview o ejecuta merge local develop -> main con push.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "confirm": {"type": "boolean"},
                        "summary": {"type": "string"},
                        "repo_path": {"type": "string"},
                        "remote": {"type": "string"},
                        "develop_branch": {"type": "string"},
                        "main_branch": {"type": "string"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["git", "write", "promote"],
            ),
            lambda args: git_tools.run_promover(load_config(), args),
        )

    def list_tools(self):
        return self._registry.list_tools()

    def call(self, tool_name: str, arguments: dict | None = None):
        return self._registry.call(tool_name, arguments)


@lru_cache(maxsize=1)
def registry_service() -> RegistryService:
    return RegistryService()