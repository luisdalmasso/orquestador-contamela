# Rules — Conti Backend (actualizado PLAN_3 v1.5, 30/jun/2026)

## Reglas de vida o muerte

1. NUNCA ejecutar `git commit`, `git push`, `git merge`, `git reset`,
   `git rebase` directo en el shell del agente.
   Solo usar las tools dedicadas: `run_salvar` (preview), `run_promover`
   (preview), `run_hotfix_sync` (preview). Estas pasan por el Gatekeeper
   (`validate_diff`) antes de aplicar.

2. NUNCA ejecutar `bash /compose/3-despliegue.sh` ni
   `docker compose -f producion.yml up -d`. Solo Luis puede deployar.

3. Toda acción destructiva → preview + confirmación explícita (`confirm=true`).

4. Idioma: siempre Español.

5. `/compose` es RW SOLO para git (commit/push en main, git pull desde
   origin). Cambios de código en producción normalmente van por el flujo
   develop → main. Edición directa en `/compose` solo se permite para
   hotfixes urgentes.

## Reglas operacionales

6. Operar DENTRO del contenedor, sin SSH (los bind-mounts ya conectan el
   host con el working dir del agente).

7. Si la tarea accede a algo FUERA de `/desarrollo`, `/compose`,
   `/contenedores/conti-backend`, `/home/nanobot`: pedir credenciales a
   Luis explícitamente antes de proceder.

8. Acción sobre palabras: nada de "¡Gran pregunta!", "¡Excelente!", etc.
   Respuestas técnicas, directas y concisas.

9. Si Luis modificó archivos en `/compose` directamente, avisar del
   riesgo antes de cualquier operación: `3-despliegue.sh` puede hacer
   `git reset --hard` y borrar archivos uncommitted.

## Reglas MCP

10. Usar solo tools registradas por el backend (`get_rules`, `get_config`,
    `get_onboarding` las lista).
11. No inventar nombres de tools ni schemas.
12. Validar argumentos antes de ejecutar mutaciones.
13. Respetar allowlists de paths y visibilidades del circuito activo.

## Reglas de los 4 circuitos

14. `circuit: desarrollo` (workspace `/desarrollo`, branch `develop`):
    - `run_salvar` commitea y pushea a develop.
    - `run_promover` y `run_hotfix_sync` NO aplican acá.
    - Code editing: editar solo dentro de `/desarrollo`. Validar con
      `validate_python_syntax` y opcionalmente `run_pytest`.
    - **Trazas de Ponytail**: Se guardan en `/desarrollo/.ponytail/traces/`
      con formato `YYYY-MM-DD_desarrollo_tr-<hash>.md`.

15. `circuit: produccion` (workspace operativo `/desarrollo`, branch
    `develop` para promover; `/compose` para hotfix en main):
    - `run_promover` fusiona develop → main (merge --no-ff) + push main.
    - `run_hotfix_sync` commitea cambios en `/compose` (main) y los
      sincroniza a `/desarrollo` (develop) via merge --no-ff.
    - NO corre `3-despliegue.sh` (solo Luis).
    - El deploy real lo hace Luis fuera del agente.
    - Code editing: editar solo dentro de `/compose` (para hotfix) o
      `/desarrollo` (vía `run_promover` después). NO editar código
      en `/compose` para cambios normales — usar flujo develop→main.
    - **Trazas de Ponytail**:
      - Si el usuario edita archivos directamente en `/compose`, las trazas
        se guardan en `/compose/.ponytail/traces/` (rama `main`).
      - Si el usuario trabaja en `/desarrollo` y promueve a `main`, las trazas
        se guardan en `/desarrollo/.ponytail/traces/` (rama `develop`).

16. `circuit: backend` (workspace `/contenedores/conti-backend`, branch
    `main`):
    - `run_salvar` commitea y pushea a main directamente (este repo solo
      tiene main).
    - `run_promover` y `run_hotfix_sync` NO aplican.
    - **Code editing OBLIGATORIO pre-commit**:
      1. `validate_python_syntax(paths=[<archivos>])` → debe pasar.
      2. `run_pytest(circuit="backend", test_path=<módulo_afectado>)` →
         debe pasar.
      3. (Opcional pero recomendado) `run_pytest(circuit="backend")` →
         suite completa verde.
    - Si validate_python_syntax falla → NO commitear, arreglar primero.
    - Si run_pytest falla → NO commitear, arreglar primero.
    - **Trazas de Ponytail**: Se guardan en `/contenedores/conti-backend/.ponytail/traces/`
      con formato `YYYY-MM-DD_backend_tr-<hash>.md`.

17. `circuit: libre` (workspace `/tmp/free-agent`):
    - SIN acceso a repos git. No tools nativas.
    - Categorías MCP permitidas: bootstrap, rag, odoo, documents, sheets,
      catolico, filesystem. **NO** tiene gitops, stack, code_edit.
    - Si Luis pasa una ruta del host no bind-mounted, pedir credenciales.
    - Si la tarea requiere editar código: usar `detect_circuit_from_path`
      primero para saber a qué circuito mandar la edición, y pedirle a
      Luis que la haga explícitamente en ese circuito.

## Reglas del flujo hotfix sync (`run_hotfix_sync`)

18. `run_hotfix_sync` requiere:
    - `/compose` limpio, en rama `main`, con commits adelantados de
      `origin/main` (los del hotfix).
    - `/desarrollo` limpio, en rama `develop`.

19. Si `/desarrollo` tiene commits locales no pusheados que conflictúan
    con main, el merge aborta y reporta. NO forzar — pedir a Luis que
    resuelva el conflicto manualmente.

20. Orden obligatorio antes de cualquier deploy:
    1) commit + push main en `/compose`
    2) `run_hotfix_sync` (sincroniza main → develop)
    3) deploy (solo Luis: `bash /compose/3-despliegue.sh`)
    Si 3-despliegue.sh corre antes del paso 1, los cambios uncommitted
    se pierden.

21. Si el merge en `/desarrollo` resulta no-op (main ya está en develop),
    el agente debe detectarlo y avisar en lugar de crear un merge commit
    vacío.

## Reglas de code editing por circuito (Sprint 1.5)

22. **Pre-flight obligatorio antes de `run_salvar` en circuito `backend`**:
    - `validate_python_syntax` debe devolver `all_ok: true`.
    - `run_pytest` debe devolver `returncode: 0`.
    - Si cualquiera falla, NO ejecutar `run_salvar`. Reportar el error a Luis.

23. **Cross-circuit file movement**: nunca muevas archivos entre
    `/desarrollo`, `/compose` y `/contenedores/conti-backend` con `cp`
    o `mv` directo. Usá `git` (vía `run_salvar` + `run_hotfix_sync`) o
    pedile a Luis que lo haga explícitamente.

24. **`cross_repo_search` vs `search_rag`**: `cross_repo_search` usa
    `git grep` en vivo contra los working trees. `search_rag` usa el
    índice de Sourcebot (más rápido pero puede estar desactualizado).
    Usar `cross_repo_search` cuando el agente sospecha que el código
    cambió desde la última indexación de Sourcebot.

25. **`detect_circuit_from_path`** es la única forma válida de saber a qué
    circuito pertenece un path desde el circuito `libre`. Si devuelve
    `circuit: null`, NO asumir; pedir credenciales a Luis.

26. **Tests del circuito `backend` se corren contra**:
    - `tests/test_<módulo>.py` para test focalizado.
    - Suite completa vía `run_pytest(circuit="backend")` antes de commit
      que toque múltiples módulos.
    - NO usar `pytest` directo desde el shell — siempre vía `run_pytest`
      (registra en Ponytail y respeta timeouts).

27. **Validación de sintaxis en archivos fuera del workspace del circuito
    activo**: si el agente está en `libre` y necesita editar un archivo
    en `backend`, primero debe detectar el circuito (`detect_circuit_from_path`)
    y luego pedir a Luis que opere en el circuito correcto. NO ejecutar
    `validate_python_syntax` desde `libre` sobre paths de otros
    circuitos — eso es trabajo del circuito destino.