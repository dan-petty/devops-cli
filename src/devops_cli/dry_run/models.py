"""Pydantic models for structured command dry-run responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

_MAX_DRY_RUN_DETAILS_KEYS: int = 100
_MAX_DRY_RUN_STRING_LENGTH: int = 1024
_MAX_DRY_RUN_COLLECTION_ITEMS: int = 50
_MAX_DRY_RUN_NESTING_DEPTH: int = 3


def _bound_detail_value(val: Any, depth: int = 0) -> Any:
    """Bound nested detail values by size, collection length, and depth."""
    if depth >= _MAX_DRY_RUN_NESTING_DEPTH:
        return "<truncated: depth exceeded>"
    if isinstance(val, str):
        if len(val) > _MAX_DRY_RUN_STRING_LENGTH:
            return f"{val[: _MAX_DRY_RUN_STRING_LENGTH - 3]}..."
        return val
    if isinstance(val, dict):
        capped_items = list(val.items())[:_MAX_DRY_RUN_COLLECTION_ITEMS]
        return {k: _bound_detail_value(v, depth + 1) for k, v in capped_items}
    if isinstance(val, (list, tuple, set)):
        capped_list = list(val)[:_MAX_DRY_RUN_COLLECTION_ITEMS]
        return [_bound_detail_value(item, depth + 1) for item in capped_list]
    return val


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
        items = list(v.items())[:_MAX_DRY_RUN_DETAILS_KEYS]
        return {k: _bound_detail_value(val, depth=1) for k, val in items}
