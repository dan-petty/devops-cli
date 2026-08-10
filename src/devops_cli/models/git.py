"""Shared domain models for git operations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BranchListing(BaseModel):
    """Result of listing git branches in a repository."""

    model_config = ConfigDict(frozen=True)

    branches: list[str]
    current: str
