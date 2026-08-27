"""Workspace and Data Tier Housekeeping and Retention Engine."""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.config.defaults import DEFAULT_DATA_DIR
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


class CleanupSummary(BaseModel):
    """Summary of cleaned files and directories."""

    pruned_files: list[str] = Field(default_factory=list)
    pruned_dirs: list[str] = Field(default_factory=list)
    freed_bytes: int = 0
    dry_run: bool = False


def _prune_single_item(
    item: Path,
    top_root: Path,
    cutoff_time: float,
    dry_run: bool,
    summary: CleanupSummary,
) -> None:
    """Helper to evaluate and prune a single expired file or directory."""
    try:
        mtime = item.stat().st_mtime
        if mtime >= cutoff_time:
            return

        rel_path = str(item.relative_to(top_root))
        if item.is_file():
            size = item.stat().st_size
            if not dry_run:
                item.unlink(missing_ok=True)
            summary.pruned_files.append(rel_path)
            summary.freed_bytes += size
        elif item.is_dir():
            size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
            if not dry_run:
                shutil.rmtree(item, ignore_errors=True)
            summary.pruned_dirs.append(rel_path)
            summary.freed_bytes += size
    except Exception as exc:
        logger.warning("Failed to prune cleanup candidate %s: %s", item, exc)


@trace_span("workspace.cleanup")
def cleanup_data_tier(
    repo_root: Path = Path("."),
    older_than_seconds: float = 7 * 86400,  # 7 days default
    dry_run: bool = False,
) -> CleanupSummary:
    """Prune stale review runs, temporary metadata, and cached traces under .data/."""
    top_root = find_top_level_repo_root(repo_root)
    data_dir = (
        (top_root / DEFAULT_DATA_DIR).resolve()
        if top_root != Path(".")
        else DEFAULT_DATA_DIR.resolve()
    )
    summary = CleanupSummary(dry_run=dry_run)

    if not data_dir.exists() or not data_dir.is_dir():
        return summary

    cutoff_time = time.time() - older_than_seconds
    subdirs_to_check = ["reviews", "analysis", "logs", "traces", "benchmarks", "cache"]

    for subdir_name in subdirs_to_check:
        target_sub = data_dir / subdir_name
        if not target_sub.exists() or not target_sub.is_dir():
            continue
        for item in target_sub.iterdir():
            _prune_single_item(item, top_root, cutoff_time, dry_run, summary)

    return summary
