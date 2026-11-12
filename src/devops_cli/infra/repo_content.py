"""What the files of an infra repo hold: playbooks, roles, the tasks that run for real in check
mode, the collections that the plays use and pin, the CI workflows and the Makefile targets that
change a node (#5121).

It reads files only. A YAML file is composed with the safe loader and never constructed, so a tag
such as `!vault` is no error and no object is built. A folder whose name starts with `.` is not
read, and no file that a link takes out of the repository is read.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from packaging.version import InvalidVersion, Version

from devops_cli.config.defaults import DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES

_YAML_SUFFIXES: Final[tuple[str, ...]] = (".yml", ".yaml")
_SKIPPED_DIRS: Final[frozenset[str]] = frozenset({"node_modules", "ansible_collections"})
# A play holds one of these keys (the keywords of a play and of `import_playbook`).
_PLAY_KEYS: Final[frozenset[str]] = frozenset(
    {"hosts", "import_playbook", "ansible.builtin.import_playbook"}
)
_BOOL_TAG: Final[str] = "tag:yaml.org,2002:bool"
# The YAML 1.1 words for false that PyYAML and Ansible read as a bool.
_YAML_FALSE: Final[frozenset[str]] = frozenset({"false", "no", "off"})
# A fully qualified collection name of a module: namespace.collection.module (Galaxy names).
_FQCN: Final = re.compile(r"(?P<collection>[a-z0-9_]+\.[a-z0-9_]+)\.[a-z0-9_]+")
_CORE_COLLECTIONS: Final[frozenset[str]] = frozenset({"ansible.builtin", "ansible.legacy"})
_ROLE_MARKERS: Final[tuple[str, ...]] = ("tasks", "meta", "handlers")
_REQUIREMENTS_FILES: Final[tuple[str, ...]] = (
    "collections/requirements.yml",
    "collections/requirements.yaml",
)
_WORKFLOWS_DIR: Final[str] = ".github/workflows"
_MAKEFILES: Final[tuple[str, ...]] = ("GNUmakefile", "makefile", "Makefile")
# The Makefile targets that cordon, drain, restart or reboot a node: the per-host targets and the
# rolling restart of the whole cluster.
_NODE_TARGET_PREFIXES: Final[tuple[str, ...]] = ("drain-", "uncordon-", "restart-", "reboot-")
_NODE_TARGETS: Final[frozenset[str]] = frozenset({"rolling-restart"})
_EXACT_VERSION_PREFIX: Final[str] = "=="


@dataclass(frozen=True)
class YamlContent:
    """What the YAML files of a repository hold."""

    playbooks: tuple[str, ...]
    unparsed: tuple[str, ...]
    # Each task with `check_mode: false`, as `<path>:<line> <name>`.
    check_mode_off: tuple[str, ...]
    collections_used: tuple[str, ...]


@dataclass(frozen=True)
class CollectionRequirements:
    """The collections file of a repository: its path, and each collection it does not pin."""

    path: str | None
    unpinned: tuple[str, ...] = ()
    error: str | None = None


def read_yaml_content(root: Path) -> YamlContent:
    """The playbooks, the tasks with `check_mode: false` and the collections in use, from every
    YAML file of the repository at `root`."""
    playbooks: list[str] = []
    unparsed: list[str] = []
    check_mode_off: list[str] = []
    collections: set[str] = set()
    for path in _files(root, _YAML_SUFFIXES):
        relative = path.relative_to(root).as_posix()
        try:
            documents = [
                node
                for node in yaml.compose_all(
                    path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader
                )
                if node is not None
            ]
        except yaml.YAMLError, UnicodeDecodeError:
            unparsed.append(relative)
            continue
        if _is_playbook(documents):
            playbooks.append(relative)
        for mapping in _list_item_mappings(documents):
            check_mode_off.extend(_check_mode_off(mapping, relative))
            collections.update(_collections(mapping))
    return YamlContent(
        playbooks=tuple(playbooks),
        unparsed=tuple(unparsed),
        check_mode_off=tuple(check_mode_off),
        collections_used=tuple(sorted(collections)),
    )


def _files(root: Path, suffixes: tuple[str, ...]) -> Iterator[Path]:
    """The files of the repository with one of `suffixes`, in a stable order."""
    resolved_root = root.resolve()
    for folder, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if not d.startswith(".") and d not in _SKIPPED_DIRS
        )
        for name in sorted(filenames):
            path = Path(folder) / name
            if name.endswith(suffixes) and _is_readable_file(path, resolved_root):
                yield path


def _is_readable_file(path: Path, resolved_root: Path) -> bool:
    """Whether `path` is a file in the repository that is small enough to read."""
    resolved = path.resolve()
    return (
        resolved.is_relative_to(resolved_root)
        and resolved.is_file()
        and resolved.stat().st_size <= DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES
    )


def _is_playbook(documents: list[yaml.Node]) -> bool:
    """Whether a file is one document that is a list of plays."""
    if len(documents) != 1 or not isinstance(documents[0], yaml.SequenceNode):
        return False
    items = documents[0].value
    return bool(items) and all(
        isinstance(item, yaml.MappingNode) and not _PLAY_KEYS.isdisjoint(_keys(item))
        for item in items
    )


def _keys(mapping: yaml.MappingNode) -> list[str]:
    return [key.value for key, _ in mapping.value if isinstance(key, yaml.ScalarNode)]


def _list_item_mappings(documents: list[yaml.Node]) -> Iterator[yaml.MappingNode]:
    """Every mapping that is an item of a list, depth first: a play, a task, a handler or a
    block. A mapping that is the value of a key, such as a dict of variables whose keys are
    sysctl names, is not one."""
    stack: list[tuple[yaml.Node, bool]] = [(document, False) for document in reversed(documents)]
    while stack:
        node, in_list = stack.pop()
        if isinstance(node, yaml.MappingNode):
            if in_list:
                yield node
            stack.extend((value, False) for _, value in reversed(node.value))
        elif isinstance(node, yaml.SequenceNode):
            stack.extend((item, True) for item in reversed(node.value))


def _check_mode_off(mapping: yaml.MappingNode, relative: str) -> list[str]:
    """The task that `mapping` is, when it has `check_mode: false`."""
    values = {key.value: value for key, value in mapping.value if isinstance(key, yaml.ScalarNode)}
    flag = values.get("check_mode")
    if not (
        isinstance(flag, yaml.ScalarNode)
        and flag.tag == _BOOL_TAG
        and flag.value.lower() in _YAML_FALSE
    ):
        return []
    name = values.get("name")
    title = name.value if isinstance(name, yaml.ScalarNode) else "(no name)"
    return [f"{relative}:{mapping.start_mark.line + 1} {title}"]


def _collections(mapping: yaml.MappingNode) -> set[str]:
    """The collections whose modules the keys of `mapping` name."""
    found: set[str] = set()
    for key in _keys(mapping):
        match = _FQCN.fullmatch(key)
        if match and match["collection"] not in _CORE_COLLECTIONS:
            found.add(match["collection"])
    return found


def find_roles(root: Path, roles_path: tuple[Path, ...]) -> tuple[str, ...]:
    """The roles in each folder of `roles_path` that is in the repository at `root`."""
    resolved_root = root.resolve()
    roles: set[str] = set()
    for folder in roles_path:
        resolved = folder.resolve()
        if not (resolved.is_relative_to(resolved_root) and resolved.is_dir()):
            continue
        roles.update(
            role.name
            for role in resolved.iterdir()
            if role.is_dir() and any((role / marker).is_dir() for marker in _ROLE_MARKERS)
        )
    return tuple(sorted(roles))


def read_collection_requirements(root: Path) -> CollectionRequirements:
    """The collections file of the repository, and each collection it names with no exact
    version."""
    path = next((root / name for name in _REQUIREMENTS_FILES if (root / name).is_file()), None)
    if path is None:
        return CollectionRequirements(path=None)
    relative = path.relative_to(root).as_posix()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        return CollectionRequirements(path=relative, error=type(exc).__name__)
    entries = data.get("collections", []) if isinstance(data, dict) else []
    return CollectionRequirements(
        path=relative,
        unpinned=tuple(_unpinned(entry) for entry in entries if _unpinned(entry)),
    )


def _unpinned(entry: object) -> str:
    """`<name> <version>` of a collection with no exact version, else empty."""
    if isinstance(entry, dict):
        name, version = str(entry.get("name", "")), entry.get("version")
    else:
        name, version = str(entry), None
    if version is not None and _is_exact(str(version)):
        return ""
    return f"{name} {version if version is not None else '(no version)'}"


def _is_exact(version: str) -> bool:
    """Whether a Galaxy version names one release, such as `2.1.0` or `==2.1.0`."""
    try:
        Version(version.strip().removeprefix(_EXACT_VERSION_PREFIX))
    except InvalidVersion:
        return False
    return True


def find_ci_workflows(root: Path) -> tuple[str, ...]:
    """The GitHub Actions workflow files of the repository."""
    folder = root / _WORKFLOWS_DIR
    if not folder.is_dir():
        return ()
    return tuple(
        sorted(
            path.relative_to(root).as_posix()
            for path in folder.iterdir()
            if path.is_file() and path.name.endswith(_YAML_SUFFIXES)
        )
    )


def find_node_targets(root: Path) -> tuple[str, ...]:
    """The Makefile targets of the repository that cordon, drain, restart or reboot a node."""
    path = next((root / name for name in _MAKEFILES if (root / name).is_file()), None)
    if path is None:
        return ()
    targets: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        targets.extend(name for name in _rule_targets(line) if _is_node_target(name))
    return tuple(dict.fromkeys(targets))


def _rule_targets(line: str) -> list[str]:
    """The targets of a Makefile rule line, or none for a recipe, a comment or an assignment."""
    if not line or line[0] in "\t #" or ":" not in line:
        return []
    head, _, tail = line.partition(":")
    if "=" in head or tail.startswith("="):
        return []
    return head.split()


def _is_node_target(name: str) -> bool:
    return name in _NODE_TARGETS or name.startswith(_NODE_TARGET_PREFIXES)


__all__ = [
    "CollectionRequirements",
    "YamlContent",
    "find_ci_workflows",
    "find_node_targets",
    "find_roles",
    "read_collection_requirements",
    "read_yaml_content",
]
