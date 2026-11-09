"""The container pins: the images of Dockerfiles and the features of the devcontainer lock (#3896).

A Dockerfile is read with the tree-sitter grammar that `devops ai ast` loads. The images are those
of a `FROM` line and of a `COPY --from=<image>`. A name that an earlier `FROM ... AS <name>` gave to
a stage is no image, and neither is a reference with a variable.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

from devops_cli.research.files import (
    LineIndex,
    is_template,
    matching_files,
    parse_errors,
    relative,
    split_image,
)
from devops_cli.research.models import Component, ComponentKind, Ecosystem

DOCKERFILE_GLOBS = ("Dockerfile*", ".devcontainer/Dockerfile*")
# A configuration in `.devcontainer/<folder>/` keeps its lock next to it (#4248).
DEVCONTAINER_LOCK_GLOBS = (
    ".devcontainer/devcontainer-lock.json",
    ".devcontainer/*/devcontainer-lock.json",
)
_FROM_FLAG = "--from="


def image_component(reference: str, file: str, line: int) -> Component:
    """The component for the image `reference`, pinned at `line` of `file`."""
    name, version = split_image(reference)
    return Component(
        kind=ComponentKind.CONTAINER_IMAGE,
        ecosystem=Ecosystem.DOCKER,
        name=name,
        version=version,
        file=file,
        line=line,
    )


def _dockerfile_parser() -> Any:
    import tree_sitter
    import tree_sitter_dockerfile

    # The 0.2 grammar hands out its language as an integer, which tree-sitter 0.26 still accepts
    # and warns about. `devops ai ast` loads the grammar the same way.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="int argument support", category=DeprecationWarning
        )
        return tree_sitter.Parser(tree_sitter.Language(tree_sitter_dockerfile.language()))


def _text(node: Any) -> str:
    return str(node.text.decode("utf-8"))


def _dockerfile_images(source: bytes) -> list[tuple[str, int]]:
    """The images of a Dockerfile in file order, each with its line (from 1)."""
    stages: set[str] = set()
    images: list[tuple[str, int]] = []
    for instruction in _dockerfile_parser().parse(source).root_node.children:
        line = instruction.start_point.row + 1
        if instruction.type == "from_instruction":
            spec = next(c for c in instruction.children if c.type == "image_spec")
            alias = next((c for c in instruction.children if c.type == "image_alias"), None)
            if _text(spec) not in stages:
                images.append((_text(spec), line))
            if alias is not None:
                stages.add(_text(alias))
        elif instruction.type == "copy_instruction":
            for param in (c for c in instruction.children if c.type == "param"):
                source_name = _text(param).removeprefix(_FROM_FLAG)
                if _text(param).startswith(_FROM_FLAG) and source_name not in stages:
                    images.append((source_name, line))
    return [(image, line) for image, line in images if not is_template(image)]


def _read_dockerfile(root: Path, path: Path) -> list[Component]:
    with parse_errors(root, path):
        images = _dockerfile_images(path.read_bytes())
    file = relative(root, path)
    # A stage number, as in `COPY --from=0`, names a stage and no image.
    return [image_component(image, file, line) for image, line in images if not image.isdigit()]


def _read_devcontainer_lock(root: Path, path: Path) -> list[Component]:
    file = relative(root, path)
    with parse_errors(root, path):
        text = path.read_text(encoding="utf-8")
        lines = LineIndex(text)
        return [
            Component(
                kind=ComponentKind.DEVCONTAINER_FEATURE,
                ecosystem=Ecosystem.DEVCONTAINER_FEATURE,
                name=split_image(key)[0],
                version=feature["version"],
                file=file,
                line=lines.find(f'"{key}"'),
            )
            for key, feature in json.loads(text).get("features", {}).items()
        ]


def read_container_pins(root: Path) -> list[Component]:
    """The container components of `root`."""
    found: list[Component] = []
    for path in matching_files(root, *DOCKERFILE_GLOBS):
        found.extend(_read_dockerfile(root, path))
    for path in matching_files(root, *DEVCONTAINER_LOCK_GLOBS):
        found.extend(_read_devcontainer_lock(root, path))
    return found
