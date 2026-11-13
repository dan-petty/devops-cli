"""The image pins of the Argo CD Applications, resolved in their registries before a merge (#1994).

Each Application of the environment tree (`devops_cli.k8s.environment`, #5131) is rendered as
Argo CD renders it: a path source with the builder of the Argo CD gate (`kubectl kustomize`), a
chart source with `helm template` and the value files that its `$ref` sources name. A git source of
the repository that holds the tree reads the checkout, and a source of another public repository is
fetched at its revision (`devops_cli.k8s.app_sources`). A kustomization folder, such as the product
base `k8s/devops`, renders the same way in place of the Applications. Helm's output then passes through `kubectl kustomize` too, which
reads YAML as Kubernetes does: a chart can write YAML that PyYAML refuses, such as a tab after a
value (the Alertmanager StatefulSet of the `prometheus` chart). The chart render leaves out the
chart's test manifests (`--skip-tests`): Argo CD does not apply a Helm test hook, so the image of a
test pod is never pulled.

Each `image` value of a rendered object is a pin, with three exceptions. Image Updater moves the
images that an `ImageUpdater` object names, so they are not pins. An image with no digest and the
`latest` tag, or no tag, is not a pin either: each pull can get a different image, so the check
refuses it (#2093). An image of a registry that only the cluster or this host reaches cannot be
resolved from a runner: its registry host is an IP address, `localhost`, a name with no dot (a
cluster Service), or a name under `.svc`, `.cluster.local` or `.local`.

`tag_digest` (`devops_cli.docker.registry`) resolves each pinned image once, as an anonymous client,
as the cluster pulls: it sends no stored registry credential, and answers a Bearer challenge with
an anonymous token. It sends a HEAD request of the manifest, which Docker Hub does not count as a
pull of the anonymous client (measured on 2026-11-01: three reads left `ratelimit-remaining`
unchanged, and a GET costs one pull).
"""

from __future__ import annotations

import ipaddress
import tempfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import dns.name
import httpx2
import yaml

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import PlannedProcessResult, run_subprocess
from devops_cli.core.serialization import YAML_SAFE_LOADER
from devops_cli.docker.registry import image_reference, tag_digest
from devops_cli.exceptions.docker import RegistryReadError
from devops_cli.exceptions.k8s import ImagePinError
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.k8s.app_sources import (
    SourceTrees,
    application_sources,
    normalize_git_url,
    ref_sources,
    repository_origin,
    source_revision,
)
from devops_cli.k8s.argocd_gate import discover_argocd_applications
from devops_cli.k8s.environment import EnvironmentTree
from devops_cli.k8s.template import build_manifest_path

# The tag of a reference that names none.
_DEFAULT_TAG = "latest"
# The domains of the registries that only the cluster or this host reaches: Kubernetes Services and
# multicast DNS names.
_LOCAL_REGISTRY_DOMAINS = tuple(
    dns.name.from_text(domain) for domain in ("svc", "cluster.local", "local")
)
_UPDATER_KIND = "ImageUpdater"
_KUSTOMIZE = ("kubectl", "kustomize")
# Applications rendered, and images resolved, at the same time: each render or resolve waits on
# the network for most of its time.
_WORKERS = 8


@dataclass(frozen=True)
class ImagePins:
    """The images that the rendered Applications name.

    `pinned` maps each image to resolve to the Applications that name it. `managed` holds the
    repositories that an `ImageUpdater` object names. `local` holds the images of a registry that
    only the cluster or this host reaches, and `latest` the images on the `latest` tag, each with
    its Applications. `planned` holds the render commands of a dry run, which renders nothing.
    """

    pinned: dict[str, tuple[str, ...]]
    managed: tuple[str, ...]
    local: dict[str, tuple[str, ...]]
    latest: dict[str, tuple[str, ...]]
    planned: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class PinResolution:
    """What resolving one image gave: its digest, or the resolver's error."""

    image: str
    applications: tuple[str, ...]
    registry: str
    digest: str | None
    error: str | None

    @property
    def resolved(self) -> bool:
        """Whether the registry holds the image."""
        return self.digest is not None


def names_latest(image: str) -> bool:
    """Whether `image` names no digest, and the `latest` tag or no tag, which the reference grammar
    reads as `latest`. A tag is in the last path component, so a registry's port is not one."""
    name, _, digest = image.partition("@")
    _, colon, tag = name.rsplit("/", 1)[-1].rpartition(":")
    return not digest and (not colon or tag == _DEFAULT_TAG)


def is_local_registry(registry: str) -> bool:
    """Whether only the cluster or this host reaches `registry`: an IP address, a name of one label
    (`localhost`, or a Service in the cluster), or a name under a local domain."""
    host = urlsplit("//" + registry).hostname or ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        name = dns.name.from_text(host)
        # A name's labels end with the root's empty label.
        return len(name.labels) <= 2 or any(name.is_subdomain(d) for d in _LOCAL_REGISTRY_DOMAINS)
    return True


def yaml_mappings(node: yaml.Node) -> Iterator[yaml.MappingNode]:
    """`node`, if it is a mapping, and every mapping below it."""
    if isinstance(node, yaml.MappingNode):
        yield node
        for _, value in node.value:
            yield from yaml_mappings(value)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            yield from yaml_mappings(item)


def yaml_scalar(node: yaml.MappingNode, key: str) -> str | None:
    """The text of the scalar that `key` holds in `node`, or `None` if `key` holds none."""
    for key_node, value in node.value:
        if key_node.value == key and isinstance(value, yaml.ScalarNode):
            return str(value.value)
    return None


def key_line(node: yaml.MappingNode, key: str) -> int:
    """The line (from 1) of the key `key` in `node`, or 0 if `node` has no such key."""
    for key_node, _ in node.value:
        if key_node.value == key:
            return int(key_node.start_mark.line) + 1
    return 0


def image_nodes(rendered: str) -> list[tuple[str, int]]:
    """Every `image` value of the objects in `rendered`, in order, with its line (from 1).

    The YAML is composed and not constructed, so a scalar keeps its text whatever tag YAML 1.1
    gives it, such as the `value` tag of a lone `=` that a CRD schema writes.
    """
    found: list[tuple[str, int]] = []
    for document in yaml.compose_all(rendered, Loader=YAML_SAFE_LOADER):
        for mapping in yaml_mappings(document) if document is not None else ():
            image = yaml_scalar(mapping, "image")
            if image:
                version = yaml_scalar(mapping, "version")
                if version and ":" not in image.rsplit("/", 1)[-1] and "@" not in image:
                    image = f"{image}:{version}"
                found.append((image, key_line(mapping, "image")))
    return found


def image_values(rendered: str) -> list[str]:
    """Every `image` value of the objects in `rendered`, in order."""
    return [image for image, _ in image_nodes(rendered)]


def updater_repositories(rendered: str) -> list[str]:
    """The repositories that the `ImageUpdater` objects in `rendered` name."""
    repositories: list[str] = []
    for document in yaml.compose_all(rendered, Loader=YAML_SAFE_LOADER):
        if (
            not isinstance(document, yaml.MappingNode)
            or yaml_scalar(document, "kind") != _UPDATER_KIND
        ):
            continue
        for mapping in yaml_mappings(document):
            name = yaml_scalar(mapping, "imageName")
            if name:
                repositories.append("/".join(image_reference(name)))
    return repositories


def _chart_command(
    trees: SourceTrees,
    name: str,
    source: dict[str, Any],
    namespace: str,
    refs: dict[str, Any],
) -> list[str]:
    helm = source.get("helm") or {}
    repo = str(source["repoURL"])
    if not urlsplit(repo).scheme:
        # An OCI chart repository: no Application of this repository uses one yet.
        raise ImagePinError(
            f"Application {name} names an OCI chart repository, which the check does not render: {repo}"
        )
    command = ["helm", "template", str(helm.get("releaseName") or name), str(source["chart"])]
    command += [
        "--repo",
        repo,
        "--version",
        str(source["targetRevision"]),
        "--namespace",
        namespace,
        # Argo CD does not apply a Helm test hook, so a test pod's image is never pulled.
        "--skip-tests",
    ]
    for value_file in helm.get("valueFiles") or []:
        command += ["--values", str(trees.value_file(str(value_file), refs))]
    return command


def _render_chart(command: list[str], workdir: Path) -> str:
    """Render a chart with `command`, then read its output as Kubernetes does."""
    proc = run_subprocess(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if isinstance(proc, PlannedProcessResult):
        return ""
    if proc.returncode != 0:
        raise ImagePinError(f"{' '.join(command[:3])} failed: {(proc.stderr or '').strip()}")
    workdir.mkdir(parents=True)
    (workdir / "chart.yaml").write_text(proc.stdout or "", encoding="utf-8")
    (workdir / "kustomization.yaml").write_text("resources:\n- chart.yaml\n", encoding="utf-8")
    return build_manifest_path(workdir)


def _application_renders(
    trees: SourceTrees, name: str, doc: dict[str, Any], workdir: Path
) -> Iterator[tuple[str, list[str] | None]]:
    """Each rendered source of an Application, with the chart command that rendered it. A dry run
    renders no path source of another repository, because it fetches nothing."""
    spec = doc.get("spec") or {}
    namespace = str((spec.get("destination") or {}).get("namespace") or "default")
    sources = application_sources(doc)
    refs = ref_sources(sources)
    for index, source in enumerate(sources):
        if "chart" in source:
            command = _chart_command(trees, name, source, namespace, refs)
            yield _render_chart(command, workdir / f"{name}-{index}"), command
        elif "path" in source:
            tree = trees.tree(str(source.get("repoURL") or trees.origin), source_revision(source))
            if not tree.planned:
                yield build_manifest_path((tree.root / str(source["path"])).resolve()), None


@dataclass(frozen=True)
class _Render:
    """What one Application's sources name."""

    name: str
    images: tuple[str, ...]
    managed: tuple[str, ...]
    planned: tuple[tuple[str, ...], ...]


def _render_application(
    trees: SourceTrees, name: str, doc: dict[str, Any], workdir: Path
) -> _Render:
    images: list[str] = []
    managed: list[str] = []
    planned: list[tuple[str, ...]] = []
    for rendered, command in _application_renders(trees, name, doc, workdir):
        if command is not None and not rendered:
            planned.append(tuple(command))
        images.extend(image_values(rendered))
        managed.extend(updater_repositories(rendered))
    return _Render(name, tuple(images), tuple(managed), tuple(planned))


def collect_image_pins(env: EnvironmentTree, *, origin_url: str | None = None) -> ImagePins:
    """Render every Argo CD Application of the environment tree `env`, a few at a time, and sort
    the images they name. A git source of the origin of `env.repo` (or `origin_url`) reads the
    checkout."""
    documents = sorted(discover_argocd_applications(env.application_dirs).items())
    origin = normalize_git_url(origin_url or repository_origin(env.repo))
    with tempfile.TemporaryDirectory(prefix="image-pins-") as tmp:
        trees = SourceTrees(env.repo, origin, Path(tmp) / "sources")
        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            renders = list(
                pool.map(
                    lambda item: _render_application(trees, item[0], item[1], Path(tmp)),
                    documents,
                )
            )
    pins = _sorted_pins(renders)
    return replace(pins, planned=(*trees.planned, *pins.planned))


def collect_kustomization_pins(path: Path) -> ImagePins:
    """Build the kustomization folder `path`, such as the product base `k8s/devops`, as a path
    source of an Application builds, and sort the images it names. The folder is the name of the
    Application in the result."""
    target = path.resolve()
    rendered = build_manifest_path(target)
    planned = () if rendered else ((*_KUSTOMIZE, str(target)),)
    render = _Render(
        str(path),
        tuple(image_values(rendered)),
        tuple(updater_repositories(rendered)),
        planned,
    )
    return _sorted_pins([render])


def _sorted_pins(renders: list[_Render]) -> ImagePins:
    """The images of the renders, sorted: managed, `latest`, local and pinned."""
    named: dict[str, set[str]] = {}
    managed: set[str] = set()
    planned: list[tuple[str, ...]] = []
    for render in renders:
        for image in render.images:
            named.setdefault(image, set()).add(render.name)
        managed.update(render.managed)
        planned.extend(render.planned)
    pinned: dict[str, tuple[str, ...]] = {}
    local: dict[str, tuple[str, ...]] = {}
    latest: dict[str, tuple[str, ...]] = {}
    for image, applications in sorted(named.items()):
        registry, repository = image_reference(image)
        if f"{registry}/{repository}" in managed:
            continue
        if names_latest(image):
            target = latest
        else:
            target = local if is_local_registry(registry) else pinned
        target[image] = tuple(sorted(applications))
    return ImagePins(pinned, tuple(sorted(managed)), local, latest, tuple(planned))


def resolve_image(
    image: str, applications: tuple[str, ...], client: httpx2.Client, *, timeout: float
) -> PinResolution:
    """Resolve `image` in its registry as an anonymous client, without pulling it.

    A registry that refuses the read, does not answer, or is on an address the client's egress level
    refuses gives a resolution with its error, not an exception: the other pins are still read.
    """
    registry, _ = image_reference(image)
    try:
        digest = tag_digest(image, client, timeout=timeout)
    except (RegistryReadError, SSRFBlockedError, httpx2.HTTPError) as exc:
        return PinResolution(image, applications, registry, None, str(exc))
    return PinResolution(image, applications, registry, digest, None)


def resolve_image_pins(
    pins: ImagePins, client: httpx2.Client, *, timeout: float
) -> list[PinResolution]:
    """Resolve each pinned image once, a few at a time, with one client."""

    def resolve(item: tuple[str, tuple[str, ...]]) -> PinResolution:
        return resolve_image(item[0], item[1], client, timeout=timeout)

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        return list(pool.map(resolve, pins.pinned.items()))
