"""Epistemic research, information foraging, and relational codebase exploration CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from devops_cli.ai.research.crawler import ForageCrawler
from devops_cli.ai.research.marginalia import annotate_file, read_marginalia
from devops_cli.ai.research.models import (
    ForageTrail,
    MarginaliaRecord,
    SocraticInquiryResult,
)
from devops_cli.ai.research.socratic import (
    SocraticFormulator,
    render_socratic_markdown,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_FORAGE_MAX_NODES,
    DEFAULT_AI_FORAGE_MIN_SCORE,
    DEFAULT_AI_SOCRATIC_MAX_PROBES,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_repo_root, find_worktree_root
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


def _render_marginalia_table(records: list[MarginaliaRecord], title: str) -> Table:
    table = Table(
        title=title,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Type", style="bold yellow")
    table.add_column("Anchor", style="cyan")
    table.add_column("Created", style="dim")
    table.add_column("Content", style="green")

    for i, rec in enumerate(records, start=1):
        table.add_row(
            str(i),
            rec.type,
            rec.anchor,
            rec.created_at[:19].replace("T", " "),
            rec.content,
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

    for node in trail.visited_nodes:
        if node.marginalia:
            console.print(
                _render_marginalia_table(
                    node.marginalia,
                    f"Active Marginalia Surfaced for: {node.path}",
                )
            )


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


def _emit_marginalia_records(records: list[MarginaliaRecord], fmt: str, path: str) -> None:
    if fmt == "json":
        write_stdout(json.dumps([r.model_dump() for r in records], indent=2, ensure_ascii=False))
        return
    if fmt == "yaml":
        write_stdout(
            yaml.safe_dump([r.model_dump() for r in records], sort_keys=False, allow_unicode=True)
        )
        return

    console = get_console()
    if not records:
        console.print(f"[dim]No marginalia found for {path}.[/dim]")
    else:
        console.print(_render_marginalia_table(records, f"Marginalia Annotations: {path}"))


@app.command(name="annotate")
def annotate_cmd(
    path: Annotated[
        str,
        typer.Argument(
            help=HELP.ai.annotate_path,
        ),
    ],
    type: Annotated[
        str | None,
        typer.Option(
            "--type",
            "-t",
            help=HELP.ai.annotate_type,
        ),
    ] = None,
    content: Annotated[
        str | None,
        typer.Option(
            "--content",
            "-c",
            "--note",
            help=HELP.ai.annotate_content,
        ),
    ] = None,
    anchor: Annotated[
        str | None,
        typer.Option(
            "--anchor",
            "-a",
            help=HELP.ai.annotate_anchor,
        ),
    ] = None,
    list_only: Annotated[
        bool,
        typer.Option(
            "--list",
            "-l",
            help=HELP.ai.annotate_list,
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help=HELP.options.format_type,
        ),
    ] = "text",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help=HELP.options.dry_run,
        ),
    ] = False,
) -> None:
    """Record or view active marginalia annotations anchored to files, AST nodes, or ranges."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ai research annotate",
            action="record_or_read_marginalia",
            details={
                "path": path,
                "type": type,
                "content": content,
                "anchor": anchor,
                "list_only": list_only,
            },
        )
        return

    repo_root = find_worktree_root(Path.cwd()) or find_repo_root(Path.cwd())

    if not list_only:
        ann_type = type or "TODO"
        ann_content = content if content is not None else f"Inspect {Path(path).name}"
        try:
            annotate_file(
                file_path=path,
                type=ann_type,
                content=ann_content,
                anchor=anchor,
                repo_root=repo_root,
            )
        except ValueError as exc:
            print_error(str(exc))
            raise typer.Exit(code=1) from exc

    records = read_marginalia(path, repo_root=repo_root)
    _emit_marginalia_records(records, format.lower(), path)


def _render_socratic_gaps_table(result: SocraticInquiryResult) -> Table:
    table = Table(
        title="Identified Knowledge Gaps & Underspecified Contracts",
        show_header=True,
        header_style="bold red",
    )
    table.add_column("Type", style="bold yellow")
    table.add_column("Description", style="white")
    table.add_column("Rationale", style="dim")
    for gap in result.gaps:
        table.add_row(gap.type, gap.description, gap.rationale)
    return table


def _render_socratic_questions_table(result: SocraticInquiryResult) -> Table:
    table = Table(
        title="Targeted Clarifying Questions (Minimal Diagnostic Probes)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Question", style="bold green")
    table.add_column("Target Gap", style="yellow")
    table.add_column("Rationale", style="dim")
    for i, q in enumerate(result.questions, start=1):
        table.add_row(str(i), q.question, q.target_gap, q.rationale)
    return table


def _render_socratic_lookups_table(result: SocraticInquiryResult) -> Table:
    table = Table(
        title="Targeted Code Lookup Instructions",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Target", style="bold white")
    table.add_column("Target Gap", style="yellow")
    table.add_column("Rationale", style="dim")
    for i, lk in enumerate(result.lookups, start=1):
        table.add_row(str(i), lk.lookup_type, lk.target, lk.target_gap, lk.rationale)
    return table


def _display_socratic_summary(result: SocraticInquiryResult) -> None:
    console = get_console()
    summary_text = (
        f"[bold]Task:[/bold] {result.task}\n"
        f"[bold]Gaps Identified:[/bold] {len(result.gaps)}  |  "
        f"[bold]Clarifying Questions:[/bold] {len(result.questions)}  |  "
        f"[bold]Code Lookups:[/bold] {len(result.lookups)}"
    )
    if result.summary:
        summary_text += f"\n\n[bold]Metacognitive Summary:[/bold]\n{result.summary}"

    console.print(
        Panel(
            summary_text,
            title="[bold green]Socratic Metacognitive Analysis[/bold green]",
            expand=False,
        )
    )
    if result.gaps:
        console.print(_render_socratic_gaps_table(result))
    if result.questions:
        console.print(_render_socratic_questions_table(result))
    if result.lookups:
        console.print(_render_socratic_lookups_table(result))


def _emit_socratic_result(result: SocraticInquiryResult, fmt: str) -> None:
    if fmt == "json":
        write_stdout(result.model_dump_json(indent=2))
        return
    if fmt == "yaml":
        write_stdout(yaml.safe_dump(result.model_dump(), sort_keys=False, allow_unicode=True))
        return
    if fmt in ("markdown", "md"):
        write_stdout(render_socratic_markdown(result))
        return
    _display_socratic_summary(result)


@app.command(name="socratic")
def socratic_cmd(
    task: Annotated[
        str | None,
        typer.Argument(
            help=HELP.ai.socratic_task,
        ),
    ] = None,
    task_opt: Annotated[
        str | None,
        typer.Option(
            "--task",
            "-t",
            help=HELP.ai.socratic_task,
        ),
    ] = None,
    context: Annotated[
        str | None,
        typer.Option(
            "--context",
            "-c",
            help=HELP.ai.socratic_context,
        ),
    ] = None,
    max_probes: Annotated[
        int,
        typer.Option(
            "--max-probes",
            "-n",
            help=HELP.ai.socratic_max_probes,
        ),
    ] = DEFAULT_AI_SOCRATIC_MAX_PROBES,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help=HELP.options.format_type,
        ),
    ] = "text",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help=HELP.options.dry_run,
        ),
    ] = False,
) -> None:
    """Metacognitive Socratic inquiry identifying knowledge gaps, ambiguities, and probes."""
    effective_task = task_opt or task
    if not effective_task or not effective_task.strip():
        print_error("A task description must be provided via argument or --task.")
        raise typer.Exit(code=1)

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ai research socratic",
            action="formulate_socratic_inquiry",
            details={
                "task": effective_task,
                "context": context,
                "max_probes": max_probes,
                "format": format,
            },
        )
        return

    repo_root = find_worktree_root(Path.cwd()) or find_repo_root(Path.cwd())
    formulator = SocraticFormulator(max_probes=max_probes)
    try:
        result = formulator.formulate(
            task=effective_task,
            context=context,
            repo_root=repo_root,
        )
    except Exception as exc:
        print_error(f"Socratic inquiry failed: {exc}")
        raise typer.Exit(code=1) from exc

    _emit_socratic_result(result, format.lower())
