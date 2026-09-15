"""Pull Request monitoring engine for CI checks, Copilot review sessions, and threads."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any, cast

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.pr_threads import ReviewThread, list_pr_review_threads

logger = logging.getLogger(__name__)

# Terminal conclusions for CheckRun and StatusContext
_PASSING_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}
_FAILING_CONCLUSIONS = {
    "FAILURE",
    "TIMED_OUT",
    "ACTION_REQUIRED",
    "CANCELLED",
    "STALE",
    "STARTUP_FAILURE",
}


class PRCheckRun(BaseModel):
    """Structured representation of a CI check run or status context."""

    name: str
    workflow: str = ""
    status: str = "COMPLETED"
    conclusion: str = "SUCCESS"
    url: str = ""

    @property
    def is_completed(self) -> bool:
        return self.status.upper() == "COMPLETED"

    @property
    def is_success(self) -> bool:
        return self.is_completed and self.conclusion.upper() in _PASSING_CONCLUSIONS

    @property
    def is_failure(self) -> bool:
        return self.is_completed and self.conclusion.upper() in _FAILING_CONCLUSIONS

    @property
    def is_pending(self) -> bool:
        return not self.is_completed


class CopilotReviewStatus(BaseModel):
    """Status of GitHub Copilot / automated code review session on a pull request."""

    is_active: bool = False
    state: str = "idle"  # idle | working | completed | changes_requested
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
    def is_ready_for_merge(self) -> bool:
        """Evaluate if PR is completely verified and ready for merge."""
        draft_ok = not self.is_draft
        checks_ok = self.all_checks_completed and self.all_checks_passed
        threads_ok = len(self.unresolved_threads) == 0
        review_approval_ok = (self.review_decision == "APPROVED") if self.require_reviews else True
        review_ok = (
            not self.copilot_status.is_active
            and self.copilot_status.state != "changes_requested"
            and not self.has_changes_requested
            and review_approval_ok
        )
        merge_ok = self.mergeable is True and (self.mergeable_state or "").lower() == "clean"
        return draft_ok and checks_ok and threads_ok and review_ok and merge_ok


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


def _try_resolve_pr_via_rest(repo_full: str | None, target_branch: str) -> int | None:
    """Attempt to resolve PR number using the REST API."""
    if not repo_full or "/" not in repo_full:
        return None
    repo_owner, repo_name = repo_full.split("/", 1)
    res = run_subprocess(
        [
            CONST_GH_CLI,
            "api",
            f"repos/{repo_owner}/{repo_name}/pulls?head={repo_owner}:{target_branch}&state=open",
            "--jq",
            ".[0].number",
        ]
    )
    if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != "null":
        try:
            return int(res.stdout.strip())
        except ValueError:
            return None
    return None


def _resolve_pr_via_gh_view(target_repo: str | None, target_branch: str) -> int:
    """Resolve PR number via gh pr view fallback."""
    cmd = [CONST_GH_CLI, "pr", "view", target_branch, "--json", "number", "--jq", ".number"]
    if target_repo:
        cmd.extend(["-R", target_repo])
    proc = run_subprocess(cmd)
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


def _parse_check_run_node(node: dict[str, Any]) -> PRCheckRun:
    """Parse a single CheckRun or StatusContext dictionary."""
    typename = node.get("__typename", "CheckRun")
    if typename == "StatusContext":
        state = str(node.get("state", "SUCCESS")).upper()
        status = "COMPLETED" if state in {"SUCCESS", "FAILURE", "ERROR"} else "IN_PROGRESS"
        conclusion = (
            "SUCCESS"
            if state == "SUCCESS"
            else ("FAILURE" if state in {"FAILURE", "ERROR"} else "")
        )
        return PRCheckRun(
            name=str(node.get("context", "StatusContext")),
            workflow="",
            status=status,
            conclusion=conclusion,
            url=str(node.get("targetUrl", "")),
        )

    status = str(node.get("status", "COMPLETED")).upper()
    conclusion = str(node.get("conclusion", "")).upper()
    return PRCheckRun(
        name=str(node.get("name", "Check")),
        workflow=str(node.get("workflowName", "")),
        status=status,
        conclusion=conclusion,
        url=str(node.get("detailsUrl", "")),
    )


def _parse_check_runs(raw_checks: list[dict[str, Any]]) -> list[PRCheckRun]:
    """Parse statusCheckRollup nodes into PRCheckRun instances."""
    return [_parse_check_run_node(item) for item in raw_checks if isinstance(item, dict)]


def _parse_timeline_copilot_state(timeline_stdout: str) -> tuple[bool, str]:
    """Parse timeline events to determine if Copilot is actively working."""
    copilot_working = False
    active_event = ""
    for line in timeline_stdout.strip().splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        try:
            evt = json.loads(line_str)
        except json.JSONDecodeError:
            continue

        evt_name = evt.get("event")
        if evt_name == "copilot_work_started":
            copilot_working = True
            active_event = "copilot_work_started"
        elif evt_name == "reviewed":
            evt_author = str(evt.get("author", "")).lower()
            if not evt_author or "copilot" in evt_author:
                copilot_working = False
                active_event = "reviewed"
    return copilot_working, active_event


def _is_copilot_review_dict(r: Any) -> bool:
    """Predicate determining whether a review record originates from Copilot."""
    if not isinstance(r, dict):
        return False
    author = str(r.get("author", {}).get("login", "")).lower()
    user = str(r.get("user", {}).get("login", "")).lower()
    return "copilot" in author or "copilot" in user


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
    copilot_reviews = [r for r in reviews if _is_copilot_review_dict(r)]
    copilot_reviews.sort(key=lambda r: str(r.get("submittedAt") or r.get("submitted_at") or ""))
    latest_review = copilot_reviews[-1] if copilot_reviews else None
    has_changes, latest_state, last_time = _check_review_changes_requested(latest_review)
    return latest_review, has_changes, latest_state, last_time


def _query_timeline_copilot_state(owner: str, repo_name: str, pr_number: int) -> tuple[bool, str]:
    """Query issue timeline to detect active Copilot review events."""
    cmd = [
        CONST_GH_CLI,
        "api",
        "--paginate",
        f"repos/{owner}/{repo_name}/issues/{pr_number}/timeline",
        "--jq",
        '.[] | select(.event | test("copilot|reviewed")) | {event: .event, created_at: .created_at, submitted_at: .submitted_at, author: (.actor.login // .user.login // "")}',
    ]
    proc = run_subprocess(cmd)
    if proc.returncode == 0 and proc.stdout.strip():
        return _parse_timeline_copilot_state(proc.stdout)
    return False, ""


def _detect_copilot_status(
    owner: str,
    repo_name: str,
    pr_number: int,
    reviews: list[dict[str, Any]],
) -> CopilotReviewStatus:
    """Inspect timeline events and review states to detect Copilot review activity."""
    latest_review, has_changes, latest_state, last_time = _extract_latest_copilot_review(reviews)
    copilot_working, active_event = _query_timeline_copilot_state(owner, repo_name, pr_number)

    if copilot_working:
        return CopilotReviewStatus(
            is_active=True,
            state="working",
            message="Copilot review is currently in progress",
            last_review_at=last_time,
            active_event=active_event,
        )
    if has_changes:
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


def _fetch_commit_check_runs(owner: str, repo: str, head_sha: str) -> list[PRCheckRun]:
    """Fetch GitHub Check Runs for commit SHA."""
    check_cmd = [
        CONST_GH_CLI,
        "api",
        "--paginate",
        f"repos/{owner}/{repo}/commits/{head_sha}/check-runs",
    ]
    check_proc = run_subprocess(check_cmd)
    if check_proc.returncode != 0 or not check_proc.stdout.strip():
        return []
    try:
        check_data = json.loads(check_proc.stdout)
        runs = (
            check_data.get("check_runs", [])
            if isinstance(check_data, dict)
            else (check_data if isinstance(check_data, list) else [])
        )
        return [
            PRCheckRun(
                name=str(c.get("name", "Check")),
                workflow=str(c.get("app", {}).get("name", "")),
                status=str(c.get("status", "completed")).upper(),
                conclusion=str(c.get("conclusion") or "").upper(),
                url=str(c.get("html_url", "")),
            )
            for c in runs
            if isinstance(c, dict)
        ]
    except json.JSONDecodeError:
        return []


def _fetch_commit_status_contexts(owner: str, repo: str, head_sha: str) -> list[PRCheckRun]:
    """Fetch GitHub Commit Status Contexts for commit SHA."""
    status_cmd = [
        CONST_GH_CLI,
        "api",
        f"repos/{owner}/{repo}/commits/{head_sha}/status",
    ]
    status_proc = run_subprocess(status_cmd)
    if status_proc.returncode != 0 or not status_proc.stdout.strip():
        return []
    try:
        status_data = json.loads(status_proc.stdout)
        results: list[PRCheckRun] = []
        for s in status_data.get("statuses", []):
            if isinstance(s, dict):
                st = str(s.get("state", "")).lower()
                status = "COMPLETED" if st in {"success", "failure", "error"} else "IN_PROGRESS"
                conclusion = (
                    "SUCCESS"
                    if st == "success"
                    else ("FAILURE" if st in {"failure", "error"} else "")
                )
                results.append(
                    PRCheckRun(
                        name=str(s.get("context", "Status")),
                        workflow="Commit Status",
                        status=status,
                        conclusion=conclusion,
                        url=str(s.get("target_url") or ""),
                    )
                )
        return results
    except json.JSONDecodeError:
        return []


def _fetch_rest_check_runs(owner: str, repo: str, head_sha: str) -> list[PRCheckRun]:
    """Fetch check runs and commit status contexts via GitHub REST API."""
    return _fetch_commit_check_runs(owner, repo, head_sha) + _fetch_commit_status_contexts(
        owner, repo, head_sha
    )


def _fetch_pr_details(owner: str, repo_name: str, pr_number: int) -> dict[str, Any]:
    """Query GitHub REST API for pull request core attributes."""
    pr_cmd = [CONST_GH_CLI, "api", f"repos/{owner}/{repo_name}/pulls/{pr_number}"]
    pr_proc = run_subprocess(pr_cmd)
    if pr_proc.returncode != 0 or not pr_proc.stdout.strip():
        err = pr_proc.stderr.strip()[:256] if pr_proc.stderr else f"Exit code {pr_proc.returncode}"
        raise GitHubOperationError(f"Failed to query PR #{pr_number}: {err}")
    try:
        data = json.loads(pr_proc.stdout)
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(f"Failed to parse PR #{pr_number} data: {exc}") from exc


def _fetch_raw_reviews(owner: str, repo_name: str, pr_number: int) -> list[dict[str, Any]]:
    """Fetch all review records for a PR."""
    from devops_cli.github.client import parse_paginated_json

    reviews_cmd = [
        CONST_GH_CLI,
        "api",
        "--paginate",
        f"repos/{owner}/{repo_name}/pulls/{pr_number}/reviews",
    ]
    reviews_proc = run_subprocess(reviews_cmd)
    if reviews_proc.returncode == 0 and reviews_proc.stdout.strip():
        return parse_paginated_json(reviews_proc.stdout)
    return []


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
    failing = [c for c in checks if c.is_failure]
    if failing:
        reasons.append(f"{len(failing)} CI check(s) failed")
    if unresolved_threads:
        reasons.append(f"{len(unresolved_threads)} unresolved review thread(s)")
    if copilot_status.state == "changes_requested":
        reasons.append(f"Copilot review: {copilot_status.message}")
    elif has_changes_requested:
        reasons.append("Reviewers requested changes on the pull request")
    elif require_reviews and review_decision != "APPROVED":
        reasons.append("Pull request requires approved review before merging")

    merge_reason = _resolve_merge_failure_reason(mergeable, mergeable_state, is_draft)
    if merge_reason:
        reasons.append(merge_reason)
    return reasons


def _resolve_review_decision(
    raw_reviews: list[dict[str, Any]], head_sha: str | None = None
) -> str | None:
    """Derive aggregate review decision from latest state per reviewer targeting head_sha."""
    if not raw_reviews:
        return None
    latest_by_user: dict[str, tuple[str, str]] = {}
    for r in raw_reviews:
        if not isinstance(r, dict):
            continue
        user = str(
            r.get("user", {}).get("login", "") or r.get("author", {}).get("login", "")
        ).strip()
        state = str(r.get("state", "")).upper()
        commit_id = str(r.get("commit_id") or r.get("commitId") or "")
        if user and state:
            latest_by_user[user] = (state, commit_id)

    # Any active changes requested blocks approval
    for state, _ in latest_by_user.values():
        if state == "CHANGES_REQUESTED":
            return "CHANGES_REQUESTED"

    # Require at least one APPROVED review targeting current head_sha (if provided)
    has_approval = any(
        state == "APPROVED" and (not head_sha or commit_id == head_sha)
        for state, commit_id in latest_by_user.values()
    )
    if has_approval:
        return "APPROVED"
    return "REVIEW_REQUIRED"


def _has_active_changes_requested(raw_reviews: list[dict[str, Any]]) -> bool:
    """Return True if any reviewer's latest review state is CHANGES_REQUESTED."""
    return _resolve_review_decision(raw_reviews) == "CHANGES_REQUESTED"


def get_pr_monitoring_status(
    owner: str, repo: str, pr_number: int, require_reviews: bool = True
) -> PRMonitorStatus:
    """Fetch current CI checks, Copilot review status, and unresolved review threads."""
    repo_name = repo.split("/")[-1]
    pr_data = _fetch_pr_details(owner, repo_name, pr_number)
    head_sha = str(pr_data.get("head", {}).get("sha", ""))
    is_draft = bool(pr_data.get("draft", False))
    mergeable = pr_data.get("mergeable")
    mergeable_state = str(pr_data.get("mergeable_state") or "unknown").lower()

    checks = _fetch_rest_check_runs(owner, repo_name, head_sha)
    raw_reviews = _fetch_raw_reviews(owner, repo_name, pr_number)
    copilot_status = _detect_copilot_status(owner, repo_name, pr_number, raw_reviews)
    unresolved_threads = _fetch_unresolved_threads(owner, repo_name, pr_number)

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
        return PRMonitorResult(
            success=False,
            exit_code=1,
            message=f"PR #{pr_number} CI checks failed: {len(latest_status.failing_checks)} failure(s).",
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
                f"PR #{pr_number} is still a draft: convert to ready for review via "
                f"'gh pr ready {pr_number}' before merging."
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
    copilot_msg = " (Copilot review still active)" if latest_status.copilot_status.is_active else ""
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
        and latest_status.copilot_status.state != "changes_requested"
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
