"""The roadmap step `infra-plan`: plan an open infra pull request and post or update its marked comment (#5129)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final

from devops_cli.config.settings import Settings, load_settings
from devops_cli.github.repo_ref import RepoRef, ServiceRow
from devops_cli.infra.access import _ORDER, AgentAccess
from devops_cli.infra.onboard import resolve_target
from devops_cli.infra.plan import (
    PlanRequest,
    plan_entry,
    plan_tables,
    render_plan_footer,
    render_plan_header,
    run_plan,
)
from devops_cli.lang import MESSAGES
from devops_cli.models.infra import InfraPlan, PlanStatus, ReadCommit
from devops_cli.output import print_info
from devops_cli.roadmap.implement.implement_size import RUNNER_SIZES
from devops_cli.roadmap.job_launcher import RunnerUnit
from devops_cli.roadmap.steps.comment import Target, post

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient

logger = logging.getLogger(__name__)

INFRA_PLAN_MARKER: Final[str] = "<!-- devops roadmap infra-plan -->"


def infra_plan_unit(
    repo: str,
    pull: int,
    head: str,
    *,
    playbook: str = "site.yaml",
) -> RunnerUnit:
    """The runner unit of an infra plan Job."""
    ref = RepoRef(repo)
    return RunnerUnit(
        row=ServiceRow.INFRA_PLAN,
        repo=ref,
        item=pull,
        args=(
            "roadmap",
            "step",
            "infra-plan",
            "--repo",
            repo,
            "--pull",
            str(pull),
            "--head",
            head,
            "--playbook",
            playbook,
        ),
        size=RUNNER_SIZES[0],
        name=ref.unit_name(ServiceRow.INFRA_PLAN, head, pull),
        deadline=7200,
        annotations={
            "roadmap.devops-cli/head": head,
        },
    )


def render_plan_comment(repo: str, head: str, plan: InfraPlan, read: ReadCommit | Any) -> str:
    """Render the pull request comment for an infra plan."""
    header_lines = render_plan_header(plan, read)
    host_columns, host_cells, task_columns, task_cells = plan_tables(plan)
    footer_lines = render_plan_footer(plan)

    parts: list[str] = [INFRA_PLAN_MARKER, f"### Infra Plan for `{repo}@{head[:8]}`", ""]
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


def run_infra_plan(
    repo: str,
    pull: int,
    head: str,
    *,
    playbook: str = "site.yaml",
    settings: Settings | None = None,
    client: GitHubClient | None = None,
    target: Target | Any = None,
    dry_run: bool = False,
    plan_runner: Callable[..., tuple[InfraPlan, Any]] | None = None,
) -> int:
    """Run an infra plan for a pull request and post or update the marked comment."""
    active_settings = settings or load_settings()
    ref = RepoRef(repo)
    entry = active_settings.infra.entry(ref)

    access = entry.agent_access if entry is not None else AgentAccess.NONE
    if _ORDER.index(access) < _ORDER.index(AgentAccess.PLAN):
        message = MESSAGES.infra.infra_plan_refused.format(repo=repo)
        logger.info(message)
        print_info(message)
        return 0

    if dry_run:
        return 0

    runner = plan_runner or run_plan
    target_obj = resolve_target(repo, path=None, settings=active_settings)
    plan_cfg = plan_entry(target_obj, active_settings)
    request = PlanRequest(playbook=playbook, ref=head)
    plan_record, read = runner(target_obj, plan_cfg, active_settings, request)

    body = render_plan_comment(repo, head, plan_record, read)
    post_target = target if target is not None else Target(repo, pull, client=client)
    post(post_target, INFRA_PLAN_MARKER, None, body)

    return 1 if plan_record.status is PlanStatus.FAILED else 0


__all__ = [
    "INFRA_PLAN_MARKER",
    "infra_plan_unit",
    "render_plan_comment",
    "run_infra_plan",
]
