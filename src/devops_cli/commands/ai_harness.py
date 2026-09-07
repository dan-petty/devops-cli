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
            f"Model: {harness.model_slot.model_name} (Local: {harness.model_slot.is_local})",
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
            (
                f"Model: {harness.subagent_slot.model_slot.model_name} | "
                f"Read-Only: {harness.subagent_slot.tool_slot.read_only}"
            ),
        ],
    ]


@app.command(name="status")
def harness_status(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
) -> None:
    """Display active harness slot configuration, models, and sandboxing status."""
    from devops_cli.ai.harness.slots import AgentHarness
    from devops_cli.output import format_json, print_table, write_stdout

    harness = AgentHarness.create_default()

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


def _render_offload_result(
    result: Any,
    output_format: str,
) -> None:
    """Render the sub-agent offload execution result."""
    from devops_cli.ai.harness.slots import TokenSavingsSummary
    from devops_cli.output import format_json, print_table, write_stdout

    savings = TokenSavingsSummary.calculate(
        frontier_tokens=25,
        offloaded_tokens=result.tokens_used,
    )

    if output_format == "json":
        data = {
            "result": result.to_dict(),
            "savings": savings.to_dict(),
        }
        write_stdout(format_json(data) + "\n")
        return

    rows = [
        ["Status", result.status],
        ["Tokens Used", str(result.tokens_used)],
        ["Output Summary", result.output],
        [
            "Token Savings",
            f"{savings.savings_percentage:.1f}% (target met: {savings.is_target_met})",
        ],
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

    harness = AgentHarness.create_default()
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
    frontier_model: Annotated[
        str,
        typer.Option("--frontier-model", help=HELP.ai_harness.frontier_model),
    ] = "claude-3-7-sonnet",
    local_model: Annotated[
        str,
        typer.Option("--local-model", help=HELP.ai_harness.local_model),
    ] = "qwen2.5-coder:7b",
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Execute tiered synthesis: Big decides, small types, big checks."""
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
                "frontier_model": frontier_model,
                "local_model": local_model,
            },
        )
        return

    harness = AgentHarness.create_default(
        frontier_model=frontier_model,
        local_model=local_model,
    )
    result = harness.execute_tiered(task=task, repo_path=repo, symbol_query=symbol)

    if output_format == "json":
        write_stdout(format_json(result.to_dict()) + "\n")
        return

    rows = [
        ["Task", result.task],
        ["Status", result.status],
        ["Tier 1 (Big Decides)", result.decision_plan],
        ["Tier 2 (Small Types)", f"{len(result.subagent_results)} offloaded task(s) executed"],
        ["Tier 3 (Big Checks)", result.verification_report],
        [
            "Token Savings",
            f"{result.savings.savings_percentage:.1f}% (target met: {result.savings.is_target_met})",
        ],
    ]

    print_table(
        title="Tiered Synthesis Execution",
        columns=[("Phase / Output", "cyan"), ("Result", "bold green")],
        rows=rows,
        box_style=None,
    )
