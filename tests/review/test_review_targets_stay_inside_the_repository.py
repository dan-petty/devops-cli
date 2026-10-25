"""A review reads only files inside the repository root (#2151).

`find_repo_files` refuses a target outside the root, gives no files for a symlinked target file,
and leaves out each candidate that is a symlink or whose real path is outside the root. Each test
builds the repository and the tree beside it under `tmp_path` and starts no program.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_ERROR_CODE_SECURITY, CONST_EXIT_FAILURE
from devops_cli.exceptions import SecurityError
from devops_cli.review.targets import find_repo_files


def _repository_beside_an_outside_tree(tmp_path: Path) -> tuple[Path, Path]:
    """A repository root with one source file, and a tree beside it that holds one file."""
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("print('inside')\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("print('outside')\n", encoding="utf-8")
    return root, outside


def _target(root: Path, outside: Path, kind: str) -> Path:
    """A target whose real path is outside `root`, of the given kind."""
    if kind == "directory":
        return outside
    if kind == "file":
        return outside / "secret.py"
    if kind == "parent-reference":
        return root / ".." / "outside"
    link = root / "src" / kind
    link.symlink_to(outside / "secret.py" if kind == "file-symlink" else outside)
    return link


@pytest.mark.parametrize(
    "kind", ["directory", "file", "parent-reference", "file-symlink", "directory-symlink"]
)
def test_a_target_outside_the_repository_root_is_refused(tmp_path: Path, kind: str) -> None:
    """A target whose real path is outside the root raises `SecurityError`, also when a path
    inside the root names it through `..` or a symlink."""
    root, outside = _repository_beside_an_outside_tree(tmp_path)
    target = _target(root, outside, kind)

    with pytest.raises(SecurityError) as refused:
        find_repo_files(target, repo_root=root)

    assert (refused.value.message, refused.value.exit_code, refused.value.error_code) == (
        "target must be a sub-path of the repository root",
        CONST_EXIT_FAILURE,
        CONST_ERROR_CODE_SECURITY,
    )


def test_a_symlinked_target_file_gives_no_files(tmp_path: Path) -> None:
    """A target file that is a symlink gives no files, also when it points inside the root; the
    file it points to gives itself."""
    root, _ = _repository_beside_an_outside_tree(tmp_path)
    source = root / "src" / "app.py"
    alias = root / "src" / "alias.py"
    alias.symlink_to(source)

    assert (
        find_repo_files(alias, repo_root=root),
        find_repo_files(source, repo_root=root),
    ) == ([], [source])


def test_a_directory_target_leaves_out_its_symlinked_files(tmp_path: Path) -> None:
    """A directory target gives none of the symlinks it holds: not one that points to a file
    outside the root, and not one that points to a file inside it."""
    root, outside = _repository_beside_an_outside_tree(tmp_path)
    (root / "src" / "leak.py").symlink_to(outside / "secret.py")
    (root / "src" / "alias.py").symlink_to(root / "src" / "app.py")

    assert find_repo_files(root / "src", repo_root=root) == [root / "src" / "app.py"]


def test_a_directory_target_leaves_out_a_file_reached_through_a_symlinked_directory(
    tmp_path: Path,
) -> None:
    """A pattern with a directory part follows a symlinked directory, so a file below it is no
    symlink itself; its real path is outside the root, and the result leaves it out."""
    root, outside = _repository_beside_an_outside_tree(tmp_path)
    (root / "vendor").symlink_to(outside, target_is_directory=True)

    assert sorted(root.rglob("*/*.py")) == [root / "src" / "app.py", root / "vendor" / "secret.py"]
    assert find_repo_files(root, pattern="*/*.py", repo_root=root) == [root / "src" / "app.py"]
