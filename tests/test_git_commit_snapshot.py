"""`commit_snapshot` against the real git: the commit holds the named files as they are (#2146).

The fake cannot see the content of a file or what a glob matches, so these tests start git.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.git.operations import commit_snapshot

WHEN = datetime(2026, 10, 3, tzinfo=UTC)


@pytest.fixture(autouse=True)
def bare_git_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A home with no git file. The runner passes no `GIT_` key of the test on, so the home is the
    one place that the user configuration of the child comes from."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return home


def _snapshot(repo: Path, paths: list[str]) -> str:
    return commit_snapshot(repo, paths, "message\n", author="Example Author", email="", date=WHEN)


def _tracked(repo: Path) -> list[str]:
    done = subprocess.run(
        ["git", "-C", str(repo), "ls-files"], capture_output=True, text=True, check=True
    )
    return done.stdout.splitlines()


def test_a_path_with_a_glob_character_stages_that_file_and_no_other(tmp_path: Path) -> None:
    """Each path is a file name, not a pattern: `[ab].py` does not stage `a.py` and `b.py`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for name in ("a.py", "b.py", "[ab].py"):
        (repo / name).write_text("x = 1\n")

    _snapshot(repo, ["[ab].py"])

    assert _tracked(repo) == ["[ab].py"]


def test_the_user_attributes_file_does_not_change_the_commit(
    tmp_path: Path, bare_git_configuration: Path
) -> None:
    """A line-ending rule in the attributes file of the user does not change a byte of the file
    that is committed, so the commit is the same on every host."""
    for name in ("plain", "converted"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "a.txt").write_bytes(b"one\r\ntwo\r\n")
    plain = _snapshot(tmp_path / "plain", ["a.txt"])
    attributes = tmp_path / "attributes"
    attributes.write_text("* text\n")
    (bare_git_configuration / ".gitconfig").write_text(f"[core]\n\tattributesFile = {attributes}\n")

    converted = _snapshot(tmp_path / "converted", ["a.txt"])

    assert converted == plain
