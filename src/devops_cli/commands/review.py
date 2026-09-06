"""AI Code Review CLI command group (branch, path, PR, findings, verify, stats)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

if TYPE_CHECKING:
    pass

import typer

from devops_cli.ai.personas import Persona
from devops_cli.ai.review.flags import resolve_stage_flags
from devops_cli.config.constants import (
    CONST_GIT_MAIN_BRANCH,
    CONST_STATUS_INVALIDATED,
)
from devops_cli.config.defaults import (
    DEFAULT_APPLY_PATCH_INDEX,
    DEFAULT_CURRENT_PATH,
    DEFAULT_MATCH_ALL_PATTERN,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, set_dry_run
from devops_cli.lang import HELP, MESSAGES

__all__ = [
    "app",
    "export_invalidated_feedback",
    "stage_finding_patch",
]


def __getattr__(name: str) -> Any:
    if name in {
        "_diff_pages",
        "_extract_code_lines",
        "_extract_segment_filenames",
        "_find_repo_files",
        "_is_generated_diff_block",
        "_paginate_file_diff_block",
        "_render_source_block",
        "_split_diff_into_file_blocks",
        "_split_source_file_blocks",
        "_split_text_lines",
    }:
        import devops_cli.ai.review.chunker

        return getattr(devops_cli.ai.review.chunker, name)
    if name == "export_invalidated_feedback":
        import devops_cli.ai.review.exporter

        return getattr(devops_cli.ai.review.exporter, name)
    if name == "stage_finding_patch":
        import devops_cli.ai.review.patching

        return getattr(devops_cli.ai.review.patching, name)
    if name in {
        "ReviewClients",
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
    }:
        import devops_cli.ai.review.runner

        return getattr(devops_cli.ai.review.runner, name)
    if name in {
        "_build_prompt",
        "_mask_secrets_in_content",
        "_sanitize_filename",
        "_sanitize_prompt_boundary_tags",
        "_truncate_for_prompt",
        "_unique_preserve_order",
    }:
        import devops_cli.ai.review.sanitization

        return getattr(devops_cli.ai.review.sanitization, name)
    if name in {
        "_build_validation_prompt",
        "_extract_location_context",
        "_find_related_file_metas",
        "_match_dep_to_filepath",
        "_merge_segment_results",
        "_reconcile_verified",
        "_validate_segment_findings",
    }:
        import devops_cli.ai.review.verification

        return getattr(devops_cli.ai.review.verification, name)
    if name in {
        "Finding",
        "ReviewResult",
        "ReviewSessionPayload",
        "SavedFinding",
        "format_clean_text_field",
    }:
        import devops_cli.ai.review_schema

        return getattr(devops_cli.ai.review_schema, name)
    if name in {
        "escape_text",
        "print_error",
        "print_info",
        "print_panel",
        "print_section",
        "print_success",
        "print_table",
        "print_warning",
        "write_json_file",
    }:
        import devops_cli.output

        return getattr(devops_cli.output, name)
    if name == "load_settings":
        from devops_cli.config.settings import load_settings

        return load_settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _get(name: str) -> Any:
    mod_dict = sys.modules[__name__].__dict__
    if name in mod_dict:
        return mod_dict[name]
    return getattr(sys.modules[__name__], name)


def _prepare_path_content(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.runner import _prepare_path_content as fn

    return fn(*args, **kwargs)


def _prepare_branch_content(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.runner import _prepare_branch_content as fn

    return fn(*args, **kwargs)


def _prepare_pr_content(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.runner import _prepare_pr_content as fn

    return fn(*args, **kwargs)


def _build_path_prompt(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.runner import _build_path_prompt as fn

    return fn(*args, **kwargs)


def _make_review_clients(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.runner import _make_review_clients as fn

    return fn(*args, **kwargs)


def _execute_review_workflow(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.runner import _execute_review_workflow as fn

    return fn(*args, **kwargs)


def _find_session_dir(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.runner import _find_session_dir as fn

    return fn(*args, **kwargs)


def _get_reviews_base_dir(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.runner import _get_reviews_base_dir as fn

    return fn(*args, **kwargs)


def load_settings(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.config.settings import load_settings as fn

    return fn(*args, **kwargs)


def _build_prompt(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.sanitization import _build_prompt as fn

    return fn(*args, **kwargs)


def stage_finding_patch(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.patching import stage_finding_patch as fn

    return fn(*args, **kwargs)


def export_invalidated_feedback(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review.exporter import export_invalidated_feedback as fn

    return fn(*args, **kwargs)


app = new_typer(help=HELP.review.app, no_args_is_help=True)


@app.callback(invoke_without_command=True)
def review_main(
    ctx: typer.Context,
    explain: Annotated[
        bool,
        typer.Option("--explain", "-e", help=HELP.review.explain_review),
    ] = False,
) -> None:
    """Multi-persona AI code review with confidence calibration and finding verification."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("review")
        raise typer.Exit(0)


# =============================================================================
# Command: devops review path
# =============================================================================


@app.command()
def path(
    targets: Annotated[
        list[Path] | None,
        typer.Argument(help=HELP.review.target_path),
    ] = None,
    pattern: Annotated[
        str,
        typer.Option("--pattern", "-g", help=HELP.options.pattern),
    ] = DEFAULT_MATCH_ALL_PATTERN,
    persona: Annotated[
        Persona | None,
        typer.Option("--persona", "-p", help=HELP.options.persona),
    ] = None,
    all_personas: Annotated[
        bool,
        typer.Option("--all", help=HELP.options.all_personas),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    summary: Annotated[
        bool,
        typer.Option("--summary", "-s", help=HELP.review.summary),
    ] = False,
    explain: Annotated[
        bool,
        typer.Option("--explain", "-e", help=HELP.review.explain_review),
    ] = False,
    no_pre_analysis: Annotated[
        bool,
        typer.Option("--no-pre-analysis", help=HELP.review.no_pre_analysis),
    ] = False,
    pre_analysis_only: Annotated[
        bool,
        typer.Option("--pre-analysis-only", help=HELP.review.pre_analysis_only),
    ] = False,
    no_static_scan: Annotated[
        bool,
        typer.Option("--no-static-scan", help=HELP.review.no_static_scan),
    ] = False,
    static_scan_only: Annotated[
        bool,
        typer.Option("--static-scan-only", help=HELP.review.static_scan_only),
    ] = False,
    no_persona_review: Annotated[
        bool,
        typer.Option("--no-persona-review", help=HELP.review.no_persona_review),
    ] = False,
    persona_review_only: Annotated[
        bool,
        typer.Option("--persona-review-only", help=HELP.review.persona_review_only),
    ] = False,
    no_verification: Annotated[
        bool,
        typer.Option("--no-verification", help=HELP.review.no_verification),
    ] = False,
    verification_only: Annotated[
        bool,
        typer.Option("--verification-only", help=HELP.review.verification_only),
    ] = False,
    no_reranking: Annotated[
        bool,
        typer.Option("--no-reranking", help=HELP.review.no_reranking),
    ] = False,
    reranking_only: Annotated[
        bool,
        typer.Option("--reranking-only", help=HELP.review.reranking_only),
    ] = False,
    no_reporting: Annotated[
        bool,
        typer.Option("--no-reporting", help=HELP.review.no_reporting),
    ] = False,
    reporting_only: Annotated[
        bool,
        typer.Option("--reporting-only", help=HELP.review.reporting_only),
    ] = False,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help=HELP.review.no_cache),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help=HELP.review.force_review),
    ] = False,
    append_cache: Annotated[
        bool,
        typer.Option("--append-cache", help=HELP.review.append_cache),
    ] = False,
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help=HELP.options.watch),
    ] = False,
    debounce_ms: Annotated[
        int,
        typer.Option("--debounce-ms", help=HELP.options.debounce_ms),
    ] = 500,
) -> None:
    """Review source files directly (no git required)."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("review")
        return
    set_dry_run(dry_run)
    stage_flags = resolve_stage_flags(
        no_pre_analysis=no_pre_analysis,
        pre_analysis_only=pre_analysis_only,
        no_static_scan=no_static_scan,
        static_scan_only=static_scan_only,
        no_persona_review=no_persona_review,
        persona_review_only=persona_review_only,
        no_verification=no_verification,
        verification_only=verification_only,
        no_reranking=no_reranking,
        reranking_only=reranking_only,
        no_reporting=no_reporting,
        reporting_only=reporting_only,
    )
    settings = load_settings()
    clients = _make_review_clients(
        settings,
        cache_enabled=False if (no_cache or force) else None,
        append_cache=append_cache,
    )
    path_targets = targets or [DEFAULT_CURRENT_PATH]

    def _execute_current_review() -> None:
        if len(path_targets) == 1:
            target = path_targets[0]
            pages, title, agents_md = _prepare_path_content(target, pattern)
            target_resolved = target.resolve()
            target_dir = target_resolved if target_resolved.is_dir() else target_resolved.parent
            target_ref = str(target_resolved)
        else:
            all_pages: list[str] = []
            agents_md = ""
            target_names: list[str] = []
            first_target_dir = Path.cwd().resolve()
            for t in path_targets:
                t_resolved = t.resolve()
                t_pages, _, t_agents = _prepare_path_content(t, pattern)
                all_pages.extend(t_pages)
                if not agents_md and t_agents:
                    agents_md = t_agents
                target_names.append(str(t_resolved))
                if (
                    first_target_dir == Path.cwd().resolve()
                    and t_resolved.exists()
                    and t_resolved.is_dir()
                ):
                    first_target_dir = t_resolved

            pages = all_pages
            title = f"Multiple targets ({len(path_targets)} paths)"
            target_dir = first_target_dir
            target_ref = ", ".join(target_names[:3]) + (
                f" (+{len(target_names) - 3} more)" if len(target_names) > 3 else ""
            )

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
            target_ref=target_ref,
            target_dir=target_dir,
            stage_flags=stage_flags,
        )

    if watch:
        from devops_cli.output import print_info
        from devops_cli.watchers.file_watcher import DebouncedFileWatcher

        def _on_change(changed: list[Path]) -> None:
            print_info(f"Detected changes in {len(changed)} file(s). Running review...")
            _execute_current_review()

        print_info(f"Watching {len(path_targets)} target(s)... Press Ctrl+C to stop.")
        watcher = DebouncedFileWatcher(
            path_targets,
            on_change=_on_change,
            debounce_ms=debounce_ms,
        )
        watcher.watch()
        return

    _execute_current_review()


# =============================================================================
# Command: devops review branch
# =============================================================================


@app.command()
def branch(
    branch_name: Annotated[
        str | None,
        typer.Argument(help=HELP.review.target_branch),
    ] = None,
    base: Annotated[
        str,
        typer.Option("--base", "-b", help=HELP.options.base_branch),
    ] = CONST_GIT_MAIN_BRANCH,
    persona: Annotated[
        Persona | None,
        typer.Option("--persona", "-p", help=HELP.options.persona),
    ] = None,
    all_personas: Annotated[
        bool,
        typer.Option("--all", help=HELP.options.all_personas),
    ] = False,
    repo_path: Annotated[
        Path,
        typer.Option("--repo", help=HELP.options.repo),
    ] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    summary: Annotated[
        bool,
        typer.Option("--summary", "-s", help=HELP.review.summary),
    ] = False,
    explain: Annotated[
        bool,
        typer.Option("--explain", "-e", help=HELP.review.explain_review),
    ] = False,
    no_pre_analysis: Annotated[
        bool,
        typer.Option("--no-pre-analysis", help=HELP.review.no_pre_analysis),
    ] = False,
    pre_analysis_only: Annotated[
        bool,
        typer.Option("--pre-analysis-only", help=HELP.review.pre_analysis_only),
    ] = False,
    no_static_scan: Annotated[
        bool,
        typer.Option("--no-static-scan", help=HELP.review.no_static_scan),
    ] = False,
    static_scan_only: Annotated[
        bool,
        typer.Option("--static-scan-only", help=HELP.review.static_scan_only),
    ] = False,
    no_persona_review: Annotated[
        bool,
        typer.Option("--no-persona-review", help=HELP.review.no_persona_review),
    ] = False,
    persona_review_only: Annotated[
        bool,
        typer.Option("--persona-review-only", help=HELP.review.persona_review_only),
    ] = False,
    no_verification: Annotated[
        bool,
        typer.Option("--no-verification", help=HELP.review.no_verification),
    ] = False,
    verification_only: Annotated[
        bool,
        typer.Option("--verification-only", help=HELP.review.verification_only),
    ] = False,
    no_reranking: Annotated[
        bool,
        typer.Option("--no-reranking", help=HELP.review.no_reranking),
    ] = False,
    reranking_only: Annotated[
        bool,
        typer.Option("--reranking-only", help=HELP.review.reranking_only),
    ] = False,
    no_reporting: Annotated[
        bool,
        typer.Option("--no-reporting", help=HELP.review.no_reporting),
    ] = False,
    reporting_only: Annotated[
        bool,
        typer.Option("--reporting-only", help=HELP.review.reporting_only),
    ] = False,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help=HELP.review.no_cache),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help=HELP.review.force_review),
    ] = False,
    append_cache: Annotated[
        bool,
        typer.Option("--append-cache", help=HELP.review.append_cache),
    ] = False,
) -> None:
    """Review a git branch diff with one or all AI personas."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("review")
        return
    set_dry_run(dry_run)
    stage_flags = resolve_stage_flags(
        no_pre_analysis=no_pre_analysis,
        pre_analysis_only=pre_analysis_only,
        no_static_scan=no_static_scan,
        static_scan_only=static_scan_only,
        no_persona_review=no_persona_review,
        persona_review_only=persona_review_only,
        no_verification=no_verification,
        verification_only=verification_only,
        no_reranking=no_reranking,
        reranking_only=reranking_only,
        no_reporting=no_reporting,
        reporting_only=reporting_only,
    )
    settings = load_settings()
    clients = _make_review_clients(
        settings,
        cache_enabled=False if (no_cache or force) else None,
        append_cache=append_cache,
    )
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
        stage_flags=stage_flags,
    )


# =============================================================================
# Command: devops review pr
# =============================================================================


@app.command()
def pr(
    number: Annotated[int, typer.Argument(help=HELP.review.pr_number)],
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-r", help=HELP.pr.target_repo),
    ] = None,
    persona: Annotated[
        Persona | None,
        typer.Option("--persona", "-p", help=HELP.options.persona),
    ] = None,
    all_personas: Annotated[
        bool,
        typer.Option("--all", help=HELP.options.all_personas),
    ] = False,
    post_comment: Annotated[
        bool,
        typer.Option("--post", help=HELP.review.post_pr),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    summary: Annotated[
        bool,
        typer.Option("--summary", "-s", help=HELP.review.summary),
    ] = False,
    explain: Annotated[
        bool,
        typer.Option("--explain", "-e", help=HELP.review.explain_review),
    ] = False,
    no_pre_analysis: Annotated[
        bool,
        typer.Option("--no-pre-analysis", help=HELP.review.no_pre_analysis),
    ] = False,
    pre_analysis_only: Annotated[
        bool,
        typer.Option("--pre-analysis-only", help=HELP.review.pre_analysis_only),
    ] = False,
    no_static_scan: Annotated[
        bool,
        typer.Option("--no-static-scan", help=HELP.review.no_static_scan),
    ] = False,
    static_scan_only: Annotated[
        bool,
        typer.Option("--static-scan-only", help=HELP.review.static_scan_only),
    ] = False,
    no_persona_review: Annotated[
        bool,
        typer.Option("--no-persona-review", help=HELP.review.no_persona_review),
    ] = False,
    persona_review_only: Annotated[
        bool,
        typer.Option("--persona-review-only", help=HELP.review.persona_review_only),
    ] = False,
    no_verification: Annotated[
        bool,
        typer.Option("--no-verification", help=HELP.review.no_verification),
    ] = False,
    verification_only: Annotated[
        bool,
        typer.Option("--verification-only", help=HELP.review.verification_only),
    ] = False,
    no_reranking: Annotated[
        bool,
        typer.Option("--no-reranking", help=HELP.review.no_reranking),
    ] = False,
    reranking_only: Annotated[
        bool,
        typer.Option("--reranking-only", help=HELP.review.reranking_only),
    ] = False,
    no_reporting: Annotated[
        bool,
        typer.Option("--no-reporting", help=HELP.review.no_reporting),
    ] = False,
    reporting_only: Annotated[
        bool,
        typer.Option("--reporting-only", help=HELP.review.reporting_only),
    ] = False,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help=HELP.review.no_cache),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help=HELP.review.force_review),
    ] = False,
    append_cache: Annotated[
        bool,
        typer.Option("--append-cache", help=HELP.review.append_cache),
    ] = False,
) -> None:
    """Review a GitHub pull request with one or all AI personas."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("review")
        return
    from devops_cli.config.settings import get_github_token

    set_dry_run(dry_run)
    stage_flags = resolve_stage_flags(
        no_pre_analysis=no_pre_analysis,
        pre_analysis_only=pre_analysis_only,
        no_static_scan=no_static_scan,
        static_scan_only=static_scan_only,
        no_persona_review=no_persona_review,
        persona_review_only=persona_review_only,
        no_verification=no_verification,
        verification_only=verification_only,
        no_reranking=no_reranking,
        reranking_only=reranking_only,
        no_reporting=no_reporting,
        reporting_only=reporting_only,
    )
    settings = load_settings()
    token = get_github_token(settings)
    if not token:
        _get("print_error")(
            MESSAGES.review.github_token_not_configured,
            prefix=False,
        )
        raise typer.Exit(1)

    clients = _make_review_clients(
        settings,
        cache_enabled=False if (no_cache or force) else None,
        append_cache=append_cache,
    )
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
        stage_flags=stage_flags,
    )

    if post_comment and reviews:
        from devops_cli.ai.review.runner import _review_to_markdown

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
            _get("print_warning")(
                MESSAGES.dry_run.skipped_pr_comment.format(number=number), prefix=False
            )
            return
        pull.create_issue_comment(comment_body)
        _get("print_success")(f"Review posted as comment on PR #{number}")


# =============================================================================
# Command: devops review findings
# =============================================================================


def _render_finding_badge(status: str) -> str:
    """Format finding verification status badge."""
    st = status.upper()
    if st == "VERIFIED":
        return "[green]✓ VERIFIED[/green]"
    if st == "INVALIDATED":
        return "[red]✗ INVALIDATED[/red]"
    if st == "MITIGATED":
        return "[cyan]~ MITIGATED[/cyan]"
    return f"[yellow]? {status}[/yellow]"


def _build_finding_panel_lines(f: Any) -> list[str]:
    """Format rich text lines for an individual finding panel."""
    persona_title = getattr(f, "persona_title", None) or getattr(f, "persona", "")
    persona_badge = (
        f"  |  [bold]Persona:[/bold] [magenta]{_get('escape_text')(persona_title)}[/magenta]"
        if persona_title
        else ""
    )
    lines = [
        f"[bold]Location:[/bold] [cyan]{_get('escape_text')(f.location)}[/cyan]{persona_badge}",
    ]
    if f.description:
        clean_desc = _get("escape_text")(_get("format_clean_text_field")(f.description).strip())
        lines.extend(["", "[bold]Description:[/bold]", clean_desc])
    if f.fix:
        clean_fix = _get("escape_text")(_get("format_clean_text_field")(f.fix).strip())
        lines.extend(["", "[bold]Suggested Fix:[/bold]", clean_fix])
    if f.invalidation_reason:
        clean_inv = _get("escape_text")(f.invalidation_reason.strip())
        lines.extend(["", f"[bold yellow]Invalidation Reason:[/bold yellow] {clean_inv}"])
    if f.references:
        refs_list = f.references if isinstance(f.references, list) else [str(f.references)]
        lines.extend(["", f"[dim]References: {_get('escape_text')(', '.join(refs_list))}[/dim]"])
    return lines


@app.command("findings")
def list_findings(
    session: Annotated[
        str | None,
        typer.Argument(help=HELP.review.session),
    ] = None,
    session_opt: Annotated[
        str | None,
        typer.Option("--session", "-s", help=HELP.review.session),
    ] = None,
    status_filter: Annotated[
        str | None,
        typer.Option("--status", help=HELP.review.status_filter),
    ] = None,
    unverified: Annotated[bool, typer.Option("--unverified", help=HELP.review.unverified)] = False,
    invalidated: Annotated[
        bool, typer.Option("--invalidated", help=HELP.review.invalidated)
    ] = False,
    verified: Annotated[bool, typer.Option("--verified", help=HELP.review.verified)] = False,
    details: Annotated[
        bool,
        typer.Option("--details", "-d", help=HELP.review.details),
    ] = False,
) -> None:
    """Inspect structured findings for a review session."""
    from devops_cli.ai.review.runner import _find_session_dir

    target_session = session or session_opt
    session_dir = _find_session_dir(target_session)
    if not session_dir:
        _get("print_warning")("No review sessions found in .data/reviews/", prefix=False)
        raise typer.Exit(0)

    findings_file = session_dir / "findings.json"
    if not findings_file.exists():
        _get("print_warning")(f"No findings.json in session {session_dir.name}", prefix=False)
        raise typer.Exit(0)

    from devops_cli.ai.review_schema import ReviewSessionPayload

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

    rows: list[list[str]] = []
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
        rows.append(
            [
                str(i),
                f.persona,
                f.severity,
                conf_str,
                f.location,
                f.title,
                st_fmt,
                info,
            ]
        )

    _get("print_table")(
        title=f"Findings: {session_dir.name}",
        columns=[
            ("#", "right"),
            ("Persona", "cyan"),
            ("Sev", "bold"),
            ("Conf", "right"),
            "Location",
            "Title",
            "Status",
            "Verified By / Reason",
        ],
        rows=rows,
    )

    if details:
        for idx, f in enumerate(findings, 1):
            sev_upper = f.severity.upper()
            sev_color = {
                "CRITICAL": "red",
                "HIGH": "orange3",
                "MEDIUM": "yellow",
                "LOW": "cyan",
                "INFO": "green",
            }.get(sev_upper, "white")

            st_badge = _render_finding_badge(f.status)
            title_header = f"[{sev_color} bold]Finding #{idx}: [{sev_upper}] {_get('escape_text')(f.title)}[/{sev_color} bold]  {st_badge}"
            panel_lines = _build_finding_panel_lines(f)

            _get("print_panel")(
                "\n".join(panel_lines),
                title=title_header,
                border_style=sev_color,
            )


# =============================================================================
# Command: devops review verify
# =============================================================================


@app.command("verify")
def verify_finding(
    session: Annotated[
        str | None,
        typer.Argument(help=HELP.review.session),
    ] = None,
    session_opt: Annotated[
        str | None,
        typer.Option("--session", "-s", help=HELP.review.session),
    ] = None,
    index: Annotated[
        int | None,
        typer.Option("--index", "-i", help=HELP.review.finding_index),
    ] = None,
    title_pattern: Annotated[
        str | None,
        typer.Option("--title", "-t", help=HELP.review.title_match),
    ] = None,
    status: Annotated[
        str,
        typer.Option("--status", help=HELP.review.status_target),
    ] = CONST_STATUS_INVALIDATED,
    reason: Annotated[
        str,
        typer.Option("--reason", "-r", help=HELP.review.reason),
    ] = "",
) -> None:
    """Validate or invalidate a review finding, persisting feedback reasons."""
    from devops_cli.ai.review.runner import _find_session_dir

    target_session = session or session_opt
    session_dir = _find_session_dir(target_session)
    if not session_dir:
        _get("print_error")(f"Session not found matching: {target_session}", prefix=False)
        raise typer.Exit(1)

    findings_file = session_dir / "findings.json"
    if not findings_file.exists():
        _get("print_error")(f"No findings.json in {session_dir}", prefix=False)
        raise typer.Exit(1)

    from devops_cli.ai.review_schema import ReviewSessionPayload

    payload = ReviewSessionPayload.model_validate_json(findings_file.read_text(encoding="utf-8"))
    if not payload.findings:
        _get("print_warning")(MESSAGES.review.no_findings_to_update, prefix=False)
        raise typer.Exit(0)

    target_idx: int | None = None
    if index is not None:
        if index < 1 or index > len(payload.findings):
            _get("print_error")(f"Index out of bounds (1-{len(payload.findings)})", prefix=False)
            raise typer.Exit(1)
        target_idx = index - 1
    elif title_pattern is not None:
        for idx, f in enumerate(payload.findings):
            if title_pattern.lower() in f.title.lower():
                target_idx = idx
                break

    if target_idx is None:
        _get("print_error")(MESSAGES.review.specify_index_or_title, prefix=False)
        raise typer.Exit(1)

    new_status = status.upper().strip()
    if new_status not in {"VERIFIED", "INVALIDATED", "MITIGATED", "UNVERIFIED"}:
        _get("print_error")(MESSAGES.review.invalid_status_choices, prefix=False)
        raise typer.Exit(1)

    finding = payload.findings[target_idx]
    finding.status = new_status
    finding.verified = new_status != "INVALIDATED"
    finding.mitigated = new_status == "MITIGATED"
    finding.verified_by = "human"
    finding.verified_at = datetime.now().isoformat()
    if reason:
        finding.invalidation_reason = reason

    if new_status == "INVALIDATED":
        try:
            from devops_cli.ai.review.common_hallucinations import auto_record_invalidated_finding

            auto_record_invalidated_finding(finding, reason=reason)
        except Exception:
            pass

    _get("write_json_file")(findings_file, payload)
    _get("print_success")(f"Updated finding #{target_idx + 1} status → {new_status}")


# =============================================================================
# Command: devops review stats
# =============================================================================


@app.command("stats")
def review_stats(
    reviews_dir: Annotated[
        Path | None,
        typer.Option("--reviews-dir", help=HELP.review.reviews_dir),
    ] = None,
) -> None:
    """Compute and display review accuracy statistics across saved sessions."""
    from devops_cli.ai.review.runner import _get_reviews_base_dir

    r_dir = reviews_dir or _get_reviews_base_dir()
    if not r_dir.exists():
        _get("print_warning")(MESSAGES.review.no_review_dir_found, prefix=False)
        raise typer.Exit(0)

    session_dirs = [d for d in r_dir.iterdir() if d.is_dir() and (d / "findings.json").exists()]
    if not session_dirs:
        _get("print_warning")(MESSAGES.review.no_saved_sessions, prefix=False)
        raise typer.Exit(0)

    total_sessions = len(session_dirs)
    total_findings = 0
    by_status: dict[str, int] = {"VERIFIED": 0, "UNVERIFIED": 0, "INVALIDATED": 0, "MITIGATED": 0}
    by_persona_total: dict[str, int] = {}
    by_persona_invalidated: dict[str, int] = {}

    from devops_cli.ai.review_schema import ReviewSessionPayload

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

    _get("print_section")(" AI Code Review Accuracy & Verification Stats ", style="bold cyan")
    _get("print_info")(f"[bold]Total Sessions:[/bold]  {total_sessions}", prefix=False)
    _get("print_info")(f"[bold]Total Findings:[/bold]  {total_findings}\n", prefix=False)

    status_rows = []
    for st, count in by_status.items():
        pct = (count / total_findings * 100) if total_findings else 0.0
        status_rows.append([st, str(count), f"{pct:.1f}%"])

    _get("print_table")(
        title="Finding Status Breakdown",
        columns=[("Status", "cyan"), ("Count", "right"), ("Percentage", "right")],
        rows=status_rows,
    )

    if by_persona_total:
        persona_rows = []
        for persona, count in by_persona_total.items():
            inval = by_persona_invalidated.get(persona, 0)
            rate = (inval / count * 100) if count else 0.0
            persona_rows.append([persona, str(count), str(inval), f"{rate:.1f}%"])

        _get("print_table")(
            title="Persona False Positive Rate (Invalidated)",
            columns=[
                ("Persona", "magenta"),
                ("Total Findings", "right"),
                ("Invalidated", "right"),
                ("False-Positive Rate", "right"),
            ],
            rows=persona_rows,
        )


# =============================================================================
# Command: devops review export-feedback
# =============================================================================


@app.command("export-feedback")
def export_feedback(
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help=HELP.review.output_feedback),
    ] = None,
    reviews_dir: Annotated[
        Path | None,
        typer.Option("--reviews-dir", help=HELP.review.reviews_dir),
    ] = None,
    status: Annotated[
        str,
        typer.Option(
            "--status",
            "-s",
            help=HELP.review.status_export,
        ),
    ] = CONST_STATUS_INVALIDATED,
) -> None:
    """Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning."""
    status_filter = None if status.upper() == "ALL" else status.upper()
    from devops_cli.ai.review.exporter import export_invalidated_feedback

    count, out_path = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output, status_filter=status_filter
    )
    if count == 0:
        target_dir = reviews_dir or _get_reviews_base_dir()
        _get("print_warning")(
            f"No {status} findings found to export under {target_dir}.", prefix=False
        )
    else:
        _get("print_success")(f"Exported {count} {status} finding(s) → [bold]{out_path}[/bold]")


# =============================================================================
# Command: devops review apply-patch
# =============================================================================


@app.command("apply-patch")
def apply_patch(
    session: Annotated[str, typer.Argument(help=HELP.review.session)],
    index: Annotated[
        int, typer.Option("--index", "-idx", help=HELP.review.finding_index)
    ] = DEFAULT_APPLY_PATCH_INDEX,
    interactive: Annotated[
        bool, typer.Option("--interactive", "-i", help=HELP.review.interactive_patch)
    ] = False,
) -> None:
    """Apply suggested LLM code fix for a verified finding."""
    ok = stage_finding_patch(session=session, index=index, interactive=interactive)
    if not ok:
        raise typer.Exit(1)


# =============================================================================
# Command: devops review auto-fix
# =============================================================================


@app.command("auto-fix")
def auto_fix_cmd(
    finding_id: Annotated[
        str,
        typer.Argument(help=HELP.review.remediate_finding_id),
    ],
    target_file: Annotated[
        str,
        typer.Option("--file", "-f", help=HELP.review.remediate_file),
    ] = "src/devops_cli/main.py",
    branch_name: Annotated[
        str | None,
        typer.Option("--branch", "-b", help=HELP.review.remediate_branch),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Create a corrective topic branch with verified unit test patch for an approved finding."""
    import json

    from devops_cli.ai.review.auto_fix import generate_remediation_branch
    from devops_cli.dry_run import is_dry_run

    res = generate_remediation_branch(
        finding_id=finding_id,
        target_file=target_file,
        branch_name=branch_name,
        dry_run=dry_run or is_dry_run(),
    )

    if json_output:
        _get("write_stdout")(json.dumps(res.to_dict(), indent=2) + "\n")
        return

    if res.applied:
        _get("print_success")(
            f"✓ Created remediation topic branch [bold]{res.branch_name}[/bold] for finding '{res.finding_id}'."
        )
    else:
        _get("print_error")(f"Failed to create remediation branch: {res.message}")
        raise typer.Exit(1)
