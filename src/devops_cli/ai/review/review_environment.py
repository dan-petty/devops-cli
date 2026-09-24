"""Review execution environment and conventions discovery helpers."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from devops_cli.config.constants import CONST_AGENTS_MD_FILENAME, CONST_REVIEW_CONVENTIONS_FILE

_TARGET_CONVENTIONS_CANDIDATES: tuple[str, ...] = (
    CONST_AGENTS_MD_FILENAME,
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".cursorrules",
    ".cursor/rules",
)


def _repo_root(directory: Path) -> Path | None:
    for candidate in (directory, *directory.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _nearest(start: Path, read: Callable[[Path], str]) -> str:
    """The first non-empty `read` result from the start directory up to its repo root.

    The nearest file wins, as for AGENTS.md generally: a subproject's conventions override its
    repository's. Outside a repository only the start directory is read.
    """
    start_resolved = start.resolve()
    directory = start_resolved if start_resolved.is_dir() else start_resolved.parent
    repo_root = _repo_root(directory)
    for candidate in (directory, *directory.parents):
        if content := read(candidate):
            return content
        if repo_root is None or candidate == repo_root:
            break
    return ""


def nearest_conventions(start: Path) -> str:
    """The nearest general conventions file (AGENTS.md and its peers) for a review target."""
    return _nearest(start, _read_candidate_conventions_file)


def _read_review_conventions_file(directory: Path) -> str:
    path = directory / CONST_REVIEW_CONVENTIONS_FILE
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else ""
    except OSError:
        return ""


def nearest_review_conventions(start: Path) -> str:
    """The nearest `.devops/review.md`: rules a project keeps for reviews of its own code."""
    return _nearest(start, _read_review_conventions_file).strip()


def _read_candidate_conventions_file(directory: Path | None) -> str:
    """Read first matching project conventions file from directory."""
    if not directory or not directory.is_dir():
        return ""
    for name in _TARGET_CONVENTIONS_CANDIDATES:
        cand = directory / name
        if not cand.is_file():
            continue
        try:
            content = cand.read_text(encoding="utf-8")
            if content.strip():
                return content
        except OSError:
            continue
    return ""


def _get_reviews_base_dir() -> Path:
    """Resolve and ensure the review data storage directory."""
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import find_top_level_repo_root

    env_data_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if env_data_dir:
        d = Path(env_data_dir) / "reviews"
    else:
        settings = load_settings()
        d = settings.data.reviews_dir
    if not d.is_absolute():
        d = find_top_level_repo_root() / d
    d = d.resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d
