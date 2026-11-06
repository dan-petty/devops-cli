"""The digest a tag names in its registry, read with the OCI distribution API (#1997)."""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from devops_cli.docker.registry import TaggedImage, tag_digest, tagged_image
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
    ],
    ids=["ghcr", "registry-port", "localhost", "digest"],
)
def test_a_reference_that_names_its_registry_and_a_tag_splits(
    reference: str, expected: TaggedImage
) -> None:
    """The registry is the first component when it holds a dot or a port, or is `localhost`."""
    assert tagged_image(reference) == expected


@pytest.mark.parametrize(
    "reference",
    [
        "nginx:1.27",
        "library/nginx:1.27",
        IMAGE,
        "registry.example.com:5000/app",
        f"https://{IMAGE}:v1",
    ],
    ids=["no-registry", "hub-path", "no-tag", "port-no-tag", "scheme"],
)
def test_a_reference_without_a_registry_host_or_a_tag_is_refused(reference: str) -> None:
    """A reference whose registry or tag is not named gives no registry to ask."""
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
