import json
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from app.config.loader import reload_config
from app.main import app


client = TestClient(app)


def test_get_git_status_on_local_fixture_repo(tmp_path, monkeypatch) -> None:
    repo, _remote = _create_git_repo(tmp_path)
    _point_config_to_repo(tmp_path, repo, monkeypatch)
    response = client.post(
        "/mcp/call",
        json={"tool": "get_git_status", "arguments": {"repo_path": str(repo)}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["branch"] == "develop"
    assert payload["result"]["is_clean"] is False
    assert "tracked.txt" in payload["result"]["modified_files"]
    assert "new_file.txt" in payload["result"]["untracked_files"]


def test_get_git_log_and_pipeline_summary(tmp_path, monkeypatch) -> None:
    repo, _remote = _create_git_repo(tmp_path)
    _point_config_to_repo(tmp_path, repo, monkeypatch)

    log_response = client.post(
        "/mcp/call",
        json={"tool": "get_git_log", "arguments": {"repo_path": str(repo), "n": 5}},
    )
    assert log_response.status_code == 200
    assert log_response.json()["result"]["count"] >= 1

    summary_response = client.post(
        "/mcp/call",
        json={"tool": "get_pipeline_summary", "arguments": {"repo_path": str(repo)}},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()["result"]
    assert summary["branch"] == "develop"
    assert summary["modified_count"] >= 1
    assert len(summary["recent_commits"]) >= 1


def test_diff_with_develop_returns_stat(tmp_path, monkeypatch) -> None:
    repo, _remote = _create_git_repo_with_feature_commit(tmp_path)
    _point_config_to_repo(tmp_path, repo, monkeypatch)
    response = client.post(
        "/mcp/call",
        json={"tool": "diff_with_develop", "arguments": {"repo_path": str(repo)}},
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["base_branch"] == "develop"
    assert "tracked.txt" in payload["diff"]


def test_run_salvar_preview_and_execute(tmp_path, monkeypatch) -> None:
    repo, remote = _create_git_repo(tmp_path)
    _point_config_to_repo(tmp_path, repo, monkeypatch)

    preview = client.post(
        "/mcp/call",
        json={
            "tool": "run_salvar",
            "arguments": {
                "repo_path": str(repo),
                "confirm": False,
                "summary": "docs: update fixture",
            },
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()["result"]
    assert preview_payload["requires_confirmation"] is True
    assert preview_payload["branch"] == "develop"

    execute = client.post(
        "/mcp/call",
        json={
            "tool": "run_salvar",
            "arguments": {
                "repo_path": str(repo),
                "confirm": True,
                "summary": "docs: update fixture",
            },
        },
    )
    assert execute.status_code == 200
    execute_payload = execute.json()["result"]
    assert execute_payload["success"] is True
    assert execute_payload["git_pushed"] is True
    remote_head = _git_stdout(
        repo, f"git ls-remote {remote.as_posix()} refs/heads/develop"
    ).split()[0]
    assert remote_head.startswith(execute_payload["commit_hash"])


def test_run_promover_preview_and_execute(tmp_path, monkeypatch) -> None:
    repo, remote = _create_promotable_git_repo(tmp_path)
    _point_config_to_repo(tmp_path, repo, monkeypatch)

    preview = client.post(
        "/mcp/call",
        json={
            "tool": "run_promover",
            "arguments": {
                "repo_path": str(repo),
                "confirm": False,
                "summary": "Release test",
            },
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()["result"]
    assert preview_payload["requires_confirmation"] is True
    assert "feat: promo delta" in preview_payload["commits_to_promote"]

    execute = client.post(
        "/mcp/call",
        json={
            "tool": "run_promover",
            "arguments": {
                "repo_path": str(repo),
                "confirm": True,
                "summary": "Release test",
            },
        },
    )
    assert execute.status_code == 200
    payload = execute.json()["result"]
    assert payload["success"] is True
    assert payload["main_branch"] == "main"
    remote_main = _git_stdout(
        repo, f"git ls-remote {remote.as_posix()} refs/heads/main"
    )
    assert remote_main.strip()


def test_run_salvar_force_branch_main_backend_circuit(tmp_path, monkeypatch) -> None:
    """Circuito backend: orquestrador-contamela solo tiene main.
    run_salvar con force_branch='main' debe poder commitear y pushear a main
    aunque el check original de línea 194 lo bloqueaba."""
    repo, remote = _create_main_only_repo(tmp_path)
    _point_config_to_repo(tmp_path, repo, monkeypatch)

    execute = client.post(
        "/mcp/call",
        json={
            "tool": "run_salvar",
            "arguments": {
                "repo_path": str(repo),
                "confirm": True,
                "summary": "feat: backend hotfix",
                "force_branch": "main",
            },
        },
    )
    assert execute.status_code == 200
    payload = execute.json()["result"]
    assert payload["success"] is True
    assert payload["branch"] == "main"
    assert payload["git_pushed"] is True

    remote_main = _git_stdout(
        repo, f"git ls-remote {remote.as_posix()} refs/heads/main"
    ).split()[0]
    assert remote_main.startswith(payload["commit_hash"])


def test_run_hotfix_sync_main_to_develop(tmp_path, monkeypatch) -> None:
    """Flujo hotfix: Luis commitea en /compose (main) y el agente sincroniza
    hacia /desarrollo (develop) via run_hotfix_sync."""
    compose_repo, desarrollo_repo, remote = _create_hotfix_setup(tmp_path)
    _point_config_to_repo(tmp_path, desarrollo_repo, monkeypatch)

    # 1. Luis edita /compose y commitea el hotfix en main (sin agente)
    (compose_repo / "HOTFIX.md").write_text(
        "hotfix aplicado en produccion\n", encoding="utf-8"
    )
    _run(compose_repo, "git add HOTFIX.md")
    _run(compose_repo, "git commit -m 'hotfix: test sync flow'")
    _run(compose_repo, "git push origin main")

    # 2. Pre-check: /desarrollo NO tiene el cambio
    develop_before = _git_stdout(desarrollo_repo, "git log --oneline -5")
    assert "hotfix: test sync flow" not in develop_before

    # 3. Llamar run_hotfix_sync con confirm=True
    response = client.post(
        "/mcp/call",
        json={
            "tool": "run_hotfix_sync",
            "arguments": {
                "repo_path": str(desarrollo_repo),
                "confirm": True,
                "summary": "sync test",
                "compose_repo_path": str(compose_repo),
                "desarrollo_repo_path": str(desarrollo_repo),
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is True
    assert payload["action"] == "hotfix_sync"
    assert payload["git_pushed"] is True

    # 4. Post-check: /desarrollo ahora SI tiene el cambio (merge --no-ff de main)
    develop_after = _git_stdout(desarrollo_repo, "git log --oneline -5")
    assert "hotfix: test sync flow" in develop_after or any(
        "hotfix:" in line for line in develop_after.splitlines()
    ), f"develop debería tener el hotfix tras sync. Log:\n{develop_after}"


def test_run_hotfix_sync_aborts_on_dirty_compose(tmp_path, monkeypatch) -> None:
    """Si /compose tiene cambios uncommitted, run_hotfix_sync debe abortar
    sin pushear nada."""
    compose_repo, desarrollo_repo, _remote = _create_hotfix_setup(tmp_path)
    _point_config_to_repo(tmp_path, desarrollo_repo, monkeypatch)

    (compose_repo / "wip.txt").write_text("wip sin commit\n", encoding="utf-8")

    response = client.post(
        "/mcp/call",
        json={
            "tool": "run_hotfix_sync",
            "arguments": {
                "confirm": True,
                "summary": "debe fallar",
                "compose_repo_path": str(compose_repo),
                "desarrollo_repo_path": str(desarrollo_repo),
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["success"] is False
    assert "uncommitted" in payload.get("error", "").lower()


def _create_git_repo(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", remote.as_posix()],
        check=True,
        capture_output=True,
        text=True,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "git init -b main")
    _run(repo, "git config user.name 'Conti Test'")
    _run(repo, "git config user.email 'conti@example.com'")
    (repo / "tracked.txt").write_text("linea inicial\n", encoding="utf-8")
    _run(repo, "git add tracked.txt")
    _run(repo, "git commit -m 'feat: initial commit'")
    _run(repo, f"git remote add origin {remote.as_posix()}")
    _run(repo, "git push -u origin main")
    _run(repo, "git checkout -b develop")
    _run(repo, "git push -u origin develop")
    (repo / "tracked.txt").write_text("linea inicial\nlinea nueva\n", encoding="utf-8")
    (repo / "new_file.txt").write_text("nuevo\n", encoding="utf-8")
    return repo, remote


def _create_git_repo_with_feature_commit(tmp_path: Path) -> tuple[Path, Path]:
    repo, remote = _create_git_repo(tmp_path)
    _run(repo, "git checkout -b feature/test")
    (repo / "tracked.txt").write_text(
        "linea inicial\nlinea nueva\ncommit feature\n", encoding="utf-8"
    )
    _run(repo, "git add tracked.txt")
    _run(repo, "git commit -m 'feat: feature delta'")
    return repo, remote


def _create_promotable_git_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo, remote = _create_git_repo(tmp_path)
    _run(repo, "git add -A")
    _run(repo, "git commit -m 'feat: promo delta'")
    _run(repo, "git push origin develop")
    return repo, remote


def _point_config_to_repo(tmp_path: Path, repo: Path, monkeypatch) -> None:
    config_file = tmp_path / "app_config.json"
    config_file.write_text(
        json.dumps(
            {
                "paths": {
                    "home_root": str(repo),
                    "development_repo": str(repo),
                    "production_repo": str(repo),
                    "onboarding_file": "/contenedores/conti-backend/docs/onboarding.md",
                    "onboarding_brief_file": "/contenedores/conti-backend/docs/onboarding_brief.md",
                    "rules_file": "/contenedores/conti-backend/docs/rules.md",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CONTI_BACKEND_CONFIG", str(config_file))
    reload_config()


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
    """Repo estilo orquestrador-contamela: solo rama main, sin develop."""
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
    (repo / "main_only.txt").write_text("solo main\n", encoding="utf-8")
    _run(repo, "git add main_only.txt")
    _run(repo, "git commit -m 'feat: initial main-only commit'")
    _run(repo, f"git remote add origin {remote.as_posix()}")
    _run(repo, "git push -u origin main")
    (repo / "main_only.txt").write_text("solo main\nmodificado\n", encoding="utf-8")
    return repo, remote


def _create_hotfix_setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Crea el setup del hotfix flow:
    - remote.git (bare)
    - /compose (clone en main, working tree separado)
    - /desarrollo (clone en develop, working tree separado)
    Ambos comparten origin pero son clones independientes.
    """
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
    _run(seed, "git commit -m 'feat: initial seed'")
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
