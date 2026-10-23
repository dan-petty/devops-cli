"""The documentation inventory: every committed Markdown file is in exactly one class, the
generated class is what the generator writes, and every hand-written and prompt document names
only real commands (#1103)."""

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
    CONST_CHANGELOG_FRAGMENTS_DIR,
    CONST_DOCS_CLASS_GENERATED,
    CONST_DOCS_CLASS_HAND_WRITTEN,
    CONST_DOCS_INVENTORY,
    CONST_DOCS_NAME_CHECKED_CLASSES,
)
from devops_cli.core.repo import list_repo_files
from devops_cli.docs.generator import DocGenerator
from devops_cli.docs.markdown_argv_collector import (
    check_documented_argv,
    collect_documented_argv_references,
    is_pattern_entry,
)
from devops_cli.lang import MESSAGES
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
) -> tuple[list[str], dict[str, list[str]], list[str]]:
    """The files in no class, the files in several, and the entries naming one document that no
    file is. A pattern entry matches the files of the release phase, so it may match none."""
    files = list(files)
    present = set(files)
    classes_by_file = {
        path: sorted(name for name, globs in CONST_DOCS_INVENTORY.items() if _matches(path, globs))
        for path in files
    }
    unclassified = [path for path, names in classes_by_file.items() if not names]
    ambiguous = {path: names for path, names in classes_by_file.items() if len(names) > 1}
    matching_no_file = [
        glob
        for globs in CONST_DOCS_INVENTORY.values()
        for glob in globs
        if not is_pattern_entry(glob) and glob not in present
    ]
    return unclassified, ambiguous, matching_no_file


def test_every_committed_markdown_file_has_exactly_one_class() -> None:
    """Verify each Markdown file is in one class, and each inventory entry matches a file, so
    a new document is classified in the pull request that adds it and a deleted one leaves no
    entry behind."""
    assert _inventory_problems(_committed_markdown_files()) == ([], {}, [])


def test_the_inventory_holds_with_no_changelog_fragment_committed() -> None:
    """Verify the inventory passes on a tree without a `changelog.d/<issue>.md`, as the release
    cut leaves it and as a release branch is before its first fragment."""
    fragments = [f"{CONST_CHANGELOG_FRAGMENTS_DIR}/[0-9]*.md"]
    files = [path for path in _committed_markdown_files() if not _matches(path, fragments)]

    assert ("changelog.d/README.md" in files, _inventory_problems(files)) == (True, ([], {}, []))


def test_a_listed_document_with_no_file_fails_the_inventory() -> None:
    """Verify an entry naming one document that is not committed is reported, so deleting a
    document leaves no entry behind."""
    files = [path for path in _committed_markdown_files() if path != "docs/SDLC.md"]

    assert _inventory_problems(files) == ([], {}, ["docs/SDLC.md"])


def test_a_pattern_entry_with_no_file_still_leaves_a_stray_file_unclassified() -> None:
    """Verify a pattern entry that matches no file is not an error, while a file beside it that
    no entry covers is still unclassified."""
    files = ["changelog.d/README.md", "changelog.d/notes.md"]

    assert _inventory_problems(files)[0] == ["changelog.d/notes.md"]


@pytest.mark.parametrize(
    ("entry", "is_pattern"),
    [
        ("docs/SDLC.md", False),
        ("docs/commands/*.md", True),
        ("changelog.d/[0-9]*.md", True),
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
    three instruction stubs. The generator also returns `README.md`, whose synced command matrix
    is its only generated part, so it is hand-written."""
    written = DocGenerator(REPO_ROOT).generate_all_docs(REPO_ROOT / "docs")
    generated_by_the_generator = {
        *(f"docs/{name}" for name in written if name != "README.md"),
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
        _matches("README.md", CONST_DOCS_INVENTORY[CONST_DOCS_CLASS_HAND_WRITTEN]),
    ) == ([], True)


def test_every_hand_written_document_names_only_real_commands() -> None:
    """Verify every `devops` command line in a hand-written or prompt document, the knowledge
    base included, resolves statically against the live command tree."""
    problems = check_documented_argv(REPO_ROOT)
    references = collect_documented_argv_references(REPO_ROOT)

    documents_read = {reference.path for reference in references}
    cli_reference_lines = sum(
        1 for reference in references if reference.path.endswith("cli_command_reference.md")
    )
    assert (
        problems,
        {"README.md", "docs/SELF_IMPROVEMENT.md", "RELEASE_CYCLE.md", "k8s/README.md"}
        <= documents_read,
        cli_reference_lines >= 60,
    ) == ([], True, True)


def test_a_listed_document_that_is_missing_fails_the_name_gate(tmp_path: Path) -> None:
    """Verify a document the inventory lists by path that has no file fails the gate, naming the
    entry, instead of being skipped; that a listed document that exists is not reported; and
    that a pattern entry matching no file is not."""
    (tmp_path / "pyproject.toml").touch()
    (tmp_path / "README.md").write_text("Run `devops docs check` to verify.\n", encoding="utf-8")

    problems = check_documented_argv(tmp_path)

    expected = [
        MESSAGES.docs.inventory_entry_missing.format(entry=entry)
        for name in CONST_DOCS_NAME_CHECKED_CLASSES
        for entry in CONST_DOCS_INVENTORY[name]
        if entry != "README.md" and not is_pattern_entry(entry)
    ]
    assert problems == expected
