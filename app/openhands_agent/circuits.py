# app/openhands_agent/circuits.py
"""
Los 4 circuitos del agente Conti.

Cada circuito tiene:
  - Workspace específico (path distinto)
  - Tool set específico (qué tools nativas + MCP puede invocar)
  - Reglas de git específicas (qué puede hacer con git)
  - LLM opcionalmente distinto

Los 4 circuitos son independientes. No hay delegación entre ellos.

Dos runtimes disponibles (seleccionados vía feature flag `CONTI_USE_OMP_AGENT`):
  - OpenHands SDK (`Conversation` + `Agent`): legacy, aún soportado.
  - oh-my-pi (`OmpClient` sobre conti-omp:7891): runtime nuevo (Sprint 4).
  - Default: OpenHands SDK (mantiene status quo mientras validamos omp).
  - Cuando flag activo: `OmpClient` (recomendado — más features, menos código).

Tabla de circuitos (definida en este archivo, fuente única):
  1. desarrollo  → /desarrollo (rama develop de contamela-stack)
                  tools: full + git run_salvar (preview) → target = develop
                  puede: commit, push a develop
                  NO puede: promover a main, hacer deploy
  2. produccion  → /compose (rama main, RW) + /desarrollo (operativa)
                  tools: full + git run_promover (develop→main+push)
                  + run_hotfix_sync (main→develop)
                  puede: promover, hotfix-sync main→develop
                  NO puede: 3-despliegue.sh, docker compose up -d prod
  3. backend     → /contenedores/conti-backend (rama main orquestador-contamela)
                  tools: full + git run_salvar (preview) → target = main
                  puede: commit, push a main de orquestador-contamela
  4. libre       → /tmp/free-agent (sin repo)
                  tools: SOLO MCP (sin file_editor, sin terminal, sin git)
                  puede: recibir ruta del host como argumento, trabajar
                         con fuentes externas si Luis da credenciales
                  NO puede: editar repos git

Campos clave de CircuitConfig (nuevos en PLAN_3):
  - git_action_target: rama a la que aplica git_action (default "develop").
                       "backend" usa "main" porque ese repo solo tiene main.
  - git_action_options: acciones git adicionales permitidas más allá de
                       git_action. "produccion" incluye "run_hotfix_sync"
                       para el flujo main→develop.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core import categories as mcp_categories

log = logging.getLogger("conti.circuits")

# ──────────────────────────────────────────────────────────────────────
# Lazy imports de openhands para no romper el módulo si no está
# ──────────────────────────────────────────────────────────────────────

try:
    from openhands.sdk import Agent, Conversation, LLM, LocalWorkspace

    OPENHANDS_AVAILABLE = True
except Exception as _exc:
    OPENHANDS_AVAILABLE = False
    log.warning("OpenHands SDK no disponible: %s", _exc)
    Agent = Conversation = LLM = LocalWorkspace = None  # type: ignore


# ──────────────────────────────────────────────────────────────────────
# Definición de cada circuito
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CircuitConfig:
    """Configuración estática de un circuito."""

    id: str
    workspace_dir: str
    description: str
    allowed_tools_native: tuple[str, ...]
    allowed_mcp_categories: tuple[str, ...]
    git_action: str  # "run_salvar" | "run_promover" | "none"
    git_action_target: str = "develop"  # rama destino de git_action
    git_action_options: tuple[str, ...] = ()  # acciones extra, ej. ("run_hotfix_sync",)
    llm_model_override: str | None = None


# Tool sets nativos de OpenHands SDK (nombres reales verificados vía
# openhands.tools.preset.default.get_default_agent).
# Tools built-in (FinishTool, ThinkTool, etc.) se incluyen automáticamente.
# Nota: NO incluimos browser_tool_set porque requiere Chromium instalado
# y agrega peso innecesario. Si el agente necesita navegar, usar MCP RAG
# + tools de búsqueda o pedir a Luis que lo habilite explícitamente.
NATIVE_TOOLS_FULL = (
    "terminal",
    "file_editor",
    "task_tracker",
)

NATIVE_TOOLS_NONE: tuple[str, ...] = ()  # circuito 4: solo MCP


# Categorías MCP (alineadas con app/core/categories.py — antes hardcoded)
MCP_CATEGORIES_ALL = (
    mcp_categories.BOOTSTRAP,
    mcp_categories.STACK,
    mcp_categories.RAG,
    mcp_categories.SOURCEBOT,
    mcp_categories.GITOPS,
    mcp_categories.FILESYSTEM,
    mcp_categories.ODOO,
    mcp_categories.DOCUMENTS,
    mcp_categories.SHEETS,
    mcp_categories.CATOLICO,
    mcp_categories.CODE_EDIT,
    mcp_categories.OBSERVABILITY,
)
MCP_CATEGORIES_NO_GIT = tuple(
    c for c in MCP_CATEGORIES_ALL if c != mcp_categories.GITOPS
)
MCP_CATEGORIES_LIBRE = (
    mcp_categories.BOOTSTRAP,
    mcp_categories.RAG,
    mcp_categories.SOURCEBOT,
    mcp_categories.ODOO,
    mcp_categories.DOCUMENTS,
    mcp_categories.SHEETS,
    mcp_categories.CATOLICO,
    mcp_categories.FILESYSTEM,
    mcp_categories.OBSERVABILITY,
)


CIRCUITS: dict[str, CircuitConfig] = {
    "desarrollo": CircuitConfig(
        id="desarrollo",
        workspace_dir="/desarrollo",
        description=(
            "DevOps en rama develop de contamela-stack. "
            "Puede commitear y pushear a develop via run_salvar (preview). "
            "NO promueve a main, NO despliega."
        ),
        allowed_tools_native=NATIVE_TOOLS_FULL,
        allowed_mcp_categories=MCP_CATEGORIES_ALL,
        git_action="run_salvar",
        git_action_target="develop",
    ),
    "produccion": CircuitConfig(
        id="produccion",
        workspace_dir="/compose",
        description=(
            "DevOps en rama main de contamela-stack (produccion). "
            "Promueve via run_promover (merge develop->main + push). "
            "Sincroniza main->develop tras hotfix via run_hotfix_sync. "
            "NO corre 3-despliegue.sh ni docker compose -f producion.yml up -d "
            "(solo Luis puede)."
        ),
        allowed_tools_native=NATIVE_TOOLS_FULL,
        allowed_mcp_categories=MCP_CATEGORIES_ALL,
        git_action="run_promover",
        git_action_target="develop",  # promover arranca desde develop
        git_action_options=("run_hotfix_sync",),
    ),
    "backend": CircuitConfig(
        id="backend",
        workspace_dir="/contenedores/conti-backend",
        description=(
            "DevOps sobre orquestador-contamela (rama main). "
            "Puede commitear y pushear a main via run_salvar (preview). "
            "Sin flujo develop->main porque este repo solo tiene main. "
            "run_hotfix_sync NO aplica (no hay develop)."
        ),
        allowed_tools_native=NATIVE_TOOLS_FULL,
        allowed_mcp_categories=MCP_CATEGORIES_ALL,
        git_action="run_salvar",
        git_action_target="main",
    ),
    "libre": CircuitConfig(
        id="libre",
        workspace_dir="/tmp/free-agent",
        description=(
            "Conversacional / fuentes externas. SIN acceso a repos git. "
            "Solo MCP tools (RAG, Odoo, Sheets, docs). "
            "Puede recibir una ruta del host como argumento; "
            "si la ruta NO está bind-mounted, pedir credenciales a Luis."
        ),
        allowed_tools_native=NATIVE_TOOLS_NONE,
        allowed_mcp_categories=MCP_CATEGORIES_LIBRE,
        git_action="none",
        git_action_target="",
    ),
}


# ──────────────────────────────────────────────────────────────────────
# Router: detecta qué circuito usar según el prompt del usuario
# ──────────────────────────────────────────────────────────────────────

# Palabras clave por circuito (case-insensitive). El primer match gana.
# Orden importa: lo más específico primero.
CIRCUIT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "produccion",
        (
            "/compose",
            "produccion",
            "producción",
            "rama main",
            "promover",
            "promocion",
            "promoción",
            "merge a main",
            "deploy",
            "desplegar",
            "despliegue",
            "en producción",
            "en produccion",
            "a main",
            # Hotfix sync (main → develop)
            "hotfix",
            "sync main",
            "main a develop",
            "sincronizar main",
            "sincronizá main",
            "pull de main",
            "main to develop",
        ),
    ),
    (
        "backend",
        (
            "/contenedores/conti-backend",
            "orquestador-contamela",
            "conti-backend",
            "el backend",
            "este repo",
            "orquestador",
        ),
    ),
    (
        "desarrollo",
        (
            "/desarrollo",
            "rama develop",
            "rama dev",
            "desarrollo",
            "en desa",
            "en dev",
            "salvar",
            "commitea",
            "commit",
            "develop branch",
        ),
    ),
]


def detect_circuit(prompt: str, force: str | None = None) -> str:
    """Detecta qué circuito usar según el prompt.

    Args:
        prompt: texto del usuario (sin system prompt)
        force: si se pasa un id ("desarrollo"/"produccion"/"backend"/"libre"),
            se usa ese sin análisis.

    Returns: id del circuito ("desarrollo" por defecto si no hay match).
    """
    if force and force in CIRCUITS:
        return force

    p = prompt.lower()
    for cid, keywords in CIRCUIT_KEYWORDS:
        for kw in keywords:
            if kw.lower() in p:
                return cid

    return "libre"  # por defecto, conversacional


# ──────────────────────────────────────────────────────────────────────
# Conversation manager: 4 conversaciones persistentes (singleton)
# ──────────────────────────────────────────────────────────────────────


class CircuitManager:
    """Mantiene los 4 runtimes persistentes (uno por circuito) en memoria.

    Runtime seleccionable vía feature flag `CONTI_USE_OMP_AGENT`:
      - true  → OmpClient (oh-my-pi via conti-omp:7891, Sprint 4)
      - false → OpenHands SDK Conversation (legacy, default)
    """

    def __init__(self) -> None:
        self._conversations: dict[str, Any] = {}  # OpenHands SDK
        self._omp_clients: dict[str, Any] = {}  # oh-my-pi
        self._initialized: dict[str, bool] = {}

    def get_or_create(self, circuit_id: str) -> Any:
        """Devuelve el runtime del circuito, creándolo si no existe.

        Returns:
            - OmpClient si CONTI_USE_OMP_AGENT=true
            - OpenHands Conversation si no
        """
        from app.openhands_agent.omp_client import is_omp_enabled

        if circuit_id not in CIRCUITS:
            raise ValueError(f"circuito desconocido: {circuit_id}")
        if self._initialized.get(circuit_id):
            if is_omp_enabled():
                return self._omp_clients.get(circuit_id)
            return self._conversations.get(circuit_id)

        cfg = CIRCUITS[circuit_id]
        log.info(
            "[circuits] inicializando circuito '%s' workspace=%s runtime=%s",
            cfg.id,
            cfg.workspace_dir,
            "omp" if is_omp_enabled() else "openhands",
        )
        if is_omp_enabled():
            self._omp_clients[circuit_id] = self._build_omp_client(cfg)
        else:
            self._conversations[circuit_id] = self._build_conversation(cfg)
        self._initialized[circuit_id] = True
        if is_omp_enabled():
            return self._omp_clients[circuit_id]
        return self._conversations[circuit_id]

    def _build_conversation(self, cfg: CircuitConfig) -> Any:
        if not OPENHANDS_AVAILABLE:
            return None
        # Asegurar que el workspace existe (excepto "libre" que usa /tmp)
        Path(cfg.workspace_dir).mkdir(parents=True, exist_ok=True)

        # Registrar las tools default de OpenHands (terminal, file_editor,
        # task_tracker, browser_tool_set). Sin esto, Tool(name='terminal')
        # falla con "is not registered".
        try:
            from openhands.tools.preset.default import register_default_tools

            register_default_tools()
        except Exception as exc:
            log.warning("register_default_tools falló: %s", exc)

        model = cfg.llm_model_override or os.getenv(
            "OPENHANDS_LLM_MODEL", "mistral/mistral-small-latest"
        )
        base_url = os.getenv("OPENHANDS_LLM_BASE_URL", "https://api.mistral.ai/v1")
        # Selección de API key según el base_url/modelo
        if "mistral.ai" in base_url:
            api_key = (
                os.getenv("OPENHANDS_LLM_API_KEY") or os.getenv("MISTRAL_API_KEY") or ""
            )
        elif "kilo" in base_url or "openrouter" in base_url:
            api_key = os.getenv("KILOCODE_API_KEY") or ""
        elif "gemini" in model.lower() or "google" in model.lower():
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        elif "deepseek" in model.lower():
            api_key = os.getenv("DEEPSEEK_API_KEY") or ""
        elif "openai" in model.lower():
            api_key = os.getenv("OPENAI_API_KEY") or ""
        else:
            api_key = (
                os.getenv("OPENHANDS_LLM_API_KEY")
                or os.getenv("KILOCODE_API_KEY")
                or ""
            )

        llm = LLM(model=model, api_key=api_key, base_url=base_url)

        # Construir lista explícita de tools vía Tool(name=...). Si la lista
        # está vacía (circuito "libre"), el agente arranca sin tools nativas.
        from openhands.sdk import Tool

        tools_list: list[Any] = []
        for tool_name in cfg.allowed_tools_native:
            tools_list.append(Tool(name=tool_name))

        # ── MCP tools del backend conti (:9001/mcp) ─────────────────
        # Integra las MCP tools permitidas por el circuito en el loop del
        # agente via SDK nativo. Conexión HTTP loopback al mismo proceso
        # uvicorn. FILTRADO REAL por categoría (Sprint 1.5 PLAN_3):
        # antes cargaba TODAS las 64 tools; ahora respeta las categorías
        # declaradas en cfg.allowed_mcp_categories usando el registro MCP.
        if cfg.allowed_mcp_categories:
            try:
                from openhands.sdk.mcp import create_mcp_tools

                mcp_url = os.getenv("CONTI_MCP_URL", "http://127.0.0.1:9001/mcp")
                mcp_tools = asyncio.run(
                    create_mcp_tools(
                        mcp_config={
                            "mcpServers": {
                                "conti-backend": {
                                    "url": mcp_url,
                                    "transport": "streamable-http",
                                }
                            }
                        },
                        timeout=30,
                    )
                )

                # Calcular set de nombres de tools permitidos por categoría
                allowed_names: set[str] = set()
                from app.services.registry_service import registry_service

                registry = registry_service()
                for tool_def in registry.list_tools():
                    if tool_def.get("category") in cfg.allowed_mcp_categories:
                        allowed_names.add(tool_def["name"])

                # Filtrar mcp_tools (OpenHands SDK Tool objects) por nombre
                filtered_mcp_tools = [
                    t for t in mcp_tools if getattr(t, "name", None) in allowed_names
                ]
                tools_list.extend(filtered_mcp_tools)
                log.info(
                    "[circuits] %s: %d/%d MCP tools cargadas (filtradas por categorías %s)",
                    cfg.id,
                    len(filtered_mcp_tools),
                    len(mcp_tools),
                    cfg.allowed_mcp_categories,
                )
            except Exception as exc:
                log.warning(
                    "[circuits] %s: no se pudieron cargar MCP tools: %s. "
                    "El agente seguirá solo con tools nativas.",
                    cfg.id,
                    exc,
                )

        agent = Agent(
            llm=llm,
            name=f"conti-{cfg.id}",
            tools=tools_list,
        )

        workspace = LocalWorkspace(working_dir=cfg.workspace_dir)
        return Conversation(agent=agent, workspace=workspace)

    def _build_omp_client(self, cfg: CircuitConfig) -> Any:
        """Construye un OmpClient para el circuito dado.

        El OmpClient habla con conti-omp:7891 vía stdio NDJSON sobre TCP
        socket (expuesto por socat en el container). omp --mode rpc corre
        el agent loop internamente.

        El system prompt base (Ponytail rules + circuit description +
        tool list) se setea UNA VEZ al constructor. Es estático por
        circuito — no cambia entre requests. Cambia solo si Luis
        cambia el AGENTS.md de Ponytail o las reglas del circuito
        (que requiere recrear el OmpClient).

        Sprint 4.2: además construye custom_tools = MCP tools filtradas
        por categoría y registradas como host_tool en omp. omp las invoca
        como built-in, pero el handler Python hace JSON-RPC loopback
        a :9001/mcp.
        """
        from app.openhands_agent.omp_client import make_omp_client_for_circuit
        from app.openhands_agent.tool_bridge import build_custom_tools_for_circuit

        # omp_rpc.RpcClient spawn el subprocess con `cwd=workspace_dir`,
        # así que el directorio DEBE existir antes de start().
        Path(cfg.workspace_dir).mkdir(parents=True, exist_ok=True)

        # Construir custom_tools (MCP loopback filtrado por categoría).
        from app.services.registry_service import registry_service

        registry = registry_service()
        mcp_url = os.getenv("CONTI_MCP_URL", "http://127.0.0.1:9001/mcp")
        custom_tools = build_custom_tools_for_circuit(cfg, registry, mcp_url)

        # Construir el system prompt base para omp (estático per-circuit).
        system_prompt = self._build_omp_system_prompt(cfg)

        return make_omp_client_for_circuit(
            cfg,
            append_system_prompt=system_prompt,
            custom_tools=custom_tools,
        )

    @staticmethod
    def _build_omp_system_prompt(cfg: CircuitConfig) -> str:
        """Construye el system prompt base para el omp subprocess.

        Contiene:
          - Ponytail rules (AGENTS.md)
          - Descripción del circuito
          - Reglas de operación y onboarding
          - Lista detallada de MCP tools disponibles (nombres, descripciones,
            args, ejemplos de uso)
          - Información de Sourcebot (endpoint, formato de request, cómo usarlo)

        El user_task del circuito (parte dinámica) se pasa como user_prompt
        a prompt_and_wait(), NO se concatena al system prompt (porque omp
        persistiría el system prompt en su session history).
        """
        from pathlib import Path

        sections: list[str] = []

        # 1) Ponytail rules (onboarding)
        ponytail_rules_path = Path("/app/vendor/ponytail/AGENTS.md")
        if ponytail_rules_path.exists():
            try:
                sections.append(ponytail_rules_path.read_text(encoding="utf-8").strip())
            except Exception:
                pass

        # 2) Circuit description
        sections.append(
            f"# Circuit: {cfg.id}\n\n"
            f"{cfg.description}\n\n"
            f"Workspace: {cfg.workspace_dir}\n"
            f"Git action permitida: {cfg.git_action}\n"
        )

        # 3) MCP tools (solo nombres, agrupadas por categoría)
        try:
            from app.services.registry_service import registry_service

            registry = registry_service()
            tools = registry.list_tools()
            if tools:
                # Agrupar tools por categoría si tienen metadata
                tools_by_cat: dict[str, list[str]] = {}
                for tool in tools:
                    name = tool.get("name", "?")
                    cat = tool.get("category", "general")
                    tools_by_cat.setdefault(cat, []).append(name)

                tools_section = "# MCP Tools Disponibles\n\n"
                tools_section += (
                    "Las siguientes tools MCP están disponibles en el servidor.\n"
                    "Para invocarlas, usá bash + curl:\n\n"
                    "```bash\n"
                    "curl -s -X POST http://conti-backend:9001/mcp/call \\\n"
                    "  -H 'Content-Type: application/json' \\\n"
                    '  -d \'{"name": "TOOL_NAME", "arguments": {}}\'\n'
                    "```\n\n"
                )
                for cat, names in sorted(tools_by_cat.items()):
                    tools_section += f"## {cat}\n"
                    tools_section += ", ".join(sorted(names)) + "\n\n"
                sections.append(tools_section)
        except Exception as exc:
            log.warning("[circuits] no pude cargar MCP tools: %s", exc)

        # 4) Sourcebot info
        sourcebot_section = (
            "# Sourcebot (búsqueda de código)\n\n"
            "Tenés acceso a Sourcebot, un motor de búsqueda de código que indexa "
            "los 3 repos del stack: orquestador-contamela, contamela-stack (develop y main).\n\n"
            "## Cómo usarlo\n"
            "- Endpoint: `http://conti-sourcebot:3000/api/search`\n"
            '- Método: POST con JSON `{"query": "términos", "matches": N}`\n'
            "- NO requiere autenticación (acceso anónimo habilitado)\n"
            "- **Funciona mejor con queries cortas (1-3 keywords técnicas)**\n"
            '  Ejemplo: `"django views"`, `"chatui"`, `"mcp tools"`\n\n'
            "## Respuesta\n"
            "Devuelve `{stats, files: [...]}` donde cada file tiene:\n"
            "- `fileName`: {text, matchRanges}\n"
            "- `chunks`: [{content, contentStart: {lineNumber}}]\n"
            "- `language`, `repository`, `branches`, `webUrl`\n\n"
            "## Ejemplo de uso desde bash\n"
            "```bash\n"
            "curl -X POST http://conti-sourcebot:3000/api/search \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            '  -d \'{"query": "django views", "matches": 5}\'\n'
            "```\n"
        )
        sections.append(sourcebot_section)

        # 5) Reglas de operación del circuito
        if cfg.id == "backend":
            sections.append(
                "# Reglas del circuito backend\n\n"
                "- SIEMPRE validá con `validate_python_syntax` antes de commitear\n"
                "- SIEMPRE ejecutá `run_pytest` después de editar código\n"
                "- Si algún test falla, NO commitees, arreglá primero\n"
                "- Usá `sourcebot_search` para buscar código antes de editar\n"
                "- Usá `ponytail_record_trace` para registrar la traza al final\n"
                "- **NO uses `get_config`** - está deprecated y causa timeouts\n"
                "- **NO busques el endpoint MCP** - ya lo sabés: `http://localhost:9001/mcp`\n"
                "- Para listar tools MCP: `curl -s http://localhost:9001/mcp`\n"
                "- Para ejecutar una tool MCP: `curl -s -X POST http://localhost:9001/mcp "
                "-H 'Content-Type: application/json' "
                '-d \'{"jsonrpc":"2.0","id":1,"method":"tools/call",'
                '"params":{"name":"TOOL_NAME","arguments":{...}}}\'`\n'
                "- **Leé los archivos directamente** del workspace "
                f"(`{cfg.workspace_dir}`) - no necesitas buscar la URL del MCP\n"
            )
        elif cfg.id in ("desarrollo", "produccion"):
            sections.append(
                f"# Reglas del circuito {cfg.id}\n\n"
                "- Usá `run_salvar` para commitear y pushear\n"
                "- Usá `run_promover` para promover develop → main (solo en producción)\n"
                "- Usá `sourcebot_search` para buscar código antes de editar\n"
                "- Usá `ponytail_record_trace` para registrar la traza al final\n"
            )

        return "\n\n---\n\n".join(sections)

    def is_ready(self, circuit_id: str) -> bool:
        return self._initialized.get(circuit_id, False)

    def is_omp_client(self, circuit_id: str) -> bool:
        """True si el runtime del circuito es OmpClient (no OpenHands)."""
        return circuit_id in self._omp_clients

    def status(self) -> dict[str, Any]:
        from app.openhands_agent.omp_client import is_omp_enabled

        return {
            cid: {
                "ready": self._initialized.get(cid, False),
                "runtime": "omp" if cid in self._omp_clients else "openhands",
                "workspace": CIRCUITS[cid].workspace_dir,
                "git_action": CIRCUITS[cid].git_action,
            }
            for cid in CIRCUITS
        }


circuit_manager = CircuitManager()
