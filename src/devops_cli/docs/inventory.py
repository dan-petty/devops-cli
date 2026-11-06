"""Classify the Markdown files of the documentation inventory (#1103, #3204).

`CONST_DOCS_INVENTORY` lists the globs of every class but the hand-written one. A Markdown file
that no listed class matches is hand-written, so a new page needs no entry.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from devops_cli.config.constants import CONST_DOCS_CLASS_HAND_WRITTEN, CONST_DOCS_INVENTORY
from devops_cli.core.repo import list_repo_files


def explicit_classes(path: str) -> list[str]:
    """The classes of the inventory whose globs match a repository path, in inventory order."""
    posix_path = PurePosixPath(path)
    return [
        name
        for name, globs in CONST_DOCS_INVENTORY.items()
        if any(posix_path.full_match(glob) for glob in globs)
    ]


def document_class(path: str) -> str:
    """The class of a Markdown file: the first class that lists it, else hand-written."""
    return next(iter(explicit_classes(path)), CONST_DOCS_CLASS_HAND_WRITTEN)


def documents_of_class(root: Path, name: str) -> list[Path]:
    """The Markdown files under a root that belong to a class, sorted."""
    if name == CONST_DOCS_CLASS_HAND_WRITTEN:
        return hand_written_documents(root)
    return sorted({path for glob in CONST_DOCS_INVENTORY[name] for path in root.glob(glob)})


def hand_written_documents(root: Path) -> list[Path]:
    """The Markdown files of a repository that no other class lists, sorted by path."""
    return sorted(
        path
        for path in list_repo_files(root)
        if path.suffix == ".md" and not explicit_classes(path.relative_to(root).as_posix())
    )
