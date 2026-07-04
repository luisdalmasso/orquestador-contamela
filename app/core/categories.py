"""
Categorías MCP del backend conti.

Estas categorías organizan las tools registradas en registry_service.py.
Cada tool tiene UNA category (enum cerrado) y N tags[] (open vocabulary).

Alineadas con MCP_CATEGORIES_* en app/openhands_agent/circuits.py para
que el filtro por circuito funcione realmente (antes el filtro usaba
strings hardcoded que no matcheaban con este enum).
"""

# Categorías base (existentes)
FILESYSTEM = "filesystem"
SEARCH = "search"
SYSTEM = "system"
CONFIG = "config"

# Categorías de dominio (alineadas con PLAN_3 §4 y circuits.py)
BOOTSTRAP = (
    "bootstrap"  # health_check, get_config, get_rules, get_onboarding, reload_config
)
STACK = "stack"  # get_container_health, get_container_logs, get_vps_status
RAG = "rag"  # search_rag*, start_rag_ingest*, scan_documentos_nuevos, list_rag_store_docs (Flamehaven)
SOURCEBOT = "sourcebot"  # sourcebot_search, sourcebot_list_repos, sourcebot_get_doc (Sourcebot v5.0.4)
GITOPS = "gitops"  # get_git_*, run_salvar, run_promover, run_hotfix_sync, get_pipeline_summary
ODOO = "odoo"  # odoo_* (21 tools)
DOCUMENTS = "documents"  # start_markdown_translation, start_pdf_to_markdown, *translation_job, *md_conversion_job
SHEETS = "sheets"  # sheet_account_*, sheet_lookup_partner, sheet_register_partner
CATOLICO = "catolico"  # catolico_*
CODE_EDIT = "code_edit"  # validate_python_syntax, run_pytest, detect_circuit_from_path
OBSERVABILITY = "observability"  # ponytail_record_trace (PLAN_3 §15.quinquies)


ALL_CATEGORIES = frozenset(
    {
        FILESYSTEM,
        SEARCH,
        SYSTEM,
        CONFIG,
        BOOTSTRAP,
        STACK,
        RAG,
        SOURCEBOT,
        GITOPS,
        ODOO,
        DOCUMENTS,
        SHEETS,
        CATOLICO,
        CODE_EDIT,
        OBSERVABILITY,
    }
)
