"""GitHub Issues management, taxonomy enforcement, and triage auditing."""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

if TYPE_CHECKING:
    from devops_cli.dry_run.requests import PlannedRequest

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.exceptions.git import (
    GitHubOperationError,
    GitHubUnreadError,
)
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import get_github_session
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.store import GitHubState, RoadmapStore

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


def issues_list_args(
    repo: str,
    state: str = "open",
    milestone: str | None = None,
    label: str | None = None,
    labels: list[str] | None = None,
    limit: int | None = 30,
) -> list[str]:
    """Arguments for listing repository issues via gh issue list."""
    cmd = [
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
    return cmd


def issues_list_requests(
    repo: str,
    state: str = "open",
    milestone: str | None = None,
    label: str | None = None,
    labels: list[str] | None = None,
    limit: int | None = 30,
) -> list[PlannedRequest]:
    """Planned requests for listing repository issues."""
    from devops_cli.roadmap.request_plan import planned_gh

    args = issues_list_args(
        repo, state=state, milestone=milestone, label=label, labels=labels, limit=limit
    )
    return [planned_gh(args, f"repos/{repo}/issues")]


def get_repository_issues(
    repo: str,
    state: str = "open",
    milestone: str | None = None,
    label: str | None = None,
    labels: list[str] | None = None,
    limit: int | None = 30,
) -> list[GitHubIssue]:
    """Retrieve issues via gh issue list with a REST fallback; ``limit=None`` reads every issue."""
    all_labels = list(labels or [])
    if label and label not in all_labels:
        all_labels.append(label)
    cmd = [
        CONST_GH_CLI,
        *issues_list_args(
            repo, state=state, milestone=milestone, label=label, labels=labels, limit=limit
        ),
    ]

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


def create_issue_args(
    repo: str,
    title: str,
    body: str = "",
    milestone: str | None = None,
    labels: list[str] | None = None,
) -> list[str]:
    """Construct argument list for gh issue create."""
    cmd = ["issue", "create", "--repo", repo, "--title", title, "--body", body]
    if milestone:
        cmd.extend(["--milestone", milestone])
    if labels:
        for lbl in labels:
            cmd.extend(["--label", lbl])
    return cmd


def create_issue_requests(
    repo: str,
    title: str,
    body: str = "",
    milestone: str | None = None,
    labels: list[str] | None = None,
) -> list[PlannedRequest]:
    """Planned requests for creating a new GitHub issue."""
    from devops_cli.roadmap.request_plan import planned_gh

    args = create_issue_args(repo, title, body, milestone, labels)
    return [planned_gh(args, f"repos/{repo}/issues")]


def _build_create_issue_cmd(
    repo: str,
    title: str,
    body: str = "",
    milestone: str | None = None,
    labels: list[str] | None = None,
) -> list[str]:
    """Construct command argument list for gh issue create."""
    return [CONST_GH_CLI, *create_issue_args(repo, title, body, milestone, labels)]


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
                patch_res = run_gh(patch_cmd, check=False, quiet=True)
                if patch_res.returncode != 0:
                    assigned_milestone = None
            else:
                assigned_milestone = None
    if res.returncode != 0:
        raise GitHubOperationError(
            f"Failed to create GitHub issue: {res.stderr or res.stdout}",
            operation="create_issue",
            details={"repo": repo, "title": title[:256]},
        )
    return _parse_created_issue(res.stdout, title, body, assigned_milestone, labels)


def _open_store(repo: str, store: RoadmapStore | None) -> RoadmapStore:
    """The given roadmap store, else the roadmap store of `repo`."""
    return store if store is not None else roadmap_store.get_roadmap_store(repo)


def _has_prefix(labels: Iterable[str], prefix: str) -> bool:
    return any(label.startswith(prefix) for label in labels)


def audit_issues_triage(repo: str, *, store: RoadmapStore | None = None) -> IssueTriageAudit:
    """Audit open issues against the mandatory taxonomy labels.

    An open issue with no Priority is a Candidate, reported once, as awaiting intake: `devops
    roadmap intake` gives it its type and Priority (#742). Every other open issue is an Item,
    which holds a Priority, and must hold a `type/*` and a `scope/*` label. A backlog item has
    no milestone, so a missing milestone is no finding.
    """
    roadmap = _open_store(repo, store)
    open_items = [item for item in roadmap.items() if item.state is GitHubState.OPEN]
    candidates = roadmap.candidates()
    audit = IssueTriageAudit(
        total_open=len(open_items) + len(candidates),
        issues_awaiting_intake=sorted(candidate.number for candidate in candidates),
    )
    for item in open_items:
        has_type = _has_prefix(item.labels, "type/")
        has_scope = _has_prefix(item.labels, "scope/")
        if not has_type:
            audit.issues_missing_type.append(item.number)
        if not has_scope:
            audit.issues_missing_scope.append(item.number)
        if has_type and has_scope:
            audit.valid_count += 1
    audit.issues_missing_type.sort()
    audit.issues_missing_scope.sort()
    return audit


def issues_triage_requests(repo: str) -> list[PlannedRequest]:
    """Planned requests for issue taxonomy triage."""
    from devops_cli.roadmap.request_plan import StoreRequests

    return list(StoreRequests(repo).every_issue())


def get_issues_summary(repo: str, *, store: RoadmapStore | None = None) -> dict[str, Any]:
    """Count the open issues by Priority, type and milestone: the open Items and the
    Candidates, which hold no Priority."""
    roadmap = _open_store(repo, store)
    open_items = [item for item in roadmap.items() if item.state is GitHubState.OPEN]
    candidates = roadmap.candidates()
    priority_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    milestone_counter: Counter[str] = Counter()
    for item in open_items:
        if item.priority:
            priority_counter[item.priority] += 1
    for labels, milestone in [
        *((item.labels, item.milestone) for item in open_items),
        *((candidate.labels, candidate.milestone) for candidate in candidates),
    ]:
        for label in labels:
            if label.startswith("type/"):
                type_counter[label] += 1
        milestone_counter[milestone or "no-milestone"] += 1
    return {
        "total_open": len(open_items) + len(candidates),
        "by_priority": dict(priority_counter),
        "by_type": dict(type_counter),
        "by_milestone": dict(milestone_counter),
    }


def issues_status_requests(repo: str) -> list[PlannedRequest]:
    """Planned requests for issue status breakdown."""
    from devops_cli.roadmap.request_plan import StoreRequests

    return list(StoreRequests(repo).every_issue())


def issues_edit_args(owner: str, repo_name: str, number: int) -> list[str]:
    """Arguments for editing an issue via gh api PATCH."""
    return [
        "api",
        "--method",
        "PATCH",
        f"repos/{owner}/{repo_name}/issues/{number}",
        "--input",
        "-",
    ]


def issues_edit_requests(
    target_repo: str,
    number: int,
    payload: dict[str, Any],
) -> list[PlannedRequest]:
    """Planned requests for editing an existing issue."""
    from devops_cli.roadmap.request_plan import planned_gh

    owner, repo_name = target_repo.split("/", 1) if "/" in target_repo else ("<owner>", target_repo)
    args = issues_edit_args(owner, repo_name, number)
    return [
        planned_gh(
            args,
            f"repos/{target_repo}/issues/{number}",
            stdin=json.dumps(payload),
        )
    ]


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
