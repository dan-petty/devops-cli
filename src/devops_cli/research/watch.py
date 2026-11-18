"""The watch list: which GitHub repository publishes the advisories of a pinned component (#3987).

An image, a chart or a release binary has no advisory database of its own. The repository that
builds it may publish advisories, and `.devops/research-watch.toml` names that repository for the
components that the project pins. One entry maps one component (its ecosystem and name, as
`devops research inventory` lists them) to the repository `owner/name`. Map a component only when
its version is a version of the repository: the version of a chart that has its own numbering is
not.

A repository names the packages of its advisories as it wishes: a Go module for each major version
(`github.com/argoproj/argo-cd/v2` and `/v3`), a PyPI package, or a free text. When `package` is
set, the command reads only the vulnerabilities that name that package, so the range of another
major version is no range of the pin. Without it, every vulnerability of an advisory counts.

The file also declares the pins that live outside the repository, in a `[[pin]]` entry: the
operating system of a node, a driver, or another component that no file of the repository holds.
The inventory lists each one at the file `external` and line 0, so a later step can query it. A
`[[pin]]` entry of any ecosystem is read; the refusal below holds for the `[[watch]]` entries.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from devops_cli.exceptions.research import InventoryError
from devops_cli.research.models import ComponentKind, Ecosystem

WATCH_FILE = ".devops/research-watch.toml"
# The ecosystems that another source covers: OSV for the registries, and GitHub for the Actions.
# The refusal holds for a `[[watch]]` entry only, so a `[[pin]]` entry of any ecosystem is read.
_COVERED_ELSEWHERE = frozenset({Ecosystem.PYPI, Ecosystem.NPM, Ecosystem.GITHUB_ACTIONS})
_REPOSITORY = r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"


class WatchEntry(BaseModel):
    """One component, and the repository that publishes its advisories.

    `osv_ecosystem` and `osv_name` are the identity of the component in OSV, which differs from
    its inventory identity for an image, a chart or a release binary. `purl` overrides the purl
    that the inventory builds from the type, the name and the version of the pin.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ecosystem: Ecosystem
    name: Annotated[str, Field(min_length=1)]
    repo: Annotated[str, Field(pattern=_REPOSITORY)]
    package: Annotated[str, Field(min_length=1)] | None = None
    osv_ecosystem: Annotated[str, Field(min_length=1)] | None = None
    osv_name: Annotated[str, Field(min_length=1)] | None = None
    purl: Annotated[str, Field(min_length=1)] | None = None


class PinEntry(BaseModel):
    """A pin that no file of the repository holds, declared in the watch list file.

    `version` is empty when the environment holds it and the repository does not. `ecosystem` is
    `unknown` unless the entry names the registry or the release channel of the pin.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ComponentKind
    name: Annotated[str, Field(min_length=1)]
    version: str = ""
    ecosystem: Ecosystem = Ecosystem.UNKNOWN
    osv_ecosystem: Annotated[str, Field(min_length=1)] | None = None
    osv_name: Annotated[str, Field(min_length=1)] | None = None
    repo: Annotated[str, Field(pattern=_REPOSITORY)] | None = None
    purl: Annotated[str, Field(min_length=1)] | None = None


class WatchList(BaseModel):
    """The entries of the watch list file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    watch: list[WatchEntry] = Field(default_factory=list)
    pin: list[PinEntry] = Field(default_factory=list)

    def entry_of(self, ecosystem: Ecosystem, name: str) -> WatchEntry | None:
        """The entry for the component, if the list names one."""
        return next((e for e in self.watch if (e.ecosystem, e.name) == (ecosystem, name)), None)


def read_watch_list(root: Path) -> WatchList:
    """The watch list of the repository at `root`; an empty one when the file does not exist."""
    path = root / WATCH_FILE
    if not path.is_file():
        return WatchList()
    try:
        entries = WatchList.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as exc:
        raise InventoryError(
            f"Cannot read the watch list {WATCH_FILE}: {exc}", details={"file": WATCH_FILE}
        ) from exc
    covered = next((e for e in entries.watch if e.ecosystem in _COVERED_ELSEWHERE), None)
    if covered is not None:
        raise InventoryError(
            f"The watch list {WATCH_FILE} maps {covered.name} of the ecosystem "
            f"{covered.ecosystem.value}, which another source covers",
            details={"file": WATCH_FILE},
        )
    return entries
