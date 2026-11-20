"""The Python pins: pyproject.toml and uv.lock (#3896).

A direct dependency has the pin of pyproject.toml. A package that only uv.lock holds is a
transitive one, and has the version of the lock. The project itself, which uv.lock lists with an
editable or virtual source, is no pin.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from devops_cli.research.files import LineIndex, parse_errors
from devops_cli.research.models import Component, ComponentKind, Ecosystem

PYPROJECT = "pyproject.toml"
UV_LOCK = "uv.lock"


def _component(name: str, version: str, file: str, line: int) -> Component:
    return Component(
        kind=ComponentKind.PYTHON_PACKAGE,
        ecosystem=Ecosystem.PYPI,
        name=canonicalize_name(name),
        version=version,
        file=file,
        line=line,
    )


def _pinned_version(requirement: Requirement) -> str:
    """The version of an `==` pin, else the specifier as written (`>=1.2`), else empty."""
    for spec in requirement.specifier:
        if spec.operator in ("==", "==="):
            return spec.version
    return str(requirement.specifier)


def _declared_requirements(data: dict[str, Any]) -> list[str]:
    """Every requirement string of pyproject.toml: dependencies, extras and dependency groups."""
    project = data.get("project", {})
    declared: list[str] = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        declared.extend(extra)
    for group in data.get("dependency-groups", {}).values():
        # An entry that is a table, `{include-group = "dev"}`, includes another group.
        declared.extend(entry for entry in group if isinstance(entry, str))
    return declared


def _read_pyproject(root: Path) -> list[Component]:
    path = root / PYPROJECT
    if not path.is_file():
        return []
    with parse_errors(root, path):
        text = path.read_text(encoding="utf-8")
        lines = LineIndex(text)
        return [
            _component(
                requirement.name,
                _pinned_version(requirement),
                PYPROJECT,
                lines.find(f'"{raw}"'),
            )
            for raw in _declared_requirements(tomllib.loads(text))
            for requirement in [Requirement(raw)]
        ]


def _read_uv_lock(root: Path, direct: set[str]) -> list[Component]:
    path = root / UV_LOCK
    if not path.is_file():
        return []
    with parse_errors(root, path):
        text = path.read_text(encoding="utf-8")
        lines = LineIndex(text)
        found: list[Component] = []
        for package in tomllib.loads(text).get("package", []):
            name = package["name"]
            line = lines.find_line(f'name = "{name}"')
            source = package.get("source", {})
            if "editable" in source or "virtual" in source or canonicalize_name(name) in direct:
                continue
            found.append(_component(name, package.get("version", ""), UV_LOCK, line))
        return found


def read_python_pins(root: Path) -> list[Component]:
    """The Python components of `root`."""
    direct = _read_pyproject(root)
    found = [
        *direct,
        *_read_uv_lock(root, {component.name for component in direct}),
    ]
    return found
