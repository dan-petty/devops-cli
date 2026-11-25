"""Classify the Markdown files of the documentation inventory (#1103, #3204).

`CONST_DOCS_INVENTORY` lists the globs of every class but the hand-written one. A Markdown file
that no listed class matches is hand-written, so a new page needs no entry.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from devops_cli.config.constants import (
    CONST_DOCS_CLASS_GENERATED,
    CONST_DOCS_CLASS_HAND_WRITTEN,
    CONST_DOCS_INVENTORY,
)
from devops_cli.core.process import run_subprocess
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


def generated_attribute_problems(root: Path) -> list[str]:
    """Check that `.gitattributes` and `git check-attr` mark generated docs and leave other
    tracked Markdown files `unspecified` (#4888)."""
    problems: list[str] = []
    attr_file = root / ".gitattributes"
    attrs_by_pattern: dict[str, set[str]] = {}
    if attr_file.is_file():
        for raw_line in attr_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            attrs_by_pattern.setdefault(parts[0], set()).update(parts[1:])

    generated_globs = CONST_DOCS_INVENTORY[CONST_DOCS_CLASS_GENERATED]
    for glob in generated_globs:
        if "linguist-generated=true" not in attrs_by_pattern.get(glob, ()):
            problems.append(
                f"Missing 'linguist-generated=true' attribute line in .gitattributes for '{glob}'."
            )

    ls_proc = run_subprocess(
        ["git", "-C", str(root), "ls-files", "-z", "--", "*.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    tracked_md = sorted(path for path in ls_proc.stdout.split("\0") if path)
    if not tracked_md:
        return problems

    attr_proc = run_subprocess(
        ["git", "-C", str(root), "check-attr", "-z", "--stdin", "linguist-generated"],
        input="".join(f"{path}\0" for path in tracked_md),
        check=True,
        capture_output=True,
        text=True,
    )
    words = attr_proc.stdout.split("\0")
    for path, _, value in zip(words[0::3], words[1::3], words[2::3], strict=False):
        if path == "CHANGELOG.md":
            # CHANGELOG.md is tool-owned by release-please and intentionally marked generated.
            continue
        expected = (
            "true"
            if any(PurePosixPath(path).full_match(glob) for glob in generated_globs)
            else "unspecified"
        )
        if value != expected:
            problems.append(
                f"Expected '{path}' to report 'linguist-generated={expected}', got '{value}'."
            )
    return problems
