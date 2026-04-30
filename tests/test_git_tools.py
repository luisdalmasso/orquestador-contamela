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
        json={"tool": "run_salvar", "arguments": {"repo_path": str(repo), "confirm": False, "summary": "docs: update fixture"}},
    )
    assert preview.status_code == 200
    preview_payload = preview.json()["result"]
    assert preview_payload["requires_confirmation"] is True
    assert preview_payload["branch"] == "develop"

    execute = client.post(
        "/mcp/call",
        json={"tool": "run_salvar", "arguments": {"repo_path": str(repo), "confirm": True, "summary": "docs: update fixture"}},
    )
    assert execute.status_code == 200
    execute_payload = execute.json()["result"]
    assert execute_payload["success"] is True
    assert execute_payload["git_pushed"] is True
    remote_head = _git_stdout(repo, f"git ls-remote {remote.as_posix()} refs/heads/develop").split()[0]
    assert remote_head.startswith(execute_payload["commit_hash"])


def test_run_promover_preview_and_execute(tmp_path, monkeypatch) -> None:
    repo, remote = _create_promotable_git_repo(tmp_path)
    _point_config_to_repo(tmp_path, repo, monkeypatch)

    preview = client.post(
        "/mcp/call",
        json={"tool": "run_promover", "arguments": {"repo_path": str(repo), "confirm": False, "summary": "Release test"}},
    )
    assert preview.status_code == 200
    preview_payload = preview.json()["result"]
    assert preview_payload["requires_confirmation"] is True
    assert "feat: promo delta" in preview_payload["commits_to_promote"]

    execute = client.post(
        "/mcp/call",
        json={"tool": "run_promover", "arguments": {"repo_path": str(repo), "confirm": True, "summary": "Release test"}},
    )
    assert execute.status_code == 200
    payload = execute.json()["result"]
    assert payload["success"] is True
    assert payload["main_branch"] == "main"
    remote_main = _git_stdout(repo, f"git ls-remote {remote.as_posix()} refs/heads/main")
    assert remote_main.strip()


def _create_git_repo(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", remote.as_posix()], check=True, capture_output=True, text=True)

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
    (repo / "tracked.txt").write_text("linea inicial\nlinea nueva\ncommit feature\n", encoding="utf-8")
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
                    "rules_file": "/contenedores/conti-backend/docs/rules.md"
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CONTI_BACKEND_CONFIG", str(config_file))
    reload_config()


def _run(repo: Path, command: str) -> None:
    subprocess.run(command, cwd=repo, shell=True, check=True, capture_output=True, text=True)


def _git_stdout(repo: Path, command: str) -> str:
    result = subprocess.run(command, cwd=repo, shell=True, check=True, capture_output=True, text=True)
    return result.stdout.strip()
