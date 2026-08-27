"""Pydantic resource models for workspace inspection and cleanup operations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkspaceEntry(BaseModel):
    """Metadata for an active workspace or managed repository."""

    name: str = Field(..., description="Workspace or repository folder name")
    path: str = Field(..., description="Absolute filesystem path")
    is_git_repo: bool = Field(
        default=True, description="Whether directory is a valid git repository"
    )
    current_branch: str = Field(default="main", description="Active git branch name")
    is_dirty: bool = Field(
        default=False, description="Whether working tree has uncommitted changes"
    )
    size_bytes: int = Field(default=0, description="Approximate disk usage in bytes")


class WorkspaceListRequest(BaseModel):
    """Request parameters for discovering active workspaces and repositories."""

    base_dir: str = Field(
        default=".", description="Base directory to search for workspaces and git repositories"
    )
    max_depth: int = Field(default=2, description="Maximum directory search depth")


class WorkspaceListResult(BaseModel):
    """Discovered workspaces and repository inventory."""

    total_workspaces: int = Field(default=0, description="Total count of discovered workspaces")
    workspaces: list[WorkspaceEntry] = Field(
        default_factory=list, description="Discovered workspace records"
    )


class WorkspaceCleanRequest(BaseModel):
    """Request parameters for cleaning stale workspace data artifacts."""

    older_than_days: int = Field(
        default=7, description="Purge reviews and analysis artifacts older than N days"
    )
    dry_run: bool = Field(default=False, description="Simulate cleanup without deleting files")


class WorkspaceCleanResult(BaseModel):
    """Execution report from workspace artifact cleanup."""

    files_removed: int = Field(default=0, description="Total count of deleted artifacts")
    bytes_reclaimed: int = Field(default=0, description="Total disk space reclaimed in bytes")
    bytes_reclaimed_human: str = Field(default="0B", description="Human-readable reclaimed space")
    purged_directories: list[str] = Field(
        default_factory=list, description="Paths of cleaned session directories"
    )
