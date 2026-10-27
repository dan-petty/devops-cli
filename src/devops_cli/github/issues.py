"""GitHub Issues management, taxonomy enforcement, and triage auditing."""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Collection, Iterable
from typing import Any
from urllib.parse import urlencode

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.exceptions.git import (
    GitHubFileNotFoundError,
    GitHubOperationError,
    GitHubUnreadError,
)
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.store import RoadmapStore

logger = logging.getLogger(__name__)


class GitHubIssue(BaseModel):
    """Normalized GitHub Issue representation with taxonomy tags and milestone."""

    number: int
    title: str
    body: str = ""
    state: str = "open"
    milestone: str | None = None
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    url: str = ""


class IssueTriageAudit(BaseModel):
    """Audit evaluation of open issues against repository taxonomy standards."""

    total_open: int = 0
    valid_count: int = 0
    issues_missing_type: list[int] = Field(default_factory=list)
    issues_missing_scope: list[int] = Field(default_factory=list)
    issues_missing_priority: list[int] = Field(default_factory=list)
    issues_awaiting_intake: list[int] = Field(default_factory=list)

    @property
    def compliance_rate(self) -> float:
        """Percentage of open issues complying with all taxonomy standards."""
        if self.total_open == 0:
            return 100.0
        return round((self.valid_count / self.total_open) * 100, 1)


def _parse_issue_labels(raw_labels: Any) -> list[str]:
    """Extract string label names from raw GitHub API label structures."""
    if not isinstance(raw_labels, list):
        return []
    names: list[str] = []
    for item in raw_labels:
        if isinstance(item, dict) and "name" in item:
            names.append(str(item["name"]))
        elif isinstance(item, str):
            names.append(item)
    return names


def _parse_issue_assignees(raw_assignees: Any) -> list[str]:
    """Extract assignee logins from raw GitHub API structures."""
    if not isinstance(raw_assignees, list):
        return []
    logins: list[str] = []
    for item in raw_assignees:
        if isinstance(item, dict) and "login" in item:
            logins.append(str(item["login"]))
        elif isinstance(item, str):
            logins.append(item)
    return logins


def _parse_single_issue(item: dict[str, Any]) -> GitHubIssue:
    """Transform raw GitHub issue dictionary into a typed GitHubIssue model."""
    raw_m = item.get("milestone")
    milestone_title: str | None = None
    if isinstance(raw_m, dict):
        milestone_title = raw_m.get("title")
    elif isinstance(raw_m, str):
        milestone_title = raw_m

    return GitHubIssue(
        number=int(item.get("number", 0)),
        title=str(item.get("title", "")),
        body=str(item.get("body", "") or ""),
        state=str(item.get("state", "open")).lower(),
        milestone=milestone_title,
        labels=_parse_issue_labels(item.get("labels")),
        assignees=_parse_issue_assignees(item.get("assignees")),
        created_at=str(item.get("createdAt") or item.get("created_at") or ""),
        updated_at=str(item.get("updatedAt") or item.get("updated_at") or ""),
        # REST sends the API address in `url` and the web address in `html_url`; gh sends the
        # web address in `url`.
        url=str(item.get("html_url") or item.get("url") or ""),
    )


# gh issue list pages through results up to --limit, so "every issue" is a limit above any
# repository's issue count rather than a separate code path.
_EVERY_ISSUE = 100_000


def _filter_rest_issues(
    raw_list: Iterable[Any], milestone: str | None, limit: int | None
) -> list[GitHubIssue]:
    """Filter raw REST issue dictionaries into typed GitHubIssue objects, reading no more of
    `raw_list` once `limit` issues are kept."""
    issues: list[GitHubIssue] = []
    for item in raw_list:
        if not isinstance(item, dict) or "pull_request" in item or "number" not in item:
            continue
        parsed = _parse_single_issue(item)
        if milestone and parsed.milestone != milestone:
            continue
        issues.append(parsed)
        if limit is not None and len(issues) >= limit:
            break
    return issues


def _fetch_issues_rest(
    repo: str,
    state: str = "open",
    milestone: str | None = None,
    labels: list[str] | None = None,
    limit: int | None = 30,
) -> list[GitHubIssue]:
    """Read issues page by page through the GitHub session when gh issue list fails, until
    `limit` are kept.

    Raises when this read fails too, or a page holds no list of issues, so a failure never looks
    like a repository with no issues.
    """
    query = {"state": state, "per_page": DEFAULT_GH_REST_PER_PAGE}
    if labels:
        query["labels"] = ",".join(labels)
    listing = get_github_session().paginate(f"/repos/{repo}/issues?{urlencode(query)}")
    return _filter_rest_issues(listing, milestone, limit)


def get_repository_issues(
    repo: str,
    state: str = "open",
    milestone: str | None = None,
    label: str | None = None,
    labels: list[str] | None = None,
    limit: int | None = 30,
) -> list[GitHubIssue]:
    """Retrieve issues via gh issue list with a REST fallback; ``limit=None`` reads every issue."""
    cmd = [
        CONST_GH_CLI,
        "issue",
        "list",
        "--repo",
        repo,
        "--state",
        state,
        "--limit",
        str(_EVERY_ISSUE if limit is None else limit),
        "--json",
        "number,title,state,milestone,labels,assignees,createdAt,updatedAt,url",
    ]
    if milestone:
        cmd.extend(["--milestone", milestone])
    all_labels = list(labels or [])
    if label and label not in all_labels:
        all_labels.append(label)
    for lbl in all_labels:
        cmd.extend(["--label", lbl])

    res = run_gh(cmd, check=False, quiet=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            raw_list = json.loads(res.stdout)
            if isinstance(raw_list, list):
                return [_parse_single_issue(item) for item in raw_list if isinstance(item, dict)]
        except Exception as exc:
            logger.debug("Failed to parse issues: %s", exc)

    return _fetch_issues_rest(
        repo,
        state=state,
        milestone=milestone,
        labels=all_labels,
        limit=limit,
    )


def get_repository_issue(repo: str, number: int) -> GitHubIssue:
    """Read issue `number` of `repo` with one request through the GitHub session.

    A 404 raises `GitHubNotFoundError`, and an answer that is no issue raises
    `GitHubUnreadError`, so a failed read never looks like an empty issue. The REST issues
    endpoint also answers for a pull request: that raises `GitHubOperationError` naming
    `devops pr view`.
    """
    item = get_github_session().rest("GET", f"/repos/{repo}/issues/{number}")
    if not isinstance(item, dict) or "number" not in item:
        raise GitHubUnreadError(
            f"GitHub gave no issue for #{number} of {repo}",
            operation="issue_view",
            details={"repo": repo, "number": number},
        )
    if "pull_request" in item:
        raise GitHubOperationError(
            f"#{number} of {repo} is a pull request; read it with `devops pr view {number}`",
            operation="issue_view",
            details={"repo": repo, "number": number},
        )
    return _parse_single_issue(item)


_EMPTY_FIELD = "—"


def render_issue(issue: GitHubIssue) -> str:
    """The text of one whole issue: a header of fields, an empty line and the full body.

    A field that is empty shows a dash. Nothing is cut, and the text holds no markup of its own.
    """
    header = [
        f"#{issue.number} {issue.title}",
        f"State: {issue.state}",
        f"URL: {issue.url or _EMPTY_FIELD}",
        f"Milestone: {issue.milestone or _EMPTY_FIELD}",
        f"Labels: {', '.join(issue.labels) or _EMPTY_FIELD}",
        f"Assignees: {', '.join(issue.assignees) or _EMPTY_FIELD}",
        f"Created: {issue.created_at or _EMPTY_FIELD}",
        f"Updated: {issue.updated_at or _EMPTY_FIELD}",
    ]
    return "\n".join([*header, "", issue.body.strip() or _EMPTY_FIELD])


def _build_create_issue_cmd(
    repo: str,
    title: str,
    body: str = "",
    milestone: str | None = None,
    labels: list[str] | None = None,
) -> list[str]:
    """Construct command argument list for gh issue create."""
    cmd = [CONST_GH_CLI, "issue", "create", "--repo", repo, "--title", title, "--body", body]
    if milestone:
        cmd.extend(["--milestone", milestone])
    if labels:
        for lbl in labels:
            cmd.extend(["--label", lbl])
    return cmd


def _extract_issue_number(url_or_text: str) -> int:
    """Extract issue integer number from a GitHub issue URL or string."""
    if "/issues/" not in url_or_text:
        return 0
    try:
        return int(url_or_text.rstrip("/").split("/")[-1])
    except ValueError:
        return 0


def _parse_created_issue(
    stdout: str,
    title: str,
    body: str = "",
    milestone: str | None = None,
    labels: list[str] | None = None,
) -> GitHubIssue:
    """Parse output from issue creation command into a typed GitHubIssue."""
    cleaned = stdout.strip()
    if cleaned.startswith("{"):
        try:
            data = json.loads(cleaned)
            if data and "number" in data:
                return _parse_single_issue(data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.debug("Failed to parse JSON issue payload: %s", exc)
    return GitHubIssue(
        number=_extract_issue_number(cleaned),
        title=title,
        body=body,
        state="open",
        milestone=milestone,
        labels=labels or [],
        url=cleaned,
    )


def create_repository_issue(
    repo: str,
    title: str,
    body: str = "",
    milestone: str | None = None,
    labels: list[str] | None = None,
) -> GitHubIssue:
    """Create a new GitHub issue with taxonomy labels and milestone linkage."""
    cmd = _build_create_issue_cmd(repo, title, body, milestone, labels)
    res = run_gh(cmd, check=False, quiet=True)
    assigned_milestone = milestone
    if (
        res.returncode != 0
        and milestone
        and "could not add to milestone" in (res.stderr or res.stdout)
    ):
        fallback_cmd = _build_create_issue_cmd(repo, title, body, None, labels)
        res = run_gh(fallback_cmd, check=False, quiet=True)
        if res.returncode == 0:
            m_num = _resolve_milestone_number(repo, milestone)
            created_num = _extract_issue_number(res.stdout)
            if m_num and created_num:
                patch_cmd = [
                    CONST_GH_CLI,
                    "api",
                    "-X",
                    "PATCH",
                    f"repos/{repo}/issues/{created_num}",
                    "-F",
                    f"milestone={m_num}",
                ]
                run_gh(patch_cmd, check=False, quiet=True)
            else:
                assigned_milestone = None
    if res.returncode != 0:
        raise GitHubOperationError(
            f"Failed to create GitHub issue: {res.stderr or res.stdout}",
            operation="create_issue",
            details={"repo": repo, "title": title[:256]},
        )
    return _parse_created_issue(res.stdout, title, body, assigned_milestone, labels)


def _resolve_store(repo: str, store: RoadmapStore | None) -> RoadmapStore | None:
    """Return the given RoadmapStore or attempt to open it from repository configuration."""
    if store is not None:
        return store
    try:
        from devops_cli.roadmap.config import open_roadmap

        _, opened = open_roadmap(repo, ref=None)
        return opened
    except GitHubFileNotFoundError:
        return None


def _audit_board_store(
    store: RoadmapStore, awaiting_intake: Collection[int] | None
) -> IssueTriageAudit:
    """Evaluate open board items and candidates against repository taxonomy rules."""
    board_items = store.items()
    open_board_items = [it for it in board_items if str(it.state).lower() == "open"]
    candidates = store.candidates()
    audit = IssueTriageAudit(total_open=len(open_board_items) + len(candidates))
    awaiting_set = (
        set(awaiting_intake) if awaiting_intake is not None else {c.number for c in candidates}
    )

    for candidate in candidates:
        audit.issues_awaiting_intake.append(candidate.number)

    for item in open_board_items:
        if item.number in awaiting_set:
            audit.issues_awaiting_intake.append(item.number)
            continue
        has_type = any(lbl.startswith("type/") for lbl in item.labels)
        has_scope = any(lbl.startswith("scope/") for lbl in item.labels)
        has_priority = bool(item.priority and item.priority.strip())

        is_valid = True
        if not has_type:
            audit.issues_missing_type.append(item.number)
            is_valid = False
        if not has_scope:
            audit.issues_missing_scope.append(item.number)
            is_valid = False
        if not has_priority:
            audit.issues_missing_priority.append(item.number)
            is_valid = False

        if is_valid:
            audit.valid_count += 1

    audit.issues_missing_type.sort()
    audit.issues_missing_scope.sort()
    audit.issues_missing_priority.sort()
    audit.issues_awaiting_intake.sort()
    return audit


def _audit_rest_issues(
    open_issues: list[GitHubIssue], awaiting_intake: Collection[int] | None
) -> IssueTriageAudit:
    """Evaluate REST queried open issues when no roadmap board is present."""
    audit = IssueTriageAudit(total_open=len(open_issues))
    awaiting_set = set(awaiting_intake or ())

    for issue in open_issues:
        if issue.number in awaiting_set:
            audit.issues_awaiting_intake.append(issue.number)
            continue
        has_type = any(lbl.startswith("type/") for lbl in issue.labels)
        has_scope = any(lbl.startswith("scope/") for lbl in issue.labels)
        has_priority = False

        is_valid = True
        if not has_type:
            audit.issues_missing_type.append(issue.number)
            is_valid = False
        if not has_scope:
            audit.issues_missing_scope.append(issue.number)
            is_valid = False
        if not has_priority:
            audit.issues_missing_priority.append(issue.number)
            is_valid = False

        if is_valid:
            audit.valid_count += 1

    audit.issues_missing_type.sort()
    audit.issues_missing_scope.sort()
    audit.issues_missing_priority.sort()
    audit.issues_awaiting_intake.sort()
    return audit


def audit_issues_triage(
    repo: str,
    *,
    awaiting_intake: Collection[int] | None = None,
    store: RoadmapStore | None = None,
) -> IssueTriageAudit:
    """Audit open issues against mandatory taxonomy labeling rules and board Priority.

    An issue in `awaiting_intake`, open and not on the roadmap board, is reported once, as
    awaiting intake: `devops roadmap intake` gives it its type and Priority (#742). A backlog
    item has no milestone, so a missing milestone is no finding.
    """
    resolved_store = _resolve_store(repo, store)
    if resolved_store is not None:
        return _audit_board_store(resolved_store, awaiting_intake)
    open_issues = get_repository_issues(repo, state="open", limit=None)
    return _audit_rest_issues(open_issues, awaiting_intake)


def _summarize_board_store(store: RoadmapStore) -> dict[str, Any]:
    """Aggregate open issues from board items and candidates by priority, type, and milestone."""
    board_items = store.items()
    open_board_items = [it for it in board_items if str(it.state).lower() == "open"]
    candidates = store.candidates()
    total_open = len(open_board_items) + len(candidates)
    priority_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    milestone_counter: Counter[str] = Counter()

    for item in open_board_items:
        if item.priority:
            priority_counter[item.priority] += 1
        for lbl in item.labels:
            if lbl.startswith("type/"):
                type_counter[lbl] += 1
        if item.milestone:
            milestone_counter[item.milestone] += 1
        else:
            milestone_counter["no-milestone"] += 1

    for candidate in candidates:
        for lbl in candidate.labels:
            if lbl.startswith("type/"):
                type_counter[lbl] += 1
        if candidate.milestone:
            milestone_counter[candidate.milestone] += 1
        else:
            milestone_counter["no-milestone"] += 1

    return {
        "total_open": total_open,
        "by_priority": dict(priority_counter),
        "by_type": dict(type_counter),
        "by_milestone": dict(milestone_counter),
    }


def _summarize_rest_issues(open_issues: list[GitHubIssue]) -> dict[str, Any]:
    """Aggregate REST queried open issues by priority, type, and milestone."""
    priority_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    milestone_counter: Counter[str] = Counter()

    for issue in open_issues:
        for lbl in issue.labels:
            if lbl.startswith("type/"):
                type_counter[lbl] += 1
        if issue.milestone:
            milestone_counter[issue.milestone] += 1
        else:
            milestone_counter["no-milestone"] += 1

    return {
        "total_open": len(open_issues),
        "by_priority": dict(priority_counter),
        "by_type": dict(type_counter),
        "by_milestone": dict(milestone_counter),
    }


def get_issues_summary(repo: str, *, store: RoadmapStore | None = None) -> dict[str, Any]:
    """Calculate aggregate issue counts by priority, type, and milestone."""
    resolved_store = _resolve_store(repo, store)
    if resolved_store is not None:
        return _summarize_board_store(resolved_store)
    open_issues = get_repository_issues(repo, state="open", limit=None)
    return _summarize_rest_issues(open_issues)


def _is_trivial_milestone(milestone: str | int | None) -> bool:
    """Check if milestone parameter is empty or explicitly clearing."""
    if milestone is None:
        return True
    if isinstance(milestone, int):
        return False
    cleaned = str(milestone).strip().lower()
    return not cleaned or cleaned in ("none", "null", "clear", "0")


def _find_milestone_match(items: Iterable[Any], title: str) -> int | None:
    """The number of the milestone with the exact title `title`, reading no further once found.

    A title is any text, so no title is read as a version.
    """
    return next(
        (
            int(m["number"])
            for m in items
            if isinstance(m, dict) and m.get("title") == title and "number" in m
        ),
        None,
    )


def _resolve_milestone_number(repo: str, milestone: str | int | None) -> int | None:
    """Resolve a milestone number, or else its exact title, into its GitHub milestone number."""
    if _is_trivial_milestone(milestone):
        return None
    if isinstance(milestone, int):
        return milestone
    cleaned = str(milestone).strip()
    if cleaned.isdigit():
        return int(cleaned)

    query = urlencode({"state": "all", "per_page": DEFAULT_GH_REST_PER_PAGE})
    milestones = get_github_session().paginate(f"/repos/{repo}/milestones?{query}")
    matched = _find_milestone_match(milestones, cleaned)
    if matched is not None:
        return matched

    raise GitHubOperationError(
        f"Milestone '{cleaned}' was not found in repository {repo}.",
        operation="resolve_milestone",
        details={"repo": repo, "milestone": cleaned[:256]},
    )


def _resolve_updated_labels(
    repo: str,
    number: int,
    labels: list[str] | None,
    add_labels: list[str] | None,
    remove_labels: list[str] | None,
) -> list[str] | None:
    """Resolve new complete label list when adding or removing taxonomy labels."""
    if labels is not None:
        return labels
    if not add_labels and not remove_labels:
        return None

    cmd = [CONST_GH_CLI, "api", f"repos/{repo}/issues/{number}"]
    res = run_gh(cmd, check=False, quiet=True)
    curr_labels: set[str] = set()
    if res.returncode == 0 and res.stdout:
        try:
            data = json.loads(res.stdout)
            curr_labels = set(_parse_issue_labels(data.get("labels", [])))
        except json.JSONDecodeError, TypeError:
            pass

    if add_labels:
        curr_labels.update(add_labels)
    if remove_labels:
        curr_labels.difference_update(remove_labels)

    return sorted(curr_labels)
