"""GitHub Issues management, taxonomy enforcement, and triage auditing."""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.git import GitHubOperationError

logger = logging.getLogger(__name__)


class GitHubIssue(BaseModel):
    """Normalized GitHub Issue representation with taxonomy tags and milestone."""

    number: int
    title: str
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
    issues_missing_milestone: list[int] = Field(default_factory=list)

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
        state=str(item.get("state", "open")).lower(),
        milestone=milestone_title,
        labels=_parse_issue_labels(item.get("labels")),
        assignees=_parse_issue_assignees(item.get("assignees")),
        created_at=str(item.get("createdAt") or item.get("created_at") or ""),
        updated_at=str(item.get("updatedAt") or item.get("updated_at") or ""),
        url=str(item.get("url") or item.get("html_url") or ""),
    )


def get_repository_issues(
    repo: str,
    state: str = "open",
    milestone: str | None = None,
    label: str | None = None,
    labels: list[str] | None = None,
    limit: int = 30,
) -> list[GitHubIssue]:
    """Retrieve issues from repository via gh issue list."""
    cmd = [
        CONST_GH_CLI,
        "issue",
        "list",
        "--repo",
        repo,
        "--state",
        state,
        "--limit",
        str(limit),
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

    res = run_subprocess(cmd, check=False, quiet=True)
    if res.returncode != 0 or not res.stdout.strip():
        return []

    try:
        raw_list = json.loads(res.stdout)
        if not isinstance(raw_list, list):
            return []
        return [_parse_single_issue(item) for item in raw_list if isinstance(item, dict)]
    except Exception as exc:
        logger.debug("Failed to parse issues: %s", exc)
        return []


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
    milestone: str | None,
    labels: list[str] | None,
) -> GitHubIssue:
    """Parse output from issue creation command into a typed GitHubIssue."""
    cleaned = stdout.strip()
    if cleaned.startswith("{"):
        try:
            data = json.loads(cleaned)
            if data and "number" in data:
                return _parse_single_issue(data)
        except Exception:
            pass
    return GitHubIssue(
        number=_extract_issue_number(cleaned),
        title=title,
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
    res = run_subprocess(cmd, check=False, quiet=True)
    if res.returncode != 0:
        raise GitHubOperationError(
            f"Failed to create GitHub issue: {res.stderr or res.stdout}",
            operation="create_issue",
            details={"repo": repo, "title": title},
        )
    return _parse_created_issue(res.stdout, title, milestone, labels)


def audit_issues_triage(repo: str) -> IssueTriageAudit:
    """Audit open issues against mandatory taxonomy labeling and milestone rules."""
    open_issues = get_repository_issues(repo, state="open", limit=100)
    audit = IssueTriageAudit(total_open=len(open_issues))

    for issue in open_issues:
        has_type = any(lbl.startswith("type/") for lbl in issue.labels)
        has_scope = any(lbl.startswith("scope/") for lbl in issue.labels)
        has_priority = any(lbl.startswith("priority/") for lbl in issue.labels)
        has_milestone = bool(issue.milestone)

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
        if not has_milestone:
            audit.issues_missing_milestone.append(issue.number)
            is_valid = False

        if is_valid:
            audit.valid_count += 1

    return audit


def get_issues_summary(repo: str) -> dict[str, Any]:
    """Calculate aggregate issue counts by priority, type, and milestone."""
    open_issues = get_repository_issues(repo, state="open", limit=100)
    priority_counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    milestone_counter: Counter[str] = Counter()

    for issue in open_issues:
        for lbl in issue.labels:
            if lbl.startswith("priority/"):
                priority_counter[lbl] += 1
            elif lbl.startswith("type/"):
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
