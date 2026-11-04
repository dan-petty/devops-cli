"""The host paths the hermetic floor allows a test to open in a linked git worktree (#3124).

A linked worktree keeps its own git directory, with the `HEAD` file that the telemetry tracer
reads, under the common git directory of the checkout it was added from. That checkout can lie
outside the worktree: `devops ci fail-to-pass` adds its replay tree under the temporary
directory, and a runner or a sandbox adds one beside its clone.
"""

from __future__ import annotations

from pathlib import Path

from tests.support.fakes.process import ProcessFake
from tests.support.host_paths import checkout_roots, is_allowed_host_path


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A main checkout and a linked worktree of it, as `git worktree add` lays them out:
    the worktree's `.git` file names `<main>/.git/worktrees/<name>`, whose `commondir` file
    names `<main>/.git`. Returns the main checkout and the worktree."""
    main = tmp_path / "clone"
    git_dir = main / ".git" / "worktrees" / "tree"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/fix/example\n", encoding="utf-8")
    (git_dir / "commondir").write_text("../..\n", encoding="utf-8")
    (main / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    worktree = tmp_path / "tree"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")
    return main, worktree


def test_a_test_in_a_linked_worktree_may_open_the_head_file_of_its_git_directory(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """The worktree's `HEAD` file and the common git directory open, and the rest of the
    checkout it was added from does not: the roots hold the git directory and no more."""
    main, worktree = _linked_worktree(tmp_path)
    (main / "secret.txt").write_text("not for a test\n", encoding="utf-8")

    roots = checkout_roots(worktree)

    assert [
        is_allowed_host_path(str(main / ".git" / "worktrees" / "tree" / "HEAD"), roots),
        is_allowed_host_path(str(main / ".git" / "HEAD"), roots),
        is_allowed_host_path(str(worktree / "README.md"), roots),
        is_allowed_host_path(str(main / "secret.txt"), roots),
        process_fake.calls,
    ] == [True, True, True, False, []]


def test_a_checkout_that_is_not_a_linked_worktree_adds_no_git_directory(tmp_path: Path) -> None:
    """A checkout whose `.git` is a directory, or a file for a submodule, is its own root."""
    plain = tmp_path / "plain"
    (plain / ".git").mkdir(parents=True)
    submodule = tmp_path / "submodule"
    (tmp_path / "super" / ".git" / "modules" / "sub").mkdir(parents=True)
    submodule.mkdir()
    (submodule / ".git").write_text(
        f"gitdir: {tmp_path / 'super' / '.git' / 'modules' / 'sub'}\n", encoding="utf-8"
    )

    assert (checkout_roots(plain), checkout_roots(submodule)) == (
        (plain.resolve(),),
        (submodule.resolve(),),
    )
