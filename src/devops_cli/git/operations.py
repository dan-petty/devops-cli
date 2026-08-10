"""Git operations using gitpython."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import git as gitlib


def _ensure_known_host(hostname: str = "github.com") -> None:
    """Add *hostname* to ~/.ssh/known_hosts when it is missing."""
    ssh_dir = Path.home() / ".ssh"
    known_hosts = ssh_dir / "known_hosts"
    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if known_hosts.exists():
        result = subprocess.run(
            ["ssh-keygen", "-F", hostname, "-f", str(known_hosts)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return

    result = subprocess.run(
        ["ssh-keyscan", "-t", "ed25519", hostname],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
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
    if url.startswith(("git@github.com:", "ssh://git@github.com/")):
        _ensure_known_host()
    gitlib.Repo.clone_from(url, str(dest))


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
) -> tuple[list[str], str]:
    """Return *(branch_names, current_branch)*."""
    repo = gitlib.Repo(str(repo_dir))
    current = "HEAD" if repo.head.is_detached else repo.active_branch.name
    local = sorted(b.name for b in repo.branches)
    if not all_branches:
        return local, current
    remote_names = [
        ref.name for remote in repo.remotes for ref in remote.refs if not ref.name.endswith("/HEAD")
    ]
    return sorted(set(local) | set(remote_names)), current


def delete_merged_branches(repo_dir: Path, dry_run: bool = False) -> list[str]:
    """Delete local branches that have been merged into the default branch."""
    repo = gitlib.Repo(str(repo_dir))
    default = next(
        (b.name for b in repo.branches if b.name in ("main", "master")),
        repo.branches[0].name if repo.branches else None,
    )
    if not default:
        return []

    result = subprocess.run(
        ["git", "-C", str(repo_dir), "branch", "--merged", default],
        capture_output=True,
        text=True,
    )
    merged = {b.strip().lstrip("* ") for b in result.stdout.splitlines()}
    protected = {default, "main", "master"}
    to_delete = [b for b in repo.branches if b.name in merged - protected]

    deleted: list[str] = []
    for branch in to_delete:
        if not dry_run:
            repo.delete_head(branch, force=False)
        deleted.append(branch.name)
    return deleted
