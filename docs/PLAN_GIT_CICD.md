# Plan de Acción — Git + CI/CD orquestador-contamela

**Repositorio**: https://github.com/luisdalmasso/orquestador-contamela  
**Fecha**: 2026-05-01  
**Estado**: En ejecución

---

## Fase 1 — Mover `conti_home` dentro del repositorio

- [x] Mover `/contenedores/conti_home` → `/contenedores/conti-backend/conti_home`
- [x] Actualizar `docker-compose.conti.yml`: bind mount de ruta absoluta a relativa
- [x] Crear `.gitignore` en `conti-backend/`

## Fase 2 — Inicializar el repositorio Git

- [x] `git init` en `/contenedores/conti-backend/`
- [x] `git remote add origin https://github.com/luisdalmasso/orquestador-contamela`
- [x] Commit inicial: `feat: v1.0.0 - versión estable inicial`
- [x] `git push -u origin main`

## Fase 3 — Reiniciar el contenedor con el nuevo bind mount

- [x] `docker compose -f docker-compose.conti.yml down`
- [x] `docker compose -f docker-compose.conti.yml up -d`
- [x] Verificar health

---

## Ciclo de Vida CI/CD

```
main         = versiones estables numeradas   v1.0.0 → v1.1.0 → v2.0.0
                          ▲
                  merge + tag vX.X.X
                          │
develop      = integración de subversiones    v1.0.1 → v1.0.2 → v1.0.3
                          ▲
                  merge cuando pasa QA
                          │
feature/fix  = trabajo diario                 fix/nombre  |  feature/nombre
```

### Convención SemVer

| Tipo | Cuándo | Ejemplo |
|------|--------|---------|
| MAJOR `v2.0.0` | Cambio de arquitectura / breaking change | Nuevo orquestador |
| MINOR `v1.1.0` | Feature nueva estable | Tools MCP en nanobot |
| PATCH `v1.0.1` | Bugfix sin romper nada | Fix normalize payload |

### Flujo diario

```bash
# 1. Rama de fix/feature
git checkout -b fix/nombre-del-bug

# 2. Commit descriptivo
git commit -m "fix: descripción del problema y solución"

# 3. Push y merge a develop
git push origin fix/nombre-del-bug

# 4. Cuando develop está estable → merge a main + tag
git checkout main
git merge develop
git tag -a v1.0.1 -m "Patch: descripción"
git push origin main --tags
```

### Rollback a una versión anterior

Si algo sale mal al pasar a producción, el procedimiento es:

```bash
# 1. Identificar la última versión estable
git tag --sort=-version:refname | head -5

# 2. Opción A — Rollback rápido (solo el contenedor, sin tocar git)
#    Checkoutear el código de esa versión y rebuilder
git checkout v1.0.0          # el tag estable anterior
docker compose -f docker-compose.conti.yml down
docker compose -f docker-compose.conti.yml build --no-cache
docker compose -f docker-compose.conti.yml up -d

# 3. Opción B — Rollback completo (revertir main)
git checkout main
git revert HEAD              # crea un commit de reversión (seguro, no reescribe historia)
git push origin main
git tag -a v1.0.2 -m "Revert: rollback a estado estable"
git push origin main --tags

# 4. Volver a develop para continuar trabajando
git checkout develop
```

> **Regla de oro**: nunca hacer `git reset --hard` en `main`. Siempre usar `git revert`
> para mantener el historial limpio y poder auditar qué pasó.

---

## Infraestructura de Red y Exposición Pública

### Topología actual

```
Internet
    │
    ▼
https://ai.contamela.com/        ← Cloudflare Tunnel (cloudflared)
    │
    │  rutea internamente via red Docker "desarrollo_odoo-network-dev"
    ▼
http://conti-backend:9001        ← conti-backend FastAPI (puerto interno)
    │
    ├── /v1/chat/completions  →  nanobot serve (127.0.0.1:8765)
    ├── /v1/models
    ├── /health
    └── ...
```

### Detalles
- **Red Docker**: `desarrollo_odoo-network-dev` (externa, compartida con el stack de desarrollo)
- **cloudflared**: servicio en la misma red, tunneliza `http://conti-backend:9001` → `https://ai.contamela.com/`
- **Sin puertos expuestos al exterior**: todo el tráfico público pasa por el tunnel de Cloudflare
- **Puerto 9001**: solo accesible dentro de la red Docker o via el tunnel
- **Puerto 8765** (nanobot serve): solo accesible desde localhost dentro del contenedor

### Implicancias para el CI/CD
- Al hacer rollback o restart, el tunnel sigue activo — cloudflared no requiere reinicio
- El DNS `ai.contamela.com` resuelve siempre al tunnel de Cloudflare, no a la IP del servidor
- Para cambiar el endpoint público basta con reconfigurar el tunnel en el dashboard de Cloudflare
