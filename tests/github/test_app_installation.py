"""The read of an App installation on one repository, signed with the JWT of the App (#6773)."""

from __future__ import annotations

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from devops_cli.exceptions import DevOpsCLIError
from devops_cli.github.app_installation import GitHubApp, repository_installed
from tests.support.fakes.github import GitHubApiFake, github_json

REPO = "example-org/app"


@pytest.fixture(scope="module")
def app_key() -> rsa.RSAPrivateKey:
    """The private key of the App, made for this run."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _app(key: rsa.RSAPrivateKey) -> GitHubApp:
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return GitHubApp(app_id=1001, installation_id=42, slug="example-app", private_key=pem)


@pytest.mark.parametrize(("status", "installed"), [(200, True), (404, False)])
def test_the_installation_read_sends_one_get_signed_by_the_app(
    github_api: GitHubApiFake, app_key: rsa.RSAPrivateKey, status: int, installed: bool
) -> None:
    payload = {"id": 42, "app_slug": "example-app"} if status == 200 else {"message": "Not Found"}
    github_api.route("GET", f"/repos/{REPO}/installation", github_json(payload, status=status))

    assert repository_installed(_app(app_key), REPO) is installed

    assert github_api.requested == [f"GET https://api.github.com/repos/{REPO}/installation"]
    scheme, _, token = github_api.sent[0].headers["authorization"].partition(" ")
    claims = jwt.decode(token, app_key.public_key(), algorithms=["RS256"])
    assert (scheme.lower(), claims["iss"]) == ("bearer", "1001")


def test_an_installation_read_that_github_refuses_raises(
    github_api: GitHubApiFake, app_key: rsa.RSAPrivateKey
) -> None:
    github_api.route(
        "GET",
        f"/repos/{REPO}/installation",
        github_json({"message": "A JSON web token could not be decoded"}, status=401),
    )

    with pytest.raises(DevOpsCLIError) as raised:
        repository_installed(_app(app_key), REPO)

    assert raised.value.error_code == "GITHUB_UNAUTHENTICATED"


def test_a_key_that_is_no_rsa_key_reads_nothing(github_api: GitHubApiFake) -> None:
    app = GitHubApp(app_id=1001, installation_id=42, slug="example-app", private_key="not a key")

    with pytest.raises(DevOpsCLIError) as raised:
        repository_installed(app, REPO)

    assert (raised.value.error_code, github_api.requested) == ("CONFIGURATION_ERROR", [])
