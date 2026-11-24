"""Detect configuration drift between declared infra repo playbooks and live hosts (#5127).

The drift command plans the playbook (default `site.yaml`) on every in-service host in check mode
at the head of the default branch of `origin`. Hosts with changed tasks indicate drift.
Results are tracked in Prometheus metrics and reflected in a single GitHub marker issue in the
target repository.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

from devops_cli.config.settings import InfraRepoConfig, Settings
from devops_cli.github.session import get_github_session
from devops_cli.infra.access import AgentAccess, require_agent_level
from devops_cli.infra.onboard import OnboardTarget
from devops_cli.infra.plan import PlanRequest, run_plan
from devops_cli.lang import MESSAGES
from devops_cli.models.infra import HostPlan, InfraPlan, PlanStatus, ReadCommit
from devops_cli.telemetry.instruments import (
    INFRA_DRIFT_HOSTS,
    INFRA_RUNS_TOTAL,
    bounded_label,
    emit,
)

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient

DRIFT_ACTION: Final[str] = "devops infra drift"
DEFAULT_PLAYBOOK: Final[str] = "site.yaml"
DRIFT_MARKER_PREFIX: Final[str] = "devops-infra-drift"
_MARKER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"<!--\s*devops-infra-drift:\s*(\S+)\s+(\S+)\s*-->"
)
DRIFT_ISSUE_TITLE: Final[str] = "fix(infra): drift detected on {repo}"


def drift_marker(repo: str, plan_id: str) -> str:
    """The hidden HTML comment marking a drift issue for `repo` and `plan_id`."""
    return f"<!-- {DRIFT_MARKER_PREFIX}: {repo} {plan_id} -->"


def find_marker(body: str | None) -> tuple[str, str] | None:
    """Extract (repo, plan_id) from an issue body containing the drift marker."""
    if not body:
        return None
    match = _MARKER_PATTERN.search(body)
    if match:
        return match.group(1), match.group(2)
    return None


def drift_entry(target: OnboardTarget, settings: Settings) -> InfraRepoConfig:
    """The settings entry of the repo, checking that the caller has `plan` access.

    Raises:
        InfraAccessRefusedError: an agent runs on a repo with access below `plan`.
    """
    entry = settings.infra.entry(target.repo) or InfraRepoConfig(repo=target.repo.display)
    require_agent_level(
        entry.agent_access, AgentAccess.PLAN, action=DRIFT_ACTION, repo=target.repo.display
    )
    return entry


def render_drift_issue_body(
    repo: str,
    commit: str,
    plan_id: str,
    drifted_hosts: Sequence[HostPlan],
) -> str:
    """Format the GitHub issue body reporting infrastructure drift on `repo`."""
    marker = drift_marker(repo, plan_id)
    lines = [
        marker,
        "",
        f"# Infrastructure Drift Detected on {repo}",
        "",
        f"Check mode found drift on `{repo}` at commit `{commit}` (plan `{plan_id}`).",
        "",
        "## Drifted Hosts",
        "",
    ]
    for host in drifted_hosts:
        lines.append(f"### `{host.host}`")
        lines.append("")
        if host.changed:
            lines.append("#### Changed Tasks")
            for ctask in host.changed:
                lines.append(f"- **{ctask.name}** (`{ctask.path}`) [{ctask.action}]")
            lines.append("")
        if host.unchecked:
            lines.append("#### Unchecked Tasks")
            for utask in host.unchecked:
                lines.append(f"- **{utask.name}** (`{utask.path}`) [{utask.action}]")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def manage_drift_issue(
    client: GitHubClient,
    repo: str,
    plan: InfraPlan,
    drifted_hosts: Sequence[HostPlan],
) -> str | None:
    """Create, update, or close the drift marker issue in `repo`.

    Returns a brief description of the action taken, or None if no action was needed.
    """
    hits = client.search_issue_bodies(repo, DRIFT_MARKER_PREFIX)
    open_hits: list[tuple[int, str, str]] = []
    for hit in hits:
        if hit.state == "open" and hit.body:
            found = find_marker(hit.body)
            if found:
                marker_repo, marker_plan_id = found
                if marker_repo.casefold() == repo.casefold():
                    open_hits.append((hit.number, marker_repo, marker_plan_id))

    open_hits.sort(key=lambda item: item[0])

    if drifted_hosts:
        body = render_drift_issue_body(repo, plan.commit, plan.id, drifted_hosts)
        if open_hits:
            issue_num, _, current_plan_id = open_hits[0]
            if current_plan_id == plan.id:
                return MESSAGES.infra.drift_issue_unchanged.format(number=issue_num)
            client.update_issue_body(repo, issue_num, body)
            return MESSAGES.infra.drift_issue_updated.format(number=issue_num, repo=repo)
        title = DRIFT_ISSUE_TITLE.format(repo=repo)
        issue_num = client.create_issue(repo, title=title, body=body, labels=())
        return MESSAGES.infra.drift_issue_opened.format(number=issue_num, repo=repo)

    if open_hits:
        issue_num = open_hits[0][0]
        client.close_issue(repo, issue_num, reason="completed")
        return MESSAGES.infra.drift_issue_closed.format(number=issue_num, repo=repo)

    return MESSAGES.infra.drift_issue_none


def render_drift_report(
    repo: str,
    playbook: str,
    plan: InfraPlan,
    read: ReadCommit,
    drifted_hosts: Sequence[HostPlan],
    issue_msg: str | None = None,
) -> list[str]:
    """Render plain text drift report for stdout."""
    lines = [
        MESSAGES.infra.drift_title.format(repo=repo, playbook=playbook),
        MESSAGES.infra.read_commit.format(ref=read.ref, commit=read.commit),
    ]
    if read.checkout_differs:
        where = (
            MESSAGES.infra.checkout_on_branch.format(branch=read.checkout_branch)
            if read.checkout_branch
            else MESSAGES.infra.checkout_detached
        )
        lines.append(
            MESSAGES.infra.checkout_differs.format(
                where=where, commit=read.checkout_commit, ref=read.ref
            )
        )
    if drifted_hosts:
        lines.append("")
        lines.append(MESSAGES.infra.drift_detected.format(repo=repo, count=len(drifted_hosts)))
        for host in drifted_hosts:
            lines.append("")
            lines.append(MESSAGES.infra.drift_host_header.format(host=host.host))
            for ctask in host.changed:
                lines.append(
                    MESSAGES.infra.drift_changed_task.format(
                        name=ctask.name, path=ctask.path, action=ctask.action
                    )
                )
            for utask in host.unchecked:
                lines.append(
                    MESSAGES.infra.drift_unchecked_task.format(
                        name=utask.name, path=utask.path, action=utask.action
                    )
                )
        lines.append("")
        lines.append(MESSAGES.infra.drift_plan_id.format(id=plan.id))
    else:
        lines.append(MESSAGES.infra.drift_no_drift.format(repo=repo))

    if issue_msg:
        lines.append(issue_msg)

    return lines


def run_drift(
    target: OnboardTarget,
    entry: InfraRepoConfig,
    settings: Settings,
    *,
    playbook: str = DEFAULT_PLAYBOOK,
    dry_run: bool = False,
    client: GitHubClient | None = None,
) -> tuple[int, list[str]]:
    """Execute drift check for `target`, record metrics, and manage marker issue.

    Returns exit code (0 for no drift, 2 for drift, 1 for failure) and report lines.
    """
    repo_label = bounded_label(target.repo.display.casefold())
    request = PlanRequest(playbook=playbook)
    plan, read = run_plan(target, entry, settings, request)

    if plan.status is PlanStatus.FAILED:
        emit(
            INFRA_RUNS_TOTAL,
            1.0,
            {"repo": repo_label, "command": "drift", "result": "failed"},
        )
        error_lines = [
            MESSAGES.infra.drift_title.format(repo=target.repo.display, playbook=playbook),
            plan.error or MESSAGES.infra.plan_run_failed.format(code=1),
        ]
        return 1, error_lines

    drifted_hosts = tuple(host for host in plan.hosts if host.changed)
    emit(INFRA_DRIFT_HOSTS, float(len(drifted_hosts)), {"repo": repo_label})
    result_label = "drift" if drifted_hosts else "ok"
    emit(
        INFRA_RUNS_TOTAL,
        1.0,
        {"repo": repo_label, "command": "drift", "result": result_label},
    )

    issue_msg: str | None = None
    if not dry_run:
        gh_client = client or get_github_session().client
        issue_msg = manage_drift_issue(gh_client, target.repo.display, plan, drifted_hosts)

    report_lines = render_drift_report(
        target.repo.display, playbook, plan, read, drifted_hosts, issue_msg=issue_msg
    )
    exit_code = 2 if drifted_hosts else 0
    return exit_code, report_lines


__all__ = [
    "DEFAULT_PLAYBOOK",
    "DRIFT_ACTION",
    "DRIFT_ISSUE_TITLE",
    "DRIFT_MARKER_PREFIX",
    "drift_entry",
    "drift_marker",
    "find_marker",
    "manage_drift_issue",
    "render_drift_issue_body",
    "render_drift_report",
    "run_drift",
]
