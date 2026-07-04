# app/openhands_agent/service.py
"""
Plataforma de emulación LLM nativa basada en OpenHands SDK v1.29.

Implementa el flujo del PLAN_LLM.MD (v4) usando la API real de
`openhands.sdk` (LLM, Agent, LocalConversation).

Stack integrado:
  - OpenHands SDK   -> runtime de ejecución del agente
  - oh-my-pi (omp-rpc) -> cliente Python para el protocolo RPC del agente
  - Sourcebot       -> indexación de código (vía HTTP en :3010)
  - Ponytail        -> trazabilidad (wrapper Python + AGENTS.md ruleset)
  - MCP             -> herramientas expuestas al agente (Tools/list)

El servicio NO delega a gateways Hermes en :8767; el stack OpenHands es
el único backend para /v1/chat/completions, /v1/models, /v1/responses.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncIterator

log = logging.getLogger("conti.openhands_agent")

# ─────────────────────────────────────────────────────────────────────
# Stack OpenHands (SDK v1.29)
# ─────────────────────────────────────────────────────────────────────

try:
    from openhands.sdk import LLM, Agent, Conversation, LocalConversation

    OPENHANDS_AVAILABLE = True
    log.info("OpenHands SDK importado correctamente.")
except Exception as _exc:  # pragma: no cover - degradación controlada
    OPENHANDS_AVAILABLE = False
    log.warning("OpenHands SDK NO disponible: %s", _exc)
    LLM = Agent = Conversation = LocalConversation = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────
# oh-my-pi (omp-rpc): cliente Python para invocar el agente vía RPC.
# ─────────────────────────────────────────────────────────────────────

try:
    import omp_rpc  # type: ignore

    OMP_AVAILABLE = True
    log.info("omp-rpc (oh-my-pi) disponible.")
except Exception as _exc:
    OMP_AVAILABLE = False
    log.warning("omp-rpc NO disponible: %s", _exc)

# ─────────────────────────────────────────────────────────────────────
# Ponytail: reglas AGENTS.md + wrapper Python de trazabilidad.
# ─────────────────────────────────────────────────────────────────────

PONYTAIL_RULES = ""
PONYTAIL_TRACES_DIR = os.environ.get("PONYTAIL_TRACES_DIR", "/app/logs/ponytail")

try:
    with open("/app/vendor/ponytail/AGENTS.md", "r", encoding="utf-8") as _f:
        PONYTAIL_RULES = _f.read()
    log.info("Ponytail ruleset cargado (%d bytes).", len(PONYTAIL_RULES))
except Exception as _exc:
    log.warning("No se pudo cargar Ponytail ruleset: %s. Continuando sin él.", _exc)

# ─────────────────────────────────────────────────────────────────────
# Sourcebot: cliente HTTP simple (el contenedor conti-sourcebot vive en
# la misma red docker que conti-backend y expone :3000 internamente).
# ─────────────────────────────────────────────────────────────────────

try:
    import httpx  # type: ignore

    HTTPX_AVAILABLE = True
except Exception:
    HTTPX_AVAILABLE = False

SOURCEBOT_URL = os.getenv("SOURCEBOT_URL", "http://conti-sourcebot:3000")


def _infer_repo(path: str) -> str:
    """Inferir repo del path. Formato: github.com/user/repo/..."""
    if not path or "/" not in path:
        return "?"
    parts = path.split("/")
    if len(parts) >= 3:
        return "/".join(parts[:3])
    return path


def _enrich_sourcebot_hit(hit: dict) -> dict:
    """Enriquece un hit de Sourcebot con metadata completa.

    Sourcebot v5.0.4 format:
    {
      fileName: {text, matchRanges},
      repository: "github.com/...",
      language: "Python",
      webUrl: "http://...",
      branches: ["refs/heads/develop"],
      chunks: [{content, contentStart: {lineNumber}}]
    }
    """
    fn = hit.get("fileName")
    if isinstance(fn, dict):
        file_name = fn.get("text", "?")
    else:
        file_name = str(fn) if fn else "?"

    repo = hit.get("repository") or _infer_repo(file_name)
    language = hit.get("language", "?")
    web_url = hit.get("webUrl", "")
    branches = hit.get("branches", [])

    # Extraer primer chunk con lineNumber
    chunks = hit.get("chunks", [])
    first_line = "?"
    snippet = ""
    if chunks and isinstance(chunks, list):
        c0 = chunks[0]
        snippet = (c0.get("content") or "")[:200]
        cs = c0.get("contentStart", {})
        if isinstance(cs, dict):
            first_line = cs.get("lineNumber", "?")

    return {
        "repo": repo,
        "fileName": file_name,
        "language": language,
        "line": first_line,
        "branches": branches[:2] if branches else [],
        "snippet": snippet,
        "webUrl": web_url,
    }


def _sourcebot_search(query: str, limit: int = 5) -> list[dict]:
    """Busca en Sourcebot por query. Devuelve [] si no está disponible.

    API de Sourcebot v5.0.4: POST /api/search con {query, matches}.
    Devuelve: { stats, files: [{fileName, path, chunks: [...]}] }.
    Si Sourcebot requiere auth, devuelve [] (no es crítico, el agent sigue
    funcionando con solo el system prompt + contexto de usuario).

    Estrategia: Sourcebot funciona mejor con keywords cortas (ej: "django
    views") que con oraciones largas. Si la query tiene >5 palabras,
    extrae las palabras técnicas relevantes (palabras en CamelCase,
    snake_case, o keywords conocidas como nombres de containers, paths).
    """
    if not HTTPX_AVAILABLE or not query:
        return []
    # Simplificar la query: si tiene más de 5 palabras, extraer keywords
    search_query = _extract_search_keywords(query)
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                f"{SOURCEBOT_URL}/api/search",
                json={"query": search_query, "matches": limit},
                headers={"Content-Type": "application/json"},
            )
            if r.status_code == 200:
                data = r.json()
                # Sourcebot v5.0.4 format: { stats, files: [...] }
                files = data.get("files", []) if isinstance(data, dict) else []
                log.info(
                    "[sourcebot] query=%r (orig=%r) matches=%d status=200 files=%d",
                    search_query[:80],
                    query[:80],
                    limit,
                    len(files),
                )
                return files
            elif r.status_code == 401:
                log.warning(
                    "[sourcebot] query=%r status=401 NOT_AUTHENTICATED. "
                    "Sourcebot requiere auth. Continuar sin RAG de código.",
                    search_query[:100],
                )
            else:
                log.warning(
                    "[sourcebot] query=%r status=%d body=%s",
                    search_query[:100],
                    r.status_code,
                    r.text[:200],
                )
    except Exception as exc:
        log.warning("[sourcebot] query=%r error: %s", search_query[:100], exc)
    return []


# Stopwords para español e inglés (palabras comunes que no aportan a búsqueda)
_SEARCH_STOPWORDS = {
    # Español
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
    "de",
    "del",
    "al",
    "a",
    "en",
    "por",
    "para",
    "con",
    "sin",
    "que",
    "qué",
    "como",
    "cómo",
    "cual",
    "cuál",
    "donde",
    "dónde",
    "es",
    "son",
    "está",
    "están",
    "hay",
    "tener",
    "tiene",
    "tienen",
    "y",
    "o",
    "u",
    "pero",
    "si",
    "no",
    "sí",
    "más",
    "menos",
    "este",
    "esta",
    "estos",
    "estas",
    "ese",
    "esa",
    "esos",
    "esas",
    "yo",
    "tú",
    "él",
    "ella",
    "nosotros",
    "vosotros",
    "ellos",
    "ellas",
    "le",
    "les",
    "se",
    "me",
    "te",
    "lo",
    "la",
    "los",
    "las",
    "mi",
    "tu",
    "su",
    "nuestro",
    "vuestro",
    "sus",
    "haz",
    "hace",
    "hacer",
    "explicame",
    "explica",
    "describe",
    "analiza",
    "documento",
    "documenta",
    "documéntalo",
    "archivo",
    "fichero",
    "puedes",
    "puede",
    "podrias",
    "podría",
    "deberia",
    "debería",
    "sobre",
    "acerca",
    "respecto",
    # Inglés
    "the",
    "a",
    "an",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "and",
    "or",
    "but",
    "if",
    "not",
    "this",
    "that",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "we",
    "they",
    "it",
    "what",
    "how",
    "which",
    "where",
    "when",
    "why",
    "can",
    "could",
    "should",
    "would",
    "may",
    "might",
    "explain",
    "describe",
    "analyze",
    "document",
    "write",
    "create",
}


def _extract_search_keywords(query: str) -> str:
    """Extrae keywords significativas de una query larga.

    Estrategia: devolver 1-3 keywords técnicas que Sourcebot pueda buscar
    efectivamente. Sourcebot funciona mejor con queries cortas (1-3 palabras
    técnicas) que con oraciones largas.

    Ejemplos:
        "Explicame la app website del contenedor django que paginas expone"
            → "django views"
        "Analiza el contenedor chatui con definicion en producion.yml"
            → "chatui"
        "Analiza el endpoint /mcp del contenedor conti-backend"
            → "mcp conti-backend"
    """
    import re

    # Lista priorizada de containers/conceptos del stack Contamela
    # Si la query menciona uno de estos, usarlo como query principal
    known_concepts = [
        "chatui",
        "django",
        "conti-backend",
        "mcp",
        "website",
        "contamela",
        "odoo",
        "n8n",
        "chainlit",
        "flamehaven",
        "sourcebot",
        "hermes",
    ]

    query_lower = query.lower()
    matches: list[str] = []
    for concept in known_concepts:
        if concept in query_lower:
            matches.append(concept)

    # Si no hay matches con conceptos conocidos, buscar sustantivos técnicos
    # (palabras en CamelCase, snake_case, contenedores)
    if not matches:
        tech_terms = re.findall(r"\b[a-z]+(?:[-_][a-z]+)+\b", query_lower) + re.findall(
            r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", query
        )
        # Filtrar stopwords y términos demasiado largos
        tech_terms = [t for t in tech_terms if t.lower() not in _SEARCH_STOPWORDS]
        matches.extend(tech_terms[:2])

    # Si todavía no hay matches, tomar 1-2 keywords filtradas
    if not matches:
        words = re.findall(r"\b\w+\b", query_lower)
        keywords = [w for w in words if w not in _SEARCH_STOPWORDS and len(w) > 3]
        matches = keywords[:2]

    # Si la query es corta (<=3 palabras) y no hay matches, devolver original
    if not matches or len(query.split()) <= 3:
        return query

    # Devolver 1-3 keywords más relevantes
    return " ".join(matches[:3])


# ─────────────────────────────────────────────────────────────────────
# Ponytail: context manager de trazabilidad.
# ─────────────────────────────────────────────────────────────────────


class PonytailTrace:
    """Wrapper mínimo de trazabilidad inspirado en `ponytail.trace()`.

    Persiste cada trace al directorio del circuito correspondiente
    (.ponytail/traces/) para que el agente quede auditable end-to-end.
    """

    def __init__(self, task_name: str, payload: dict | None = None) -> None:
        self.task_name = task_name or "unnamed-task"
        self.payload = payload or {}
        self.task_id = f"trace-{int(time.time() * 1000)}"
        self.events: list[dict] = []
        self.started_at = time.time()
        # Extraer circuit del payload para determinar el directorio
        self.circuit_id = self.payload.get("_circuit") or self.payload.get("circuit")
        # Session management
        self.session_id = self.payload.get("_session") or self.payload.get("session_id")
        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def _resolve_traces_dir(self) -> str:
        """Resuelve el directorio de trazas según el circuito activo.

        Prioridad:
        1. Directorio del circuito + subcarpeta de sesión
           (.ponytail/traces/<circuit>/<session_name>/)
        2. PONYTAIL_TRACES_DIR env var (override para tests, solo si NO hay sesión)
        3. Default fallback (/app/logs/ponytail)
        """
        if self.circuit_id:
            try:
                from app.tools.ponytail_trace_tools import _get_trace_dir_for_circuit

                trace_dir = _get_trace_dir_for_circuit(self.circuit_id)

                # Subcarpeta por sesión: <circuit>/<session_name>/
                if self.session_id:
                    import re

                    date_str = time.strftime("%Y-%m-%d")
                    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", self.task_name[:40])
                    safe_name = safe_name.strip("_").lower()
                    session_dir = f"{date_str}_{safe_name}_{self.session_id}"
                    trace_dir = trace_dir / session_dir

                return str(trace_dir)
            except Exception:
                pass

        # Fallback: env var override (solo si no hay circuito/sesión)
        env_override = os.environ.get("PONYTAIL_TRACES_DIR")
        if env_override:
            return env_override

        return PONYTAIL_TRACES_DIR

    def __enter__(self) -> "PonytailTrace":
        traces_dir = self._resolve_traces_dir()
        try:
            os.makedirs(traces_dir, exist_ok=True)
        except Exception:
            pass
        self._log(
            "start",
            {
                "task": self.task_name,
                "payload_keys": list(self.payload.keys()),
                "circuit": self.circuit_id,
                "traces_dir": traces_dir,
            },
        )
        log.info(
            "[ponytail] trace %s START task=%s circuit=%s dir=%s",
            self.task_id,
            self.task_name,
            self.circuit_id,
            traces_dir,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._log("end", {"duration_s": round(time.time() - self.started_at, 3)})
        traces_dir = self._resolve_traces_dir()
        log.info(
            "[ponytail] trace %s END duration=%.3fs dir=%s",
            self.task_id,
            time.time() - self.started_at,
            traces_dir,
        )

        # 1) Siempre persistir JSON crudo (compatibilidad / debugging)
        try:
            with open(f"{traces_dir}/{self.task_id}.json", "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "task_id": self.task_id,
                        "task_name": self.task_name,
                        "circuit": self.circuit_id,
                        "traces_dir": traces_dir,
                        "started_at": self.started_at,
                        "ended_at": time.time(),
                        "events": self.events,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as exc:
            log.debug("Ponytail no pudo persistir trace JSON: %s", exc)

        # 2) Persistir Markdown renderizable a .ponytail/traces/<circuit>/<id>.md
        #    y commitear a git en el repo del circuito
        if self.circuit_id and self.circuit_id != "_internal":
            try:
                self._persist_markdown_trace()
            except Exception as exc:
                log.warning("[ponytail] No se pudo persistir MD trace: %s", exc)

    def _persist_markdown_trace(self) -> None:
        """Serializa la traza a Markdown con YAML frontmatter + GFM + Mermaid,
        la guarda en .ponytail/traces/<circuit>/<id>.md y la commitea
        en el repo del circuito via ponytail_record_trace.

        No-op si el circuito es 'libre' (no commitea en /tmp/free-agent).
        """
        from app.tools.ponytail_trace_tools import (
            ponytail_record_trace,
            trace_to_markdown,
        )

        # workspace del circuito
        from app.openhands_agent.circuits import CIRCUITS

        cfg = CIRCUITS.get(self.circuit_id) if self.circuit_id else None
        workspace = cfg.workspace_dir if cfg else ""

        trace_data = {
            "task_name": self.task_name,
            "started_at": self.started_at,
            "ended_at": time.time(),
            "events": self.events,
            "workspace": workspace,
        }

        markdown = trace_to_markdown(self.task_id, self.circuit_id, trace_data)

        # Construir session_dir para subcarpeta por sesión
        session_dir = ""
        if self.session_id:
            import re

            date_str = time.strftime("%Y-%m-%d")
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", self.task_name[:40])
            safe_name = safe_name.strip("_").lower()
            session_dir = f"{date_str}_{safe_name}_{self.session_id}"

        # Llamar a la tool MCP que ya maneja la persistencia + commit
        result = ponytail_record_trace(
            config=None,
            arguments={
                "trace_id": self.task_id,
                "circuit": self.circuit_id,
                "markdown": markdown,
                "auto_commit": True,
                "session_dir": session_dir,
            },
        )
        log.info(
            "[ponytail] MD trace %s → %s (committed=%s)",
            self.task_id,
            result.get("file_path"),
            result.get("committed"),
        )
        # Registrar el evento en la traza misma (post-mortem)
        self.events.append(
            {
                "event": "ponytail_recorded",
                "ts": time.time(),
                "data": {
                    "file_path": result.get("file_path"),
                    "committed": result.get("committed"),
                    "commit_error": result.get("commit_error"),
                },
            }
        )

    def _log(self, event: str, data: dict | None = None) -> None:
        self.events.append({"event": event, "ts": time.time(), "data": data or {}})

    def record_event(self, event: str, data: dict | None = None) -> None:
        """API pública para hooks de omp: registra un evento en la traza.

        Equivalente a _log() pero pensado para ser llamado desde fuera
        de la clase (ej: OmpClient._on_message_update, OmpClient._on_tool_start, etc.).
        """
        self._log(event, data)


# ─────────────────────────────────────────────────────────────────────
# OpenHandsService
# ─────────────────────────────────────────────────────────────────────


class OpenHandsService:
    def is_available(self) -> bool:
        return OPENHANDS_AVAILABLE

    def list_models(self) -> dict:
        """GET /v1/models — lista OpenAI-compatible de modelos."""
        available = OPENHANDS_AVAILABLE
        models = [
            {
                "id": "openhands-agent-v1",
                "object": "model",
                "created": 1700000000,
                "owned_by": "openhands",
                "available": available,
            },
            {
                "id": "codevibing-agent",
                "object": "model",
                "created": 1700000000,
                "owned_by": "openhands",
                "available": available,
            },
        ]
        # Incluir cada circuito como modelo "virtual" para que clientes que
        # enrutan por modelo puedan elegir circuito.
        from app.openhands_agent.circuits import CIRCUITS, circuit_manager

        for cid, cfg in CIRCUITS.items():
            models.append(
                {
                    "id": f"circuit/{cid}",
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": "openhands",
                    "available": circuit_manager.is_ready(cid),
                    "circuit": cid,
                    "workspace": cfg.workspace_dir,
                }
            )
        return {
            "object": "list",
            "data": models,
            "backend": "openhands",
            "stack": {
                "openhands_sdk": OPENHANDS_AVAILABLE,
                "oh_my_pi_omp_rpc": OMP_AVAILABLE,
                "ponytail_rules_bytes": len(PONYTAIL_RULES),
                "sourcebot_url": SOURCEBOT_URL,
                "circuits": circuit_manager.status(),
            },
        }

    def backend_status(self) -> dict:
        from app.openhands_agent.circuits import circuit_manager

        return {
            "backend": "openhands",
            "runtime_available": OPENHANDS_AVAILABLE,
            "stack": {
                "oh_my_pi_omp_rpc": OMP_AVAILABLE,
                "ponytail_rules_loaded": bool(PONYTAIL_RULES),
                "ponytail_rules_bytes": len(PONYTAIL_RULES),
                "sourcebot_url": SOURCEBOT_URL,
                "circuits": circuit_manager.status(),
            },
        }

    def reload_backend(self) -> dict:
        global PONYTAIL_RULES
        try:
            with open("/app/vendor/ponytail/AGENTS.md", "r", encoding="utf-8") as _f:
                PONYTAIL_RULES = _f.read()
            log.info("Ponytail ruleset recargado (%d bytes).", len(PONYTAIL_RULES))
        except Exception as exc:
            log.error("No se pudo recargar ponytail: %s", exc)
        return self.backend_status()

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _extract_user_prompt(payload: dict) -> str:
        messages = payload.get("messages") or []
        user_msgs = [
            m for m in messages if isinstance(m, dict) and m.get("role") == "user"
        ]
        if user_msgs:
            content = user_msgs[-1].get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
                return "\n".join(parts)
            return str(content)
        return payload.get("prompt", "") or ""

    def _build_final_prompt(self, user_prompt: str, sourcebot_hits: list[dict]) -> str:
        sections: list[str] = []
        if PONYTAIL_RULES:
            sections.append(PONYTAIL_RULES.strip())
        if sourcebot_hits:
            sections.append("# Code Context (from Sourcebot)")
            for hit in sourcebot_hits[:5]:
                # Sourcebot v5.0.4 format: { fileName: {text, matchRanges},
                #                            path: null o string, chunks: [...] }
                fn = hit.get("fileName")
                if isinstance(fn, dict):
                    file_name = fn.get("text", "?")
                else:
                    file_name = str(fn) if fn else "?"
                path = hit.get("path") or file_name
                # Inferir repo del path (formato: github.com/user/repo/...)
                repo = hit.get("repo", "?")
                if repo == "?" and "/" in path:
                    parts = path.split("/")
                    if len(parts) >= 3:
                        repo = "/".join(parts[:3])  # github.com/user/repo
                # Extraer snippet de chunks
                snippet = ""
                chunks = hit.get("chunks", [])
                if chunks and isinstance(chunks, list):
                    snippet = chunks[0].get("content", "")[:400]
                if not snippet:
                    snippet = hit.get("content") or hit.get("snippet") or ""
                    snippet = snippet[:400]
                sections.append(
                    f"### {repo} :: {path}\nFile: {file_name}\n```\n{snippet}\n```"
                )
        sections.append("# User Task")
        sections.append(user_prompt)
        return "\n\n---\n\n".join(sections)

    def _to_openai_completion(self, raw: Any, payload: dict) -> dict:
        model_name = payload.get("model", "openhands-agent-v1")
        content = str(raw) if raw is not None else ""
        return {
            "id": f"chatcmpl-openhands-{os.getpid()}-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    # ── ejecución principal ────────────────────────────────────

    def run_task(self, payload: dict) -> dict:
        """Ejecuta un prompt usando OpenHands Agent Server como orquestador.

        Flujo:
        1. Detectar circuito y session
        2. Iniciar PonytailTrace
        3. Fetch governance (solo primer mensaje)
        4. Delegar a OpenHandsOrchestrator
        5. Persistir traza
        """
        from app.openhands_agent.open_hands_service import OpenHandsOrchestrator

        log.info("OpenHands run_task invocado.")
        user_prompt = self._extract_user_prompt(payload)
        if not user_prompt:
            return {
                "status": "error",
                "details": "No user prompt found in payload.",
            }

        # 0) Detectar circuito
        from app.openhands_agent.circuits import (
            CIRCUITS,
            detect_circuit,
        )

        force = payload.get("circuit")
        circuit_id = detect_circuit(user_prompt, force=force)
        circuit_cfg = CIRCUITS[circuit_id]
        log.info("[circuits] prompt → circuito '%s'", circuit_id)

        # 0b) Session management
        session_id = payload.get("session_id")
        is_new_session = session_id is None
        if is_new_session:
            import uuid

            session_id = uuid.uuid4().hex[:12]
            log.info("[session] nueva sesión: %s", session_id)
        else:
            log.info("[session] reutilizando sesión: %s", session_id)

        # 1) Iniciar traza con Ponytail
        with PonytailTrace(
            task_name=user_prompt,
            payload={**payload, "_circuit": circuit_id, "_session": session_id},
        ) as trace:
            trace._log(
                "circuit_selected",
                {
                    "id": circuit_id,
                    "workspace": circuit_cfg.workspace_dir,
                    "session_id": session_id,
                    "is_new_session": is_new_session,
                },
            )

            # 2) Governance injection (solo en primer mensaje de sesión)
            governance_context = ""
            if is_new_session:
                governance_context = self._fetch_governance(trace)
                trace._log(
                    "governance_injected",
                    {
                        "onboarding_len": len(governance_context),
                        "is_new_session": True,
                    },
                )
            else:
                trace._log(
                    "governance_skipped",
                    {
                        "reason": "session_continuation",
                        "session_id": session_id,
                    },
                )

            # 3) Delegar a OpenHands Agent Server
            orchestrator = OpenHandsOrchestrator()
            try:
                result = orchestrator.run_task(
                    prompt=user_prompt,
                    circuit_id=circuit_id,
                    session_id=session_id,
                    governance_context=governance_context,
                    trace=trace,
                )
            finally:
                orchestrator.close()

            # 4) Construir respuesta OpenAI-compatible
            if result.get("status") == "ok":
                completion = self._to_openai_completion(
                    result.get("response", ""), payload
                )
                completion["circuit"] = circuit_id
                completion["session_id"] = result.get("session_id", session_id)
                return completion
            else:
                return {
                    "status": "error",
                    "details": result.get("details", "Unknown error"),
                    "circuit": circuit_id,
                    "session_id": session_id,
                }

        # 0) Detectar circuito
        from app.openhands_agent.circuits import (
            CIRCUITS,
            circuit_manager,
            detect_circuit,
        )

        force = payload.get("circuit")
        circuit_id = detect_circuit(user_prompt, force=force)
        circuit_cfg = CIRCUITS[circuit_id]
        log.info("[circuits] prompt → circuito '%s'", circuit_id)

        # 0b) Session management
        session_id = payload.get("session_id")
        is_new_session = session_id is None
        if is_new_session:
            import uuid

            session_id = uuid.uuid4().hex[:12]
            log.info("[session] nueva sesión: %s", session_id)
        else:
            log.info("[session] reutilizando sesión: %s", session_id)

        # 1) Iniciar traza con Ponytail
        with PonytailTrace(
            task_name=user_prompt,
            payload={**payload, "_circuit": circuit_id, "_session": session_id},
        ) as trace:
            trace._log(
                "circuit_selected",
                {
                    "id": circuit_id,
                    "workspace": circuit_cfg.workspace_dir,
                    "session_id": session_id,
                    "is_new_session": is_new_session,
                },
            )

            # 2) Governance injection (solo en primer mensaje de sesión)
            governance_context = ""
            if is_new_session:
                governance_context = self._fetch_governance(trace)
                trace._log(
                    "governance_injected",
                    {
                        "onboarding_len": len(governance_context),
                        "is_new_session": True,
                    },
                )
            else:
                trace._log(
                    "governance_skipped",
                    {"reason": "session_continuation", "session_id": session_id},
                )

            # 3) Construir prompt final
            #    - Primer mensaje: governance + reglas circuito + user prompt
            #    - Mensajes siguientes: solo user prompt (omp ya tiene el contexto)
            final_prompt = self._build_session_prompt(
                user_prompt,
                circuit_cfg,
                governance_context,
                is_new_session,
            )

            # 3b) Loggear el system prompt en la traza para debugging
            trace._log(
                "system_prompt",
                {
                    "length": len(final_prompt),
                    "is_new_session": is_new_session,
                    "governance_chars": len(governance_context),
                    "preview": final_prompt[:800],
                    "circuit": circuit_id,
                    "workspace": circuit_cfg.workspace_dir,
                },
            )

            if not OPENHANDS_AVAILABLE:
                trace._log("error", {"reason": "openhands_sdk_unavailable"})
                return {
                    "status": "error",
                    "details": "OpenHands SDK not available.",
                    "stack_status": self.backend_status(),
                    "circuit": circuit_id,
                    "session_id": session_id,
                }

            # 4) Obtener o crear la conversación persistente del circuito
            try:
                conv = circuit_manager.get_or_create(circuit_id)
                if conv is None:
                    raise RuntimeError("circuit_manager returned None")
            except Exception as exc:
                log.error(
                    "Error creando circuito %s: %s", circuit_id, exc, exc_info=True
                )
                trace._log("error", {"exception": str(exc)})
                return {
                    "status": "error",
                    "details": f"Error inicializando circuito '{circuit_id}': {exc}",
                    "circuit": circuit_id,
                    "session_id": session_id,
                }

            # 4b) Attach trace al OmpClient
            if type(conv).__name__ == "OmpClient" and hasattr(conv, "set_trace"):
                conv.set_trace(trace)

            # 5) Invocar omp
            try:
                if (
                    type(conv).__name__ == "OmpClient"
                    and hasattr(conv, "set_trace")
                    and getattr(conv, "_trace", None) is None
                ):
                    conv.set_trace(trace)

                result_text = self._invoke_on_circuit(conv, final_prompt)
                trace._log(
                    "openhands_invoke", {"circuit": circuit_id, "len": len(result_text)}
                )
                completion = self._to_openai_completion(result_text, payload)
                completion["circuit"] = circuit_id
                completion["session_id"] = session_id
                return completion
            except Exception as exc:
                log.error(
                    "Error ejecutando OpenHands en %s: %s",
                    circuit_id,
                    exc,
                    exc_info=True,
                )
                trace._log("error", {"exception": str(exc)})
                return {
                    "status": "error",
                    "details": f"An error occurred during OpenHands execution: {exc}",
                    "circuit": circuit_id,
                    "session_id": session_id,
                }

    def _build_circuit_prompt(
        self,
        user_prompt: str,
        sourcebot_hits: list[dict],
        circuit_cfg: Any,
    ) -> str:
        """Construye el prompt final con: Ponytail AGENTS.md + reglas del circuito
        + contexto Sourcebot + prompt del usuario."""
        sections: list[str] = []

        # 1) Identidad base
        if PONYTAIL_RULES:
            sections.append(PONYTAIL_RULES.strip())

        # 2) Reglas específicas del circuito
        sections.append(f"# Circuit: {circuit_cfg.id}\n{circuit_cfg.description}")
        sections.append(self._circuit_tool_list(circuit_cfg))

        # 3) Contexto de Sourcebot (RAG)
        if sourcebot_hits:
            sections.append("# Code Context (from Sourcebot)")
            sections.append(
                "Los siguientes archivos fueron encontrados por Sourcebot "
                "en los repos indexados. Usalos como contexto para tu trabajo."
            )
            for hit in sourcebot_hits[:5]:
                enriched = _enrich_sourcebot_hit(hit)
                repo = enriched.get("repo", "?")
                fname = enriched.get("fileName", "?")
                lang = enriched.get("language", "?")
                line = enriched.get("line", "?")
                snippet = enriched.get("snippet", "")[:400]
                sections.append(
                    f"### {repo} :: {fname} (line {line}, {lang})\n```\n{snippet}\n```"
                )

        # 4) Prompt del usuario
        sections.append("# User Task")
        sections.append(user_prompt)

        return "\n\n---\n\n".join(sections)

    def _fetch_governance(self, trace: Any) -> str:
        """Llama las 3 MCP governance tools y devuelve el contexto concatenado.

        Esto se hace UNA SOLA VEZ por sesión (primer mensaje).
        El resultado se inyecta en el system prompt de omp para que tenga
        toda la información de onboarding, reglas y configuración.

        Las governance tools son:
        - get_onboarding(): workspace info, MCP tools, circuitos
        - get_rules(): reglas operativas del agente
        - get_config(): configuración del backend (redactada)
        """
        from app.services.registry_service import registry_service

        registry = registry_service()
        sections: list[str] = []

        for tool_name in ("get_onboarding", "get_rules", "get_config"):
            try:
                result = registry.call(tool_name, {})
                text = self._extract_governance_text(tool_name, result)

                if text and len(text.strip()) > 10:
                    sections.append(f"## {tool_name}\n\n{text.strip()}")
                    log.info("[governance] %s: %d chars", tool_name, len(text))
                    trace._log(
                        "governance_tool",
                        {"tool": tool_name, "chars": len(text)},
                    )
                else:
                    log.warning("[governance] %s: respuesta vacía", tool_name)
                    trace._log(
                        "governance_tool",
                        {"tool": tool_name, "chars": 0, "warning": "empty"},
                    )
            except Exception as exc:
                log.warning("[governance] %s error: %s", tool_name, exc)
                trace._log(
                    "governance_tool",
                    {"tool": tool_name, "error": str(exc)[:200]},
                )

        return "\n\n---\n\n".join(sections)

    @staticmethod
    def _extract_governance_text(tool_name: str, result) -> str:
        """Extrae el texto de la respuesta de una governance tool.

        Cada tool devuelve un formato distinto:
        - get_onboarding: {content: "texto"} o {result: "texto"}
        - get_rules: {content: "texto"} o {raw: {main: "texto"}}
        - get_config: {config: {...}} → serializar a YAML-like

        Filtra errores de parsing (ej: Cypher errors de codebase-memory-mcp).
        """
        import json

        if not isinstance(result, dict):
            text = str(result) if result else ""
            # Filtrar errores de parsing conocidos
            if (
                text.startswith("('")
                or text.startswith("Error:")
                or "traceback" in text.lower()
            ):
                return ""
            return text

        # get_onboarding y get_rules: content directo
        content = result.get("content", "")
        if isinstance(content, str) and len(content) > 10:
            # Filtrar errores de Cypher/parsing
            if (
                content.startswith("('")
                or content.startswith("Error:")
                or "traceback" in content.lower()
            ):
                return ""
            return content

        # get_rules: raw.main
        raw = result.get("raw", {})
        if isinstance(raw, dict):
            main_text = raw.get("main", "")
            if isinstance(main_text, str) and len(main_text) > 10:
                return main_text

        # get_config: serializar el dict de config
        config = result.get("config", {})
        if isinstance(config, dict) and config:
            return json.dumps(config, indent=2, ensure_ascii=False)

        # Fallback: result como string
        r = result.get("result", "")
        if isinstance(r, str) and len(r) > 10:
            if r.startswith("('") or r.startswith("Error:"):
                return ""
            return r
        if isinstance(r, list) and r:
            text = r[0].get("text", "") if isinstance(r[0], dict) else str(r[0])
            if text.startswith("('") or text.startswith("Error:"):
                return ""
            return text

        return ""

    def _build_session_prompt(
        self,
        user_prompt: str,
        circuit_cfg: Any,
        governance_context: str,
        is_new_session: bool,
    ) -> str:
        """Construye el prompt para omp según si es primer mensaje o continuación.

        Primer mensaje de sesión:
          - Ponytail AGENTS.md (identidad base)
          - Governance context (onboarding + rules + config)
          - Reglas del circuito
          - Sourcebot info (como tool, no como pre-search)
          - User prompt

        Mensajes siguientes (continuación de sesión):
          - Solo user prompt
          - (omp ya tiene el contexto de governance en su historial)
        """
        sections: list[str] = []

        if is_new_session:
            # 1) Identidad base (Ponytail AGENTS.md)
            if PONYTAIL_RULES:
                sections.append(PONYTAIL_RULES.strip())

            # 2) Governance context (onboarding + rules + config)
            if governance_context:
                sections.append(governance_context)

            # 3) Reglas del circuito
            sections.append(
                f"# Circuit: {circuit_cfg.id}\n"
                f"{circuit_cfg.description}\n\n"
                f"Workspace: {circuit_cfg.workspace_dir}\n"
                f"Git action: {circuit_cfg.git_action}"
            )

            # 4) Sourcebot info (disponible como tool, no como pre-search)
            sections.append(
                "# Sourcebot (búsqueda de código)\n\n"
                "Tenés acceso a Sourcebot como tool MCP `sourcebot_search`.\n"
                "Endpoint: `http://conti-sourcebot:3000/api/search`\n"
                'Método: POST con `{"query": "keywords", "matches": N}`\n'
                "Funciona mejor con queries cortas (1-3 keywords técnicas).\n"
                "NO requiere autenticación.\n"
            )

            # 5) User prompt
            sections.append("# User Task")
            sections.append(user_prompt)
        else:
            # Continuación de sesión: solo el user prompt
            # omp ya tiene todo el contexto en su historial
            sections.append(user_prompt)

        return "\n\n---\n\n".join(sections)

    def _circuit_tool_list(self, cfg: Any) -> str:
        """Devuelve la lista compacta de tools disponibles para este circuito."""
        lines = ["## Tools disponibles en este circuito"]
        if cfg.allowed_tools_native:
            lines.append(f"- Nativas OpenHands: {', '.join(cfg.allowed_tools_native)}")
        else:
            lines.append(
                "- Nativas OpenHands: **NINGUNA** (este circuito no edita archivos)"
            )
        if cfg.allowed_mcp_categories:
            lines.append(f"- MCP categories: {', '.join(cfg.allowed_mcp_categories)}")
        lines.append(f"- Git action permitida: **{cfg.git_action}**")
        return "\n".join(lines)

    def _invoke_on_circuit(self, conv: Any, prompt: str) -> str:
        """Envía el prompt a la conversación persistente del circuito y
        devuelve el contenido del último mensaje del agente.

        Soporta dos tipos de conversación:
        - OpenHands SDK legacy: usa send_message() + run()
        - OmpClient (oh-my-pi via conti-omp): usa prompt_and_wait()
        """
        # Detectar tipo de conversación
        is_omp = (
            hasattr(conv, "prompt_and_wait") and not hasattr(conv, "send_message")
        ) or type(conv).__name__ == "OmpClient"

        if is_omp:
            # OmpClient (oh-my-pi): prompt_and_wait() ejecuta y devuelve texto
            log.info(
                "[omp] invoking via prompt_and_wait (conv=%s)", type(conv).__name__
            )
            try:
                result_text = conv.prompt_and_wait(prompt)
                if result_text and result_text.strip():
                    return result_text
                # Si devolvió vacío, es un caso edge: omp ejecutó tools
                # pero no produjo un mensaje final. Devolvemos un placeholder
                # útil en lugar de string vacío.
                log.warning(
                    "[omp] prompt_and_wait devolvió respuesta vacía. "
                    "Posible causa: omp ejecutó tools sin mensaje final."
                )
                return (
                    "[omp ejecutó el prompt pero no devolvió un mensaje final. "
                    "Esto puede pasar cuando el prompt no requiere una "
                    "respuesta textual (ej: solo ejecutar acciones o "
                    "explorar archivos). Si esperás una respuesta, "
                    "formulá el prompt pidiendo explícitamente una "
                    "respuesta textual (ej: 'Decime X', 'Resumí Y').]"
                )
            except Exception as exc:
                log.error("[omp] prompt_and_wait falló: %s", exc, exc_info=True)
                return f"[omp error: {exc}]"

        # OpenHands SDK legacy: send_message() + run() + extraer último evento
        conv.send_message(prompt)
        conv.run()

        try:
            state = conv.state
            events = getattr(state, "events", []) or []
            # Buscar el último evento del agente que tenga contenido textual.
            # Orden de preferencia:
            #   1. MessageEvent del agente (llm_message.content: list[TextContent])
            #   2. ActionEvent con FinishAction (action.message)
            #   3. ActionEvent con reasoning_content (pensamiento)
            for ev in reversed(events):
                cls = type(ev).__name__
                src = getattr(ev, "source", None)
                # Solo eventos del agente
                if src not in ("agent", None):
                    continue
                if cls == "MessageEvent":
                    # El content vive en ev.llm_message.content (list[TextContent])
                    llm_msg = getattr(ev, "llm_message", None)
                    if llm_msg is not None:
                        content = getattr(llm_msg, "content", None)
                        text = self._extract_text(content)
                        if text:
                            return text
                    # Fallback a otros atributos
                    for attr in ("message", "content"):
                        v = getattr(ev, attr, None)
                        text = self._extract_text(v)
                        if text:
                            return text
                elif cls == "ActionEvent":
                    action = getattr(ev, "action", None)
                    if action is not None:
                        msg = getattr(action, "message", None)
                        if msg:
                            return str(msg)
                    reasoning = getattr(ev, "reasoning_content", None)
                    if reasoning:
                        return str(reasoning)
        except Exception as exc:
            log.debug("No se pudo extraer último mensaje del state: %s", exc)
        return f"[Circuito ejecutó el prompt pero no devolvió contenido. Conv ID: {conv.id}]"

    def _extract_text(self, v: Any) -> str:
        """Extrae texto de un campo que puede ser str, list[TextContent], etc."""
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, list):
            parts: list[str] = []
            for item in v:
                if isinstance(item, str):
                    parts.append(item)
                elif hasattr(item, "text"):
                    # TextContent (OpenHands SDK)
                    t = str(item.text)
                    if t:
                        parts.append(t)
                elif hasattr(item, "content"):
                    parts.append(str(item.content))
            if parts:
                return "\n".join(parts)
        return ""

    # ── streaming OpenAI-compatible ────────────────────────────

    async def stream_chat_completions(
        self, payload: dict, auth_header: str = ""
    ) -> AsyncIterator[bytes]:
        result = await asyncio.to_thread(self.run_task, payload)

        model_name = payload.get("model", "openhands-agent-v1")
        completion_id = result.get("id", f"chatcmpl-openhands-{int(time.time())}")
        content = ""
        if "choices" in result and result["choices"]:
            content = result["choices"][0].get("message", {}).get("content", "")
        elif "details" in result:
            content = f"[error] {result['details']}"

        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"


openhands_service = OpenHandsService()
