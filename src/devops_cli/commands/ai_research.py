"""Epistemic research, information foraging, and relational codebase exploration CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.ai.research.crawler import ForageCrawler
from devops_cli.ai.research.models import ForageTrail
from devops_cli.config.defaults import (
    DEFAULT_AI_FORAGE_MAX_NODES,
    DEFAULT_AI_FORAGE_MIN_SCORE,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_worktree_root
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import HELP
from devops_cli.output import (
    Panel,
    Table,
    get_console,
    print_error,
    render_dry_run_result,
    write_stdout,
)

app = new_typer(
    help=HELP.ai.research,
    no_args_is_help=True,
)


def _render_forage_trail_table(trail: ForageTrail) -> Table:
    table = Table(
        title=f"Information Foraging Trail: {trail.anchor} (query: '{trail.query}')",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Hop", justify="right", style="dim")
    table.add_column("Node Path", style="bold green")
    table.add_column("Scent Score", justify="right", style="magenta")
    table.add_column("Edge Type", style="yellow")
    table.add_column("Edge Detail", style="dim")

    for i, node in enumerate(trail.visited_nodes, start=1):
        table.add_row(
            str(i),
            node.path,
            f"{node.score:.3f}",
            node.edge_type or "anchor",
            node.detail,
        )
    return table


def _render_backtrack_table(trail: ForageTrail) -> Table:
    table = Table(
        title="Backtracking Decisions (Trail Grew Cold)",
        show_header=True,
        header_style="bold red",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("From Node", style="yellow")
    table.add_column("Backtracked To", style="cyan")
    table.add_column("Branch Score", justify="right", style="magenta")
    table.add_column("Min Threshold", justify="right", style="dim")

    for i, b in enumerate(trail.backtrack_events, start=1):
        table.add_row(
            str(i),
            b.from_node,
            b.to_node,
            f"{b.score:.3f}",
            f"{b.threshold:.3f}",
        )
    return table


def _display_forage_summary(trail: ForageTrail) -> None:
    console = get_console()
    console.print(
        Panel(
            f"[bold]Anchor:[/bold] {trail.anchor}\n"
            f"[bold]Query:[/bold] {trail.query}\n"
            f"[bold]Visited Nodes:[/bold] {len(trail.visited_nodes)}  |  "
            f"[bold]Edges Traversed:[/bold] {len(trail.edges)}  |  "
            f"[bold]Cycles Avoided:[/bold] {len(trail.cycles_detected)}  |  "
            f"[bold]Backtracks:[/bold] {len(trail.backtrack_events)}",
            title="[bold green]Information Foraging Summary[/bold green]",
            expand=False,
        )
    )
    console.print(_render_forage_trail_table(trail))
    if trail.backtrack_events:
        console.print(_render_backtrack_table(trail))


@app.command(name="forage")
def forage_cmd(
    anchor: Annotated[
        str,
        typer.Argument(
            help=HELP.ai.forage_anchor,
        ),
    ],
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help=HELP.ai.forage_query,
        ),
    ] = "",
    max_nodes: Annotated[
        int,
        typer.Option(
            "--max-nodes",
            "-n",
            help=HELP.ai.forage_max_nodes,
        ),
    ] = DEFAULT_AI_FORAGE_MAX_NODES,
    min_score: Annotated[
        float,
        typer.Option(
            "--min-score",
            "-s",
            help=HELP.ai.forage_min_score,
        ),
    ] = DEFAULT_AI_FORAGE_MIN_SCORE,
    repo: Annotated[
        Path | None,
        typer.Option(
            "--repo",
            "-R",
            help=HELP.options.repo,
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help=HELP.options.json_output,
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help=HELP.options.dry_run,
        ),
    ] = False,
) -> None:
    """Forage relational information trails across codebases using semantic scent."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ai research forage",
            action="forage_information_trail",
            details={
                "anchor": anchor,
                "query": query,
                "max_nodes": max_nodes,
                "min_score": min_score,
            },
        )
        return

    repo_root = repo.resolve() if repo is not None else None
    if repo_root is None and Path(anchor).exists():
        repo_root = find_worktree_root(Path(anchor).resolve().parent)

    crawler = ForageCrawler(repo_root=repo_root, max_nodes=max_nodes, min_score=min_score)
    try:
        trail = crawler.forage(anchor=anchor, query=query)
    except Exception as exc:
        print_error(f"Information foraging failed: {exc}")
        raise typer.Exit(code=1) from exc

    if json_output:
        write_stdout(trail.model_dump_json(indent=2))
    else:
        _display_forage_summary(trail)
