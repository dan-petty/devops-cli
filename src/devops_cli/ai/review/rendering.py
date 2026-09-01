"""Rich console table rendering and persona review UI layout formatters."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.personas import PersonaDefinition
from devops_cli.ai.review_schema import ReviewResult, format_clean_text_field
from devops_cli.output import (
    MarkdownPayload,
    PanelPayload,
    TableColumn,
    TablePayload,
    escape_text,
    print,
    write_stdout,
)

SEV_COLOR_MAP: dict[str, str] = {
    "CRITICAL": "red",
    "HIGH": "orange3",
    "MEDIUM": "yellow",
    "LOW": "blue",
    "INFO": "green",
}

RECOMMENDATION_COLOR_MAP: dict[str, str] = {
    "APPROVE": "green",
    "REQUEST CHANGES": "yellow",
    "BLOCK": "red",
}


def _render_findings_table(findings: list[Any]) -> None:
    """Render compact tabular view of review findings."""
    columns: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Sev"),
        TableColumn(header="Location", style="dim"),
        TableColumn(header="Title"),
        TableColumn(header="✓"),
    ]
    rows: list[list[str]] = []
    for finding in findings:
        color = SEV_COLOR_MAP.get(finding.severity, "white")
        mark = (
            "[green]✓[/green]"
            if finding.verified and not finding.mitigated
            else "[yellow]~[/yellow]"
            if finding.mitigated
            else "[dim]?[/dim]"
        )
        rows.append(
            [
                f"[{color}]{escape_text(finding.severity)}[/{color}]",
                escape_text(finding.location),
                escape_text(finding.title),
                mark,
            ]
        )
    table_payload = TablePayload(columns=columns, rows=rows, border_style=None)
    print(table_payload)
    write_stdout("\n")


def _render_finding_panels(findings: list[Any]) -> None:
    """Render expanded Rich panels with description and remediation for findings."""
    for finding_index, finding in enumerate(findings, 1):
        sev_upper = finding.severity.upper()
        color = SEV_COLOR_MAP.get(sev_upper, "white")
        status_badge = (
            "[green]✓ VERIFIED[/green]"
            if finding.verified and not finding.mitigated
            else ("[cyan]~ MITIGATED[/cyan]" if finding.mitigated else "[dim]? UNVERIFIED[/dim]")
        )
        title_header = f"[{color} bold]Finding #{finding_index}: [{sev_upper}] {escape_text(finding.title)}[/{color} bold]  {status_badge}"
        panel_lines = [f"[bold]Location:[/bold] [cyan]{escape_text(finding.location)}[/cyan]"]
        if finding.description:
            panel_lines.extend(
                [
                    "",
                    "[bold]Description:[/bold]",
                    format_clean_text_field(finding.description).strip(),
                ]
            )
        if finding.fix:
            panel_lines.extend(
                ["", "[bold]Suggested Fix:[/bold]", format_clean_text_field(finding.fix).strip()]
            )
        if finding.references:
            refs_list = (
                finding.references
                if isinstance(finding.references, list)
                else [str(finding.references)]
            )
            panel_lines.extend(["", f"[dim]References: {escape_text(', '.join(refs_list))}[/dim]"])
        panel_payload = PanelPayload(
            content="\n".join(panel_lines),
            title=title_header,
            border_style=color,
        )
        print(panel_payload)
    write_stdout("\n")


def _render_dependencies_table(deps: list[Any]) -> None:
    """Render external dependencies audit table."""
    dep_cols: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Severity"),
        TableColumn(header="Dependency", style="bold cyan"),
        TableColumn(header="Version Range"),
        TableColumn(header="Ecosystem"),
        TableColumn(header="Security Status"),
        TableColumn(header="Location", style="dim"),
    ]
    dep_rows: list[list[str]] = []
    for dependency in deps:
        sev_upper = dependency.severity.upper()
        color = SEV_COLOR_MAP.get(sev_upper, "green")
        dep_rows.append(
            [
                f"[{color}]{sev_upper}[/{color}]",
                escape_text(getattr(dependency, "name", str(dependency))),
                escape_text(getattr(dependency, "version_range", "any")),
                escape_text(getattr(dependency, "ecosystem", "-")),
                f"[{color}]{escape_text(getattr(dependency, 'security_status', 'Clean'))}[/{color}]",
                escape_text(getattr(dependency, "location", "-")),
            ]
        )
    table_payload = TablePayload(
        title="[bold yellow]External Dependencies Audit[/bold yellow]",
        columns=dep_cols,
        rows=dep_rows,
    )
    print(table_payload)
    write_stdout("\n")


def _render_network_references_table(refs: list[Any]) -> None:
    """Render network and external egress references audit table."""
    net_cols: list[TableColumn | str | tuple[str, str | int]] = [
        TableColumn(header="Status"),
        TableColumn(header="Target / Reference", style="bold cyan"),
        TableColumn(header="Type"),
        TableColumn(header="Scope"),
        TableColumn(header="Location", style="dim"),
    ]
    net_rows: list[list[str]] = []
    for network_reference in refs:
        scope_str = (
            "[dim]Local[/dim]"
            if getattr(network_reference, "is_local", False)
            else "[bold cyan]External[/bold cyan]"
        )
        status_val = getattr(network_reference, "security_status", "Safe")
        color = "red" if "⚠️" in status_val or "RISK" in status_val.upper() else "green"
        net_rows.append(
            [
                f"[{color}]{escape_text(status_val)}[/{color}]",
                escape_text(getattr(network_reference, "target", str(network_reference))),
                escape_text(getattr(network_reference, "reference_type", "domain")),
                scope_str,
                escape_text(getattr(network_reference, "location", "-")),
            ]
        )
    table_payload = TablePayload(
        title="[bold yellow]Network & Egress References Audit[/bold yellow]",
        columns=net_cols,
        rows=net_rows,
    )
    print(table_payload)
    write_stdout("\n")


def _render_review_result(persona: PersonaDefinition, result: ReviewResult) -> None:
    """Render a structured ReviewResult object using tables and Markdown blocks."""
    rec_color = RECOMMENDATION_COLOR_MAP.get(result.recommendation, "white")
    print(
        f"[bold {rec_color}]\u25b6 {escape_text(result.recommendation)}[/bold {rec_color}]\n",
        level="info",
        prefix=False,
    )

    if result.sorted_findings:
        _render_findings_table(result.sorted_findings)
        _render_finding_panels(result.sorted_findings)

    if result.external_dependencies:
        _render_dependencies_table(result.external_dependencies)

    if result.network_references:
        _render_network_references_table(result.network_references)

    if result.positive_observations:
        print("[bold green]Positive Observations[/bold green]", level="info", prefix=False)
        for observation in result.positive_observations:
            print(f"  [green]\u2713[/green] {escape_text(observation)}", level="info", prefix=False)
        write_stdout("\n")

    if result.summary:
        print("[bold]Summary[/bold]", level="info", prefix=False)
        print(MarkdownPayload(content=result.summary))


def _render_review_raw(persona: PersonaDefinition, raw: str) -> None:
    """Render a raw string response using Panel and Markdown."""
    panel_payload = PanelPayload(
        content=raw,
        title=f"[bold cyan]{escape_text(persona.title)}[/bold cyan]",
        border_style="cyan",
    )
    print(panel_payload)
