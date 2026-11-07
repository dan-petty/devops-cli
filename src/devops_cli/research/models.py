"""The typed list of components that a repository pins (#3896)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ComponentKind(StrEnum):
    """The class of file or entry that holds a pin."""

    PYTHON_PACKAGE = "python-package"
    NODE_PACKAGE = "node-package"
    TOOL = "tool"
    CONTAINER_IMAGE = "container-image"
    DEVCONTAINER_FEATURE = "devcontainer-feature"
    ACTION = "action"
    CHART = "chart"
    TERRAFORM_PROVIDER = "terraform-provider"


class Ecosystem(StrEnum):
    """The registry or release channel that publishes a pinned component.

    `unknown` is a component whose publisher the reader cannot name from the pin alone. It stays
    in the list and in the count, so a later step can map it.
    """

    PYPI = "pypi"
    NPM = "npm"
    DOCKER = "docker"
    GITHUB_ACTIONS = "github-actions"
    GITHUB_RELEASE = "github-release"
    HELM = "helm"
    TERRAFORM = "terraform"
    DEVCONTAINER_FEATURE = "devcontainer-feature"
    UNKNOWN = "unknown"


class Component(BaseModel):
    """One pin: a named component at a version, in one place of one file.

    `file` is the path from the repository root, with `/` separators. `line` counts from 1, and is
    0 when the file's parser gives no line and the text of the file does not show it.
    """

    model_config = ConfigDict(frozen=True)

    kind: ComponentKind
    ecosystem: Ecosystem
    name: str
    version: str
    file: str
    line: int


class InventorySummary(BaseModel):
    """How many components the inventory holds, in total and for each kind and ecosystem."""

    model_config = ConfigDict(frozen=True)

    total: int
    unknown: int
    by_kind: dict[str, int]
    by_ecosystem: dict[str, int]


class Inventory(BaseModel):
    """Every pin of a repository, ordered by file, then line, then name."""

    model_config = ConfigDict(frozen=True)

    components: list[Component]
    summary: InventorySummary
