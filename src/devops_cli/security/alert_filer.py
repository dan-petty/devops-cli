"""The issue of each open `Trivy-config` code scanning alert group (#4401).

The `Security Scan` step of CI uploads the results of `trivy config` to GitHub code scanning, and
nothing turned an alert there into work. `file_alert_issues` reads the open alerts, groups them by
rule and file, and files one issue for each group that no open issue names. `SECURITY.md` ("Judging
a Trivy-config Alert") names who judges the issue and in what time.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from pydantic import AliasPath, BaseModel, Field

from devops_cli.config.constants import (
    CONST_TRIVY_CONFIG_ALERT_ISSUE_LABELS,
    CONST_TRIVY_CONFIG_ALERT_ISSUES_PER_RUN,
    CONST_TRIVY_CONFIG_ALERT_TOOL,
)
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github.session import GitHubSession

# The severities of Trivy, worst first: a run that files too few issues files the worst first.
_SEVERITY_ORDER: Final[tuple[str, ...]] = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")
_TITLE: Final[str] = "fix(security): judge Trivy-config {rule_id} in {path}"


class CodeScanningAlert(BaseModel):
    """The fields of one code scanning alert that the filer reads."""

    number: int
    tool_name: str = Field(validation_alias=AliasPath("tool", "name"))
    rule_id: str = Field(validation_alias=AliasPath("rule", "id"))
    severity_level: str | None = Field(
        default=None, validation_alias=AliasPath("rule", "security_severity_level")
    )
    severity_label: str | None = Field(default=None, validation_alias=AliasPath("rule", "severity"))
    path: str = Field(
        validation_alias=AliasPath("most_recent_instance", "location", "path"),
    )

    @property
    def severity(self) -> str:
        """The severity of Trivy in capitals, or the coarse level of GitHub when it gives none."""
        return (self.severity_level or self.severity_label or "UNKNOWN").upper()


@dataclass(frozen=True)
class AlertGroup:
    """The open alerts of one rule in one file."""

    rule_id: str
    path: str
    severity: str
    numbers: tuple[int, ...]

    @property
    def title(self) -> str:
        """The title of the issue, which is also the key that tells an open issue holds the group."""
        return _TITLE.format(rule_id=self.rule_id, path=self.path)

    def body(self, repo: str) -> str:
        """The text of the issue: the rule, the path, the severity and the alerts."""
        alerts = "\n".join(
            f"- alert {number}: https://github.com/{repo}/security/code-scanning/{number}"
            for number in self.numbers
        )
        return (
            "Trivy reports a misconfiguration that no issue names.\n\n"
            f"- Rule: {self.rule_id}\n"
            f"- Path: {self.path}\n"
            f"- Severity: {self.severity}\n\n"
            f"Open alerts:\n{alerts}\n\n"
            'Judge it under "Judging a Trivy-config Alert" in SECURITY.md: fix the file, dismiss '
            "the alert with a reason, or add a time-limited entry to `.trivyignore.yaml`. The "
            "owner judges a CRITICAL alert within 24 hours. An agent judges any other alert "
            "within 14 days.\n"
        )


@dataclass(frozen=True)
class FilingPlan:
    """The groups that a run files, and those that it leaves for the next run."""

    to_file: tuple[AlertGroup, ...]
    left: tuple[AlertGroup, ...]


@dataclass(frozen=True)
class FilingOutcome:
    """What a run did: the issue of each group it filed, the groups that an open issue holds, and
    the groups it left for the next run."""

    filed: tuple[tuple[AlertGroup, int], ...]
    held: tuple[AlertGroup, ...]
    left: tuple[AlertGroup, ...]


class _CreatedIssue(BaseModel):
    number: int


def _rank(severity: str) -> int:
    return _SEVERITY_ORDER.index(severity) if severity in _SEVERITY_ORDER else len(_SEVERITY_ORDER)


def group_alerts(alerts: Iterable[CodeScanningAlert]) -> list[AlertGroup]:
    """The `Trivy-config` alerts of `alerts` grouped by rule id and file path, the worst severity
    first. An alert of another tool belongs to no group."""
    by_key: dict[tuple[str, str], list[CodeScanningAlert]] = {}
    for alert in alerts:
        if alert.tool_name == CONST_TRIVY_CONFIG_ALERT_TOOL:
            by_key.setdefault((alert.rule_id, alert.path), []).append(alert)
    groups = [
        AlertGroup(
            rule_id=rule_id,
            path=path,
            severity=min((a.severity for a in members), key=_rank),
            numbers=tuple(sorted(a.number for a in members)),
        )
        for (rule_id, path), members in by_key.items()
    ]
    return sorted(groups, key=lambda g: (_rank(g.severity), g.rule_id, g.path))


def plan_filing(groups: Sequence[AlertGroup], open_titles: set[str], *, limit: int) -> FilingPlan:
    """The groups with no open issue, split into the first `limit` and the rest. A group that an
    open issue names uses none of the limit."""
    wanted = [group for group in groups if group.title not in open_titles]
    return FilingPlan(to_file=tuple(wanted[:limit]), left=tuple(wanted[limit:]))


def _repo_path(repo: str, tail: str) -> str:
    return f"/repos/{repo}/{tail}"


def read_open_alerts(session: GitHubSession, repo: str) -> list[CodeScanningAlert]:
    """Every open `Trivy-config` alert of `repo`, all pages read."""
    path = _repo_path(
        repo,
        f"code-scanning/alerts?state=open&tool_name={CONST_TRIVY_CONFIG_ALERT_TOOL}"
        f"&per_page={DEFAULT_GH_REST_PER_PAGE}",
    )
    return [CodeScanningAlert.model_validate(item) for item in session.paginate(path)]


def read_open_issue_titles(session: GitHubSession, repo: str) -> set[str]:
    """The title of every open issue of `repo`, all pages read. A pull request is no issue."""
    path = _repo_path(repo, f"issues?state=open&per_page={DEFAULT_GH_REST_PER_PAGE}")
    return {
        str(item["title"])
        for item in session.paginate(path)
        if isinstance(item, dict) and "pull_request" not in item
    }


def file_alert_issues(
    session: GitHubSession,
    repo: str,
    *,
    limit: int = CONST_TRIVY_CONFIG_ALERT_ISSUES_PER_RUN,
) -> FilingOutcome:
    """File one issue for each open `Trivy-config` alert group of `repo` that no open issue names,
    at most `limit` of them, the worst severity first."""
    groups = group_alerts(read_open_alerts(session, repo))
    if not groups:
        return FilingOutcome((), (), ())
    open_titles = read_open_issue_titles(session, repo)
    plan = plan_filing(groups, open_titles, limit=limit)
    filed: list[tuple[AlertGroup, int]] = []
    for group in plan.to_file:
        path = _repo_path(repo, "issues")
        answer = session.rest(
            "POST",
            path,
            body={
                "title": group.title,
                "body": group.body(repo),
                "labels": list(CONST_TRIVY_CONFIG_ALERT_ISSUE_LABELS),
            },
        )
        try:
            created = _CreatedIssue.model_validate(answer)
        except ValueError as exc:
            raise GitHubUnreadError(
                f"GitHub's answer to POST {path} holds no issue number",
                details={"path": path},
            ) from exc
        filed.append((group, created.number))
    held = tuple(group for group in groups if group.title in open_titles)
    return FilingOutcome(filed=tuple(filed), held=held, left=plan.left)
