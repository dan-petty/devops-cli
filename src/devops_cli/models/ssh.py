"""Shared domain models for SSH key management."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ManagedSSHKey(BaseModel):
    """A managed SSH key with pre-computed date and age metadata."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    path: Path
    key_date: date | None = None
    age_days: int | None = None
