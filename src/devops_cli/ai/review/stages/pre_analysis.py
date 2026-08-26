"""Pre-Analysis Metadata Refresh & File Review Payload Initialization."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from devops_cli.ai.analyze.cache import load_cached_analysis
from devops_cli.ai.analyze.outlines import analyze_single_file
from devops_cli.ai.client import LLMClient
from devops_cli.config.constants import CONST_MAX_FILE_SIZE_BYTES
from devops_cli.config.defaults import DEFAULT_REVIEW_MAX_WORKERS
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.telemetry import ContextPropagatingThreadPoolExecutor as ThreadPoolExecutor
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


def _collect_analysis_results(
    future_to_path: dict[Any, str],
    metadata_by_path: dict[str, FileAnalysisMeta],
) -> None:
    """Safely resolve background file analysis futures and populate metadata dict."""
    for future, rel_path in future_to_path.items():
        try:
            meta = future.result()
            if meta:
                metadata_by_path[rel_path] = meta
        except Exception as exc:
            logger.debug("Stage analysis failed for %s: %s", rel_path, exc)


@trace_span("review.stage.pre_analysis")
def run_pre_analysis(
    target_dir: Path,
    llm_client: LLMClient | None = None,
    max_workers: int = DEFAULT_REVIEW_MAX_WORKERS,
) -> dict[str, FileAnalysisMeta]:
    """Refresh codebase analysis metadata for files in target_dir."""
    metadata_by_path: dict[str, FileAnalysisMeta] = {}
    cached_payload = load_cached_analysis(repo_root=target_dir)
    cached_by_path = {f.path: f for f in cached_payload.files} if cached_payload else {}

    target_root = target_dir.resolve()
    candidate_paths: list[Path] = []

    for item in target_root.rglob("*"):
        if (
            item.is_file()
            and not item.name.startswith(".")
            and ".git" not in item.parts
            and ".data" not in item.parts
            and ".venv" not in item.parts
        ):
            try:
                if item.stat().st_size <= CONST_MAX_FILE_SIZE_BYTES:
                    candidate_paths.append(item)
            except OSError:
                continue

    paths_to_analyze: list[tuple[Path, str]] = []
    for p in candidate_paths:
        try:
            rel_str = str(p.relative_to(target_root))
            old_meta = cached_by_path.get(rel_str)
            if old_meta and getattr(old_meta, "last_analyzed", None):
                metadata_by_path[rel_str] = old_meta
            else:
                paths_to_analyze.append((p, rel_str))
        except (ValueError, OSError) as exc:
            logger.debug("Failed evaluating path %s: %s", p, exc)

    if paths_to_analyze and llm_client:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(
                    analyze_single_file,
                    fpath,
                    rel_path,
                    llm_client,
                    force=True,
                    enhanced=True,
                ): rel_path
                for fpath, rel_path in paths_to_analyze
            }
            _collect_analysis_results(future_to_path, metadata_by_path)

    return metadata_by_path
