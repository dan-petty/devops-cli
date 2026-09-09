"""Autonomous RAG Index Drift Detection & Auto-Reindexing Engine.

Detects staleness and drift between the working tree, git commit HEAD,
and the Qdrant vector index cache, and orchestrates auto-reindexing.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.rag.chunker import SemanticChunker
from devops_cli.ai.rag.indexer import WorkspaceIndexer, detect_project_name
from devops_cli.config.defaults import DEFAULT_RAG_CACHE_DIR
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)

CONST_RAG_COMMIT_MARKER = "rag_indexed_commit.txt"


class RAGDriftReport(BaseModel):
    """Structured report of RAG vector index drift status."""

    root_dir: str
    project: str
    total_files: int
    synced_files: int
    stale_files: list[str] = Field(default_factory=list)
    new_files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)
    git_commit_drift: bool = False
    last_indexed_commit: str | None = None
    current_head_commit: str | None = None
    drift_score: float = 0.0
    reindexed_files: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary representation."""
        return self.model_dump()


def _resolve_git_head_commit(root_dir: Path) -> str | None:
    """Retrieve current git commit hash for directory with graceful fallback."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root_dir,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception as exc:
        logger.debug("Failed checking git commit for %s: %s", root_dir, exc)
    return None


def _load_indexed_commit(cache_dir: Path) -> str | None:
    """Load previously recorded git commit from cache marker file."""
    marker = cache_dir / CONST_RAG_COMMIT_MARKER
    if marker.is_file():
        try:
            return marker.read_text(encoding="utf-8").strip() or None
        except Exception:
            return None
    return None


def _save_indexed_commit(cache_dir: Path, commit: str) -> None:
    """Record successfully indexed git commit to cache marker file."""
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        marker = cache_dir / CONST_RAG_COMMIT_MARKER
        marker.write_text(commit.strip() + "\n", encoding="utf-8")
    except Exception as exc:
        logger.debug("Failed saving indexed commit marker: %s", exc)


def _scan_file_drift(
    fpath: Path,
    root_dir: Path,
    proj: str,
    cache: dict[str, str],
    stale: list[str],
    new: list[str],
) -> None:
    """Scan a single indexable file and classify as synced, stale, or new."""
    try:
        rel_str = str(fpath.relative_to(root_dir))
    except ValueError:
        rel_str = fpath.name

    cache_key = f"{proj}:{rel_str}"
    try:
        content = fpath.read_text(encoding="utf-8", errors="replace")
        cur_hash = SemanticChunker._hash_content(content)
    except Exception:
        return

    cached_hash = cache.get(cache_key)
    if cached_hash is None:
        new.append(rel_str)
    elif cached_hash != cur_hash:
        stale.append(rel_str)


def _find_deleted_files(
    cache: dict[str, str],
    proj: str,
    active_rel_paths: set[str],
) -> list[str]:
    """Identify cached files that no longer exist on disk."""
    deleted: list[str] = []
    prefix = f"{proj}:"
    for ckey in cache:
        if ckey.startswith(prefix):
            rel_file = ckey[len(prefix) :]
            if rel_file and rel_file not in active_rel_paths:
                deleted.append(rel_file)
    return sorted(deleted)


def _calculate_drift_score(
    total_active: int, stale_cnt: int, new_cnt: int, deleted_cnt: int
) -> float:
    """Compute normalized drift score between 0.0 (clean) and 1.0 (drifted)."""
    denominator = max(1, total_active + deleted_cnt)
    changed = stale_cnt + new_cnt + deleted_cnt
    return round(min(1.0, changed / denominator), 3)


def _resolve_drift_commits(
    root_dir: Path,
    cache_dir: Path,
    last_indexed_commit: str | None,
    current_commit: str | None,
) -> tuple[str | None, str | None, bool]:
    """Resolve current and previously indexed git commits and determine divergence."""
    cur = current_commit if current_commit is not None else _resolve_git_head_commit(root_dir)
    last = (
        last_indexed_commit if last_indexed_commit is not None else _load_indexed_commit(cache_dir)
    )
    git_drift = bool(last and cur and last != cur)
    return last, cur, git_drift


def _scan_all_files(
    files: Sequence[Path],
    root_dir: Path,
    project: str,
    cache: dict[str, str],
) -> tuple[list[str], list[str], set[str]]:
    """Scan all active workspace files and categorize drift status."""
    stale_files: list[str] = []
    new_files: list[str] = []
    active_paths: set[str] = set()

    for fpath in files:
        try:
            rel_f = str(fpath.relative_to(root_dir))
        except ValueError:
            rel_f = fpath.name
        active_paths.add(rel_f)
        _scan_file_drift(fpath, root_dir, project, cache, stale_files, new_files)

    return stale_files, new_files, active_paths


class RAGDriftDetector:
    """Detects vector index staleness and manages autonomous RAG re-indexing."""

    def __init__(
        self,
        root_dir: Path | str = ".",
        indexer: WorkspaceIndexer | None = None,
        cache_dir: Path = DEFAULT_RAG_CACHE_DIR,
    ) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.cache_dir = cache_dir
        self.indexer = indexer or WorkspaceIndexer(cache_dir=cache_dir)
        self.project = detect_project_name(self.root_dir, self.root_dir)

    def detect_drift(
        self,
        current_cache: dict[str, str] | None = None,
        last_indexed_commit: str | None = None,
        current_commit: str | None = None,
    ) -> RAGDriftReport:
        """Analyze workspace files and detect drift against vector index cache."""
        with trace_span("rag.drift_detection", attributes={"rag.root_dir": str(self.root_dir)}):
            cache = current_cache if current_cache is not None else self.indexer._load_cache()
            files = self.indexer.collect_files(self.root_dir)

            last_commit, cur_commit, git_drift = _resolve_drift_commits(
                self.root_dir, self.cache_dir, last_indexed_commit, current_commit
            )

            stale_files, new_files, active_paths = _scan_all_files(
                files, self.root_dir, self.project, cache
            )

            deleted_files = _find_deleted_files(cache, self.project, active_paths)
            total_active = len(files)
            synced = total_active - len(stale_files) - len(new_files)

            drift_score = _calculate_drift_score(
                total_active, len(stale_files), len(new_files), len(deleted_files)
            )

            record_metric(
                "devops_cli_rag_drift_detected_total",
                1.0 if (drift_score > 0 or git_drift) else 0.0,
                attributes={"project": self.project},
            )
            record_metric(
                "devops_cli_rag_drift_score",
                drift_score,
                unit="ratio",
                attributes={"project": self.project},
            )

            return RAGDriftReport(
                root_dir=str(self.root_dir),
                project=self.project,
                total_files=total_active,
                synced_files=max(0, synced),
                stale_files=sorted(stale_files),
                new_files=sorted(new_files),
                deleted_files=deleted_files,
                git_commit_drift=git_drift,
                last_indexed_commit=last_commit,
                current_head_commit=cur_commit,
                drift_score=drift_score,
            )

    def detect_and_sync(self, auto_sync: bool = False) -> RAGDriftReport:
        """Detect drift and automatically re-index if auto_sync is enabled and drift exists."""
        report = self.detect_drift()
        if not auto_sync:
            return report

        if report.drift_score > 0.0 or report.git_commit_drift or not report.synced_files:
            logger.info(
                "Auto-syncing RAG index for %s (drift: %s)", self.project, report.drift_score
            )
            index_res = self.indexer.index_workspace(self.root_dir, project=self.project)
            reindexed = int(index_res.get("indexed_files", 0))
            if report.current_head_commit:
                _save_indexed_commit(self.cache_dir, report.current_head_commit)
            report.reindexed_files = reindexed
            report.drift_score = 0.0
            report.git_commit_drift = False
            report.synced_files = report.total_files
            report.stale_files = []
            report.new_files = []
            report.deleted_files = []

        return report
