"""The roadmap step `infra-apply`: plan and apply a merged infra pull request (#5130)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final

from devops_cli.config.settings import Settings, load_settings
from devops_cli.exceptions.k8s import ClusterJobExistsError
from devops_cli.github.repo_ref import RepoRef, ServiceRow
from devops_cli.github.session import get_github_session
from devops_cli.infra.access import _ORDER, AgentAccess
from devops_cli.infra.apply import (
    ApplyRequest,
    apply_saved_plan,
    apply_table,
    audit_details,
    render_apply_footer,
    render_apply_header,
)
from devops_cli.infra.onboard import resolve_target
from devops_cli.infra.plan import (
    PlanRequest,
    plan_entry,
    plan_tables,
    render_plan_footer,
    render_plan_header,
    run_plan,
)
from devops_cli.k8s.cluster_job_api import ClusterJobs
from devops_cli.lang import MESSAGES
from devops_cli.models.infra import (
    ApplyReport,
    ApplyResult,
    HostOutcome,
    InfraPlan,
    PlanStatus,
    ReadCommit,
)
from devops_cli.output import print_info
from devops_cli.roadmap.implement.implement_size import RUNNER_SIZES
from devops_cli.roadmap.job_launcher import RunnerUnit, launch
from devops_cli.roadmap.steps.comment import Target, post

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient

logger = logging.getLogger(__name__)

INFRA_APPLY_MARKER: Final[str] = "<!-- devops roadmap infra-apply -->"


def infra_apply_unit(
    repo: str,
    pull: int,
    commit: str,
    *,
    playbook: str = "site.yaml",
) -> RunnerUnit:
    """The runner unit of an infra apply Job."""
    ref = RepoRef(repo)
    return RunnerUnit(
        row=ServiceRow.INFRA_APPLY,
        repo=ref,
        item=pull,
        args=(
            "roadmap",
            "step",
            "infra-apply",
            "--repo",
            repo,
            "--pull",
            str(pull),
            "--commit",
            commit,
            "--playbook",
            playbook,
        ),
        size=RUNNER_SIZES[0],
        name=ref.unit_name(ServiceRow.INFRA_APPLY, commit, pull),
        deadline=7200,
        annotations={
            "roadmap.devops-cli/commit": commit,
        },
    )


def launch_infra_apply(
    repo: str,
    pull: int,
    commit: str,
    *,
    playbook: str = "site.yaml",
    settings: Settings | None = None,
    jobs: ClusterJobs | None = None,
) -> str | None:
    """Launch a cluster Job for infra apply if the repository is at level safe or full."""
    active_settings = settings or load_settings()
    ref = RepoRef(repo)
    entry = active_settings.infra.entry(ref)
    access = entry.agent_access if entry is not None else AgentAccess.NONE
    if _ORDER.index(access) < _ORDER.index(AgentAccess.SAFE):
        return None
    unit = infra_apply_unit(repo, pull, commit, playbook=playbook)
    cluster_jobs = jobs or ClusterJobs()
    try:
        return launch(cluster_jobs, unit)
    except ClusterJobExistsError:
        return None


def render_apply_comment(repo: str, commit: str, report: ApplyReport) -> str:
    """Render the pull request comment for an infra apply with its result and audit record."""
    header_lines = render_apply_header(report)
    columns, cells = apply_table(report)
    footer_lines = render_apply_footer(report)
    audit = audit_details(report)
    audit_json = json.dumps(audit, indent=2)

    parts: list[str] = [
        f"{INFRA_APPLY_MARKER} commit={commit}",
        f"### Infra Apply for `{repo}@{commit[:8]}`",
        "",
    ]
    parts.extend(header_lines)
    parts.append("")
    if cells:
        parts.append("| " + " | ".join(columns) + " |")
        parts.append("| " + " | ".join(["---"] * len(columns)) + " |")
        for row in cells:
            parts.append("| " + " | ".join(row) + " |")
        parts.append("")
    parts.extend(footer_lines)
    parts.append("")
    parts.append("<details><summary>Audit record (infra.apply)</summary>")
    parts.append("")
    parts.append("```json")
    parts.append(audit_json)
    parts.append("```")
    parts.append("</details>")
    return "\n".join(parts)


def render_failed_plan_comment(
    repo: str, commit: str, plan: InfraPlan, read: ReadCommit | Any
) -> str:
    """Render the pull request comment when the plan failed."""
    header_lines = render_plan_header(plan, read)
    host_columns, host_cells, task_columns, task_cells = plan_tables(plan)
    footer_lines = render_plan_footer(plan)
    parts: list[str] = [
        f"{INFRA_APPLY_MARKER} commit={commit}",
        f"### Infra Apply for `{repo}@{commit[:8]}`",
        "",
        "**Plan failed; apply not started.**",
        "",
    ]
    parts.extend(header_lines)
    parts.append("")
    if host_cells:
        parts.append("| " + " | ".join(host_columns) + " |")
        parts.append("| " + " | ".join(["---"] * len(host_columns)) + " |")
        for row in host_cells:
            parts.append("| " + " | ".join(row) + " |")
        parts.append("")
    if task_cells:
        parts.append(f"**{MESSAGES.infra.plan_caption}**")
        parts.append("")
        parts.append("| " + " | ".join(task_columns) + " |")
        parts.append("| " + " | ".join(["---"] * len(task_columns)) + " |")
        for row in task_cells:
            parts.append("| " + " | ".join(row) + " |")
        parts.append("")
    parts.extend(footer_lines)
    return "\n".join(parts)


def failure_marker(repo: str, host: str) -> str:
    """The marker string for an apply failure issue."""
    return f"<!-- devops roadmap infra-apply failure: repo={repo} host={host} -->"


def manage_apply_failure_issue(
    client: GitHubClient,
    repo: str,
    commit: str,
    host: str,
    reason: str,
    *,
    plan_id: str | None = None,
) -> str | None:
    """Create or update one failure issue in `repo` for `host`."""
    marker = failure_marker(repo, host)
    hits = client.search_issue_bodies(repo, marker)
    open_hits: list[int] = []
    for hit in hits:
        if hit.state == "open" and hit.body and marker in hit.body:
            open_hits.append(hit.number)
    open_hits.sort()

    title = f"fix(infra): apply failed on {host} in {repo}"
    body_lines = [
        marker,
        f"## Infra Apply Failure on `{host}`",
        "",
        f"- **Repository**: `{repo}`",
        f"- **Commit**: `{commit}`",
    ]
    if plan_id:
        body_lines.append(f"- **Plan**: `{plan_id}`")
    body_lines.extend(
        [
            f"- **Reason**: {reason}",
            "",
            "The node stays cordoned. Resolve the problem, then plan and apply again on a workstation.",
        ]
    )
    body = "\n".join(body_lines) + "\n"

    if open_hits:
        issue_num = open_hits[0]
        client.update_issue_body(repo, issue_num, body)
        return f"Updated issue #{issue_num} in {repo} for host {host}."

    issue_num = client.create_issue(repo, title=title, body=body, labels=())
    return f"Opened issue #{issue_num} in {repo} for host {host}."


def run_infra_apply(
    repo: str,
    pull: int,
    commit: str,
    *,
    playbook: str = "site.yaml",
    settings: Settings | None = None,
    client: GitHubClient | None = None,
    target: Target | Any = None,
    dry_run: bool = False,
    plan_runner: Callable[..., tuple[InfraPlan, Any]] | None = None,
    apply_runner: Callable[..., ApplyReport] | None = None,
) -> int:
    """Run an infra apply for a merged pull request and post or update the marked comment."""
    active_settings = settings or load_settings()
    ref = RepoRef(repo)
    entry = active_settings.infra.entry(ref)

    access = entry.agent_access if entry is not None else AgentAccess.NONE
    if _ORDER.index(access) < _ORDER.index(AgentAccess.SAFE):
        message = MESSAGES.infra.infra_apply_refused.format(repo=repo)
        logger.info(message)
        print_info(message)
        return 0

    if dry_run:
        return 0

    runner_plan = plan_runner or run_plan
    target_obj = resolve_target(repo, path=None, settings=active_settings)
    plan_cfg = plan_entry(target_obj, active_settings)
    request = PlanRequest(playbook=playbook, ref=commit)
    plan_record, read = runner_plan(target_obj, plan_cfg, active_settings, request)

    post_target = target if target is not None else Target(repo, pull, client=client)
    gh_client = client if client is not None else get_github_session().client

    if plan_record.status is not PlanStatus.OK:
        body = render_failed_plan_comment(repo, commit, plan_record, read)
        post(post_target, INFRA_APPLY_MARKER, commit, body)
        failed_host = next((h for h in plan_record.hosts if h.failed), None)
        host_name = (
            failed_host.host
            if failed_host
            else (plan_record.hosts[0].host if plan_record.hosts else "unknown")
        )
        failed_reason = failed_host.failed[0].reason if failed_host and failed_host.failed else None
        reason = failed_reason or "Plan failed"
        manage_apply_failure_issue(
            gh_client, repo, commit, host_name, reason, plan_id=plan_record.id
        )
        return 1

    runner_apply = apply_runner or apply_saved_plan
    apply_req = ApplyRequest(plan_id=plan_record.id, playbook=playbook)
    report = runner_apply(target_obj, active_settings, apply_req, approve=lambda _: True)

    body = render_apply_comment(repo, commit, report)
    post(post_target, INFRA_APPLY_MARKER, commit, body)

    if report.result is not ApplyResult.OK:
        stopped_host = next((h for h in report.hosts if h.outcome is HostOutcome.STOPPED), None)
        host_name = (
            stopped_host.host
            if stopped_host
            else (report.hosts[0].host if report.hosts else "unknown")
        )
        reason = (stopped_host.reason if stopped_host else report.reason) or "Apply stopped"
        manage_apply_failure_issue(
            gh_client, repo, commit, host_name, reason, plan_id=report.plan_id
        )
        return 1

    return 0


__all__ = [
    "INFRA_APPLY_MARKER",
    "failure_marker",
    "infra_apply_unit",
    "launch_infra_apply",
    "manage_apply_failure_issue",
    "render_apply_comment",
    "render_failed_plan_comment",
    "run_infra_apply",
]
