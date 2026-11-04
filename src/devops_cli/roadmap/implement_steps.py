"""The project steps of the implement job (#3484): `docs` and `archive`.

The job regenerates the documents and archives the change of an item with the commands of
devops-cli. A target repository that is not devops-cli has no such documents and no such change
tooling, and the same commands fail there. So the job runs a step only when the target declares it:

```toml
[implement.steps]
docs = true
archive = true
```

The declaration is `CONST_ROADMAP_IMPLEMENT_STEPS_FILE`. The default branch decides, as for the
hooks (`implement_hooks.trusted_config`): an agent can edit the file of the checkout, and an edit
must not add or remove a step. A default branch with no file declares no step.
"""

from __future__ import annotations

import tomllib
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_STEPS_FILE
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git

_OPERATION = "roadmap.implement.steps"


class ProjectStep(StrEnum):
    """A step that the job runs only where the target declares it. The value is the key of the
    declaration and the name of the step in the comment."""

    DOCS = "docs"
    ARCHIVE = "archive"


class _Steps(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    docs: bool = False
    archive: bool = False


class _Implement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    steps: _Steps = _Steps()


class _Declaration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    implement: _Implement = _Implement()


def declared_steps(source: Path, ref: str) -> frozenset[ProjectStep]:
    """The steps that commit `ref` declares in `CONST_ROADMAP_IMPLEMENT_STEPS_FILE`. Empty when
    `ref` holds no file. The commit decides, not the files of the checkout. Raises
    `GitOperationError` when git cannot read `ref`, and `ConfigurationError` when the file is not
    valid."""
    name = CONST_ROADMAP_IMPLEMENT_STEPS_FILE
    listed = git(source, "ls-tree", "--name-only", ref, "--", name, operation=_OPERATION)
    if not listed:
        return frozenset()
    text = git(source, "show", f"{ref}:{name}", operation=_OPERATION)
    try:
        declaration = _Declaration.model_validate(tomllib.loads(text))
    except (tomllib.TOMLDecodeError, ValidationError) as exc:
        raise ConfigurationError(
            MESSAGES.roadmap.implement_steps_invalid.format(file=name, reason=exc),
            key=name,
        ) from exc
    steps = declaration.implement.steps
    return frozenset(step for step in ProjectStep if getattr(steps, step.value))


__all__ = ["ProjectStep", "declared_steps"]
