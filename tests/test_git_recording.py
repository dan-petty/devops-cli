"""The recorder of the git transcripts runs the real git the same way on every host (#2146)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.git_recording import RecordingRunner
from tests.support.git_scenarios import Workspace


def test_the_recording_reads_no_git_configuration_file_of_the_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transcript holds what git does with no configuration, so a runner whose user or system
    file sets `pull.ff` or `core.*` records the same text as any other host."""
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("[pull]\n\tff = only\n[core]\n\tautocrlf = true\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    runner = RecordingRunner(Workspace(tmp_path / "ws", recording=True))
    (tmp_path / "ws").mkdir()

    listed = runner.run(["git", "config", "--list", "--show-scope"], cwd=tmp_path / "ws")

    assert [
        line
        for line in listed.stdout.splitlines()
        if line.startswith(("global", "system", "pull.", "core.autocrlf"))
    ] == []
