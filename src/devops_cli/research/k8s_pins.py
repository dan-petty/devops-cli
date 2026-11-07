"""The pins under `k8s/`: the Helm charts of the Argo CD Applications and the images in YAML (#3896).

The files are read as they stand, so the reader needs no `helm` or `kubectl` and makes no request:
a chart that an Application pins is a component, and so is each image that a manifest or a values
file names. `devops k8s image-pins` renders each Application and resolves each image in its
registry; this reader lists what the files say. It finds an image in two shapes: an `image` value,
read as `devops k8s image-pins` reads it, and a mapping with a `repository` and a `tag`, the form
of a values file. A `tag` with no `repository` beside it is a chart's own default, and no image.
An Application source with no `chart` tracks a branch, and is no pin.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from devops_cli.core.serialization import YAML_SAFE_LOADER
from devops_cli.k8s.image_pins import image_nodes, key_line, yaml_mappings, yaml_scalar
from devops_cli.research.container_pins import image_component
from devops_cli.research.files import is_template, matching_files, parse_errors, relative
from devops_cli.research.models import Component, ComponentKind, Ecosystem

K8S_GLOBS = ("k8s/**/*.yaml", "k8s/**/*.yml")


def _read_file(root: Path, path: Path) -> list[Component]:
    with parse_errors(root, path):
        text = path.read_text(encoding="utf-8")
        file = relative(root, path)
        found = [
            image_component(image, file, line)
            for image, line in image_nodes(text)
            if not is_template(image)
        ]
        for document in yaml.compose_all(text, Loader=YAML_SAFE_LOADER):
            for mapping in yaml_mappings(document) if document is not None else ():
                chart = yaml_scalar(mapping, "chart")
                revision = yaml_scalar(mapping, "targetRevision")
                if chart and revision:
                    found.append(
                        Component(
                            kind=ComponentKind.CHART,
                            ecosystem=Ecosystem.HELM,
                            name=chart,
                            version=revision,
                            file=file,
                            line=key_line(mapping, "targetRevision"),
                        )
                    )
                repository = yaml_scalar(mapping, "repository")
                tag = yaml_scalar(mapping, "tag")
                if repository and tag and not is_template(f"{repository}{tag}"):
                    found.append(
                        image_component(f"{repository}:{tag}", file, key_line(mapping, "tag"))
                    )
        return found


def read_k8s_pins(root: Path) -> list[Component]:
    """The chart and image components of the YAML files under `k8s/` in `root`."""
    found: list[Component] = []
    for path in matching_files(root, *K8S_GLOBS):
        found.extend(_read_file(root, path))
    return found
