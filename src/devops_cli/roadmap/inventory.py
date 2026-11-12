"""The tools that a repository uses, as the alternatives check reads them (#4661).

A `covers` or `partly` verdict for a tool that the repository already uses is `in-use`. Three
sources say that a tool is in use, the cheapest first:

- the SPDX SBOM that the GitHub dependency graph exports for the default branch: one request, and a
  package URL for each package of a manifest, a lock file or a workflow;
- the files of the deployed paths of a clone (`roadmap.alternatives.inventory_paths`): a service,
  an image or a CLI that no manifest names, such as LiteLLM or Grafana, which the paths name as a
  whole word, in any case, as `git grep -i -w -F` finds it;
- the packages that deps.dev links to the GitHub project of the tool as their source: a repository
  whose package has another name, such as `modelcontextprotocol/python-sdk` and `mcp`.

A run with no clone reads the SBOM and deps.dev only. The canonical id of a tool is the deps.dev
project key of its GitHub repository, `github.com/<owner>/<name>` in lower case. A PyPI package
that names no GitHub repository as its source has its package URL, `pkg:pypi/<name>`, with the name
in the canonical form of `packaging`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

import httpx2
from packageurl import PackageURL
from packaging.utils import canonicalize_name
from pydantic import BaseModel, Field

from devops_cli.config.defaults import (
    DEFAULT_DEPS_DEV_PROJECT_URL,
    DEFAULT_DEPS_DEV_TIMEOUT_SECONDS,
)
from devops_cli.core.paths import safe_resolve_subpath
from devops_cli.github.repo_ref import is_repository_name
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client

if TYPE_CHECKING:
    from devops_cli.roadmap.stores.store import RoadmapStore

logger = logging.getLogger(__name__)

_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
_PYPI_HOSTS = frozenset({"pypi.org", "www.pypi.org"})
_PYPI_PROJECT = "project"
_GITHUB_PROJECT = "github.com"
# The package URL types of a GitHub repository: an action is a `githubactions` package.
_GITHUB_TYPES = frozenset({"github", "githubactions"})
_PYPI = "pypi"
_NPM = "npm"
# The package URL type of each deps.dev package system whose package name is the name of the
# package URL.
_DEPS_DEV_TYPES = {
    "PYPI": _PYPI,
    "NPM": _NPM,
    "GO": "golang",
    "CARGO": "cargo",
    "NUGET": "nuget",
    "RUBYGEMS": "gem",
}
# The relation of a package version to a project that makes the project its source.
_SOURCE_REPO = "SOURCE_REPO"


class _VersionKey(BaseModel):
    system: str
    name: str


class _PackageVersion(BaseModel):
    version_key: _VersionKey = Field(validation_alias="versionKey")
    relation_type: str = Field(default="", validation_alias="relationType")


class _ProjectPackageVersions(BaseModel):
    """The package versions that deps.dev links to a project."""

    versions: list[_PackageVersion] = Field(default_factory=list)


def project_of(url: str) -> str | None:
    """The deps.dev project key of the GitHub repository at `url`, `github.com/<owner>/<name>` in
    lower case, or None when `url` is no URL of a GitHub repository."""
    parts = urlsplit(url)
    segments = [segment for segment in parts.path.split("/") if segment]
    if (parts.hostname or "").lower() not in _GITHUB_HOSTS or len(segments) < 2:
        return None
    name = f"{segments[0]}/{segments[1].removesuffix('.git')}"
    return f"{_GITHUB_PROJECT}/{name.lower()}" if is_repository_name(name) else None


def _pypi_name(url: str) -> str | None:
    """The canonical name of the PyPI package at `url`, or None when `url` is no PyPI page."""
    parts = urlsplit(url)
    segments = [segment for segment in parts.path.split("/") if segment]
    if (parts.hostname or "").lower() not in _PYPI_HOSTS or len(segments) < 2:
        return None
    return canonicalize_name(segments[1]) if segments[0] == _PYPI_PROJECT else None


def source_project(urls: Iterable[str]) -> str | None:
    """The project of the first of `urls` that is a GitHub repository, or None."""
    return next((project for project in map(project_of, urls) if project), None)


def canonical_id(url: str, project: str | None) -> str:
    """The canonical id of the tool at `url` whose GitHub project is `project`: the project key,
    else the package URL of a PyPI package, else `url`."""
    if found := project or project_of(url):
        return found
    name = _pypi_name(url)
    return PackageURL(type=_PYPI, name=name).to_string() if name else url


def _key(kind: str, namespace: str | None, name: str) -> str:
    """The key of a package of the package URL type `kind`: the first two segments of an action,
    which name its repository, and the canonical name of a PyPI package."""
    if kind in _GITHUB_TYPES:
        segments = [*namespace.split("/"), name] if namespace else [name]
        return f"github:{'/'.join(segments[:2]).lower()}"
    if kind == _PYPI:
        return f"{_PYPI}:{canonicalize_name(name)}"
    return f"{kind}:{namespace}/{name}".lower() if namespace else f"{kind}:{name}".lower()


def package_keys(purls: Iterable[str]) -> frozenset[str]:
    """The keys of the packages of `purls`. A string that is no package URL is left out."""
    keys: set[str] = set()
    for purl in purls:
        try:
            package = PackageURL.from_string(purl)
        except ValueError:
            logger.warning("The SBOM holds a package URL that does not parse: %s.", purl[:120])
            continue
        keys.add(_key(package.type, package.namespace, package.name))
    return frozenset(keys)


def _tool_keys(url: str, project: str | None) -> set[str]:
    """The keys of the packages that are the tool: its repository, the scoped npm package of the
    same name and its PyPI package."""
    keys: set[str] = set()
    if project:
        owner_name = project.removeprefix(f"{_GITHUB_PROJECT}/")
        keys |= {f"github:{owner_name}", f"{_NPM}:@{owner_name}"}
    if name := _pypi_name(url):
        keys.add(f"{_PYPI}:{name}")
    return keys


def _tool_names(url: str) -> list[str]:
    """The names that a deployed file writes for the tool: the name of its repository or of its
    package."""
    project = project_of(url)
    name = project.rsplit("/", 1)[-1] if project else _pypi_name(url)
    return [name] if name else []


def _whole_word(name: str) -> re.Pattern[str]:
    """`name` as `git grep -i -w -F` finds it: a fixed string, in any case, with no letter, digit
    or `_` next to it."""
    return re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)


def _read_files(root: Path, paths: Sequence[str]) -> str:
    """The text of each file under the deployed `paths` of the clone at `root`. A path that the
    clone does not hold is left out, and a symbolic link is not followed."""
    texts: list[str] = []
    for path in paths:
        target = safe_resolve_subpath(root, path)
        files = [target] if target.is_file() else sorted(target.rglob("*"))
        texts += [
            file.read_text(encoding="utf-8", errors="ignore")
            for file in files
            if file.is_file() and not file.is_symlink()
        ]
    return "\n".join(texts)


def _linked_packages(project: str) -> frozenset[str]:
    """The keys of the packages that deps.dev links to `project` as their source, none when
    deps.dev does not know the project. Raises `httpx2.HTTPError` on another failed read and
    `pydantic.ValidationError` on a malformed answer."""
    url = DEFAULT_DEPS_DEV_PROJECT_URL.format(project=quote(project, safe=""))
    with http_client(EgressLevel.PUBLIC) as client:
        response = client.get(url, timeout=DEFAULT_DEPS_DEV_TIMEOUT_SECONDS)
    if response.status_code == httpx2.codes.NOT_FOUND:
        return frozenset()
    response.raise_for_status()
    answer = _ProjectPackageVersions.model_validate_json(response.content)
    return frozenset(
        _key(kind, None, version.version_key.name)
        for version in answer.versions
        if version.relation_type == _SOURCE_REPO
        and (kind := _DEPS_DEV_TYPES.get(version.version_key.system))
    )


@dataclass
class Inventory:
    """The tools in use of one repository at HEAD: the keys of the packages of its SBOM, and the
    text of the deployed files of a clone. One run reads it once, and keeps what deps.dev said
    of each project it asked about."""

    packages: frozenset[str] = frozenset()
    deployed: str = ""
    _linked: dict[str, frozenset[str]] = field(default_factory=dict, init=False, repr=False)

    def uses(self, url: str, project: str | None) -> bool:
        """Whether the repository uses the tool at `url`, whose GitHub project is `project`:
        the SBOM holds its package, the deployed files name it, or the SBOM holds a package that
        deps.dev links to its project. deps.dev is asked only when the SBOM holds a package.
        Raises as deps.dev raises."""
        project = project or project_of(url)
        if _tool_keys(url, project) & self.packages:
            return True
        if any(_whole_word(name).search(self.deployed) for name in _tool_names(url)):
            return True
        if project is None or not self.packages:
            return False
        if project not in self._linked:
            self._linked[project] = _linked_packages(project)
        return bool(self._linked[project] & self.packages)


def read_inventory(store: RoadmapStore, source: Path | None, paths: Sequence[str]) -> Inventory:
    """The inventory of the repository of `store`: one read of its SBOM, and the deployed `paths`
    of the clone at `source` when the run has one."""
    deployed = _read_files(source, paths) if source is not None else ""
    return Inventory(package_keys(store.dependency_purls()), deployed)


__all__ = [
    "Inventory",
    "canonical_id",
    "package_keys",
    "project_of",
    "read_inventory",
    "source_project",
]
