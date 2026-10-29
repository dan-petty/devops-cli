"""The image pins of the Argo CD Applications: rendered, sorted and resolved (#1994)."""

from __future__ import annotations

import json
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from docker.auth import resolve_repository_name
from docker.utils import parse_repository_tag

from devops_cli.dry_run.state import set_dry_run
from devops_cli.exceptions.k8s import ImagePinError
from devops_cli.k8s.image_pins import (
    collect_image_pins,
    image_reference,
    image_values,
    is_local_registry,
    names_latest,
    resolve_image,
)
from tests.support.fakes.imagetools import ImagetoolsFake
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.imagetools_recording import RECORDED_IMAGES

_CHART_RENDER = files("tests").joinpath("fixtures", "image_pins", "chart_render.yaml")
_SERVICE = "ghcr.io/example/service"
_LOCAL = "registry.example.svc:5000/team/tool:1.0"
_ALERTMANAGER = "quay.io/example/alertmanager:v1.0.0"

_PATH_APPLICATION = """apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: web
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example/repo
    path: k8s/web
  destination:
    namespace: web
"""

_CHART_APPLICATION = """apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: monitoring
  namespace: argocd
spec:
  project: default
  sources:
    - repoURL: https://charts.example.com
      chart: example
      targetRevision: 1.2.3
      helm:
        valueFiles:
          - $values/k8s/example/values.yaml
    - repoURL: https://github.com/example/repo
      ref: values
  destination:
    namespace: monitoring
"""


def _tree(root: Path, *images: str) -> Path:
    """A repository with a path Application whose Deployment runs `images`, and a chart one."""
    apps = root / "k8s" / "argocd" / "apps"
    apps.mkdir(parents=True)
    (apps / "web.yaml").write_text(_PATH_APPLICATION, encoding="utf-8")
    (apps / "monitoring.yaml").write_text(_CHART_APPLICATION, encoding="utf-8")
    (root / "k8s" / "example").mkdir()
    (root / "k8s" / "example" / "values.yaml").write_text("replicas: 1\n", encoding="utf-8")
    web = root / "k8s" / "web"
    web.mkdir()
    (web / "kustomization.yaml").write_text("resources:\n- deployment.yaml\n", encoding="utf-8")
    containers = "".join(
        f"        - name: c{index}\n          image: {image}\n"
        for index, image in enumerate(images)
    )
    (web / "deployment.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web\nspec:\n"
        "  selector:\n    matchLabels:\n      app: web\n  template:\n    metadata:\n"
        f"      labels:\n        app: web\n    spec:\n      containers:\n{containers}",
        encoding="utf-8",
    )
    return root


def _chart_answers(
    process_fake: ProcessFake,
    *,
    returncode: int = 0,
    stderr: str = "",
    alertmanager: str = _ALERTMANAGER,
) -> None:
    """`helm template` writes the canned chart, with two things that the real charts write and that
    PyYAML refuses, which the committed fixture cannot hold (the repository's hooks read it with
    PyYAML): the tab after a value of the `prometheus` chart's Alertmanager StatefulSet, and the
    lone `=` of a CRD schema of `prometheus-operator-crds`. `alertmanager` is the image that the
    value files give the StatefulSet."""
    rendered = (
        _CHART_RENDER.read_text(encoding="utf-8")
        .replace("- apiVersion: v1\n", "- apiVersion: v1\t\n", 1)
        .replace('- "="\n', "- =\n", 1)
        .replace(_ALERTMANAGER, alertmanager)
    )
    stdout = rendered if returncode == 0 else ""
    process_fake.answer(
        ("helm", "template"), ProcessAnswer(returncode=returncode, stdout=stdout, stderr=stderr)
    )


def test_image_values_reads_each_image_scalar_of_the_rendered_objects() -> None:
    """A container, an init container and a WorkflowTemplate step name images; a CRD schema whose
    property is called `image` names none, and a lone `=` does not stop the read."""
    rendered = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: one
spec:
  template:
    spec:
      initContainers:
        - name: init
          image: busybox:1.37
      containers:
        - name: main
          image: ghcr.io/example/main:2.0
---
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: two
spec:
  templates:
    - name: step
      container:
        image: quay.io/example/step:3.0
---
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: things.example.com
spec:
  versions:
    - name: v1
      schema:
        openAPIV3Schema:
          properties:
            image:
              type: string
            operator:
              enum:
                - =
"""
    assert image_values(rendered) == [
        "busybox:1.37",
        "ghcr.io/example/main:2.0",
        "quay.io/example/step:3.0",
    ]


@pytest.mark.parametrize(
    "image",
    [
        "traefik",
        "valkey/valkey:9.1.2-alpine",
        "docker.io/traefik:v3.7.16",
        "index.docker.io/library/nginx:1.27",
        "ghcr.io/example/service",
        "ghcr.io/example/service:latest@sha256:" + "c" * 64,
        "quay.io/argoproj/argocd:v3.5.3",
        "nvcr.io/nvidia/k8s/dcgm-exporter:4.6.1-4.8.4-distroless",
        "localhost:5000/team/tool:1.0",
        "192.0.2.10:5000/team/tool",
        "gitea-http:3000/team/tool:1.0",
        "registry.example.svc:5000/team/tool:1.0",
    ],
)
def test_an_image_reference_splits_as_the_docker_sdk_splits_it(image: str) -> None:
    """The registry and the repository are the Docker SDK's, whose rule is the reference grammar's.

    The SDK strips only the digest of a reference that holds a tag and a digest, so its split is
    applied twice: a repository is compared without its tag."""
    repository, _ = parse_repository_tag(parse_repository_tag(image)[0])
    assert image_reference(image) == resolve_repository_name(repository)


@pytest.mark.parametrize(
    ("registry", "local"),
    [
        ("docker.io", False),
        ("ghcr.io", False),
        ("quay.io", False),
        ("registry.k8s.io", False),
        ("localhost:5000", True),
        ("192.0.2.10:5000", True),
        ("[2001:db8::1]:5000", True),
        ("gitea-http:3000", True),
        ("registry.example.svc", True),
        ("registry.registry.svc.cluster.local:5000", True),
        ("registry.local", True),
    ],
)
def test_a_registry_that_only_the_cluster_or_this_host_reaches_is_local(
    registry: str, local: bool
) -> None:
    """An IP address, localhost, a name with no dot, or a name under `.svc`, `.cluster.local` or
    `.local` is a registry that a runner cannot reach."""
    assert is_local_registry(registry) is local


@pytest.mark.parametrize(
    ("image", "latest"),
    [
        ("example/app:latest", True),
        ("example/app", True),
        ("traefik", True),
        ("registry.example.com:5000/team/app", True),
        ("localhost:5000/team/app:latest", True),
        ("example/app:1.0", False),
        ("example/app:latest-alpine", False),
        ("registry.example.com:5000/team/app:1.0", False),
        ("example/app@sha256:" + "d" * 64, False),
        ("example/app:latest@sha256:" + "d" * 64, False),
    ],
)
def test_an_image_with_no_digest_and_the_latest_tag_or_no_tag_names_latest(
    image: str, latest: bool
) -> None:
    """The reference grammar gives a reference with no tag the tag `latest`; a digest pins the
    image whatever its tag, and a registry's port is not a tag."""
    assert names_latest(image) is latest


def test_the_pins_are_the_rendered_images_less_the_managed_and_the_local_ones(
    tmp_path: Path, imagetools: ImagetoolsFake, process_fake: ProcessFake
) -> None:
    """A path source renders with kustomize and a chart source with `helm template` and the value
    files of the repository, less its test manifests, which Argo CD does not apply. The image that
    the chart's ImageUpdater names and the image of a cluster-only registry are not pins."""
    root = _tree(tmp_path, "cloudflare/cloudflared:2026.10.4", _SERVICE, _LOCAL)
    _chart_answers(process_fake)

    pins = collect_image_pins(root)

    helm = [call.argv for call in process_fake.calls if call.argv[:2] == ("helm", "template")]
    assert (pins.pinned, pins.managed, pins.local, pins.latest, helm) == (
        {"cloudflare/cloudflared:2026.10.4": ("web",), _ALERTMANAGER: ("monitoring",)},
        (_SERVICE,),
        {_LOCAL: ("web",)},
        {},
        [
            (
                "helm",
                "template",
                "monitoring",
                "example",
                "--repo",
                "https://charts.example.com",
                "--version",
                "1.2.3",
                "--namespace",
                "monitoring",
                "--skip-tests",
                "--values",
                str(root / "k8s" / "example" / "values.yaml"),
            )
        ],
    )


def test_an_image_on_the_latest_tag_is_not_a_pin(
    tmp_path: Path, imagetools: ImagetoolsFake, process_fake: ProcessFake
) -> None:
    """A `latest` tag, no tag, and a `latest` tag of a cluster-only registry name `latest`. The
    untagged image that the chart's ImageUpdater names does not: Image Updater sets its tag."""
    local_latest = "registry.example.svc:5000/team/tool:latest"
    root = _tree(tmp_path, "example/app:latest", "example/plain", _SERVICE, local_latest)
    _chart_answers(process_fake)

    pins = collect_image_pins(root)

    assert (pins.latest, pins.pinned, pins.local) == (
        {"example/app:latest": ("web",), "example/plain": ("web",), local_latest: ("web",)},
        {_ALERTMANAGER: ("monitoring",)},
        {},
    )


def test_a_value_file_that_sets_the_latest_tag_names_a_latest_image(
    tmp_path: Path, imagetools: ImagetoolsFake, process_fake: ProcessFake
) -> None:
    """A tag that a chart's value file sets is in the render, which a check of the raw files does
    not see."""
    root = _tree(tmp_path, "cloudflare/cloudflared:2026.10.4")
    _chart_answers(process_fake, alertmanager="quay.io/example/alertmanager:latest")

    pins = collect_image_pins(root)

    assert (pins.latest, pins.pinned) == (
        {"quay.io/example/alertmanager:latest": ("monitoring",)},
        {"cloudflare/cloudflared:2026.10.4": ("web",)},
    )


def test_a_chart_that_does_not_render_stops_the_check_with_helms_error(
    tmp_path: Path, imagetools: ImagetoolsFake, process_fake: ProcessFake
) -> None:
    """A failed render is not an empty list of images."""
    root = _tree(tmp_path, "cloudflare/cloudflared:2026.10.4")
    _chart_answers(process_fake, returncode=1, stderr="Error: chart example 1.2.3 not found\n")

    with pytest.raises(ImagePinError) as caught:
        collect_image_pins(root)

    assert caught.value.message == (
        "helm template monitoring failed: Error: chart example 1.2.3 not found"
    )


def test_an_oci_chart_repository_stops_the_check(
    tmp_path: Path, imagetools: ImagetoolsFake, process_fake: ProcessFake
) -> None:
    """No Application uses an OCI chart repository yet, so the check names one instead of skipping
    its images."""
    root = _tree(tmp_path, "cloudflare/cloudflared:2026.10.4")
    chart_app = root / "k8s" / "argocd" / "apps" / "monitoring.yaml"
    chart_app.write_text(
        chart_app.read_text(encoding="utf-8").replace(
            "https://charts.example.com", "registry.example.com/charts"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ImagePinError) as caught:
        collect_image_pins(root)

    assert caught.value.message == (
        "Application monitoring names an OCI chart repository, which the check does not render: "
        "registry.example.com/charts"
    )


def test_each_image_resolves_to_its_digest_or_to_the_resolvers_error(
    imagetools: ImagetoolsFake,
) -> None:
    """The resolver's own error line names the cause: a missing tag, a missing repository, or a
    registry that refuses an anonymous client."""
    resolutions = [resolve_image(image, ("app",)) for image in RECORDED_IMAGES]

    digests = {
        image: json.loads(run.stdout)["digest"]
        for image, run in imagetools.runs.items()
        if run.returncode == 0
    }
    assert [(r.image, r.registry, r.digest, r.error) for r in resolutions] == [
        (RECORDED_IMAGES[0], "docker.io", digests[RECORDED_IMAGES[0]], None),
        (RECORDED_IMAGES[1], "ghcr.io", digests[RECORDED_IMAGES[1]], None),
        (
            RECORDED_IMAGES[2],
            "docker.io",
            None,
            "docker.io/ollama/ollama:0.0.0-does-not-exist: not found",
        ),
        (RECORDED_IMAGES[3], "quay.io", None, "quay.io/argoproj/argocd:v0.0.0-missing: not found"),
        (
            RECORDED_IMAGES[4],
            "docker.io",
            None,
            "pull access denied, repository does not exist or may require authorization: "
            "server message: insufficient_scope: authorization failed",
        ),
        (
            RECORDED_IMAGES[5],
            "ghcr.io",
            None,
            "failed to authorize: failed to fetch anonymous token: unexpected status from GET "
            "request to https://ghcr.io/token?scope=repository%3Adan-petty%2Fno-such-image-1994"
            "%3Apull&service=ghcr.io: 403 Forbidden",
        ),
    ]


def test_each_image_resolves_as_an_anonymous_client(
    imagetools: ImagetoolsFake, process_fake: ProcessFake
) -> None:
    """The cluster pulls without credentials, so the resolver runs with an empty Docker
    configuration: a stored credential that a registry refuses does not fail the pin."""
    resolve_image(RECORDED_IMAGES[0], ("web",))

    configs = [
        call.env.get("DOCKER_CONFIG") if call.env else None
        for call in process_fake.calls
        if call.argv[:4] == ("docker", "buildx", "imagetools", "inspect")
    ]
    assert (
        len(configs),
        all(config and Path(config).name.startswith("image-pins-docker-") for config in configs),
    ) == (1, True)


def test_a_manifest_with_no_digest_does_not_resolve(imagetools: ImagetoolsFake) -> None:
    """Exit 0 alone is not a resolved image."""
    imagetools.script(_ALERTMANAGER, returncode=0, stdout='{"schemaVersion": 2}')

    resolution = resolve_image(_ALERTMANAGER, ("monitoring",))

    assert (resolution.resolved, resolution.error) == (False, "the manifest names no digest")


def test_the_command_reports_each_pin_and_passes_when_each_resolves(
    tmp_path: Path,
    imagetools: ImagetoolsFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
) -> None:
    """The managed and the local images are named, and are not resolved."""
    root = _tree(tmp_path, "cloudflare/cloudflared:2026.10.4", _SERVICE, _LOCAL)
    _chart_answers(process_fake)
    imagetools.script(_ALERTMANAGER, returncode=0, stdout='{"digest": "sha256:' + "a" * 64 + '"}')

    result = cli("k8s", "image-pins", str(root))

    assert (
        result.exit_code,
        sorted(imagetools.calls),
        "Each of the 2 image(s) that the Argo CD Applications pin resolves" in result.output,
        f"Image Updater moves these repositories, so they are not pins: {_SERVICE}"
        in result.output,
        _LOCAL in result.output,
    ) == (0, sorted(["cloudflare/cloudflared:2026.10.4", _ALERTMANAGER]), True, True, True)


def test_the_command_fails_on_an_image_that_its_registry_does_not_hold(
    tmp_path: Path,
    imagetools: ImagetoolsFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
) -> None:
    """The error names the image, its Applications, its registry and the resolver's error."""
    root = _tree(tmp_path, "ollama/ollama:0.0.0-does-not-exist")
    _chart_answers(process_fake)
    imagetools.script(_ALERTMANAGER, returncode=0, stdout='{"digest": "sha256:' + "b" * 64 + '"}')

    result = cli("k8s", "image-pins", str(root))

    assert (
        result.exit_code,
        "1 image(s) that the Argo CD Applications pin do not resolve: "
        "ollama/ollama:0.0.0-does-not-exist (Application web, registry docker.io): "
        "docker.io/ollama/ollama:0.0.0-does-not-exist: not found"
        in " ".join(result.output.split()),
    ) == (1, True)


def test_the_command_refuses_an_image_on_the_latest_tag_and_resolves_nothing(
    tmp_path: Path,
    imagetools: ImagetoolsFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
) -> None:
    """The error names each `latest` image and its Applications. No image is resolved, so the
    refused check spends no Docker Hub pull."""
    root = _tree(tmp_path, "example/app:latest", "cloudflare/cloudflared:2026.10.4")
    _chart_answers(process_fake)

    result = cli("k8s", "image-pins", str(root))

    assert (
        result.exit_code,
        imagetools.calls,
        "1 image(s) that the Argo CD Applications name use the latest tag and no digest, so each "
        "pull can get a different image. Set a version tag or a digest: "
        "example/app:latest (Application web)" in " ".join(result.output.split()),
    ) == (1, [], True)


def test_a_dry_run_renders_and_resolves_nothing(
    tmp_path: Path,
    imagetools: ImagetoolsFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
) -> None:
    """The renders and the resolves are planned, not run."""
    root = _tree(tmp_path, "cloudflare/cloudflared:2026.10.4")
    _chart_answers(process_fake)

    try:
        result = cli("k8s", "image-pins", str(root), "--dry-run")
    finally:
        set_dry_run(False)

    assert (
        result.exit_code,
        imagetools.calls,
        "docker buildx imagetools inspect <image> --format {{json .Manifest}}"
        in " ".join(result.output.split()),
    ) == (0, [], True)
