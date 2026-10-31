"""CLI command for outward-facing capability and upstream dependency maturity survey."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from devops_cli.config.constants import (
    CONST_OUTPUT_FORMAT_TABLE,
)
from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run

if TYPE_CHECKING:
    from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_info, print_table
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.survey.capabilities import (
    compare_capabilities,
    find_capability_gaps,
    load_survey_config,
)
from devops_cli.survey.dependencies import (
    inspect_all_dependencies,
    read_pinned_dependencies,
)
from devops_cli.survey.intake import (
    emit_all_gaps_to_intake,
)
from devops_cli.survey.models import (
    CapabilityComparison,
    CapabilityGap,
    DependencyMaturity,
    SurveyReport,
)

RepoOption = Annotated[str | None, typer.Option("--repo", "-R", help=HELP.survey.repo)]

app = new_typer(
    help=HELP.survey.app,
    no_args_is_help=False,
)


def _render_dependencies_table(dependencies: list[DependencyMaturity]) -> None:
    """Render table of pinned dependencies and mechanical maintenance signals."""
    columns = [
        ("Dependency", "bold cyan"),
        "Version",
        "Last Commit",
        "Cadence",
        "Archival",
        "Licence",
        "Score",
    ]
    rows = []
    for dep in dependencies:
        arch_style = "[bold red]archived[/bold red]" if dep.is_archived else "[green]active[/green]"
        score_val = dep.maintenance_score
        score_str = (
            f"[green]{score_val:.1f}[/green]"
            if score_val >= 80.0
            else f"[yellow]{score_val:.1f}[/yellow]"
            if score_val >= 50.0
            else f"[red]{score_val:.1f}[/red]"
        )
        rows.append(
            [
                dep.name,
                dep.version or "-",
                dep.last_commit_date[:10] if dep.last_commit_date else "-",
                dep.release_cadence,
                arch_style,
                dep.licence,
                score_str,
            ]
        )
    print_table(MESSAGES.survey.survey_dependencies_title, columns, rows)


def _render_capabilities_table(comparisons: list[CapabilityComparison]) -> None:
    """Render table of assessed capabilities across comparable tools."""
    columns = [
        ("Capability", "bold cyan"),
        "Tool",
        "devops-cli",
        "Tool Status",
        "Citation",
        "Gap",
    ]
    rows = []
    for comp in comparisons:
        gap_badge = "[bold red]YES[/bold red]" if comp.is_gap else "[green]NO[/green]"
        rows.append(
            [
                comp.capability,
                comp.tool,
                comp.devops_cli_status.value,
                comp.tool_status.value,
                comp.citation,
                gap_badge,
            ]
        )
    print_table(MESSAGES.survey.survey_capabilities_title, columns, rows)


def survey_requests(
    repo: str,
    *,
    config_file: Path | None = None,
    emit_candidates: bool = False,
    dependencies_only: bool = False,
    capabilities_only: bool = False,
) -> list[PlannedRequest]:
    """Planned requests for outward capability and upstream dependency survey."""
    from devops_cli.dry_run.requests import PlannedRequest
    from devops_cli.roadmap.intake import Filer, NewCandidate, dry_run_intake

    requests: list[PlannedRequest] = []
    if not capabilities_only:
        pins = read_pinned_dependencies()
        for pin in pins:
            requests.append(
                PlannedRequest(
                    method="GET",
                    target=f"PyPI package metadata for {pin.name}",
                    argv=("curl", f"https://pypi.org/pypi/{pin.name}/json"),
                )
            )

    if not dependencies_only and emit_candidates:
        config = load_survey_config(config_file)
        comparisons = compare_capabilities(config)
        gaps = find_capability_gaps(comparisons)
        for gap in gaps:
            title = f"feat(cli): {gap.capability}"
            body = (
                "## Context & Rationale\n"
                f"Outward-facing capability survey identified a capability gap.\n"
                f"The feature is present in comparable tool '{gap.tool}' but absent in devops-cli.\n\n"
                "## Scope & Deliverables\n"
                f"{gap.description or gap.capability}\n\n"
                "## Source Citation\n"
                f"{gap.citation}\n"
            )
            candidate = NewCandidate(
                title=title,
                body=body,
                source=gap.citation,
                filed_by=Filer.AGENT,
            )
            plan = dry_run_intake(repo, new=candidate)
            requests.extend(plan.requests)
            requests.extend(plan.writes)

    return requests


def _render_survey_dry_run(
    target_repo: str,
    *,
    config_file: Path | None,
    emit_candidates: bool,
    dependencies_only: bool,
    capabilities_only: bool,
    format_opt: str,
    json_output: bool,
) -> None:
    from devops_cli.dry_run.requests import render_request_plan

    planned = survey_requests(
        target_repo,
        config_file=config_file,
        emit_candidates=emit_candidates,
        dependencies_only=dependencies_only,
        capabilities_only=capabilities_only,
    )
    resolved_format = resolve_format(format_opt, json_output=json_output)
    if resolved_format != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(
            {"dry_run": True, "requests": [r.__dict__ for r in planned]}, resolved_format
        )
        return
    render_request_plan(f"Plan for survey ({target_repo})", planned)


@app.callback(invoke_without_command=True)
@dry_run_class("request-plan")
def survey_main(
    ctx: typer.Context,
    format_opt: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.survey.format),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help=HELP.survey.json),
    ] = False,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help=HELP.survey.config),
    ] = None,
    emit_candidates: Annotated[
        bool,
        typer.Option("--emit-candidates", help=HELP.survey.emit_candidates),
    ] = False,
    confirm: Annotated[
        bool,
        typer.Option("--confirm", help=HELP.survey.confirm),
    ] = False,
    repo: RepoOption = None,
    dependencies_only: Annotated[
        bool,
        typer.Option("--dependencies-only", help=HELP.survey.dependencies_only),
    ] = False,
    capabilities_only: Annotated[
        bool,
        typer.Option("--capabilities-only", help=HELP.survey.capabilities_only),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run outward-facing capability and upstream dependency maturity survey."""
    if ctx.invoked_subcommand is not None:
        return

    effective_dry_run = dry_run or is_dry_run()
    target_repo = repo or "dan-petty/devops-cli"

    if effective_dry_run:
        _render_survey_dry_run(
            target_repo,
            config_file=config_file,
            emit_candidates=emit_candidates,
            dependencies_only=dependencies_only,
            capabilities_only=capabilities_only,
            format_opt=format_opt,
            json_output=json_output,
        )
        return

    dependencies: list[DependencyMaturity] = []
    if not capabilities_only:
        dependencies = inspect_all_dependencies()

    comparisons: list[CapabilityComparison] = []
    gaps: list[CapabilityGap] = []
    if not dependencies_only:
        config = load_survey_config(config_file)
        comparisons = compare_capabilities(config)
        gaps = find_capability_gaps(comparisons)

        if emit_candidates:
            effective_confirm = confirm and not effective_dry_run
            emit_all_gaps_to_intake(
                gaps,
                repo=target_repo,
                confirm=effective_confirm,
            )

    report = SurveyReport(
        dependencies=dependencies,
        capabilities=comparisons,
        gaps=gaps,
        summary={
            "dependencies_count": len(dependencies),
            "capabilities_count": len(comparisons),
            "gaps_count": len(gaps),
        },
    )

    resolved_format = resolve_format(format_opt, json_output=json_output)
    if resolved_format != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.model_dump(), resolved_format)
        return

    if dependencies:
        _render_dependencies_table(dependencies)

    if comparisons:
        _render_capabilities_table(comparisons)

    if gaps:
        print_info(MESSAGES.survey.gaps_found.format(count=len(gaps)))
