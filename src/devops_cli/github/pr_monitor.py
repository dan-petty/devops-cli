"""Pull Request monitoring engine for CI checks, Copilot review sessions, and threads."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.pr_threads import ReviewComment, ReviewThread, list_pr_review_threads

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
    checks: list[PRCheckRun] = Field(default_factory=list)
    copilot_status: CopilotReviewStatus = Field(default_factory=CopilotReviewStatus)
    unresolved_threads: list[ReviewThread] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)

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
        review_ok = (
            not self.copilot_status.is_active and self.copilot_status.state != "changes_requested"
        )
        return draft_ok and checks_ok and threads_ok and review_ok


class PRMonitorResult(BaseModel):
    """Final outcome of monitoring a pull request."""

    success: bool
    exit_code: int  # 0: ready, 1: checks failed, 2: unresolved threads, 3: timeout
    message: str
    status: PRMonitorStatus


def resolve_branch_pr_number(
    branch_name: str | None = None,
    owner: str | None = None,
    repo: str | None = None,
) -> int:
    """Resolve pull request number associated with current or specified branch."""
    target_branch = branch_name
    if not target_branch:
        proc_br = run_subprocess(["git", "branch", "--show-current"])
        target_branch = proc_br.stdout.strip() if proc_br.returncode == 0 else ""

    if not target_branch:
        raise GitHubOperationError("Unable to determine current git branch.")

    # 1. Try REST API endpoint (immune to GraphQL rate limiting)
    from devops_cli.core.repo import get_repo_origin_name

    target_repo = f"{owner}/{repo}" if owner and repo else get_repo_origin_name()
    if target_repo and "/" in target_repo:
        repo_owner, repo_name = target_repo.split("/", 1)
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
                pass

    # 2. Fallback to gh pr view
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


def _detect_copilot_status(
    owner: str,
    repo_name: str,
    pr_number: int,
    reviews: list[dict[str, Any]],
) -> CopilotReviewStatus:
    """Inspect timeline events and review states to detect Copilot review activity."""
    copilot_reviews = [
        r
        for r in reviews
        if isinstance(r, dict)
        and (
            "copilot" in str(r.get("author", {}).get("login", "")).lower()
            or "copilot" in str(r.get("user", {}).get("login", "")).lower()
        )
    ]
    copilot_reviews.sort(key=lambda r: str(r.get("submittedAt") or r.get("submitted_at") or ""))
    latest_review = copilot_reviews[-1] if copilot_reviews else None
    latest_state = str(latest_review.get("state", "")).upper() if latest_review else ""
    has_changes_requested = latest_state == "CHANGES_REQUESTED"
    last_review_time = (
        str(latest_review.get("submittedAt") or latest_review.get("submitted_at") or "")
        if latest_review
        else ""
    )

    cmd = [
        CONST_GH_CLI,
        "api",
        "--paginate",
        f"repos/{owner}/{repo_name}/issues/{pr_number}/timeline",
        "--jq",
        '.[] | select(.event | test("copilot|reviewed")) | {event: .event, created_at: .created_at, submitted_at: .submitted_at, author: (.actor.login // .user.login // "")}',
    ]
    proc = run_subprocess(cmd)
    copilot_working, active_event = (
        _parse_timeline_copilot_state(proc.stdout)
        if proc.returncode == 0 and proc.stdout.strip()
        else (False, "")
    )

    if copilot_working:
        return CopilotReviewStatus(
            is_active=True,
            state="working",
            message="Copilot review is currently in progress",
            last_review_at=last_review_time,
            active_event=active_event,
        )

    if has_changes_requested:
        return CopilotReviewStatus(
            is_active=False,
            state="changes_requested",
            message="Copilot requested changes on the pull request",
            last_review_at=last_review_time,
            active_event=active_event,
        )

    if copilot_reviews:
        return CopilotReviewStatus(
            is_active=False,
            state="completed",
            message="Copilot review session completed",
            last_review_at=last_review_time,
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
    check_cmd = [
        CONST_GH_CLI,
        "api",
        "--paginate",
        f"repos/{owner}/{repo}/commits/{head_sha}/check-runs",
    ]
    check_proc = run_subprocess(check_cmd)
    checks: list[PRCheckRun] = []
    if check_proc.returncode == 0 and check_proc.stdout.strip():
        try:
            check_data = json.loads(check_proc.stdout)
            runs = (
                check_data.get("check_runs", [])
                if isinstance(check_data, dict)
                else (check_data if isinstance(check_data, list) else [])
            )
            for c in runs:
                if isinstance(c, dict):
                    status = str(c.get("status", "completed")).upper()
                    conclusion = str(c.get("conclusion") or "").upper()
                    workflow = str(c.get("app", {}).get("name", ""))
                    checks.append(
                        PRCheckRun(
                            name=str(c.get("name", "Check")),
                            workflow=workflow,
                            status=status,
                            conclusion=conclusion,
                            url=str(c.get("html_url", "")),
                        )
                    )
        except json.JSONDecodeError:
            pass

    status_cmd = [
        CONST_GH_CLI,
        "api",
        f"repos/{owner}/{repo}/commits/{head_sha}/status",
    ]
    status_proc = run_subprocess(status_cmd)
    if status_proc.returncode == 0 and status_proc.stdout.strip():
        try:
            status_data = json.loads(status_proc.stdout)
            for s in status_data.get("statuses", []):
                if isinstance(s, dict):
                    st = str(s.get("state", "")).lower()
                    status = "COMPLETED" if st in {"success", "failure", "error"} else "IN_PROGRESS"
                    conclusion = (
                        "SUCCESS"
                        if st == "success"
                        else ("FAILURE" if st in {"failure", "error"} else "")
                    )
                    checks.append(
                        PRCheckRun(
                            name=str(s.get("context", "Status")),
                            workflow="Commit Status",
                            status=status,
                            conclusion=conclusion,
                            url=str(s.get("target_url") or ""),
                        )
                    )
        except json.JSONDecodeError:
            pass

    return checks


def _fetch_rest_unresolved_comments(owner: str, repo: str, pr_number: int) -> list[ReviewThread]:
    """Fetch review comments via REST API when GraphQL is rate limited.

    Fails closed by treating all root review comments as unresolved threads since REST
    does not expose thread resolution status.
    """
    comments_cmd = [
        CONST_GH_CLI,
        "api",
        "--paginate",
        f"repos/{owner}/{repo}/pulls/{pr_number}/comments",
    ]
    comments_proc = run_subprocess(comments_cmd)
    if comments_proc.returncode != 0:
        err = (
            comments_proc.stderr.strip()[:256]
            if comments_proc.stderr
            else f"Exit code {comments_proc.returncode}"
        )
        raise GitHubOperationError(f"Failed to fetch review comments for PR #{pr_number}: {err}")

    if not comments_proc.stdout.strip():
        return []

    threads: list[ReviewThread] = []
    try:
        c_list = json.loads(comments_proc.stdout)
        if not isinstance(c_list, list):
            return []
        for c in c_list:
            if isinstance(c, dict) and c.get("in_reply_to_id") is None:
                cid = c.get("id")
                author = c.get("user", {}).get("login", "")
                threads.append(
                    ReviewThread(
                        id=str(c.get("node_id", cid)),
                        is_resolved=False,
                        path=str(c.get("path", "")),
                        line=c.get("line"),
                        comments=[
                            ReviewComment(id=str(cid), body=c.get("body", ""), author=author)
                        ],
                    )
                )
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(
            f"Malformed review comment response for PR #{pr_number}: {exc}"
        ) from exc
    return threads


def get_pr_monitoring_status(owner: str, repo: str, pr_number: int) -> PRMonitorStatus:
    """Fetch current CI checks, Copilot review status, and unresolved review threads."""
    repo_name = repo.split("/")[-1]

    # 1. Fetch PR details via REST API (immune to GraphQL rate limit)
    pr_cmd = [CONST_GH_CLI, "api", f"repos/{owner}/{repo_name}/pulls/{pr_number}"]
    pr_proc = run_subprocess(pr_cmd)
    if pr_proc.returncode != 0 or not pr_proc.stdout.strip():
        err = pr_proc.stderr.strip()[:256] if pr_proc.stderr else f"Exit code {pr_proc.returncode}"
        raise GitHubOperationError(f"Failed to query PR #{pr_number}: {err}")

    try:
        pr_data = json.loads(pr_proc.stdout)
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(f"Failed to parse PR #{pr_number} data: {exc}") from exc

    title = str(pr_data.get("title", ""))
    head_sha = str(pr_data.get("head", {}).get("sha", ""))
    is_draft = bool(pr_data.get("draft", False))

    # 2. Fetch Check Runs via REST API
    checks = _fetch_rest_check_runs(owner, repo_name, head_sha)

    # 3. Fetch Reviews via REST API
    reviews_cmd = [
        CONST_GH_CLI,
        "api",
        "--paginate",
        f"repos/{owner}/{repo_name}/pulls/{pr_number}/reviews",
    ]
    reviews_proc = run_subprocess(reviews_cmd)
    raw_reviews: list[dict[str, Any]] = []
    if reviews_proc.returncode == 0 and reviews_proc.stdout.strip():
        try:
            raw_reviews = json.loads(reviews_proc.stdout)
        except json.JSONDecodeError:
            raw_reviews = []

    copilot_status = _detect_copilot_status(owner, repo_name, pr_number, raw_reviews)

    # 4. Fetch Unresolved Review Threads (GraphQL with REST fallback)
    unresolved_threads: list[ReviewThread] = []
    try:
        unresolved_threads = list_pr_review_threads(
            owner, repo_name, pr_number, unresolved_only=True
        )
    except GitHubOperationError as exc:
        if "rate limit" in str(exc).lower():
            unresolved_threads = _fetch_rest_unresolved_comments(owner, repo_name, pr_number)
        else:
            raise

    failure_reasons: list[str] = []
    failing = [c for c in checks if c.is_failure]
    if failing:
        failure_reasons.append(f"{len(failing)} CI check(s) failed")
    if unresolved_threads:
        failure_reasons.append(f"{len(unresolved_threads)} unresolved review thread(s)")
    if copilot_status.state == "changes_requested":
        failure_reasons.append("Copilot review requested changes")

    return PRMonitorStatus(
        number=pr_number,
        title=title,
        head_sha=head_sha,
        is_draft=is_draft,
        checks=checks,
        copilot_status=copilot_status,
        unresolved_threads=unresolved_threads,
        failure_reasons=failure_reasons,
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
    """Monitor PR checks, Copilot review sessions, and threads until ready or failure."""
    valid_interval = max(1, interval)
    valid_timeout = max(1, timeout)
    valid_settle = max(0, settle_timeout)

    start_time = time.monotonic()
    settle_deadline = start_time + valid_settle
    max_deadline = start_time + valid_timeout
    latest_status: PRMonitorStatus | None = None

    while True:
        now = time.monotonic()
        elapsed = int(now - start_time)
        latest_status = get_pr_monitoring_status(owner, repo, pr_number)

        if status_callback:
            status_callback(latest_status, elapsed)

        # 1. Early failure: if checks have already failed, stop immediately
        if latest_status.failing_checks:
            return PRMonitorResult(
                success=False,
                exit_code=1,
                message=f"PR #{pr_number} CI checks failed: {len(latest_status.failing_checks)} failure(s).",
                status=latest_status,
            )

        # 2. Terminal review state: if Copilot requested changes, stop immediately
        if (
            latest_status.copilot_status.state == "changes_requested"
            and not latest_status.copilot_status.is_active
        ):
            return PRMonitorResult(
                success=False,
                exit_code=2,
                message=f"PR #{pr_number} Copilot review requested changes.",
                status=latest_status,
            )

        # 3. Check if all checks completed successfully
        checks_completed = latest_status.all_checks_completed and latest_status.all_checks_passed
        copilot_done = (
            not latest_status.copilot_status.is_active
            and latest_status.copilot_status.state != "changes_requested"
        )
        settled = now >= settle_deadline

        if checks_completed and copilot_done and (settled or not require_reviews):
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

            return PRMonitorResult(
                success=True,
                exit_code=0,
                message=(
                    f"PR #{pr_number} is 100% READY FOR MERGING: all checks passed, "
                    "reviews complete, 0 unresolved threads."
                ),
                status=latest_status,
            )

        # 4. Timeout check and bounded sleep
        time_left = max_deadline - time.monotonic()
        if time_left <= 0:
            pending_checks = len(latest_status.pending_checks)
            copilot_msg = (
                " (Copilot review still active)" if latest_status.copilot_status.is_active else ""
            )
            return PRMonitorResult(
                success=False,
                exit_code=3,
                message=(
                    f"PR #{pr_number} monitoring timed out after {elapsed}s: "
                    f"{pending_checks} check(s) pending{copilot_msg}."
                ),
                status=latest_status,
            )

        time.sleep(min(float(valid_interval), time_left))
