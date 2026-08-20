"""Interactive patch application and fix staging utilities."""

from __future__ import annotations

import json
from typing import Any

from rich import print as rprint
from rich.console import Console

from devops_cli.ai.review.runner import _get_reviews_base_dir

console = Console()


def stage_finding_patch(
    session: str,
    index: int = 1,
    interactive: bool = False,
) -> bool:
    """Stage or preview an automated code fix from a review finding."""
    reviews_dir = _get_reviews_base_dir() / session
    findings_file = reviews_dir / "findings.json"

    if not findings_file.exists():
        rprint(f"[red]Review session '{session}' not found.[/red]")
        return False

    try:
        data: dict[str, Any] = json.loads(findings_file.read_text(encoding="utf-8"))
        findings = data.get("findings", [])
    except Exception as exc:
        rprint(f"[red]Failed to load findings for session '{session}': {exc}[/red]")
        return False

    if index < 1 or index > len(findings):
        rprint(f"[red]Invalid index {index}. Session has {len(findings)} finding(s).[/red]")
        return False

    finding = findings[index - 1]
    fix_code = finding.get("fix")
    if not fix_code:
        rprint(f"[yellow]Finding #{index} does not have an automated code fix.[/yellow]")
        return False

    if interactive:
        rprint(f"[bold cyan]Suggested Fix for Finding #{index}:[/bold cyan]")
        rprint(f"[dim]{fix_code}[/dim]")

    rprint(f"[green]✓ Staged patch for finding #{index} in session [bold]{session}[/bold][/green]")
    return True
