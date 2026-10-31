"""Pull Request monitoring engine for CI checks, Copilot review sessions, and threads."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Iterable
from typing import Any, NamedTuple, cast

from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_COPILOT_REVIEWER_LOGINS,
    CONST_GH_CLI,
    CONST_GITHUB_REVIEW_AUTHOR_KEYS,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.core import clock
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.check_verdict import CheckBucket, PRCheckItem
from devops_cli.github.merge_readiness import (
    CHECK_FAILURE_KINDS,
    BlockerKind,
    assess_merge_readiness,
)
from devops_cli.github.pr_threads import GhRun, ReviewThread
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import get_github_session

logger = logging.getLogger(__name__)

_PASSING_BUCKETS = frozenset({CheckBucket.PASS, CheckBucket.SKIPPING})
_FAILING_BUCKETS = frozenset({CheckBucket.FAIL, CheckBucket.CANCEL, CheckBucket.UNREAD})


class CopilotReviewStatus(BaseModel):
    """Status of GitHub Copilot / automated code review session on a pull request."""

    is_active: bool = False
    state: str = "idle"  # idle | working | completed | changes_requested | unread
    unread_reason: str = ""
    message: str = ""
    last_review_at: str = ""
    active_event: str = ""


class PRMonitorStatus(BaseModel):
    """One poll of a pull request: the verdict's checks and blockers, and the review gate's.

    `blockers` holds every blocker, the merge-readiness verdict's and then the review gate's.
    `checks_failed` is whether a check failed or could not be read, which the monitor exits 1 on.
    """

    number: int
    title: str = ""
    head_sha: str = ""
    is_draft: bool = False
    merged: bool = False
    mergeable: bool | None = None
    mergeable_state: str = "unknown"
    review_decision: str | None = None
    has_changes_requested: bool = False
    checks: list[PRCheckItem] = Field(default_factory=list)
    pending_checks: list[str] = Field(default_factory=list)
    copilot_status: CopilotReviewStatus = Field(default_factory=CopilotReviewStatus)
    unresolved_threads: list[ReviewThread] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    checks_failed: bool = False
    require_reviews: bool = True

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    @property
    def completed_checks(self) -> int:
        return sum(1 for c in self.checks if c.bucket != CheckBucket.PENDING)

    @property
    def successful_checks(self) -> int:
        return sum(1 for c in self.checks if c.bucket in _PASSING_BUCKETS)

    @property
    def failing_checks(self) -> list[PRCheckItem]:
        return [c for c in self.checks if c.bucket in _FAILING_BUCKETS]

    @property
    def settled(self) -> bool:
        """Whether no check runs and no Copilot review is active, so the blockers are final."""
        return not self.pending_checks and not self.copilot_status.is_active


class PRMonitorResult(BaseModel):
    """Final outcome of monitoring a pull request."""

    success: bool
    exit_code: int  # 0: ready, 1: a check failed or is unread, 2: another blocker, 3: timeout
    message: str
    status: PRMonitorStatus


def _resolve_current_git_branch(branch_name: str | None) -> str:
    """Resolve target git branch from argument or current repo branch."""
    if branch_name:
        return branch_name
    proc_br = run_subprocess(["git", "branch", "--show-current"])
    target = proc_br.stdout.strip() if proc_br.returncode == 0 else ""
    if not target:
        raise GitHubOperationError("Unable to determine current git branch.")
    return target


def branch_pr_rest_argv(repo_full: str, branch: str) -> list[str]:
    """The gh command that reads the number of `branch`'s open pull request in `owner/repo`
    through the REST API."""
    repo_owner = repo_full.split("/", 1)[0]
    pulls = f"repos/{repo_full}/pulls?head={repo_owner}:{branch}&state=open"
    return [CONST_GH_CLI, "api", pulls, "--jq", ".[0].number"]


def branch_pr_view_argv(repo_full: str | None, branch: str) -> list[str]:
    """The gh command that reads the number of `branch`'s pull request with `gh pr view`, which
    gh answers over GraphQL, in `repo_full` or the checkout's repository."""
    cmd = [CONST_GH_CLI, "pr", "view", branch, "--json", "number", "--jq", ".number"]
    return [*cmd, "-R", repo_full] if repo_full else cmd


def pr_details_argv(owner: str, repo_name: str, pr_number: int | str) -> list[str]:
    """The gh command that reads pull request `pr_number` through the REST API."""
    return [CONST_GH_CLI, "api", f"repos/{owner}/{repo_name}/pulls/{pr_number}"]


def _try_resolve_pr_via_rest(repo_full: str | None, target_branch: str) -> int | None:
    """Attempt to resolve PR number using the REST API."""
    if not repo_full or "/" not in repo_full:
        return None
    res = run_gh(branch_pr_rest_argv(repo_full, target_branch), check=False, quiet=True)
    if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != "null":
        try:
            return int(res.stdout.strip())
        except ValueError:
            return None
    return None


def _resolve_pr_via_gh_view(target_repo: str | None, target_branch: str) -> int:
    """Resolve PR number via gh pr view fallback."""
    proc = run_gh(branch_pr_view_argv(target_repo, target_branch), check=False, quiet=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise GitHubOperationError(f"No open pull request found for branch '{target_branch}'.")
    try:
        return int(proc.stdout.strip())
    except ValueError as exc:
        raise GitHubOperationError(f"Unexpected PR number output: {proc.stdout.strip()}") from exc


def resolve_branch_pr_number(branch_name: str | None = None, *, owner: str, repo: str) -> int:
    """Resolve the number of the open pull request of the current or the specified branch in
    `owner`/`repo`, which the command gives (#2127)."""
    target_branch = _resolve_current_git_branch(branch_name)
    target_repo = f"{owner}/{repo}"
    rest_num = _try_resolve_pr_via_rest(target_repo, target_branch)
    if rest_num is not None:
        return rest_num
    return _resolve_pr_via_gh_view(target_repo, target_branch)


def _extract_timeline_author(evt: dict[str, Any]) -> str:
    """Extract actor or user login from timeline event dictionary."""
    actor = evt.get("actor")
    if isinstance(actor, dict) and actor.get("login"):
        return str(actor["login"])
    user = evt.get("user")
    if isinstance(user, dict) and user.get("login"):
        return str(user["login"])
    author = evt.get("author")
    if isinstance(author, dict) and author.get("login"):
        return str(author["login"])
    if isinstance(author, str):
        return author
    return ""


class CopilotTimeline(NamedTuple):
    """What a pull request's issue timeline says of Copilot: whether a pass is running, the event
    that says so, and why the timeline could not be read, if it could not."""

    working: bool = False
    event: str = ""
    error: str = ""


def _ends_copilot_pass(evt: dict[str, Any], copilot_review_ids: frozenset[int]) -> bool:
    """Whether a `reviewed` event ends Copilot's pass: it records one of Copilot's reviews, named
    by the review's id, or names no author at all."""
    review_id = evt.get("id")
    names_copilot_review = type(review_id) is int and review_id in copilot_review_ids
    return not _extract_timeline_author(evt) or names_copilot_review


def _process_single_timeline_event(
    evt: dict[str, Any], state: CopilotTimeline, copilot_review_ids: frozenset[int]
) -> CopilotTimeline:
    """What the timeline says of Copilot once `evt` is read: its start event runs a pass, and its
    review's `reviewed` event ends it."""
    evt_name = str(evt.get("event") or "")
    if evt_name == "copilot_work_started":
        return CopilotTimeline(working=True, event=evt_name)
    if evt_name == "reviewed" and _ends_copilot_pass(evt, copilot_review_ids):
        return CopilotTimeline(event=evt_name)
    return state


def timeline_copilot_state(
    events: Iterable[Any], copilot_review_ids: frozenset[int]
) -> CopilotTimeline:
    """What a timeline's events, in order, say of Copilot, its own reviews named by
    `copilot_review_ids`."""
    state = CopilotTimeline()
    for evt in events:
        if isinstance(evt, dict):
            state = _process_single_timeline_event(evt, state, copilot_review_ids)
    return state


def is_copilot_login(login: str) -> bool:
    """Whether a review record's author `login` is Copilot code review's bot: exactly one of the
    logins the reviews endpoint and GraphQL give it, never any login that merely contains
    "copilot" (#1345). The issue timeline names the bot otherwise, so its events never use this."""
    return login in CONST_COPILOT_REVIEWER_LOGINS


def _login_of(account: Any) -> str:
    """The login of a REST `user` or GraphQL `author` object; empty when it names none."""
    return str(account.get("login") or "") if isinstance(account, dict) else ""


def is_copilot_review(review: Any) -> bool:
    """Whether a review record is Copilot's: its REST `user` or GraphQL `author` is Copilot's."""
    if not isinstance(review, dict):
        return False
    authors = (review.get(key) for key in CONST_GITHUB_REVIEW_AUTHOR_KEYS)
    return any(is_copilot_login(_login_of(author)) for author in authors)


def _copilot_review_ids(reviews: Iterable[Any]) -> frozenset[int]:
    """The ids of Copilot's reviews among `reviews`: the issue timeline's `reviewed` event for a
    review carries its id, the one way the timeline names a review as Copilot's."""
    ids = (review.get("id") for review in reviews if is_copilot_review(review))
    return frozenset(review_id for review_id in ids if type(review_id) is int)


def is_copilot_changes_recommended(body: str) -> bool:
    """Detect if Copilot review heading recommends changes, excluding 'no changes'."""
    if not body:
        return False
    match = re.search(r"###\s*(.+?)(?:\r?\n|$)", body)
    if not match:
        return False
    heading = match.group(1).strip()
    if re.search(r"no changes\s+(?:recommended|requested)", heading, re.IGNORECASE):
        return False
    return bool(re.search(r"(?:changes recommended|changes requested)", heading, re.IGNORECASE))


def _check_review_changes_requested(review: dict[str, Any] | None) -> tuple[bool, str, str]:
    """Evaluate whether review requests changes and extract state and timestamp."""
    if not review:
        return False, "", ""
    state = str(review.get("state", "")).upper()
    body = str(review.get("body", ""))
    has_changes = state == "CHANGES_REQUESTED" or is_copilot_changes_recommended(body)
    last_time = str(review.get("submittedAt") or review.get("submitted_at") or "")
    return has_changes, state, last_time


def _extract_latest_copilot_review(
    reviews: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, bool, str, str]:
    """Extract latest Copilot review and determine requested changes status."""
    copilot_reviews = [r for r in reviews if is_copilot_review(r)]
    copilot_reviews.sort(key=lambda r: str(r.get("submittedAt") or r.get("submitted_at") or ""))
    latest_review = copilot_reviews[-1] if copilot_reviews else None
    has_changes, latest_state, last_time = _check_review_changes_requested(latest_review)
    return latest_review, has_changes, latest_state, last_time


def _extract_proc_error(proc: Any) -> str:
    """Extract trimmed stderr or exit code from a process result."""
    stderr = str(getattr(proc, "stderr", "") or "").strip()
    if stderr:
        return stderr[:256]
    return f"Exit code {getattr(proc, 'returncode', 1)}"


def query_timeline_copilot_state(
    owner: str, repo_name: str, pr_number: int, copilot_review_ids: frozenset[int]
) -> CopilotTimeline:
    """Read every page of the pull request's issue timeline for Copilot's review events, its own
    reviews named by `copilot_review_ids`, or why the timeline could not be read."""
    timeline = f"/repos/{owner}/{repo_name}/issues/{pr_number}/timeline?per_page={DEFAULT_GH_REST_PER_PAGE}"
    try:
        return timeline_copilot_state(get_github_session().paginate(timeline), copilot_review_ids)
    except GitHubOperationError as exc:
        return CopilotTimeline(error=str(exc)[:CONST_MAX_ERROR_DETAIL_LENGTH])


def _build_changes_status(
    latest_state: str,
    last_time: str,
    active_event: str,
    unresolved_threads: list[ReviewThread] | None,
) -> CopilotReviewStatus:
    """Construct CopilotReviewStatus when changes were requested in latest review."""
    if unresolved_threads is not None and not unresolved_threads:
        return CopilotReviewStatus(
            is_active=False,
            state="completed",
            message="Copilot review session completed (all recommended changes resolved)",
            last_review_at=last_time,
            active_event=active_event,
        )
    msg = (
        "Copilot requested changes on the pull request"
        if latest_state == "CHANGES_REQUESTED"
        else "Copilot recommended changes on the pull request"
    )
    return CopilotReviewStatus(
        is_active=False,
        state="changes_requested",
        message=msg,
        last_review_at=last_time,
        active_event=active_event,
    )


def detect_copilot_status(
    owner: str,
    repo_name: str,
    pr_number: int,
    reviews: list[dict[str, Any]],
    unresolved_threads: list[ReviewThread] | None = None,
    reviews_err: str = "",
) -> CopilotReviewStatus:
    """Inspect timeline events and review states to detect Copilot review activity.

    A timeline `reviewed` event ends Copilot's pass when it carries the id of one of Copilot's
    reviews among `reviews`. A review Copilot submits between the reviews read and the timeline
    read therefore reads as running for this one call, and the monitor sees the pass end on its
    next poll.
    """
    timeline = query_timeline_copilot_state(
        owner, repo_name, pr_number, _copilot_review_ids(reviews)
    )
    err = reviews_err or getattr(reviews, "error", "") or timeline.error
    return _copilot_review_status(reviews, timeline, unresolved_threads, err)


def _copilot_review_status(
    reviews: list[dict[str, Any]],
    timeline: CopilotTimeline,
    unresolved_threads: list[ReviewThread] | None,
    err: str,
) -> CopilotReviewStatus:
    """Copilot's review state from its latest review and what the timeline says of it, or the
    reason `err` that either could not be read."""
    latest_review, has_changes, latest_state, last_time = _extract_latest_copilot_review(reviews)
    copilot_working, active_event = timeline.working, timeline.event
    if err:
        return CopilotReviewStatus(
            is_active=False,
            state="unread",
            unread_reason=err,
            message=f"Copilot review state could not be read: {err}",
            last_review_at=last_time,
            active_event=active_event,
        )

    if copilot_working:
        return CopilotReviewStatus(
            is_active=True,
            state="working",
            message="Copilot review is currently in progress",
            last_review_at=last_time,
            active_event=active_event,
        )
    if has_changes:
        return _build_changes_status(latest_state, last_time, active_event, unresolved_threads)
    if latest_review:
        return CopilotReviewStatus(
            is_active=False,
            state="completed",
            message="Copilot review session completed",
            last_review_at=last_time,
            active_event=active_event,
        )
    return CopilotReviewStatus(
        is_active=False,
        state="idle",
        message="No active Copilot review session",
        last_review_at="",
        active_event=active_event,
    )


class RawReviewsList(list[dict[str, Any]]):
    """List of review dictionaries carrying optional read error reason."""

    error: str = ""

    def __init__(self, items: Any = (), error: str = "") -> None:
        super().__init__(items)
        self.error = error


def fetch_pr_details(
    owner: str, repo_name: str, pr_number: int, *, runner: GhRun = run_gh
) -> dict[str, Any]:
    """Read pull request `pr_number` through the REST API: the one read of a pull request that
    every `devops pr` command makes, raising `GitHubOperationError` when GitHub cannot answer."""
    pr_proc = runner(pr_details_argv(owner, repo_name, pr_number), check=False, quiet=True)
    if pr_proc.returncode != 0 or not pr_proc.stdout.strip():
        err = _extract_proc_error(pr_proc)
        raise GitHubOperationError(f"Failed to query PR #{pr_number}: {err}")
    try:
        data = json.loads(pr_proc.stdout)
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(f"Failed to parse PR #{pr_number} data: {exc}") from exc


def fetch_raw_reviews(owner: str, repo_name: str, pr_number: int) -> RawReviewsList:
    """Read every page of a PR's reviews, or none and the reason they could not be read."""
    reviews = (
        f"/repos/{owner}/{repo_name}/pulls/{pr_number}/reviews?per_page={DEFAULT_GH_REST_PER_PAGE}"
    )
    try:
        return RawReviewsList(list(get_github_session().paginate(reviews)), error="")
    except GitHubOperationError as exc:
        return RawReviewsList([], error=str(exc)[:CONST_MAX_ERROR_DETAIL_LENGTH])


def _extract_latest_reviews_by_user(
    raw_reviews: list[dict[str, Any]],
) -> dict[str, tuple[str, str]]:
    """Map each reviewer to their latest review state and target commit ID."""
    latest_by_user: dict[str, tuple[str, str]] = {}
    for r in raw_reviews:
        if not isinstance(r, dict) or is_copilot_review(r):
            continue
        user = str(
            r.get("user", {}).get("login", "") or r.get("author", {}).get("login", "")
        ).strip()
        state = str(r.get("state", "")).upper()
        commit_id = str(r.get("commit_id") or r.get("commitId") or "")
        if user and state:
            latest_by_user[user] = (state, commit_id)
    return latest_by_user


def resolve_review_decision(
    raw_reviews: list[dict[str, Any]], head_sha: str | None = None
) -> str | None:
    """Derive aggregate review decision from latest state per reviewer targeting head_sha."""
    if not raw_reviews:
        return None
    latest_by_user = _extract_latest_reviews_by_user(raw_reviews)
    if not latest_by_user:
        return None

    if any(state == "CHANGES_REQUESTED" for state, _ in latest_by_user.values()):
        return "CHANGES_REQUESTED"

    has_approval = any(
        state == "APPROVED" and (not head_sha or commit_id == head_sha)
        for state, commit_id in latest_by_user.values()
    )
    return "APPROVED" if has_approval else "REVIEW_REQUIRED"


def _review_blockers(
    pr_number: int,
    copilot_status: CopilotReviewStatus,
    review_decision: str | None,
    require_reviews: bool,
) -> list[str]:
    """The monitor's review gate: what Copilot's review and the reviewers' verdicts block.

    `check-readiness` reads no review, so this gate is the monitor's own; the merge-readiness
    verdict judges everything else.
    """
    blockers: list[str] = []
    if copilot_status.state == "unread":
        blockers.append(
            f"PR #{pr_number} Copilot review state could not be read: "
            f"{copilot_status.unread_reason}"
        )
    elif copilot_status.state == "changes_requested":
        blockers.append(
            f"PR #{pr_number} Copilot review requested changes: {copilot_status.message}."
        )
    if review_decision == "CHANGES_REQUESTED":
        blockers.append(f"PR #{pr_number} has review changes requested.")
    elif require_reviews and review_decision != "APPROVED":
        blockers.append(
            f"PR #{pr_number} requires review approval before merging: current review decision "
            f"is '{review_decision or 'NONE'}'."
        )
    return blockers


def get_pr_monitoring_status(
    owner: str,
    repo: str,
    pr_number: int,
    require_reviews: bool = True,
    *,
    runner: GhRun = run_gh,
) -> PRMonitorStatus:
    """Read pull request `pr_number` once, judge it through the merge-readiness verdict, and add
    the review gate's blockers."""
    repo_name = repo.split("/")[-1]
    pr_data = fetch_pr_details(owner, repo_name, pr_number, runner=runner)
    head_sha = str(pr_data.get("head", {}).get("sha", ""))
    status = PRMonitorStatus(
        number=pr_number,
        title=str(pr_data.get("title", "")),
        head_sha=head_sha,
        is_draft=bool(pr_data.get("draft", False)),
        merged=pr_data.get("merged") is True,
        mergeable=pr_data.get("mergeable"),
        mergeable_state=str(pr_data.get("mergeable_state") or "unknown").lower(),
        require_reviews=require_reviews,
    )
    if status.merged:
        return status
    verdict = assess_merge_readiness(pr_data, owner, repo_name, pr_number, runner=runner)
    threads_read = BlockerKind.THREADS_UNREAD not in verdict.kinds
    raw_reviews = fetch_raw_reviews(owner, repo_name, pr_number)
    copilot_status = detect_copilot_status(
        owner,
        repo_name,
        pr_number,
        raw_reviews,
        unresolved_threads=list(verdict.threads_to_show) if threads_read else None,
        reviews_err=raw_reviews.error,
    )
    review_decision = resolve_review_decision(raw_reviews, head_sha=head_sha)
    status.copilot_status = copilot_status
    status.review_decision = review_decision
    status.has_changes_requested = (
        copilot_status.state == "changes_requested" or review_decision == "CHANGES_REQUESTED"
    )
    status.checks = list(verdict.checks.items) if verdict.checks else []
    status.pending_checks = list(verdict.pending_checks)
    status.unresolved_threads = list(verdict.threads_to_show)
    status.checks_failed = bool(verdict.kinds & CHECK_FAILURE_KINDS)
    status.blockers = [
        *verdict.blockers,
        *_review_blockers(pr_number, copilot_status, review_decision, require_reviews),
    ]
    return status


def _settled_result(status: PRMonitorStatus, pr_number: int) -> PRMonitorResult:
    """The result once no check runs: ready, or every blocker the poll found."""
    if status.merged:
        return PRMonitorResult(
            success=True, exit_code=0, message=f"PR #{pr_number} is merged.", status=status
        )
    if not status.blockers:
        return PRMonitorResult(
            success=True,
            exit_code=0,
            message=(
                f"PR #{pr_number} is 100% READY FOR MERGING: all checks passed, "
                "reviews complete, 0 unresolved threads."
            ),
            status=status,
        )
    return PRMonitorResult(
        success=False,
        exit_code=1 if status.checks_failed else 2,
        message=f"PR #{pr_number} has {len(status.blockers)} blocker(s): "
        + " ".join(status.blockers),
        status=status,
    )


def _build_monitor_timeout_result(
    latest_status: PRMonitorStatus, pr_number: int, elapsed: int
) -> PRMonitorResult:
    """The result when the timeout passes while a check runs or Copilot reviews."""
    pending = latest_status.pending_checks
    running = f": {', '.join(pending)}" if pending else ""
    if latest_status.copilot_status.is_active:
        copilot_msg = " (Copilot review still active)"
    else:
        copilot_msg = ""
    return PRMonitorResult(
        success=False,
        exit_code=3,
        message=(
            f"PR #{pr_number} monitoring timed out after {elapsed}s: "
            f"{len(pending)} check(s) pending{running}{copilot_msg}."
        ),
        status=latest_status,
    )


def monitor_pr(
    owner: str,
    repo: str,
    pr_number: int,
    *,
    timeout: int = 300,
    interval: int = 60,
    settle_timeout: int = 60,
    require_reviews: bool = True,
    status_callback: Callable[[PRMonitorStatus, int], None] | None = None,
) -> PRMonitorResult:
    """Poll a pull request until no check runs and no Copilot review is active, then report every
    blocker at once; return the timeout result if it passes first.

    While a check runs the monitor waits, whatever other blockers it sees, so a blocker that
    comes later is not left for a second run (#998). With `require_reviews`, it also waits out
    `settle_timeout`, so a Copilot review that starts late is seen.
    """
    valid_interval = max(1, interval)
    valid_timeout = max(1, timeout)
    valid_settle = max(0, settle_timeout)

    start_time = clock.monotonic()
    settle_deadline = start_time + valid_settle
    max_deadline = start_time + valid_timeout

    while True:
        now = clock.monotonic()
        elapsed = int(now - start_time)
        latest_status = get_pr_monitoring_status(
            owner, repo, pr_number, require_reviews=require_reviews
        )

        if status_callback:
            status_callback(latest_status, elapsed)

        if latest_status.merged or (
            latest_status.settled and (now >= settle_deadline or not require_reviews)
        ):
            return _settled_result(latest_status, pr_number)

        time_left = max_deadline - clock.monotonic()
        if time_left <= 0:
            return _build_monitor_timeout_result(latest_status, pr_number, elapsed)

        clock.sleep(min(float(valid_interval), time_left))


def sort_prs_oldest_first(prs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort pull requests in ascending order by PR number (FIFO / oldest first)."""
    return sorted(prs, key=lambda p: int(p.get("number") or 0))
