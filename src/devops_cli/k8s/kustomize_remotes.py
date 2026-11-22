"""The remote targets of a kustomization: what `kubectl kustomize` fetches to build it (#6681).

Kustomize clones a git repository or downloads a file when a kustomization names one, and it has
no option that refuses a remote load. So a dry run that builds a folder as a local read must know
first whether the build fetches. `remote_targets` reads the kustomization of a folder, and the
kustomization of each local folder that it takes through a field that loads a kustomization root,
and gives each entry that Kustomize loads from outside the local folders.

No open Python library holds the loader rule of Kustomize. The rule here follows two functions of
`sigs.k8s.io/kustomize/api`: `loader.IsRemoteFile` (an http or https URL is a remote file) and
`git.NewRepoSpecFromURL` (the forms of a git repository). The fields are the field names of the
Kustomization schema.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from devops_cli.config.constants import CONST_K8S_KUSTOMIZATION_NAMES
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.lang import ERRORS

# The fields whose entries Kustomize loads as a file, a local kustomization root or a remote
# target: a file URL or a git repository (`accumulateResources` and `accumulateComponents`).
_TARGET_FIELDS: Final[tuple[str, ...]] = (
    "resources",
    "bases",
    "components",
    "generators",
    "transformers",
    "validators",
)
# The fields whose entries Kustomize reads only as a file, and the file keys of the items of the
# other fields. Kustomize downloads such a file when it is an http or https URL.
_FILE_FIELDS: Final[tuple[str, ...]] = ("crds", "configurations", "patchesStrategicMerge")
_FILE_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "patches": ("path",),
    "patchesJson6902": ("path",),
    "replacements": ("path",),
    "openapi": ("path",),
    "configMapGenerator": ("files", "envs", "env"),
    "secretGenerator": ("files", "envs", "env"),
}
_HTTP_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})
# The URL schemes of a git repository (`extractScheme`), the user of the SCP form
# `<user>@<host>:<path>` (`extractUsername`), and the host that needs no scheme and no user.
_REPO_SCHEMES: Final[frozenset[str]] = frozenset({"ssh", "https", "http", "file"})
_REPO_USER: Final[re.Pattern[str]] = re.compile(r"[a-zA-Z][a-zA-Z0-9-]*@")
_GITHUB_HOSTS: Final[tuple[str, ...]] = ("github.com/", "github.com:")
_FORCED_GIT: Final[str] = "git::"


def remote_targets(folder: Path) -> list[str]:
    """Each entry that Kustomize loads from outside the local folders to build `folder`, in the
    order of the read, each once: of its kustomization, and of each local folder that a target
    field of a kustomization reaches. A folder with no kustomization gives no entry.

    Raises:
        KubernetesContextError: a kustomization is not a YAML mapping.
    """
    found: dict[str, None] = {}
    _read(folder.resolve(), set(), found)
    return list(found)


def _read(folder: Path, seen: set[Path], found: dict[str, None]) -> None:
    """Add the remote entries of the kustomization of `folder` and of its local roots to `found`."""
    if folder in seen:
        return
    seen.add(folder)
    kustomization = _kustomization(folder)
    for entry in _strings(kustomization, _TARGET_FIELDS):
        if _is_remote_file(entry) or _is_repository(entry):
            found.setdefault(entry)
        elif (folder / entry).is_dir():
            _read((folder / entry).resolve(), seen, found)
    for entry in _file_entries(kustomization):
        if _is_remote_file(entry):
            found.setdefault(entry)


def _kustomization(folder: Path) -> Mapping[str, Any]:
    """The kustomization of `folder`, or an empty mapping when the folder holds none."""
    import yaml

    for name in CONST_K8S_KUSTOMIZATION_NAMES:
        path = folder / name
        if path.is_file():
            try:
                doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                raise KubernetesContextError(
                    ERRORS.k8s.kustomization_not_mapping.format(path=path, reason=exc)
                ) from exc
            if doc is None:
                return {}
            if not isinstance(doc, Mapping):
                raise KubernetesContextError(
                    ERRORS.k8s.kustomization_not_mapping.format(
                        path=path, reason=f"it is a {type(doc).__name__}"
                    )
                )
            return doc
    return {}


def _entries(value: Any, kind: type) -> list[Any]:
    """The items of type `kind` of the field value `value`: one value, or the items of a list."""
    items = value if isinstance(value, list) else [value]
    return [item for item in items if isinstance(item, kind)]


def _strings(kustomization: Mapping[str, Any], fields: tuple[str, ...]) -> Iterator[str]:
    """Each string entry of the fields `fields` of `kustomization`."""
    for field in fields:
        yield from _entries(kustomization.get(field), str)


def _file_entries(kustomization: Mapping[str, Any]) -> Iterator[str]:
    """Each file that `kustomization` names outside its target fields. A generator file
    `<key>=<path>` gives its path."""
    yield from _strings(kustomization, _FILE_FIELDS)
    for field, keys in _FILE_KEYS.items():
        for item in _entries(kustomization.get(field), Mapping):
            for key in keys:
                yield from (entry.rsplit("=", 1)[-1] for entry in _entries(item.get(key), str))


def _is_remote_file(entry: str) -> bool:
    """Whether Kustomize downloads `entry` as a file: an http or https URL (`IsRemoteFile`)."""
    return urlsplit(entry).scheme in _HTTP_SCHEMES


def _is_repository(entry: str) -> bool:
    """Whether Kustomize takes `entry` as a git repository (`NewRepoSpecFromURL`): after an
    optional `git::`, an ssh, https, http or file URL, the SCP form with a user, or a path on
    github.com. An absolute path is local."""
    if entry.startswith("/"):
        return False
    spec = entry.split("?", 1)[0]
    if spec[: len(_FORCED_GIT)].lower() == _FORCED_GIT:
        spec = spec[len(_FORCED_GIT) :]
    if urlsplit(spec).scheme in _REPO_SCHEMES:
        return True
    return _REPO_USER.match(spec) is not None or spec.lower().startswith(_GITHUB_HOSTS)


__all__ = ["remote_targets"]
