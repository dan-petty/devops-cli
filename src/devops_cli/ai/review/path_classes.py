"""Declarative path classification for review routing and tool scoping (#1047).

Paths are classified into classes (src, test, fixture, iac, docs) declared in
`.devops/review.toml` at the base revision, falling back to default repository conventions.
Fixtures and golden test sets are routed to the secret scanner only.
"""

from __future__ import annotations

import fnmatch
import logging
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import (
    CONST_DEFAULT_PATH_CLASSES,
    CONST_REVIEW_CONFIG_FILE,
)

if TYPE_CHECKING:
    from devops_cli.ai.analyze.symbols import BaseRevision

logger = logging.getLogger(__name__)

# Priority order ensures specific folders (e.g. fixtures inside tests/) match first.
_CLASS_PRIORITY: tuple[str, ...] = ("fixture", "test", "iac", "docs", "src")


def _read_config_content(base_revision: BaseRevision | None, repo_root: Path | None) -> str | None:
    """Read .devops/review.toml content from the base revision or workspace root."""
    if base_revision is not None and base_revision.read is not None:
        try:
            content = base_revision.read(CONST_REVIEW_CONFIG_FILE)
            if content:
                return content
        except Exception as exc:
            logger.debug("Failed reading %s from base revision: %s", CONST_REVIEW_CONFIG_FILE, exc)

    if repo_root is not None:
        cfg_file = repo_root / CONST_REVIEW_CONFIG_FILE
        try:
            if cfg_file.is_file():
                return cfg_file.read_text(encoding="utf-8")
        except Exception as exc:
            logger.debug("Failed reading %s from disk: %s", cfg_file, exc)

    return None


def _parse_toml_classes(content: str) -> dict[str, tuple[str, ...]]:
    """Parse TOML content extracting path classes."""
    try:
        data: dict[str, Any] = tomllib.loads(content)
    except Exception as exc:
        logger.warning("Failed parsing %s: %s; using defaults", CONST_REVIEW_CONFIG_FILE, exc)
        return dict(CONST_DEFAULT_PATH_CLASSES)

    paths_section = data.get("paths") or data.get("path_classes") or data
    if not isinstance(paths_section, dict):
        return dict(CONST_DEFAULT_PATH_CLASSES)

    classes: dict[str, tuple[str, ...]] = {}
    for cls, default_pats in CONST_DEFAULT_PATH_CLASSES.items():
        user_pats = paths_section.get(cls)
        if isinstance(user_pats, list):
            classes[cls] = tuple(str(p) for p in user_pats if isinstance(p, str))
        else:
            classes[cls] = default_pats
    return classes


def load_path_classes(
    base_revision: BaseRevision | None = None, repo_root: Path | None = None
) -> dict[str, tuple[str, ...]]:
    """Load path classes from .devops/review.toml at base revision or repo root."""
    content = _read_config_content(base_revision, repo_root)
    if not content:
        return dict(CONST_DEFAULT_PATH_CLASSES)
    return _parse_toml_classes(content)


def _matches_any_pattern(norm_path: str, patterns: Sequence[str]) -> bool:
    """Check if normalized posix path matches any glob pattern in patterns."""
    posix_path = PurePosixPath(norm_path)
    for pat in patterns:
        clean_pat = pat.strip()
        if not clean_pat:
            continue
        try:
            if (
                posix_path.match(clean_pat)
                or posix_path.full_match(clean_pat)
                or fnmatch.fnmatchcase(norm_path, clean_pat)
                or fnmatch.fnmatchcase(norm_path, f"*/{clean_pat}")
            ):
                return True
        except ValueError:
            if fnmatch.fnmatchcase(norm_path, clean_pat) or fnmatch.fnmatchcase(
                norm_path, f"*/{clean_pat}"
            ):
                return True
    return False


def classify_path(
    rel_path: str | Path | PurePosixPath,
    path_classes: Mapping[str, Sequence[str]] | None = None,
) -> str:
    """Classify a relative path into one of (fixture, test, iac, docs, src)."""
    norm = str(rel_path).replace("\\", "/").strip("./")
    classes = path_classes or CONST_DEFAULT_PATH_CLASSES

    for cls in _CLASS_PRIORITY:
        patterns = classes.get(cls, ())
        if _matches_any_pattern(norm, patterns):
            return cls

    return "src"


def is_fixture_path(
    rel_path: str | Path | PurePosixPath,
    path_classes: Mapping[str, Sequence[str]] | None = None,
) -> bool:
    """Whether a path belongs to test fixtures or golden sets."""
    return classify_path(rel_path, path_classes) == "fixture"
