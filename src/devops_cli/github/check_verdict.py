"""Fail-closed PR check verdict classification and aggregation."""

from __future__ import annotations

import json
import logging
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_GH_CHECK_BUCKET_CANCEL,
    CONST_GH_CHECK_BUCKET_FAIL,
    CONST_GH_CHECK_BUCKET_PASS,
    CONST_GH_CHECK_BUCKET_PENDING,
    CONST_GH_CHECK_BUCKET_SKIPPING,
    CONST_GH_CHECK_BUCKET_UNREAD,
    CONST_GH_CLI,
)
from devops_cli.github.rate_limiter import run_gh

logger = logging.getLogger(__name__)


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


def _parse_gh_checks_dict(data: dict[str, Any]) -> list[PRCheckItem]:
    """Parse dictionary wrapper containing check_runs from JSON output."""
    check_runs = data.get("check_runs")
    if isinstance(check_runs, list):
        return [_check_run_dict_to_item(cr) for cr in check_runs if isinstance(cr, dict)]
    return []


def _parse_gh_checks_json(raw_json: str) -> list[PRCheckItem] | None:
    """Parse JSON output from 'gh pr checks --json' into check items."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError, TypeError, ValueError:
        return None
    if isinstance(data, list):
        return _parse_gh_checks_list(data)
    if isinstance(data, dict):
        return _parse_gh_checks_dict(data)
    return None


def _extract_page_check_runs(page: Any) -> list[dict[str, Any]]:
    """Extract check run dicts from a single REST response page."""
    if isinstance(page, dict):
        check_runs = page.get("check_runs")
        if isinstance(check_runs, list):
            return [c for c in check_runs if isinstance(c, dict)]
        if "name" in page:
            return [page]
    return []


def _parse_rest_check_runs_payload(raw_json: str) -> list[PRCheckItem]:
    """Parse check-runs response from REST API into PRCheckItem objects."""
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError, ValueError) as err:
        raise ValueError(f"Invalid JSON from check-runs API: {err}") from err

    if isinstance(data, list):
        raw_runs = [r for page in data for r in _extract_page_check_runs(page)]
    elif isinstance(data, dict):
        raw_runs = _extract_page_check_runs(data)
    else:
        raise ValueError("GitHub check-runs API returned unexpected payload structure")

    return [_check_run_dict_to_item(cr) for cr in raw_runs]


def _fetch_checks_from_rest(
    owner: str,
    repo_name: str,
    head_sha: str,
    runner: Any = run_gh,
) -> CheckVerdictSummary:
    """Fetch and parse check runs from GitHub REST API with pagination."""
    if not head_sha:
        return CheckVerdictSummary(
            unread_reason="PR head commit SHA is missing for check-runs query"
        )
    res = runner(
        [
            CONST_GH_CLI,
            "api",
            "--paginate",
            "--slurp",
            f"repos/{owner}/{repo_name}/commits/{head_sha}/check-runs?per_page=100",
        ],
        check=False,
        quiet=True,
    )
    if res.returncode != 0:
        err_msg = res.stderr.strip() or f"exit code {res.returncode}"
        return CheckVerdictSummary(unread_reason=f"GitHub check-runs API error: {err_msg}")
    if not res.stdout.strip():
        return CheckVerdictSummary(unread_reason="GitHub check-runs API returned empty response")

    try:
        items = _parse_rest_check_runs_payload(res.stdout)
    except ValueError as err:
        return CheckVerdictSummary(unread_reason=str(err))

    return CheckVerdictSummary(items=items)


def _resolve_target_owner_repo(repo: str | None) -> tuple[str, str] | None:
    """Resolve owner and repo_name from repo string or git origin."""
    from devops_cli.core.repo import get_repo_origin_name

    target = repo or get_repo_origin_name()
    if not target or "/" not in target:
        return None
    owner, repo_name = target.split("/", 1)
    return owner, repo_name


def _resolve_head_sha(number: int, repo: str | None, runner: Any = run_gh) -> str:
    """Resolve head commit SHA for a PR number."""
    cmd = [CONST_GH_CLI, "pr", "view", str(number), "--json", "head"]
    if repo:
        cmd.extend(["--repo", repo])
    res = runner(cmd, check=False, quiet=True)
    if res.returncode != 0 or not res.stdout.strip():
        return ""
    try:
        data = json.loads(res.stdout)
        head = data.get("head", {})
        return str(head.get("sha", "") if isinstance(head, dict) else "")
    except json.JSONDecodeError, TypeError, ValueError:
        return ""


def pr_checks_args(number: int | str, repo: str | None = None) -> list[str]:
    """The `gh pr checks` command that reads pull request `number`'s check runs as JSON."""
    cmd = [CONST_GH_CLI, "pr", "checks", str(number), "--json", "name,state,bucket,workflow,link"]
    return [*cmd, "--repo", repo] if repo else cmd


def fetch_pr_check_verdicts(
    number: int,
    repo: str | None = None,
    head_sha: str | None = None,
    runner: Any = None,
) -> CheckVerdictSummary:
    """Fetch PR check runs and return structured fail-closed verdict summary.

    First attempts to read checks via 'gh pr checks --json name,state,bucket,workflow,link'.
    If that fails, returns invalid JSON, or fails closed, falls back to REST check-runs API.
    """
    gh_runner = runner if runner is not None else run_gh
    cmd = pr_checks_args(number, repo)

    res = gh_runner(cmd, check=False, quiet=True)
    if res.returncode == 0 and res.stdout.strip():
        parsed = _parse_gh_checks_json(res.stdout)
        if parsed is not None:
            return CheckVerdictSummary(items=parsed)

    owner_repo = _resolve_target_owner_repo(repo)
    if not owner_repo:
        err_msg = res.stderr.strip() or f"exit code {res.returncode}"
        return CheckVerdictSummary(
            unread_reason=f"Failed to read checks and cannot resolve target repo: {err_msg}"
        )

    owner, repo_name = owner_repo
    sha = head_sha or _resolve_head_sha(number, repo, runner=gh_runner)
    if not sha:
        err_msg = res.stderr.strip() or f"exit code {res.returncode}"
        return CheckVerdictSummary(
            unread_reason=f"Failed to read checks and cannot resolve head commit SHA: {err_msg}"
        )

    return _fetch_checks_from_rest(owner, repo_name, sha, runner=gh_runner)
