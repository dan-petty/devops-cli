"""The clone of a phased step (#3702): a plain clone of the issue branch, as a developer makes one.

`prepare` makes it before any code of the pull request runs: a full clone of the repository on
GitHub in the work folder of the run, which is new to the run, and a switch to the issue branch. A
pushed branch must hold only commits of the App past the default branch, apart from a clean merge
(`check_authors`). `prepare` records two commits that it read itself: the base, the tip of the
default branch, and the lease, the tip of the pushed branch or empty for a new branch. No call
with the token touches the clone after the agent phase starts: `publish` works in a new
repository. Until #3700, an earlier item of the same Job can have run code of a pull request in
the home folder, so the git calls read no global or system configuration (`git_call`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME
from devops_cli.git.branch_authors import LOG_FORMAT, person_authors
from devops_cli.git.worktree_add import check_authors
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.phases.publish import git_call


@dataclass(frozen=True)
class BranchClone:
    """The clone on the issue branch: its path, the branch, the default branch, the base and the
    lease."""

    path: Path
    branch: str
    default: str
    base: str
    lease: str


def clone_branch(work: Path, *, url: str, issue: int, branch: str) -> BranchClone:
    """Clone the repository at `url` into the work folder `work`, and switch to `branch` of item
    `issue`: the pushed branch, or a new branch at the tip of the default branch. The clone commits
    as the identity of the session, the bot of the App in a runner."""
    path = work / CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME
    work.mkdir(parents=True, exist_ok=True)
    git_call(work, "clone", "--quiet", url, str(path))
    default = git_call(path, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    default = default.removeprefix("origin/")
    base = git_call(path, "rev-parse", f"refs/remotes/origin/{default}").strip()
    remote = f"refs/remotes/origin/{branch}"
    if git_call(path, "for-each-ref", "--format=%(objectname)", remote).strip():
        log = git_call(path, "log", LOG_FORMAT, f"origin/{default}..{remote}")
        check_authors(issue, branch, person_authors([BIN_GIT, "-C", str(path)], log))
        git_call(path, "switch", "--quiet", "-C", branch, remote)
        lease = git_call(path, "rev-parse", "HEAD").strip()
    else:
        git_call(path, "switch", "--quiet", "-c", branch, f"origin/{default}")
        lease = ""
    session = get_github_session()
    git_call(path, "config", "user.name", session.login)
    git_call(path, "config", "user.email", session.commit_email)
    return BranchClone(path, branch, default, base, lease)


__all__ = ["BranchClone", "clone_branch"]
