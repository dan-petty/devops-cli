"""Shared domain models for git operations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BranchListing(BaseModel):
    """Result of listing git branches in a repository."""

    model_config = ConfigDict(frozen=True)

    branches: list[str] = Field(default_factory=list, description="Discovered branch names")
    current: str = Field(default="main", description="Active current branch name")


class BranchesListRequest(BaseModel):
    """Request parameters for querying git repository branches."""

    repo_path: str = Field(default=".", description="Target repository path")
    remote: bool = Field(default=False, description="Include remote branches")


class RepoEntry(BaseModel):
    """Metadata for a managed repository."""

    name: str = Field(..., description="Repository name")
    path: str = Field(..., description="Absolute path on disk")
    remote_url: str = Field(default="", description="Origin remote git URL")
    current_branch: str = Field(default="main", description="Active git branch")


class ReposListRequest(BaseModel):
    """Request parameters for listing managed repositories."""

    filter_pattern: str = Field(default="*", description="Glob pattern for filtering repo names")


class ReposListResult(BaseModel):
    """Result of repository listing."""

    total_repos: int = Field(default=0, description="Total count of discovered repositories")
    repos: list[RepoEntry] = Field(default_factory=list, description="Repository entries")


class RepoStatusEntry(BaseModel):
    """Detailed status for a repository."""

    name: str = Field(..., description="Repository name")
    path: str = Field(..., description="Repository directory path")
    branch: str = Field(default="main", description="Current branch name")
    is_clean: bool = Field(
        default=True, description="Whether working tree has no uncommitted changes"
    )
    uncommitted_files_count: int = Field(
        default=0, description="Number of modified/untracked files"
    )
    commits_ahead: int = Field(default=0, description="Commits ahead of upstream tracking branch")
    commits_behind: int = Field(default=0, description="Commits behind upstream tracking branch")


class ReposStatusRequest(BaseModel):
    """Request parameters for inspecting status across repositories."""

    dirty_only: bool = Field(
        default=False, description="Filter only repositories with uncommitted changes"
    )


class ReposStatusResult(BaseModel):
    """Consolidated status report across managed repositories."""

    total_repos: int = Field(default=0, description="Total count of checked repositories")
    dirty_repos_count: int = Field(
        default=0, description="Count of repositories with uncommitted changes"
    )
    repos: list[RepoStatusEntry] = Field(
        default_factory=list, description="Repository status entries"
    )


class ReposSyncRequest(BaseModel):
    """Request parameters for synchronizing repositories with remotes."""

    branch: str = Field(
        default="", description="Specific branch to sync (empty for current branch)"
    )
    prune: bool = Field(default=True, description="Prune deleted remote tracking branches")


class ReposSyncResult(BaseModel):
    """Execution report from repository synchronization."""

    repos_synced: int = Field(default=0, description="Count of successfully synced repositories")
    failed_repos: list[str] = Field(
        default_factory=list, description="Repositories that failed to sync"
    )
    success: bool = Field(
        default=True, description="Whether all repositories synced without errors"
    )
