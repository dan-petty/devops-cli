"""The image pins of the Argo CD Applications, resolved in their registries before a merge (#1994).

Each Application under `k8s/argocd/` is rendered as Argo CD renders it: a path source with the
builder of the Argo CD gate (`kubectl kustomize`), a chart source with `helm template` and the
value files of the repository. Helm's output then passes through `kubectl kustomize` too, which
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

`docker buildx imagetools inspect` resolves each pinned image once, as an anonymous client, as the
cluster pulls: it runs with an empty Docker configuration, so a stored registry credential neither
helps nor breaks it (GHCR refuses an expired one with 403). It reads the manifest, which Docker Hub
counts as a pull of an anonymous client (measured on 2026-10-29: three inspects took
`ratelimit-remaining` from 100 to 97).
"""

from __future__ import annotations

import ipaddress
import json
import tempfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import dns.name
import yaml

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import PlannedProcessResult, run_subprocess
from devops_cli.core.serialization import YAML_SAFE_LOADER
from devops_cli.exceptions.k8s import ImagePinError
from devops_cli.k8s.argocd_gate import discover_argocd_applications
from devops_cli.k8s.template import build_manifest_path

# The registry of a name whose first component names none, and Docker Hub's other name.
_DEFAULT_REGISTRY = "docker.io"
_DEFAULT_REGISTRY_ALIAS = "index.docker.io"
# The tag of a reference that names none.
_DEFAULT_TAG = "latest"
# The domains of the registries that only the cluster or this host reaches: Kubernetes Services and
# multicast DNS names.
_LOCAL_REGISTRY_DOMAINS = tuple(
    dns.name.from_text(domain) for domain in ("svc", "cluster.local", "local")
)
_UPDATER_KIND = "ImageUpdater"
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
    planned: bool = False

    @property
    def resolved(self) -> bool:
        """Whether the registry holds the image."""
        return self.digest is not None


def inspect_command(image: str) -> list[str]:
    """The command that resolves `image` without pulling it."""
    return ["docker", "buildx", "imagetools", "inspect", image, "--format", "{{json .Manifest}}"]


def image_reference(image: str) -> tuple[str, str]:
    """The registry host and the repository of `image`, with no tag and no digest.

    The rule is the Docker reference grammar's (`splitDockerDomain` of distribution/reference): the
    first component names a registry when it holds a `.` or a `:` or is `localhost`. The Docker SDK's
    `parse_repository_tag` and `resolve_repository_name` read a name the same way, and a test holds
    the two equal; the SDK is not imported here, because it ships no type information.
    """
    name = image.split("@", 1)[0]
    if ":" in name.rsplit("/", 1)[-1]:
        name = name.rsplit(":", 1)[0]
    first, _, rest = name.partition("/")
    if rest and ("." in first or ":" in first or first == "localhost"):
        return (_DEFAULT_REGISTRY if first == _DEFAULT_REGISTRY_ALIAS else first), rest
    return _DEFAULT_REGISTRY, name


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


def _mappings(node: yaml.Node) -> Iterator[yaml.MappingNode]:
    if isinstance(node, yaml.MappingNode):
        yield node
        for _, value in node.value:
            yield from _mappings(value)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            yield from _mappings(item)


def _scalar(node: yaml.MappingNode, key: str) -> str | None:
    for key_node, value in node.value:
        if key_node.value == key and isinstance(value, yaml.ScalarNode):
            return str(value.value)
    return None


def image_values(rendered: str) -> list[str]:
    """Every `image` value of the objects in `rendered`, in order.

    The YAML is composed and not constructed, so a scalar keeps its text whatever tag YAML 1.1
    gives it, such as the `value` tag of a lone `=` that a CRD schema writes.
    """
    found: list[str] = []
    for document in yaml.compose_all(rendered, Loader=YAML_SAFE_LOADER):
        for mapping in _mappings(document) if document is not None else ():
            image = _scalar(mapping, "image")
            if image:
                version = _scalar(mapping, "version")
                if version and ":" not in image.rsplit("/", 1)[-1] and "@" not in image:
                    image = f"{image}:{version}"
                found.append(image)
    return found


def updater_repositories(rendered: str) -> list[str]:
    """The repositories that the `ImageUpdater` objects in `rendered` name."""
    repositories: list[str] = []
    for document in yaml.compose_all(rendered, Loader=YAML_SAFE_LOADER):
        if not isinstance(document, yaml.MappingNode) or _scalar(document, "kind") != _UPDATER_KIND:
            continue
        for mapping in _mappings(document):
            name = _scalar(mapping, "imageName")
            if name:
                repositories.append("/".join(image_reference(name)))
    return repositories


def _value_file(root: Path, value_file: str) -> Path:
    # `$values/<path>` names a file of the repository that the `values` ref source checks out.
    return root / (value_file.split("/", 1)[1] if value_file.startswith("$") else value_file)


def _chart_command(root: Path, name: str, source: dict[str, Any], namespace: str) -> list[str]:
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
        command += ["--values", str(_value_file(root, str(value_file)))]
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
    root: Path, name: str, doc: dict[str, Any], workdir: Path
) -> Iterator[tuple[str, list[str] | None]]:
    """Each rendered source of an Application, with the chart command that rendered it."""
    spec = doc.get("spec") or {}
    namespace = str((spec.get("destination") or {}).get("namespace") or "default")
    sources = spec.get("sources") or [spec.get("source") or {}]
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        if "chart" in source:
            command = _chart_command(root, name, source, namespace)
            yield _render_chart(command, workdir / f"{name}-{index}"), command
        elif "path" in source:
            yield build_manifest_path((root / str(source["path"])).resolve()), None


@dataclass(frozen=True)
class _Render:
    """What one Application's sources name."""

    name: str
    images: tuple[str, ...]
    managed: tuple[str, ...]
    planned: tuple[tuple[str, ...], ...]


def _render_application(root: Path, name: str, doc: dict[str, Any], workdir: Path) -> _Render:
    images: list[str] = []
    managed: list[str] = []
    planned: list[tuple[str, ...]] = []
    for rendered, command in _application_renders(root, name, doc, workdir):
        if command is not None and not rendered:
            planned.append(tuple(command))
        images.extend(image_values(rendered))
        managed.extend(updater_repositories(rendered))
    return _Render(name, tuple(images), tuple(managed), tuple(planned))


def collect_image_pins(root: Path) -> ImagePins:
    """Render every Argo CD Application of `root`, a few at a time, and sort the images they name."""
    named: dict[str, set[str]] = {}
    managed: set[str] = set()
    planned: list[tuple[str, ...]] = []
    documents = sorted(discover_argocd_applications(root).items())
    with (
        tempfile.TemporaryDirectory(prefix="image-pins-") as tmp,
        ThreadPoolExecutor(max_workers=_WORKERS) as pool,
    ):
        renders = list(
            pool.map(lambda item: _render_application(root, item[0], item[1], Path(tmp)), documents)
        )
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


def _error_line(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1].removeprefix("ERROR: ") if lines else "the resolver gave no error text"


def resolve_image(image: str, applications: tuple[str, ...]) -> PinResolution:
    """Resolve `image` in its registry as an anonymous client, without pulling it."""
    registry, _ = image_reference(image)
    with tempfile.TemporaryDirectory(prefix="image-pins-docker-") as anonymous:
        proc = run_subprocess(
            inspect_command(image),
            capture_output=True,
            text=True,
            check=False,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            env={"DOCKER_CONFIG": anonymous},
        )
    if isinstance(proc, PlannedProcessResult):
        return PinResolution(image, applications, registry, None, None, planned=True)
    if proc.returncode != 0:
        return PinResolution(image, applications, registry, None, _error_line(proc.stderr or ""))
    try:
        digest = json.loads(proc.stdout or "")["digest"]
    except json.JSONDecodeError, KeyError, TypeError:
        return PinResolution(image, applications, registry, None, "the manifest names no digest")
    return PinResolution(image, applications, registry, str(digest), None)


def resolve_image_pins(pins: ImagePins) -> list[PinResolution]:
    """Resolve each pinned image once, a few at a time."""
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        return list(pool.map(lambda item: resolve_image(*item), pins.pinned.items()))
