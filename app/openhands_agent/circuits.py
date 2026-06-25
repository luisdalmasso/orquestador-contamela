# app/openhands_agent/circuits.py
"""
Los 4 circuitos del agente Conti (OpenHands).

Cada circuito es una conversación persistente de OpenHands SDK con:
  - Workspace específico (LocalWorkspace con path distinto)
  - Tool set específico (qué tools nativas + MCP puede invocar)
  - Reglas de git específicas (qué puede hacer con git)
  - LLM opcionalmente distinto (coding model para los 3 con código, lightweight para el 4)

Los 4 circuitos son independientes. No hay delegación entre ellos. La
comunicación entre circuitos se hace exclusivamente via git (push en uno,
pull en otro cuando corresponde).

Tabla de circuitos (definida en este archivo, fuente única):
  1. desarrollo  → /desarrollo (rama develop de contamela-stack)
                  tools: full + git run_salvar (preview)
                  puede: commit, push a develop
                  NO puede: promover a main, hacer deploy
  2. produccion  → /compose (rama main de contamela-stack, RW)
                  tools: full + git run_promover (merge develop→main + push)
                  puede: promover, después sincronizar /desarrollo (git pull)
                  NO puede: 3-despliegue.sh, docker compose up -d prod
  3. backend     → /contenedores/conti-backend (rama main orquestador-contamela)
                  tools: full + git run_salvar (preview)
                  puede: commit, push a main de orquestador-contamela
  4. libre       → /tmp/free-agent (sin repo)
                  tools: SOLO MCP (sin file_editor, sin terminal, sin git)
                  puede: recibir ruta del host como argumento, trabajar
                         con fuentes externas si Luis da credenciales
                  NO puede: editar repos git
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


# Categorías MCP (definidas en PLAN_2_LLM.md §3)
MCP_CATEGORIES_ALL = (
    "bootstrap",  # health_check, get_config, get_rules, get_onboarding
    "stack",  # get_container_health, get_container_logs, get_vps_status
    "rag",  # search_rag*, start_rag_ingest*, catolico_*
    "gitops",  # get_git_*, run_salvar (preview), run_promover (preview)
    "filesystem",  # list_files, read_file, search_code_literal, grep_workspace
    "odoo",  # odoo_* (21 tools)
    "documents",  # start_markdown_translation, start_pdf_to_markdown
    "sheets",  # sheet_account_*, sheet_lookup_partner, sheet_register_partner
)
MCP_CATEGORIES_NO_GIT = tuple(c for c in MCP_CATEGORIES_ALL if c != "gitops")
MCP_CATEGORIES_LIBRE = (
    "bootstrap",
    "rag",
    "odoo",
    "documents",
    "sheets",
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
    ),
    "produccion": CircuitConfig(
        id="produccion",
        workspace_dir="/compose",
        description=(
            "DevOps en rama main de contamela-stack (produccion). "
            "Promueve via run_promover (merge develop->main + push). "
            "Después de promover, sincroniza /desarrollo (git checkout main && pull). "
            "NO corre 3-despliegue.sh ni docker compose -f producion.yml up -d "
            "(solo Luis puede)."
        ),
        allowed_tools_native=NATIVE_TOOLS_FULL,
        allowed_mcp_categories=MCP_CATEGORIES_ALL,
        git_action="run_promover",
    ),
    "backend": CircuitConfig(
        id="backend",
        workspace_dir="/contenedores/conti-backend",
        description=(
            "DevOps sobre orquestador-contamela (rama main). "
            "Puede commitear y pushear via run_salvar (preview). "
            "Sin flujo develop->main porque este repo solo tiene main."
        ),
        allowed_tools_native=NATIVE_TOOLS_FULL,
        allowed_mcp_categories=MCP_CATEGORIES_ALL,
        git_action="run_salvar",
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
    """Mantiene las 4 conversaciones persistentes en memoria."""

    def __init__(self) -> None:
        self._conversations: dict[str, Any] = {}
        self._initialized: dict[str, bool] = {}

    def get_or_create(self, circuit_id: str) -> Any:
        """Devuelve la conversación del circuito, creándola si no existe."""
        if circuit_id not in CIRCUITS:
            raise ValueError(f"circuito desconocido: {circuit_id}")
        if self._initialized.get(circuit_id):
            return self._conversations.get(circuit_id)

        cfg = CIRCUITS[circuit_id]
        log.info(
            "[circuits] inicializando circuito '%s' workspace=%s",
            cfg.id,
            cfg.workspace_dir,
        )
        self._conversations[circuit_id] = self._build_conversation(cfg)
        self._initialized[circuit_id] = True
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
        # Integra las 64 MCP tools (odoo_*, run_salvar, search_rag*, etc.)
        # en el loop del agente via SDK nativo. Conexión HTTP loopback al
        # mismo proceso uvicorn (no importa el loopback como dijiste).
        # Solo si el circuito tiene categorías MCP permitidas (no "libre"
        # sin gitops).
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
                # Filtrar tools MCP según categorías permitidas del circuito
                # Para empezar, incluirlas todas si allowed_mcp_categories != ()
                tools_list.extend(mcp_tools)
                log.info(
                    "[circuits] %s: %d MCP tools cargadas desde %s",
                    cfg.id,
                    len(mcp_tools),
                    mcp_url,
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

    def is_ready(self, circuit_id: str) -> bool:
        return self._initialized.get(circuit_id, False)

    def status(self) -> dict[str, Any]:
        return {
            cid: {
                "ready": self._initialized.get(cid, False),
                "workspace": CIRCUITS[cid].workspace_dir,
                "git_action": CIRCUITS[cid].git_action,
            }
            for cid in CIRCUITS
        }


circuit_manager = CircuitManager()
