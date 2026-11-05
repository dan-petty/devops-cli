"""The authors of the commits that a pushed branch holds past the default branch, except a clean
merge (#3392).

GitHub writes a merge commit for the "Update branch" button, with the person who pressed it as the
author. A merge commit with two parents is a clean merge when `git merge-tree --write-tree` gives
its tree: the merge changes no file by hand and resolves no conflict. The implement job, the stage
reconcile and the takeover of `worktrees add` leave a clean merge out of the authors. A merge that
changed a file or resolved a conflict keeps its author.
"""

from __future__ import annotations

from collections.abc import Sequence

from devops_cli.core.process import run_subprocess

# `%x1f` is the unit separator. It keeps an author name apart from the parents and the tree.
LOG_FORMAT = "--format=%an%x1f%P%x1f%T"
_FIELD_SEPARATOR = "\x1f"


def person_authors(git: Sequence[str], log: str) -> list[str]:
    """The author of each commit in `log`, the output of `git log LOG_FORMAT`, except a clean merge.
    `git` is the argv that starts git in the repository, such as `["git", "-C", path]`."""
    authors: list[str] = []
    for line in log.splitlines():
        author, parents, tree = line.split(_FIELD_SEPARATOR)
        if not _is_clean_merge(git, parents.split(), tree):
            authors.append(author)
    return authors


def _is_clean_merge(git: Sequence[str], parents: list[str], tree: str) -> bool:
    """Whether the commit has two parents, and `git merge-tree --write-tree` of them exits 0 and
    prints `tree`. A conflict exits 1, so a merge that resolved a conflict is not a clean merge."""
    if len(parents) != 2:
        return False
    proc = run_subprocess(
        [*git, "merge-tree", "--write-tree", *parents],
        check=False,
        quiet=True,
        local_read=True,
    )
    return proc.returncode == 0 and proc.stdout.split()[:1] == [tree]
