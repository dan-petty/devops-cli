"""The roadmap step `watch`: one pure function gives the verdict of a pull request, and block mode
watches the pull request until it settles (ADR 0021, section 8; #5021)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from devops_cli.config.constants import (
    CONST_CI_TEST_JOB_NAME,
)
from devops_cli.core import clock
from devops_cli.exceptions import GitHubOperationError
from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.github.merge_readiness import merge_conflict
from devops_cli.github.pr_threads import ReviewThread
from devops_cli.github.session import get_github_session
from devops_cli.output import print_warning
from devops_cli.roadmap.failure import (
    FailureClass,
    FailureEvidence,
    classify_failure,
)

logger = logging.getLogger(__name__)

# Pattern for skip-ci in commit message (Owner decision 2026-11-13 / #5482 Phase 3)
_SKIP_CI_RE = re.compile(r"\[(?:skip ci|ci skip)\]", re.IGNORECASE)

# A monitor stops when this many polls in a row fail to read the pull request (#4838).
_MAX_CONSECUTIVE_READ_FAILURES = 3


class PRVerdict(StrEnum):
    """The verdict of watching a pull request."""

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    CONFLICT = "conflict"
    BEHIND = "behind"
    THREADS = "threads"
    MERGED = "merged"
    CLOSED = "closed"
    HEAD_MOVED = "head_moved"


@dataclass(frozen=True)
class WatchVerdict:
    """The outcome of the verdict function."""

    verdict: PRVerdict
    check: str | None = None
    failure_class: FailureClass | str | None = None
    reason: str = ""

    def to_json(self) -> str:
        """JSON serialization for CLI output."""
        return json.dumps(
            {
                "verdict": self.verdict.value,
                "check": self.check,
                "failure_class": (
                    self.failure_class.value
                    if isinstance(self.failure_class, FailureClass)
                    else self.failure_class
                ),
                "reason": self.reason,
            }
        )


@dataclass(frozen=True)
class WatchState:
    """The facts of a pull request that `verdict` reads."""

    pull: int
    head_sha: str
    state: str = "open"
    merged: bool = False
    draft: bool = False
    base_ref: str = "main"
    mergeable: bool | None = True
    mergeable_state: str = "clean"
    expected_head: str | None = None
    commit_message: str | None = None
    checks: CheckVerdictSummary | Sequence[PRCheckItem] | None = None
    unresolved_threads: int | Sequence[ReviewThread] = 0


def _first_failure(failing: Sequence[PRCheckItem]) -> PRCheckItem:
    """The failed check whose log holds the cause. The join check `Tests & Coverage` fails when a
    test shard failed, and its log holds no test output (#3050). A failed shard check is the one
    to read then."""
    shard_prefix = f"{CONST_CI_TEST_JOB_NAME} (shard "
    for check in failing:
        if check.name.startswith(shard_prefix):
            return check
    return failing[0]


def _lifecycle_verdict(state: WatchState) -> WatchVerdict | None:
    """Judge pull request lifecycle states (merged, closed, conflict, behind, head moved)."""
    if state.expected_head and state.head_sha and state.head_sha != state.expected_head:
        return WatchVerdict(
            verdict=PRVerdict.HEAD_MOVED,
            reason=(
                f"PR #{state.pull} head {state.head_sha[:12]} does not match "
                f"expected head {state.expected_head[:12]}."
            ),
        )

    if state.merged or state.state.lower() == "merged":
        return WatchVerdict(verdict=PRVerdict.MERGED, reason=f"PR #{state.pull} is merged.")

    if state.state.lower() == "closed":
        return WatchVerdict(
            verdict=PRVerdict.CLOSED, reason=f"PR #{state.pull} is closed without being merged."
        )

    if merge_conflict(state.mergeable, state.mergeable_state):
        return WatchVerdict(
            verdict=PRVerdict.CONFLICT,
            reason=f"PR #{state.pull} has merge conflicts with base branch '{state.base_ref}'.",
        )

    if state.mergeable_state.lower() == "behind":
        return WatchVerdict(
            verdict=PRVerdict.BEHIND,
            reason=f"PR #{state.pull} is behind base branch '{state.base_ref}'.",
        )

    return None


def _checks_verdict(state: WatchState) -> WatchVerdict:
    """Judge check runs and review threads on a settled commit."""
    # A poll that reads no check is PENDING (#4927).
    if state.checks is None:
        return WatchVerdict(
            verdict=PRVerdict.PENDING, reason=f"PR #{state.pull} has no check runs reported yet."
        )

    items: Sequence[PRCheckItem] = (
        state.checks.items if isinstance(state.checks, CheckVerdictSummary) else state.checks
    )
    if not items:
        return WatchVerdict(
            verdict=PRVerdict.PENDING, reason=f"PR #{state.pull} has no check runs reported yet."
        )

    if isinstance(state.checks, CheckVerdictSummary) and state.checks.unread_reason:
        return WatchVerdict(
            verdict=PRVerdict.FAILED,
            failure_class=FailureClass.CI_INFRA,
            reason=state.checks.unread_reason,
        )

    failing = [
        c for c in items if c.bucket in (CheckBucket.FAIL, CheckBucket.CANCEL, CheckBucket.UNREAD)
    ]
    if failing:
        first = _first_failure(failing)
        klass = classify_failure(FailureEvidence(check=first.name))
        return WatchVerdict(
            verdict=PRVerdict.FAILED,
            check=first.name,
            failure_class=klass,
            reason=f"Check '{first.name}' failed.",
        )

    pending = [c for c in items if c.bucket == CheckBucket.PENDING]
    if pending:
        return WatchVerdict(
            verdict=PRVerdict.PENDING,
            reason=f"PR #{state.pull} has {len(pending)} check(s) pending.",
        )

    threads_count = (
        len(state.unresolved_threads)
        if isinstance(state.unresolved_threads, Sequence)
        else state.unresolved_threads
    )
    if threads_count > 0:
        return WatchVerdict(
            verdict=PRVerdict.THREADS,
            reason=f"PR #{state.pull} has {threads_count} unresolved thread(s).",
        )

    return WatchVerdict(verdict=PRVerdict.READY, reason=f"PR #{state.pull} is ready.")


def verdict(state: WatchState) -> WatchVerdict | None:
    """One pure function gives the verdict of a pull request state.

    Returns None when the head commit message holds `[skip ci]`: the verdict judges only a
    checked head (Owner decision 2026-11-13 / #5482 Phase 3).
    """
    if state.commit_message and _SKIP_CI_RE.search(state.commit_message):
        return None

    lifecycle = _lifecycle_verdict(state)
    if lifecycle is not None:
        return lifecycle

    return _checks_verdict(state)


def _read_watch_state(
    repo: str,
    pull: int,
    expected_head: str | None = None,
) -> WatchState:
    """Read the live facts of pull request `pull` from GitHub."""
    owner, name = repo.split("/", 1)
    client = get_github_session().client
    pull_status = client.get_pull_status(repo, pull)
    head_sha = pull_status.head_sha

    from devops_cli.github.check_verdict import read_check_runs

    checks = read_check_runs(owner, name, head_sha) if head_sha else ()
    return WatchState(
        pull=pull,
        head_sha=head_sha,
        state=pull_status.state,
        merged=pull_status.merged,
        draft=pull_status.draft,
        base_ref=pull_status.base_ref,
        mergeable=pull_status.mergeable,
        mergeable_state=pull_status.mergeable_state,
        expected_head=expected_head,
        checks=checks,
    )


def watch(
    repo: str,
    pull: int,
    expected_head: str | None = None,
    *,
    timeout: int = 3600,
    interval: int = 60,
    block: bool = True,
    status_callback: Callable[[WatchState, int], None] | None = None,
) -> WatchVerdict:
    """Watch pull request `pull` of `repo` until its verdict settles.

    A failed read is read again at the next poll (#4838).
    Block mode polls every `interval` seconds up to `timeout` seconds.
    """
    valid_interval = max(1, interval)
    valid_timeout = max(1, timeout)
    start_time = clock.monotonic()
    deadline = start_time + valid_timeout
    failures = 0

    while True:
        now = clock.monotonic()
        elapsed = int(now - start_time)
        try:
            state = _read_watch_state(repo, pull, expected_head)
            failures = 0
        except GitHubOperationError as exc:
            failures += 1
            if failures >= _MAX_CONSECUTIVE_READ_FAILURES or not block:
                raise
            print_warning(
                f"Failed to read PR #{pull} ({failures} of {_MAX_CONSECUTIVE_READ_FAILURES}): "
                f"{exc}. Polling again in {valid_interval}s..."
            )
            clock.sleep(valid_interval)
            continue

        if status_callback is not None:
            status_callback(state, elapsed)

        res = verdict(state)
        if res is None:
            return WatchVerdict(
                verdict=PRVerdict.PENDING,
                reason="Head commit has [skip ci]: no verdict.",
            )

        if not block or res.verdict != PRVerdict.PENDING:
            return res

        if now + valid_interval > deadline:
            return WatchVerdict(
                verdict=PRVerdict.PENDING,
                reason=f"Watch of PR #{pull} timed out after {elapsed}s with checks still pending.",
            )

        clock.sleep(valid_interval)
