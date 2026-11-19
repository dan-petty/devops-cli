"""The opt-in render of the Argo CD Applications for the inventory (#3932).

`devops k8s image-pins` renders each Application of an environment tree as Argo CD renders it and
sorts the images that its charts name. The inventory lists the pins that the files of a repository
hold, so an image that only a rendered chart names is absent from it until the caller asks for the
render. `renderer_for` builds that render as a callable: a run of `devops research inventory`
without `--render`, and a dry run, builds none, so it starts no program and opens no connection.

The render yields the pinned images and the images on the `latest` tag, and not the images of a
registry that only the cluster reaches: a cluster-local name is no public pin to query, and the
advisory and release steps query public sources.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devops_cli.research.mapping import Render


def renderer_for(k8s_dir: Path | None = None) -> Render:
    """The renderer of the Argo CD Applications of the environment tree that `k8s_dir` names, else
    of the tree that the profile of the repository gives.

    The returned callable resolves the tree, renders it and gives the image references of its
    charts. It starts helm and kubectl, and it reads a chart source over the network, so only the
    run that sets `--render` calls it.
    """

    def rendered() -> Iterator[str]:
        """The image references of the rendered Applications, each once, in sorted order."""
        # The k8s render loads the chart and registry clients, so a command that imports this
        # module pays for none of them until the caller asks for the render.
        from devops_cli.k8s.environment import resolve_environment
        from devops_cli.k8s.image_pins import collect_image_pins

        pins = collect_image_pins(resolve_environment(k8s_dir))
        yield from pins.pinned
        yield from pins.latest

    return rendered
