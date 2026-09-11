"""Pydantic models for structured command dry-run responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

_MAX_DRY_RUN_DETAILS_KEYS: int = 100


class CommandDryRunResult(BaseModel):
    """Structured Pydantic model representation of a dry-run command execution."""

    command: str
    target: str | None = None
    dry_run: bool = True
    status: str = "DRY_RUN"
    action: str = ""
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("details", mode="before")
    @classmethod
    def _bound_details(cls, v: Any) -> dict[str, Any]:
        """Ensure details dictionary is bounded to prevent unbounded memory allocation."""
        if not isinstance(v, dict):
            return {}
        if len(v) > _MAX_DRY_RUN_DETAILS_KEYS:
            return dict(list(v.items())[:_MAX_DRY_RUN_DETAILS_KEYS])
        return v
