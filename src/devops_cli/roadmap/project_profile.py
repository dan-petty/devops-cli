"""The project profile of the implement job (#4635).

A repository declares its toolchain preset in `.devops/roadmap.toml` on the default branch:

```toml
[project]
toolchain = "devops-cli"
```

The default branch decides, as for the hooks: an agent can edit the file of the checkout, and an
edit must not change the checks. A default branch with no file declares the `neutral` preset.
"""

from __future__ import annotations

import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_STEPS_FILE,
    CONST_ROADMAP_REVIEW_TAG_PATTERN,
)
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.toolchains import (
    NEUTRAL_PRESET,
    PRESETS,
    ToolchainPreset,
)

_OPERATION = "roadmap.project.profile"


class ProjectStep(StrEnum):
    """A step that the job runs only where the target declares it."""

    DOCS = "docs"
    ARCHIVE = "archive"


class _Project(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    toolchain: str = "neutral"


class _Review(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tag_pattern: str = CONST_ROADMAP_REVIEW_TAG_PATTERN

    @field_validator("tag_pattern")
    @classmethod
    def _valid_tag_pattern(cls, value: str) -> str:
        if not value or value.startswith("-") or any(ch.isspace() for ch in value):
            raise ValueError("tag_pattern must be non-empty, without '-' prefix or whitespace")
        return value


class _Declaration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project: _Project = _Project()
    review: _Review = _Review()


class ProjectProfile(BaseModel):
    """The resolved profile of a target repository."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    preset: ToolchainPreset

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ProjectProfile):
            return self.preset == other.preset
        if isinstance(other, ToolchainPreset):
            return self.preset == other
        return NotImplemented

    def __getattr__(self, name: str) -> Any:
        return getattr(self.preset, name)


def resolve_profile(source: Path, ref: str) -> ProjectProfile:
    """The profile that commit `ref` declares in `CONST_ROADMAP_IMPLEMENT_STEPS_FILE`. Defaults to
    the neutral preset when `ref` holds no file. The commit decides, not the files of the checkout.
    Raises `GitOperationError` when git cannot read `ref`, and `ConfigurationError` when the file is
    not valid or the toolchain is unknown."""
    name = CONST_ROADMAP_IMPLEMENT_STEPS_FILE
    listed = git(source, "ls-tree", "--name-only", ref, "--", name, operation=_OPERATION)
    if not listed:
        return ProjectProfile(preset=NEUTRAL_PRESET)
    text = git(source, "show", f"{ref}:{name}", operation=_OPERATION)
    try:
        raw = tomllib.loads(text)
        declaration = _Declaration.model_validate(raw)
    except (tomllib.TOMLDecodeError, ValidationError) as exc:
        raise ConfigurationError(
            MESSAGES.roadmap.roadmap_toml_invalid.format(file=name, reason=exc),
            key=name,
        ) from exc
    toolchain_name = declaration.project.toolchain
    preset = PRESETS.get(toolchain_name)
    if preset is None:
        raise ConfigurationError(
            MESSAGES.roadmap.roadmap_toml_invalid.format(
                file=name,
                reason=f"unknown toolchain '{toolchain_name}'",
            ),
            key=name,
        )
    return ProjectProfile(preset=preset)


def review_tag_pattern(checkout: Path) -> str:
    """Return `[review] tag_pattern` from `.devops/roadmap.toml` in `checkout`, or default `v*`.

    Raises `ConfigurationError` naming the file when the TOML or table schema is invalid.
    """
    name = CONST_ROADMAP_IMPLEMENT_STEPS_FILE
    path = checkout / name
    if not path.is_file():
        return CONST_ROADMAP_REVIEW_TAG_PATTERN
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        declaration = _Declaration.model_validate(raw)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as exc:
        raise ConfigurationError(
            MESSAGES.roadmap.roadmap_toml_invalid.format(file=name, reason=exc),
            key=name,
        ) from exc
    return declaration.review.tag_pattern


__all__ = [
    "ProjectProfile",
    "ProjectStep",
    "resolve_profile",
    "review_tag_pattern",
]
