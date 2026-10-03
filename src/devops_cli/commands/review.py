"""AI Code Review CLI command group (branch, path, PR, findings, verify, stats)."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from devops_cli.ai.personas import PersonaDefinition
    from devops_cli.ai.review_schema import ReviewResult
    from devops_cli.config.settings import Settings

import typer

from devops_cli.ai.personas import Persona
from devops_cli.ai.review.flags import resolve_stage_flags
from devops_cli.config.constants import (
    CONST_GIT_MAIN_BRANCH,
    CONST_OUTPUT_FORMAT_TABLE,
    CONST_REVIEW_CANDIDATES_FILENAME,
    CONST_REVIEW_FINDINGS_FILENAME,
    CONST_STATUS_INVALIDATED,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_MATCH_ALL_PATTERN,
    DEFAULT_REVIEW_BENCHMARK_RUNS,
    DEFAULT_REVIEW_CORPUS_SEED,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.untrusted_trees import reading_untrusted_trees
from devops_cli.dry_run import is_dry_run, set_dry_run
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output.serialization import emit_serialized, normalize_format

__all__ = [
    "app",
    "export_invalidated_feedback",
]

from devops_cli.ai.review import runner
from devops_cli.ai.review.adjudication import (
    Verdict,
    adjudicating,
    judge_candidate,
    judge_reported,
    number_by_title,
    write_session_files,
)
from devops_cli.ai.review.defects import (
    CORPUS_FILES_DIR,
    RUN_FIGURE_DECIMALS,
    TEMPLATES,
    CorpusRunsScore,
    CorpusScore,
    DefectCorpus,
    DefectTemplate,
    generate_corpus,
    score_corpus,
    score_corpus_runs,
    select_templates,
)
from devops_cli.ai.review.exporter import export_invalidated_feedback
from devops_cli.ai.review.history import HistoryFinding, load_review_history
from devops_cli.ai.review.judged_claims import project_of
from devops_cli.ai.review.profile import (
    BenchmarkSummary,
    ReviewProfile,
    StageSummary,
    collect_profiles,
    summarize_profiles,
)
from devops_cli.ai.review.review_environment import nearest_review_conventions
from devops_cli.ai.review.runner import (
    _build_path_prompt,
    _corpus_digest,
    _execute_review_workflow,
    _find_session_dir,
    _make_review_clients,
    _nearest_conventions,
    _prepare_branch_content,
    _prepare_path_content,
    _prepare_pr_content,
    _review_candidate_files,
)
from devops_cli.ai.review.sample_validation import (
    CategoryReport,
    CorpusReview,
    review_problems,
    sample_files,
    validate_category,
)
from devops_cli.ai.review.samples import (
    SampleCategory,
    SampleRepository,
    checkout_problems,
    fetch_sample,
    load_sample_catalog,
    samples_dir,
)
from devops_cli.ai.review.sanitization import _build_prompt
from devops_cli.ai.review.template_sweep import (
    TemplateSweepReport,
    save_sweep_run,
    sweep_templates,
)
from devops_cli.ai.review.verdicts import Adjudicator
from devops_cli.ai.review_schema import (
    ReviewSessionPayload,
    SavedFinding,
    format_clean_text_field,
    severity_named,
)
from devops_cli.ai.run_store import (
    Mechanism,
    digest,
    keep_runs,
    new_run,
    record_run,
    review_setup,
    unpinned_groups,
)
from devops_cli.commands.ai_runs import announce_run, announce_runs
from devops_cli.config.settings import load_settings
from devops_cli.output import (
    escape_text,
    format_duration,
    print_error,
    print_info,
    print_panel,
    print_section,
    print_success,
    print_table,
    print_warning,
    write_stdout,
)

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
    # Every review command reads a tree devops-cli does not own, or what a review of one wrote,
    # so none takes the project config or the data directory from the repository it starts in,
    # unless that is devops-cli's own repository (#972); the commands that read a session resolve
    # the data directory as the review did.
    ctx.with_resource(reading_untrusted_trees())
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("review")
        raise typer.Exit(0)


def _init_logfire_if_enabled(logfire: bool | None, settings: Settings) -> None:
    """Initialize Logfire observability if explicitly flagged or configured."""
    is_enabled = logfire if logfire is not None else getattr(settings.telemetry, "logfire", False)
    if not is_enabled:
        return

    from devops_cli.telemetry.logfire import get_logfire_bridge

    if logfire is True:
        get_logfire_bridge().configure(settings=settings)
    else:
        import contextlib

        with contextlib.suppress(Exception):
            get_logfire_bridge().configure(settings=settings)


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
    full: Annotated[
        bool,
        typer.Option("--full", help=HELP.review.full_output),
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
    concurrency: Annotated[
        int | None,
        typer.Option("--concurrency", "-c", help=HELP.review.concurrency),
    ] = None,
    parallel: Annotated[
        bool,
        typer.Option("--parallel/--no-parallel", help=HELP.review.parallel),
    ] = True,
    logfire: Annotated[
        bool | None,
        typer.Option("--logfire/--no-logfire", help=HELP.review.logfire),
    ] = None,
) -> None:
    """Review source files directly (no git required)."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("review")
        return
    set_dry_run(dry_run)
    settings = load_settings()
    _init_logfire_if_enabled(logfire, settings)
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
    clients = _make_review_clients(
        settings,
        cache_enabled=False if (no_cache or force) else None,
        append_cache=append_cache,
    )
    path_targets = targets or [DEFAULT_CURRENT_PATH]

    def _execute_current_review() -> None:
        if len(path_targets) == 1:
            target = path_targets[0]
            pages, title, agents_md, routed_files = _prepare_path_content(target, pattern)
            target_resolved = target.resolve()
            target_dir = target_resolved if target_resolved.is_dir() else target_resolved.parent
            target_ref = str(target_resolved)
        else:
            all_pages: list[str] = []
            agents_md = ""
            target_names: list[str] = []
            routed_files = []
            first_target_dir = Path.cwd().resolve()
            for t in path_targets:
                t_resolved = t.resolve()
                t_pages, _, t_agents, t_routed = _prepare_path_content(t, pattern)
                all_pages.extend(t_pages)
                routed_files.extend(t_routed)
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
            concurrency=concurrency,
            parallel=parallel,
            full_output=full,
            routed_files=routed_files,
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
    full: Annotated[
        bool,
        typer.Option("--full", help=HELP.review.full_output),
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
    concurrency: Annotated[
        int | None,
        typer.Option("--concurrency", "-c", help=HELP.review.concurrency),
    ] = None,
    parallel: Annotated[
        bool,
        typer.Option("--parallel/--no-parallel", help=HELP.review.parallel),
    ] = True,
    logfire: Annotated[
        bool | None,
        typer.Option("--logfire/--no-logfire", help=HELP.review.logfire),
    ] = None,
) -> None:
    """Review a git branch diff with one or all AI personas."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("review")
        return
    set_dry_run(dry_run)
    settings = load_settings()
    _init_logfire_if_enabled(logfire, settings)
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
    clients = _make_review_clients(
        settings,
        cache_enabled=False if (no_cache or force) else None,
        append_cache=append_cache,
    )
    pages, title, agents_md, target_ref, base_revision = _prepare_branch_content(
        branch_name, base, repo_path
    )
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
        target_ref=target_ref,
        target_dir=repo_path,
        stage_flags=stage_flags,
        concurrency=concurrency,
        parallel=parallel,
        base_revision=base_revision,
        full_output=full,
    )


# =============================================================================
# Command: devops review pr
# =============================================================================


def _resolve_pr_files(pages: list[str], pull: Any) -> list[str]:
    """Extract changed file paths from PR pages or pull object."""
    from devops_cli.ai.review.chunker import _extract_header_filenames

    all_files = sorted(list({fn for page in pages for fn in _extract_header_filenames(page)}))
    if not all_files and pull:
        try:
            return [f.filename for f in pull.get_files() if getattr(f, "status", "") != "removed"]
        except Exception:
            return []
    return all_files


def _post_pr_review_comment(
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]],
    pages: list[str],
    head_dir: Path,
    pull: Any,
    repo_name: str,
    number: int,
) -> None:
    """Post formatted review comment to GitHub PR."""
    from devops_cli.ai.review.runner import format_pr_review_comment

    all_files = _resolve_pr_files(pages, pull)
    comment_body = format_pr_review_comment(
        reviews=reviews,
        files=all_files,
        target_dir=head_dir,
    )
    if is_dry_run():
        from devops_cli.ai.review.runner import _debug_block

        _debug_block(
            f"Would post PR comment on #{number}",
            {"repo": repo_name, "pr_number": number, "comment_body": comment_body},
        )
        print_warning(MESSAGES.dry_run.skipped_pr_comment.format(number=number), prefix=False)
        return
    pull.create_issue_comment(comment_body)
    print_success(f"Review posted as comment on PR #{number}")


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
    full: Annotated[
        bool,
        typer.Option("--full", help=HELP.review.full_output),
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
    concurrency: Annotated[
        int | None,
        typer.Option("--concurrency", "-c", help=HELP.review.concurrency),
    ] = None,
    parallel: Annotated[
        bool,
        typer.Option("--parallel/--no-parallel", help=HELP.review.parallel),
    ] = True,
    logfire: Annotated[
        bool | None,
        typer.Option("--logfire/--no-logfire", help=HELP.review.logfire),
    ] = None,
) -> None:
    """Review a GitHub pull request with one or all AI personas."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("review")
        return
    from devops_cli.config.settings import get_github_token

    set_dry_run(dry_run)
    settings = load_settings()
    _init_logfire_if_enabled(logfire, settings)
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
    token = get_github_token(settings)
    if not token:
        print_error(
            MESSAGES.review.github_token_not_configured,
            prefix=False,
        )
        raise typer.Exit(1)

    clients = _make_review_clients(
        settings,
        cache_enabled=False if (no_cache or force) else None,
        append_cache=append_cache,
    )
    # The review reads the PR head's files, not the local checkout's version of them. The head
    # is named after the checkout the review runs in, which its project resolves to, so the
    # review is shown and suppresses the claims people judged there (#950).
    with tempfile.TemporaryDirectory(prefix=f"devops-review-pr-{number}-") as head_parent:
        head_dir = Path(head_parent) / project_of(Path.cwd())
        # A review run from the file-system root names no project, and keeps the directory itself.
        head_dir.mkdir(exist_ok=True)
        pages, title, agents_md, pull, repo_name, base_revision = _prepare_pr_content(
            number, repo, token, head_dir=head_dir
        )
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
            target_dir=head_dir,
            stage_flags=stage_flags,
            concurrency=concurrency,
            parallel=parallel,
            base_revision=base_revision,
            full_output=full,
        )

    if post_comment and reviews:
        _post_pr_review_comment(
            reviews=reviews,
            pages=pages,
            head_dir=head_dir,
            pull=pull,
            repo_name=repo_name,
            number=number,
        )


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
        f"  |  [bold]Persona:[/bold] [magenta]{escape_text(persona_title)}[/magenta]"
        if persona_title
        else ""
    )
    lines = [
        f"[bold]Location:[/bold] [cyan]{escape_text(f.location)}[/cyan]{persona_badge}",
    ]
    if f.description:
        clean_desc = escape_text(format_clean_text_field(f.description).strip())
        lines.extend(["", "[bold]Description:[/bold]", clean_desc])
    if f.fix:
        clean_fix = escape_text(format_clean_text_field(f.fix).strip())
        lines.extend(["", "[bold]Suggested Fix:[/bold]", clean_fix])
    if f.invalidation_reason:
        clean_inv = escape_text(f.invalidation_reason.strip())
        lines.extend(["", f"[bold yellow]Invalidation Reason:[/bold yellow] {clean_inv}"])
    if f.references:
        refs_list = f.references if isinstance(f.references, list) else [str(f.references)]
        lines.extend(["", f"[dim]References: {escape_text(', '.join(refs_list))}[/dim]"])
    return lines


_SEVERITY_COLORS = {
    "CRITICAL": "red",
    "HIGH": "orange3",
    "MEDIUM": "yellow",
    "LOW": "cyan",
    "INFO": "green",
}
_STATUS_COLORS = {"VERIFIED": "green", "INVALIDATED": "red", "MITIGATED": "cyan"}
_VERDICT_STATUSES = frozenset({"VERIFIED", "INVALIDATED", "MITIGATED", "UNVERIFIED"})


def _listed_status(
    status_filter: str | None, unverified: bool, invalidated: bool, verified: bool, mitigated: bool
) -> str | None:
    """The status `review findings` keeps; a status flag wins over `--status`."""
    flags = (
        (unverified, "UNVERIFIED"),
        (invalidated, "INVALIDATED"),
        (verified, "VERIFIED"),
        (mitigated, "MITIGATED"),
    )
    return next((st for on, st in flags if on), status_filter.upper() if status_filter else None)


def _listed_findings(
    findings: list[SavedFinding], status: str | None, severities: list[str]
) -> list[tuple[int, SavedFinding]]:
    """Each finding with `status`, when given, and one of `severities`, spelled as a review
    accepts them (`informational` is INFO), under its number: its place in the file."""
    wanted = {severity_named(s) or s.upper() for s in severities}
    return [
        (number, f)
        for number, f in enumerate(findings, 1)
        if (status is None or f.status == status) and (not wanted or f.severity.upper() in wanted)
    ]


def _finding_row(number: int, f: SavedFinding) -> list[str]:
    """A finding's `devops review findings` table cells, its text escaped."""
    color = _STATUS_COLORS.get(f.status)
    st_fmt = f"[{color}]{f.status}[/{color}]" if color else "[yellow]UNVERIFIED[/yellow]"
    by = f.verified_by or ""
    reason = f.invalidation_reason or ""
    info = f"{by}: {reason}".strip(": ") if (by or reason) else "—"
    conf_str = f"{f.confidence_score:.2f}" if f.confidence_score is not None else "N/A"
    return [
        str(number),
        escape_text(f.persona),
        escape_text(f.severity),
        conf_str,
        escape_text(f.location),
        escape_text(f.title),
        st_fmt,
        escape_text(info),
    ]


def _print_finding_details(numbered: Sequence[tuple[int, SavedFinding]], noun: str) -> None:
    for number, f in numbered:
        sev_upper = f.severity.upper()
        sev_color = _SEVERITY_COLORS.get(sev_upper, "white")
        st_badge = _render_finding_badge(f.status)
        title_header = f"[{sev_color} bold]{noun} #{number}: [{sev_upper}] {escape_text(f.title)}[/{sev_color} bold]  {st_badge}"
        print_panel(
            "\n".join(_build_finding_panel_lines(f)),
            title=title_header,
            border_style=sev_color,
        )


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
    mitigated: Annotated[
        bool, typer.Option("--mitigated", help="Filter findings by MITIGATED status")
    ] = False,
    candidates: Annotated[bool, typer.Option("--candidates", help=HELP.review.candidates)] = False,
    severities: Annotated[
        list[str] | None,
        typer.Option("--severity", help=HELP.review.severity_filter),
    ] = None,
    details: Annotated[
        bool,
        typer.Option("--details", "-d", help=HELP.review.details),
    ] = False,
) -> None:
    """Inspect structured findings for a review session.

    Each finding keeps its number, its place in findings.json, whatever filter the list
    applies, and `devops review verify --index` takes that number. With `--candidates` the list
    is candidates.json: every finding the review raised, the ones verification invalidated
    included, numbered for `devops review verify --candidate`.
    """

    target_session = session or session_opt
    session_dir = _find_session_dir(target_session)
    if not session_dir:
        # A review's data directory may not be the repository's `.data` (#972), so say where.
        reviews_dir = runner._get_reviews_base_dir()
        print_warning(
            MESSAGES.review.no_review_sessions_found.format(reviews_dir=reviews_dir), prefix=False
        )
        raise typer.Exit(0)

    file_name = CONST_REVIEW_CANDIDATES_FILENAME if candidates else CONST_REVIEW_FINDINGS_FILENAME
    source = session_dir / file_name
    if not source.exists():
        print_warning(f"No {file_name} in session {session_dir.name}", prefix=False)
        raise typer.Exit(0)

    payload = ReviewSessionPayload.model_validate_json(source.read_text(encoding="utf-8"))
    target_status = _listed_status(status_filter, unverified, invalidated, verified, mitigated)
    # Each keeps its place in the file whatever the filter, the number `verify` takes.
    numbered = _listed_findings(payload.findings, target_status, severities or [])
    noun = "Candidate" if candidates else "Finding"
    print_table(
        title=f"{noun}s: {session_dir.name}",
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
        rows=[_finding_row(number, f) for number, f in numbered],
    )
    if details:
        _print_finding_details(numbered, noun)


# =============================================================================
# Command: devops review verify
# =============================================================================


def _require_session_dir(target_session: str | None) -> Path:
    session_dir = _find_session_dir(target_session)
    if not session_dir:
        print_error(MESSAGES.review.session_not_found.format(session=target_session), prefix=False)
        raise typer.Exit(1)
    return session_dir


def _read_session_file(session_dir: Path, file_name: str) -> tuple[Path, ReviewSessionPayload]:
    path = session_dir / file_name
    if not path.is_file():
        print_error(f"No {file_name} in {session_dir}", prefix=False)
        raise typer.Exit(1)
    return path, ReviewSessionPayload.model_validate_json(path.read_text(encoding="utf-8"))


def _require_findings(payload: ReviewSessionPayload) -> None:
    if not payload.findings:
        print_warning(MESSAGES.review.no_findings_to_update, prefix=False)
        raise typer.Exit(0)


def _judge_reported(
    session_dir: Path, index: int | None, title_pattern: str | None, verdict: Verdict
) -> str:
    """Record the verdict on a finding in findings.json, named by number or title, and on the
    candidates in candidates.json it reports."""
    with adjudicating(session_dir) as changes:
        findings_file, payload = _read_session_file(session_dir, CONST_REVIEW_FINDINGS_FILENAME)
        _require_findings(payload)
        files = [(findings_file, payload)]
        candidates = None
        if (session_dir / CONST_REVIEW_CANDIDATES_FILENAME).is_file():
            candidates_file, candidates = _read_session_file(
                session_dir, CONST_REVIEW_CANDIDATES_FILENAME
            )
            files.append((candidates_file, candidates))
        number = (
            index if index is not None else number_by_title(payload.findings, title_pattern or "")
        )
        judge_reported(payload, candidates, number, verdict, changes)
        write_session_files(files)
    return MESSAGES.review.updated_finding_status.format(index=number, status=verdict.status)


def _judge_candidate(session_dir: Path, number: int, verdict: Verdict) -> str:
    """Record the verdict on a candidate, moving it into findings.json when it is reported."""
    with adjudicating(session_dir) as changes:
        candidates_file, candidates = _read_session_file(
            session_dir, CONST_REVIEW_CANDIDATES_FILENAME
        )
        _require_findings(candidates)
        findings_file, reported = _read_session_file(session_dir, CONST_REVIEW_FINDINGS_FILENAME)
        moved = judge_candidate(candidates, reported, number, verdict, changes)
        write_session_files([(candidates_file, candidates), (findings_file, reported)])
    done = MESSAGES.review.updated_candidate_status.format(index=number, status=verdict.status)
    if not moved:
        return done
    added = MESSAGES.review.candidate_moved.format(index=number, number=len(reported.findings))
    return f"{done}\n{added}"


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
    candidate: Annotated[
        int | None,
        typer.Option("--candidate", help=HELP.review.candidate_index),
    ] = None,
    *,
    status: Annotated[
        str,
        typer.Option("--status", help=HELP.review.status_target),
    ],
    adjudicator: Annotated[
        Adjudicator,
        typer.Option("--adjudicator", help=HELP.review.adjudicator),
    ] = Adjudicator.HUMAN,
    reason: Annotated[
        str,
        typer.Option("--reason", "-r", help=HELP.review.reason),
    ] = "",
    perimeter: Annotated[
        list[str] | None,
        typer.Option("--perimeter", "-p", help=HELP.review.perimeter),
    ] = None,
    regression_test: Annotated[
        str | None,
        typer.Option("--regression-test", help=HELP.review.regression_test),
    ] = None,
) -> None:
    """Record a person's or an agent's verdict on a review finding or candidate.

    Name one finding: `--index` takes the number `devops review findings` shows, `--title` a
    substring of exactly one title, and `--candidate` the number `review findings --candidates`
    shows. There is no default verdict, so `--status` is required. A candidate given VERIFIED
    or MITIGATED moves into findings.json, unless findings.json already reports its defect under
    another title: give that finding the verdict instead.

    A verdict on a finding in findings.json is recorded on the candidate it reports too, and a
    verdict on a candidate on its copy in findings.json, so both lists agree. When that copy also
    reports another candidate of the same persona, title, location and description, give the
    verdict to the copy with `--index`. Verdicts given on one session at once take turns.

    `--adjudicator` records who gave the verdict: `human`, the default, or `agent`, which an AI
    agent passes and the MCP `verify_finding` tool always sends. An agent cannot change a
    person's verdict. Only a person's verdict ranks review history, teaches the learned catalog
    (INVALIDATED) or records a mitigation in the ledger (MITIGATED). A later verdict withdraws
    what the finding's earlier verdicts recorded there that it no longer stands behind: the
    catalog entry once the finding is not INVALIDATED, so later reviews stop suppressing its
    claim, and the ledger entry once it is not MITIGATED. An entry another verdict also recorded
    stays, and one nothing else recorded is removed.
    """
    new_status = status.upper().strip()
    if new_status not in _VERDICT_STATUSES:
        print_error(MESSAGES.review.invalid_status_choices, prefix=False)
        raise typer.Exit(1)
    if [index, title_pattern, candidate].count(None) != 2:
        print_error(MESSAGES.review.specify_one_finding, prefix=False)
        raise typer.Exit(1)

    session_dir = _require_session_dir(session or session_opt)
    verdict = Verdict(new_status, adjudicator, reason, tuple(perimeter or ()), regression_test)
    try:
        done = (
            _judge_candidate(session_dir, candidate, verdict)
            if candidate is not None
            else _judge_reported(session_dir, index, title_pattern, verdict)
        )
    except ValidationError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1) from None
    except (AssertionError, ValueError) as exc:
        print_error(f"Cannot update finding: verdict invariants violated: {exc}", prefix=False)
        raise typer.Exit(1) from None
    except OSError as exc:
        print_error(MESSAGES.review.session_write_failed.format(error=exc), prefix=False)
        raise typer.Exit(1) from None
    print_success(done)


# =============================================================================
# Command: devops review stats
# =============================================================================


def _tally_findings(
    findings: Sequence[HistoryFinding],
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """Count findings by status, and by persona in total and invalidated.

    A finding several personas raised is joined into one with their names comma-separated, and
    counts once for each of them.
    """
    by_status: dict[str, int] = {"VERIFIED": 0, "UNVERIFIED": 0, "INVALIDATED": 0, "MITIGATED": 0}
    by_persona_total: dict[str, int] = {}
    by_persona_invalidated: dict[str, int] = {}
    for f in findings:
        by_status[f.status] = by_status.get(f.status, 0) + 1
        raw_personas = [p.strip() for p in f.persona.split(",") if p.strip()]
        for persona in raw_personas or ["unknown"]:
            by_persona_total[persona] = by_persona_total.get(persona, 0) + 1
            if f.status == "INVALIDATED":
                by_persona_invalidated[persona] = by_persona_invalidated.get(persona, 0) + 1
    return by_status, by_persona_total, by_persona_invalidated


def _render_status_breakdown_table(by_status: dict[str, int], total_findings: int) -> None:
    """Render findings status distribution table."""
    status_rows = []
    for st, count in by_status.items():
        pct = (count / total_findings * 100) if total_findings else 0.0
        status_rows.append([st, str(count), f"{pct:.1f}%"])

    print_table(
        title="Finding Status Breakdown",
        columns=[("Status", "cyan"), ("Count", "right"), ("Percentage", "right")],
        rows=status_rows,
    )


def _render_persona_stats_table(
    by_persona_total: dict[str, int], by_persona_invalidated: dict[str, int]
) -> None:
    """Render per-persona false-positive rate table."""
    if not by_persona_total:
        return
    persona_rows = []
    for persona, count in by_persona_total.items():
        inval = by_persona_invalidated.get(persona, 0)
        rate = (inval / count * 100) if count else 0.0
        persona_rows.append([persona, str(count), str(inval), f"{rate:.1f}%"])

    print_table(
        title="Persona False Positive Rate (Invalidated)",
        columns=[
            ("Persona", "magenta"),
            ("Total Findings", "right"),
            ("Invalidated", "right"),
            ("False-Positive Rate", "right"),
        ],
        rows=persona_rows,
    )


def _render_category_stats_table(category_metrics: dict[str, Any]) -> None:
    """Render per-category false-positive rate table across historical review runs."""
    if not category_metrics:
        return
    cat_rows = []
    for cat, metric in category_metrics.items():
        cat_rows.append(
            [
                cat,
                str(metric.total),
                str(metric.invalidated),
                str(metric.verified),
                f"{metric.false_positive_rate:.1f}%",
            ]
        )

    print_table(
        title="Category False Positive Rate (Invalidated)",
        columns=[
            ("Category", "cyan"),
            ("Total Findings", "right"),
            ("Invalidated", "right"),
            ("Verified", "right"),
            ("False-Positive Rate", "right"),
        ],
        rows=cat_rows,
    )


@app.command("stats")
def review_stats(
    reviews_dir: Annotated[
        Path | None,
        typer.Option("--reviews-dir", help=HELP.review.reviews_dir),
    ] = None,
) -> None:
    """Compute and display review accuracy statistics across saved sessions."""
    r_dir = reviews_dir or runner._get_reviews_base_dir()
    if not r_dir.exists():
        print_warning(MESSAGES.review.no_review_dir_found, prefix=False)
        raise typer.Exit(0)

    # Each subject counts once. Findings come from findings.json: the reported findings, with
    # the verdicts `devops review verify` gave them, and the candidates a VERIFIED or MITIGATED
    # verdict moved there. A verdict on a candidate kept out of findings.json ranks its session
    # in history, but these figures do not count the candidate.
    history = load_review_history(r_dir)
    if not history.sessions:
        print_warning(MESSAGES.review.no_saved_sessions, prefix=False)
        raise typer.Exit(0)

    findings = [f for session in history.counted for f in session.findings]
    by_status, by_persona_total, by_persona_invalidated = _tally_findings(findings)

    print_section(" AI Code Review Accuracy & Verification Stats ", style="bold cyan")
    print_info(
        MESSAGES.review.sessions_counted.format(
            total=len(history.sessions),
            counted=len(history.counted),
            repeats=history.repeats,
            target_only=history.target_only,
            unkeyed=history.unkeyed,
        ),
        prefix=False,
    )
    print_info(MESSAGES.review.total_findings_count.format(count=len(findings)), prefix=False)

    _render_status_breakdown_table(by_status, len(findings))
    _render_persona_stats_table(by_persona_total, by_persona_invalidated)

    from devops_cli.ai.review.category_metrics import compute_category_metrics

    category_metrics = compute_category_metrics(findings)
    _render_category_stats_table(category_metrics)


# =============================================================================
# Command: devops review benchmark
# =============================================================================


def _backend_host(served_by: str) -> str:
    """Shorten a serving backend's API base to its host, and an in-cluster host to its pod or service."""
    host = urlparse(served_by).hostname or served_by
    return host.split(".", 1)[0] if host.endswith(".svc.cluster.local") else host


def _busy_shares(stage: StageSummary) -> str:
    """Each backend's share of the stage it spent serving calls, busiest first, with its peak."""
    shares = sorted(stage.backend_busy_share.items(), key=lambda item: -item[1])
    return ", ".join(
        f"{_backend_host(backend)} {share:.0%} ×{stage.backend_peak_concurrency.get(backend, 0)}"
        for backend, share in shares
    )


def _render_benchmark(summary: BenchmarkSummary, saved: Path) -> None:
    """Show the median review and the median of each stage."""
    per_candidate = summary.median_seconds_per_candidate
    print_section(" Review Benchmark ", style="bold cyan")
    median = format_duration(summary.median_wall_seconds)
    print_info(
        f"[bold]{summary.runs} run(s)[/bold] over {escape_text(summary.target)} "
        f"({summary.files} files, corpus {summary.corpus_digest}): median {median}, "
        f"{summary.median_llm_calls:g} LLM calls, {summary.median_candidate_findings:g} candidate "
        f"and {summary.median_reported_findings:g} reported findings"
        + (f", {per_candidate:.1f}s per candidate" if per_candidate else ""),
        prefix=False,
    )
    if summary.static_analyzers:
        analyzers = ", ".join(
            f"{name} {' / '.join(states)}" for name, states in summary.static_analyzers.items()
        )
        print_info(f"Static analyzers: {escape_text(analyzers)}", prefix=False)
    rows = [
        [
            stage.name,
            f"{stage.median_wall_seconds:.1f}",
            f"{stage.median_llm_calls:g}",
            f"{stage.median_prompt_tokens:g}",
            f"{stage.median_completion_tokens:g}",
            ", ".join(
                f"{_backend_host(backend)} {calls}"
                for backend, calls in sorted(stage.backends.items(), key=lambda item: -item[1])
            ),
            _busy_shares(stage),
        ]
        for stage in summary.stages
    ]
    print_table(
        title="Median per Stage",
        columns=[
            ("Stage", "cyan"),
            ("Wall (s)", "right"),
            ("LLM Calls", "right"),
            ("Prompt Tokens", "right"),
            ("Completion Tokens", "right"),
            ("Backends (calls, all runs)", "magenta"),
            ("Busy (median share, peak in flight)", "magenta"),
        ],
        rows=rows,
    )
    print_success(f"Saved benchmark → [bold]{saved}[/bold]")


@app.command("benchmark")
def benchmark(
    targets: Annotated[
        list[Path],
        typer.Argument(help=HELP.review.benchmark_targets),
    ],
    runs: Annotated[
        int,
        typer.Option("--runs", "-n", min=1, help=HELP.review.benchmark_runs),
    ] = DEFAULT_REVIEW_BENCHMARK_RUNS,
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
    no_pre_analysis: Annotated[
        bool,
        typer.Option("--no-pre-analysis", help=HELP.review.no_pre_analysis),
    ] = False,
    no_static_scan: Annotated[
        bool,
        typer.Option("--no-static-scan", help=HELP.review.no_static_scan),
    ] = False,
    concurrency: Annotated[
        int | None,
        typer.Option("--concurrency", "-c", help=HELP.review.concurrency),
    ] = None,
) -> None:
    """Review the same files several times and report median time, LLM calls, tokens and backend busy share per stage."""
    # Each run bypasses the response cache and writes its session's profile.json. Findings vary
    # between identical runs, so the summary takes medians, and time per candidate finding
    # normalises for runs that happen to verify more findings.
    with collect_profiles() as profiles:
        for run in range(1, runs + 1):
            print_section(f" Benchmark Run {run}/{runs} ", style="bold cyan")
            path(
                targets=targets,
                pattern=pattern,
                persona=persona,
                all_personas=all_personas,
                no_pre_analysis=no_pre_analysis,
                no_static_scan=no_static_scan,
                no_cache=True,
                concurrency=concurrency,
            )
    if not profiles:
        print_warning("No review was profiled; check that the targets contain files to review.")
        raise typer.Exit(1)
    summary = summarize_profiles(profiles)
    summary.corpus_digest = _corpus_digest(targets, pattern)
    _render_benchmark(summary, summary.write(runner._get_reviews_base_dir()))
    setup = review_setup(
        persona=persona.value if persona else None,
        all_personas=all_personas,
        pre_analysis=not no_pre_analysis,
        static_scan=not no_static_scan,
        concurrency=concurrency,
    )
    subject = {"corpus_digest": summary.corpus_digest, "target": Path(summary.target).name}
    announce_run(
        record_run(
            Mechanism.REVIEW_BENCHMARK,
            setup=setup,
            subject=subject,
            results=summary.model_dump(mode="json"),
        )
    )


# =============================================================================
# Commands: devops review corpus generate | score
# =============================================================================

corpus_app = new_typer(help=HELP.review.corpus, no_args_is_help=True)
app.add_typer(corpus_app, name="corpus")

CORPORA_DIRNAME = "corpora"


def _corpus_sources(sources: list[Path], pattern: str) -> list[tuple[Path, str]]:
    """The files a review of each source reads, under the source's name in the corpus."""
    files: list[tuple[Path, str]] = []
    for source in sources:
        root = source.resolve()
        if root.is_file():
            files.append((root, root.name))
            continue
        files.extend(
            (path, f"{root.name}/{path.relative_to(root).as_posix()}")
            for path in _review_candidate_files(root, pattern)
        )
    return files


@corpus_app.command("generate")
def corpus_generate(
    sources: Annotated[list[Path], typer.Argument(help=HELP.review.corpus_source)],
    out: Annotated[
        Path | None,
        typer.Option("--out", "-o", help=HELP.review.corpus_out),
    ] = None,
    seed: Annotated[
        int,
        typer.Option("--seed", help=HELP.review.corpus_seed),
    ] = DEFAULT_REVIEW_CORPUS_SEED,
    pattern: Annotated[
        str,
        typer.Option("--pattern", "-g", help=HELP.options.pattern),
    ] = DEFAULT_MATCH_ALL_PATTERN,
    template: Annotated[
        list[str] | None,
        typer.Option("--template", "-t", help=HELP.review.corpus_template),
    ] = None,
) -> None:
    """Copy source files with one known defect injected into each, and record where."""
    try:
        templates = select_templates(template)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc
    names = [source.resolve().name for source in sources]
    corpus_dir = out or runner._get_reviews_base_dir() / CORPORA_DIRNAME / (
        f"{'-'.join(names)}-{seed}"
    )
    if corpus_dir.exists() and any(corpus_dir.iterdir()):
        print_error(f"{corpus_dir} already exists; choose another --seed or --out.")
        raise typer.Exit(1)
    if len(set(names)) < len(names):
        print_error(
            f"Sources must have distinct names, since each is a folder of the corpus: {names}"
        )
        raise typer.Exit(1)
    corpus = generate_corpus(
        _corpus_sources(sources, pattern),
        corpus_dir,
        sources=[str(source.resolve()) for source in sources],
        seed=seed,
        # One set of conventions serves the corpus: the first source's, as its review would read.
        conventions=_nearest_conventions(sources[0]),
        review_conventions=nearest_review_conventions(sources[0]),
        templates=templates,
    )
    if not corpus.injections:
        print_warning("No source file had a place for the selected defect templates.")
        raise typer.Exit(1)
    counts: dict[str, int] = {}
    for injection in corpus.injections:
        counts[injection.template] = counts.get(injection.template, 0) + 1
    print_table(
        title=f"{len(corpus.injections)} Injected Defect(s)",
        columns=[("Template", "cyan"), ("Injections", "right")],
        rows=[[name, str(count)] for name, count in sorted(counts.items())],
    )
    files_dir = corpus_dir / CORPUS_FILES_DIR
    print_success(f"Corpus written → [bold]{corpus_dir}[/bold]")
    print_info(f"Review it:  devops review path {files_dir} --all", prefix=False)
    print_info(f"Score it:   devops review corpus score {corpus_dir}", prefix=False)
    print_info(f"[dim]{corpus.caveat}[/dim]", prefix=False)


def _corpus_session_dirs(files_dir: Path) -> list[Path]:
    """Every session whose profile shows it reviewed the corpus, oldest first."""
    reviews_dir = runner._get_reviews_base_dir()
    if not reviews_dir.exists():
        return []
    target = str(files_dir.resolve())
    reviews = [
        d
        for d in reviews_dir.iterdir()
        if (d / "findings.json").exists()
        and (profile := ReviewProfile.load(d)) is not None
        and profile.target == target
    ]
    return sorted(reviews, key=lambda d: d.name)


def _named_session_dirs(sessions: list[str]) -> list[Path]:
    """The named sessions, oldest first; a name that matches no reviewed session exits 1."""
    found = {name: _find_session_dir(name) for name in dict.fromkeys(sessions)}
    dirs = {d: None for d in found.values() if d is not None and (d / "findings.json").exists()}
    if missing := [name for name, d in found.items() if d not in dirs]:
        print_error(f"No review session with findings matches: {', '.join(missing)}")
        raise typer.Exit(1)
    return sorted(dirs, key=lambda d: d.name)


def _arm_session_dirs(files_dir: Path, sessions: list[str] | None, runs: int | None) -> list[Path]:
    """The sessions of one arm: those named, the latest `runs` reviews of the corpus, or the
    latest one."""
    if sessions and runs is not None:
        print_error("Name sessions with --session or take the latest with --runs, not both.")
        raise typer.Exit(1)
    if sessions:
        return _named_session_dirs(sessions)
    reviews = _corpus_session_dirs(files_dir)
    if runs is not None and len(reviews) < runs:
        print_error(
            f"Only {len(reviews)} review(s) of {files_dir} exist, and --runs asks for {runs}; "
            f"run: devops review benchmark {files_dir} --runs {runs}"
        )
        raise typer.Exit(1)
    if not reviews:
        print_error(f"No review of {files_dir} found; run: devops review path {files_dir}")
        raise typer.Exit(1)
    return reviews[-(runs or 1) :]


def _session_findings(path: Path) -> list[SavedFinding]:
    return ReviewSessionPayload.model_validate_json(path.read_text(encoding="utf-8")).findings


def _replied_personas(profiles: list[ReviewProfile | None]) -> list[str]:
    """Every persona that replied in any of the sessions."""
    return sorted(
        {
            reply["persona"]
            for p in profiles
            if p
            for reply in p.persona_replies
            if "persona" in reply
        }
    )


def _out_of(count: int, whole: int, share: float) -> str:
    return f"{count}/{whole} ({share:.0%})"


def _render_arm_totals(arm: CorpusRunsScore) -> None:
    """How many injections the arm's runs caught: in at least one run, in every run, in none."""
    whole, k = len(arm.tallies), arm.runs
    rows = []
    for label, total, counts in (
        ("Found", arm.found, [t.found_in for t in arm.tallies]),
        ("Still reported after verification", arm.reported, [t.reported_in for t in arm.tallies]),
    ):
        rows.append(
            [
                label,
                _out_of(sum(c > 0 for c in counts), whole, total.pass_at_k),
                _out_of(sum(c == k for c in counts), whole, total.pass_hat_k),
                str(total.in_none),
            ]
        )
    print_table(
        title=f"Injections Caught Across {k} Run(s)",
        columns=[
            ("Outcome", "cyan"),
            (f"In at least one run (pass@{k})", "right"),
            (f"In every run (pass^{k})", "right"),
            ("In no run", "right"),
        ],
        rows=rows,
    )


def _render_arm_means(arm: CorpusRunsScore) -> None:
    """The mean of each figure across the runs, beside its range; one run has no range."""
    spread = arm.spread or {}
    print_table(
        title="Mean per Run",
        columns=[("Figure", "cyan"), ("Mean", "right"), ("Range across runs", "right")],
        rows=[
            [
                name,
                f"{getattr(arm, name):g}",
                f"{spread[name][0]:g}–{spread[name][1]:g}" if name in spread else "—",
            ]
            for name in RUN_FIGURE_DECIMALS
        ],
    )


def _render_arm_sessions(arm: CorpusRunsScore) -> None:
    print_table(
        title="Runs",
        columns=[
            ("Session", "magenta"),
            ("Recall found", "right"),
            ("Recall reported", "right"),
            ("Candidates", "right"),
            ("Invalidated by the verifier", "right"),
            ("Reported", "right"),
            ("Prompt tokens", "right"),
            ("Completion tokens", "right"),
            ("Unparsed persona replies", "right"),
        ],
        rows=[
            [
                row.session_id,
                f"{row.recall_found:.0%}",
                f"{row.recall_reported:.0%}",
                str(row.candidate_findings),
                str(row.invalidated_findings),
                str(row.reported_findings),
                str(row.prompt_tokens),
                str(row.completion_tokens),
                str(row.unparsed_replies),
            ]
            for row in arm.sessions
        ],
    )


def _render_arm_templates(arm: CorpusRunsScore) -> None:
    by_template: dict[str, list[int]] = {}
    for tally in arm.tallies:
        counts = by_template.setdefault(tally.template, [0, 0, 0])
        counts[0] += 1
        counts[1] += tally.found_in > 0
        counts[2] += tally.found_in == arm.runs
    print_table(
        title="By Template",
        columns=[
            ("Template", "cyan"),
            ("Injections", "right"),
            ("Found in any run", "right"),
            ("Found in every run", "right"),
        ],
        rows=[[name, *map(str, counts)] for name, counts in sorted(by_template.items())],
    )


def _render_arm_injections(arm: CorpusRunsScore) -> None:
    """Each injection: in how many runs it was found and reported, and every finding matched."""
    titles: dict[str, dict[str, None]] = {}
    for outcome in (outcome for score in arm.scores for outcome in score.outcomes):
        titles.setdefault(outcome.id, {}).update(dict.fromkeys(outcome.titles))
    print_table(
        title="Injections",
        columns=[
            ("Injection", "magenta"),
            ("Template", "cyan"),
            ("Found", "right"),
            ("Reported", "right"),
            ("Matched findings (any run)", "dim"),
        ],
        rows=[
            [
                escape_text(f"{t.file}:{t.line}"),
                t.template,
                f"found in {t.found_in}/{arm.runs}",
                f"reported in {t.reported_in}/{arm.runs}",
                escape_text("; ".join(titles.get(t.id, {}))),
            ]
            for t in arm.tallies
        ],
    )


def _render_corpus_runs(arm: CorpusRunsScore) -> None:
    print_section(
        f" Synthetic Defect Recall: {arm.runs} run(s), prompts {arm.prompt_digest or 'unrecorded'} ",
        style="bold cyan",
    )
    _render_arm_totals(arm)
    _render_arm_means(arm)
    _render_arm_sessions(arm)
    _render_arm_templates(arm)
    _render_arm_injections(arm)
    print_info(f"[dim]{arm.caveat}[/dim]", prefix=False)


def _warn_unpinned(setup: dict[str, Any], *, to_stderr: bool) -> None:
    """Say when a gateway group the review used serves several models, so runs mix models."""
    for group, models in unpinned_groups(setup).items():
        print_warning(
            f"not model-pinned: {group} serves {models} models, so its runs mix them; pin one "
            "model with a single-model gateway group to compare prompts.",
            prefix=False,
            to_stderr=to_stderr,
        )


@corpus_app.command("score")
def corpus_score(
    corpus_dir: Annotated[Path, typer.Argument(help=HELP.review.corpus_dir)],
    session: Annotated[
        list[str] | None,
        typer.Option("--session", "-s", help=HELP.review.corpus_session),
    ] = None,
    runs: Annotated[
        int | None,
        typer.Option("--runs", "-n", min=1, help=HELP.review.corpus_runs),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Score one arm of reviews of a corpus: which injected defects each run found, and what verification kept."""
    try:
        corpus = DefectCorpus.load(corpus_dir)
    except (OSError, ValueError) as exc:
        print_error(f"No corpus manifest in {corpus_dir}: {exc}")
        raise typer.Exit(1) from exc
    session_dirs = _arm_session_dirs(corpus_dir / CORPUS_FILES_DIR, session, runs)
    profiles = [ReviewProfile.load(d) for d in session_dirs]
    try:
        arm = score_corpus_runs([_scored_session(corpus, d.name) for d in session_dirs], profiles)
    except ValidationError as exc:
        print_error(exc.message)
        raise typer.Exit(1) from exc
    # The setup is read when scoring, so score a review before changing its models or pool.
    setup = review_setup(
        prompt_digest=arm.prompt_digest, runs=arm.runs, personas=_replied_personas(profiles)
    )
    saved = record_run(
        Mechanism.CORPUS_SCORE,
        setup=setup,
        subject={"corpus_digest": digest(corpus.model_dump(mode="json", exclude={"created_at"}))},
        results=arm.model_dump(mode="json"),
    )
    if json_output:
        write_stdout(arm.model_dump_json(indent=2) + "\n")
    else:
        _render_corpus_runs(arm)
    _warn_unpinned(setup, to_stderr=json_output)
    announce_run(saved, to_stderr=json_output)


# =============================================================================
# Commands: devops review samples list | fetch
# =============================================================================

samples_app = new_typer(help=HELP.review.samples, no_args_is_help=True)
app.add_typer(samples_app, name="samples")


SAMPLE_VALIDATIONS_DIRNAME = "sample-validations"


def _select_samples(
    names: list[str] | None, categories: list[SampleCategory] | None
) -> list[SampleRepository]:
    try:
        return load_sample_catalog().select(names, categories)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc


@samples_app.command("list")
def samples_list(
    category: Annotated[
        list[SampleCategory] | None,
        typer.Option("--category", "-c", help=HELP.review.samples_category),
    ] = None,
) -> None:
    """List the sample catalog, and whether each sample is fetched at its commit."""
    root = samples_dir()
    samples = load_sample_catalog().select(categories=category)
    print_table(
        title=f"{len(samples)} Sample Repositories ({root})",
        columns=[
            ("Name", "cyan"),
            ("Category", ""),
            ("Languages", ""),
            ("Licence", ""),
            ("Commit", "dim"),
            ("Paths", ""),
            ("Fetched", ""),
        ],
        rows=[
            [
                sample.name,
                sample.category.value,
                ", ".join(sample.languages),
                sample.license,
                sample.commit[:12],
                ", ".join(sample.paths),
                "no" if checkout_problems(sample, root / sample.name) else "yes",
            ]
            for sample in samples
        ],
    )


@samples_app.command("fetch")
def samples_fetch(
    names: Annotated[
        list[str] | None,
        typer.Argument(help=HELP.review.samples_names, show_default=False),
    ] = None,
    category: Annotated[
        list[SampleCategory] | None,
        typer.Option("--category", "-c", help=HELP.review.samples_category),
    ] = None,
) -> None:
    """Fetch samples at their pinned commits, verifying commit, licence files and paths."""
    samples = _select_samples(names, category)
    root = samples_dir()
    if is_dry_run():
        for sample in samples:
            print_info(f"Would fetch {sample.repository} at {sample.commit} → {root / sample.name}")
        return
    failed = 0
    for sample in samples:
        problems = fetch_sample(sample, root)
        if problems:
            failed += 1
            print_error(f"{sample.name}: {'; '.join(problems)}")
        else:
            print_success(f"{sample.name} at {sample.commit[:12]} → {root / sample.name}")
    if failed:
        raise typer.Exit(1)


def _by_category(samples: list[SampleRepository]) -> dict[str, list[SampleRepository]]:
    groups: dict[str, list[SampleRepository]] = {}
    for sample in samples:
        groups.setdefault(sample.category.value, []).append(sample)
    return groups


def _scored_session(corpus: DefectCorpus, session_id: str) -> CorpusScore:
    session_dir = runner._get_reviews_base_dir() / session_id
    reported = _session_findings(session_dir / "findings.json")
    candidates_file = session_dir / CONST_REVIEW_CANDIDATES_FILENAME
    candidates = _session_findings(candidates_file) if candidates_file.exists() else reported
    return score_corpus(corpus, candidates, reported, session_id=session_id)


def _review_sample_corpus(
    samples: list[SampleRepository], root: Path, corpus_dir: Path, seed: int, all_personas: bool
) -> CorpusReview:
    """Inject the category's defects into copies of its samples, review them and score it."""
    files = [
        (file, f"{sample.name}/{file.relative_to(root / sample.name).as_posix()}")
        for sample in samples
        for file in sample_files(sample, root / sample.name)
    ]
    corpus = generate_corpus(
        files, corpus_dir, sources=[str(root / sample.name) for sample in samples], seed=seed
    )
    review = CorpusReview(corpus_dir=str(corpus_dir), injections=len(corpus.injections))
    if not corpus.injections:
        return review
    try:
        with collect_profiles() as profiles:
            path(targets=[corpus_dir / CORPUS_FILES_DIR], all_personas=all_personas, no_cache=True)
    except typer.Exit as exc:
        return review.model_copy(update={"error": f"the review exited with {exc.exit_code}"})
    if not profiles:
        return review.model_copy(update={"error": "the review wrote no session"})
    session_id = profiles[-1].session_id
    return review.model_copy(
        update={"session_id": session_id, "score": _scored_session(corpus, session_id)}
    )


def _review_cell(report: CategoryReport) -> str:
    review = report.review
    if review is None:
        return "-"
    if review.score is None:
        return review.error or f"{review.injections} injected"
    score = review.score
    return f"{score.found}/{score.reported}/{score.injections}"


def _render_validation(reports: list[CategoryReport], run_dir: Path) -> None:
    print_table(
        title="devops ai Tooling on the Sample Repositories",
        columns=[
            ("Category", "cyan"),
            ("Files", "right"),
            ("Parsers", ""),
            ("Symbols", "right"),
            ("Repomap files", "right"),
            ("Review found/reported/injected", ""),
            ("Problems", "right"),
        ],
        rows=[
            [
                report.category,
                str(len(report.files)),
                ", ".join(f"{name} {count}" for name, count in sorted(report.parsers.items())),
                str(sum(result.symbols for result in report.files)),
                str(sum(repomap.files_mapped for repomap in report.repomaps)),
                _review_cell(report),
                str(len(report.problems)),
            ]
            for report in reports
        ],
    )
    for report in reports:
        for problem in report.problems:
            print_warning(f"{report.category}: {problem}", prefix=False)
    print_success(f"Reports saved → [bold]{run_dir}[/bold]")


@samples_app.command("validate")
def samples_validate(
    names: Annotated[
        list[str] | None,
        typer.Argument(help=HELP.review.samples_validate_names, show_default=False),
    ] = None,
    category: Annotated[
        list[SampleCategory] | None,
        typer.Option("--category", "-c", help=HELP.review.samples_category),
    ] = None,
    review: Annotated[
        bool,
        typer.Option("--review", help=HELP.review.samples_review),
    ] = False,
    all_personas: Annotated[
        bool,
        typer.Option("--all", help=HELP.options.all_personas),
    ] = False,
    seed: Annotated[
        int,
        typer.Option("--seed", help=HELP.review.corpus_seed),
    ] = DEFAULT_REVIEW_CORPUS_SEED,
) -> None:
    """Run devops ai tooling over fetched samples and save a JSON report per category."""
    samples = _select_samples(names, category)
    root = samples_dir()
    unfetched = [s.name for s in samples if checkout_problems(s, root / s.name)]
    if unfetched:
        print_error(
            f"Not fetched at their pinned commits: {', '.join(unfetched)}. "
            f"Run: devops review samples fetch {' '.join(unfetched)}"
        )
        raise typer.Exit(1)
    run_dir = (
        runner._get_reviews_base_dir()
        / SAMPLE_VALIDATIONS_DIRNAME
        / datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    )
    reports: list[CategoryReport] = []
    for category_name, group in _by_category(samples).items():
        report = validate_category(category_name, group, root)
        if review:
            corpus_dir = run_dir / f"{category_name}-corpus"
            report.review = _review_sample_corpus(group, root, corpus_dir, seed, all_personas)
            report.problems += review_problems(report.review)
        report.write(run_dir)
        reports.append(report)
    _render_validation(reports, run_dir)
    setup = {"review": review, "seed": seed, "all_personas": all_personas}
    if review:
        setup |= review_setup()
    records = [
        new_run(
            Mechanism.SAMPLE_VALIDATION,
            setup=setup,
            subject={"category": report.category, "samples": report.samples},
            results=report.model_dump(mode="json"),
        )
        for report in reports
    ]
    announce_runs(keep_runs(records))


# =============================================================================
# Commands: devops review templates list | check | sweep
# =============================================================================

templates_app = new_typer(help=HELP.review.templates, no_args_is_help=True)
app.add_typer(templates_app, name="templates")


def _render_templates_table(templates: tuple[DefectTemplate, ...]) -> None:
    rows = []
    for t in templates:
        suffixes = sorted({s for sfx_group, _ in t.finders for s in sfx_group})
        rows.append([t.name, t.severity, ", ".join(suffixes), t.description])
    print_table(
        title="Synthetic Defect Templates",
        columns=[
            ("Template", "cyan"),
            ("Severity", "magenta"),
            ("Suffixes / Languages", "green"),
            ("Description", "white"),
        ],
        rows=rows,
    )


def _render_sweep_summary(report: TemplateSweepReport) -> None:
    status_str = "[green]✓ Pass[/green]" if report.passed else "[red]✗ Fail[/red]"
    rows = [
        ["Samples Checked", str(report.samples_checked)],
        ["Files Checked", str(report.files_checked)],
        ["Total Sites Found", str(report.total_sites)],
        ["Tested Mutations", str(sum(report.checkers_run.values()))],
        ["Untested Sites (Missing Checkers)", str(sum(report.checkers_not_run.values()))],
        ["Parse Failures", str(len(report.parse_failures))],
        ["Comment Collisions", str(len(report.comment_collisions))],
        ["Overall Verdict", status_str],
    ]
    print_table(
        title="Defect Template Sweep Summary",
        columns=[("Metric", "cyan"), ("Value", "white")],
        rows=rows,
    )


def _render_sweep_breakdowns(report: TemplateSweepReport) -> None:
    if report.sites_per_template:
        t_rows = [
            [t, str(c)] for t, c in sorted(report.sites_per_template.items(), key=lambda x: -x[1])
        ]
        print_table(
            title="Sites per Template",
            columns=[("Template", "cyan"), ("Sites", "right")],
            rows=t_rows,
        )
    if report.sites_per_category:
        c_rows = [
            [c, str(n)] for c, n in sorted(report.sites_per_category.items(), key=lambda x: -x[1])
        ]
        print_table(
            title="Sites per Category",
            columns=[("Category", "magenta"), ("Sites", "right")],
            rows=c_rows,
        )
    ch_rows = [
        [ch, str(n), "[green]Run[/green]"] for ch, n in sorted(report.checkers_run.items())
    ] + [
        [ch, str(n), "[yellow]Not Run (missing tool)[/yellow]"]
        for ch, n in sorted(report.checkers_not_run.items())
    ]
    if ch_rows:
        print_table(
            title="Checker Execution Status",
            columns=[("Checker", "cyan"), ("Mutations", "right"), ("Status", "white")],
            rows=ch_rows,
        )


def _render_sweep_failures(report: TemplateSweepReport) -> None:
    if report.parse_failures:
        p_rows = [
            [
                f["template"],
                f["sample"],
                f"{f['file']}:{f['line']}",
                f["checker"],
                f.get("error", "") or "—",
            ]
            for f in report.parse_failures
        ]
        print_table(
            title="[red]Syntax Parse Failures[/red]",
            columns=[
                ("Template", "cyan"),
                ("Sample", "magenta"),
                ("Location", "yellow"),
                ("Checker", "white"),
                ("Error", "red"),
            ],
            rows=p_rows,
        )
    if report.comment_collisions:
        cc_rows = [
            [c["template"], c["sample"], f"{c['file']}:{c['line']}"]
            for c in report.comment_collisions
        ]
        print_table(
            title="[red]Comment Collisions[/red]",
            columns=[("Template", "cyan"), ("Sample", "magenta"), ("Location", "yellow")],
            rows=cc_rows,
        )


@templates_app.command("list")
def templates_list(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """List registered synthetic defect templates and their supported languages."""
    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        data = [
            {
                "name": t.name,
                "severity": t.severity,
                "description": t.description,
                "suffixes": sorted({s for sfx_group, _ in t.finders for s in sfx_group}),
            }
            for t in TEMPLATES
        ]
        emit_serialized(data, resolved)
        return
    _render_templates_table(TEMPLATES)


@templates_app.command("check")
@templates_app.command("sweep")
def templates_check(
    template: Annotated[
        list[str] | None,
        typer.Option("--template", "-t", help=HELP.review.templates_names),
    ] = None,
    category: Annotated[
        list[SampleCategory] | None,
        typer.Option("--category", "-c", help=HELP.review.samples_category),
    ] = None,
    sample: Annotated[
        list[str] | None,
        typer.Option("--sample", "-s", help="Specific sample name(s) to check."),
    ] = None,
    save: Annotated[
        bool,
        typer.Option("--save/--no-save", help=HELP.review.templates_save),
    ] = True,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Sweep synthetic defect templates over sample repositories, validating syntax and comment isolation."""
    try:
        templates = select_templates(template)
        samples = _select_samples(sample, category)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc

    root = samples_dir()
    unfetched = [s.name for s in samples if checkout_problems(s, root / s.name)]
    if unfetched:
        print_error(
            f"Not fetched at their pinned commits: {', '.join(unfetched)}. "
            f"Run: devops review samples fetch {' '.join(unfetched)}"
        )
        raise typer.Exit(1)

    report = sweep_templates(samples=samples, templates=templates, root=root)

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.model_dump(mode="json"), resolved)
    else:
        _render_sweep_summary(report)
        _render_sweep_breakdowns(report)
        _render_sweep_failures(report)

    if save:
        saved = save_sweep_run(report, templates, samples, root=None)
        announce_run(saved, to_stderr=(resolved != CONST_OUTPUT_FORMAT_TABLE))

    if not report.passed:
        print_error(
            "Defect template sweep failed: one or more mutations failed syntax checks or collided with comments."
        )
        raise typer.Exit(1)

    if resolved == CONST_OUTPUT_FORMAT_TABLE:
        print_success("Defect template well-formedness sweep passed across all evaluated samples.")


hallucinations_app = new_typer(help=HELP.review.hallucinations, no_args_is_help=True)
app.add_typer(hallucinations_app, name="hallucinations")


@hallucinations_app.command("list")
def hallucinations_list(
    learned_only: Annotated[
        bool,
        typer.Option("--learned", help=HELP.review.hallucinations_learned_only),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """List catalog entries: builtin ones shipped with the tool, and learned ones from this workspace."""
    from devops_cli.ai.review.common_hallucinations import load_common_hallucinations

    entries = load_common_hallucinations(include_builtin=not learned_only)
    entries.sort(key=lambda e: (e.source == "builtin", -e.occurrence_count, e.id))
    if json_output:
        write_stdout(json.dumps([e.model_dump(mode="json") for e in entries], indent=2) + "\n")
        return
    print_table(
        title=f"Hallucinations Catalog ({len(entries)} entries)",
        columns=[
            ("Id", "cyan"),
            ("Source", ""),
            ("Category", ""),
            ("Seen", "right"),
            ("Last Seen", "dim"),
            ("Name", ""),
        ],
        rows=[
            [
                e.id,
                e.source,
                str(e.category),
                str(e.occurrence_count),
                e.last_seen[:10],
                escape_text(e.name[:70]),
            ]
            for e in entries
        ],
    )


@hallucinations_app.command("remove")
def hallucinations_remove(
    ids: Annotated[
        list[str] | None,
        typer.Argument(help=HELP.review.hallucination_ids),
    ] = None,
    all_learned: Annotated[
        bool,
        typer.Option("--all-learned", help=HELP.review.hallucinations_all_learned),
    ] = False,
) -> None:
    """Remove learned catalog entries; builtin entries cannot be removed."""
    from devops_cli.ai.review.common_hallucinations import (
        _builtin_ids,
        remove_learned_hallucinations,
    )

    if not ids and not all_learned:
        print_error("Name the learned entries to remove, or pass --all-learned.")
        raise typer.Exit(1)
    if builtin := sorted(set(ids or ()) & _builtin_ids()):
        print_error(f"Builtin entries ship with the tool and cannot be removed: {builtin}")
        raise typer.Exit(1)
    removed = remove_learned_hallucinations(None if all_learned else ids)
    missing = sorted(set(ids or ()) - set(removed))
    if missing:
        print_warning(f"No learned entry with id: {missing}")
    print_success(f"Removed {len(removed)} learned entr{'y' if len(removed) == 1 else 'ies'}.")


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
    """Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads.

    Each session's findings.json and candidates.json are read, and only the findings whose
    verdict the dataset does not hold yet are appended. An export that finds none leaves the
    dataset as it was. Without --status only INVALIDATED verdicts are exported. The dataset
    changes no prompt and no later review.
    """
    status_filter = None if status.upper() == "ALL" else status.upper()
    from devops_cli.ai.review.exporter import export_invalidated_feedback

    count, out_path = export_invalidated_feedback(
        reviews_dir=reviews_dir, output_file=output, status_filter=status_filter
    )
    if count == 0:
        target_dir = reviews_dir or runner._get_reviews_base_dir()
        print_warning(
            MESSAGES.review.no_findings_to_export.format(
                status=status, target=target_dir, path=out_path
            ),
            prefix=False,
        )
    else:
        print_success(
            MESSAGES.review.exported_findings.format(count=count, status=status, path=out_path)
        )
