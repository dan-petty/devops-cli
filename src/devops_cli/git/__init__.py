"""Git repository operations, remote tracking, and branch management subsystem."""

from __future__ import annotations

from devops_cli.git.operations import (
    clone_repo,
    create_branch,
    delete_merged_branches,
    fetch_all,
    get_latest_git_tag,
    is_git_clean,
    iter_workspace_repos,
    list_branches,
    pull_tracking,
)

__all__ = [
    "clone_repo",
    "create_branch",
    "delete_merged_branches",
    "fetch_all",
    "get_latest_git_tag",
    "is_git_clean",
    "iter_workspace_repos",
    "list_branches",
    "pull_tracking",
]
