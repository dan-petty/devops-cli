"""Pydantic resource models for release cycle management and versioning."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReleaseStatusRequest(BaseModel):
    """Request parameters for checking release readiness and version consistency."""

    check_remote: bool = Field(default=False, description="Verify remote git tags on GitHub origin")


class ReleaseStatusResult(BaseModel):
    """Status summary of current project release state."""

    current_version: str = Field(..., description="Active version string from pyproject.toml")
    latest_git_tag: str = Field(default="", description="Most recent git release tag")
    is_clean: bool = Field(default=True, description="Whether git working tree is clean")
    branch_name: str = Field(default="main", description="Active git branch name")
    unreleased_commits_count: int = Field(
        default=0, description="Count of commits since latest release tag"
    )
    docs_synchronized: bool = Field(
        default=True, description="Whether CLI documentation is up-to-date"
    )
    ready_for_release: bool = Field(
        default=True, description="Overall evaluation of release readiness"
    )


class ReleasePrepareRequest(BaseModel):
    """Request parameters for preparing a new release bump."""

    bump_type: str = Field(
        default="patch", description="Semver increment type (patch, minor, major)"
    )
    dry_run: bool = Field(
        default=False, description="Simulate version bump without modifying files"
    )


class ReleasePrepareResult(BaseModel):
    """Execution report from release preparation."""

    previous_version: str = Field(..., description="Original version string")
    new_version: str = Field(..., description="Calculated next semver version")
    updated_files: list[str] = Field(
        default_factory=list, description="Files updated with the new version"
    )
    release_branch: str = Field(default="", description="Created release branch name")
