"""The images an Argo CD Application pins to a digest, and whether each tag still names it (#1997)."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.argo.image_pins import ImagePin, PinCheck, check_pins, kustomize_image_pins
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
from tests.support.fakes.oci_registry import RegistryFake
from tests.web_fakes import StubWeb

IMAGE = "ghcr.io/example/devops-cli/service"
PINNED = "sha256:" + "a" * 64
MOVED = "sha256:" + "b" * 64


def _application(images: list[str] | None, *, sources: bool = False) -> dict[str, Any]:
    source: dict[str, Any] = {"repoURL": "https://github.com/example/repo", "path": "k8s/devops"}
    if images is not None:
        source["kustomize"] = {"images": images}
    if sources:
        return {"spec": {"sources": [{"chart": "c"}, source]}}
    return {"spec": {"source": source}}


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        ([f"{IMAGE}:latest@{PINNED}"], [ImagePin(f"{IMAGE}:latest", PINNED)]),
        ([f"old/name={IMAGE}:v1@{PINNED}"], [ImagePin(f"{IMAGE}:v1", PINNED)]),
        ([f"localhost:5000/app:v1@{PINNED}"], [ImagePin("localhost:5000/app:v1", PINNED)]),
        ([f"{IMAGE}:latest"], []),
        ([f"{IMAGE}@{PINNED}"], []),
        ([f"localhost:5000/app@{PINNED}"], []),
        ([], []),
    ],
    ids=[
        "tag-and-digest",
        "renamed",
        "registry-port",
        "tag-only",
        "digest-only",
        "port-digest-only",
        "none",
    ],
)
def test_a_pin_is_a_kustomize_image_that_names_a_tag_and_a_digest(
    entries: list[str], expected: list[ImagePin]
) -> None:
    """Only an entry with a tag and a digest pins a moving tag to one digest."""
    assert kustomize_image_pins(_application(entries)) == expected


def test_a_multi_source_application_gives_the_pins_of_its_sources() -> None:
    """An Application with `spec.sources` has its kustomize images in one of its sources."""
    item = _application([f"{IMAGE}:latest@{PINNED}"], sources=True)

    assert kustomize_image_pins(item) == [ImagePin(f"{IMAGE}:latest", PINNED)]


def test_an_application_with_no_kustomize_images_has_no_pins() -> None:
    """A source with no kustomize section pins nothing."""
    assert kustomize_image_pins(_application(None)) == []


def test_each_pin_is_checked_against_the_digest_its_tag_names_now(stub_web: StubWeb) -> None:
    """A pin in step, a moved tag and a tag the registry lacks each give their own check."""
    stub_web.serve(RegistryFake({f"{IMAGE}:latest": PINNED, f"{IMAGE}:next": MOVED}))
    pins = [
        ImagePin(f"{IMAGE}:latest", PINNED),
        ImagePin(f"{IMAGE}:next", PINNED),
        ImagePin(f"{IMAGE}:gone", PINNED),
    ]

    with new_http_client(level=EgressLevel.PUBLIC) as client:
        checks = check_pins(pins, client, timeout=5.0)

    assert checks == [
        PinCheck(pins[0], current=PINNED),
        PinCheck(pins[1], current=MOVED),
        PinCheck(pins[2], error=f"The registry gives no manifest for {IMAGE}:gone (HTTP 404)."),
    ]
    assert [check.in_step for check in checks] == [True, False, False]
