"""The Node pins: each package of the `package-lock.json` at the root, which pins the Node tools of
the project as devDependencies (#3896, #6409).
"""

from __future__ import annotations

import json
from pathlib import Path

from devops_cli.config.constants import CONST_NPM_LOCKFILE
from devops_cli.research.files import LineIndex, matching_files, parse_errors, relative
from devops_cli.research.models import Component, ComponentKind, Ecosystem

_NODE_MODULES = "node_modules/"


def _read_node_packages(root: Path, path: Path) -> list[Component]:
    """The packages of a `package-lock.json`, by the name that follows the last `node_modules/`."""
    with parse_errors(root, path):
        text = path.read_text(encoding="utf-8")
        lines = LineIndex(text)
        file = relative(root, path)
        found: list[Component] = []
        for key, package in json.loads(text).get("packages", {}).items():
            if _NODE_MODULES not in key or "version" not in package:
                continue
            found.append(
                Component(
                    kind=ComponentKind.NODE_PACKAGE,
                    ecosystem=Ecosystem.NPM,
                    name=key.rsplit(_NODE_MODULES, 1)[1],
                    version=package["version"],
                    file=file,
                    line=lines.find(f'"{key}"'),
                )
            )
        return found


def read_node_pins(root: Path) -> list[Component]:
    """The components of the npm lockfile at the root of `root`."""
    found: list[Component] = []
    for path in matching_files(root, CONST_NPM_LOCKFILE):
        found.extend(_read_node_packages(root, path))
    return found
