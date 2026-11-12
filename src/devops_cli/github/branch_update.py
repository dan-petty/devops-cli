"""GitHub branch update planning, the check reads that decide an update, and CLI command
builders."""

from __future__ import annotations

import json

from devops_cli.config.constants import (
    CONST_CI_WORKFLOW_FILE,
    CONST_GH_CLI,
)
from devops_cli.config.defaults import (
    DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS,
    DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.check_verdict import (
    CheckBucket,
    PaginatingSession,
    read_check_runs,
    read_required_check_names,
)
from devops_cli.github.session import get_github_session

_NO_CONFLICT = "no conflict"
_UPDATE_CONDITION = "no conflict, and a required check failed on the head"


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


def plan_update_single_pr(
    number: int,
    target_repo: str,
    expected_head_sha: str | None = None,
    dispatch_ci: bool = False,
) -> list[PlannedRequest]:
    """The requests of `devops pr update <number>`: the read of the pull request, the reads of
    the required checks and of the check runs of its head, and the update only when they find a
    failed required check and GitHub reports no conflict."""
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/pulls/{number}",
            argv=(CONST_GH_CLI, "api", f"repos/{target_repo}/pulls/{number}"),
        ),
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/rules/branches/<base>",
            condition=_NO_CONFLICT,
            repeat="for each page",
        ),
        PlannedRequest(
            method="GET",
            target=f"repos/{target_repo}/commits/<head-sha>/check-runs",
            condition=_NO_CONFLICT,
            repeat="for each page",
        ),
        PlannedRequest(
            method="PUT",
            target=f"repos/{target_repo}/pulls/{number}/update-branch",
            argv=tuple(
                build_update_branch_cmd(target_repo, number, expected_head_sha or "<head-sha>")
            ),
            condition=_UPDATE_CONDITION,
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


def failed_required_checks(
    target_repo: str,
    base_ref: str,
    head_sha: str,
    *,
    session: PaginatingSession | None = None,
) -> tuple[tuple[str, ...], str]:
    """The names of the checks that the rules of `base_ref` require and that failed on
    `head_sha`, sorted, and the reason they could not be read: empty when they were read.

    The rules and the check runs are read through `session`, the GitHub session of the process
    unless one is given. A read that fails gives no names, so no caller updates on a part of the
    checks.
    """
    owner, repo_name = target_repo.split("/", 1)
    listing = session or get_github_session()
    try:
        required = read_required_check_names(listing, target_repo, base_ref)
    except GitHubOperationError as exc:
        return (), str(exc)
    summary = read_check_runs(owner, repo_name, head_sha, session=listing)
    if summary.unread_reason:
        return (), summary.unread_reason
    failed = {
        item.name
        for item in summary.items
        if item.bucket is CheckBucket.FAIL and item.name in required
    }
    return tuple(sorted(failed)), ""
