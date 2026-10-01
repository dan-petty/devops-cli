"""Codebase metadata analysis commands (branch, pr, path)."""

from __future__ import annotations

import fnmatch
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.ai.analyze.cache import (
    _render_analysis_summary,
    analysis_directory,
    save_analysis_metadata,
)
from devops_cli.ai.analyze.scanner import detect_language, sanitize_reference
from devops_cli.ai.client import LLMClient
from devops_cli.config.constants import (
    CONST_GIT_MAIN_BRANCH,
    CONST_MAX_FILE_SIZE_BYTES,
    CONST_SAFE_GIT_REF_PATTERN,
    CONST_SAFE_GIT_RELPATH_PATTERN,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_MATCH_ALL_PATTERN,
)
from devops_cli.config.settings import get_ai_api_key, get_github_token, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import (
    find_repo_root,
    get_repo_origin_name,
    list_repo_files,
)
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import HELP, MESSAGES
from devops_cli.models.ai import AnalysisMetadata, FileAnalysisMeta
from devops_cli.output.console import print_error, print_info

app = new_typer(
    help=HELP.analyze.app,
    no_args_is_help=True,
)


def __getattr__(name: str) -> Any:
    if name in {"detect_language", "sanitize_reference", "scan_directory"}:
        import devops_cli.ai.analyze.scanner as sc

        return getattr(sc, name)
    if name == "analyze_single_file":
        from devops_cli.ai.analyze.outlines import analyze_single_file

        return analyze_single_file
    if name in {"load_cached_analysis", "save_analysis_metadata"}:
        import devops_cli.ai.analyze.cache as ca

        return getattr(ca, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# =============================================================================
# File Metadata Extraction & Cache Re-use Helpers
# =============================================================================


def _create_deleted_file_meta(rel_path: str) -> FileAnalysisMeta:
    """Create a FileAnalysisMeta instance representing a deleted repository file."""
    return FileAnalysisMeta(
        path=rel_path,
        size_bytes=0,
        line_count=0,
        char_count=0,
        language=detect_language(rel_path),
        primary_purpose=f"Deleted file {Path(rel_path).name}",
        key_symbols=[],
        dependencies=[],
        change_type="deleted",
        pseudocode=None,
        last_updated=None,
        complexity_score=None,
    )


def _try_reuse_cached_file_meta(
    old_meta: FileAnalysisMeta, file_mtime: datetime
) -> FileAnalysisMeta | None:
    """Attempt to reuse cached analysis metadata if file has not been modified."""
    if not (old_meta.last_analyzed and old_meta.pseudocode):
        return None
    try:
        analyzed_dt = datetime.fromisoformat(old_meta.last_analyzed)
        if file_mtime <= analyzed_dt:
            return old_meta.model_copy(update={"last_analyzed": datetime.now(UTC).isoformat()})
    except Exception:
        pass
    return None


def _process_single_repo_file_meta(
    p: Path,
    repo: Path,
    enhanced: bool,
    existing_file_metas: dict[str, FileAnalysisMeta],
    ai_client: LLMClient | None,
) -> FileAnalysisMeta | None:
    """Analyze a single file for repository-wide or path analysis."""
    try:
        if not p.resolve().is_relative_to(repo.resolve()):
            return None
        if p.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
            return None
        rel_str = str(p.relative_to(repo)) if p.is_relative_to(repo) else str(p)
        file_mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC)

        if enhanced and rel_str in existing_file_metas:
            reused = _try_reuse_cached_file_meta(existing_file_metas[rel_str], file_mtime)
            if reused is not None:
                return reused

        content = p.read_text(encoding="utf-8", errors="replace")
        from devops_cli.ai.analyze.outlines import analyze_single_file

        return analyze_single_file(
            rel_str,
            content,
            p.stat().st_size,
            enhanced=enhanced,
            repo_root=repo,
            ai_client=ai_client,
        )
    except Exception:
        return None


def _fetch_git_file_content(repo: Path, revision: str, rel_path: str) -> str | None:
    """Fetch content of a file at a specific git revision using git show."""
    if not revision or revision.startswith("-") or not rel_path or rel_path.startswith("-"):
        return None
    if not CONST_SAFE_GIT_REF_PATTERN.match(revision):
        return None
    if not CONST_SAFE_GIT_RELPATH_PATTERN.match(rel_path):
        return None
    if ".." in Path(rel_path).parts:
        return None
    try:
        from devops_cli.core.process import run_subprocess

        # No "--": git would read "<rev>:<path>" as a pathspec; both parts are validated above.
        proc = run_subprocess(["git", "--no-pager", "show", f"{revision}:{rel_path}"], cwd=repo)
        if proc.returncode == 0:
            return proc.stdout
    except Exception:
        pass
    return None


def _resolve_merge_base(repo: Path, base: str | None, head: str | None = None) -> str | None:
    """Resolve git merge-base between base and target branch/HEAD."""
    if not base or base.startswith("-") or not CONST_SAFE_GIT_REF_PATTERN.match(base):
        return None
    ref = head or "HEAD"
    if ref.startswith("-") or not CONST_SAFE_GIT_REF_PATTERN.match(ref):
        return None
    try:
        from devops_cli.core.process import run_subprocess

        proc = run_subprocess(["git", "merge-base", "--", base, ref], cwd=repo)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        pass
    return base


def _apply_symbol_delta_to_meta(
    meta: FileAnalysisMeta,
    repo: Path,
    base: str | None,
    rel_path: str,
    head_content: str | None,
    change_type: str,
    merge_base: str | None = None,
) -> FileAnalysisMeta:
    """Compute and attach base-vs-head symbol delta to file analysis metadata."""
    if not (rel_path.endswith(".py") or rel_path.endswith(".pyi")):
        return meta
    from devops_cli.ai.analyze.symbols import compute_symbol_delta

    eff_base = merge_base or (base and _resolve_merge_base(repo, base))
    base_content = (
        _fetch_git_file_content(repo, eff_base, rel_path)
        if eff_base and change_type != "added"
        else None
    )
    added, removed, retained = compute_symbol_delta(base_content, head_content)
    return meta.model_copy(
        update={
            "symbols_added": added,
            "symbols_removed": removed,
            "symbols_retained": retained,
        }
    )


def _handle_deleted_branch_file(
    rel_path: str, repo: Path, base: str | None, merge_base: str | None = None
) -> FileAnalysisMeta:
    """Create analysis metadata for a deleted file and compute removed symbols."""
    meta = _create_deleted_file_meta(rel_path)
    return _apply_symbol_delta_to_meta(
        meta, repo, base, rel_path, None, "deleted", merge_base=merge_base
    )


def _is_branch_file_inspectable(file_path: Path, repo: Path) -> bool:
    """Check if branch file is within repo boundary and under size limit."""
    try:
        resolved = file_path.resolve()
        if not resolved.is_relative_to(repo.resolve()):
            return False
        return file_path.stat().st_size <= CONST_MAX_FILE_SIZE_BYTES
    except Exception:
        return False


def _try_reuse_branch_file_meta(
    file_path: Path,
    rel_path: str,
    enhanced: bool,
    existing_file_metas: dict[str, FileAnalysisMeta],
    repo: Path,
    base: str | None,
    change_type: str,
    merge_base: str | None = None,
) -> FileAnalysisMeta | None:
    """Try reusing cached branch file analysis meta, backfilling delta if missing."""
    if not (enhanced and rel_path in existing_file_metas):
        return None
    try:
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime, UTC)
        reused = _try_reuse_cached_file_meta(existing_file_metas[rel_path], mtime)
        if reused is None:
            return None
        has_delta = bool(reused.symbols_added or reused.symbols_removed or reused.symbols_retained)
        if base and not has_delta:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            return _apply_symbol_delta_to_meta(
                reused, repo, base, rel_path, content, change_type, merge_base=merge_base
            )
        return reused
    except Exception:
        return None


def _process_single_branch_file_meta(
    file_path: Path,
    rel_path: str,
    change_type: str,
    enhanced: bool,
    existing_file_metas: dict[str, FileAnalysisMeta],
    repo: Path,
    ai_client: LLMClient | None,
    base: str | None = None,
    merge_base: str | None = None,
) -> FileAnalysisMeta | None:
    """Analyze a single file for branch diff analysis."""
    if change_type == "deleted" or not file_path.exists():
        return _handle_deleted_branch_file(rel_path, repo, base, merge_base=merge_base)
    if not _is_branch_file_inspectable(file_path, repo):
        return None

    reused = _try_reuse_branch_file_meta(
        file_path,
        rel_path,
        enhanced,
        existing_file_metas,
        repo,
        base,
        change_type,
        merge_base=merge_base,
    )
    if reused is not None:
        return reused

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        from devops_cli.ai.analyze.outlines import analyze_single_file

        meta = analyze_single_file(
            rel_path,
            content,
            file_path.stat().st_size,
            change_type=change_type,
            enhanced=enhanced,
            repo_root=repo,
            ai_client=ai_client,
        )
        if meta is not None and base:
            return _apply_symbol_delta_to_meta(
                meta, repo, base, rel_path, content, change_type, merge_base=merge_base
            )
        return meta
    except Exception:
        return None


@app.callback(invoke_without_command=True)
def analyze_main(
    ctx: typer.Context,
    explain: Annotated[
        bool,
        typer.Option("--explain", "-x", help=HELP.analyze.explain),
    ] = False,
) -> None:
    """Analyze repository source code structure, dependencies, and cyclomatic complexity."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("analyze")
        raise typer.Exit(0)


# =============================================================================
# Command: devops analyze path
# =============================================================================


@app.command(name="path")
def analyze_path(
    target: Annotated[Path, typer.Argument(help=HELP.analyze.target)] = DEFAULT_CURRENT_PATH,
    pattern: Annotated[
        str,
        typer.Option("--pattern", "-g", help=HELP.options.pattern),
    ] = DEFAULT_MATCH_ALL_PATTERN,
    enhanced: Annotated[
        bool,
        typer.Option(
            "--enhanced/--no-enhanced",
            "-e",
            help=HELP.analyze.enhanced,
        ),
    ] = True,
    update_all: Annotated[
        bool,
        typer.Option(
            "--update-all",
            "-u",
            help=HELP.analyze.force,
        ),
    ] = False,
    explain: Annotated[
        bool,
        typer.Option("--explain", "-x", help=HELP.analyze.explain),
    ] = False,
) -> None:
    """Analyze all repository files under target path and save metadata to .data/analysis/."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("analyze")
        return
    repo = find_repo_root(target)
    target_abs = target.resolve() if target.is_absolute() else (repo / target).resolve()

    if not target_abs.exists():
        print_error(MESSAGES.analyze.path_not_exists.format(path=target), prefix=False)
        raise typer.Exit(1)

    if not (target_abs == repo or target_abs.is_relative_to(repo)):
        print_error(
            f"Target path '{target}' is outside the repository root '{repo}'.", prefix=False
        )
        raise typer.Exit(1)

    collected_paths = list_repo_files(target_abs)
    if pattern and pattern != "*":
        collected_paths = [p for p in collected_paths if fnmatch.fnmatch(p.name, pattern)]

    ai_client = None
    if enhanced and not is_dry_run():
        try:
            from devops_cli.ai.client import LLMClient
            from devops_cli.config.settings import get_ai_api_key, load_settings

            settings = load_settings()
            ai_client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
            print_info(
                f"[dim]Analyzing with AI backend: [cyan]{ai_client.backend_info}[/cyan]...[/dim]",
                prefix=False,
            )
        except Exception:
            ai_client = None

    ref_str = str(target.relative_to(repo)) if target_abs != repo else repo.name
    sanitized_ref = sanitize_reference(ref_str, repo)
    existing_file_metas: dict[str, FileAnalysisMeta] = {}
    analysis_dir = analysis_directory(repo)
    out_file_path = analysis_dir / f"path-{sanitized_ref}-metadata.json"

    if enhanced and not update_all and out_file_path.exists():
        try:
            existing_data = json.loads(out_file_path.read_text(encoding="utf-8"))
            existing_payload = AnalysisMetadata.model_validate(existing_data)
            existing_file_metas = {f.path: f for f in existing_payload.files}
        except Exception:
            existing_file_metas = {}

    file_metas: list[FileAnalysisMeta] = []
    for p in collected_paths:
        meta = _process_single_repo_file_meta(p, repo, enhanced, existing_file_metas, ai_client)
        if meta is not None:
            file_metas.append(meta)

    title = f"{repo.name} path analysis: {ref_str}"
    out_file = save_analysis_metadata("path", ref_str, title, file_metas, repo, enhanced=enhanced)

    if not is_dry_run():
        payload_data = json.loads(out_file.read_text(encoding="utf-8"))
        _render_analysis_summary(AnalysisMetadata.model_validate(payload_data), out_file)


# =============================================================================
# Command: devops analyze branch
# =============================================================================


@app.command(name="branch")
def analyze_branch(
    branch: Annotated[str | None, typer.Argument(help=HELP.analyze.target_branch)] = None,
    base: Annotated[
        str, typer.Option("--base", "-b", help=HELP.options.base_branch)
    ] = CONST_GIT_MAIN_BRANCH,
    enhanced: Annotated[
        bool,
        typer.Option(
            "--enhanced/--no-enhanced",
            "-e",
            help=HELP.analyze.enhanced,
        ),
    ] = True,
    update_all: Annotated[
        bool,
        typer.Option(
            "--update-all",
            "-u",
            help=HELP.analyze.force,
        ),
    ] = False,
    explain: Annotated[
        bool,
        typer.Option("--explain", "-x", help=HELP.analyze.explain),
    ] = False,
) -> None:
    """Analyze a git branch diff against base and save metadata to .data/analysis/."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("analyze")
        return
    from devops_cli.core.process import run_subprocess
    from devops_cli.git.operations import list_branches

    repo = find_repo_root()
    target_branch = branch or list_branches(repo).current
    if not target_branch:
        print_error(MESSAGES.analyze.git_branch_failed, prefix=False)
        raise typer.Exit(1)

    ai_client = None
    if enhanced and not is_dry_run():
        try:
            from devops_cli.ai.client import LLMClient
            from devops_cli.config.settings import get_ai_api_key, load_settings

            settings = load_settings()
            ai_client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
            print_info(
                f"[dim]Analyzing with AI backend: [cyan]{ai_client.backend_info}[/cyan]...[/dim]",
                prefix=False,
            )
        except Exception:
            ai_client = None

    sanitized_ref = sanitize_reference(target_branch, repo)
    sanitized_base = sanitize_reference(base, repo) if base else "default"
    cache_ref = f"{sanitized_ref}-base-{sanitized_base}"
    existing_file_metas: dict[str, FileAnalysisMeta] = {}
    analysis_dir = analysis_directory(repo)
    out_file_path = analysis_dir / f"branch-{cache_ref}-metadata.json"

    if enhanced and not update_all and out_file_path.exists():
        try:
            existing_data = json.loads(out_file_path.read_text(encoding="utf-8"))
            existing_payload = AnalysisMetadata.model_validate(existing_data)
            existing_file_metas = {f.path: f for f in existing_payload.files}
        except Exception:
            existing_file_metas = {}

    merge_base = _resolve_merge_base(repo, base, target_branch)
    proc = run_subprocess(["git", "diff", "--name-status", f"{base}...{target_branch}"], cwd=repo)
    file_metas: list[FileAnalysisMeta] = []

    if proc.returncode == 0 and proc.stdout:
        for line in proc.stdout.splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) < 2:
                continue
            status, rel_path = parts[0], parts[1]
            change_type = (
                "added"
                if status.startswith("A")
                else ("deleted" if status.startswith("D") else "modified")
            )
            file_path = repo / rel_path
            meta = _process_single_branch_file_meta(
                file_path,
                rel_path,
                change_type,
                enhanced,
                existing_file_metas,
                repo,
                ai_client,
                base=base,
                merge_base=merge_base,
            )
            if meta is not None:
                file_metas.append(meta)

    title = f"{repo.name} branch analysis: {target_branch} vs {base}"
    out_file = save_analysis_metadata(
        "branch", cache_ref, title, file_metas, repo, enhanced=enhanced
    )

    if not is_dry_run():
        payload_data = json.loads(out_file.read_text(encoding="utf-8"))
        _render_analysis_summary(AnalysisMetadata.model_validate(payload_data), out_file)


# =============================================================================
# Command: devops analyze pr
# =============================================================================


@app.command(name="pr")
def analyze_pr(
    pr_number: Annotated[int, typer.Argument(help=HELP.analyze.pr_number)],
    enhanced: Annotated[
        bool,
        typer.Option(
            "--enhanced/--no-enhanced",
            "-e",
            help=HELP.analyze.enhanced,
        ),
    ] = True,
    update_all: Annotated[
        bool,
        typer.Option(
            "--update-all",
            "-u",
            help=HELP.analyze.force,
        ),
    ] = False,
    explain: Annotated[
        bool,
        typer.Option("--explain", "-x", help=HELP.analyze.explain),
    ] = False,
) -> None:
    """Analyze a GitHub Pull Request and save metadata to .data/analysis/."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("analyze")
        return
    from devops_cli.github.client import GitHubClient

    repo = find_repo_root()
    settings = load_settings()
    token = get_github_token(settings)
    if not token:
        from devops_cli.config.settings import get_github_token as _get_token

        token = _get_token(settings)
    if not token:
        print_error(MESSAGES.analyze.github_token_required, prefix=False)
        raise typer.Exit(1)

    ai_client = None
    if enhanced and not is_dry_run():
        try:
            settings = load_settings()
            ai_client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
            print_info(
                f"[dim]Analyzing with AI backend: [cyan]{ai_client.backend_info}[/cyan]...[/dim]",
                prefix=False,
            )
        except Exception:
            ai_client = None

    repo_name = get_repo_origin_name(repo)
    if not repo_name:
        from devops_cli.core.repo import get_repo_origin_name as _get_origin

        repo_name = _get_origin(repo)
    if not repo_name:
        print_error(MESSAGES.analyze.github_origin_failed, prefix=False)
        raise typer.Exit(1)

    gh_client = GitHubClient(token=token)
    pull = gh_client.get_pull(repo_name, pr_number)
    file_metas: list[FileAnalysisMeta] = []

    for f_file in pull.get_files():
        path = f_file.filename
        if not path or ".." in path or path.startswith(("/", "\\")):
            continue
        from devops_cli.core.paths import safe_resolve_subpath

        try:
            file_path = safe_resolve_subpath(repo, path)
        except Exception:
            continue
        status = str(f_file.status)
        if file_path.exists() and status != "removed":
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                from devops_cli.ai.analyze.outlines import analyze_single_file

                meta = analyze_single_file(
                    path,
                    content,
                    file_path.stat().st_size,
                    change_type=status,
                    enhanced=enhanced,
                    repo_root=repo,
                    ai_client=ai_client,
                )
                file_metas.append(meta)
                continue
            except Exception:
                pass

        file_metas.append(
            FileAnalysisMeta(
                path=path,
                size_bytes=int(f_file.changes),
                line_count=int(f_file.additions),
                char_count=int(f_file.changes),
                language=detect_language(path),
                primary_purpose=f"PR file {Path(path).name}",
                key_symbols=[],
                dependencies=[],
                change_type=status,
                pseudocode=None,
                last_updated=None,
                complexity_score=None,
            )
        )

    title = f"{repo.name} PR #{pr_number} analysis: {pull.title}"
    ref_str = str(pr_number)
    out_file = save_analysis_metadata("pr", ref_str, title, file_metas, repo, enhanced=enhanced)

    if not is_dry_run():
        payload_data = json.loads(out_file.read_text(encoding="utf-8"))
        _render_analysis_summary(AnalysisMetadata.model_validate(payload_data), out_file)
