"""Shared helper for viewing GitHub workflow run details and logs."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from devops_cli.config.defaults import DEFAULT_GH_RUN_LOG_TIMEOUT_SECONDS
from devops_cli.github.rate_limiter import run_gh
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.dry_run.requests import PlannedRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunViewResult:
    """Result of viewing a workflow run log."""

    returncode: int
    stdout: str
    stderr: str


def run_view_args(
    run_id: int | str,
    *,
    log_failed: bool = False,
    full_log: bool = False,
    job: str | None = None,
    repo: str | None = None,
) -> list[str]:
    """Build the `gh run view` argument list."""
    cmd = ["run", "view", str(run_id)]
    if log_failed:
        cmd.append("--log-failed")
    elif full_log:
        cmd.append("--log")
    if job:
        cmd.extend(["--job", str(job)])
    if repo:
        cmd.extend(["--repo", str(repo)])
    return cmd


def fetch_workflow_run_view(
    run_id: int | str,
    *,
    log_failed: bool = False,
    full_log: bool = False,
    job: str | None = None,
    repo: str | None = None,
    runner: Callable[..., Any] = run_gh,
    timeout: float = DEFAULT_GH_RUN_LOG_TIMEOUT_SECONDS,
) -> RunViewResult:
    """Execute `gh run view` with rate limiting, timeouts, and masked output."""
    cmd = run_view_args(run_id, log_failed=log_failed, full_log=full_log, job=job, repo=repo)
    res = runner(cmd, check=False, timeout=timeout)
    stdout_masked = mask_secrets(res.stdout or "")
    stderr_masked = mask_secrets(res.stderr or "")
    return RunViewResult(
        returncode=res.returncode,
        stdout=stdout_masked,
        stderr=stderr_masked,
    )


def runs_view_requests(
    run_id: int | str,
    *,
    log_failed: bool = False,
    full_log: bool = False,
    job: str | None = None,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Planned requests for viewing a workflow run."""
    from devops_cli.roadmap.request_plan import planned_gh

    args = run_view_args(run_id, log_failed=log_failed, full_log=full_log, job=job, repo=repo)
    return [planned_gh(args, f"repos/{repo or '<repo>'}/actions/runs/{run_id}")]


def runs_list_args(
    limit: int = 10,
    branch: str | None = None,
    repo: str | None = None,
) -> list[str]:
    """Build the `gh run list` argument list."""
    cmd = [
        "run",
        "list",
        "--limit",
        str(limit),
        "--json",
        "databaseId,name,status,conclusion,headBranch,event,url",
    ]
    if branch:
        cmd.extend(["--branch", branch])
    if repo:
        cmd.extend(["--repo", repo])
    return cmd


def runs_list_requests(
    limit: int = 10,
    branch: str | None = None,
    repo: str | None = None,
) -> list[PlannedRequest]:
    """Planned requests for listing workflow runs."""
    from devops_cli.roadmap.request_plan import planned_gh

    args = runs_list_args(limit=limit, branch=branch, repo=repo)
    return [planned_gh(args, f"repos/{repo or '<repo>'}/actions/runs")]
