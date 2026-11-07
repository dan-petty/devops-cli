"""The state of devops-cli's own source checkout, which a review compares at start and end (#1142)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.core.repo import (
    _own_source_dir,
    install_own_source_dir,
    own_source_state,
    reset_own_source_dir,
    reset_repo_caches,
)
from tests.support.fakes.git import GitFake


def test_own_source_state_changes_with_each_edit_and_commit(
    tmp_path: Path, git_fake: GitFake
) -> None:
    """A commit changes it, and so does a further edit to a file that is already modified; a
    new untracked file does not."""
    git_fake.replay("source_state")
    package = tmp_path / "own" / "src" / "devops_cli"
    package.mkdir(parents=True)
    (tmp_path / "own" / ".git").mkdir()
    module = package / "__init__.py"
    module.write_text('"""devops-cli."""\n', encoding="utf-8")

    states = [own_source_state(package)]
    (package / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    states.append(own_source_state(package))
    for text in ("x = 1\n", "x = 2\n"):
        module.write_text(text, encoding="utf-8")
        states.append(own_source_state(package))
    states.append(own_source_state(package))

    assert (states[0] == states[1], len(set(states[1:])), all(states)) == (True, 4, True)


def test_an_installed_copy_has_no_source_state() -> None:
    """devops-cli installed in site-packages, as every test runs it, reads no checkout."""
    assert own_source_state() is None


def test_a_reset_of_the_caches_keeps_the_installed_source_directory(tmp_path: Path) -> None:
    """A test that clears the repository caches in its middle stays where the floor put it; only
    `reset_own_source_dir` removes the directory."""
    install_own_source_dir(tmp_path)

    reset_repo_caches()
    kept = _own_source_dir()
    reset_own_source_dir()

    assert (kept, _own_source_dir() == tmp_path) == (tmp_path, False)
