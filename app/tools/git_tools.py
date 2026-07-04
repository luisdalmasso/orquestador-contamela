from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config.models import AppConfig
from app.utils.security import resolve_allowed_path


class LocalGitOps:
    def __init__(
        self,
        repo_path: str,
        remote: str = "origin",
        develop_branch: str = "develop",
        main_branch: str = "main",
        target_branch: str | None = None,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.remote = remote
        self.develop_branch = develop_branch
        self.main_branch = main_branch
        self.target_branch = target_branch or develop_branch

    def _run_git(self, *args: str) -> dict[str, Any]:
        if not self.repo_path.exists() or not self.repo_path.is_dir():
            return {"success": False, "error": f"Repo no encontrado: {self.repo_path}"}
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout ejecutando git"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }

    def get_status(self) -> dict[str, Any]:
        result = self._run_git("status", "--porcelain=v2", "--branch")
        if not result["success"]:
            return {
                "available": False,
                "error": result.get("error") or result.get("stderr", ""),
            }

        lines = [line for line in result["stdout"].splitlines() if line]
        branch = "unknown"
        upstream = None
        ahead = 0
        behind = 0
        staged: list[str] = []
        modified: list[str] = []
        untracked: list[str] = []
        deleted: list[str] = []

        for line in lines:
            if line.startswith("# branch.head"):
                branch = line.split()[-1]
            elif line.startswith("# branch.upstream"):
                upstream = line.split()[-1]
            elif line.startswith("# branch.ab"):
                parts = line.split()
                ahead = int(parts[2].removeprefix("+"))
                behind = int(parts[3].removeprefix("-"))
            elif line.startswith("1 "):
                parts = line.split()
                xy = parts[1]
                filename = parts[-1]
                if xy[0] != ".":
                    staged.append(filename)
                if xy[1] != ".":
                    modified.append(filename)
                if "D" in xy:
                    deleted.append(filename)
            elif line.startswith("?"):
                untracked.append(line.split()[-1])

        return {
            "available": True,
            "repo_path": str(self.repo_path),
            "branch": branch,
            "upstream": upstream,
            "ahead": ahead,
            "behind": behind,
            "staged_files": staged,
            "modified_files": modified,
            "deleted_files": deleted,
            "untracked_files": untracked,
            "is_clean": not staged and not modified and not deleted and not untracked,
        }

    def get_log(self, limit: int = 10) -> dict[str, Any]:
        result = self._run_git("log", f"-{limit}", "--pretty=format:%H|%an|%ae|%ai|%s")
        if not result["success"]:
            return {
                "available": False,
                "error": result.get("error") or result.get("stderr", ""),
            }

        commits = []
        for line in result["stdout"].splitlines():
            if not line or "|" not in line:
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append(
                    {
                        "hash": parts[0][:8],
                        "author": parts[1],
                        "email": parts[2],
                        "date": parts[3],
                        "message": parts[4],
                    }
                )
        return {"available": True, "commits": commits, "count": len(commits)}

    def diff_with_develop(self) -> dict[str, Any]:
        target = self._resolve_compare_target()
        diff_result = self._run_git("diff", target)
        stat_result = self._run_git("diff", "--stat", target)
        compare_result = self._run_git("rev-list", "--left-right", "--count", target)
        ahead = behind = 0
        if compare_result["success"] and compare_result["stdout"]:
            parts = compare_result["stdout"].split()
            if len(parts) == 2:
                behind = int(parts[0])
                ahead = int(parts[1])
        return {
            "available": diff_result["success"],
            "base_branch": self.develop_branch,
            "remote": self.remote,
            "compare_target": target,
            "diff": diff_result.get("stdout", "")[:5000],
            "stat": stat_result.get("stdout", ""),
            "ahead_vs_develop": ahead,
            "behind_vs_develop": behind,
        }

    def get_pipeline_summary(self) -> dict[str, Any]:
        status = self.get_status()
        log = self.get_log(limit=5)
        diff = self.diff_with_develop()
        remotes = self._run_git("remote", "-v")
        return {
            "available": status.get("available", False),
            "repo_path": str(self.repo_path),
            "branch": status.get("branch"),
            "upstream": status.get("upstream"),
            "ahead": status.get("ahead", 0),
            "behind": status.get("behind", 0),
            "is_clean": status.get("is_clean", False),
            "modified_count": len(status.get("modified_files", [])),
            "deleted_count": len(status.get("deleted_files", [])),
            "untracked_count": len(status.get("untracked_files", [])),
            "staged_count": len(status.get("staged_files", [])),
            "recent_commits": log.get("commits", []),
            "diff_stat_vs_develop": diff.get("stat", ""),
            "ahead_vs_develop": diff.get("ahead_vs_develop", 0),
            "behind_vs_develop": diff.get("behind_vs_develop", 0),
            "remotes": remotes.get("stdout", "").splitlines()
            if remotes.get("success")
            else [],
            "next_actions": [
                "Revisar diff con develop antes de salvar.",
                "Usar run_salvar para commitear cuando la fase mutativa esté habilitada.",
                "Usar run_promover solo después de validar el pipeline local.",
            ],
        }

    def run_salvar(
        self,
        confirm: bool = False,
        summary: str = "",
        force_branch: str | None = None,
    ) -> dict[str, Any]:
        expected_branch = force_branch or self.target_branch
        status = self.get_status()
        if not status.get("available", False):
            return {"success": False, "error": status.get("error", "Git no disponible")}

        commit_message = self._build_salvar_message(summary)
        preview = {
            "success": False,
            "requires_confirmation": True,
            "action": f"commit+push a {expected_branch}",
            "repo_path": str(self.repo_path),
            "branch": status.get("branch"),
            "target_branch": expected_branch,
            "commit_message": commit_message,
            "git_status": status,
            "diff_stat": self._run_git("diff", "--stat", "HEAD").get("stdout", ""),
            "working_tree_preview": self._run_git("status", "--short").get(
                "stdout", ""
            ),
        }

        if not confirm:
            preview["message"] = (
                "Preview generado. Ejecutar run_salvar(confirm=true) para aplicar el commit."
            )
            return preview

        if status.get("branch") != expected_branch:
            return {
                "success": False,
                "error": f"run_salvar requiere estar en la rama {expected_branch}",
                "branch": status.get("branch"),
                "target_branch": expected_branch,
            }

        if status.get("is_clean"):
            return {
                "success": True,
                "action": "salvar",
                "git_nothing_new": True,
                "branch": status.get("branch"),
                "message": "No hay cambios para commitear.",
            }

        add_result = self._run_git("add", "-A")
        if not add_result["success"]:
            return {
                "success": False,
                "error": add_result.get("stderr") or add_result.get("error"),
            }

        commit_result = self._run_git("commit", "-m", commit_message)
        if not commit_result["success"]:
            return {
                "success": False,
                "error": commit_result.get("stderr")
                or commit_result.get("error")
                or "Commit falló",
                "commit_message": commit_message,
            }

        push_result = self._run_git("push", self.remote, expected_branch)
        if not push_result["success"]:
            return {
                "success": False,
                "error": push_result.get("stderr")
                or push_result.get("error")
                or "Push falló",
                "commit_message": commit_message,
            }

        head_result = self._run_git("rev-parse", "HEAD")
        next_step = (
            "Usar run_promover(confirm=false) para revisar la promoción a main."
            if expected_branch == self.develop_branch
            else f"Commit pusheado a {expected_branch}. No hay flujo de promoción desde {expected_branch}."
        )
        return {
            "success": True,
            "action": "salvar",
            "branch": expected_branch,
            "commit_message": commit_message,
            "commit_hash": head_result.get("stdout", "")[:8],
            "git_pushed": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "next_step": next_step,
        }

    def run_promover(self, confirm: bool = False, summary: str = "") -> dict[str, Any]:
        status = self.get_status()
        if not status.get("available", False):
            return {"success": False, "error": status.get("error", "Git no disponible")}

        current_branch = status.get("branch")
        develop_ref = self._resolve_branch_ref(self.develop_branch)
        main_ref = self._resolve_branch_ref(self.main_branch)
        commits_result = self._run_git("log", "--oneline", f"{main_ref}..{develop_ref}")
        diff_result = self._run_git("diff", "--stat", f"{main_ref}..{develop_ref}")
        merge_message = self._build_promover_message(summary)

        preview = {
            "success": False,
            "requires_confirmation": True,
            "action": "merge develop -> main",
            "repo_path": str(self.repo_path),
            "branch": current_branch,
            "commits_to_promote": commits_result.get("stdout", ""),
            "diff_stat": diff_result.get("stdout", ""),
            "merge_message": merge_message,
            "git_status": status,
        }

        if not confirm:
            preview["message"] = (
                "Preview generado. Ejecutar run_promover(confirm=true, summary='...') "
                "para aplicar la promoción."
            )
            return preview

        if current_branch != self.develop_branch:
            return {
                "success": False,
                "error": f"run_promover requiere estar en la rama {self.develop_branch}",
                "branch": current_branch,
            }

        if not status.get("is_clean", False):
            return {
                "success": False,
                "error": "El working tree debe estar limpio antes de promover.",
                "git_status": status,
            }

        original_branch = current_branch
        checkout_main = self._checkout_main_branch()
        if not checkout_main["success"]:
            return checkout_main

        pull_main = self._pull_main_if_available()
        if not pull_main["success"]:
            self._run_git("checkout", original_branch)
            return pull_main

        merge_result = self._run_git(
            "merge", "--no-ff", self.develop_branch, "-m", merge_message
        )
        if not merge_result["success"]:
            self._run_git("merge", "--abort")
            self._run_git("checkout", original_branch)
            return {
                "success": False,
                "error": merge_result.get("stderr")
                or merge_result.get("error")
                or "Merge falló",
                "merge_message": merge_message,
            }

        push_result = self._run_git("push", self.remote, self.main_branch)
        self._run_git("checkout", original_branch)
        if not push_result["success"]:
            return {
                "success": False,
                "error": push_result.get("stderr")
                or push_result.get("error")
                or "Push a main falló",
                "merge_message": merge_message,
            }

        head_result = self._run_git("rev-parse", self.main_branch)
        return {
            "success": True,
            "action": "promover",
            "branch": original_branch,
            "main_branch": self.main_branch,
            "merge_message": merge_message,
            "main_head": head_result.get("stdout", "")[:8],
            "git_pushed": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "next_step": "Si corresponde, ejecutar despliegue manual fuera del backend.",
        }

    def run_hotfix_sync(
        self,
        confirm: bool = False,
        summary: str = "",
        compose_repo_path: str | None = None,
        desarrollo_repo_path: str | None = None,
    ) -> dict[str, Any]:
        """Sincroniza main → develop tras un hotfix commiteado en /compose.

        Por default opera sobre /compose (origen del hotfix) y /desarrollo
        (destino del sync). Construye dos LocalGitOps con target_branch
        adecuado a cada working tree y orquesta el flujo.

        Pre-condiciones:
        - /compose está en main con commits nuevos (adelantado de origin/main)
        - /desarrollo está limpio en develop

        Pasos:
        1) git push origin main  (en /compose)
        2) git fetch origin       (en /desarrollo)
        3) git merge --no-ff origin/main -m "hotfix: ..." (en /desarrollo)
        4) git push origin develop (en /desarrollo)

        Si falla cualquier paso, devuelve error sin completar pasos siguientes.
        """
        compose_path = compose_repo_path or str(Path(self.repo_path).parent / "compose")
        desarrollo_path = desarrollo_repo_path or str(
            Path(self.repo_path).parent / "desarrollo"
        )

        compose_ops = LocalGitOps(
            repo_path=compose_path,
            remote=self.remote,
            develop_branch=self.develop_branch,
            main_branch=self.main_branch,
            target_branch=self.main_branch,
        )
        desarrollo_ops = LocalGitOps(
            repo_path=desarrollo_path,
            remote=self.remote,
            develop_branch=self.develop_branch,
            main_branch=self.main_branch,
            target_branch=self.develop_branch,
        )

        compose_status = compose_ops.get_status()
        desarrollo_status = desarrollo_ops.get_status()

        if not compose_status.get("available", False):
            return {
                "success": False,
                "error": f"/compose no disponible: {compose_status.get('error', '?')}",
            }
        if not desarrollo_status.get("available", False):
            return {
                "success": False,
                "error": f"/desarrollo no disponible: {desarrollo_status.get('error', '?')}",
            }

        ahead_main = compose_status.get("ahead", 0)
        merge_message = (
            f"hotfix: {self._sanitize_summary(summary) or 'sync main → develop'}"
        )

        preview = {
            "success": False,
            "requires_confirmation": True,
            "action": "hotfix_sync main -> develop",
            "compose_branch": compose_status.get("branch"),
            "compose_ahead_of_origin_main": ahead_main,
            "develop_branch": desarrollo_status.get("branch"),
            "develop_is_clean": desarrollo_status.get("is_clean", False),
            "merge_message": merge_message,
            "step_1_preview": {
                "cmd": f"cd {compose_path} && git push {self.remote} {self.main_branch}",
                "would_push_commits": ahead_main,
            },
        }

        if not confirm:
            preview["message"] = (
                "Preview generado. Ejecutar run_hotfix_sync(confirm=true) "
                "para aplicar el sync."
            )
            return preview

        if compose_status.get("branch") != self.main_branch:
            return {
                "success": False,
                "error": (
                    f"run_hotfix_sync requiere /compose en {self.main_branch}, "
                    f"está en {compose_status.get('branch')}"
                ),
                "compose_branch": compose_status.get("branch"),
            }

        if not compose_status.get("is_clean", False):
            return {
                "success": False,
                "error": (
                    "/compose tiene cambios uncommitted. Commiteá o stasheá "
                    "antes de run_hotfix_sync."
                ),
                "compose_status": compose_status,
            }

        if desarrollo_status.get("branch") != self.develop_branch:
            return {
                "success": False,
                "error": (
                    f"run_hotfix_sync requiere /desarrollo en {self.develop_branch}, "
                    f"está en {desarrollo_status.get('branch')}"
                ),
                "develop_branch": desarrollo_status.get("branch"),
            }

        if not desarrollo_status.get("is_clean", False):
            return {
                "success": False,
                "error": (
                    "/desarrollo tiene cambios uncommitted. Commiteá o stasheá "
                    "antes de run_hotfix_sync."
                ),
                "develop_status": desarrollo_status,
            }

        # Step 1: push main en /compose
        r1 = compose_ops._run_git("push", self.remote, self.main_branch)
        if not r1["success"]:
            return {
                "success": False,
                "step": "compose_push_main",
                "error": r1.get("stderr") or r1.get("error") or "Push a main falló",
            }

        # Step 2: fetch origin en /desarrollo
        r2 = desarrollo_ops._run_git("fetch", self.remote)
        if not r2["success"]:
            return {
                "success": False,
                "step": "develop_fetch",
                "error": r2.get("stderr") or r2.get("error") or "Fetch falló",
            }

        # Step 3: merge origin/main en /desarrollo (--no-ff para preservar historial)
        r3 = desarrollo_ops._run_git(
            "merge", "--no-ff", f"origin/{self.main_branch}", "-m", merge_message
        )
        if not r3["success"]:
            desarrollo_ops._run_git("merge", "--abort")
            return {
                "success": False,
                "step": "develop_merge",
                "error": r3.get("stderr") or r3.get("error") or "Merge falló",
                "merge_message": merge_message,
                "note": "Merge abortado automáticamente. /desarrollo queda como estaba.",
            }

        # Step 4: push develop en /desarrollo
        r4 = desarrollo_ops._run_git("push", self.remote, self.develop_branch)
        if not r4["success"]:
            return {
                "success": False,
                "step": "develop_push",
                "error": r4.get("stderr") or r4.get("error") or "Push a develop falló",
                "merge_message": merge_message,
                "note": "Merge local OK pero push falló. Reintentar push manual.",
            }

        develop_head = desarrollo_ops._run_git("rev-parse", self.develop_branch)
        return {
            "success": True,
            "action": "hotfix_sync",
            "compose_commit_count": ahead_main,
            "develop_merge_message": merge_message,
            "develop_head": develop_head.get("stdout", "")[:8],
            "git_pushed": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "next_step": (
                "/desarrollo tiene los commits de main. /compose sigue en main. "
                "Si vas a promover develop→main vía run_promover, ahora los commits "
                "estarán duplicados; usá git pull --ff-only o noop."
            ),
        }

    def _resolve_compare_target(self) -> str:
        remote_ref = f"refs/remotes/{self.remote}/{self.develop_branch}"
        local_ref = f"refs/heads/{self.develop_branch}"
        if self._ref_exists(remote_ref):
            return f"{self.remote}/{self.develop_branch}...HEAD"
        if self._ref_exists(local_ref):
            return f"{self.develop_branch}...HEAD"
        return "HEAD"

    def _ref_exists(self, ref_name: str) -> bool:
        result = self._run_git("show-ref", "--verify", "--quiet", ref_name)
        return result["success"]

    def _resolve_branch_ref(self, branch: str) -> str:
        remote_ref = f"refs/remotes/{self.remote}/{branch}"
        local_ref = f"refs/heads/{branch}"
        if self._ref_exists(remote_ref):
            return f"{self.remote}/{branch}"
        if self._ref_exists(local_ref):
            return branch
        return branch

    def _build_salvar_message(self, summary: str) -> str:
        clean_summary = self._sanitize_summary(summary)
        if not clean_summary:
            return "chore: salvar cambios locales"
        if ":" in clean_summary:
            return clean_summary
        return f"chore: {clean_summary}"

    def _build_promover_message(self, summary: str) -> str:
        clean_summary = self._sanitize_summary(summary) or "promoción local"
        return f"merge: promoción {datetime.now(timezone.utc).strftime('%Y-%m-%d')} — {clean_summary}"

    def _sanitize_summary(self, summary: str) -> str:
        allowed = [
            char for char in summary[:120] if char.isalnum() or char in " _-.,;:()/"
        ]
        return "".join(allowed).strip()

    def _checkout_main_branch(self) -> dict[str, Any]:
        local_main = f"refs/heads/{self.main_branch}"
        remote_main = f"refs/remotes/{self.remote}/{self.main_branch}"
        if self._ref_exists(local_main):
            return self._run_git("checkout", self.main_branch)
        if self._ref_exists(remote_main):
            return self._run_git(
                "checkout", "-B", self.main_branch, f"{self.remote}/{self.main_branch}"
            )
        return self._run_git("checkout", "-B", self.main_branch, self.develop_branch)

    def _pull_main_if_available(self) -> dict[str, Any]:
        remote_main = f"refs/remotes/{self.remote}/{self.main_branch}"
        if self._ref_exists(remote_main):
            return self._run_git("pull", "--ff-only", self.remote, self.main_branch)
        return {"success": True, "stdout": "", "stderr": "", "returncode": 0}


def _git_ops(config: AppConfig, arguments: dict) -> LocalGitOps:
    repo_path = arguments.get("repo_path", config.paths.development_repo)
    resolved_repo = resolve_allowed_path(config, repo_path)
    if not resolved_repo.is_dir():
        raise ValueError(f"Repo inválido: {repo_path}")
    return LocalGitOps(
        repo_path=str(resolved_repo),
        remote=arguments.get("remote", "origin"),
        develop_branch=arguments.get("develop_branch", "develop"),
        main_branch=arguments.get("main_branch", "main"),
        target_branch=arguments.get("target_branch"),
    )


def get_git_status(config: AppConfig, arguments: dict) -> dict[str, Any]:
    return _git_ops(config, arguments).get_status()


def get_git_log(config: AppConfig, arguments: dict) -> dict[str, Any]:
    limit = int(arguments.get("n", 10))
    return _git_ops(config, arguments).get_log(limit=limit)


def diff_with_develop(config: AppConfig, arguments: dict) -> dict[str, Any]:
    return _git_ops(config, arguments).diff_with_develop()


def get_pipeline_summary(config: AppConfig, arguments: dict) -> dict[str, Any]:
    return _git_ops(config, arguments).get_pipeline_summary()


def run_salvar(config: AppConfig, arguments: dict) -> dict[str, Any]:
    return _git_ops(config, arguments).run_salvar(
        confirm=bool(arguments.get("confirm", False)),
        summary=str(arguments.get("summary", "")),
        force_branch=arguments.get("force_branch"),
    )


def run_promover(config: AppConfig, arguments: dict) -> dict[str, Any]:
    return _git_ops(config, arguments).run_promover(
        confirm=bool(arguments.get("confirm", False)),
        summary=str(arguments.get("summary", "")),
    )


def run_hotfix_sync(config: AppConfig, arguments: dict) -> dict[str, Any]:
    """Sincroniza hotfix main→develop.

    Requiere que /compose esté commiteado en main y /desarrollo limpio en develop.
    Para configurar paths alternativos pasar `compose_repo_path` y/o
    `desarrollo_repo_path` en arguments.
    """
    ops = _git_ops(config, arguments)
    return ops.run_hotfix_sync(
        confirm=bool(arguments.get("confirm", False)),
        summary=str(arguments.get("summary", "")),
        compose_repo_path=arguments.get("compose_repo_path"),
        desarrollo_repo_path=arguments.get("desarrollo_repo_path"),
    )
