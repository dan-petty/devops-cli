"""Archiving a release's changes in the order they merged, planned before it is written (#1844)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions import OpenSpecArchiveError, ToolExecutionError
from devops_cli.openspec.archive import archive_complete_changes, merge_order, scratch_copy
from devops_cli.openspec.tool import isolated_openspec
from tests.support.fakes.openspec import OpenSpecFake

Git = Callable[..., Any]


def _add_changes(root: Path, git: Git, *names: str) -> None:
    """Commit the change folders `names` in `root` as one commit, whose `.openspec.yaml` each adds."""
    for name in names:
        folder = root / "openspec/changes" / name
        folder.mkdir(parents=True)
        (folder / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
        git(root, "add", f"openspec/changes/{name}")
    git(root, "commit", "-q", "-m", ", ".join(names))


@pytest.fixture
def repo(tmp_path: Path, git: Git) -> Path:
    """A repository with one commit and no change folder."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "commit", "-q", "--allow-empty", "-m", "base")
    return root


def test_changes_are_ordered_by_the_commit_that_added_each_not_by_issue(
    repo: Path, git: Git
) -> None:
    """Issue 1000 merged before issue 100 and 5, so it archives first."""
    for name in ("1000-first", "100-second", "5-third"):
        _add_changes(repo, git, name)

    assert merge_order(repo, ["5-third", "100-second", "1000-first"]) == [
        "1000-first",
        "100-second",
        "5-third",
    ]


def test_a_change_authored_on_top_of_another_archives_after_it(repo: Path, git: Git) -> None:
    """A change that modifies a requirement an earlier change adds cannot archive before it, so
    the order is the history's, parents first, whatever the issue numbers."""
    git(repo, "checkout", "-q", "-b", "topic")
    _add_changes(repo, git, "2000-adds-the-requirement")
    _add_changes(repo, git, "1900-modifies-it")
    git(repo, "checkout", "-q", "-")
    git(repo, "merge", "-q", "--no-ff", "-m", "merge topic", "topic")

    assert merge_order(repo, ["1900-modifies-it", "2000-adds-the-requirement"]) == [
        "2000-adds-the-requirement",
        "1900-modifies-it",
    ]


def test_changes_added_in_one_commit_are_ordered_by_issue_read_as_a_number(
    repo: Path, git: Git
) -> None:
    """999 before 1000, though '1000' sorts before '999' as text."""
    _add_changes(repo, git, "1000-b", "999-a", "1001-c")

    assert merge_order(repo, ["1001-c", "1000-b", "999-a"]) == ["999-a", "1000-b", "1001-c"]


def test_a_change_not_committed_yet_archives_last(repo: Path, git: Git) -> None:
    """A folder still in the working tree is the newest, and several of them keep issue order."""
    _add_changes(repo, git, "2000-committed")
    for name in ("1500-not-yet", "1400-not-yet-either"):
        (repo / "openspec/changes" / name).mkdir(parents=True)

    assert merge_order(repo, ["1500-not-yet", "2000-committed", "1400-not-yet-either"]) == [
        "2000-committed",
        "1400-not-yet-either",
        "1500-not-yet",
    ]


def test_a_renamed_folder_merges_when_it_was_renamed(repo: Path, git: Git) -> None:
    """Git shows a renamed folder as a rename, which is no addition, so a folder renamed after it
    merged would be taken for one not committed and archive last. With renames switched off, its
    `.openspec.yaml` is added at the rename."""
    _add_changes(repo, git, "1700-renamed")
    _add_changes(repo, git, "1800-later")
    git(repo, "mv", "openspec/changes/1700-renamed", "openspec/changes/1700-better-name")
    git(repo, "commit", "-q", "-m", "rename")
    _add_changes(repo, git, "1900-newer")

    assert merge_order(repo, ["1900-newer", "1700-better-name", "1800-later"]) == [
        "1800-later",
        "1700-better-name",
        "1900-newer",
    ]


def test_a_name_that_is_not_an_issue_and_a_slug_archives_after_the_changes_that_are(
    repo: Path,
) -> None:
    """The gate and the cut order whatever folders exist; the folder grammar is a test's to keep."""
    assert merge_order(repo, ["notes", "10-real", "9-real"]) == ["9-real", "10-real", "notes"]


def test_no_history_is_read_when_there_is_nothing_to_order(tmp_path: Path) -> None:
    """A directory that is no repository orders an empty list, and names the failure otherwise."""
    assert merge_order(tmp_path, []) == []
    with pytest.raises(ToolExecutionError) as unreadable:
        merge_order(tmp_path, ["1-a"])
    assert (unreadable.value.exit_code, unreadable.value.details) == (
        1,
        {"tool_name": "git"},
    )


def test_the_cut_archives_the_complete_changes_in_a_scratch_copy_before_the_tree(
    openspec_fake: OpenSpecFake,
) -> None:
    """The sequence is planned in a copy of `openspec/`, so that a change the tool refuses writes
    nothing; only the complete change archives, and the one with an unticked task stays."""
    tree = openspec_fake.tree("pair")

    with isolated_openspec() as tool:
        archived = archive_complete_changes(tool, tree)

    archive_runs = [
        (call.argv, call.cwd == tree) for call in openspec_fake.calls if call.argv[0] == "archive"
    ]
    assert (archived, archive_runs) == (
        ["1901-export-widgets"],
        [
            (("archive", "1901-export-widgets", "--yes", "--json"), False),
            (("archive", "1901-export-widgets", "--yes", "--json"), True),
        ],
    )


def test_a_change_the_tool_refuses_stops_the_cut_before_it_writes_anything(
    openspec_fake: OpenSpecFake,
) -> None:
    """The plan fails in the copy, naming the change and why, and no archive runs in the tree."""
    tree = openspec_fake.tree("modified-spec-absent")

    with isolated_openspec() as tool, pytest.raises(OpenSpecArchiveError) as refused:
        archive_complete_changes(tool, tree)

    assert (
        refused.value.exit_code,
        refused.value.error_code,
        refused.value.change,
        refused.value.reason,
        [
            call.cwd
            for call in openspec_fake.calls
            if call.argv[0] == "archive" and call.cwd == tree
        ],
    ) == (
        1,
        "OPENSPEC_ARCHIVE_FAILED",
        "1911-export-json",
        "widget-export: target spec does not exist; only ADDED requirements are allowed for new "
        "specs. MODIFIED and RENAMED operations require an existing spec.",
        [],
    )


SYMLINK_REFUSED = (
    "openspec/specs/linked: a symbolic link under openspec/ would send the copy that plans the "
    "cut, and the archive in it, outside the folder: replace it with the file or folder it "
    "points to."
)


def _link_to_a_folder_outside(tree: Path, outside: Path) -> None:
    """Link `openspec/specs/linked` in `tree` to `outside`, a folder with a file in it."""
    outside.mkdir()
    (outside / "secret.md").write_text("Not OpenSpec's.\n", encoding="utf-8")
    (tree / "openspec/specs/linked").symlink_to(outside, target_is_directory=True)


def test_a_symlink_under_openspec_is_refused_and_its_target_is_not_copied(
    openspec_fake: OpenSpecFake, tmp_path: Path
) -> None:
    """A copy that follows a link would carry a folder outside `openspec/` into the scratch
    directory, and an archive in it could write through the link: the copy refuses, naming the
    link, and copies nothing."""
    tree = openspec_fake.tree("pair")
    _link_to_a_folder_outside(tree, tmp_path / "outside")

    with pytest.raises(ToolExecutionError) as refused, scratch_copy(tree):
        pytest.fail("the copy was made")

    assert (refused.value.exit_code, refused.value.message) == (1, SYMLINK_REFUSED)


def test_a_symlink_stops_the_cut_before_the_tool_archives_anything(
    openspec_fake: OpenSpecFake, tmp_path: Path
) -> None:
    """The cut does not run the gate, so its own copy refuses the link, and no archive runs."""
    tree = openspec_fake.tree("pair")
    _link_to_a_folder_outside(tree, tmp_path / "outside")

    with isolated_openspec() as tool, pytest.raises(ToolExecutionError) as refused:
        archive_complete_changes(tool, tree)

    assert (
        refused.value.message,
        [call.argv for call in openspec_fake.calls if call.argv[0] == "archive"],
    ) == (SYMLINK_REFUSED, [])
