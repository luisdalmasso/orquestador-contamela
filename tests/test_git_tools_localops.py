"""
Tests standalone para LocalGitOps: target_branch, force_branch, run_hotfix_sync.

Estos tests NO importan app.main (que tiene una cadena de deps larga)
y testean LocalGitOps directamente. Complementan tests/test_git_tools.py
que sí pasan por el MCP HTTP layer.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.tools.git_tools import LocalGitOps


def _run(repo: Path, command: str) -> None:
    subprocess.run(
        command, cwd=repo, shell=True, check=True, capture_output=True, text=True
    )


def _git_stdout(repo: Path, command: str) -> str:
    result = subprocess.run(
        command, cwd=repo, shell=True, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _create_main_only_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Repo estilo orquestrador-contamela: solo main, sin develop."""
    remote = tmp_path / "remote_main.git"
    subprocess.run(
        ["git", "init", "--bare", remote.as_posix()],
        check=True,
        capture_output=True,
        text=True,
    )

    repo = tmp_path / "repo_main"
    repo.mkdir()
    _run(repo, "git init -b main")
    _run(repo, "git config user.name 'Conti Test'")
    _run(repo, "git config user.email 'conti@example.com'")
    (repo / "main_only.txt").write_text("v1\n", encoding="utf-8")
    _run(repo, "git add main_only.txt")
    _run(repo, "git commit -m 'feat: initial main-only'")
    _run(repo, f"git remote add origin {remote.as_posix()}")
    _run(repo, "git push -u origin main")
    (repo / "main_only.txt").write_text("v1\nv2\n", encoding="utf-8")
    return repo, remote


def _create_hotfix_setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Setup hotfix: remote.git + compose (main) + desarrollo (develop) clones."""
    remote = tmp_path / "remote_hotfix.git"
    subprocess.run(
        ["git", "init", "--bare", remote.as_posix()],
        check=True,
        capture_output=True,
        text=True,
    )

    seed = tmp_path / "seed"
    seed.mkdir()
    _run(seed, "git init -b main")
    _run(seed, "git config user.name 'Conti Test'")
    _run(seed, "git config user.email 'conti@example.com'")
    (seed / "base.txt").write_text("base\n", encoding="utf-8")
    _run(seed, "git add base.txt")
    _run(seed, "git commit -m 'feat: seed'")
    _run(seed, f"git remote add origin {remote.as_posix()}")
    _run(seed, "git push -u origin main")
    _run(seed, "git checkout -b develop")
    _run(seed, "git push -u origin develop")

    compose_repo = tmp_path / "compose"
    desarrollo_repo = tmp_path / "desarrollo"
    for path in (compose_repo, desarrollo_repo):
        subprocess.run(
            ["git", "clone", remote.as_posix(), path.as_posix()],
            check=True,
            capture_output=True,
            text=True,
        )
        _run(path, "git config user.name 'Conti Test'")
        _run(path, "git config user.email 'conti@example.com'")

    _run(compose_repo, "git checkout main")
    _run(desarrollo_repo, "git checkout develop")
    return compose_repo, desarrollo_repo, remote


# ── Tests ──────────────────────────────────────────────────────────


def test_default_target_branch_is_develop(tmp_path: Path) -> None:
    """Default sin override: target_branch == develop_branch."""
    repo, _remote = _create_main_only_repo(tmp_path)
    ops = LocalGitOps(
        repo_path=str(repo),
        remote="origin",
        develop_branch="develop",
        main_branch="main",
    )
    assert ops.target_branch == "develop"


def test_target_branch_override_main(tmp_path: Path) -> None:
    """Circuito backend: target_branch=main permite commitear en main
    sin disparar el check de línea 194."""
    repo, _remote = _create_main_only_repo(tmp_path)
    ops = LocalGitOps(
        repo_path=str(repo),
        remote="origin",
        develop_branch="develop",
        main_branch="main",
        target_branch="main",
    )
    assert ops.target_branch == "main"

    # run_salvar con force_branch="main" debe funcionar
    result = ops.run_salvar(confirm=True, summary="backend hotfix", force_branch="main")
    assert result["success"] is True
    assert result["branch"] == "main"
    assert result["git_pushed"] is True


def test_run_salvar_blocks_when_branch_mismatch(tmp_path: Path) -> None:
    """Sin force_branch ni target_branch override, run_salvar debe rechazar
    commits en main (legacy check que destrabamos con force_branch)."""
    repo, _remote = _create_main_only_repo(tmp_path)
    ops = LocalGitOps(
        repo_path=str(repo),
        remote="origin",
        develop_branch="develop",
        main_branch="main",
    )
    # target_branch default es develop, pero estamos en main → debe fallar
    result = ops.run_salvar(confirm=True, summary="intento en main")
    assert result["success"] is False
    assert "develop" in result["error"]


def test_run_hotfix_sync_full_flow(tmp_path: Path) -> None:
    """Happy path: hotfix en /compose se sincroniza a /desarrollo."""
    compose_repo, desarrollo_repo, _remote = _create_hotfix_setup(tmp_path)

    # Luis edita /compose
    (compose_repo / "HOTFIX.md").write_text("fix urgente\n", encoding="utf-8")
    _run(compose_repo, "git add HOTFIX.md")
    _run(compose_repo, "git commit -m 'hotfix: urgente'")

    # Antes del sync: /desarrollo NO tiene el cambio
    log_before = _git_stdout(desarrollo_repo, "git log --oneline")
    assert "hotfix: urgente" not in log_before

    # Ejecutar sync
    ops = LocalGitOps(repo_path=str(desarrollo_repo), remote="origin")
    result = ops.run_hotfix_sync(
        confirm=True,
        summary="sync test",
        compose_repo_path=str(compose_repo),
        desarrollo_repo_path=str(desarrollo_repo),
    )
    assert result["success"] is True
    assert result["action"] == "hotfix_sync"
    assert result["git_pushed"] is True

    # Después del sync: /desarrollo SÍ tiene el cambio
    log_after = _git_stdout(desarrollo_repo, "git log --oneline")
    assert any("hotfix" in line for line in log_after.splitlines()), (
        f"develop debería tener el hotfix. log:\n{log_after}"
    )


def test_run_hotfix_sync_aborts_on_dirty_compose(tmp_path: Path) -> None:
    """Si /compose tiene cambios uncommitted, el sync aborta antes de pushear."""
    compose_repo, desarrollo_repo, _remote = _create_hotfix_setup(tmp_path)
    (compose_repo / "wip.txt").write_text("wip\n", encoding="utf-8")

    ops = LocalGitOps(repo_path=str(desarrollo_repo), remote="origin")
    result = ops.run_hotfix_sync(
        confirm=True,
        summary="debe fallar",
        compose_repo_path=str(compose_repo),
        desarrollo_repo_path=str(desarrollo_repo),
    )
    assert result["success"] is False
    assert "uncommitted" in result["error"].lower()


def test_run_hotfix_sync_aborts_on_wrong_branch(tmp_path: Path) -> None:
    """Si /compose no está en main, abortar."""
    compose_repo, desarrollo_repo, _remote = _create_hotfix_setup(tmp_path)
    _run(compose_repo, "git checkout -b otra-rama")

    ops = LocalGitOps(repo_path=str(desarrollo_repo), remote="origin")
    result = ops.run_hotfix_sync(
        confirm=True,
        summary="test",
        compose_repo_path=str(compose_repo),
        desarrollo_repo_path=str(desarrollo_repo),
    )
    assert result["success"] is False
    assert "main" in result["error"]


def test_run_hotfix_sync_preview_mode(tmp_path: Path) -> None:
    """confirm=False devuelve preview sin ejecutar nada."""
    compose_repo, desarrollo_repo, _remote = _create_hotfix_setup(tmp_path)
    (compose_repo / "HOTFIX.md").write_text("preview test\n", encoding="utf-8")
    _run(compose_repo, "git add HOTFIX.md")
    _run(compose_repo, "git commit -m 'hotfix: preview test'")

    ops = LocalGitOps(repo_path=str(desarrollo_repo), remote="origin")
    result = ops.run_hotfix_sync(
        confirm=False,
        summary="preview",
        compose_repo_path=str(compose_repo),
        desarrollo_repo_path=str(desarrollo_repo),
    )
    assert result["requires_confirmation"] is True
    assert result["action"] == "hotfix_sync main -> develop"
    assert result["compose_ahead_of_origin_main"] >= 1

    # /desarrollo NO debe tener el cambio todavía (preview no ejecuta)
    log = _git_stdout(desarrollo_repo, "git log --oneline")
    assert "hotfix: preview test" not in log
