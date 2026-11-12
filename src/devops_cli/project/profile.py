"""The project profile of a repository: its type and the facts of its files (#4627, #5121).

The values merge from low to high precedence:

1. The built-in defaults: the field defaults of `ProjectProfile`, with no fact of any project.
2. The type template `src/devops_cli/templates/profiles/<type>.toml`, versioned with devops-cli.
   The `extends` of the project file chooses the type, else detection does.
3. The facts that detection reads in the files of the repository.
4. The project file `.devops/project.toml` of the repository.

The config of devops-cli holds operational keys only, such as the agent access level of an infra
repo, so it sets no value of the profile. A table merges by key, and a scalar or a list replaces
the lower value. Each value records its source, so onboarding can show why it holds.

Detection knows one type, `ansible-k8s`: an `ansible.cfg` at the root. It reads the inventory and
`roles_path` of `ansible.cfg` (relative to the file, as Ansible reads them), the first `playbooks`
folder at the root or one level down, and a `k8s` folder. It keeps only paths in the repository.
"""

from __future__ import annotations

import configparser
import copy
import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import ERRORS

PROJECT_FILE: Final[str] = ".devops/project.toml"
_ANSIBLE_CONFIG: Final[str] = "ansible.cfg"
_PLAYBOOKS: Final[str] = "playbooks"
_K8S_DIR: Final[str] = "k8s"
_TEMPLATES: Final[tuple[str, ...]] = ("templates", "profiles")


class ProjectType(StrEnum):
    """A type of repository, each with its template in `templates/profiles/`."""

    ANSIBLE_K8S = "ansible-k8s"


class AnsibleProfile(BaseModel):
    """The Ansible layout of a repository, relative to its root."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    inventory: list[str] = Field(default_factory=list, description="The inventory sources")
    playbook_dir: str | None = Field(default=None, description="The folder of the playbooks")
    roles_path: list[str] = Field(default_factory=list, description="The folders of the roles")
    offline_group: str | None = Field(
        default=None, description="The inventory group of the hosts that are out of service"
    )


class KubernetesProfile(BaseModel):
    """The Kubernetes tree of a repository, relative to its root."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dir: str | None = Field(default=None, description="The folder of the Kubernetes manifests")


class ProjectProfile(BaseModel):
    """The facts of a repository that devops-cli reads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    extends: ProjectType | None = Field(default=None, description="The type of the repository")
    ansible: AnsibleProfile = Field(default_factory=AnsibleProfile)
    kubernetes: KubernetesProfile = Field(default_factory=KubernetesProfile)


@dataclass(frozen=True)
class ResolvedProfile:
    """A profile, the source of each value that is not a built-in default, and whether the
    repository holds a project file."""

    profile: ProjectProfile
    sources: dict[str, str]
    project_file: bool
    template: dict[str, Any]

    def declarable(self) -> dict[str, Any]:
        """Each value, by its dotted key, that differs from the type template: what a project
        file declares so that the profile does not depend on detection."""
        values = dict(_leaves(self.profile.model_dump(mode="json")))
        template = dict(_leaves(self.template))
        return {
            key: values[key]
            for key in self.sources
            if key in values and template.get(key) != values[key]
        }


def type_template(kind: ProjectType) -> dict[str, Any]:
    """The packaged template of `kind`."""
    resource = files("devops_cli").joinpath(*_TEMPLATES, f"{kind.value}.toml")
    return tomllib.loads(resource.read_text(encoding="utf-8"))


def resolve_profile(root: Path) -> ResolvedProfile:
    """The profile of the repository at `root`, from the files of the checkout.

    Raises:
        ConfigurationError: `.devops/project.toml` is not TOML or does not fit the profile.
    """
    declared = _project_file(root)
    detected_type, detected = _detect(root)
    kind = _kind(declared.get("extends"), detected_type)
    template = type_template(kind) if kind is not None else {}
    layers = [
        (f"template: {kind.value}" if kind else "template", template),
        *detected,
        (PROJECT_FILE, declared),
    ]
    merged = ProjectProfile().model_dump(mode="json")
    sources: dict[str, str] = {}
    for label, layer in layers:
        _merge(merged, layer, sources, label)
    try:
        profile = ProjectProfile.model_validate(merged)
    except ValidationError as exc:
        raise _invalid(exc) from exc
    # The sources in the order of the fields of the profile, so a report lists them in one order.
    sources = {key: sources[key] for key, _ in _leaves(merged) if key in sources}
    return ResolvedProfile(profile, sources, (root / PROJECT_FILE).is_file(), template)


def _invalid(exc: Exception) -> ConfigurationError:
    reason = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    return ConfigurationError(
        ERRORS.config.project_file_invalid.format(file=PROJECT_FILE, reason=reason),
        key=PROJECT_FILE,
    )


def _project_file(root: Path) -> dict[str, Any]:
    path = root / PROJECT_FILE
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise _invalid(exc) from exc


def _kind(declared: object, detected: ProjectType | None) -> ProjectType | None:
    """The type that the project file names, else the detected type."""
    if declared is None:
        return detected
    try:
        return ProjectType(str(declared))
    except ValueError as exc:
        raise _invalid(exc) from exc


def _detect(root: Path) -> tuple[ProjectType | None, list[tuple[str, dict[str, Any]]]]:
    """The detected type, and the detected facts as layers, each named by the file it read."""
    config = root / _ANSIBLE_CONFIG
    if not config.is_file():
        return None, []
    layers: list[tuple[str, dict[str, Any]]] = [
        (f"detected: {_ANSIBLE_CONFIG}", {"extends": ProjectType.ANSIBLE_K8S.value})
    ]
    layers.append(
        (f"detected: {_ANSIBLE_CONFIG}", {"ansible": _ansible_config_facts(root, config)})
    )
    playbooks = _playbook_dir(root)
    if playbooks is not None:
        layers.append((f"detected: {playbooks}", {"ansible": {"playbook_dir": playbooks}}))
    if (root / _K8S_DIR).is_dir():
        layers.append((f"detected: {_K8S_DIR}", {"kubernetes": {"dir": _K8S_DIR}}))
    return ProjectType.ANSIBLE_K8S, layers


def _ansible_config_facts(root: Path, config: Path) -> dict[str, Any]:
    """The inventory sources and the role folders that `ansible.cfg` names, in the repository. A
    role folder that does not exist is left out, as Ansible skips it."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config, encoding="utf-8")
    inventory = parser.get("defaults", "inventory", fallback="")
    roles = parser.get("defaults", "roles_path", fallback="")
    facts: dict[str, Any] = {}
    sources = list(_in_repo(root, inventory.split(",")))
    if sources:
        facts["inventory"] = sources
    folders = [path for path in _in_repo(root, roles.split(":")) if (root / path).is_dir()]
    if folders:
        facts["roles_path"] = folders
    return facts


def _in_repo(root: Path, entries: list[str]) -> Iterator[str]:
    """Each entry that is a path in the repository, relative to its root, once."""
    resolved_root = root.resolve()
    seen: set[str] = set()
    for entry in entries:
        text = entry.strip()
        if not text:
            continue
        resolved = (root / Path(text).expanduser()).resolve()
        if resolved.is_relative_to(resolved_root) and resolved != resolved_root:
            relative = resolved.relative_to(resolved_root).as_posix()
            if relative not in seen:
                seen.add(relative)
                yield relative


def _playbook_dir(root: Path) -> str | None:
    """The first `playbooks` folder at the root or one folder down."""
    if (root / _PLAYBOOKS).is_dir():
        return _PLAYBOOKS
    for folder in sorted(
        path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")
    ):
        if (folder / _PLAYBOOKS).is_dir():
            return f"{folder.name}/{_PLAYBOOKS}"
    return None


def _merge(
    merged: dict[str, Any],
    layer: Mapping[str, Any],
    sources: dict[str, str],
    label: str,
    prefix: str = "",
) -> None:
    """Merge `layer` into `merged`: a table by key, any other value in place of the lower one.
    Record `label` as the source of each value that the layer gives."""
    for key, value in layer.items():
        path = f"{prefix}{key}"
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            _merge(merged[key], value, sources, label, f"{path}.")
            continue
        merged[key] = copy.deepcopy(value)
        if isinstance(value, Mapping):
            sources.update({f"{path}.{leaf}": label for leaf, _ in _leaves(value)})
        else:
            sources[path] = label


def _leaves(mapping: Mapping[str, Any], prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Each value of a nested mapping that is not a mapping, by its dotted key."""
    for key, value in mapping.items():
        if isinstance(value, Mapping):
            yield from _leaves(value, f"{prefix}{key}.")
        else:
            yield f"{prefix}{key}", value


__all__ = [
    "PROJECT_FILE",
    "AnsibleProfile",
    "KubernetesProfile",
    "ProjectProfile",
    "ProjectType",
    "ResolvedProfile",
    "resolve_profile",
    "type_template",
]
