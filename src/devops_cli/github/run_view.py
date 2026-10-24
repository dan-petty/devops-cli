"""Shared helper for viewing GitHub workflow run details and logs."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from devops_cli.config.defaults import DEFAULT_GH_RUN_LOG_TIMEOUT_SECONDS
from devops_cli.github.rate_limiter import run_gh
from devops_cli.security.sanitizer import mask_secrets

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
    res = runner(cmd, timeout=timeout)
    stdout_masked = mask_secrets(res.stdout or "")
    stderr_masked = mask_secrets(res.stderr or "")
    return RunViewResult(
        returncode=res.returncode,
        stdout=stdout_masked,
        stderr=stderr_masked,
    )
