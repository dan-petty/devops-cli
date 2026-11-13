"""The image pins of the Argo CD Applications: rendered, sorted and resolved (#1994)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator
from importlib.resources import files
from pathlib import Path
from typing import Any

import httpx2
import pytest
import yaml

from devops_cli.dry_run.state import set_dry_run
from devops_cli.exceptions.k8s import ApplicationSourceError, ImagePinError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from devops_cli.k8s.environment import EnvironmentTree
from devops_cli.k8s.image_pins import (
    collect_image_pins,
    collect_kustomization_pins,
    image_values,
    is_local_registry,
    names_latest,
    resolve_image,
)
from tests.support.fakes.http import WebFake
from tests.support.fakes.oci_registry import ANONYMOUS_TOKEN, RegistryFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_CHART_RENDER = files("tests").joinpath("fixtures", "image_pins", "chart_render.yaml")
_SERVICE = "ghcr.io/example/service"
_LOCAL = "registry.example.svc:5000/team/tool:1.0"
_ALERTMANAGER = "quay.io/example/alertmanager:v1.0.0"
_CLOUDFLARED = "cloudflare/cloudflared:2026.10.4"
_HUB = "registry-1.docker.io"
_ORIGIN = "https://github.com/example/repo"
_DIGEST = "sha256:" + "a" * 64
_CRAWL4AI = "unclecode/crawl4ai"
_CRAWL4AI_DIGEST = "sha256:0b05666882bfb67f45d559a5b827839c54127b74aedd723f8ab338a3571b5fc9"
_SEARXNG = "searxng/searxng"
_SEARXNG_DIGEST = "sha256:aecad882e86eeb022b76351c8dce4eb48d0cbb16a5f1691f77ea32c96d317502"

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


def _kustomize(call: ProcessCall) -> ProcessAnswer:
    """`kubectl kustomize <directory>` prints each resource that the kustomization of the directory
    lists, as one YAML stream."""
    directory = Path(call.argv[2])
    kustomization = yaml.safe_load((directory / "kustomization.yaml").read_text(encoding="utf-8"))
    resources = [
        (directory / name).read_text(encoding="utf-8") for name in kustomization["resources"]
    ]
    return ProcessAnswer(stdout="---\n".join(resources))


@pytest.fixture(autouse=True)
def _kustomize_answers(process_fake: ProcessFake) -> Iterator[None]:
    """`kubectl kustomize` answers from the files of the tree, and helm answers from a test. The
    `image-pins` workflow runs the real kubectl and helm over the committed Applications (#5132)."""
    process_fake.answer(("kubectl", "kustomize"), _kustomize)
    process_fake.answer(
        lambda call: "remote.origin.url" in call.argv, ProcessAnswer(stdout=f"{_ORIGIN}.git\n")
    )
    yield


def _env(root: Path) -> EnvironmentTree:
    """The environment tree `k8s` of the repository at `root`."""
    return EnvironmentTree(root / "k8s", root)


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
    lone `=` of a CRD schema of `prometheus-operator-crds`. `kubectl kustomize` of the chart's
    output writes it again as YAML that PyYAML reads, which the committed fixture holds.
    `alertmanager` is the image that the value files give the StatefulSet."""
    normalized = _CHART_RENDER.read_text(encoding="utf-8").replace(_ALERTMANAGER, alertmanager)
    rendered = normalized.replace("- apiVersion: v1\n", "- apiVersion: v1\t\n", 1).replace(
        '- "="\n', "- =\n", 1
    )
    stdout = rendered if returncode == 0 else ""
    process_fake.answer(
        ("helm", "template"), ProcessAnswer(returncode=returncode, stdout=stdout, stderr=stderr)
    )
    process_fake.answer(
        lambda call: (
            call.argv[:2] == ("kubectl", "kustomize")
            and (Path(call.argv[2]) / "chart.yaml").is_file()
        ),
        ProcessAnswer(stdout=normalized),
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


def test_image_values_combines_image_and_version_for_operators() -> None:
    """When a Custom Resource separates repository and version into image and version fields,
    image_values combines them into a single reference (#1391)."""
    rendered = """apiVersion: installation.mattermost.com/v1beta1
kind: Mattermost
metadata:
  name: mattermost
spec:
  image: mattermost/mattermost-team-edition
  version: 11.7.11
"""
    assert image_values(rendered) == ["mattermost/mattermost-team-edition:11.7.11"]


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
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """A path source renders with kustomize and a chart source with `helm template` and the value
    files of the repository, less its test manifests, which Argo CD does not apply. The image that
    the chart's ImageUpdater names and the image of a cluster-only registry are not pins."""
    root = _tree(tmp_path, "cloudflare/cloudflared:2026.10.4", _SERVICE, _LOCAL)
    _chart_answers(process_fake)

    pins = collect_image_pins(_env(root))

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


def test_an_image_on_the_latest_tag_is_not_a_pin(tmp_path: Path, process_fake: ProcessFake) -> None:
    """A `latest` tag, no tag, and a `latest` tag of a cluster-only registry name `latest`. The
    untagged image that the chart's ImageUpdater names does not: Image Updater sets its tag."""
    local_latest = "registry.example.svc:5000/team/tool:latest"
    root = _tree(tmp_path, "example/app:latest", "example/plain", _SERVICE, local_latest)
    _chart_answers(process_fake)

    pins = collect_image_pins(_env(root))

    assert (pins.latest, pins.pinned, pins.local) == (
        {"example/app:latest": ("web",), "example/plain": ("web",), local_latest: ("web",)},
        {_ALERTMANAGER: ("monitoring",)},
        {},
    )


def test_a_value_file_that_sets_the_latest_tag_names_a_latest_image(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """A tag that a chart's value file sets is in the render, which a check of the raw files does
    not see."""
    root = _tree(tmp_path, "cloudflare/cloudflared:2026.10.4")
    _chart_answers(process_fake, alertmanager="quay.io/example/alertmanager:latest")

    pins = collect_image_pins(_env(root))

    assert (pins.latest, pins.pinned) == (
        {"quay.io/example/alertmanager:latest": ("monitoring",)},
        {"cloudflare/cloudflared:2026.10.4": ("web",)},
    )


def test_a_chart_that_does_not_render_stops_the_check_with_helms_error(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """A failed render is not an empty list of images."""
    root = _tree(tmp_path, "cloudflare/cloudflared:2026.10.4")
    _chart_answers(process_fake, returncode=1, stderr="Error: chart example 1.2.3 not found\n")

    with pytest.raises(ImagePinError) as caught:
        collect_image_pins(_env(root))

    assert caught.value.message == (
        "helm template monitoring failed: Error: chart example 1.2.3 not found"
    )


def test_an_oci_chart_repository_stops_the_check(tmp_path: Path, process_fake: ProcessFake) -> None:
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
        collect_image_pins(_env(root))

    assert caught.value.message == (
        "Application monitoring names an OCI chart repository, which the check does not render: "
        "registry.example.com/charts"
    )


def _resolve(*images: str) -> list[tuple[str, str, str | None, str | None]]:
    with http_client(EgressLevel.PUBLIC) as client:
        resolutions = [resolve_image(image, ("app",), client, timeout=5.0) for image in images]
    return [(r.image, r.registry, r.digest, r.error) for r in resolutions]


def test_each_image_resolves_to_its_digest_or_to_the_resolvers_error(web: WebFake) -> None:
    """The error line names the cause: a missing tag, a missing repository, or a registry that
    refuses an anonymous client. A Docker Hub image is read at the Docker Hub registry host, and
    its registry is `docker.io`."""
    web.serve(RegistryFake({f"{_HUB}/library/traefik:v3.7.16": _DIGEST}, host=_HUB))
    web.serve(RegistryFake({"ghcr.io/example/service:1.0": _DIGEST}))
    web.serve(RegistryFake({}, host="quay.io"))
    web.serve(RegistryFake({}, host="gcr.io", anonymous=False))

    assert _resolve(
        "traefik:v3.7.16",
        "ghcr.io/example/service:1.0",
        "ollama/ollama:0.0.0-does-not-exist",
        "quay.io/argoproj/argocd:v0.0.0-missing",
        "gcr.io/example/private:1.0",
    ) == [
        ("traefik:v3.7.16", "docker.io", _DIGEST, None),
        ("ghcr.io/example/service:1.0", "ghcr.io", _DIGEST, None),
        (
            "ollama/ollama:0.0.0-does-not-exist",
            "docker.io",
            None,
            "The registry gives no manifest for ollama/ollama:0.0.0-does-not-exist (HTTP 404).",
        ),
        (
            "quay.io/argoproj/argocd:v0.0.0-missing",
            "quay.io",
            None,
            "The registry gives no manifest for quay.io/argoproj/argocd:v0.0.0-missing (HTTP 404).",
        ),
        (
            "gcr.io/example/private:1.0",
            "gcr.io",
            None,
            "The registry of gcr.io/example/private:1.0 gives no anonymous pull token, so reading "
            "it needs credentials (HTTP 401).",
        ),
    ]


def test_an_image_with_a_tag_and_a_digest_is_a_pin_that_resolves_by_its_digest(
    tmp_path: Path, process_fake: ProcessFake, web: WebFake
) -> None:
    """The Crawl4AI image names a release tag and the digest of its index (#3884). It is a pin, not
    a `latest` image, and the registry is asked for the manifest of the digest."""
    image = f"{_CRAWL4AI}:0.9.5@{_CRAWL4AI_DIGEST}"
    _chart_answers(process_fake)
    web.serve(RegistryFake({f"{_HUB}/{_CRAWL4AI}:{_CRAWL4AI_DIGEST}": _CRAWL4AI_DIGEST}, host=_HUB))

    pins = collect_image_pins(_env(_tree(tmp_path, image)))

    assert (pins.pinned[image], pins.latest, _resolve(image)) == (
        ("web",),
        {},
        [(image, "docker.io", _CRAWL4AI_DIGEST, None)],
    )


def test_an_image_with_a_registry_host_a_date_tag_and_a_digest_resolves_by_its_digest(
    tmp_path: Path, process_fake: ProcessFake, web: WebFake
) -> None:
    """The SearXNG image names Docker Hub in full and a date tag with a commit (#3924). It is a
    pin, and the registry is asked for the manifest of the digest."""
    image = f"docker.io/{_SEARXNG}:2026.10.23-629368e40@{_SEARXNG_DIGEST}"
    _chart_answers(process_fake)
    web.serve(RegistryFake({f"{_HUB}/{_SEARXNG}:{_SEARXNG_DIGEST}": _SEARXNG_DIGEST}, host=_HUB))

    pins = collect_image_pins(_env(_tree(tmp_path, image)))

    assert (pins.pinned[image], pins.latest, _resolve(image)) == (
        ("web",),
        {},
        [(image, "docker.io", _SEARXNG_DIGEST, None)],
    )


def test_each_image_resolves_as_an_anonymous_client(web: WebFake) -> None:
    """The cluster pulls without credentials. The first request of a pin has no `Authorization`
    header, and the only one sent later is the anonymous token that the registry gave."""
    web.serve(RegistryFake({f"{_HUB}/{_CLOUDFLARED}": _DIGEST}, host=_HUB))

    _resolve(_CLOUDFLARED)

    assert [(r.method, r.url.path, r.headers.get("authorization")) for r in web.sent] == [
        ("HEAD", "/v2/cloudflare/cloudflared/manifests/2026.10.4", None),
        ("GET", "/token", None),
        ("HEAD", "/v2/cloudflare/cloudflared/manifests/2026.10.4", f"Bearer {ANONYMOUS_TOKEN}"),
    ]


def test_a_manifest_with_no_digest_does_not_resolve(web: WebFake) -> None:
    """A reply of 200 alone is not a resolved image."""
    web.respond("HEAD", "https://quay.io/v2/example/alertmanager/manifests/v1.0.0", 200)

    assert _resolve(_ALERTMANAGER) == [
        (
            _ALERTMANAGER,
            "quay.io",
            None,
            f"The registry reply for {_ALERTMANAGER} names no digest.",
        )
    ]


def test_a_registry_that_does_not_answer_is_an_error_of_the_pin(web: WebFake) -> None:
    """A lost connection fails one pin with its text, and not the whole run with a traceback."""
    web.fail(
        "https://quay.io/v2/example/alertmanager/manifests/v1.0.0",
        httpx2.ReadTimeout("The read operation timed out"),
    )

    [(_, _, digest, error)] = _resolve(_ALERTMANAGER)

    assert (digest, error) == (None, "The read operation timed out")


def _serve_registries(web: WebFake) -> None:
    web.serve(RegistryFake({f"{_HUB}/{_CLOUDFLARED}": _DIGEST}, host=_HUB))
    web.serve(RegistryFake({_ALERTMANAGER: _DIGEST}, host="quay.io"))


def test_the_command_reports_each_pin_and_passes_when_each_resolves(
    tmp_path: Path,
    web: WebFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
) -> None:
    """The managed and the local images are named, and are not resolved. Every request to a
    manifest is a HEAD, and none goes to `docker.io`, which redirects to the web site."""
    root = _tree(tmp_path, _CLOUDFLARED, _SERVICE, _LOCAL)
    _chart_answers(process_fake)
    _serve_registries(web)

    result = cli("k8s", "image-pins", "--k8s-dir", str(root / "k8s"))

    manifests = [r for r in web.sent if "/manifests/" in r.url.path]
    assert (
        result.exit_code,
        sorted({r.url.host for r in web.sent}),
        {r.method for r in manifests},
        "Each of the 2 image(s) that the Argo CD Applications pin resolves" in result.output,
        f"so they are not pins: {_SERVICE}" in " ".join(result.output.split()),
        _LOCAL in result.output,
    ) == (0, ["quay.io", _HUB], {"HEAD"}, True, True, True)


def test_the_command_follows_the_redirect_of_a_registry_to_its_storage(
    tmp_path: Path,
    web: WebFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
) -> None:
    """registry.k8s.io answers a manifest request with HTTP 307 to the host that stores the image."""
    image = "registry.k8s.io/example/tool:v1.0.0"
    root = _tree(tmp_path, image)
    _chart_answers(process_fake)
    web.redirect(
        "https://registry.k8s.io/v2/example/tool/manifests/v1.0.0",
        "https://storage.example.com/v2/example/tool/manifests/v1.0.0",
        status=307,
    )
    web.serve(RegistryFake({_ALERTMANAGER: _DIGEST}, host="quay.io"))
    web.answer(
        "https://storage.example.com/v2/example/tool/manifests/v1.0.0",
        200,
        method="HEAD",
        headers={"docker-content-digest": _DIGEST},
    )

    result = cli("k8s", "image-pins", "--k8s-dir", str(root / "k8s"))

    assert (result.exit_code, f"registry.k8s.io  {_DIGEST}" in result.output) == (0, True)


def test_the_command_fails_on_an_image_that_its_registry_does_not_hold(
    tmp_path: Path,
    web: WebFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
) -> None:
    """The error names the image, its Applications, its registry and the resolver's error."""
    root = _tree(tmp_path, "ollama/ollama:0.0.0-does-not-exist")
    _chart_answers(process_fake)
    web.serve(RegistryFake({}, host=_HUB))
    web.serve(RegistryFake({_ALERTMANAGER: _DIGEST}, host="quay.io"))

    result = cli("k8s", "image-pins", "--k8s-dir", str(root / "k8s"))

    assert (
        result.exit_code,
        "1 image(s) that the Argo CD Applications pin do not resolve: "
        "ollama/ollama:0.0.0-does-not-exist (Application web, registry docker.io): "
        "The registry gives no manifest for ollama/ollama:0.0.0-does-not-exist (HTTP 404)."
        in " ".join(result.output.split()),
    ) == (1, True)


def test_the_command_refuses_an_image_on_the_latest_tag_and_resolves_nothing(
    tmp_path: Path,
    web: WebFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
) -> None:
    """The error names each `latest` image and its Applications. No image is resolved, so the
    refused check sends no request."""
    root = _tree(tmp_path, "example/app:latest", _CLOUDFLARED)
    _chart_answers(process_fake)

    result = cli("k8s", "image-pins", "--k8s-dir", str(root / "k8s"))

    assert (
        result.exit_code,
        web.sent,
        "1 image(s) that the Argo CD Applications name use the latest tag and no digest, so each "
        "pull can get a different image. Set a version tag or a digest: "
        "example/app:latest (Application web)" in " ".join(result.output.split()),
    ) == (1, [], True)


def test_a_dry_run_renders_and_resolves_nothing(
    tmp_path: Path,
    web: WebFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
) -> None:
    """The renders are planned, not run, and no request goes to a registry. The output names the
    request that a run sends for each image."""
    root = _tree(tmp_path, _CLOUDFLARED)
    _chart_answers(process_fake)

    try:
        result = cli("k8s", "image-pins", "--k8s-dir", str(root / "k8s"), "--dry-run")
    finally:
        set_dry_run(False)

    assert (
        result.exit_code,
        web.sent,
        "HEAD https://<registry>/v2/<repository>/manifests/<reference>"
        in " ".join(result.output.split()),
    ) == (0, [], True)


_PRODUCT = "https://github.com/example/product"

_FOREIGN_PATH_APPLICATION = f"""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: devops
  namespace: argocd
spec:
  project: default
  source:
    repoURL: {_PRODUCT}
    targetRevision: main
    path: k8s/devops
  destination:
    namespace: devops
"""

_TWO_REF_APPLICATION = f"""apiVersion: argoproj.io/v1alpha1
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
          - $product/k8s/devops/monitoring/rules-values.yaml
    - repoURL: {_ORIGIN}
      targetRevision: main
      ref: values
    - repoURL: {_PRODUCT}.git
      targetRevision: main
      ref: product
  destination:
    namespace: monitoring
"""


def _product_files(checkout: Path, image: str) -> None:
    """The files of the product repository at its revision: a kustomization of one Deployment,
    and a values file of the rules."""
    base = checkout / "k8s" / "devops"
    (base / "monitoring").mkdir(parents=True)
    (base / "kustomization.yaml").write_text("resources:\n- deployment.yaml\n", encoding="utf-8")
    (base / "deployment.yaml").write_text(
        f"apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: service\nspec:\n  template:\n"
        f"    spec:\n      containers:\n        - name: service\n          image: {image}\n",
        encoding="utf-8",
    )
    (base / "monitoring" / "rules-values.yaml").write_text("rules: {}\n", encoding="utf-8")


def _serve_product(process_fake: ProcessFake, image: str) -> list[ProcessCall]:
    """git fetches the product repository: `git init` makes the folder and the fetch writes its
    files. The fetch calls are returned as the fake records them."""
    fetches: list[ProcessCall] = []

    def fetch(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        fetches.append(call)
        _product_files(Path(call.argv[2]), image)
        return subprocess.CompletedProcess(list(call.argv), 0, "", "")

    def init(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        Path(call.argv[-1]).mkdir(parents=True)
        return subprocess.CompletedProcess(list(call.argv), 0, "", "")

    process_fake.answer(("git", "init"), ProcessAnswer(side_effect=init))
    process_fake.answer(
        lambda call: call.argv[:1] == ("git",) and "fetch" in call.argv,
        ProcessAnswer(side_effect=fetch),
    )
    return fetches


def test_a_source_of_another_public_repository_is_fetched_once_at_its_revision(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """An infra repo names the product base of another repository and a second ref on it, as
    Application `devops` and Application `prometheus` do in the infra repo (#5131). The origin reads
    the checkout, and the other repository is fetched once, at `main`, after `--end-of-options`."""
    root = _tree(tmp_path, _CLOUDFLARED)
    apps = root / "k8s" / "argocd" / "apps"
    (apps / "devops.yaml").write_text(_FOREIGN_PATH_APPLICATION, encoding="utf-8")
    (apps / "monitoring.yaml").write_text(_TWO_REF_APPLICATION, encoding="utf-8")
    _chart_answers(process_fake)
    fetches = _serve_product(process_fake, "ghcr.io/example/product:2.0")

    pins = collect_image_pins(_env(root))

    [helm] = [call.argv for call in process_fake.calls if call.argv[:2] == ("helm", "template")]
    [fetch] = fetches
    checkout = Path(fetch.argv[2])
    assert (
        pins.pinned,
        fetch.argv[-3:],
        helm[-4:],
    ) == (
        {
            _CLOUDFLARED: ("web",),
            _ALERTMANAGER: ("monitoring",),
            "ghcr.io/example/product:2.0": ("devops",),
        },
        ("--end-of-options", _PRODUCT, "main"),
        (
            "--values",
            str(root / "k8s" / "example" / "values.yaml"),
            "--values",
            str(checkout / "k8s" / "devops" / "monitoring" / "rules-values.yaml"),
        ),
    )


def test_a_source_that_is_not_an_https_repository_is_not_fetched(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """Only an https repository is fetched: a `file://` or an `ext::` URL could read the host or
    run a command."""
    root = _tree(tmp_path, _CLOUDFLARED)
    apps = root / "k8s" / "argocd" / "apps"
    (apps / "devops.yaml").write_text(
        _FOREIGN_PATH_APPLICATION.replace(_PRODUCT, "file:///srv/product"), encoding="utf-8"
    )
    _chart_answers(process_fake)

    with pytest.raises(ApplicationSourceError) as caught:
        collect_image_pins(_env(root))

    assert (caught.value.message, [c for c in process_fake.calls if "fetch" in c.argv]) == (
        f"The git source file:///srv/product is not the origin {_ORIGIN} and not an https "
        "repository, so it is not fetched.",
        [],
    )


def test_a_dry_run_lists_the_fetch_of_another_repository_and_runs_none(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    root = _tree(tmp_path, _CLOUDFLARED)
    (root / "k8s" / "argocd" / "apps" / "devops.yaml").write_text(
        _FOREIGN_PATH_APPLICATION, encoding="utf-8"
    )
    _chart_answers(process_fake)

    set_dry_run(True)
    try:
        pins = collect_image_pins(_env(root))
    finally:
        set_dry_run(False)

    fetches = [command for command in pins.planned if "fetch" in command]
    assert (
        [command[-3:] for command in fetches],
        [c.argv for c in process_fake.calls if c.argv[:1] == ("git",) and "fetch" in c.argv],
        "devops" in {app for apps in pins.pinned.values() for app in apps},
    ) == ([("--end-of-options", _PRODUCT, "main")], [], False)


def test_a_kustomization_folder_renders_in_place_of_the_applications(
    tmp_path: Path,
    web: WebFake,
    cli: Callable[..., Any],
) -> None:
    """`devops k8s image-pins k8s/devops` renders the product base alone, with no Application and
    no environment tree, and names the folder as the Application of each image."""
    _product_files(tmp_path, "ghcr.io/example/product:2.0")
    web.serve(RegistryFake({"ghcr.io/example/product:2.0": _DIGEST}))
    base = tmp_path / "k8s" / "devops"

    result = cli("k8s", "image-pins", str(base))

    assert (
        result.exit_code,
        "Each of the 1 image(s) that the Argo CD Applications pin resolves" in result.output,
        collect_kustomization_pins(base).pinned,
    ) == (0, True, {"ghcr.io/example/product:2.0": (str(base),)})


def test_managed_names_a_repository_whose_tag_the_deploy_sets(
    tmp_path: Path, web: WebFake, cli: Callable[..., Any]
) -> None:
    """The product base names its own images with no tag, because Image Updater of the infra repo
    sets them. The folder holds no `ImageUpdater` object, so `--managed` names such a repository:
    the command does not refuse or resolve its images, and it names the repository (#5131)."""
    _product_files(tmp_path, _SERVICE)
    base = tmp_path / "k8s" / "devops"

    refused = cli("k8s", "image-pins", str(base))
    result = cli("k8s", "image-pins", str(base), "--managed", _SERVICE)

    assert (
        refused.exit_code,
        result.exit_code,
        web.sent,
        f"so they are not pins: {_SERVICE}" in " ".join(result.output.split()),
    ) == (1, 0, [], True)
