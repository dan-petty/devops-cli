"""The pins of the tools lock: each tool, and each package of the lock of a Node tool (#3896).

The lock is read with the model of `devops_cli.tools_lock`, so a lock that the installer refuses is
refused here too. A binary tool has the ecosystem `github-release` when its `source` is a GitHub
repository, and `unknown` for any other source.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from devops_cli.research.files import LineIndex, matching_files, parse_errors, relative
from devops_cli.research.models import Component, ComponentKind, Ecosystem
from devops_cli.tools_lock import LOCK_FILENAME, read_tools_lock

LOCK_DIR = "src/devops_cli/tools_lock"
_NODE_MODULES = "node_modules/"


def _binary_ecosystem(source: str) -> Ecosystem:
    return (
        Ecosystem.GITHUB_RELEASE if urlsplit(source).hostname == "github.com" else Ecosystem.UNKNOWN
    )


def _read_tools(root: Path, lock_dir: Path) -> list[Component]:
    lock_path = lock_dir / LOCK_FILENAME
    if not lock_path.is_file():
        return []
    with parse_errors(root, lock_path):
        lock = read_tools_lock(lock_dir)
        lines = LineIndex(lock_path.read_text(encoding="utf-8"))
        file = relative(root, lock_path)
        found: list[Component] = []
        groups = (
            ("binary", lock.binary, None),
            ("python", lock.python, Ecosystem.PYPI),
            ("npm", lock.npm, Ecosystem.NPM),
        )
        for table, tools, ecosystem in groups:
            for name, tool in tools.items():
                found.append(
                    Component(
                        kind=ComponentKind.TOOL,
                        ecosystem=ecosystem or _binary_ecosystem(tool.source),
                        name=name,
                        version=tool.version,
                        file=file,
                        line=lines.find_line(f"[{table}.{name}]"),
                    )
                )
        return found


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


def read_tool_pins(root: Path) -> list[Component]:
    """The components of the tools lock of `root`."""
    found = _read_tools(root, root / LOCK_DIR)
    for path in matching_files(root, f"{LOCK_DIR}/*/package-lock.json"):
        found.extend(_read_node_packages(root, path))
    return found
