"""CLI commands to inspect harness slots, run local sub-agent offloading, and execute tiered synthesis."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP, MESSAGES

app = new_typer(
    help=HELP.ai_harness.app,
    no_args_is_help=True,
)


def _build_status_rows(harness: Any) -> list[list[str]]:
    """Build summary table rows for each harness slot."""
    return [
        [
            "ModelSlot",
            harness.model_slot.state.value,
            f"Provider: {harness.model_slot.provider} | Model: {harness.model_slot.model_name}",
        ],
        [
            "SkillSlot",
            harness.skill_slot.state.value,
            f"Active Skills: {len(harness.skill_slot.skills)}",
        ],
        [
            "ToolSlot",
            harness.tool_slot.state.value,
            f"Tools: {len(harness.tool_slot.tools)} (Read-Only: {harness.tool_slot.read_only})",
        ],
        [
            "SubAgentSlot",
            harness.subagent_slot.state.value,
            "Local AST, glob and symbol-catalog search (calls no model)",
        ],
    ]


@app.command(name="status")
def harness_status(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
) -> None:
    """Display the harness slots as configured; nothing here checks a model is reachable."""
    from devops_cli.ai.harness.slots import AgentHarness
    from devops_cli.output import format_json, print_table, write_stdout

    harness = AgentHarness.from_config()

    if output_format == "json":
        write_stdout(format_json(harness.to_dict()) + "\n")
        return

    rows = _build_status_rows(harness)
    print_table(
        title=MESSAGES.ai.harness_title,
        columns=[
            ("Slot Name", "cyan"),
            ("State", "bold green"),
            ("Configuration Details", "white"),
        ],
        rows=rows,
        box_style=None,
    )


def _extract_result_metrics(data: dict[str, Any]) -> tuple[int, int]:
    """Extract files scanned and match count from subagent data dictionary."""
    files_scanned = int(
        data.get(
            "files_scanned",
            data.get("file_count", len(data.get("files", []))),
        )
    )
    matches = 0
    for key in ("matches", "symbols", "files"):
        if key in data:
            matches = len(data[key])
            break
    return files_scanned, matches


def _render_offload_result(
    result: Any,
    output_format: str,
) -> None:
    """Render the sub-agent offload execution result."""
    from devops_cli.output import format_json, print_table, write_stdout

    files_scanned, matches = _extract_result_metrics(result.data)

    if output_format == "json":
        data = {
            "result": result.to_dict(),
        }
        write_stdout(format_json(data) + "\n")
        return

    rows = [
        ["Status", result.status],
        ["Files Scanned", str(files_scanned)],
        ["Matches", str(matches)],
        ["Output Summary", result.output],
    ]

    print_table(
        title=MESSAGES.ai.harness_offload_title,
        columns=[("Metric / Field", "cyan"), ("Value", "bold green")],
        rows=rows,
        box_style=None,
    )


@app.command(name="offload")
def harness_offload(
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help=HELP.ai_harness.repo),
    ] = Path("."),
    symbol: Annotated[
        str | None,
        typer.Option("--symbol", "-s", help=HELP.ai_harness.symbol),
    ] = None,
    pattern: Annotated[
        str | None,
        typer.Option("--pattern", "-p", help=HELP.ai_harness.pattern),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Offload AST exploration, symbol cataloging, or file scouting to local sub-agent slot."""
    from devops_cli.ai.harness.slots import AgentHarness
    from devops_cli.dry_run import is_dry_run, render_dry_run_result

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ai harness offload",
            action="subagent_offload",
            details={
                "repo": str(repo),
                "symbol": symbol,
                "pattern": pattern,
            },
        )
        return

    harness = AgentHarness.from_config()
    subagent = harness.subagent_slot

    if symbol:
        res = subagent.offload_ast_search(repo, symbol)
    elif pattern:
        res = subagent.offload_file_scout(repo, pattern)
    else:
        res = subagent.offload_symbol_catalog(repo)

    _render_offload_result(res, output_format)


@app.command(name="run")
def harness_run(
    task: Annotated[
        str,
        typer.Argument(help="Task description to execute via 3-tier synthesis protocol"),
    ],
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help=HELP.ai_harness.repo),
    ] = Path("."),
    symbol: Annotated[
        str | None,
        typer.Option("--symbol", "-s", help=HELP.ai_harness.symbol),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Run the sub-agent's local AST or glob search for a task and report what it found."""
    from devops_cli.ai.harness.slots import AgentHarness
    from devops_cli.dry_run import is_dry_run, render_dry_run_result
    from devops_cli.output import format_json, print_table, write_stdout

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ai harness run",
            action="execute_tiered_synthesis",
            details={
                "task": task,
                "repo": str(repo),
                "symbol": symbol,
            },
        )
        return

    harness = AgentHarness.from_config()
    result = harness.execute_tiered(task=task, repo_path=repo, symbol_query=symbol)

    if output_format == "json":
        write_stdout(format_json(result.to_dict()) + "\n")
        return

    rows = [
        ["Task", result.task],
        ["Search", result.search],
        ["Status", result.status],
        ["Files Scanned", str(result.files_scanned)],
        ["Matches", str(result.matches)],
        ["Summary", result.summary],
    ]

    print_table(
        title="Harness Run",
        columns=[("Phase / Output", "cyan"), ("Result", "bold green")],
        rows=rows,
        box_style=None,
    )
