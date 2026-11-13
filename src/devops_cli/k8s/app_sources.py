"""The git sources of the Argo CD Applications of an environment tree, as local folders (#5131).

A source of the repository that holds the tree, its `origin`, reads the local checkout. A source of
another repository is fetched once for each repository and revision, at the `targetRevision` of
the source, into a work folder: `git init`, a shallow `git fetch` and a checkout of `FETCH_HEAD`,
as `render_at_revision` fetches the revision of an Application. Only an `https` repository is
fetched. The fetch adds no credential of its own, so a public repository resolves, and a private
one resolves only where the git configuration of the host gives a credential (#5294). A dry run
fetches nothing: it records each fetch command.

A value file `$<ref>/<path>` of a chart source names a file of the source whose `ref` is `<ref>`,
which can be the origin or another repository. Argo CD reads it the same way.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from devops_cli.config.constants import (
    CONST_CANONICAL_OCI_SOURCE,
    CONST_GIT_NONINTERACTIVE_ENV,
    CONST_GIT_NONINTERACTIVE_SSH_CONFIG,
    CONST_K8S_ARGOCD_FETCH_TIMEOUT_SECONDS,
)
from devops_cli.core.process import PlannedProcessResult, run_subprocess
from devops_cli.dry_run import is_dry_run
from devops_cli.exceptions.k8s import ApplicationSourceError

_REF_VALUE_FILE: Final[re.Pattern[str]] = re.compile(r"^\$(?P<ref>[^/]+)/(?P<path>.+)$")
_FETCHED_SCHEME: Final[str] = "https"
_SSH_PREFIX: Final[str] = "git@github.com:"
_GITHUB: Final[str] = "https://github.com/"
_GIT_SUFFIX: Final[str] = ".git"


def normalize_git_url(url: str) -> str:
    """`url` in one form for a comparison: no `.git`, no end slash, and a GitHub SSH URL as its
    https URL."""
    norm = url.strip().rstrip("/")
    if norm.endswith(_GIT_SUFFIX):
        norm = norm[: -len(_GIT_SUFFIX)]
    if norm.startswith(_SSH_PREFIX):
        return _GITHUB + norm[len(_SSH_PREFIX) :]
    parsed = urlsplit(norm)
    if parsed.scheme == "ssh" and parsed.netloc == "git@github.com":
        return _GITHUB + parsed.path.lstrip("/")
    return norm


def repository_origin(repo: Path) -> str:
    """The `origin` of the checkout at `repo`, normalized, or the source of devops-cli when the
    folder has none, such as a copy of a tree outside a repository."""
    proc = run_subprocess(
        ["git", "-C", str(repo), "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=False,
        local_read=True,
    )
    if proc.returncode == 0 and proc.stdout and proc.stdout.strip():
        return normalize_git_url(proc.stdout.strip())
    return normalize_git_url(CONST_CANONICAL_OCI_SOURCE)


@dataclass(frozen=True)
class SourceTree:
    """The local folder of one repository at one revision. `planned` holds the fetch commands of a
    dry run, which leaves the folder empty."""

    root: Path
    planned: tuple[tuple[str, ...], ...] = ()


@dataclass
class SourceTrees:
    """The local folder of each git repository that the Applications of a tree name.

    `local` is the checkout that holds the tree, and `origin` its normalized URL. A fetched
    repository goes in a new folder under `workdir`. The trees are safe to read from several
    threads: a repository and revision are fetched once.
    """

    local: Path
    origin: str
    workdir: Path
    _fetched: dict[tuple[str, str], SourceTree] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def tree(self, repo_url: str, revision: str | None) -> SourceTree:
        """The folder of `repo_url` at `revision`: the local checkout for the origin, else a
        fetch of the revision (`HEAD` when the source names none).

        Raises:
            ApplicationSourceError: the repository is not an https URL, or the fetch fails.
        """
        url = normalize_git_url(repo_url)
        if url == self.origin:
            return SourceTree(self.local)
        if urlsplit(url).scheme != _FETCHED_SCHEME:
            raise ApplicationSourceError(
                f"The git source {repo_url} is not the origin {self.origin} and not an https "
                "repository, so it is not fetched."
            )
        key = (url, revision or "HEAD")
        with self._lock:
            if key not in self._fetched:
                checkout = self.workdir / f"source-{len(self._fetched)}"
                self._fetched[key] = _fetch(url, key[1], checkout)
            return self._fetched[key]

    @property
    def planned(self) -> tuple[tuple[str, ...], ...]:
        """The fetch commands of a dry run, in the order of the fetches."""
        with self._lock:
            return tuple(command for tree in self._fetched.values() for command in tree.planned)

    def value_file(self, value_file: str, refs: Mapping[str, Mapping[str, Any]]) -> Path:
        """The file that a value file of a chart source names: `$<ref>/<path>` in the folder of
        the source whose `ref` is `<ref>`, else a path of the local checkout.

        Raises:
            ApplicationSourceError: no source of the Application has the ref, or its tree fails.
        """
        match = _REF_VALUE_FILE.match(value_file)
        if match is None:
            return self.local / value_file
        source = refs.get(match["ref"])
        if source is None:
            raise ApplicationSourceError(
                f"The value file {value_file} names the ref {match['ref']}, and no source of the "
                "Application has it."
            )
        tree = self.tree(str(source.get("repoURL") or ""), source_revision(source))
        return tree.root / match["path"]


def application_sources(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The sources of an Application: `spec.sources`, else the one `spec.source`."""
    spec = doc.get("spec") or {}
    sources = spec.get("sources") or [spec.get("source") or {}]
    return [source for source in sources if isinstance(source, dict)]


def ref_sources(sources: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """Each source of an Application that has a `ref`, by its ref."""
    return {str(source["ref"]): source for source in sources if source.get("ref")}


def source_revision(source: Mapping[str, Any]) -> str | None:
    """The `targetRevision` of a source, or None."""
    revision = source.get("targetRevision")
    return str(revision) if revision else None


def _fetch_commands(url: str, revision: str, checkout: Path) -> list[list[str]]:
    """The commands that fetch `url` at `revision` into `checkout`. The URL and the revision come
    from the files of the tree, so git reads them after `--end-of-options`."""
    git = ["git", "-C", str(checkout)]
    return [
        ["git", "init", "--quiet", str(checkout)],
        [
            *git,
            "-c",
            CONST_GIT_NONINTERACTIVE_SSH_CONFIG,
            "fetch",
            "--quiet",
            "--depth",
            "1",
            "--end-of-options",
            url,
            revision,
        ],
        [*git, "checkout", "--quiet", "FETCH_HEAD"],
    ]


def _fetch(url: str, revision: str, checkout: Path) -> SourceTree:
    commands = _fetch_commands(url, revision, checkout)
    if is_dry_run():
        return SourceTree(checkout, tuple(tuple(command) for command in commands))
    for command in commands:
        proc = run_subprocess(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=CONST_K8S_ARGOCD_FETCH_TIMEOUT_SECONDS,
            env=dict(CONST_GIT_NONINTERACTIVE_ENV),
        )
        if isinstance(proc, PlannedProcessResult):
            return SourceTree(checkout, tuple(tuple(c) for c in commands))
        if proc.returncode != 0:
            reason = (proc.stderr or proc.stdout or "").strip()
            raise ApplicationSourceError(f"The fetch of {url} at {revision} failed: {reason}")
    return SourceTree(checkout)


__all__ = [
    "SourceTree",
    "SourceTrees",
    "application_sources",
    "normalize_git_url",
    "ref_sources",
    "repository_origin",
    "source_revision",
]
