"""The state of devops-cli's own source checkout, which a review compares at start and end (#1142)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.core.repo import own_source_state


def test_own_source_state_changes_with_each_edit_and_commit(
    tmp_path: Path, git: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commit changes it, and so does a further edit to a file that is already modified; a
    new untracked file does not."""
    package = tmp_path / "own" / "src" / "devops_cli"
    package.mkdir(parents=True)
    module = package / "__init__.py"
    module.write_text('"""devops-cli."""\n', encoding="utf-8")
    git(tmp_path / "own", "init", "--quiet")
    git(tmp_path / "own", "add", ".")
    git(tmp_path / "own", "commit", "--quiet", "-m", "first")
    monkeypatch.setattr("devops_cli.core.repo._own_source_dir", lambda: package.resolve())

    states = [own_source_state()]
    (package / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    states.append(own_source_state())
    for text in ("x = 1\n", "x = 2\n"):
        module.write_text(text, encoding="utf-8")
        states.append(own_source_state())
    git(tmp_path / "own", "commit", "--quiet", "-am", "second")
    states.append(own_source_state())

    assert (states[0] == states[1], len(set(states[1:])), all(states)) == (True, 4, True)


def test_an_installed_copy_has_no_source_state() -> None:
    """devops-cli installed in site-packages, as every test runs it, reads no checkout."""
    assert own_source_state() is None
