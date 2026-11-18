"""The watch list applied to the pins: OSV identity, purl and registry reference (#3932).

The inventory reads the files of a repository and names each pin by its inventory ecosystem and
name. A source query needs more: the ecosystem and name that OSV gives the component, the package
URL of a package, the registry host of an image and the upstream repository. The watch list of
`.devops/research-watch.toml` gives them, and it also declares the pins that no file of the
repository holds, such as the operating system of a node.

The mapping starts no program and makes no request: it reads the same files as the inventory. The
one path that reaches outside them is the opt-in render of the Argo CD Applications, which
`renderer_for` builds for the caller that asks for it (#3932).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from packageurl import PackageURL

from devops_cli.docker.registry import image_reference
from devops_cli.research.container_pins import image_component
from devops_cli.research.inventory import read_inventory, summarize
from devops_cli.research.models import Component, ComponentKind, Ecosystem, Inventory
from devops_cli.research.watch import PinEntry, WatchEntry, WatchList, read_watch_list

# The purl type of each ecosystem that a package registry serves. A component of another ecosystem
# has no purl that a package source reads, so its purl stays empty.
_PURL_TYPES = {
    Ecosystem.PYPI: "pypi",
    Ecosystem.NPM: "npm",
    Ecosystem.HELM: "helm",
}
# The file of a pin that no file of the repository holds.
_EXTERNAL_FILE = "external"
# The file of an image that only the rendered Applications name.
_RENDERED_FILE = "rendered"

# The opt-in render of the Argo CD Applications, which gives the image references of their charts.
Render = Callable[[], Iterable[str]]


def purl_of(component: Component) -> str:
    """The purl of `component`, or the empty string when its ecosystem, name or version gives none."""
    purl_type = _PURL_TYPES.get(component.ecosystem)
    if purl_type is None or not component.name or not component.version:
        return ""
    return PackageURL(type=purl_type, name=component.name, version=component.version).to_string()


def registry_of(component: Component) -> str:
    """The registry host that serves the image of `component`, or the empty string for another kind."""
    if component.kind is not ComponentKind.CONTAINER_IMAGE:
        return ""
    return image_reference(component.name)[0]


def apply_mapping(components: list[Component], watch: WatchList) -> list[Component]:
    """`components` with the OSV identity, the purl and the repository of their watch entry, and
    one component for each pin that `watch` declares."""
    mapped = [
        _mapped(component, watch.entry_of(component.ecosystem, component.name))
        for component in components
    ]
    return [*mapped, *(_pin_component(pin) for pin in watch.pin)]


def mapped_inventory(root: Path, *, renderer: Render | None = None) -> Inventory:
    """The inventory of `root`, mapped to the OSV identity, the purl and the repository of each
    component, and extended with the pins of the watch list.

    `renderer` is the opt-in render of the Argo CD Applications: with one set, each image that the
    rendered charts name joins the inventory at the file `rendered`. Without one, the inventory
    reads the files of `root` alone and reaches nothing outside them.
    """
    components = read_inventory(root).components
    if renderer is not None:
        components = [*components, *_rendered_components(renderer())]
    mapped = apply_mapping(components, read_watch_list(root))
    mapped.sort(key=lambda c: (c.file, c.line, c.name))
    return Inventory(components=mapped, summary=summarize(mapped))


def _rendered_components(references: Iterable[str]) -> list[Component]:
    """The container image component of each reference that the rendered Applications name."""
    return [image_component(reference, _RENDERED_FILE, 0) for reference in references]


def _mapped(component: Component, entry: WatchEntry | None) -> Component:
    """`component` with the OSV identity, the purl, the registry reference and the repository that
    `entry` gives. An entry that gives no purl leaves the purl that the pin builds."""
    purl = purl_of(component) if entry is None or entry.purl is None else entry.purl
    return component.model_copy(
        update={
            "osv_ecosystem": "" if entry is None else entry.osv_ecosystem or "",
            "osv_name": "" if entry is None else entry.osv_name or "",
            "purl": purl,
            "registry": registry_of(component),
            "repo": "" if entry is None else entry.repo,
        }
    )


def _pin_component(pin: PinEntry) -> Component:
    """The component of a `[[pin]]` entry, at the file `external` and line 0."""
    component = Component(
        kind=pin.kind,
        ecosystem=pin.ecosystem,
        name=pin.name,
        version=pin.version,
        file=_EXTERNAL_FILE,
        line=0,
    )
    purl = purl_of(component) if pin.purl is None else pin.purl
    return component.model_copy(
        update={
            "osv_ecosystem": pin.osv_ecosystem or "",
            "osv_name": pin.osv_name or "",
            "purl": purl,
            "registry": registry_of(component),
            "repo": pin.repo or "",
        }
    )
