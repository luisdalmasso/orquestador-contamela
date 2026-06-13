# Implementación Tenant Católico

## PASO 1: Infraestructura base
- [x] RedisSessionManager (memory.py)
- [x] TenantConfig Pydantic models (base.py)
- [x] TenantRegistry (registry.py)
- [x] ContextWriter (context_writer.py)
- [x] RedisConfig en app config (requirements.txt)

## PASO 2: Home del tenant católico
- [x] Crear estructura de carpetas `/contenedores/tenants/catolico/`
- [x] `.nanobot/config.json` (provider, MCP, sin telegram/heartbeat)
- [x] `workspace/SOUL.md`
- [x] `workspace/AGENTS.md`
- [x] `workspace/USER.md`
- [x] `workspace/CONSTANTS.md`
- [x] `workspace/TOOLS.md`
- [x] `context/` carpeta con archivos iniciales
- [x] `config.yaml` para FastAPI
- [x] Symlinks a skills (rag-manager, voice-manager, gemini-vision)

## PASO 3: Lanzar nanobot serve del tenant
- [x] Modificar entrypoint.sh para levantar serves de tenants
- [x] docker-compose: bind mount /tenants + puerto 8766
- [ ] Verificar arranque del serve católico (requiere rebuild)

## PASO 3.5: Pruebas de prompting
- [ ] T1: Saludo
- [ ] T2: Lecturas del día (RAG)
- [ ] T3: Biblia
- [ ] T4: Doctrina (RAG)
- [ ] T5: Fuera de tema

## PASO 4: Orquestador + endpoint
- [x] orchestrator.py
- [x] router.py (POST /v1/chat)
- [x] Registrar router en main.py
- [ ] Verificar imports y código compila

## PASO 5: Tests end-to-end
- [ ] curl al endpoint → respuesta correcta
- [ ] Memoria Redis (historial persiste)
- [ ] Integrar con n8n (reemplazar AI Agent por HTTP Request)
