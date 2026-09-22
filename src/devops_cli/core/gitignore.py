"""In-memory evaluation of git's ignore rules.

Ignore checks previously loaded only the repository root's `.gitignore` and, on a miss,
spawned `git check-ignore` for the file. A miss is the common case -- most files in a
repository are *not* ignored -- so the fast path was the rare one and the slow path ran per
file. Measured over this repository's own sources: 39.5 ms per tracked file, essentially
all of it process spawn.

Reading only the root file is also incorrect. Git consults a `.gitignore` in every
directory between the repository root and the file, plus `.git/info/exclude`, with deeper
files overriding shallower ones and `!` re-including. A nested rule was therefore invisible
to the in-memory path and could only ever be resolved by the subprocess.

This module implements the real rules against `pathspec`, which already provides git's
wildmatch semantics, so no ignore check needs a subprocess.

Reference: gitignore(5).
"""

from __future__ import annotations

import logging
import os.path
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_GIT_DIR_NAME,
    CONST_GIT_INFO_EXCLUDE_RELATIVE,
    CONST_GITIGNORE_FILENAME,
    CONST_GITIGNORE_PATTERN_STYLE,
)
from devops_cli.config.defaults import DEFAULT_GITIGNORE_REVALIDATE_SECONDS

logger = logging.getLogger(__name__)


def _load_patterns(path: Path) -> list[str]:
    """Read ignore patterns from a file, returning nothing when it cannot be read."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.debug("Cannot read ignore file '%s': %s", path, exc)
        return []
    return [
        line for line in (raw_line.rstrip("\n") for raw_line in raw.splitlines()) if line.strip()
    ]


def _compile(patterns: list[str]) -> Any | None:
    """Compile ignore patterns, or return ``None`` when there are none."""
    if not patterns:
        return None
    import pathspec

    try:
        # "gitignore", not the deprecated "gitwildmatch" alias; identical semantics.
        return pathspec.PathSpec.from_lines(CONST_GITIGNORE_PATTERN_STYLE, patterns)
    except Exception as exc:
        # One malformed pattern must not make the whole directory unevaluable.
        logger.debug("Failed compiling ignore patterns: %s", exc)
        return None


@dataclass
class _CachedSpec:
    """One compiled ignore file, with enough state to revalidate it cheaply."""

    mtime: float
    spec: Any | None
    checked_at: float


@dataclass
class GitignoreIndex:
    """Evaluates git ignore rules for a repository without spawning git.

    Two things dominate the cost of an ignore check, and neither is pattern matching:
    resolving paths and stat-ing ignore files. A profile of the first implementation showed
    2404 `stat` and 2396 `lstat` calls for 150 files -- four path resolutions and ten
    ignore-file stats each -- so it evaluated rules correctly and still spent all its time
    in the filesystem.

    Paths are therefore taken as given rather than resolved, which also matches git, and a
    compiled ignore file is revalidated at most once per interval instead of on every
    check. A walk over thousands of files pays for one stat per directory per interval.
    """

    repo_root: Path
    revalidate_after: float = DEFAULT_GITIGNORE_REVALIDATE_SECONDS
    _specs: dict[Path, _CachedSpec] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.repo_root = self.repo_root.resolve()

    def _cached_spec(self, ignore_file: Path) -> Any | None:
        """Return the compiled spec for an ignore file, revalidating periodically."""
        now = time.monotonic()
        cached = self._specs.get(ignore_file)
        if cached is not None and now - cached.checked_at < self.revalidate_after:
            return cached.spec

        try:
            mtime = ignore_file.stat().st_mtime
        except OSError:
            self._specs[ignore_file] = _CachedSpec(mtime=0.0, spec=None, checked_at=now)
            return None

        if cached is not None and cached.mtime == mtime:
            cached.checked_at = now
            return cached.spec

        spec = _compile(_load_patterns(ignore_file))
        self._specs[ignore_file] = _CachedSpec(mtime=mtime, spec=spec, checked_at=now)
        return spec

    def _relative(self, target: Path) -> Path | None:
        """Return the path relative to the repository root, or None if outside it.

        `Path.relative_to` is purely lexical, so it accepts a path that walks back out of
        the root: `repo/../../etc/x` is "relative to" `repo` as `../../etc/x`. Collapsing
        `..` first is what makes the containment check mean containment.
        """
        collapsed = Path(os.path.normpath(target))
        try:
            return collapsed.relative_to(self.repo_root)
        except ValueError:
            return None

    def is_ignored(self, target: Path, is_dir: bool | None = None) -> bool:
        """Report whether git would ignore a path.

        Walks from the repository root downwards, evaluating each directory against the
        rules that are in scope for it before descending. A directory that is ignored ends
        the walk immediately: git does not descend into an excluded directory, so no rule
        underneath it can re-include anything, and stopping there is both correct and the
        cheapest outcome.
        """
        absolute = target if target.is_absolute() else (self.repo_root / target)
        relative = self._relative(absolute)
        if relative is None or not relative.parts:
            return False

        # Rules in scope, shallowest first. A directory's own ignore file does not apply to
        # the directory itself, only to what is inside it, so the scope grows as we descend.
        scope: list[tuple[Any, Path]] = []
        exclude_spec = self._cached_spec(self.repo_root / CONST_GIT_INFO_EXCLUDE_RELATIVE)
        if exclude_spec is not None:
            scope.append((exclude_spec, self.repo_root))
        root_spec = self._cached_spec(self.repo_root / CONST_GITIGNORE_FILENAME)
        if root_spec is not None:
            scope.append((root_spec, self.repo_root))

        current = self.repo_root
        for part in relative.parts[:-1]:
            current = current / part
            if _verdict(scope, current, is_dir=True) is True:
                return True
            nested = self._cached_spec(current / CONST_GITIGNORE_FILENAME)
            if nested is not None:
                scope.append((nested, current))

        leaf = self.repo_root / relative
        directory_flag = leaf.is_dir() if is_dir is None else is_dir
        return _verdict(scope, leaf, is_dir=directory_flag) is True

    def invalidate(self) -> None:
        """Discard every compiled spec, forcing a reload on the next check."""
        self._specs.clear()


def _verdict(scope: list[tuple[Any, Path]], target: Path, is_dir: bool) -> bool | None:
    """Apply every in-scope ignore file, returning the last matching verdict."""
    verdict: bool | None = None
    for spec, base in scope:
        verdict = _match(spec, target, base, is_dir, verdict)
    return verdict


def _match(spec: Any, target: Path, base: Path, is_dir: bool, current: bool | None) -> bool | None:
    """Match a path against one ignore file, keeping the previous verdict on no match."""
    try:
        relative = target.relative_to(base)
    except ValueError:
        return current
    candidate = relative.as_posix()
    if not candidate:
        return current
    # A trailing slash is how a directory is offered to a `dir/`-style pattern.
    if is_dir:
        candidate = f"{candidate}/"

    try:
        result = spec.check_file(candidate)
    except Exception as exc:
        logger.debug("Ignore match failed for '%s': %s", candidate, exc)
        return current
    return current if result.include is None else bool(result.include)


_INDEXES: dict[Path, GitignoreIndex] = {}


def get_index(repo_root: Path) -> GitignoreIndex:
    """Return the cached evaluator for a repository root."""
    resolved = repo_root.resolve()
    index = _INDEXES.get(resolved)
    if index is None:
        index = GitignoreIndex(repo_root=resolved)
        _INDEXES[resolved] = index
    return index


def reset_indexes() -> None:
    """Discard every cached evaluator."""
    _INDEXES.clear()


def is_within_git_dir(repo_root: Path, target: Path) -> bool:
    """Report whether a path lies inside *this* repository's own `.git` directory.

    A path outside the repository is not inside its `.git`, however it is spelled. Falling
    back to the target's own components answered a different question -- whether any
    ancestor anywhere is named `.git` -- so an unrelated checkout under a temporary
    directory reported as part of this repository.
    """
    try:
        parts = target.resolve().relative_to(repo_root.resolve()).parts
    except ValueError:
        return False
    return CONST_GIT_DIR_NAME in parts


__all__ = [
    "GitignoreIndex",
    "get_index",
    "is_within_git_dir",
    "reset_indexes",
]
