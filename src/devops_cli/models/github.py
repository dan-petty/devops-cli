"""Shared domain models for GitHub API responses."""

from __future__ import annotations

from pydantic import BaseModel


class SSHKeyInfo(BaseModel):
    """A GitHub user SSH key."""

    id: int
    title: str
    key: str
