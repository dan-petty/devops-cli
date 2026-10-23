"""Pull Request monitoring engine for CI checks, Copilot review sessions, and threads."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Iterable
from typing import Any, NamedTuple, cast

from pydantic import BaseModel, Field, model_validator

from devops_cli.config.constants import (
    CONST_COPILOT_REVIEWER_LOGINS,
    CONST_GH_CLI,
    CONST_GITHUB_REVIEW_AUTHOR_KEYS,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.check_verdict import CheckBucket, classify_check_item
from devops_cli.github.pr_threads import ReviewThread, list_pr_review_threads
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import get_github_session

logger = logging.getLogger(__name__)


class PRCheckRun(BaseModel):
    """Structured representation of a CI check run or status context."""

    name: str
    workflow: str = ""
    status: str = "COMPLETED"
    conclusion: str = "SUCCESS"
    url: str = ""
    bucket: CheckBucket = CheckBucket.PASS

    @model_validator(mode="before")
    @classmethod
    def _resolve_bucket_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("bucket"):
                raw_status = data.get("status")
                raw_conclusion = data.get("conclusion")
                st = raw_status if raw_status is not None else "COMPLETED"
                conc = (
                    raw_conclusion
                    if raw_conclusion is not None
                    else ("SUCCESS" if raw_status is None else "")
                )
                item = classify_check_item(
                    name=str(data.get("name") or "Check"),
                    status=st,
                    conclusion=conc,
                )
                data["bucket"] = item.bucket
        return data

    @property
    def is_completed(self) -> bool:
        return self.bucket != CheckBucket.PENDING

    @property
    def is_success(self) -> bool:
        return self.bucket in {CheckBucket.PASS, CheckBucket.SKIPPING}

    @property
    def is_failure(self) -> bool:
        return self.bucket in {CheckBucket.FAIL, CheckBucket.CANCEL, CheckBucket.UNREAD}

    @property
    def is_pending(self) -> bool:
        return self.bucket == CheckBucket.PENDING


class CopilotReviewStatus(BaseModel):
    """Status of GitHub Copilot / automated code review session on a pull request."""

    is_active: bool = False
    state: str = "idle"  # idle | working | completed | changes_requested | unread
    unread_reason: str = ""
    message: str = ""
    last_review_at: str = ""
    active_event: str = ""


class PRMonitorStatus(BaseModel):
    """Comprehensive snapshot of a PR's CI checks, reviews, and discussion threads."""

    number: int
    title: str = ""
    head_sha: str = ""
    is_draft: bool = False
    mergeable: bool | None = None
    mergeable_state: str = "unknown"
    review_decision: str | None = None
    has_changes_requested: bool = False
    checks: list[PRCheckRun] = Field(default_factory=list)
    copilot_status: CopilotReviewStatus = Field(default_factory=CopilotReviewStatus)
    unresolved_threads: list[ReviewThread] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    require_reviews: bool = True

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    @property
    def completed_checks(self) -> int:
        return sum(1 for c in self.checks if c.is_completed)

    @property
    def successful_checks(self) -> int:
        return sum(1 for c in self.checks if c.is_success)

    @property
    def failing_checks(self) -> list[PRCheckRun]:
        return [c for c in self.checks if c.is_failure]

    @property
    def pending_checks(self) -> list[PRCheckRun]:
        return [c for c in self.checks if c.is_pending]

    @property
    def all_checks_completed(self) -> bool:
        return len(self.checks) > 0 and all(c.is_completed for c in self.checks)

    @property
    def all_checks_passed(self) -> bool:
        return len(self.checks) > 0 and all(c.is_success for c in self.checks)

    @property
    def is_review_ready(self) -> bool:
        """Evaluate if reviews and thread resolutions satisfy readiness."""
        threads_ok = len(self.unresolved_threads) == 0
        approval_ok = (self.review_decision == "APPROVED") if self.require_reviews else True
        copilot_ok = (
            not self.copilot_status.is_active
            and self.copilot_status.state not in {"changes_requested", "unread"}
            and not self.has_changes_requested
        )
        return threads_ok and approval_ok and copilot_ok

    @property
    def is_ready_for_merge(self) -> bool:
        """Evaluate if PR is completely verified and ready for merge."""
        draft_ok = not self.is_draft
        checks_ok = self.all_checks_completed and self.all_checks_passed
        merge_ok = self.mergeable is True and (self.mergeable_state or "").lower() == "clean"
        return draft_ok and checks_ok and self.is_review_ready and merge_ok


class PRMonitorResult(BaseModel):
    """Final outcome of monitoring a pull request."""

    success: bool
    exit_code: int  # 0: ready, 1: checks failed, 2: unresolved threads, 3: timeout
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


def resolve_branch_pr_number(
    branch_name: str | None = None,
    owner: str | None = None,
    repo: str | None = None,
) -> int:
    """Resolve pull request number associated with current or specified branch."""
    target_branch = _resolve_current_git_branch(branch_name)
    from devops_cli.core.repo import get_repo_origin_name

    target_repo = f"{owner}/{repo}" if owner and repo else get_repo_origin_name()
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


class _CopilotTimeline(NamedTuple):
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
    evt: dict[str, Any], state: _CopilotTimeline, copilot_review_ids: frozenset[int]
) -> _CopilotTimeline:
    """What the timeline says of Copilot once `evt` is read: its start event runs a pass, and its
    review's `reviewed` event ends it."""
    evt_name = str(evt.get("event") or "")
    if evt_name == "copilot_work_started":
        return _CopilotTimeline(working=True, event=evt_name)
    if evt_name == "reviewed" and _ends_copilot_pass(evt, copilot_review_ids):
        return _CopilotTimeline(event=evt_name)
    return state


def _timeline_copilot_state(
    events: Iterable[Any], copilot_review_ids: frozenset[int]
) -> _CopilotTimeline:
    """What a timeline's events, in order, say of Copilot, its own reviews named by
    `copilot_review_ids`."""
    state = _CopilotTimeline()
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


def _is_copilot_changes_recommended(body: str) -> bool:
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
    has_changes = state == "CHANGES_REQUESTED" or _is_copilot_changes_recommended(body)
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


def _query_timeline_copilot_state(
    owner: str, repo_name: str, pr_number: int, copilot_review_ids: frozenset[int]
) -> _CopilotTimeline:
    """Read every page of the pull request's issue timeline for Copilot's review events, its own
    reviews named by `copilot_review_ids`, or why the timeline could not be read."""
    timeline = f"/repos/{owner}/{repo_name}/issues/{pr_number}/timeline?per_page={DEFAULT_GH_REST_PER_PAGE}"
    try:
        return _timeline_copilot_state(get_github_session().paginate(timeline), copilot_review_ids)
    except GitHubOperationError as exc:
        return _CopilotTimeline(error=str(exc)[:CONST_MAX_ERROR_DETAIL_LENGTH])


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


def _detect_copilot_status(
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
    timeline = _query_timeline_copilot_state(
        owner, repo_name, pr_number, _copilot_review_ids(reviews)
    )
    err = reviews_err or getattr(reviews, "error", "") or timeline.error
    return _copilot_review_status(reviews, timeline, unresolved_threads, err)


def _copilot_review_status(
    reviews: list[dict[str, Any]],
    timeline: _CopilotTimeline,
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


def _fetch_rest_check_runs(owner: str, repo: str, head_sha: str) -> list[PRCheckRun]:
    """Fetch check runs and commit status contexts via GitHub REST API."""
    from devops_cli.github.check_verdict import _fetch_checks_from_rest

    verdict = _fetch_checks_from_rest(owner, repo, head_sha, runner=run_gh)
    if verdict.unread_reason:
        return [
            PRCheckRun(
                name="PR check verification failed closed",
                status="COMPLETED",
                conclusion=verdict.unread_reason,
                bucket=CheckBucket.UNREAD,
            )
        ]
    return [
        PRCheckRun(
            name=item.name,
            workflow=item.workflow,
            status="COMPLETED" if item.bucket != CheckBucket.PENDING else "IN_PROGRESS",
            conclusion=item.state.upper() if item.bucket != CheckBucket.PENDING else "",
            url=item.link,
            bucket=item.bucket,
        )
        for item in verdict.items
    ]


class RawReviewsList(list[dict[str, Any]]):
    """List of review dictionaries carrying optional read error reason."""

    error: str = ""

    def __init__(self, items: Any = (), error: str = "") -> None:
        super().__init__(items)
        self.error = error


def fetch_pr_details(owner: str, repo_name: str, pr_number: int) -> dict[str, Any]:
    """Query GitHub REST API for pull request core attributes."""
    pr_proc = run_gh(pr_details_argv(owner, repo_name, pr_number), check=False, quiet=True)
    if pr_proc.returncode != 0 or not pr_proc.stdout.strip():
        err = _extract_proc_error(pr_proc)
        raise GitHubOperationError(f"Failed to query PR #{pr_number}: {err}")
    try:
        data = json.loads(pr_proc.stdout)
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(f"Failed to parse PR #{pr_number} data: {exc}") from exc


def _fetch_raw_reviews(owner: str, repo_name: str, pr_number: int) -> RawReviewsList:
    """Read every page of a PR's reviews, or none and the reason they could not be read."""
    reviews = (
        f"/repos/{owner}/{repo_name}/pulls/{pr_number}/reviews?per_page={DEFAULT_GH_REST_PER_PAGE}"
    )
    try:
        return RawReviewsList(list(get_github_session().paginate(reviews)), error="")
    except GitHubOperationError as exc:
        return RawReviewsList([], error=str(exc)[:CONST_MAX_ERROR_DETAIL_LENGTH])


def _fetch_unresolved_threads(owner: str, repo_name: str, pr_number: int) -> list[ReviewThread]:
    """Fetch unresolved review threads via GitHub GraphQL API, honoring rate limits."""
    return list_pr_review_threads(owner, repo_name, pr_number, unresolved_only=True)


def _resolve_merge_failure_reason(
    mergeable: bool | None,
    mergeable_state: str,
    is_draft: bool,
) -> str | None:
    """Evaluate mergeability state and draft status into an actionable failure reason."""
    if is_draft:
        return "Pull request is currently a draft"
    if mergeable is False or mergeable_state == "dirty":
        return "Merge conflicts with base branch"
    if mergeable_state == "blocked":
        return "Blocked by branch protection or awaiting required review approval"
    if mergeable_state == "behind":
        return "Branch is behind target base branch"
    if mergeable is not True:
        return "Pull request mergeability is not yet determined by GitHub"
    if mergeable_state != "clean":
        return f"Mergeable state is '{mergeable_state}' (requires clean)"
    return None


def _build_failure_reasons(
    checks: list[PRCheckRun],
    unresolved_threads: list[ReviewThread],
    copilot_status: CopilotReviewStatus,
    has_changes_requested: bool,
    mergeable: bool | None,
    mergeable_state: str,
    is_draft: bool,
    require_reviews: bool = True,
    review_decision: str | None = None,
) -> list[str]:
    """Compile structured list of failure reasons preventing merge."""
    reasons: list[str] = []
    unread = [c for c in checks if c.bucket == CheckBucket.UNREAD]
    failing = [c for c in checks if c.is_failure]
    if unread:
        reasons.append(f"PR check verification failed closed: {unread[0].conclusion}")
    elif failing:
        reasons.append(f"{len(failing)} CI check(s) failed")
    if unresolved_threads:
        reasons.append(f"{len(unresolved_threads)} unresolved review thread(s)")
    if copilot_status.state == "unread":
        reasons.append(f"Copilot review state could not be read: {copilot_status.unread_reason}")
    elif copilot_status.state == "changes_requested":
        reasons.append(f"Copilot review: {copilot_status.message}")
    elif has_changes_requested:
        reasons.append("Reviewers requested changes on the pull request")
    elif require_reviews and review_decision != "APPROVED":
        reasons.append("Pull request requires approved review before merging")

    merge_reason = _resolve_merge_failure_reason(mergeable, mergeable_state, is_draft)
    if merge_reason:
        reasons.append(merge_reason)
    return reasons


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


def _resolve_review_decision(
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


def _has_active_changes_requested(raw_reviews: list[dict[str, Any]]) -> bool:
    """Return True if any reviewer's latest review state is CHANGES_REQUESTED."""
    return _resolve_review_decision(raw_reviews) == "CHANGES_REQUESTED"


def get_pr_monitoring_status(
    owner: str, repo: str, pr_number: int, require_reviews: bool = True
) -> PRMonitorStatus:
    """Fetch current CI checks, Copilot review status, and unresolved review threads."""
    repo_name = repo.split("/")[-1]
    pr_data = fetch_pr_details(owner, repo_name, pr_number)
    head_sha = str(pr_data.get("head", {}).get("sha", ""))
    is_draft = bool(pr_data.get("draft", False))
    mergeable = pr_data.get("mergeable")
    mergeable_state = str(pr_data.get("mergeable_state") or "unknown").lower()

    checks = _fetch_rest_check_runs(owner, repo_name, head_sha)
    raw_reviews = _fetch_raw_reviews(owner, repo_name, pr_number)
    unresolved_threads = _fetch_unresolved_threads(owner, repo_name, pr_number)
    reviews_err = getattr(raw_reviews, "error", "")
    copilot_status = _detect_copilot_status(
        owner,
        repo_name,
        pr_number,
        raw_reviews,
        unresolved_threads=unresolved_threads,
        reviews_err=reviews_err,
    )

    review_decision = _resolve_review_decision(raw_reviews, head_sha=head_sha)
    has_changes_requested = (
        copilot_status.state == "changes_requested" or review_decision == "CHANGES_REQUESTED"
    )
    failure_reasons = _build_failure_reasons(
        checks,
        unresolved_threads,
        copilot_status,
        has_changes_requested,
        mergeable,
        mergeable_state,
        is_draft,
        require_reviews=require_reviews,
        review_decision=review_decision,
    )
    return PRMonitorStatus(
        number=pr_number,
        title=str(pr_data.get("title", "")),
        head_sha=head_sha,
        is_draft=is_draft,
        mergeable=mergeable,
        mergeable_state=mergeable_state,
        review_decision=review_decision,
        has_changes_requested=has_changes_requested,
        checks=checks,
        copilot_status=copilot_status,
        unresolved_threads=unresolved_threads,
        failure_reasons=failure_reasons,
        require_reviews=require_reviews,
    )


def _check_early_pr_failures(
    latest_status: PRMonitorStatus, pr_number: int
) -> PRMonitorResult | None:
    """Check for immediate failure conditions such as failing CI or requested changes."""
    if latest_status.failing_checks:
        unread = [c for c in latest_status.failing_checks if c.bucket == CheckBucket.UNREAD]
        if unread:
            msg = f"PR #{pr_number} check verification failed closed: {unread[0].conclusion}"
        else:
            msg = (
                f"PR #{pr_number} CI checks failed: {len(latest_status.failing_checks)} failure(s)."
            )
        return PRMonitorResult(
            success=False,
            exit_code=1,
            message=msg,
            status=latest_status,
        )
    if (
        latest_status.copilot_status.state == "changes_requested"
        and not latest_status.copilot_status.is_active
    ):
        return PRMonitorResult(
            success=False,
            exit_code=2,
            message=f"PR #{pr_number} Copilot review requested changes: {latest_status.copilot_status.message}",
            status=latest_status,
        )
    if latest_status.has_changes_requested:
        return PRMonitorResult(
            success=False,
            exit_code=2,
            message=f"PR #{pr_number} has review changes requested.",
            status=latest_status,
        )
    if latest_status.mergeable is False or latest_status.mergeable_state == "dirty":
        return PRMonitorResult(
            success=False,
            exit_code=2,
            message=f"PR #{pr_number} has merge conflicts with the base branch.",
            status=latest_status,
        )
    return None


def _evaluate_pr_settled_readiness(
    latest_status: PRMonitorStatus, pr_number: int, require_reviews: bool
) -> PRMonitorResult | None:
    """Evaluate settled readiness, verifying draft, threads, and mergeable state."""
    if latest_status.is_draft:
        return PRMonitorResult(
            success=False,
            exit_code=2,
            message=(
                f"PR #{pr_number} is still a draft and its checks pass. Mark it ready with "
                f"'devops pr ready {pr_number}'."
            ),
            status=latest_status,
        )
    if latest_status.unresolved_threads:
        return PRMonitorResult(
            success=False,
            exit_code=2,
            message=(
                f"PR #{pr_number} has {len(latest_status.unresolved_threads)} unresolved "
                "review discussion thread(s)."
            ),
            status=latest_status,
        )
    if latest_status.mergeable_state == "blocked":
        return PRMonitorResult(
            success=False,
            exit_code=2,
            message=(
                f"PR #{pr_number} is blocked from merging by GitHub: "
                "awaiting required review approval or branch protection requirements."
            ),
            status=latest_status,
        )
    if require_reviews and latest_status.review_decision != "APPROVED":
        return PRMonitorResult(
            success=False,
            exit_code=2,
            message=(
                f"PR #{pr_number} requires review approval before merging: "
                f"current review decision is '{latest_status.review_decision or 'NONE'}'."
            ),
            status=latest_status,
        )
    if latest_status.mergeable_state == "behind":
        return PRMonitorResult(
            success=False,
            exit_code=2,
            message=f"PR #{pr_number} branch is behind base branch: update branch before merging.",
            status=latest_status,
        )
    if latest_status.is_ready_for_merge:
        return PRMonitorResult(
            success=True,
            exit_code=0,
            message=(
                f"PR #{pr_number} is 100% READY FOR MERGING: all checks passed, "
                "reviews complete, 0 unresolved threads."
            ),
            status=latest_status,
        )
    return None


def _build_monitor_timeout_result(
    latest_status: PRMonitorStatus, pr_number: int, elapsed: int
) -> PRMonitorResult:
    """Build timeout result with pending check and review diagnostics."""
    pending_checks = len(latest_status.pending_checks)
    if latest_status.copilot_status.is_active:
        copilot_msg = " (Copilot review still active)"
    elif latest_status.copilot_status.state == "unread":
        reason = latest_status.copilot_status.unread_reason or "unknown"
        copilot_msg = f" (Copilot review state could not be read: {reason})"
    else:
        copilot_msg = ""
    return PRMonitorResult(
        success=False,
        exit_code=3,
        message=(
            f"PR #{pr_number} monitoring timed out after {elapsed}s: "
            f"{pending_checks} check(s) pending{copilot_msg}."
        ),
        status=latest_status,
    )


def _check_pr_ready_step(
    latest_status: PRMonitorStatus,
    pr_number: int,
    now: float,
    settle_deadline: float,
    require_reviews: bool,
) -> PRMonitorResult | None:
    """Check whether PR meets settled criteria and return settled result if so."""
    checks_completed = latest_status.all_checks_completed and latest_status.all_checks_passed
    copilot_done = (
        not latest_status.copilot_status.is_active
        and latest_status.copilot_status.state not in {"changes_requested", "unread"}
    )
    settled = now >= settle_deadline
    if checks_completed and copilot_done and (settled or not require_reviews):
        return _evaluate_pr_settled_readiness(latest_status, pr_number, require_reviews)
    return None


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
    """Monitor PR checks, Copilot review sessions, and threads until ready or failure."""
    valid_interval = max(1, interval)
    valid_timeout = max(1, timeout)
    valid_settle = max(0, settle_timeout)

    start_time = time.monotonic()
    settle_deadline = start_time + valid_settle
    max_deadline = start_time + valid_timeout

    while True:
        now = time.monotonic()
        elapsed = int(now - start_time)
        latest_status = get_pr_monitoring_status(
            owner, repo, pr_number, require_reviews=require_reviews
        )
        latest_status.require_reviews = require_reviews

        if status_callback:
            status_callback(latest_status, elapsed)

        early_failure = _check_early_pr_failures(latest_status, pr_number)
        if early_failure:
            return early_failure

        settled_res = _check_pr_ready_step(
            latest_status, pr_number, now, settle_deadline, require_reviews
        )
        if settled_res:
            return settled_res

        time_left = max_deadline - time.monotonic()
        if time_left <= 0:
            return _build_monitor_timeout_result(latest_status, pr_number, elapsed)

        time.sleep(min(float(valid_interval), time_left))


def sort_prs_oldest_first(prs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort pull requests in ascending order by PR number (FIFO / oldest first)."""
    return sorted(prs, key=lambda p: int(p.get("number") or 0))
