"""The roadmap step `watch`: one pure function gives the verdict of a pull request, and block mode
watches the pull request until it settles (ADR 0021, section 8; #5021)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

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
from devops_cli.roadmap.pr_verdict import VERDICT_LABEL_NAMES

logger = logging.getLogger(__name__)

# Pattern for skip-ci in commit message (Owner decision 2026-11-13 / #5482 Phase 3)
_SKIP_CI_RE = re.compile(r"\[(?:skip ci|ci skip)\]", re.IGNORECASE)

# A monitor stops when this many polls in a row fail to read the pull request (#4838).
_MAX_CONSECUTIVE_READ_FAILURES = 3

# The classes of a failed check that a fix-checks unit takes (ADR 0021, section 8; #5027). A
# `ci_infra` failure, such as a failed `Semantic PR title`, gets no unit.
FIX_CHECK_CLASSES: Final[frozenset[FailureClass]] = frozenset(
    {FailureClass.TEST, FailureClass.LINT, FailureClass.TYPES, FailureClass.PLAN_DEFECT}
)


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


class DueStep(StrEnum):
    """The due steps that a pull request verdict routes to (#5024)."""

    READY = "ready"
    COMMENT_CONFLICT = "comment_conflict"
    STOP = "stop"
    FIX_CHECKS = "fix_checks"
    STATUS_SYNC = "status_sync"
    CLEANUP = "cleanup"


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
    author: str = ""
    is_bot: bool = False
    is_plan: bool = False
    has_live_unit: bool = False
    labels: tuple[str, ...] = ()

    @property
    def bot(self) -> bool:
        """Whether this pull request was created by the Service or App bot."""
        if self.is_bot:
            return True
        if self.author:
            return (
                self.author.endswith("[bot]")
                or self.author.startswith("app/")
                or self.author == "devops-cli-service"
            )
        return False


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


def _check_items(state: WatchState) -> Sequence[PRCheckItem]:
    if state.checks is None:
        return ()
    return state.checks.items if isinstance(state.checks, CheckVerdictSummary) else state.checks


def fix_checks_check(state: WatchState) -> str | None:
    """The check of the fix-checks unit of `state` (#5027): the failed check whose log holds the
    cause, a shard of `Tests & Coverage` first (`_first_failure`), when the class of its name is
    one of `FIX_CHECK_CLASSES`. None when no check failed or the class is `ci_infra`. A cancelled
    check is no failure of the code, so it gives no unit. The watch row reads no log, so the class
    comes from the name, as the verdict reads it."""
    failed = [check for check in _check_items(state) if check.bucket is CheckBucket.FAIL]
    if not failed:
        return None
    first = _first_failure(failed)
    if classify_failure(FailureEvidence(check=first.name)) not in FIX_CHECK_CLASSES:
        return None
    return first.name


def unrepaired_check(state: WatchState) -> str | None:
    """The check of `state` that no fix-checks unit repairs (#6559): the first failed or cancelled
    check (`_first_failure`), when it was cancelled or when the class of its name is not one of
    `FIX_CHECK_CLASSES`. None when no check failed or was cancelled, when a unit repairs it, or
    when GitHub could not say how the checks ended: a later read may say."""
    if isinstance(state.checks, CheckVerdictSummary) and state.checks.unread_reason:
        return None
    ended = [c for c in _check_items(state) if c.bucket in (CheckBucket.FAIL, CheckBucket.CANCEL)]
    if not ended:
        return None
    first = _first_failure(ended)
    if first.bucket is CheckBucket.CANCEL:
        return first.name
    if classify_failure(FailureEvidence(check=first.name)) in FIX_CHECK_CLASSES:
        return None
    return first.name


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


# The verdict label that lets a green pull request be marked ready.
_MERGEABLE_LABEL = "verdict/mergeable"


def ready_held(labels: Sequence[str]) -> bool:
    """Whether a verdict label other than `verdict/mergeable` holds the ready mark of a green
    pull request: the review step or another check sent the work back (#6024)."""
    return any(name in VERDICT_LABEL_NAMES and name != _MERGEABLE_LABEL for name in labels)


def _failed_steps(state: WatchState) -> tuple[DueStep, ...]:
    """The due step of a bot pull request with a failed check: `fix_checks` for the check that a
    unit repairs, else `stop` for a delivery whose check no unit repairs (#6559)."""
    if fix_checks_check(state) is not None:
        return (DueStep.FIX_CHECKS,)
    if not state.is_plan and unrepaired_check(state) is not None:
        return (DueStep.STOP,)
    return ()


def due_steps(state: WatchState) -> tuple[DueStep, ...]:
    """One pure function gives the due steps for a pull request (ADR 0021, section 8; #5024).

    Routes:
    - Live unit active: skipped (returns ())
    - Skip-ci: no verdict (returns ())
    - READY: `ready` step for bot PRs, unless a verdict label other than `verdict/mergeable`
      holds it (#6024); nothing for person PRs
    - CONFLICT: `comment_conflict` for person PRs; `stop` for a bot delivery (#6559); nothing for
      a bot plan
    - FAILED: `fix_checks` for bot PRs whose failed check `fix_checks_check` names (#5027);
      `stop` for a bot delivery whose check `unrepaired_check` names, as a check of CI_INFRA or a
      cancelled check (#6559); nothing for person PRs
    - MERGED / CLOSED: `status_sync` (plus `cleanup` for bot plan PRs)
    - PENDING / BEHIND / THREADS / HEAD_MOVED: ()
    """
    if state.has_live_unit:
        return ()

    v = verdict(state)
    if v is None:
        return ()

    is_bot = state.bot

    if v.verdict is PRVerdict.READY:
        return (DueStep.READY,) if is_bot and not ready_held(state.labels) else ()

    if v.verdict is PRVerdict.CONFLICT:
        if not is_bot:
            return (DueStep.COMMENT_CONFLICT,)
        return () if state.is_plan else (DueStep.STOP,)

    if v.verdict is PRVerdict.FAILED:
        return _failed_steps(state) if is_bot else ()

    if v.verdict in (PRVerdict.MERGED, PRVerdict.CLOSED):
        if is_bot and state.is_plan:
            return (DueStep.STATUS_SYNC, DueStep.CLEANUP)
        return (DueStep.STATUS_SYNC,)

    return ()


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
