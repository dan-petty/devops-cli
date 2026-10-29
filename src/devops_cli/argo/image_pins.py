"""The images an Argo CD Application pins to a digest, and whether each tag still names it (#1997).

Argo CD Image Updater keeps the `devops` Application on the digest that `service:latest` names by
writing `<image>:<tag>@<digest>` into `spec.source.kustomize.images`. When it stops, the
Application stays on an old digest and no condition says so. The check reads each pin with a tag
and a digest, asks the image's registry which digest the tag names now, and reports each pin that
differs or that the registry does not give.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx2

from devops_cli.docker.registry import tag_digest
from devops_cli.exceptions.docker import RegistryReadError
from devops_cli.exceptions.security import SSRFBlockedError


@dataclass(frozen=True)
class ImagePin:
    """An image reference with a tag, and the digest the Application pins it to."""

    image: str
    digest: str


@dataclass(frozen=True)
class PinCheck:
    """One pin, the digest its tag names in the registry now, or why the registry gave none."""

    pin: ImagePin
    current: str | None = None
    error: str | None = None

    @property
    def in_step(self) -> bool:
        """Whether the Application runs the digest that its tag names now."""
        return self.error is None and self.current == self.pin.digest


def _pin(entry: str) -> ImagePin | None:
    # A kustomize image override is `[<name>=]<new name>[:<tag>][@<digest>]`, and a tag is in the
    # last path component, after its `:`.
    override = entry.rpartition("=")[2]
    reference, _, digest = override.partition("@")
    if not digest or ":" not in reference.rpartition("/")[2]:
        return None
    return ImagePin(image=reference, digest=digest)


def kustomize_image_pins(application: Mapping[str, Any]) -> list[ImagePin]:
    """Return the kustomize images of `application` that pin a tag to a digest.

    The images of `spec.source` and of each entry of `spec.sources` count. An entry with only a
    tag or only a digest pins no moving tag, so it is not a pin.
    """
    spec = application.get("spec")
    if not isinstance(spec, Mapping):
        return []
    sources = [spec.get("source"), *(spec.get("sources") or [])]
    pins: list[ImagePin] = []
    for source in sources:
        kustomize = source.get("kustomize") if isinstance(source, Mapping) else None
        images = kustomize.get("images") if isinstance(kustomize, Mapping) else None
        for entry in images or []:
            if (pin := _pin(str(entry))) is not None:
                pins.append(pin)
    return pins


def check_pins(pins: list[ImagePin], client: httpx2.Client, *, timeout: float) -> list[PinCheck]:
    """Ask each pin's registry which digest its tag names now.

    A registry that needs credentials, does not answer, or is on an address the client's egress
    level refuses gives a check with its error, not an exception: the other pins are still read.
    """
    checks: list[PinCheck] = []
    for pin in pins:
        try:
            checks.append(PinCheck(pin, current=tag_digest(pin.image, client, timeout=timeout)))
        except (RegistryReadError, SSRFBlockedError, httpx2.HTTPError) as exc:
            checks.append(PinCheck(pin, error=str(exc)))
    return checks
