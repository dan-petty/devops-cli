"""The checkout a review session read, and whether the session is on merged code (#2415).

When a review starts, the session records the commit of the checkout that holds its target and
whether the working tree was clean. A session is on merged code when it reviewed a path, its tree
was clean, and `origin/main` holds its commit: then the text it reviewed is the text of a commit
that `main` holds, so a finding of the session is about merged code. A branch or pull request
review is never on merged code, because a finding about its own diff is fixed before it merges.

The commit is kept apart from the session's subject (`history.review_subject`): the subject keys
review history on the reviewed text, and a commit that changes nothing in the target must not
make a second subject of the same text.

Git runs with `--no-optional-locks`, so reading the tree does not write its index.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.review_schema import ReviewCheckout, ReviewSessionPayload
from devops_cli.config.constants import CONST_GIT_MAIN_BRANCH, CONST_GIT_REMOTE_ORIGIN
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import nearest_checkout
from devops_cli.exceptions import GitOperationError

# `git merge-base --is-ancestor` exits 1 when the first commit is not an ancestor of the second.
_NOT_AN_ANCESTOR = 1


def _git(checkout: Path, *arguments: str, accepted: tuple[int, ...] = (0,)) -> tuple[int, str]:
    """The exit code and standard output of `git` in `checkout`. An exit code outside
    `accepted` raises `GitOperationError` with git's own error."""
    done = run_subprocess(
        ["git", "-C", str(checkout), "--no-optional-locks", *arguments],
        quiet=True,
        local_read=True,
    )
    if done.returncode not in accepted:
        raise GitOperationError(
            f"git cannot read the checkout {checkout}: {done.stderr.strip()}",
            operation=arguments[0],
            details={"exit_code": done.returncode},
        )
    return done.returncode, done.stdout.strip()


def read_checkout(target: Path) -> ReviewCheckout | None:
    """The commit and the clean state of the checkout that holds `target`.

    A target outside any checkout, or in a checkout that holds no commit yet, has none. A file
    that git ignores does not make the tree dirty; an untracked file does.
    """
    checkout = nearest_checkout(target if target.is_dir() else target.parent)
    if checkout is None:
        return None
    # `rev-parse --verify --quiet` exits with 1 when HEAD names no commit, as in a new checkout.
    _, head = _git(checkout, "rev-parse", "--verify", "--quiet", "HEAD", accepted=(0, 1))
    if not head:
        return None
    _, changes = _git(checkout, "status", "--porcelain", "--untracked-files=all")
    return ReviewCheckout(head=head, clean=not changes)


def is_on_merged_code(session: ReviewSessionPayload, repository: Path) -> bool:
    """Whether `session` reviewed a path in a clean tree at a commit that `origin/main` holds.

    `repository` is the checkout whose `origin/main` decides it. A commit that the repository
    does not hold raises `GitOperationError`: the repository cannot tell, so the answer is not no.
    """
    checkout = session.checkout
    if session.subject.get("type") != "path" or checkout is None or not checkout.clean:
        return False
    main = f"{CONST_GIT_REMOTE_ORIGIN}/{CONST_GIT_MAIN_BRANCH}"
    code, _ = _git(
        repository,
        "merge-base",
        "--is-ancestor",
        checkout.head,
        main,
        accepted=(0, _NOT_AN_ANCESTOR),
    )
    return code == 0
