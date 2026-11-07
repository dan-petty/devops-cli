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


class AdvisoryFinding(BaseModel):
    """One advisory that affects the pinned version of one component (#3898, #3987).

    A finding is an advisory that affects the pin: OSV matched the version to the affected ranges
    (`source` is `OSV`), or the version of a GitHub Action, image, chart or release matched a range
    of a GitHub advisory (`source` is `GitHub`). `locations` lists each `file:line` that pins the
    component at this version; `component` is the first of them. `affected_range` and
    `fixed_version` are those of the record, as `>=0 <5.4` and `5.4`; a package with more than one
    fix lists them all. `exploited` is true when a CVE of the advisory is in the CISA KEV list.
    """

    model_config = ConfigDict(frozen=True)

    component: Component
    locations: list[str]
    advisory_id: str
    aliases: list[str]
    severity: str
    summary: str
    affected_range: str
    fixed_version: str
    source: str
    exploited: bool = False


class LookupFailure(BaseModel):
    """A lookup that got no answer. Its component has no verdict: it is not clean.

    `advisory_id` is empty when the query for the component failed, and names the advisory when
    its record could not be read.
    """

    model_config = ConfigDict(frozen=True)

    ecosystem: Ecosystem
    name: str
    version: str
    advisory_id: str
    reason: str


class AdvisorySummary(BaseModel):
    """What a run checked and what it left out.

    `queried` counts the distinct component versions that OSV or GitHub was asked about.
    `unpinned` counts the components of a checked kind that pin no exact release: a range, a
    branch, a commit or a tag such as `v7`. `exploited` counts the findings that the CISA KEV list
    flags. `not_covered` counts the components of each ecosystem that no source matches (an image,
    chart or release binary that the watch list does not map), and the `tool-lock-entry`
    components, whose packages the Python and Node lists hold under their own name.
    """

    model_config = ConfigDict(frozen=True)

    components: int
    queried: int
    with_findings: int
    findings: int
    unpinned: int
    failed: int
    exploited: int
    not_covered: dict[str, int]


class AdvisoryReport(BaseModel):
    """The advisories of the pins of a repository, most severe first.

    `kev_failure` holds the reason that the CISA KEV list could not be read; it is empty
    otherwise. When it is set, no finding has a verdict for `exploited`.
    """

    model_config = ConfigDict(frozen=True)

    findings: list[AdvisoryFinding]
    failures: list[LookupFailure]
    kev_failure: str = ""
    summary: AdvisorySummary
