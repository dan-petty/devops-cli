"""GitHub branch update planning and CLI command builders."""

from __future__ import annotations

import json

from devops_cli.config.constants import (
    CONST_CI_WORKFLOW_FILE,
    CONST_GH_CLI,
    CONST_PR_UPDATE_AUTHOR,
)
from devops_cli.config.defaults import (
    DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS,
    DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS,
)
from devops_cli.dry_run.requests import PlannedRequest


def build_update_branch_cmd(
    owner_repo: str,
    number: int,
    expected_head_sha: str | None = None,
) -> list[str]:
    """Build GitHub CLI API invocation for updating a pull request branch."""
    endpoint = f"repos/{owner_repo}/pulls/{number}/update-branch"
    cmd = [CONST_GH_CLI, "api", "-X", "PUT", endpoint]
    if expected_head_sha:
        cmd.extend(["-f", f"expected_head_sha={expected_head_sha}"])
    return cmd


def build_dispatch_ci_cmd(
    owner_repo: str,
    head_ref: str,
) -> list[str]:
    """Build GitHub CLI API invocation for dispatching the CI workflow."""
    endpoint = f"repos/{owner_repo}/actions/workflows/{CONST_CI_WORKFLOW_FILE}/dispatches"
    return [CONST_GH_CLI, "api", "-X", "POST", endpoint, "-f", f"ref={head_ref}"]


def parse_update_error(raw_text: str) -> str:
    """Extract readable error message from gh api failure output."""
    clean = raw_text.strip()
    try:
        data = json.loads(clean)
        if isinstance(data, dict) and "message" in data:
            msg = str(data["message"])
            errors = data.get("errors")
            if isinstance(errors, list) and errors:
                return f"{msg}: {', '.join(str(e) for e in errors)}"
            return msg
    except json.JSONDecodeError:
        pass
    return clean or "Unknown API error"


def open_prs_argv(repo: str | None, base: str | None) -> list[str]:
    """The `gh pr list` arguments that list the open pull requests the current account wrote,
    into `base` when one is given."""
    argv = [
        CONST_GH_CLI,
        "pr",
        "list",
        "--state",
        "open",
        "--author",
        CONST_PR_UPDATE_AUTHOR,
        "--limit",
        "100",
        "--json",
        "number,title,headRefName,baseRefName,isDraft",
    ]
    if repo:
        argv.extend(["--repo", repo])
    if base:
        argv.extend(["--base", base])
    return argv


def plan_update_single_pr(
    number: int,
    target_repo: str,
    expected_head_sha: str | None = None,
    dispatch_ci: bool = False,
) -> list[PlannedRequest]:
    """Generate planned requests for single PR update dry-run."""
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{number}",
            argv=(CONST_GH_CLI, "api", f"repos/{target_repo}/pulls/{number}"),
        ),
        PlannedRequest(
            method="PUT",
            target=f"repos/{target_repo}/pulls/{number}/update-branch",
            argv=tuple(build_update_branch_cmd(target_repo, number, expected_head_sha)),
        ),
    ]
    if dispatch_ci:
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"repos/{target_repo}/pulls/{number}",
                argv=(CONST_GH_CLI, "api", f"repos/{target_repo}/pulls/{number}"),
                repeat=f"up to {DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS}, {DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS:g}s apart",
            )
        )
        requests.append(
            PlannedRequest(
                method="POST",
                target=f"repos/{target_repo}/actions/workflows/{CONST_CI_WORKFLOW_FILE}/dispatches",
                argv=tuple(build_dispatch_ci_cmd(target_repo, "<branch>")),
                condition="the head changed and lives in this repository",
            )
        )
    return requests


def plan_update_all_prs(
    target_repo: str | None,
    target_base: str | None,
    dispatch_ci: bool = False,
) -> list[PlannedRequest]:
    """Generate planned requests for all PRs update dry-run."""
    list_argv = open_prs_argv(target_repo, target_base)
    repo_slug = target_repo or ":owner/:repo"
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="GET",
            target=f"repos/{repo_slug}/pulls",
            argv=tuple(list_argv),
        ),
        PlannedRequest(
            method="GET",
            target=f"repos/{repo_slug}/pulls/<number>",
            argv=(CONST_GH_CLI, "api", f"repos/{repo_slug}/pulls/<number>"),
            repeat="each open non-draft PR",
        ),
        PlannedRequest(
            method="PUT",
            target=f"repos/{repo_slug}/pulls/<number>/update-branch",
            argv=(
                CONST_GH_CLI,
                "api",
                "-X",
                "PUT",
                f"repos/{repo_slug}/pulls/<number>/update-branch",
            ),
            repeat="each open non-draft PR",
        ),
    ]
    if dispatch_ci:
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"repos/{repo_slug}/pulls/<number>",
                argv=(CONST_GH_CLI, "api", f"repos/{repo_slug}/pulls/<number>"),
                repeat=f"each open non-draft PR; up to {DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS}, {DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS:g}s apart",
            )
        )
        requests.append(
            PlannedRequest(
                method="POST",
                target=f"repos/{repo_slug}/actions/workflows/{CONST_CI_WORKFLOW_FILE}/dispatches",
                argv=tuple(build_dispatch_ci_cmd(repo_slug, "<branch>")),
                condition="the head changed and lives in this repository",
                repeat="each open non-draft PR",
            )
        )
    return requests
