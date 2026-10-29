"""The calls the implement job makes about its pull request (#2665): the watch of its checks, the
log of a failed check, and `gh pr ready`.

All of them run in the job's own process. The agent's shell never calls them, and holds no
credential for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_ROADMAP_IMPLEMENT_HEAD_POLLS,
    CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS
from devops_cli.core import clock
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.github.check_verdict import PRCheckItem
from devops_cli.github.pr_monitor import PRMonitorResult, monitor_pr
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.run_view import fetch_workflow_run_view
from devops_cli.lang import MESSAGES
from devops_cli.security.sanitizer import mask_secrets

# GitHub's name for a pull request that cannot merge because its branch conflicts with the base.
_CONFLICT_STATES = frozenset({"dirty", "conflicting"})
# The index of the run's number in the path of a check's link, after `runs`: `runs/<run>/job/<job>`.
_JOB_SEGMENT = 2


class WatchKind(StrEnum):
    """What the watch found: every check passed, a check failed, or something else stops the
    item."""

    READY = "ready"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(frozen=True)
class Watch:
    """The result of watching a pull request. `reason` says why the item stops or the check failed,
    and `check` is the first failed check."""

    kind: WatchKind
    reason: str = ""
    check: PRCheckItem | None = None


def _judge(result: PRMonitorResult) -> Watch:
    """The watch's verdict on a settled status: the checks first, then the threads, then the
    mergeability. A draft and a blocked merge state are not reasons to stop: a person approves
    the pull request later."""
    texts = MESSAGES.roadmap
    status = result.status
    if status.merged:
        return Watch(WatchKind.STOPPED, texts.implement_stop_merged)
    if result.exit_code == 3 or status.pending_checks:
        reason = texts.implement_stop_checks_timeout.format(
            seconds=CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS
        )
        return Watch(WatchKind.STOPPED, reason)
    if status.checks_failed:
        failing = status.failing_checks
        if not failing:
            return Watch(WatchKind.STOPPED, texts.implement_stop_checks_unread)
        reason = texts.implement_stop_check_failed.format(name=failing[0].name)
        return Watch(WatchKind.FAILED, reason, failing[0])
    if status.unresolved_threads:
        count = len(status.unresolved_threads)
        return Watch(WatchKind.STOPPED, texts.implement_stop_threads.format(count=count))
    if status.mergeable is False or status.mergeable_state in _CONFLICT_STATES:
        return Watch(WatchKind.STOPPED, texts.implement_stop_conflict)
    return Watch(WatchKind.READY)


def watch_pull(repo: str, pull: int, head: str) -> Watch:
    """Watch pull request `pull` of `repo` until the checks of its head `head` settle.

    Right after a push GitHub can still show the old head, with the checks of the old head. A
    status is a result only when its head is `head`; else the watch reads again,
    `CONST_ROADMAP_IMPLEMENT_HEAD_POLLS` times at most. The monitor itself waits while a check
    runs, or while a head holds no check yet, up to
    `CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS`.
    """
    owner, name = repo.split("/", 1)
    for _ in range(CONST_ROADMAP_IMPLEMENT_HEAD_POLLS):
        result = monitor_pr(
            owner,
            name,
            pull,
            timeout=CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS,
            interval=DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS,
            settle_timeout=0,
            require_reviews=False,
        )
        if result.status.head_sha == head:
            return _judge(result)
        clock.sleep(DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS)
    reason = MESSAGES.roadmap.implement_stop_old_head.format(head=head[:12])
    return Watch(WatchKind.STOPPED, reason)


def failed_log(repo: str, check: PRCheckItem) -> str:
    """The log of the failed run of `check`, with credentials masked. It is what `gh` said when it
    cannot read the log, and empty when the link of the check names no run. The fix step then
    works from the name of the check."""
    parts = PurePosixPath(urlsplit(check.link).path).parts
    if "runs" not in parts:
        return ""
    at = parts.index("runs")
    run = parts[at + 1] if len(parts) > at + 1 else ""
    has_job = len(parts) > at + _JOB_SEGMENT + 1 and parts[at + _JOB_SEGMENT] == "job"
    if not run:
        return ""
    viewed = fetch_workflow_run_view(
        run, log_failed=True, job=parts[at + _JOB_SEGMENT + 1] if has_job else None, repo=repo
    )
    return viewed.stdout if viewed.returncode == 0 else viewed.stderr


def mark_ready(repo: str, pull: int) -> None:
    """Mark the draft pull request `pull` ready for review with `gh pr ready`. Raises
    `RoadmapImplementError` when `gh` fails."""
    done = run_gh([CONST_GH_CLI, "pr", "ready", str(pull), "--repo", repo], check=False)
    if done.returncode != 0:
        output = mask_secrets((done.stderr or done.stdout or "").strip())
        raise RoadmapImplementError(
            MESSAGES.roadmap.implement_stop_ready_failed.format(output=output)
        )
