"""Pydantic models for structured command dry-run responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CommandDryRunResult(BaseModel):
    """Structured Pydantic model representation of a dry-run command execution."""

    command: str
    target: str | None = None
    dry_run: bool = True
    status: str = "DRY_RUN"
    action: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
