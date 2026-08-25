"""Rich console table rendering and persona review UI layout formatters."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
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
    console.print(f"[bold {rec_color}]\u25b6 {escape(result.recommendation)}[/bold {rec_color}]")
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
            table.add_row(
                f"[{color}]{escape(f.severity)}[/{color}]",
                escape(f.location),
                escape(f.title),
                mark,
            )
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
            sev_title = f"{idx}. {escape(f.severity)} — {escape(f.title)}"
            console.print(f"[bold {color}]{sev_title}[/bold {color}]{unverified}")
            console.print(f"[dim]Location:[/dim] {escape(f.location)}")
            if f.description:
                console.print(Markdown(f.description))
            if f.fix:
                console.print("[bold]Fix:[/bold]")
                console.print(Markdown(f.fix))
            if f.references:
                console.print(f"[dim]References: {escape(', '.join(f.references))}[/dim]")
            console.print()

    if result.external_dependencies:
        dep_tbl = Table(title="External Dependencies Security Audit (OSV.dev & NVD)")
        dep_tbl.add_column("Severity", justify="center", no_wrap=True)
        dep_tbl.add_column("Dependency", style="bold cyan")
        dep_tbl.add_column("Version Range")
        dep_tbl.add_column("Ecosystem")
        dep_tbl.add_column("Security Status")
        dep_tbl.add_column("Location", style="dim")
        for d in result.external_dependencies:
            sev_upper = d.severity.upper()
            if sev_upper == "CRITICAL":
                sev_str = "[bold red]CRITICAL[/bold red]"
                status_str = f"[bold red]{d.security_status}[/bold red]"
            elif sev_upper == "HIGH":
                sev_str = "[red]HIGH[/red]"
                status_str = f"[red]{d.security_status}[/red]"
            elif sev_upper == "MEDIUM":
                sev_str = "[yellow]MEDIUM[/yellow]"
                status_str = f"[yellow]{d.security_status}[/yellow]"
            elif sev_upper == "LOW":
                sev_str = "[cyan]LOW[/cyan]"
                status_str = f"[cyan]{d.security_status}[/cyan]"
            else:
                sev_str = "[green]CLEAN[/green]"
                status_str = f"[green]{d.security_status}[/green]"

            dep_tbl.add_row(
                sev_str,
                d.name,
                d.version_range,
                d.ecosystem,
                status_str,
                d.location or "—",
            )
        console.print(dep_tbl)
        console.print()

    if result.network_references:
        net_tbl = Table(
            title="Network References & Endpoints Security Audit (Shodan & Cloudflare Radar)"
        )
        net_tbl.add_column("Target", style="bold cyan")
        net_tbl.add_column("Type")
        net_tbl.add_column("Scope")
        net_tbl.add_column("Security Status")
        net_tbl.add_column("Location", style="dim")
        for n in result.network_references:
            scope_str = "[dim]Local[/dim]" if n.is_local else "[bold cyan]External[/bold cyan]"
            color = "red" if "⚠️" in n.security_status else ("cyan" if n.is_local else "green")
            net_tbl.add_row(
                n.target,
                n.reference_type,
                scope_str,
                f"[{color}]{n.security_status}[/{color}]",
                n.location or "—",
            )
        console.print(net_tbl)
        console.print()

    if result.positive_observations:
        console.print("[bold green]Positive Observations[/bold green]")
        for obs in result.positive_observations:
            console.print(f"  [green]\u2713[/green] {escape(obs)}")
        console.print()

    if result.summary:
        console.print("[bold]Summary[/bold]")
        console.print(Markdown(result.summary))


def _render_review_raw(persona: PersonaDefinition, raw: str) -> None:
    """Render a raw string response using Rich Panel and Markdown."""
    console.print(
        Panel(
            Markdown(raw),
            title=f"[bold cyan]{escape(persona.title)}[/bold cyan]",
            border_style="cyan",
        )
    )
