"""Agent Skill model and name normalization used by the harness skill slot."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli.exceptions.ai import HarnessValidationError


class ParsedSkill(BaseModel):
    """An Agent Skill held by the harness skill slot."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    body: str = ""
    directory: Path
    loaded: bool = False


def normalize_skill_name(name: str) -> str:
    """Normalize and validate an Agent Skill name using Unicode NFKC."""
    norm = unicodedata.normalize("NFKC", str(name)).strip().lower()
    if not re.fullmatch(r"^[a-z0-9]+(-[a-z0-9]+)*$", norm) or len(norm) > 64:
        raise HarnessValidationError(
            f"Invalid skill name '{name}': normalized name must be 1-64 lowercase alphanumeric characters separated by hyphens"
        )
    return norm
