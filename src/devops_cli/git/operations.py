"""Git repository operations using GitPython and git CLI subprocesses.

Functionality:
- URL normalization: forces HTTPS for web URLs while leaving SSH URLs intact.
- SSH known_hosts management: ensures GitHub host key presence in `~/.ssh/known_hosts` (mode 0600).
- Branch management: listing, tracking branch pull, and merged branch deletion.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Generator
from pathlib import Path

import git as gitlib

from devops_cli.config.constants import (
    CONST_GIT_DIR_NAME,
    CONST_GITHUB_HOST,
    CONST_GITHUB_HTTP_PREFIX,
    CONST_GITHUB_HTTPS_PREFIX,
    CONST_GITHUB_SSH_PREFIX,
    CONST_GITHUB_SSH_URL_PREFIX,
    CONST_PERM_DIR,
    CONST_URL_SCHEME_HTTP,
    CONST_URL_SCHEME_HTTPS,
)
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_FAST_TIMEOUT_SECONDS
from devops_cli.models.git import BranchListing


def _normalize_clone_url(url: str) -> str:
    if url.startswith((CONST_GITHUB_SSH_PREFIX, CONST_GITHUB_SSH_URL_PREFIX)):
        return url
    if url.startswith(f"{CONST_GITHUB_HOST}/"):
        return f"{CONST_URL_SCHEME_HTTPS}{url}"
    if url.startswith(CONST_GITHUB_HTTP_PREFIX):
        return f"{CONST_URL_SCHEME_HTTPS}{url.removeprefix(CONST_URL_SCHEME_HTTP)}"
    if url.startswith(CONST_GITHUB_HTTPS_PREFIX):
        return url
    return url


def iter_workspace_repos(root: Path) -> Generator[Path]:
    """Yield all valid Git repository directories under *root* across 2 directory levels."""
    if not root.exists():
        return
    resolved_root = root.resolve()
    for group_dir in sorted(root.iterdir()):
        if not group_dir.is_dir():
            continue
        for repo_dir in sorted(group_dir.iterdir()):
            if (repo_dir / CONST_GIT_DIR_NAME).exists() and repo_dir.resolve().is_relative_to(
                resolved_root
            ):
                yield repo_dir


def _ensure_known_host(hostname: str = CONST_GITHUB_HOST) -> None:
    """Add *hostname* to ~/.ssh/known_hosts when it is missing."""
    ssh_dir = Path.home() / ".ssh"
    known_hosts = ssh_dir / "known_hosts"
    ssh_dir.mkdir(mode=CONST_PERM_DIR, parents=True, exist_ok=True)
    if known_hosts.exists():
        result = subprocess.run(
            ["ssh-keygen", "-F", hostname, "-f", str(known_hosts)],
            capture_output=True,
            text=True,
            check=False,
            timeout=DEFAULT_SUBPROCESS_FAST_TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            return

    result = subprocess.run(
        ["ssh-keyscan", "-t", "ed25519", hostname],
        capture_output=True,
        text=True,
        check=False,
        timeout=DEFAULT_SUBPROCESS_FAST_TIMEOUT_SECONDS,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return

    with known_hosts.open("a", encoding="utf-8") as handle:
        if known_hosts.stat().st_size > 0 and not result.stdout.startswith(os.linesep):
            handle.write("\n")
        handle.write(result.stdout)
    known_hosts.chmod(0o600)


def clone_repo(url: str, dest: Path) -> None:
    """Clone a repository to *dest*."""
    normalized_url = _normalize_clone_url(url)
    if normalized_url.startswith((CONST_GITHUB_SSH_PREFIX, CONST_GITHUB_SSH_URL_PREFIX)):
        _ensure_known_host()
    gitlib.Repo.clone_from(normalized_url, str(dest))


def fetch_all(repo_dir: Path) -> None:
    """Fetch all remotes with pruning."""
    repo = gitlib.Repo(str(repo_dir))
    for remote in repo.remotes:
        try:
            remote.fetch(prune=True)
        except gitlib.GitCommandError:
            pass


def pull_tracking(repo_dir: Path) -> None:
    """Pull the current tracking branch if one is configured."""
    repo = gitlib.Repo(str(repo_dir))
    try:
        if not repo.head.is_detached:
            tracking = repo.active_branch.tracking_branch()
            if tracking:
                repo.remotes[tracking.remote_name].pull(repo.active_branch.name)
    except gitlib.GitCommandError, IndexError:
        pass


def create_branch(repo_dir: Path, branch_name: str) -> None:
    """Create and checkout a new branch from the current HEAD."""
    repo = gitlib.Repo(str(repo_dir))
    if branch_name in [b.name for b in repo.branches]:
        raise ValueError(f"Branch '{branch_name}' already exists")
    repo.git.checkout("-b", branch_name)


def list_branches(
    repo_dir: Path,
    all_branches: bool = False,
) -> BranchListing:
    """Return a BranchListing with branch names and the current branch name."""
    repo = gitlib.Repo(str(repo_dir))
    current = "HEAD" if repo.head.is_detached else repo.active_branch.name
    local = sorted(b.name for b in repo.branches)
    if not all_branches:
        return BranchListing(branches=local, current=current)
    remote_names = [
        ref.name for remote in repo.remotes for ref in remote.refs if not ref.name.endswith("/HEAD")
    ]
    return BranchListing(branches=sorted(set(local) | set(remote_names)), current=current)


def delete_merged_branches(repo_dir: Path, dry_run: bool = False) -> list[str]:
    """Delete local branches that have been merged into the default branch."""
    repo = gitlib.Repo(str(repo_dir))
    default = next(
        (b.name for b in repo.branches if b.name in ("main", "master")),
        repo.branches[0].name if repo.branches else None,
    )
    if not default:
        return []

    merged_output = repo.git.branch("--merged", default)
    merged = {b.strip().lstrip("* ") for b in merged_output.splitlines()}
    protected = {default, "main", "master"}
    to_delete = [b for b in repo.branches if b.name in merged - protected]

    deleted: list[str] = []
    for branch in to_delete:
        if not dry_run:
            repo.delete_head(branch, force=False)
        deleted.append(branch.name)
    return deleted
