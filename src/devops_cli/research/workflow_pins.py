"""The GitHub Actions pins: each `uses:` of the workflows and of the composite actions (#3896).

A repository pins an action to a commit and writes the release after it, as in
`uses: actions/checkout@<sha> # v7`. The version of the component is that release; an action with
no such comment has its ref. YAML parsers drop comments, so the comment comes from the line that
the parser gives for the key. A local action (`./...`) is no pin, and `docker://<image>` is an
image.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from devops_cli.core.serialization import YAML_SAFE_LOADER
from devops_cli.k8s.image_pins import key_line, yaml_mappings, yaml_scalar
from devops_cli.research.container_pins import image_component
from devops_cli.research.files import matching_files, parse_errors, relative
from devops_cli.research.models import Component, ComponentKind, Ecosystem

WORKFLOW_GLOBS = (
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".github/actions/*/action.yml",
    ".github/actions/*/action.yaml",
)
_DOCKER_PREFIX = "docker://"


def _comment_version(line_text: str) -> str:
    """The first word of the comment at the end of `line_text`, or an empty string."""
    words = line_text.partition(" #")[2].split()
    return words[0] if words else ""


def _component(uses: str, comment: str, file: str, line: int) -> Component | None:
    if uses.startswith("./"):
        return None
    if uses.startswith(_DOCKER_PREFIX):
        return image_component(uses.removeprefix(_DOCKER_PREFIX), file, line)
    name, _, ref = uses.partition("@")
    return Component(
        kind=ComponentKind.ACTION,
        ecosystem=Ecosystem.GITHUB_ACTIONS,
        name=name,
        version=comment or ref,
        file=file,
        line=line,
    )


def _read_file(root: Path, path: Path) -> list[Component]:
    with parse_errors(root, path):
        text = path.read_text(encoding="utf-8")
        text_lines = text.splitlines()
        file = relative(root, path)
        found: list[Component] = []
        for document in yaml.compose_all(text, Loader=YAML_SAFE_LOADER):
            for mapping in yaml_mappings(document) if document is not None else ():
                uses = yaml_scalar(mapping, "uses")
                if uses is None:
                    continue
                line = key_line(mapping, "uses")
                component = _component(uses, _comment_version(text_lines[line - 1]), file, line)
                if component is not None:
                    found.append(component)
        return found


def read_workflow_pins(root: Path) -> list[Component]:
    """The action and image components of the workflows of `root`."""
    found: list[Component] = []
    for path in matching_files(root, *WORKFLOW_GLOBS):
        found.extend(_read_file(root, path))
    return found
