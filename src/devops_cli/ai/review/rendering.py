"""Rich console table rendering and persona review UI layout formatters."""

from __future__ import annotations

from devops_cli.ai.personas import PersonaDefinition
from devops_cli.ai.review_schema import ReviewResult
from devops_cli.output import (
    escape_text,
    print_info,
    print_markdown,
    print_panel,
    print_table,
    write_stdout,
)


def _render_review_result(persona: PersonaDefinition, result: ReviewResult) -> None:
    """Render a structured ReviewResult object using tables and Markdown blocks."""
    sev_color = {
        "CRITICAL": "red",
        "HIGH": "orange3",
        "MEDIUM": "yellow",
        "LOW": "blue",
        "INFO": "green",
    }
    rec_color_map = {"APPROVE": "green", "REQUEST CHANGES": "yellow", "BLOCK": "red"}
    rec_color = rec_color_map.get(result.recommendation, "white")
    print_info(
        f"[bold {rec_color}]\u25b6 {escape_text(result.recommendation)}[/bold {rec_color}]\n",
        prefix=False,
    )

    findings = result.sorted_findings
    if findings:
        columns = [
            "Sev",
            ("Location", "dim"),
            "Title",
            "\u2713",
        ]
        rows: list[list[str]] = []
        for f in findings:
            color = sev_color.get(f.severity, "white")
            mark = (
                "[green]✓[/green]"
                if f.verified and not f.mitigated
                else "[yellow]~[/yellow]"
                if f.mitigated
                else "[dim]?[/dim]"
            )
            rows.append(
                [
                    f"[{color}]{escape_text(f.severity)}[/{color}]",
                    escape_text(f.location),
                    escape_text(f.title),
                    mark,
                ]
            )
        print_table(columns=columns, rows=rows, border_style=None)
        write_stdout("\n")

        for idx, f in enumerate(findings, 1):
            sev_upper = f.severity.upper()
            color = sev_color.get(sev_upper, "white")
            st_badge = (
                "[green]✓ VERIFIED[/green]"
                if f.verified and not f.mitigated
                else ("[cyan]~ MITIGATED[/cyan]" if f.mitigated else "[dim]? UNVERIFIED[/dim]")
            )
            title_header = f"[{color} bold]Finding #{idx}: [{sev_upper}] {escape_text(f.title)}[/{color} bold]  {st_badge}"
            panel_lines = [
                f"[bold]Location:[/bold] [cyan]{escape_text(f.location)}[/cyan]",
            ]
            if f.description:
                panel_lines.extend(["", "[bold]Description:[/bold]", f.description.strip()])
            if f.fix:
                panel_lines.extend(["", "[bold]Suggested Fix:[/bold]", f.fix.strip()])
            if f.references:
                panel_lines.extend(
                    ["", f"[dim]References: {escape_text(', '.join(f.references))}[/dim]"]
                )
            print_panel(
                "\n".join(panel_lines),
                title=title_header,
                border_style=color,
            )
        write_stdout("\n")

    if result.external_dependencies:
        dep_cols = [
            "Severity",
            ("Dependency", "bold cyan"),
            "Version Range",
            "Ecosystem",
            "Security Status",
            ("Location", "dim"),
        ]
        dep_rows: list[list[str]] = []
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

            dep_rows.append(
                [
                    sev_str,
                    d.name,
                    d.version_range,
                    d.ecosystem,
                    status_str,
                    d.location or "—",
                ]
            )
        print_table(
            title="External Dependencies Security Audit (OSV.dev & NVD)",
            columns=dep_cols,
            rows=dep_rows,
        )
        write_stdout("\n")

    if result.network_references:
        net_cols = [
            ("Target", "bold cyan"),
            "Type",
            "Scope",
            "Security Status",
            ("Location", "dim"),
        ]
        net_rows: list[list[str]] = []
        for n in result.network_references:
            scope_str = "[dim]Local[/dim]" if n.is_local else "[bold cyan]External[/bold cyan]"
            color = "red" if "⚠️" in n.security_status else ("cyan" if n.is_local else "green")
            net_rows.append(
                [
                    n.target,
                    n.reference_type,
                    scope_str,
                    f"[{color}]{n.security_status}[/{color}]",
                    n.location or "—",
                ]
            )
        print_table(
            title="Network References & Endpoints Security Audit (Shodan & Cloudflare Radar)",
            columns=net_cols,
            rows=net_rows,
        )
        write_stdout("\n")

    if result.positive_observations:
        print_info("[bold green]Positive Observations[/bold green]", prefix=False)
        for obs in result.positive_observations:
            print_info(f"  [green]\u2713[/green] {escape_text(obs)}", prefix=False)
        write_stdout("\n")

    if result.summary:
        print_info("[bold]Summary[/bold]", prefix=False)
        print_markdown(result.summary)


def _render_review_raw(persona: PersonaDefinition, raw: str) -> None:
    """Render a raw string response using Panel and Markdown."""
    print_panel(
        raw,
        title=f"[bold cyan]{escape_text(persona.title)}[/bold cyan]",
        border_style="cyan",
    )
