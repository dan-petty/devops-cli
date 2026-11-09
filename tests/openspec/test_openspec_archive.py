"""`devops openspec archive` checks the result on disk before it reports `Archived` (#4270).

The wrapper once decided success from exit codes alone, so a run that exited 0 and moved nothing
printed `Archived`. The fake `openspec` here exits 0 in each case; the tests differ in what it
leaves on disk."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions import ToolExecutionError
from devops_cli.openspec.archive import archive_change
from devops_cli.openspec.tool import isolated_openspec
from tests.support.fakes.openspec import OpenSpecFake

Cli = Callable[..., Any]
CHANGE = "1930-export-widgets"
ARCHIVE_COMMAND = ("archive", CHANGE, "--yes")
SOURCE = Path("openspec/changes") / CHANGE
ARCHIVED = Path("openspec/changes/archive")


def _archive(tree: Path) -> None:
    with isolated_openspec() as tool:
        archive_change(tool, tree, CHANGE)


def _archive_commands(fake: OpenSpecFake) -> list[tuple[str, ...]]:
    return [call.argv for call in fake.calls if call.argv[0] in {"archive", "validate"}]


def test_archive_fails_when_the_tool_exits_zero_and_moves_nothing(
    openspec_fake: OpenSpecFake,
) -> None:
    """A tool that exits 0 and leaves the folder in place is not an archive: the error names the
    change and the folder that is still there, and the validation does not run."""
    tree = openspec_fake.tree("archive-adds-a-spec")
    openspec_fake.script(ARCHIVE_COMMAND, 0, stdout="done\n")

    with pytest.raises(ToolExecutionError) as failed:
        _archive(tree)

    assert (CHANGE in failed.value.message, str(SOURCE) in failed.value.message) == (True, True)
    assert (tree / SOURCE).is_dir()
    assert _archive_commands(openspec_fake) == [ARCHIVE_COMMAND]


def test_archive_fails_when_no_archive_folder_exists(openspec_fake: OpenSpecFake) -> None:
    """A tool that removes the folder and keeps no copy has lost the change: the error says that no
    archive folder of the change exists."""
    tree = openspec_fake.tree("archive-adds-a-spec")
    openspec_fake.script(ARCHIVE_COMMAND, 0, effect=lambda cwd: shutil.rmtree(cwd / SOURCE))

    with pytest.raises(ToolExecutionError) as failed:
        _archive(tree)

    assert (CHANGE in failed.value.message, str(ARCHIVED) in failed.value.message) == (True, True)
    assert _archive_commands(openspec_fake) == [ARCHIVE_COMMAND]


def test_archive_fails_when_the_only_archive_folder_is_an_older_one(
    openspec_fake: OpenSpecFake,
) -> None:
    """An archive of the same name from an earlier day does not prove this run archived: the tool
    left the folder in place and the old copy stays."""
    tree = openspec_fake.tree("archive-adds-a-spec")
    (tree / ARCHIVED / f"2026-01-02-{CHANGE}").mkdir(parents=True)
    openspec_fake.script(ARCHIVE_COMMAND, 0, effect=lambda cwd: shutil.rmtree(cwd / SOURCE))

    with pytest.raises(ToolExecutionError) as failed:
        _archive(tree)

    assert str(ARCHIVED) in failed.value.message


def test_archive_succeeds_when_the_folder_moved(openspec_fake: OpenSpecFake) -> None:
    """The recorded run of the real tool moves the folder: the archive returns and the validation
    runs after it."""
    tree = openspec_fake.tree("archive-adds-a-spec")

    _archive(tree)

    assert (tree / SOURCE).exists() is False
    assert [folder.name for folder in (tree / ARCHIVED).iterdir() if folder.is_dir()] == [
        f"2026-10-23-{CHANGE}"
    ]
    assert _archive_commands(openspec_fake) == [
        ARCHIVE_COMMAND,
        ("validate", "--all", "--strict"),
    ]


def test_archive_command_reports_the_missing_move_and_exits_1(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command prints the reason and never `Archived`."""
    monkeypatch.chdir(openspec_fake.tree("archive-adds-a-spec"))
    openspec_fake.script(ARCHIVE_COMMAND, 0)

    result = cli("openspec", "archive", CHANGE)

    assert result.exit_code == 1
    assert str(SOURCE) in result.output
    assert "Archived" not in result.output


def test_archive_in_dry_run_does_not_report_archived(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dry run starts no process, so nothing is archived: the command lists the two commands it
    would run and says `Would archive`, for a change that does not exist as for one that does."""
    monkeypatch.chdir(openspec_fake.tree("archive-adds-a-spec"))
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "1")

    result = cli("openspec", "archive", "no-such-change-zz")

    assert result.exit_code == 0
    assert "Would archive no-such-change-zz" in result.output
    assert "Archived" not in result.output
    assert "openspec archive no-such-change-zz --yes" in result.output
    assert "openspec validate --all --strict" in result.output
    assert openspec_fake.calls == []


def test_archive_with_the_dry_run_option_does_not_report_archived(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `--dry-run` option of the command gives the same plan as the environment variable."""
    tree = openspec_fake.tree("archive-adds-a-spec")
    monkeypatch.chdir(tree)

    result = cli("--dry-run", "openspec", "archive", CHANGE)

    assert (result.exit_code, "Would archive " + CHANGE in result.output) == (0, True)
    assert "Archived" not in result.output
    assert (tree / SOURCE).is_dir()
    assert openspec_fake.calls == []
