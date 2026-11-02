"""`devops argo cd apps status` reports the images an Application pins against their registry (#1997).

The Argo CD API and the OCI registry are faked at the HTTP edge with `stub_web`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes.oci_registry import RegistryFake
from tests.web_fakes import StubWeb

ARGOCD = "https://argocd.example.com"
APPLICATION = f"{ARGOCD}/api/v1/applications/devops"
IMAGE = "ghcr.io/example/devops-cli/service"
PINNED = "sha256:" + "a" * 64
MOVED = "sha256:" + "b" * 64


def _application(images: list[str] | None) -> dict[str, Any]:
    source: dict[str, Any] = {"repoURL": "https://github.com/example/repo", "path": "k8s/devops"}
    if images is not None:
        source["kustomize"] = {"images": images}
    return {
        "metadata": {"name": "devops"},
        "spec": {"project": "homelab", "source": source},
        "status": {
            "sync": {"status": "Synced", "revision": "0123456789abcdef"},
            "health": {"status": "Healthy"},
        },
    }


@pytest.fixture(autouse=True)
def argocd(config: Callable[..., Path], keyring_store: Any) -> None:
    """Point devops-cli at a fake Argo CD with a stored token, so no token is minted."""
    config(argocd={"url": ARGOCD})
    keyring_store.values["argocd_token"] = "argocd-api-token"


def test_status_exits_1_when_the_registry_moved_a_pinned_tag(
    cli: Callable[..., Any], stub_web: StubWeb
) -> None:
    """A pin whose tag now names another digest is reported with both digests."""
    stub_web.respond("GET", APPLICATION, 200, _application([f"{IMAGE}:latest@{PINNED}"]))
    stub_web.serve(RegistryFake({f"{IMAGE}:latest": MOVED}))

    result = cli("argo", "cd", "apps", "status", "devops")

    assert result.exit_code == 1
    assert (
        f"{IMAGE}:latest pins sha256:aaaaaaaaaaaa, but the tag names sha256:bbbbbbbbbbbb now"
        in result.output
    )


def test_status_exits_0_when_each_pin_is_the_digest_of_its_tag(
    cli: Callable[..., Any], stub_web: StubWeb
) -> None:
    """A pin that names its tag's current digest is in step."""
    stub_web.respond("GET", APPLICATION, 200, _application([f"{IMAGE}:latest@{PINNED}"]))
    stub_web.serve(RegistryFake({f"{IMAGE}:latest": PINNED}))

    result = cli("argo", "cd", "apps", "status", "devops")

    assert result.exit_code == 0
    assert f"{IMAGE}:latest at sha256:aaaaaaaaaaaa" in result.output


def test_status_of_an_application_with_no_pins_reads_only_argo_cd(
    cli: Callable[..., Any], stub_web: StubWeb
) -> None:
    """With no pinned image, the command sends no registry request."""
    stub_web.respond("GET", APPLICATION, 200, _application(None))

    result = cli("argo", "cd", "apps", "status", "devops")

    assert result.exit_code == 0
    assert stub_web.requested == [APPLICATION]


def test_status_exits_1_when_the_registry_gives_no_digest(
    cli: Callable[..., Any], stub_web: StubWeb
) -> None:
    """A pin that the registry does not give a digest for is reported, not taken as in step."""
    stub_web.respond("GET", APPLICATION, 200, _application([f"{IMAGE}:latest@{PINNED}"]))
    stub_web.serve(RegistryFake({}, anonymous=False))

    result = cli("argo", "cd", "apps", "status", "devops")

    assert result.exit_code == 1
    assert "gives no anonymous pull token" in result.output


def test_status_exits_1_when_argo_cd_refuses_the_read(
    cli: Callable[..., Any], stub_web: StubWeb
) -> None:
    """A status that shows an error exits 1, so a script can tell it from a healthy status."""
    stub_web.respond("GET", APPLICATION, 401, {"error": "invalid session"})

    result = cli("argo", "cd", "apps", "status", "devops")

    assert result.exit_code == 1
    assert "401" in result.output


def test_status_dry_run_sends_no_request(cli: Callable[..., Any], stub_web: StubWeb) -> None:
    """`--dry-run` names the action and reads neither Argo CD nor a registry."""
    result = cli("argo", "cd", "apps", "status", "devops", "--dry-run")

    assert result.exit_code == 0
    assert "Plan for Argo CD application 'devops' status" in result.output
    assert stub_web.sent == []


def _refusing_argocd(stub_web: StubWeb) -> None:
    """Answer HTTP 401 to the stored token, the token `fresh` to the session request, and the
    application to a read with `fresh`."""
    import httpx2

    def server(request: httpx2.Request) -> httpx2.Response | None:
        if str(request.url) == f"{ARGOCD}/api/v1/session":
            return httpx2.Response(200, json={"token": "fresh"})
        if str(request.url) != APPLICATION:
            return None
        if request.headers.get("Authorization") == "Bearer fresh":
            return httpx2.Response(200, json=_application(None))
        return httpx2.Response(401, json={"error": "invalid session"})

    stub_web.serve(server)


def test_status_replaces_a_refused_token_and_shows_the_application(
    cli: Callable[..., Any], stub_web: StubWeb, keyring_store: Any
) -> None:
    """Old vs new (#2576): a 401 with the admin password stored mints a token and reads again."""
    keyring_store.values["argocd_password"] = "admin-pw"
    _refusing_argocd(stub_web)

    result = cli("argo", "cd", "apps", "status", "devops")

    assert (result.exit_code, "Healthy" in result.output) == (0, True)
    assert keyring_store.values["argocd_token"] == "fresh"


def test_status_with_a_refused_token_and_no_password_names_the_setting(
    cli: Callable[..., Any], stub_web: StubWeb
) -> None:
    """The panel tells how to set the token, and the status exits 1."""
    _refusing_argocd(stub_web)

    result = cli("argo", "cd", "apps", "status", "devops")

    assert (
        result.exit_code,
        "argocd.token" in result.output,
        "sync-secrets" in result.output,
    ) == (1, True, True)
