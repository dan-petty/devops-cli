"""Rich console table rendering and persona review UI layout formatters."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from devops_cli.ai.personas import PersonaDefinition
from devops_cli.ai.review_schema import ReviewResult

console = Console()


def _render_review_result(persona: PersonaDefinition, result: ReviewResult) -> None:
    """Render a structured ReviewResult object using Rich tables and Markdown blocks."""
    sev_color = {
        "CRITICAL": "red",
        "HIGH": "orange3",
        "MEDIUM": "yellow",
        "LOW": "blue",
        "INFO": "green",
    }
    rec_color_map = {"APPROVE": "green", "REQUEST CHANGES": "yellow", "BLOCK": "red"}
    rec_color = rec_color_map.get(result.recommendation, "white")
    console.print(f"[bold {rec_color}]\u25b6 {result.recommendation}[/bold {rec_color}]")
    console.print()

    findings = result.sorted_findings
    if findings:
        table = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 1))
        table.add_column("Sev", no_wrap=True)
        table.add_column("Location", style="dim")
        table.add_column("Title")
        table.add_column("\u2713", no_wrap=True)
        for f in findings:
            color = sev_color.get(f.severity, "white")
            mark = (
                "[green]✓[/green]"
                if f.verified and not f.mitigated
                else "[yellow]~[/yellow]"
                if f.mitigated
                else "[dim]?[/dim]"
            )
            table.add_row(f"[{color}]{f.severity}[/{color}]", f.location, f.title, mark)
        console.print(table)
        console.print()

        for idx, f in enumerate(findings, 1):
            color = sev_color.get(f.severity, "white")
            unverified = (
                ""
                if f.verified and not f.mitigated
                else " [dim](mitigated)[/dim]"
                if f.mitigated
                else " [dim](unverified)[/dim]"
            )
            console.print(
                f"[bold {color}]{idx}. {f.severity} \u2014 {f.title}[/bold {color}]{unverified}"
            )
            console.print(f"[dim]Location:[/dim] {f.location}")
            if f.description:
                console.print(Markdown(f.description))
            if f.fix:
                console.print("[bold]Fix:[/bold]")
                console.print(Markdown(f.fix))
            if f.references:
                console.print(f"[dim]References: {', '.join(f.references)}[/dim]")
            console.print()

    if result.positive_observations:
        console.print("[bold green]Positive Observations[/bold green]")
        for obs in result.positive_observations:
            console.print(f"  [green]\u2713[/green] {obs}")
        console.print()

    if result.summary:
        console.print("[bold]Summary[/bold]")
        console.print(Markdown(result.summary))


def _render_review_raw(persona: PersonaDefinition, raw: str) -> None:
    """Render a raw string response using Rich Panel and Markdown."""
    console.print(
        Panel(
            Markdown(raw),
            title=f"[bold cyan]{persona.title}[/bold cyan]",
            border_style="cyan",
        )
    )
