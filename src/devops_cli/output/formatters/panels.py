"""Panel formatters and rich layout helpers."""

from __future__ import annotations

from typing import Any

from devops_cli.lang import MESSAGES
from devops_cli.output.formatters.scalars import (
    SEV_COLOR_MAP,
    format_finding_status_badge,
    format_review_recommendation,
)
from devops_cli.output.formatters.tables import (
    format_dependencies_table,
    format_network_references_table,
    format_review_findings_table,
)
from devops_cli.output.models import PanelPayload


def format_finding_panel(finding: Any, finding_index: int = 1) -> PanelPayload:
    """Build a structured PanelPayload with description and suggested remediation for a finding."""
    from devops_cli.output.console import escape_text

    sev = getattr(finding, "severity", "INFO")
    sev_upper = str(sev).upper()
    color = SEV_COLOR_MAP.get(sev_upper, "white")
    status_badge = format_finding_status_badge(
        getattr(finding, "status", ""),
        verified=getattr(finding, "verified", False),
        mitigated=getattr(finding, "mitigated", False),
    )
    title_str = getattr(finding, "title", "")
    title_header = f"[{color} bold]Finding #{finding_index}: [{sev_upper}] {escape_text(str(title_str))}[/{color} bold]  {status_badge}"
    loc_str = getattr(finding, "location", "-")
    panel_lines = [
        f"[bold]{MESSAGES.output.location_label}[/bold] [cyan]{escape_text(str(loc_str))}[/cyan]"
    ]
    desc = getattr(finding, "description", None)
    if desc:
        panel_lines.extend(
            ["", f"[bold]{MESSAGES.output.description_label}[/bold]", str(desc).strip()]
        )
    fix = getattr(finding, "fix", None)
    if fix:
        panel_lines.extend(
            ["", f"[bold]{MESSAGES.output.suggested_fix_label}[/bold]", str(fix).strip()]
        )
    references = getattr(finding, "references", None)
    if references:
        refs_list = references if isinstance(references, list) else [str(references)]
        refs_formatted = MESSAGES.output.references_label.format(
            refs=escape_text(", ".join(str(r) for r in refs_list))
        )
        panel_lines.extend(["", f"[dim]{refs_formatted}[/dim]"])
    return PanelPayload(
        content="\n".join(panel_lines),
        title=title_header,
        border_style=color,
    )


def render_review_result(persona: Any, result: Any) -> None:
    """Render a structured ReviewResult object using tables, panels, and Markdown blocks."""
    from devops_cli.output.console import escape_text, print, write_stdout
    from devops_cli.output.models import MarkdownPayload

    rec = getattr(result, "recommendation", "APPROVE")
    rec_badge = format_review_recommendation(str(rec))
    print(f"\u25b6 {rec_badge}\n", level="info", prefix=False)

    findings = getattr(result, "sorted_findings", None) or getattr(result, "findings", None)
    if findings:
        print(format_review_findings_table(findings))
        write_stdout("\n")
        for finding_index, finding in enumerate(findings, 1):
            print(format_finding_panel(finding, finding_index))
        write_stdout("\n")

    deps = getattr(result, "external_dependencies", None)
    if deps:
        print(format_dependencies_table(deps))
        write_stdout("\n")

    refs = getattr(result, "network_references", None)
    if refs:
        print(format_network_references_table(refs))
        write_stdout("\n")

    positive = getattr(result, "positive_observations", None)
    if positive:
        print(MESSAGES.review.positive_observations, level="info", prefix=False)
        for observation in positive:
            print(
                f"  [green]\u2713[/green] {escape_text(str(observation))}",
                level="info",
                prefix=False,
            )
        write_stdout("\n")

    summary = getattr(result, "summary", None)
    if summary:
        print(MESSAGES.review.summary, level="info", prefix=False)
        print(MarkdownPayload(content=str(summary)))


def render_review_raw(persona: Any, raw: str) -> None:
    """Render a raw string review response using Panel and Markdown."""
    from devops_cli.output.console import escape_text, print

    persona_title = getattr(persona, "title", str(persona))
    panel_payload = PanelPayload(
        content=raw,
        title=f"[bold cyan]{escape_text(str(persona_title))}[/bold cyan]",
        border_style="cyan",
    )
    print(panel_payload)


def format_argo_app_status_panel(
    name: str,
    sync_status: str,
    health_status: str,
    revision: str,
    error: str | None = None,
) -> PanelPayload:
    """Build a structured PanelPayload for ArgoCD application status."""
    if error:
        err_msg = MESSAGES.output.argo_error_fetching.format(error=error)
        return PanelPayload(content=f"[red]{err_msg}[/red]", title=name)
    sync_c = "green" if sync_status == "Synced" else "yellow"
    health_c = "green" if health_status == "Healthy" else "red"
    lines = [
        f"  [bold]{MESSAGES.output.argo_sync_label}[/bold]     [{sync_c}]{sync_status}[/{sync_c}]",
        f"  [bold]{MESSAGES.output.argo_health_label}[/bold]   [{health_c}]{health_status}[/{health_c}]",
        f"  [bold]{MESSAGES.output.argo_revision_label}[/bold] {revision}",
    ]
    return PanelPayload(content="\n".join(lines), title=f"[bold cyan]{name}[/bold cyan]")
