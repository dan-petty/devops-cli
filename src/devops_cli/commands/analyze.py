"""Codebase metadata analysis commands (branch, pr, path)."""

from __future__ import annotations

import fnmatch
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console

from devops_cli.ai.analyze.cache import _render_analysis_summary, save_analysis_metadata
from devops_cli.ai.analyze.outlines import analyze_single_file
from devops_cli.ai.analyze.scanner import detect_language, sanitize_reference
from devops_cli.config.constants import (
    CONST_ANALYSIS_DATA_DIR,
    CONST_MAX_FILE_SIZE_BYTES,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_repo_root, find_top_level_repo_root, list_repo_files
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import MESSAGES
from devops_cli.models.ai import AnalysisMetadata, FileAnalysisMeta

app = new_typer(
    help=MESSAGES.analyze.app_help,
    no_args_is_help=True,
)
console = Console()


# ── Subcommands ───────────────────────────────────────────────────────────────


@app.command(name="path")
def analyze_path(
    target: Annotated[Path, typer.Argument(help="File or directory path to analyze")] = Path("."),
    pattern: Annotated[
        str,
        typer.Option("--pattern", "-g", help="Glob pattern for files (default: all files)"),
    ] = "*",
    enhanced: Annotated[
        bool,
        typer.Option(
            "--enhanced/--no-enhanced",
            "-e",
            help="Generate AI-enhanced metadata (pseudocode, complexity, last_updated)",
        ),
    ] = True,
    update_all: Annotated[
        bool,
        typer.Option(
            "--update-all",
            "-u",
            help="Regenerate all enhanced metadata fields regardless of last_* timestamps",
        ),
    ] = False,
) -> None:
    """Analyze a local directory path or single file and save metadata to .data/analysis/."""
    repo = find_repo_root(target)
    target_abs = target.resolve() if target.is_absolute() else (repo / target).resolve()

    if not target_abs.exists():
        rprint(f"[red]{MESSAGES.analyze.path_not_exists.format(path=target)}[/red]")
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
            rprint(
                f"[dim]Analyzing with AI backend: [cyan]{ai_client.backend_info}[/cyan]...[/dim]"
            )
        except Exception:
            ai_client = None

    ref_str = str(target.relative_to(repo)) if target_abs != repo else repo.name
    sanitized_ref = sanitize_reference(ref_str, repo)
    existing_file_metas: dict[str, FileAnalysisMeta] = {}
    top_root = find_top_level_repo_root(repo)
    out_file_path = top_root / CONST_ANALYSIS_DATA_DIR / f"path-{sanitized_ref}-metadata.json"

    if enhanced and not update_all and out_file_path.exists():
        try:
            existing_data = json.loads(out_file_path.read_text(encoding="utf-8"))
            existing_payload = AnalysisMetadata.model_validate(existing_data)
            existing_file_metas = {f.path: f for f in existing_payload.files}
        except Exception:
            existing_file_metas = {}

    file_metas: list[FileAnalysisMeta] = []
    for p in collected_paths:
        if p.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
            continue
        try:
            rel_str = str(p.relative_to(repo)) if p.is_relative_to(repo) else str(p)
            file_mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC)

            if enhanced and rel_str in existing_file_metas:
                old_meta = existing_file_metas[rel_str]
                if old_meta.last_analyzed and old_meta.pseudocode:
                    try:
                        analyzed_dt = datetime.fromisoformat(old_meta.last_analyzed)
                        if file_mtime <= analyzed_dt:
                            reused_meta = old_meta.model_copy(
                                update={"last_analyzed": datetime.now(UTC).isoformat()}
                            )
                            file_metas.append(reused_meta)
                            continue
                    except Exception:
                        pass

            content = p.read_text(encoding="utf-8", errors="replace")
            meta = analyze_single_file(
                rel_str,
                content,
                p.stat().st_size,
                enhanced=enhanced,
                repo_root=repo,
                ai_client=ai_client,
            )
            file_metas.append(meta)
        except Exception:
            continue

    title = f"{repo.name} path analysis: {ref_str}"
    out_file = save_analysis_metadata("path", ref_str, title, file_metas, repo, enhanced=enhanced)

    if not is_dry_run():
        payload_data = json.loads(out_file.read_text(encoding="utf-8"))
        _render_analysis_summary(AnalysisMetadata.model_validate(payload_data), out_file)


@app.command(name="branch")
def analyze_branch(
    branch: Annotated[
        str | None, typer.Argument(help="Branch to analyze (default: active branch)")
    ] = None,
    base: Annotated[str, typer.Option("--base", "-b", help="Base branch for diff")] = "main",
    enhanced: Annotated[
        bool,
        typer.Option(
            "--enhanced/--no-enhanced",
            "-e",
            help="Generate AI-enhanced metadata (pseudocode, complexity, last_updated)",
        ),
    ] = True,
    update_all: Annotated[
        bool,
        typer.Option(
            "--update-all",
            "-u",
            help="Regenerate all enhanced metadata fields regardless of last_* timestamps",
        ),
    ] = False,
) -> None:
    """Analyze a git branch diff against base and save metadata to .data/analysis/."""
    from devops_cli.core.process import run_subprocess
    from devops_cli.git.operations import list_branches

    repo = find_repo_root()
    target_branch = branch or list_branches(repo).current
    if not target_branch:
        rprint(f"[red]{MESSAGES.analyze.git_branch_failed}[/red]")
        raise typer.Exit(1)

    ai_client = None
    if enhanced and not is_dry_run():
        try:
            from devops_cli.ai.client import LLMClient
            from devops_cli.config.settings import get_ai_api_key, load_settings

            settings = load_settings()
            ai_client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
            rprint(
                f"[dim]Analyzing with AI backend: [cyan]{ai_client.backend_info}[/cyan]...[/dim]"
            )
        except Exception:
            ai_client = None

    sanitized_ref = sanitize_reference(target_branch, repo)
    existing_file_metas: dict[str, FileAnalysisMeta] = {}
    top_root = find_top_level_repo_root(repo)
    out_file_path = top_root / CONST_ANALYSIS_DATA_DIR / f"branch-{sanitized_ref}-metadata.json"

    if enhanced and not update_all and out_file_path.exists():
        try:
            existing_data = json.loads(out_file_path.read_text(encoding="utf-8"))
            existing_payload = AnalysisMetadata.model_validate(existing_data)
            existing_file_metas = {f.path: f for f in existing_payload.files}
        except Exception:
            existing_file_metas = {}

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

            if change_type == "deleted" or not file_path.exists():
                file_metas.append(
                    FileAnalysisMeta(
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
                )
                continue

            try:
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, UTC)
                if enhanced and rel_path in existing_file_metas:
                    old_meta = existing_file_metas[rel_path]
                    if old_meta.last_analyzed and old_meta.pseudocode:
                        try:
                            analyzed_dt = datetime.fromisoformat(old_meta.last_analyzed)
                            if file_mtime <= analyzed_dt:
                                reused_meta = old_meta.model_copy(
                                    update={"last_analyzed": datetime.now(UTC).isoformat()}
                                )
                                file_metas.append(reused_meta)
                                continue
                        except Exception:
                            pass

                content = file_path.read_text(encoding="utf-8", errors="replace")
                meta = analyze_single_file(
                    rel_path,
                    content,
                    file_path.stat().st_size,
                    change_type=change_type,
                    enhanced=enhanced,
                    repo_root=repo,
                    ai_client=ai_client,
                )
                file_metas.append(meta)
            except Exception:
                continue

    title = f"{repo.name} branch analysis: {target_branch} vs {base}"
    out_file = save_analysis_metadata(
        "branch", target_branch, title, file_metas, repo, enhanced=enhanced
    )

    if not is_dry_run():
        payload_data = json.loads(out_file.read_text(encoding="utf-8"))
        _render_analysis_summary(AnalysisMetadata.model_validate(payload_data), out_file)


@app.command(name="pr")
def analyze_pr(
    pr_number: Annotated[int, typer.Argument(help="GitHub PR number to analyze")],
    enhanced: Annotated[
        bool,
        typer.Option(
            "--enhanced/--no-enhanced",
            "-e",
            help="Generate AI-enhanced metadata (pseudocode, complexity, last_updated)",
        ),
    ] = True,
    update_all: Annotated[
        bool,
        typer.Option(
            "--update-all",
            "-u",
            help="Regenerate all enhanced metadata fields regardless of last_* timestamps",
        ),
    ] = False,
) -> None:
    """Analyze a GitHub Pull Request and save metadata to .data/analysis/."""
    from devops_cli.config.settings import get_github_token, load_settings
    from devops_cli.github.client import GitHubClient

    repo = find_repo_root()
    settings = load_settings()
    token = get_github_token(settings)
    if not token:
        rprint(f"[red]{MESSAGES.analyze.github_token_required}[/red]")
        raise typer.Exit(1)

    ai_client = None
    if enhanced and not is_dry_run():
        try:
            from devops_cli.ai.client import LLMClient
            from devops_cli.config.settings import get_ai_api_key, load_settings

            settings = load_settings()
            ai_client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
            rprint(
                f"[dim]Analyzing with AI backend: [cyan]{ai_client.backend_info}[/cyan]...[/dim]"
            )
        except Exception:
            ai_client = None

    from devops_cli.core.repo import get_repo_origin_name

    repo_name = get_repo_origin_name(repo)
    if not repo_name:
        rprint(f"[red]{MESSAGES.analyze.github_origin_failed}[/red]")
        raise typer.Exit(1)

    gh_client = GitHubClient(token=token)
    pull = gh_client.get_pull(repo_name, pr_number)
    file_metas: list[FileAnalysisMeta] = []

    for f_file in pull.get_files():
        path = f_file.filename
        if not path:
            continue
        status = str(f_file.status)
        file_path = repo / path
        if file_path.exists() and status != "removed":
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
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
