"""
Tests para app.tools.code_edit_tools: validate_python_syntax, run_pytest,
detect_circuit_from_path, cross_repo_search.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from app.tools.code_edit_tools import (
    _circuit_for_path,
    cross_repo_search,
    detect_circuit_from_path,
    run_pytest,
    validate_python_syntax,
)


# ── validate_python_syntax ───────────────────────────────────────────


def test_validate_syntax_ok(tmp_path: Path) -> None:
    good = tmp_path / "good.py"
    good.write_text("x = 1\ny = 2\n", encoding="utf-8")
    result = validate_python_syntax(None, {"paths": [str(good)]})
    assert result["all_ok"] is True
    assert result["ok_count"] == 1
    assert result["fail_count"] == 0
    assert result["results"][0]["ok"] is True


def test_validate_syntax_syntax_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("def foo(:\n    pass\n", encoding="utf-8")
    result = validate_python_syntax(None, {"paths": [str(bad)]})
    assert result["all_ok"] is False
    assert result["fail_count"] == 1
    assert "SyntaxError" in result["results"][0]["error"]


def test_validate_syntax_missing_file(tmp_path: Path) -> None:
    result = validate_python_syntax(None, {"paths": [str(tmp_path / "nope.py")]})
    assert result["all_ok"] is False
    assert "No existe" in result["results"][0]["error"]


def test_validate_syntax_ignores_non_py(tmp_path: Path) -> None:
    txt = tmp_path / "file.txt"
    txt.write_text("not python\n", encoding="utf-8")
    result = validate_python_syntax(None, {"paths": [str(txt)]})
    assert result["all_ok"] is False
    assert "No es .py" in result["results"][0]["error"]


def test_validate_syntax_empty_paths_raises() -> None:
    try:
        validate_python_syntax(None, {"paths": []})
        assert False, "should have raised"
    except ValueError as exc:
        assert "paths" in str(exc).lower()


# ── _circuit_for_path helper ─────────────────────────────────────────


def test_circuit_for_path_development() -> None:
    assert _circuit_for_path("/desarrollo/foo.py") == ("desarrollo", "/desarrollo")
    assert _circuit_for_path("/desarrollo/sub/bar.py") == ("desarrollo", "/desarrollo")


def test_circuit_for_path_production() -> None:
    assert _circuit_for_path("/compose/docker-compose.yml") == (
        "produccion",
        "/compose",
    )


def test_circuit_for_path_backend() -> None:
    assert _circuit_for_path("/contenedores/conti-backend/app/main.py") == (
        "backend",
        "/contenedores/conti-backend",
    )


def test_circuit_for_path_unknown() -> None:
    assert _circuit_for_path("/tmp/whatever.py") is None


# ── detect_circuit_from_path ────────────────────────────────────────


def test_detect_circuit_absolute(tmp_path: Path) -> None:
    real_dir = Path("/desarrollo")
    test_file = real_dir / "marker_test.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        test_file.write_text("# marker\n", encoding="utf-8")
        result = detect_circuit_from_path(None, {"path": str(test_file)})
        assert result["circuit"] == "desarrollo"
        assert result["workspace"] == "/desarrollo"
    finally:
        if test_file.exists():
            test_file.unlink()


def test_detect_circuit_unknown_path() -> None:
    result = detect_circuit_from_path(None, {"path": "/etc/passwd"})
    assert result["circuit"] is None
    assert "ningún workspace" in result["reason"].lower()


# ── run_pytest (usa el repo del backend en este container) ────────────


def test_run_pytest_in_backend_circuit() -> None:
    """Corremos pytest en el circuito backend (cwd /contenedores/conti-backend)
    sobre un test que sabemos que pasa."""
    result = run_pytest(
        None,
        {
            "circuit": "backend",
            "test_path": "tests/test_git_tools_localops.py",
            "timeout": 120,
        },
    )
    assert result["circuit"] == "backend"
    assert (
        "passed" in result["stdout"].lower()
        or "passed" in result["stderr"].lower()
        or result["returncode"] == 0
    )


def test_run_pytest_invalid_circuit_raises() -> None:
    try:
        run_pytest(None, {"circuit": "invalid_circuit"})
        assert False, "should have raised"
    except ValueError as exc:
        assert "desconocido" in str(exc).lower()


# ── cross_repo_search ────────────────────────────────────────────────


def test_cross_repo_search_finds_marker() -> None:
    """Buscar un string único que solo exista en uno de los repos."""
    # Asumimos que 'def run_hotfix_sync' solo está en este repo
    result = cross_repo_search(
        None,
        {
            "query": "def run_hotfix_sync",
            "include_globs": ["*.py"],
            "max_results": 10,
        },
    )
    assert result["query"] == "def run_hotfix_sync"
    # Debe encontrar al menos un match en backend
    repos_found = {r["repo"] for r in result["results"]}
    assert (
        "backend" in repos_found
        or "desarrollo" in repos_found
        or "produccion" in repos_found
    )


def test_cross_repo_search_max_results() -> None:
    result = cross_repo_search(
        None,
        {
            "query": "def ",
            "include_globs": ["*.py"],
            "max_results": 5,
        },
    )
    assert len(result["results"]) <= 5
    if len(result["results"]) == 5:
        assert result["truncated"] is True


def test_cross_repo_search_no_matches() -> None:
    # Generar un string verdaderamente aleatorio para evitar matches accidentales
    import uuid

    unique = f"__test_no_match_{uuid.uuid4().hex}__"
    result = cross_repo_search(
        None,
        {
            "query": unique,
            "max_results": 10,
        },
    )
    assert result["total_matches"] == 0
    assert result["results"] == []
