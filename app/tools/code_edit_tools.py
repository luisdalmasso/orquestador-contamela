"""
Tools MCP para code editing y codevibing.

Estas tools complementan el flujo de edición de código en los 4 circuitos:
  - validate_python_syntax: chequea sintaxis antes de commitear
  - run_pytest: corre el test suite del circuito activo
  - detect_circuit_from_path: determina qué circuito corresponde a un path
  - cross_repo_search: busca código a través de los repos indexados

Categoría MCP: CODE_EDIT.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import Any

from app.config.models import AppConfig


# Mapeo path → circuito (single source of truth).
# Orden importa: el primer match gana. Los paths más específicos primero.
_PATH_TO_CIRCUIT: tuple[tuple[str, str], ...] = (
    ("/desarrollo", "desarrollo"),
    ("/compose", "produccion"),
    ("/contenedores/conti-backend", "backend"),
    ("/home/nanobot", "libre"),
    ("/tmp/free-agent", "libre"),
)


def _circuit_for_path(path: str) -> tuple[str, str] | None:
    """Devuelve (circuit_id, workspace_dir) para un path dado.
    None si no matchea ningún workspace conocido."""
    resolved = str(Path(path).resolve())
    for prefix, circuit_id in _PATH_TO_CIRCUIT:
        if resolved.startswith(prefix):
            return circuit_id, prefix
    return None


# ── validate_python_syntax ───────────────────────────────────────────


def validate_python_syntax(config: AppConfig, arguments: dict) -> dict:
    """Valida la sintaxis Python de uno o más archivos usando `ast.parse`.

    No ejecuta el archivo, solo chequea que parsee correctamente. Más
    seguro que `py_compile` para archivos que no querés ejecutar.

    Args:
        config: AppConfig (no usado directamente, mantenido por interfaz).
        arguments: {"paths": list[str]} — paths absolutos a validar.

    Returns:
        {"results": [{"path": str, "ok": bool, "error": str|None}], "ok_count": int, "fail_count": int}
    """
    paths = arguments.get("paths") or []
    if not paths:
        raise ValueError("Se requiere 'paths' (lista de paths a validar)")

    results = []
    ok_count = 0
    fail_count = 0

    for p in paths:
        path = Path(p)
        result = {"path": str(path), "ok": False, "error": None}
        if not path.exists():
            result["error"] = f"No existe: {path}"
        elif not path.is_file():
            result["error"] = f"No es un archivo: {path}"
        elif path.suffix != ".py":
            result["error"] = f"No es .py: {path}"
        else:
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
                ast.parse(source, filename=str(path))
                result["ok"] = True
            except SyntaxError as exc:
                result["error"] = f"SyntaxError línea {exc.lineno}: {exc.msg}"
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"

        if result["ok"]:
            ok_count += 1
        else:
            fail_count += 1
        results.append(result)

    return {
        "results": results,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "all_ok": fail_count == 0,
    }


# ── run_pytest ──────────────────────────────────────────────────────


def run_pytest(config: AppConfig, arguments: dict) -> dict:
    """Corre pytest en el directorio del circuito activo.

    Args:
        config: AppConfig (no usado, mantenido por interfaz).
        arguments:
          - "circuit" (str, opcional): id del circuito ("backend", "desarrollo", etc.).
              Si se omite, se detecta del cwd.
          - "test_path" (str, opcional): path específico a testear (ej: "tests/test_git_tools.py").
              Si se omite, corre toda la suite del circuito.
          - "timeout" (int, opcional, default=300): segundos de timeout.
          - "args" (list[str], opcional): argumentos extra para pytest.

    Returns:
        {"returncode": int, "stdout": str, "stderr": str, "circuit": str, "test_path": str|None}
    """
    circuit = arguments.get("circuit")
    test_path = arguments.get("test_path")
    timeout = int(arguments.get("timeout", 300))
    extra_args = arguments.get("args") or []

    # Resolver el directorio del circuito
    if circuit:
        from app.openhands_agent.circuits import CIRCUITS

        if circuit not in CIRCUITS:
            raise ValueError(f"circuito desconocido: {circuit}")
        workdir = Path(CIRCUITS[circuit].workspace_dir)
    else:
        cwd = Path.cwd()
        match = _circuit_for_path(str(cwd))
        if not match:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"cwd {cwd} no pertenece a ningún circuito conocido",
                "circuit": None,
                "test_path": test_path,
            }
        circuit = match[0]
        workdir = cwd

    if not workdir.exists():
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"workdir no existe: {workdir}",
            "circuit": circuit,
            "test_path": test_path,
        }

    cmd = ["python3", "-m", "pytest", "-v", "--tb=short"]
    if test_path:
        cmd.append(test_path)
    cmd.extend(extra_args)

    try:
        result = subprocess.run(
            cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Timeout después de {timeout}s",
            "circuit": circuit,
            "test_path": test_path,
            "timed_out": True,
        }

    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-5000:],  # truncate últimos 5KB
        "stderr": result.stderr[-2000:],
        "circuit": circuit,
        "test_path": test_path,
        "cmd": " ".join(cmd),
    }


# ── detect_circuit_from_path ───────────────────────────────────────


def detect_circuit_from_path(config: AppConfig, arguments: dict) -> dict:
    """Dado un path absoluto, devuelve qué circuito corresponde y por qué.

    Útil cuando el agente está en el circuito `libre` y necesita saber
    a qué circuito mandar una edición antes de commitear.

    Args:
        config: AppConfig (no usado).
        arguments: {"path": str} — path absoluto o relativo al cwd.

    Returns:
        {"input_path": str, "circuit": str|None, "workspace": str|None,
         "reason": str, "candidates": list[{prefix, circuit}]}
    """
    raw_path = arguments.get("path")
    if not raw_path:
        raise ValueError("Se requiere 'path'")

    path = Path(raw_path)
    candidates_checked = []

    if path.is_absolute():
        # Path absoluto: si matchea workspace → return; si NO matchea → también
        # return None (no probar como relativo, eso sería incorrecto).
        match = _circuit_for_path(str(path))
        if match:
            return {
                "input_path": raw_path,
                "circuit": match[0],
                "workspace": match[1],
                "reason": f"path absoluto cae dentro de {match[1]}",
                "candidates": [
                    {"prefix": p, "circuit": c} for p, c in _PATH_TO_CIRCUIT
                ],
            }
        return {
            "input_path": raw_path,
            "circuit": None,
            "workspace": None,
            "reason": "path absoluto no pertenece a ningún workspace conocido",
        }

    # Path relativo: probar resolviendo contra cada workspace
    for prefix, circuit_id in _PATH_TO_CIRCUIT:
        candidate = Path(prefix) / raw_path
        candidates_checked.append(str(candidate))
        if candidate.exists():
            return {
                "input_path": raw_path,
                "circuit": circuit_id,
                "workspace": prefix,
                "resolved": str(candidate),
                "reason": f"path existe dentro de {prefix}",
                "candidates_checked": candidates_checked,
            }

    return {
        "input_path": raw_path,
        "circuit": None,
        "workspace": None,
        "reason": "path relativo no encontrado en ningún workspace conocido",
        "candidates_checked": candidates_checked,
    }

    # Probar resolviendo contra cada workspace
    for prefix, circuit_id in _PATH_TO_CIRCUIT:
        candidate = Path(prefix) / raw_path
        if candidate.exists():
            return {
                "input_path": raw_path,
                "circuit": circuit_id,
                "workspace": prefix,
                "resolved": str(candidate),
                "reason": f"path existe dentro de {prefix}",
                "candidates_checked": candidates_checked,
            }
        candidates_checked.append(str(candidate))

    return {
        "input_path": raw_path,
        "circuit": None,
        "workspace": None,
        "reason": "path no pertenece a ningún workspace conocido",
        "candidates_checked": candidates_checked,
    }


# ── cross_repo_search ──────────────────────────────────────────────


def cross_repo_search(config: AppConfig, arguments: dict) -> dict:
    """Busca un término en los 3 repos bind-mounted (/desarrollo, /compose,
    /contenedores/conti-backend) usando grep literal.

    A diferencia de search_rag (que usa Sourcebot sobre índices pre-construidos),
    cross_repo_search hace grep en vivo contra el working tree actual.
    Útil para codevibing cuando el índice de Sourcebot está desactualizado.

    Args:
        config: AppConfig.
        arguments:
          - "query" (str, requerido): término a buscar.
          - "include_globs" (list[str], opcional): ej: ["*.py", "*.md"].
              Default: ["*.py"].
          - "exclude_globs" (list[str], opcional): ej: ["*/__pycache__/*", "*/.git/*"].
          - "max_results" (int, opcional, default=50).
          - "repos" (list[str], opcional): subset de ["desarrollo","produccion","backend"].
              Default: los 3.

    Returns:
        {"query": str, "repos_searched": list[str], "total_matches": int,
         "results": [{repo, path, line, content}], "truncated": bool}
    """
    query = arguments.get("query")
    if not query:
        raise ValueError("Se requiere 'query'")

    include_globs = arguments.get("include_globs") or ["*.py"]
    exclude_globs = arguments.get("exclude_globs") or [
        "*/__pycache__/*",
        "*/.git/*",
        "*/node_modules/*",
    ]
    max_results = int(arguments.get("max_results", 50))
    requested_repos = arguments.get("repos")

    repo_paths = {
        "desarrollo": Path("/desarrollo"),
        "produccion": Path("/compose"),
        "backend": Path("/contenedores/conti-backend"),
    }
    if requested_repos:
        repo_paths = {k: v for k, v in repo_paths.items() if k in requested_repos}

    # git grep es más rápido que recursive grep y respeta .gitignore
    results = []
    total = 0
    truncated = False

    for repo_name, repo_path in repo_paths.items():
        if not repo_path.exists():
            continue

        cmd = [
            "git",
            "grep",
            "-n",
            "-I",
            "--untracked",
            "-e",
            query,
            "--",
            *include_globs,
        ]
        # Excluir patrones (git grep no soporta exclude directamente,
        # usamos pathspec magic)
        for exc in exclude_globs:
            cmd.extend([f":(exclude){exc}"])

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            continue
        except Exception:
            continue

        if result.returncode not in (0, 1):  # 0=matches, 1=no matches
            continue

        for line in result.stdout.splitlines():
            if total >= max_results:
                truncated = True
                break
            # git grep output: path:lineno:content
            parts = line.split(":", 2)
            if len(parts) == 3:
                results.append(
                    {
                        "repo": repo_name,
                        "path": parts[0],
                        "line": int(parts[1]),
                        "content": parts[2][:200],
                    }
                )
                total += 1
        if truncated:
            break

    return {
        "query": query,
        "repos_searched": [r for r, p in repo_paths.items() if p.exists()],
        "total_matches": total,
        "results": results,
        "truncated": truncated,
        "max_results": max_results,
    }
