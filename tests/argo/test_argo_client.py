"""Where Argo CD is and how a request to it authenticates.

The settings come from the `config` fixture and the token from the keyring fake. The `web` fixture
answers below the HTTP entry point and vets each host at the level of the client, so a test reads
the requests that reached the fake and patches no name.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.argo.client import ArgoCDEndpoint, resolve_argocd_endpoint
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import SSRFBlockedError
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.http.egress import EgressLevel
from tests.support.fakes.http import WebFake
from tests.support.fakes.keyring import FakeKeyring

pytestmark = pytest.mark.usefixtures("web")


def _endpoint(config: Callable[..., Path], url: str | None, **sections: object) -> ArgoCDEndpoint:
    """Resolve the endpoint of an `argocd.url` setting."""
    config(argocd={"url": url}, **sections)
    return resolve_argocd_endpoint(load_settings())


def test_the_endpoint_reads_the_url_without_a_trailing_slash(
    config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """A URL that ends in a slash gives the base that the paths of the API follow."""
    endpoint = _endpoint(config, "https://example.com/argo/")

    assert endpoint.base_url == "https://example.com/argo"


def test_a_stored_token_becomes_a_bearer_header(
    config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """The token of the keyring is sent as a bearer token, and the body is declared JSON."""
    keyring_store.values["argocd_token"] = "test-token"

    endpoint = _endpoint(config, "https://example.com")

    assert endpoint.headers == {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-token",
    }


def test_a_missing_token_sends_no_authorization(
    config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """With no token and no admin password there is nothing to send, so the header is absent."""
    endpoint = _endpoint(config, "https://example.com")

    assert endpoint.headers == {"Content-Type": "application/json"}


def test_a_masked_token_is_no_token(
    config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """A token that is only asterisks is a masked display value, never a credential."""
    keyring_store.values["argocd_token"] = "******"

    endpoint = _endpoint(config, "https://example.com")

    assert "Authorization" not in endpoint.headers


def test_a_missing_url_raises_an_error_that_names_the_setting(
    config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """With no `argocd.url` the error says which setting to set."""
    with pytest.raises(ConfigurationError, match=r"argocd\.url"):
        _endpoint(config, None)


def test_an_address_the_client_cannot_dial_is_refused_before_a_token_is_read(
    config: Callable[..., Path], keyring_store: FakeKeyring
) -> None:
    """A `k8s://` address raises the error that names the setting, and no secret is read."""
    with pytest.raises(ConfigurationError, match=r"argocd\.url"):
        _endpoint(config, "k8s://argocd/argocd-server:443")

    assert keyring_store.secret_reads() == set()


def test_the_client_dials_the_configured_level(
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
    monkeypatch: pytest.MonkeyPatch,
    web: WebFake,
) -> None:
    """A private address without `ai.allow_private_network` is refused, and nothing is sent."""
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
    endpoint = _endpoint(config, "http://10.0.0.1:8080", ai={"allow_private_network": False})

    with (
        pytest.raises(SSRFBlockedError, match="egress level refuses"),
        endpoint.client() as client,
    ):
        client.get(f"{endpoint.base_url}/api/v1/applications")

    assert (endpoint.level, web.recorded) == (EgressLevel.LOOPBACK, [])
