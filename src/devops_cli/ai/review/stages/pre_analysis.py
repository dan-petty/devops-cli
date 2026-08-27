"""Pre-analysis metadata scanning and structural AST indexing."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.analyze.cache import load_cached_analysis
from devops_cli.ai.analyze.scanner import scan_directory
from devops_cli.core.repo import find_repo_root
from devops_cli.models.ai import AnalysisMetadata, FileAnalysisMeta
from devops_cli.output import print_info
from devops_cli.telemetry.tracer import trace_span


def run_pre_analysis_stage(
    target_dir: Path,
    target_ref: str,
    target_type: str,
    force_refresh: bool = False,
) -> tuple[AnalysisMetadata | None, dict[str, FileAnalysisMeta]]:
    """Execute pre-analysis metadata scanning for reviewed target."""
    with trace_span(
        "review.pre_analysis",
        attributes={"target_ref": target_ref, "target_type": target_type},
    ):
        repo = find_repo_root(target_dir)
        target_abs = (
            target_dir.resolve() if target_dir.is_absolute() else (repo / target_dir).resolve()
        )
        print_info(
            f"[dim]Scanning pre-analysis metadata for '{target_ref}'...[/dim]",
            prefix=False,
        )

        scan_root = target_abs if target_abs.is_dir() else repo
        file_metas = scan_directory(scan_root)
        cached_meta = load_cached_analysis(repo)
        metadata_by_path = {f.path: f for f in file_metas}
        return cached_meta, metadata_by_path
