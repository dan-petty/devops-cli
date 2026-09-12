"""Review execution environment and conventions discovery helpers."""

from __future__ import annotations

import os
from pathlib import Path

from devops_cli.config.constants import CONST_AGENTS_MD_FILENAME

_TARGET_CONVENTIONS_CANDIDATES: tuple[str, ...] = (
    CONST_AGENTS_MD_FILENAME,
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".cursorrules",
    ".cursor/rules",
)


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
