"""Workspace and Data Tier Housekeeping and Retention Engine."""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_DATA_DIR
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


class CleanupSummary(BaseModel):
    """Summary of cleaned files and directories."""

    pruned_files: list[str] = Field(default_factory=list)
    pruned_dirs: list[str] = Field(default_factory=list)
    freed_bytes: int = 0
    dry_run: bool = False


@trace_span("workspace.cleanup")
def cleanup_data_tier(
    repo_root: Path = Path("."),
    older_than_seconds: float = 7 * 86400,  # 7 days default
    dry_run: bool = False,
) -> CleanupSummary:
    """Prune stale review runs, temporary metadata, and cached traces under .data/."""
    top_root = find_top_level_repo_root(repo_root)
    data_dir = top_root / CONST_DATA_DIR
    summary = CleanupSummary(dry_run=dry_run)

    if not data_dir.exists() or not data_dir.is_dir():
        return summary

    cutoff_time = time.time() - older_than_seconds

    # Target candidate subdirectories
    subdirs_to_check = ["reviews", "analysis", "logs", "traces"]
    for subdir_name in subdirs_to_check:
        target_sub = data_dir / subdir_name
        if not target_sub.exists() or not target_sub.is_dir():
            continue

        for item in target_sub.iterdir():
            try:
                mtime = item.stat().st_mtime
                if mtime < cutoff_time:
                    size = 0
                    if item.is_file():
                        size = item.stat().st_size
                        summary.pruned_files.append(str(item.relative_to(top_root)))
                        summary.freed_bytes += size
                        if not dry_run:
                            item.unlink(missing_ok=True)
                    elif item.is_dir():
                        for sub_f in item.rglob("*"):
                            if sub_f.is_file():
                                size += sub_f.stat().st_size
                        summary.pruned_dirs.append(str(item.relative_to(top_root)))
                        summary.freed_bytes += size
                        if not dry_run:
                            shutil.rmtree(item, ignore_errors=True)
            except Exception as exc:
                logger.debug("Failed checking %s during cleanup: %s", item, exc)

    return summary
