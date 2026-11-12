"""The documentation inventory: every committed Markdown file is in exactly one class, the
generated class is what the generator writes, and every hand-written and prompt document names
only real commands (#1103). A file that no other class claims is hand-written (#3204)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePosixPath

import pytest

from devops_cli.ai.instruction_generator import (
    CONST_CLAUDE_MD_FILENAME,
    CONST_COPILOT_INSTRUCTIONS_PATH,
    CONST_GEMINI_MD_FILENAME,
)
from devops_cli.config.constants import (
    CONST_DOCS_CLASS_GENERATED,
    CONST_DOCS_CLASS_HAND_WRITTEN,
    CONST_DOCS_CLASS_PROMPT,
    CONST_DOCS_CLASS_RECORD,
    CONST_DOCS_CLASS_TOOL_GENERATED,
    CONST_DOCS_CLASS_TOOL_OWNED,
    CONST_DOCS_INVENTORY,
)
from devops_cli.core.repo import list_repo_files
from devops_cli.docs.generator import DocGenerator
from devops_cli.docs.inventory import document_class, hand_written_documents
from devops_cli.docs.markdown_argv_collector import (
    collect_documented_argv_references,
    is_pattern_entry,
)
from devops_cli.docs.source_argv_collector import describe_unresolved_references
from tests.support.paths import REPO_ROOT


def _matches(path: str, globs: Iterable[str]) -> bool:
    return any(PurePosixPath(path).full_match(glob) for glob in globs)


def _committed_markdown_files() -> list[str]:
    """Every Markdown file the repository holds, tracked or about to be, by repository path."""
    return [
        path.relative_to(REPO_ROOT).as_posix()
        for path in list_repo_files(REPO_ROOT)
        if path.suffix == ".md"
    ]


def _inventory_problems(
    files: Iterable[str],
) -> tuple[dict[str, list[str]], list[str]]:
    """The files in several explicit classes, and the entries naming one document that no file
    is. A pattern entry may match no file, and a file no explicit class claims is hand-written."""
    files = list(files)
    present = set(files)
    classes_by_file = {
        path: sorted(name for name, globs in CONST_DOCS_INVENTORY.items() if _matches(path, globs))
        for path in files
    }
    ambiguous = {path: names for path, names in classes_by_file.items() if len(names) > 1}
    matching_no_file = [
        glob
        for globs in CONST_DOCS_INVENTORY.values()
        for glob in globs
        if not is_pattern_entry(glob) and glob not in present
    ]
    return ambiguous, matching_no_file


def test_every_committed_markdown_file_has_exactly_one_class() -> None:
    """Verify no Markdown file is in two explicit classes, and each inventory entry matches a
    file, so a deleted document leaves no entry behind. A new document that no explicit class
    claims is hand-written."""
    assert _inventory_problems(_committed_markdown_files()) == ({}, [])


def test_a_listed_document_with_no_file_fails_the_inventory() -> None:
    """Verify an entry naming one document that is not committed is reported, so deleting a
    document leaves no entry behind."""
    files = [path for path in _committed_markdown_files() if path != "CHANGELOG.md"]

    assert _inventory_problems(files) == ({}, ["CHANGELOG.md"])


def test_a_page_that_no_other_class_matches_is_hand_written() -> None:
    """Verify a Markdown file at a path that no explicit class matches is hand-written with no
    entry of its own, so a new page, or a committed skill, needs no edit of the inventory."""
    paths = ["docs/example.md", "openspec/notes.md", ".claude/skills/new-scaffold/SKILL.md"]

    assert [document_class(path) for path in paths] == [CONST_DOCS_CLASS_HAND_WRITTEN] * 3


def test_a_page_that_another_class_claims_is_not_hand_written() -> None:
    """Verify a page that an explicit class matches keeps that class, so the complement hides no
    generated, record, prompt or tool page."""
    paths = [
        "docs/commands/ci.md",
        "CHANGELOG.md",
        "docs/adr/0001-example.md",
        "src/devops_cli/ai/tasks/example.md",
        ".claude/skills/openspec-explore/SKILL.md",
    ]

    assert [document_class(path) for path in paths] == [
        CONST_DOCS_CLASS_GENERATED,
        CONST_DOCS_CLASS_TOOL_OWNED,
        CONST_DOCS_CLASS_RECORD,
        CONST_DOCS_CLASS_PROMPT,
        CONST_DOCS_CLASS_TOOL_GENERATED,
    ]


def test_the_hand_written_documents_of_a_root_are_the_pages_no_other_class_claims(
    tmp_path: Path,
) -> None:
    """Verify the listing of a root holds a page that no explicit class claims, and holds none
    that one does."""
    (tmp_path / "pyproject.toml").touch()
    for name in ("README.md", "docs/example.md", "docs/adr/0001-example.md", "CHANGELOG.md"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("Text.\n", encoding="utf-8")

    listed = [path.relative_to(tmp_path).as_posix() for path in hand_written_documents(tmp_path)]

    assert listed == ["README.md", "docs/example.md"]


@pytest.mark.parametrize(
    ("entry", "is_pattern"),
    [
        ("docs/SDLC.md", False),
        ("docs/commands/*.md", True),
        ("openspec/changes/archive/*/tasks.md", True),
        ("k8s/**/README.md", True),
        ("docs/adr/000?.md", True),
    ],
)
def test_an_inventory_entry_is_a_pattern_when_it_holds_a_glob_wildcard(
    entry: str, is_pattern: bool
) -> None:
    """Verify an entry is a pattern exactly when `glob` reads a wildcard in it."""
    assert is_pattern_entry(entry) is is_pattern


def test_the_generated_class_is_what_the_generator_writes() -> None:
    """Verify the generated class is the documents `DocGenerator` writes under `docs/` plus the
    three instruction stubs. The generator also returns each page with a synced block, such as
    the grade table of `docs/roadmap/job-success.md`, so these are hand-written. It writes no
    block of `README.md` (#5163)."""
    generator = DocGenerator(REPO_ROOT)
    written = generator.generate_all_docs(REPO_ROOT / "docs")
    synced = set(generator.synced_blocks())
    generated_by_the_generator = {
        *(f"docs/{name}" for name in written if name not in synced),
        CONST_CLAUDE_MD_FILENAME,
        CONST_GEMINI_MD_FILENAME,
        CONST_COPILOT_INSTRUCTIONS_PATH,
    }
    generated_in_the_inventory = {
        path
        for path in _committed_markdown_files()
        if _matches(path, CONST_DOCS_INVENTORY[CONST_DOCS_CLASS_GENERATED])
    }

    assert (
        sorted(generated_in_the_inventory ^ generated_by_the_generator),
        document_class("README.md"),
    ) == ([], CONST_DOCS_CLASS_HAND_WRITTEN)


def test_every_hand_written_document_names_only_real_commands() -> None:
    """Verify every `devops` command line in a hand-written or prompt document, the knowledge
    base included, resolves statically against the live command tree."""
    references = collect_documented_argv_references(REPO_ROOT)
    problems = describe_unresolved_references(references)

    documents_read = {reference.path for reference in references}
    cli_reference_lines = sum(
        1 for reference in references if reference.path.endswith("cli_command_reference.md")
    )
    assert (
        problems,
        {"README.md", "docs/SELF_IMPROVEMENT.md", "CONTRIBUTING.md", "k8s/README.md"}
        <= documents_read,
        cli_reference_lines >= 60,
    ) == ([], True, True)
