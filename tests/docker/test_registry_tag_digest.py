"""The digest a tag names in its registry, read with the OCI distribution API (#1997)."""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from devops_cli.docker.registry import TaggedImage, image_reference, tag_digest, tagged_image
from devops_cli.exceptions.docker import RegistryReadError, RegistryTagNotFoundError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from tests.support.fakes.http import WebFake
from tests.support.fakes.oci_registry import RegistryFake

IMAGE = "ghcr.io/example/devops-cli/service"
DIGEST = "sha256:" + "b" * 64


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        (f"{IMAGE}:latest", TaggedImage("ghcr.io", "example/devops-cli/service", "latest")),
        ("localhost:5000/team/app:v1", TaggedImage("localhost:5000", "team/app", "v1")),
        ("localhost/app:v1", TaggedImage("localhost", "app", "v1")),
        (f"{IMAGE}@{DIGEST}", TaggedImage("ghcr.io", "example/devops-cli/service", DIGEST)),
        (f"{IMAGE}:1.0@{DIGEST}", TaggedImage("ghcr.io", "example/devops-cli/service", DIGEST)),
        ("nginx:1.27", TaggedImage("docker.io", "nginx", "1.27")),
        ("library/nginx:1.27", TaggedImage("docker.io", "library/nginx", "1.27")),
        ("valkey/valkey:9.1.2-alpine", TaggedImage("docker.io", "valkey/valkey", "9.1.2-alpine")),
        ("docker.io/traefik:v3.7.16", TaggedImage("docker.io", "traefik", "v3.7.16")),
        (
            "index.docker.io/library/nginx:1.27",
            TaggedImage("docker.io", "library/nginx", "1.27"),
        ),
    ],
    ids=[
        "ghcr",
        "registry-port",
        "localhost",
        "digest",
        "tag-and-digest",
        "hub-one-component",
        "hub-library",
        "hub-path",
        "hub-host",
        "hub-alias",
    ],
)
def test_a_reference_that_names_its_registry_and_a_tag_splits(
    reference: str, expected: TaggedImage
) -> None:
    """The registry is the first component when it holds a dot or a port, or is `localhost`; a name
    with no registry is on Docker Hub. A digest takes the place of the tag."""
    assert tagged_image(reference) == expected


@pytest.mark.parametrize(
    "reference",
    [IMAGE, "nginx", "registry.example.com:5000/app", f"https://{IMAGE}:v1"],
    ids=["no-tag", "hub-no-tag", "port-no-tag", "scheme"],
)
def test_a_reference_without_a_tag_or_a_digest_is_refused(reference: str) -> None:
    """A reference that names neither a tag nor a digest has no digest to look up."""
    with pytest.raises(RegistryReadError) as caught:
        tagged_image(reference)

    assert caught.value.error_code == "DOCKER_REGISTRY_READ_ERROR"
    assert caught.value.exit_code == 1


def test_the_tag_digest_comes_from_the_registry_with_an_anonymous_token(
    web: WebFake,
) -> None:
    """The lookup answers the Bearer challenge and reads the digest of the tag's manifest."""
    web.serve(RegistryFake({f"{IMAGE}:latest": DIGEST}))

    with http_client(EgressLevel.PUBLIC) as client:
        digest = tag_digest(f"{IMAGE}:latest", client, timeout=5.0)

    manifest = "https://ghcr.io/v2/example/devops-cli/service/manifests/latest"
    token = next(request for request in web.sent if request.url.path == "/token")
    assert digest == DIGEST
    assert [(r.method, str(r.url).split("?")[0]) for r in web.sent] == [
        ("HEAD", manifest),
        ("GET", "https://ghcr.io/token"),
        ("HEAD", manifest),
    ]
    assert parse_qs(token.url.query.decode()) == {
        "scope": ["repository:example/devops-cli/service:pull"],
        "service": ["ghcr.io"],
    }
    assert "application/vnd.oci.image.index.v1+json" in web.sent[-1].headers["accept"]


def test_a_registry_that_needs_credentials_raises_a_registry_read_error(
    web: WebFake,
) -> None:
    """A private image is a RegistryReadError that says why, and not a missing tag."""
    web.serve(RegistryFake({}, anonymous=False))

    with (
        http_client(EgressLevel.PUBLIC) as client,
        pytest.raises(RegistryReadError) as caught,
    ):
        tag_digest(f"{IMAGE}:latest", client, timeout=5.0)

    assert not isinstance(caught.value, RegistryTagNotFoundError)
    assert str(caught.value) == (
        f"The registry of {IMAGE}:latest gives no anonymous pull token, so reading it needs "
        "credentials (HTTP 401)."
    )
    assert caught.value.error_code == "DOCKER_REGISTRY_READ_ERROR"


def test_a_tag_that_the_registry_does_not_hold_raises_the_missing_tag_error(
    web: WebFake,
) -> None:
    """HTTP 404 is a RegistryTagNotFoundError. It is also a RegistryReadError, so a caller that
    catches the base keeps its handling."""
    web.serve(RegistryFake({}))

    with (
        http_client(EgressLevel.PUBLIC) as client,
        pytest.raises(RegistryReadError) as caught,
    ):
        tag_digest(f"{IMAGE}:missing", client, timeout=5.0)

    assert isinstance(caught.value, RegistryTagNotFoundError)
    assert str(caught.value) == f"The registry gives no manifest for {IMAGE}:missing (HTTP 404)."
    assert caught.value.error_code == "DOCKER_REGISTRY_TAG_NOT_FOUND"


def test_a_registry_status_other_than_404_is_not_a_missing_tag(web: WebFake) -> None:
    """HTTP 500 raises the base error: the tag may exist, so the caller cannot wait for it."""
    web.respond("HEAD", "https://ghcr.io/v2/example/devops-cli/service/manifests/v1", 500)

    with (
        http_client(EgressLevel.PUBLIC) as client,
        pytest.raises(RegistryReadError) as caught,
    ):
        tag_digest(f"{IMAGE}:v1", client, timeout=5.0)

    assert not isinstance(caught.value, RegistryTagNotFoundError)
    assert str(caught.value) == f"The registry gives no manifest for {IMAGE}:v1 (HTTP 500)."
    assert caught.value.error_code == "DOCKER_REGISTRY_READ_ERROR"


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        ("traefik", ("docker.io", "traefik")),
        ("valkey/valkey:9.1.2-alpine", ("docker.io", "valkey/valkey")),
        ("docker.io/traefik:v3.7.16", ("docker.io", "traefik")),
        ("index.docker.io/library/nginx:1.27", ("docker.io", "library/nginx")),
        ("ghcr.io/example/service", ("ghcr.io", "example/service")),
        (f"ghcr.io/example/service:latest@{DIGEST}", ("ghcr.io", "example/service")),
        (f"ghcr.io/example/service@{DIGEST}", ("ghcr.io", "example/service")),
        ("quay.io/argoproj/argocd:v3.5.3", ("quay.io", "argoproj/argocd")),
        (
            "nvcr.io/nvidia/k8s/dcgm-exporter:4.6.1-4.8.4-distroless",
            ("nvcr.io", "nvidia/k8s/dcgm-exporter"),
        ),
        ("localhost:5000/team/tool:1.0", ("localhost:5000", "team/tool")),
        ("192.0.2.10:5000/team/tool", ("192.0.2.10:5000", "team/tool")),
        ("gitea-http:3000/team/tool:1.0", ("gitea-http:3000", "team/tool")),
        (
            "registry.example.svc:5000/team/tool:1.0",
            ("registry.example.svc:5000", "team/tool"),
        ),
    ],
)
def test_an_image_reference_gives_its_registry_and_its_repository_without_tag_or_digest(
    image: str, expected: tuple[str, str]
) -> None:
    """The registry host and the repository are those of the Docker reference grammar, which the
    Docker SDK reads: a name with no registry, and `index.docker.io`, are `docker.io`."""
    assert image_reference(image) == expected


@pytest.mark.parametrize(
    ("reference", "path"),
    [
        ("nginx:1.27", "library/nginx/manifests/1.27"),
        ("valkey/valkey:9.1.2-alpine", "valkey/valkey/manifests/9.1.2-alpine"),
        ("docker.io/traefik:v3.7.16", "library/traefik/manifests/v3.7.16"),
        ("index.docker.io/library/nginx:1.27", "library/nginx/manifests/1.27"),
        (f"nginx:1.27@{DIGEST}", f"library/nginx/manifests/{DIGEST}"),
    ],
    ids=["one-component", "two-components", "hub-host", "hub-alias", "tag-and-digest"],
)
def test_a_docker_hub_name_is_read_at_the_hub_registry_host(
    web: WebFake, reference: str, path: str
) -> None:
    """Docker Hub answers a manifest at `registry-1.docker.io`, under `library/` for a name of
    one component. `docker.io` itself redirects to the web site. The first request has no token."""
    web.serve(
        RegistryFake(
            {f"registry-1.docker.io/{path.replace('/manifests/', ':')}": DIGEST},
            host="registry-1.docker.io",
        )
    )

    with http_client(EgressLevel.PUBLIC) as client:
        digest = tag_digest(reference, client, timeout=5.0)

    heads = [r for r in web.sent if r.method == "HEAD"]
    assert digest == DIGEST
    assert [(r.method, str(r.url)) for r in web.sent if r.url.path != "/token"] == [
        ("HEAD", f"https://registry-1.docker.io/v2/{path}"),
        ("HEAD", f"https://registry-1.docker.io/v2/{path}"),
    ]
    assert "authorization" not in heads[0].headers
    assert all(r.method == "HEAD" for r in web.sent if "/manifests/" in r.url.path)


def test_a_reference_with_a_digest_asks_for_the_manifest_of_the_digest(web: WebFake) -> None:
    """A pin by digest resolves by that digest, whatever tag it also names."""
    web.serve(RegistryFake({f"ghcr.io/example/app:{DIGEST}": DIGEST}))

    with http_client(EgressLevel.PUBLIC) as client:
        digest = tag_digest(f"ghcr.io/example/app:1.0@{DIGEST}", client, timeout=5.0)

    manifests = {str(r.url) for r in web.sent if r.url.path != "/token"}
    assert (digest, manifests) == (DIGEST, {f"https://ghcr.io/v2/example/app/manifests/{DIGEST}"})
