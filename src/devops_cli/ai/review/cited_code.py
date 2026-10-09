"""The code a finding's location cites, recorded when a review saves its session (#950).

It is evidence about a location, not a verdict. `devops review score` places a row by the
repository file it names, even when the location is an absolute path into a review worktree, and
`devops review export-feedback` carries its excerpt. The code is read only from a file inside the
reviewed checkout, at most DEFAULT_CITED_EXCERPT_MAX_LINES lines, with secrets masked. A finding
about a secret records none: its cited line may hold a secret the masking does not know.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from devops_cli.ai.review_schema import CitedCode, DefectClass, SavedFinding, _parse_location
from devops_cli.config.defaults import (
    DEFAULT_CITED_EXCERPT_MAX_LINES,
    DEFAULT_MAX_AST_FILE_SIZE_BYTES,
)
from devops_cli.core.repo import main_worktree_root
from devops_cli.security.sanitizer import mask_secrets


def cited_code(location: str, file_path: Path, checkout: Path) -> CitedCode | None:
    """The code `location` cites in `file_path`, a file of the checkout rooted at `checkout`.

    None when the location cites no line, or none the file holds, or the file lies outside the
    checkout. The project is the name of the checkout's main worktree, so a linked worktree's
    code belongs to the repository it was made from.
    """
    _, start, end = _parse_location(location)
    resolved, root = file_path.resolve(), checkout.resolve()
    if start is None or start < 1 or not resolved.is_relative_to(root):
        return None
    try:
        if resolved.stat().st_size > DEFAULT_MAX_AST_FILE_SIZE_BYTES:
            return None
        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if start > len(lines):
        return None
    last = min(end or start, len(lines), start + DEFAULT_CITED_EXCERPT_MAX_LINES - 1)
    return CitedCode(
        project=main_worktree_root(root).name,
        file=resolved.relative_to(root).as_posix(),
        line=start,
        excerpt=mask_secrets("\n".join(lines[start - 1 : last])),
    )


def record_cited_code(
    findings: Iterable[SavedFinding],
    resolve_file_path: Callable[[str], Path],
    checkout: Path,
) -> None:
    """Record on each finding the code its location cites, as this review read it.

    `resolve_file_path` turns the location's file into a path, as the review resolved the files
    it read; `checkout` is the reviewed checkout's root.
    """
    for finding in findings:
        file_part = _parse_location(finding.location)[0]
        about_a_secret = finding.category == DefectClass.SECRET_EXPOSURE.value
        finding.cited_code = (
            cited_code(finding.location, resolve_file_path(file_part), checkout)
            if file_part and not about_a_secret
            else None
        )
