"""Planned requests for the git workspace commands, `branches` and `repos` (#412, #886, #2258).

A dry run makes zero external requests and returns ordered PlannedRequest items. Each command
comes from the same builder that the real run calls, so the plan cannot drift from the run. A
read of the local repository (its remotes, its current branch, its tracking remote) runs in a
dry run, because it makes no external request.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.constants import CONST_VSCODE_CLI
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.git.operations import clone_argv, fetch_commands, git_argv, pull_command
from devops_cli.github.client import org_repos_path, own_repos_path


def reload_workspace_argv(workspace_file: Path) -> list[str]:
    """The command that opens `workspace_file` in the VS Code window that is open."""
    return [CONST_VSCODE_CLI, "--reuse-window", "--", str(workspace_file)]


def plan_repo_sync(repo_dir: Path, label: str, *, pull: bool = True) -> list[PlannedRequest]:
    """The fetch of each remote of `repo_dir`, then the pull of its tracking branch."""
    commands = [args for _remote, args in fetch_commands(repo_dir)]
    if pull:
        command = pull_command(repo_dir)
        if command is not None:
            commands.append(command[1])
    return [
        PlannedRequest(method="git", target=label, argv=tuple(git_argv(repo_dir, *args)))
        for args in commands
    ]


def plan_reload_workspace(workspace_file: Path) -> list[PlannedRequest]:
    """The VS Code command that reloads the workspace after a sync or a clone."""
    return [
        PlannedRequest(
            method=CONST_VSCODE_CLI,
            target=str(workspace_file),
            argv=tuple(reload_workspace_argv(workspace_file)),
        )
    ]


def plan_clone(url: str, dest: Path, workspace_file: Path) -> list[PlannedRequest]:
    """The clone of `url` to `dest`, then the reload of the workspace."""
    return [
        PlannedRequest(method="git", target=str(dest), argv=tuple(clone_argv(url, dest))),
        *plan_reload_workspace(workspace_file),
    ]


def plan_clone_org(
    org_name: str, org_dir: Path, workspace_file: Path, *, include_private: bool = True
) -> list[PlannedRequest]:
    """The listing of the repositories of `org_name`, its fallback to the own account, the
    clone of each listed repository, then the reload of the workspace. The names of the listed
    repositories are known only to the run, so they are placeholders."""
    repo_url = "https://github.com/<owner>/<repo>.git"
    dest = org_dir / "<repo>"
    return [
        PlannedRequest(
            method="GET",
            target=org_repos_path(org_name, include_private=include_private),
            repeat="for each next page of the listing",
        ),
        PlannedRequest(
            method="GET",
            target="/user",
            condition="GitHub answers 404 for the organization and the session has no login",
        ),
        PlannedRequest(
            method="GET",
            target=own_repos_path(include_private=include_private),
            condition=f"GitHub answers 404 for the organization and {org_name} is the login",
            repeat="for each next page of the listing",
        ),
        PlannedRequest(
            method="git",
            target=str(dest),
            argv=tuple(clone_argv(repo_url, dest)),
            repeat="for each listed repository whose directory does not exist",
        ),
        *plan_reload_workspace(workspace_file),
    ]
