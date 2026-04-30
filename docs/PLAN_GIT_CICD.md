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
