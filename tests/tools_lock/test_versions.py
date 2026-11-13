"""The version that the command on PATH prints (#5107)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.fakes.process import ProcessAnswer

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tests.support.fakes.process import ProcessFake


def test_version_line_is_the_first_non_empty_line() -> None:
    """Leading blank and space-only lines are skipped, and the line is stripped."""
    from devops_cli.tools_lock.versions import version_line

    assert version_line("\n   \n  1.17.0  \n") == "1.17.0"


def test_version_line_is_none_when_the_output_holds_no_line() -> None:
    """An empty output, and one of blank lines, name no version."""
    from devops_cli.tools_lock.versions import version_line

    assert (version_line(""), version_line("\n  \n")) == (None, None)


def test_path_version_reads_the_command_on_path(process_fake: ProcessFake) -> None:
    """The helper runs the command that PATH resolves, as a local read, and answers its path and
    the version line it prints."""
    from devops_cli.tools_lock.versions import path_version

    process_fake.answer(("/usr/local/bin/openspec", "--version"), ProcessAnswer(stdout="1.17.0\n"))

    assert path_version("openspec") == ("/usr/local/bin/openspec", "1.17.0")
    assert [(call.argv, call.local_read) for call in process_fake.calls] == [
        (("/usr/local/bin/openspec", "--version"), True)
    ]


def test_path_version_is_none_when_path_resolves_no_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command that PATH does not hold names no path and starts no run."""
    from devops_cli.tools_lock.versions import path_version

    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert path_version("openspec") is None


def test_path_version_answers_no_version_when_the_command_fails(
    process_fake: ProcessFake,
) -> None:
    """A run that exits 1 answers the path with no version, so a caller can report it."""
    from devops_cli.tools_lock.versions import path_version

    process_fake.answer(
        ("/usr/local/bin/openspec", "--version"), ProcessAnswer(returncode=1, stderr="boom\n")
    )

    assert path_version("openspec") == ("/usr/local/bin/openspec", None)
