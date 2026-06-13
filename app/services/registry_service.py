from __future__ import annotations

from functools import lru_cache

from app.config.loader import load_config
from app.core import categories, visibility
from app.core.tool_models import ToolDefinition
from app.core.tool_registry import ToolRegistry
from app.tools import config_tools, container_tools, document_tools, filesystem, git_tools, rag_tools, rag_search_tools, search_literal, system_status, translation_tools, catolico_tools

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
        self._registry.register(
            ToolDefinition(
                name="start_markdown_translation",
                description="Inicia traducción de Markdown en background y devuelve job_id para seguimiento.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "input_path": {"type": "string"},
                        "output_path": {"type": "string"},
                        "source_lang": {"type": "string"},
                        "target_lang": {"type": "string"},
                        "chunk_size": {"type": "integer"},
                        "retries": {"type": "integer"},
                        "overwrite": {"type": "boolean"},
                    },
                    "required": ["input_path"],
                },
                visibility=visibility.PUBLIC,
                tags=["translation", "background", "markdown"],
            ),
            lambda args: translation_tools.start_markdown_translation(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_translation_job",
                description="Consulta estado y progreso de un job de traducción.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                    },
                    "required": ["job_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["translation", "status", "read-only"],
            ),
            lambda args: translation_tools.get_translation_job(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="list_translation_jobs",
                description="Lista jobs recientes de traducción y su estado.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["translation", "status", "read-only"],
            ),
            lambda args: translation_tools.list_translation_jobs(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="start_pdf_to_markdown",
                description="Convierte un PDF (URL o ruta local) a Markdown en background y devuelve job_id. Si no se pasa output_path, guarda por defecto en /compose/documentos_listos/{store}/. Opcionalmente inicia traducción automática al terminar.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "URL o ruta local al PDF/documento"},
                        "store": {"type": "string", "description": "Store destino para output por defecto (default: config.rag.default_store)"},
                        "output_path": {"type": "string", "description": "Ruta de salida del .md (opcional)"},
                        "also_translate": {"type": "boolean", "description": "Si es true lanza traducción al terminar"},
                        "target_lang": {"type": "string", "description": "Idioma destino si also_translate=true (default: en)"},
                    },
                    "required": ["source"],
                },
                visibility=visibility.PUBLIC,
                tags=["document", "pdf", "markdown", "background"],
            ),
            lambda args: document_tools.start_pdf_to_markdown(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_md_conversion_job",
                description="Consulta estado de un job de conversión PDF/documento a Markdown.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                    },
                    "required": ["job_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["document", "status", "read-only"],
            ),
            lambda args: document_tools.get_md_conversion_job(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="list_md_conversion_jobs",
                description="Lista jobs recientes de conversión PDF/documento a Markdown.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["document", "status", "read-only"],
            ),
            lambda args: document_tools.list_md_conversion_jobs(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="start_rag_ingest",
                description=(
                    "Ingesta un documento (URL o ruta local) en el RAG Flamehaven. "
                    "Convierte a Markdown preservando el nombre original y lo sube a una colección (store). "
                    "Devuelve job_id inmediatamente; el proceso ocurre en background."
                ),
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "URL o ruta local al documento (PDF, DOCX, etc.)"},
                        "store": {"type": "string", "description": "Colección destino en Flamehaven (default: config rag.default_store)"},
                        "original_name": {"type": "string", "description": "Nombre descriptivo para identificar el doc en el índice"},
                        "overwrite": {"type": "boolean", "description": "Si true y ya existe un doc con el mismo nombre, lo reemplaza. Si false (default) rechaza el duplicado informando el doc existente."},
                    },
                    "required": ["source"],
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "document", "ingest", "background"],
            ),
            lambda args: rag_tools.start_rag_ingest(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="get_rag_ingest_job",
                description="Consulta estado de un job de ingestión RAG en Flamehaven.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                    },
                    "required": ["job_id"],
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "status", "read-only"],
            ),
            lambda args: rag_tools.get_rag_ingest_job(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="list_rag_ingest_jobs",
                description="Lista jobs recientes de ingestión RAG en Flamehaven.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "status", "read-only"],
            ),
            lambda args: rag_tools.list_rag_ingest_jobs(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="scan_documentos_nuevos",
                description=(
                    "Escanea /compose/documentos_nuevos/{store}/ y lanza un job de ingesta por cada archivo. "
                    "Los archivos se mueven a procesados/ al ser encolados. "
                    "Opcionalmente puede incluir archivos ya movidos en procesados/. "
                    "Usa store='all' para escanear todos los stores. "
                    "Usa dry_run=true para previsualizar sin ingestar. "
                    "Usa max_files para limitar cuántos archivos encola por request. "
                    "overwrite=false (default): rechaza documentos con nombre ya existente en el store. "
                    "overwrite=true: reemplaza el doc anterior."
                ),
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "store": {"type": "string", "description": "Store a escanear, o 'all' para todos (default: config.rag.default_store)"},
                        "dry_run": {"type": "boolean", "description": "Solo listar archivos sin ingestar"},
                        "max_files": {"type": "integer", "description": "Límite de archivos por llamada para evitar timeout (ej: 25, 50, 100)."},
                        "overwrite": {"type": "boolean", "description": "Si true reemplaza docs existentes con el mismo nombre. Default: false."},
                        "include_procesados": {"type": "boolean", "description": "Si true incluye tambien documentos_nuevos/{store}/procesados para auditoria o reingesta."},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "ingest", "scan"],
            ),
            lambda args: rag_tools.scan_documentos_nuevos(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="search_rag",
                    description=(
                        "Búsqueda completa en el RAG Flamehaven con respuesta generada por LLM (Gemini). "
                    "Soporta modos: hybrid (recomendado, fusiona BM25+semántico), semantic, keyword. "
                    "Usar cuando Conti necesita RESPONDER algo al usuario basándose en documentos. "
                    "Devuelve answer, sources, search_confidence [0-1] y low_confidence si los resultados son débiles."
                ),
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Pregunta o consulta a buscar"},
                        "store": {"type": "string", "description": "Colección destino (default: config rag.default_store)"},
                        "mode": {"type": "string", "enum": ["hybrid", "semantic", "keyword"], "description": "Modo de búsqueda (default: hybrid)"},
                        "top_k": {"type": "integer", "description": "Número de resultados (default: 5)"},
                        "threshold": {"type": "number", "description": "Umbral de similitud [0-1]"},
                        "max_tokens": {"type": "integer", "description": "Máx tokens para la respuesta LLM"},
                    },
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "search", "hybrid", "llm"],
            ),
            lambda args: rag_search_tools.search_rag(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="search_rag_quick",
                description=(
                    "Búsqueda rápida por keyword en Flamehaven SIN generar respuesta LLM. Solo devuelve sources y matched. "
                    "Usar cuando Conti necesita VERIFICAR si algo existe en el RAG o encadenar con otra tool. "
                    "No consume tokens de Gemini — instantáneo."
                ),
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Término o frase a buscar"},
                        "store": {"type": "string", "description": "Colección destino (default: config rag.default_store)"},
                        "top_k": {"type": "integer", "description": "Número de resultados (default: 5)"},
                    },
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "search", "keyword", "read-only"],
            ),
            lambda args: rag_search_tools.search_rag_quick(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="search_rag_semantic",
                description=(
                    "Búsqueda semántica en Flamehaven (DSP v2.0) con respuesta LLM. "
                    "Sin BM25 — usa únicamente vectores: ideal para queries conceptuales, sinónimos y paráfrasis. "
                    "Tolerante a typos. Usar cuando las palabras exactas no importan sino el concepto."
                ),
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Concepto o pregunta a buscar semánticamente"},
                        "store": {"type": "string", "description": "Colección destino (default: config rag.default_store)"},
                        "top_k": {"type": "integer", "description": "Número de resultados (default: 5)"},
                        "threshold": {"type": "number", "description": "Umbral de similitud [0-1]"},
                        "max_tokens": {"type": "integer", "description": "Máx tokens para la respuesta LLM"},
                    },
                    "required": ["query"],
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "search", "semantic", "llm"],
            ),
            lambda args: rag_search_tools.search_rag_semantic(load_config(), args),
        )
        self._registry.register(
            ToolDefinition(
                name="list_rag_store_docs",
                description=(
                    "Lista todos los documentos indexados en un store de Flamehaven. Sin búsqueda ni LLM. "
                    "Usar cuando Conti necesita saber QUÉ documentos hay guardados en el RAG (inventario). "
                    "Devuelve title, URI y metadata de cada doc."
                ),
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "store": {"type": "string", "description": "Colección a listar (default: config rag.default_store)"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["rag", "status", "read-only"],
            ),
            lambda args: rag_search_tools.list_rag_store_docs(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="catolico_lecturas_dia",
                description="Obtiene las lecturas del día para la liturgia católica.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "fecha": {"type": "string", "description": "Fecha de la cual extraer las lecturas (por defecto 'hoy')"},
                    },
                },
                visibility=visibility.PUBLIC,
                tags=["catolico", "api"],
            ),
            lambda args: catolico_tools.catolico_lecturas_dia(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="catolico_biblia_buscar",
                description="Busca citas bíblicas o versículos por palabras clave. Úsala EXCLUSIVAMENTE para referencias bíblicas.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "modo": {"type": "string", "description": "Define si se busca una 'cita' específica o una 'busqueda' por texto."},
                        "libro": {"type": "string", "description": "Nombre del libro bíblico (ej: Mateo)"},
                        "capitulo": {"type": "number", "description": "Número del capítulo. Requerido si modo='cita'"},
                        "versiculo_inicio": {"type": "number"},
                        "versiculo_fin": {"type": "number"},
                        "texto": {"type": "string", "description": "Texto o frase a buscar. Requerido si modo='busqueda'"},
                    },
                    "required": ["modo"]
                },
                visibility=visibility.PUBLIC,
                tags=["catolico", "biblia"],
            ),
            lambda args: catolico_tools.catolico_biblia_buscar(load_config(), args),
        )

        self._registry.register(
            ToolDefinition(
                name="catolico_leer_documento",
                description="Lee el contenido de un documento del RAG en texto completo. Usa esta tool si el usuario solicita un resumen o leer el documento completo de un resultado previo de search_rag.",
                category=categories.SYSTEM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "uri": {"type": "string", "description": "La URI o nombre del archivo markdown a leer"},
                    },
                    "required": ["uri"]
                },
                visibility=visibility.PUBLIC,
                tags=["catolico", "rag", "resumen"],
            ),
            lambda args: catolico_tools.catolico_leer_documento(load_config(), args),
        )

    def list_tools(self):
        return self._registry.list_tools()

    def call(self, tool_name: str, arguments: dict | None = None):
        return self._registry.call(tool_name, arguments)


@lru_cache(maxsize=1)
def registry_service() -> RegistryService:
    return RegistryService()