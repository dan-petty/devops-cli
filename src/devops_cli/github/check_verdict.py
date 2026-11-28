"""Fail-closed PR check verdict classification and aggregation."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Protocol

from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_GH_CHECK_BUCKET_CANCEL,
    CONST_GH_CHECK_BUCKET_FAIL,
    CONST_GH_CHECK_BUCKET_PASS,
    CONST_GH_CHECK_BUCKET_PENDING,
    CONST_GH_CHECK_BUCKET_SKIPPING,
    CONST_GH_CHECK_BUCKET_UNREAD,
    CONST_GH_CLI,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import get_github_session

logger = logging.getLogger(__name__)

# The start of the error that `gh pr checks` prints for a head with no check:
# "no checks reported on the '<branch>' branch" (cli/cli, pkg/cmd/pr/checks/checks.go).
_NO_CHECKS_REPORTED: Final[str] = "no checks reported"


class CheckBucket(StrEnum):
    """Canonical classification bucket for CI checks and commit statuses."""

    PASS = CONST_GH_CHECK_BUCKET_PASS
    FAIL = CONST_GH_CHECK_BUCKET_FAIL
    PENDING = CONST_GH_CHECK_BUCKET_PENDING
    SKIPPING = CONST_GH_CHECK_BUCKET_SKIPPING
    CANCEL = CONST_GH_CHECK_BUCKET_CANCEL
    UNREAD = CONST_GH_CHECK_BUCKET_UNREAD


BUCKET_CLASSIFIER_MAP: Final[dict[str, CheckBucket]] = {
    "pass": CheckBucket.PASS,
    "success": CheckBucket.PASS,
    "fail": CheckBucket.FAIL,
    "failure": CheckBucket.FAIL,
    "error": CheckBucket.FAIL,
    "timed_out": CheckBucket.FAIL,
    "action_required": CheckBucket.FAIL,
    "startup_failure": CheckBucket.FAIL,
    "stale": CheckBucket.FAIL,
    "pending": CheckBucket.PENDING,
    "in_progress": CheckBucket.PENDING,
    "queued": CheckBucket.PENDING,
    "waiting": CheckBucket.PENDING,
    "requested": CheckBucket.PENDING,
    "skipping": CheckBucket.SKIPPING,
    "skipped": CheckBucket.SKIPPING,
    "neutral": CheckBucket.SKIPPING,
    "cancel": CheckBucket.CANCEL,
    "cancelled": CheckBucket.CANCEL,
}
_BUCKET_NAME_MAP: Final[dict[str, CheckBucket]] = BUCKET_CLASSIFIER_MAP


class PRCheckItem(BaseModel):
    """Structured representation of a single PR check run or commit status."""

    name: str
    state: str = ""
    bucket: CheckBucket = CheckBucket.UNREAD
    workflow: str = ""
    link: str = ""


class CheckVerdictSummary(BaseModel):
    """Aggregated verdict summary of all check runs for a pull request."""

    items: list[PRCheckItem] = Field(default_factory=list)
    unread_reason: str = ""

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.items if c.bucket == CheckBucket.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.items if c.bucket == CheckBucket.FAIL)

    @property
    def pending_count(self) -> int:
        return sum(1 for c in self.items if c.bucket == CheckBucket.PENDING)

    @property
    def skipping_count(self) -> int:
        return sum(1 for c in self.items if c.bucket == CheckBucket.SKIPPING)

    @property
    def cancel_count(self) -> int:
        return sum(1 for c in self.items if c.bucket == CheckBucket.CANCEL)

    @property
    def unread_count(self) -> int:
        return sum(1 for c in self.items if c.bucket == CheckBucket.UNREAD)

    @property
    def exit_code(self) -> int:
        """Fail-closed exit code.

        0: all checks are pass or skipping (and read succeeded)
        8: one or more checks pending (matching GitHub CLI exit 8 convention)
        1: one or more checks failing, cancelled, or unread
        """
        if self.unread_count > 0 or bool(self.unread_reason):
            return 1
        if self.fail_count > 0 or self.cancel_count > 0:
            return 1
        if self.pending_count > 0:
            return 8
        return 0

    @property
    def is_passing(self) -> bool:
        return self.exit_code == 0

    @property
    def reports_nothing(self) -> bool:
        """Whether the commit reports no check run and no commit status: the one item is the
        pending stand-in for them (#3767)."""
        return not self.unread_reason and self.items == [no_checks_reported()]


def no_checks_reported() -> PRCheckItem:
    """The pending item that stands for a commit that reports no check run and no commit status,
    since a check can still start."""
    return PRCheckItem(name="no checks reported", bucket=CheckBucket.PENDING, state="pending")


def _normalize_token(val: Any) -> str:
    """Normalize string token for bucket lookup."""
    if val is None:
        return ""
    return str(val).strip().lower()


def _resolve_bucket(
    bucket_str: str,
    conclusion_str: str,
    status_str: str,
) -> tuple[CheckBucket, str]:
    """Resolve matched check bucket and fallback state name."""
    if bucket_str in BUCKET_CLASSIFIER_MAP:
        return BUCKET_CLASSIFIER_MAP[bucket_str], bucket_str
    if status_str in {"in_progress", "queued", "waiting", "requested", "pending"}:
        return CheckBucket.PENDING, status_str
    if conclusion_str in BUCKET_CLASSIFIER_MAP:
        return BUCKET_CLASSIFIER_MAP[conclusion_str], conclusion_str
    if status_str in BUCKET_CLASSIFIER_MAP:
        return BUCKET_CLASSIFIER_MAP[status_str], status_str
    return CheckBucket.UNREAD, "unknown"


def classify_check_item(
    name: str,
    bucket: str | None = None,
    state: str | None = None,
    conclusion: str | None = None,
    status: str | None = None,
    workflow: str = "",
    link: str = "",
) -> PRCheckItem:
    """Classify check run attributes into a typed PRCheckItem."""
    b_norm = _normalize_token(bucket)
    c_norm = _normalize_token(conclusion)
    raw_status = status if status is not None else state
    s_norm = _normalize_token(raw_status)
    matched_bucket, default_state = _resolve_bucket(b_norm, c_norm, s_norm)
    resolved_state = state if state else default_state
    resolved_name = name if name else "unknown"
    return PRCheckItem(
        name=resolved_name,
        state=resolved_state,
        bucket=matched_bucket,
        workflow=workflow,
        link=link,
    )


def _entry_to_check_item(entry: dict[str, Any]) -> PRCheckItem:
    """Convert a single parsed JSON entry into a PRCheckItem."""
    return classify_check_item(
        name=str(entry.get("name") or "unknown"),
        bucket=entry.get("bucket"),
        state=entry.get("state"),
        workflow=str(entry.get("workflow") or ""),
        link=str(entry.get("link") or ""),
    )


def _check_run_dict_to_item(cr: dict[str, Any]) -> PRCheckItem:
    """Convert a REST check-run dict into a PRCheckItem."""
    return classify_check_item(
        name=str(cr.get("name") or "unknown"),
        conclusion=cr.get("conclusion"),
        status=cr.get("status"),
        workflow=str(cr.get("app", {}).get("name") or ""),
        link=str(cr.get("html_url") or ""),
    )


def _parse_gh_checks_list(data: list[Any]) -> list[PRCheckItem]:
    """Parse list of check dicts from GitHub CLI JSON output."""
    return [_entry_to_check_item(e) for e in data if isinstance(e, dict)]


def _parse_gh_checks_json(raw_json: str) -> list[PRCheckItem] | None:
    """The check items of the list that `gh pr checks --json` prints, or None for output that is
    no list."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError, TypeError, ValueError:
        return None
    return _parse_gh_checks_list(data) if isinstance(data, list) else None


def _run_check(run: dict[str, Any]) -> tuple[str, object]:
    """The check that `run` is a run of: its name and the id of the app that reports it."""
    app = run.get("app")
    return str(run.get("name") or ""), app.get("id") if isinstance(app, dict) else None


def _run_time(run: dict[str, Any]) -> datetime | None:
    """When `run` started, else when it completed, else None."""
    stamp = run.get("started_at") or run.get("completed_at")
    return datetime.fromisoformat(stamp) if isinstance(stamp, str) else None


def latest_run_of_each_check(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the latest run of each check, whatever its conclusion (#5383).

    Each event of a pull request starts its workflows in a new check suite. The REST API lists
    the latest run of a check in each suite, and `filter=latest` does not collapse the runs of two
    suites. So a head commit can hold an old failed or cancelled run beside the newer run that
    replaced it. `gh pr checks` also shows only the newer run. A newer failure or cancel still
    fails the check. A check is a name and an app, and the time of a run is its `started_at`,
    else its `completed_at`. A run with no time stays, and each run at the latest time of its
    check stays, because nothing shows that a newer run replaced it.
    """
    latest: dict[tuple[str, object], datetime] = {}
    for run in runs:
        if (when := _run_time(run)) is not None:
            check = _run_check(run)
            latest[check] = max(latest.get(check, when), when)
    return [
        run for run in runs if (when := _run_time(run)) is None or when >= latest[_run_check(run)]
    ]


class PaginatingSession(Protocol):
    """A session that reads a REST listing page by page, such as `GitHubSession` (#3494)."""

    def paginate(self, path: str, *, iterable_key: str | None = None) -> Iterator[Any]: ...


def _fetch_check_runs_from_rest(
    owner: str, repo_name: str, head_sha: str, session: PaginatingSession | None
) -> tuple[list[PRCheckItem], str]:
    """Read every page of a commit's check runs through the GitHub session, the process's own
    unless `session` is given, returning (items, unread_reason). A page that can't be read, or
    holds no list of runs, leaves no items and the reason, never a shorter list."""
    check_runs = (
        f"/repos/{owner}/{repo_name}/commits/{head_sha}/check-runs?per_page="
        f"{DEFAULT_GH_REST_PER_PAGE}"
    )
    try:
        listing = session or get_github_session()
        runs = list(listing.paginate(check_runs, iterable_key="check_runs"))
    except GitHubOperationError as err:
        return [], f"GitHub check-runs API error: {str(err)[:CONST_MAX_ERROR_DETAIL_LENGTH]}"
    readable = [run for run in runs if isinstance(run, dict)]
    return [_check_run_dict_to_item(cr) for cr in latest_run_of_each_check(readable)], ""


def read_check_runs(
    owner: str,
    repo_name: str,
    head_sha: str,
    *,
    session: PaginatingSession | None = None,
) -> CheckVerdictSummary:
    """Read and classify the check runs of a commit, failing closed, with no commit status.

    The roadmap Service acts as a GitHub App whose token holds `checks: read` and no `statuses`
    permission, which the commit status endpoint needs (#2865). A commit with no check run reads
    as one pending check, as in `read_pr_checks`.
    """
    if not head_sha:
        return CheckVerdictSummary(unread_reason="PR head commit SHA is missing for checks query")
    check_items, check_err = _fetch_check_runs_from_rest(owner, repo_name, head_sha, session)
    if check_err:
        return CheckVerdictSummary(unread_reason=check_err)
    return CheckVerdictSummary(items=check_items or [no_checks_reported()])


def read_required_check_names(
    session: PaginatingSession, repository: str, branch: str
) -> frozenset[str]:
    """The names of the checks that the rules of `branch` of `repository` require.

    A page that cannot be read raises the `GitHubOperationError` of the session.
    """
    names: set[str] = set()
    for rule in session.paginate(
        f"/repos/{repository}/rules/branches/{branch}?per_page={DEFAULT_GH_REST_PER_PAGE}"
    ):
        if isinstance(rule, dict) and rule.get("type") == "required_status_checks":
            for check in rule.get("parameters", {}).get("required_status_checks", []):
                names.add(str(check["context"]))
    return frozenset(names)


def pr_checks_args(number: int | str, repo: str | None = None) -> list[str]:
    """The `gh pr checks` command that reads pull request `number`'s check runs as JSON."""
    cmd = [CONST_GH_CLI, "pr", "checks", str(number), "--json", "name,state,bucket,workflow,link"]
    return [*cmd, "--repo", repo] if repo else cmd


def read_pr_checks(
    number: int, repo: str | None = None, *, runner: Any = run_gh
) -> CheckVerdictSummary:
    """Read and classify the checks of pull request `number` with `gh pr checks`, failing closed.

    gh reads the check runs and the commit statuses of the head commit, keeps the newest run of
    each check and gives its bucket (#7508). With no `repo`, gh reads the pull request of the
    repository of the working directory. gh answers a head with no check with exit 1 and
    `no checks reported`, the exit code of a failed check, so that answer is told apart by its
    text; it reads as the pending stand-in, since a check can still start. Each other failed
    read, and output that is no list of checks, leaves no items and the reason.
    """
    res = runner(pr_checks_args(number, repo), check=False, quiet=True)
    error = (res.stderr or "").strip()
    if res.returncode != 0:
        if error.startswith(_NO_CHECKS_REPORTED):
            return CheckVerdictSummary(items=[no_checks_reported()])
        detail = error or f"exit code {res.returncode}"
        return CheckVerdictSummary(
            unread_reason=f"gh pr checks failed: {detail[:CONST_MAX_ERROR_DETAIL_LENGTH]}"
        )
    items = _parse_gh_checks_json(res.stdout)
    if items is None:
        return CheckVerdictSummary(unread_reason="gh pr checks printed no list of checks")
    return CheckVerdictSummary(items=items or [no_checks_reported()])
