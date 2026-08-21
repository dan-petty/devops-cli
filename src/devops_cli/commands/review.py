"""AI Code Review CLI command group (branch, path, PR, findings, verify, stats)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from devops_cli.ai.personas import Persona
from devops_cli.ai.review.chunker import (
    _diff_pages,
    _extract_code_lines,
    _extract_diff_filenames,
    _extract_path_filenames,
    _extract_segment_filenames,
    _find_repo_files,
    _is_generated_diff_block,
    _paginate_file_diff_block,
    _render_source_block,
    _split_diff_into_file_blocks,
    _split_source_file_blocks,
    _split_text_lines,
)
from devops_cli.ai.review.exporter import export_invalidated_feedback
from devops_cli.ai.review.patching import stage_finding_patch
from devops_cli.ai.review.runner import (
    ReviewClients,
    _build_path_prompt,
    _build_recompose_prompt,
    _build_segment_review_prompt,
    _collect_file_blocks,
    _collect_files,
    _debug_block,
    _detect_base_branch,
    _execute_review_workflow,
    _fallback_join,
    _find_session_dir,
    _get_reviews_base_dir,
    _git_repo_root,
    _is_allowed_review_boundary,
    _is_git_ignored,
    _llm_request_preview,
    _load_agents_md,
    _make_review_clients,
    _persona_format_section,
    _persona_system_prompt,
    _personas_to_run,
    _prepare_branch_content,
    _prepare_path_content,
    _prepare_pr_content,
    _print_analysis_metadata,
    _print_review,
    _resolve_review_clients,
    _review_session_dir,
    _review_to_markdown,
    _run_persona_loop,
    _run_review,
    _save_findings_json,
    _save_persona_review,
    _save_segments,
    _write_summary,
)
from devops_cli.ai.review.sanitization import (
    _build_prompt,
    _mask_secrets_in_content,
    _sanitize_filename,
    _sanitize_prompt_boundary_tags,
    _truncate_for_prompt,
    _unique_preserve_order,
)
from devops_cli.ai.review.verification import (
    _build_validation_prompt,
    _extract_location_context,
    _find_related_file_metas,
    _match_dep_to_filepath,
    _merge_segment_results,
    _reconcile_verified,
    _validate_segment_findings,
)
from devops_cli.ai.review_schema import (
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
)
from devops_cli.config.constants import (
    CONST_DATA_DIR,
    CONST_REVIEWS_DATA_DIR,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, set_dry_run

__all__ = [
    "app",
    "ReviewClients",
    "Finding",
    "ReviewResult",
    "ReviewSessionPayload",
    "SavedFinding",
    "CONST_DATA_DIR",
    "CONST_REVIEWS_DATA_DIR",
    "_diff_pages",
    "_extract_code_lines",
    "_extract_diff_filenames",
    "_extract_path_filenames",
    "_extract_segment_filenames",
    "_find_repo_files",
    "_is_generated_diff_block",
    "_paginate_file_diff_block",
    "_render_source_block",
    "_split_diff_into_file_blocks",
    "_split_source_file_blocks",
    "_split_text_lines",
    "export_invalidated_feedback",
    "stage_finding_patch",
    "_build_path_prompt",
    "_build_recompose_prompt",
    "_build_segment_review_prompt",
    "_collect_file_blocks",
    "_collect_files",
    "_debug_block",
    "_detect_base_branch",
    "_execute_review_workflow",
    "_fallback_join",
    "_find_session_dir",
    "_get_reviews_base_dir",
    "_git_repo_root",
    "_is_allowed_review_boundary",
    "_is_git_ignored",
    "_llm_request_preview",
    "_load_agents_md",
    "_make_review_clients",
    "_persona_format_section",
    "_persona_system_prompt",
    "_personas_to_run",
    "_prepare_branch_content",
    "_prepare_path_content",
    "_prepare_pr_content",
    "_print_analysis_metadata",
    "_print_review",
    "_resolve_review_clients",
    "_review_session_dir",
    "_review_to_markdown",
    "_run_persona_loop",
    "_run_review",
    "_save_findings_json",
    "_save_persona_review",
    "_save_segments",
    "_write_summary",
    "_build_prompt",
    "_mask_secrets_in_content",
    "_sanitize_filename",
    "_sanitize_prompt_boundary_tags",
    "_truncate_for_prompt",
    "_unique_preserve_order",
    "_build_validation_prompt",
    "_extract_location_context",
    "_find_related_file_metas",
    "_match_dep_to_filepath",
    "_merge_segment_results",
    "_reconcile_verified",
    "_validate_segment_findings",
    "load_settings",
    "is_dry_run",
    "set_dry_run",
]

app = new_typer(
    help="AI Code Review across branches, paths, and pull requests.", no_args_is_help=True
)
console = Console()


# ── path ──────────────────────────────────────────────────────────────────────


@app.command()
def path(
    target: Annotated[
        Path,
        typer.Argument(help="File or directory to review"),
    ] = Path("."),
    pattern: Annotated[
        str,
        typer.Option("--pattern", "-g", help="Glob pattern for files (default: all files)"),
    ] = "*",
    persona: Annotated[
        Persona | None,
        typer.Option("--persona", "-p", help="Reviewer persona"),
    ] = None,
    all_personas: Annotated[
        bool,
        typer.Option("--all", help="Run all four reviewer personas"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print commands and AI request payloads without executing."),
    ] = False,
    summary: Annotated[
        bool,
        typer.Option(
            "--summary", "-s", help="Show segment metadata without running a full review."
        ),
    ] = False,
) -> None:
    """Review source files directly (no git required)."""
    set_dry_run(dry_run)
    settings = load_settings()
    clients = _make_review_clients(settings)
    pages, title, agents_md = _prepare_path_content(target, pattern)
    _execute_review_workflow(
        pages,
        title,
        _build_path_prompt,
        agents_md,
        all_personas,
        persona,
        summary,
        clients,
        target_type="path",
        target_ref=str(target),
        target_dir=target,
    )


# ── branch ────────────────────────────────────────────────────────────────────


@app.command()
def branch(
    branch_name: Annotated[
        str | None,
        typer.Argument(help="Branch to review (default: current branch)"),
    ] = None,
    base: Annotated[
        str,
        typer.Option("--base", "-b", help="Base branch to diff against"),
    ] = "main",
    persona: Annotated[
        Persona | None,
        typer.Option("--persona", "-p", help="Reviewer persona"),
    ] = None,
    all_personas: Annotated[
        bool,
        typer.Option("--all", help="Run all four reviewer personas"),
    ] = False,
    repo_path: Annotated[
        Path,
        typer.Option("--repo", help="Path to the git repository"),
    ] = Path("."),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print commands and AI request payloads without executing."),
    ] = False,
    summary: Annotated[
        bool,
        typer.Option(
            "--summary", "-s", help="Show segment metadata without running a full review."
        ),
    ] = False,
) -> None:
    """Review a git branch diff with one or all AI personas."""
    set_dry_run(dry_run)
    settings = load_settings()
    clients = _make_review_clients(settings)
    pages, title, agents_md = _prepare_branch_content(branch_name, base, repo_path)
    _execute_review_workflow(
        pages,
        title,
        _build_prompt,
        agents_md,
        all_personas,
        persona,
        summary,
        clients,
        target_type="branch",
        target_ref=str(branch_name or "active"),
        target_dir=repo_path,
    )


# ── pr ────────────────────────────────────────────────────────────────────────


@app.command()
def pr(
    number: Annotated[int, typer.Argument(help="Pull request number")],
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-r", help="owner/repo (default: detected from git remote)"),
    ] = None,
    persona: Annotated[
        Persona | None,
        typer.Option("--persona", "-p", help="Reviewer persona"),
    ] = None,
    all_personas: Annotated[
        bool,
        typer.Option("--all", help="Run all four reviewer personas"),
    ] = False,
    post_comment: Annotated[
        bool,
        typer.Option("--post", help="Post the review as a comment on the GitHub PR"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print commands and AI request payloads without executing."),
    ] = False,
    summary: Annotated[
        bool,
        typer.Option(
            "--summary", "-s", help="Show segment metadata without running a full review."
        ),
    ] = False,
) -> None:
    """Review a GitHub pull request with one or all AI personas."""
    from devops_cli.config.settings import get_github_token

    set_dry_run(dry_run)
    settings = load_settings()
    token = get_github_token(settings)
    if not token:
        rprint(
            "[red]GitHub token not configured. Run: devops config set github.token <token>[/red]"
        )
        raise typer.Exit(1)

    clients = _make_review_clients(settings)
    pages, title, agents_md, pull, repo_name = _prepare_pr_content(number, repo, token)
    reviews = _execute_review_workflow(
        pages,
        title,
        _build_prompt,
        agents_md,
        all_personas,
        persona,
        summary,
        clients,
        target_type="pr",
        target_ref=str(number),
        target_dir=Path.cwd(),
    )

    if post_comment and reviews:
        sections = "\n\n---\n\n".join(
            f"## Review by {pd.title}\n\n{_review_to_markdown(text)}" for pd, text in reviews
        )
        comment_body = f"## 🤖 AI Code Review\n\n{sections}"
        if is_dry_run():
            from devops_cli.ai.review.runner import _debug_block

            _debug_block(
                f"Would post PR comment on #{number}",
                {"repo": repo_name, "pr_number": number, "comment_body": comment_body},
            )
            rprint(f"\n[yellow][dry-run][/yellow] Skipped posting comment to PR #{number}")
            return
        pull.create_issue_comment(comment_body)
        rprint(f"\n[green]✓[/green] Review posted as comment on PR #{number}")


# ── Verification & Invalidation Commands ─────────────────────────────────────


@app.command("findings")
def list_findings(
    session: Annotated[
        str | None,
        typer.Option("--session", "-s", help="Session ID or substring (default: latest)"),
    ] = None,
    status_filter: Annotated[
        str | None,
        typer.Option(
            "--status", help="Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED"
        ),
    ] = None,
    unverified: Annotated[
        bool, typer.Option("--unverified", help="Show unverified findings only")
    ] = False,
    invalidated: Annotated[
        bool, typer.Option("--invalidated", help="Show invalidated findings only")
    ] = False,
    verified: Annotated[
        bool, typer.Option("--verified", help="Show verified findings only")
    ] = False,
) -> None:
    """Inspect structured findings for a review session."""
    session_dir = _find_session_dir(session)
    if not session_dir:
        rprint("[yellow]No review sessions found in .data/reviews/[/yellow]")
        raise typer.Exit(0)

    findings_file = session_dir / "findings.json"
    if not findings_file.exists():
        rprint(f"[yellow]No findings.json in session {session_dir.name}[/yellow]")
        raise typer.Exit(0)

    payload = ReviewSessionPayload.model_validate_json(findings_file.read_text(encoding="utf-8"))
    findings = payload.findings

    target_status = status_filter.upper() if status_filter else None
    if unverified:
        target_status = "UNVERIFIED"
    elif invalidated:
        target_status = "INVALIDATED"
    elif verified:
        target_status = "VERIFIED"

    if target_status:
        findings = [f for f in findings if f.status == target_status]

    table = Table(title=f"Findings: {session_dir.name}")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Persona", style="cyan")
    table.add_column("Sev", style="bold")
    table.add_column("Conf", justify="right")
    table.add_column("Location", overflow="fold")
    table.add_column("Title", overflow="fold")
    table.add_column("Status")
    table.add_column("Verified By / Reason", overflow="fold")

    for i, f in enumerate(findings, 1):
        st = f.status
        if st == "VERIFIED":
            st_fmt = "[green]VERIFIED[/green]"
        elif st == "INVALIDATED":
            st_fmt = "[red]INVALIDATED[/red]"
        elif st == "MITIGATED":
            st_fmt = "[cyan]MITIGATED[/cyan]"
        else:
            st_fmt = "[yellow]UNVERIFIED[/yellow]"

        by = f.verified_by or ""
        reason = f.invalidation_reason or ""
        info = f"{by}: {reason}".strip(": ") if (by or reason) else "—"

        conf_str = f"{f.confidence_score:.2f}" if f.confidence_score is not None else "N/A"
        table.add_row(
            str(i),
            f.persona,
            f.severity,
            conf_str,
            f.location,
            f.title,
            st_fmt,
            info,
        )

    console.print(table)


@app.command("verify")
def verify_finding(
    session: Annotated[str, typer.Argument(help="Session ID or substring")],
    index: Annotated[
        int | None,
        typer.Option("--index", "-i", help="1-based index of the finding to update"),
    ] = None,
    title_pattern: Annotated[
        str | None,
        typer.Option("--title", "-t", help="Title substring to match finding"),
    ] = None,
    status: Annotated[
        str,
        typer.Option(
            "--status", help="Target status: VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED"
        ),
    ] = "INVALIDATED",
    reason: Annotated[
        str,
        typer.Option("--reason", "-r", help="Explanation or justification for the status change"),
    ] = "",
) -> None:
    """Validate or invalidate a review finding, persisting feedback reasons."""
    session_dir = _find_session_dir(session)
    if not session_dir:
        rprint(f"[red]Session not found matching: {session}[/red]")
        raise typer.Exit(1)

    findings_file = session_dir / "findings.json"
    if not findings_file.exists():
        rprint(f"[red]No findings.json in {session_dir}[/red]")
        raise typer.Exit(1)

    payload = ReviewSessionPayload.model_validate_json(findings_file.read_text(encoding="utf-8"))
    if not payload.findings:
        rprint("[yellow]Session has no findings to update.[/yellow]")
        raise typer.Exit(0)

    target_idx: int | None = None
    if index is not None:
        if index < 1 or index > len(payload.findings):
            rprint(f"[red]Index out of bounds (1-{len(payload.findings)})[/red]")
            raise typer.Exit(1)
        target_idx = index - 1
    elif title_pattern is not None:
        for idx, f in enumerate(payload.findings):
            if title_pattern.lower() in f.title.lower():
                target_idx = idx
                break

    if target_idx is None:
        rprint("[red]Must specify --index <N> or --title <pattern>[/red]")
        raise typer.Exit(1)

    new_status = status.upper().strip()
    if new_status not in {"VERIFIED", "INVALIDATED", "MITIGATED", "UNVERIFIED"}:
        rprint("[red]Status must be one of: VERIFIED, INVALIDATED, MITIGATED, UNVERIFIED[/red]")
        raise typer.Exit(1)

    finding = payload.findings[target_idx]
    finding.status = new_status
    finding.verified = new_status != "INVALIDATED"
    finding.mitigated = new_status == "MITIGATED"
    finding.verified_by = "human"
    finding.verified_at = datetime.now().isoformat()
    if reason:
        finding.invalidation_reason = reason

    findings_file.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    rprint(f"[green]✓ Updated finding #{target_idx + 1} status → [bold]{new_status}[/bold][/green]")


@app.command("stats")
def review_stats(
    reviews_dir: Annotated[
        Path | None,
        typer.Option("--reviews-dir", help="Directory containing review sessions"),
    ] = None,
) -> None:
    """Compute and display review accuracy statistics across saved sessions."""
    r_dir = reviews_dir or _get_reviews_base_dir()
    if not r_dir.exists():
        rprint("[yellow]No review directory found.[/yellow]")
        raise typer.Exit(0)

    session_dirs = [d for d in r_dir.iterdir() if d.is_dir() and (d / "findings.json").exists()]
    if not session_dirs:
        rprint("[yellow]No saved review sessions found.[/yellow]")
        raise typer.Exit(0)

    total_sessions = len(session_dirs)
    total_findings = 0
    by_status: dict[str, int] = {"VERIFIED": 0, "UNVERIFIED": 0, "INVALIDATED": 0, "MITIGATED": 0}
    by_persona_total: dict[str, int] = {}
    by_persona_invalidated: dict[str, int] = {}

    for d in session_dirs:
        try:
            payload = ReviewSessionPayload.model_validate_json(
                (d / "findings.json").read_text(encoding="utf-8")
            )
            for f in payload.findings:
                total_findings += 1
                st = f.status
                by_status[st] = by_status.get(st, 0) + 1
                persona = f.persona or "unknown"
                by_persona_total[persona] = by_persona_total.get(persona, 0) + 1
                if st == "INVALIDATED":
                    by_persona_invalidated[persona] = by_persona_invalidated.get(persona, 0) + 1
        except Exception:
            continue

    rprint(Rule(" AI Code Review Accuracy & Verification Stats ", style="bold cyan"))
    rprint(f"[bold]Total Sessions:[/bold]  {total_sessions}")
    rprint(f"[bold]Total Findings:[/bold]  {total_findings}\n")

    table = Table(title="Finding Status Breakdown")
    table.add_column("Status", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    for st, count in by_status.items():
        pct = (count / total_findings * 100) if total_findings else 0.0
        table.add_row(st, str(count), f"{pct:.1f}%")

    console.print(table)
    console.print()

    if by_persona_total:
        ptable = Table(title="Persona False Positive Rate (Invalidated)")
        ptable.add_column("Persona", style="magenta")
        ptable.add_column("Total Findings", justify="right")
        ptable.add_column("Invalidated", justify="right")
        ptable.add_column("False-Positive Rate", justify="right")

        for persona, count in by_persona_total.items():
            inval = by_persona_invalidated.get(persona, 0)
            rate = (inval / count * 100) if count else 0.0
            ptable.add_row(persona, str(count), str(inval), f"{rate:.1f}%")

        console.print(ptable)


@app.command("export-feedback")
def export_feedback(
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output JSONL path for benchmark feedback dataset"),
    ] = None,
    reviews_dir: Annotated[
        Path | None,
        typer.Option("--reviews-dir", help="Directory containing review sessions"),
    ] = None,
    status: Annotated[
        str,
        typer.Option(
            "--status",
            "-s",
            help="Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL",
        ),
    ] = "INVALIDATED",
) -> None:
    """Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning."""
    status_filter = None if status.upper() == "ALL" else status.upper()
    count, out_path = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output, status_filter=status_filter
    )
    if count == 0:
        target_dir = reviews_dir or _get_reviews_base_dir()
        rprint(f"[yellow]No {status} findings found to export under {target_dir}.[/yellow]")
    else:
        rprint(f"[green]✓ Exported {count} {status} finding(s) → [bold]{out_path}[/bold][/green]")


@app.command("apply-patch")
def apply_patch(
    session: Annotated[str, typer.Argument(help="Review session ID")],
    index: Annotated[int, typer.Option("--index", "-idx", help="Finding index (1-based)")] = 1,
    interactive: Annotated[
        bool, typer.Option("--interactive", "-i", help="Preview patch diff interactively")
    ] = False,
) -> None:
    """Apply suggested LLM code fix for a verified finding (v0.1.3)."""
    ok = stage_finding_patch(session=session, index=index, interactive=interactive)
    if not ok:
        raise typer.Exit(1)
