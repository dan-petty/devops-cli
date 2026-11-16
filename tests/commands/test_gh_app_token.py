"""`devops gh app-token` writes an installation token of the Renovate GitHub App to a file (#4897).

GitHub is faked at the HTTP edge (`github_api`) and the keyring at its edge (`keyring_store`).
The App's private key is an RSA key that each test run makes. The init container of the Renovate
CronJob gets the three settings as variables from Secret `devops/renovate`, so most tests set
them the same way.
"""

from __future__ import annotations

import json
import logging
import stat
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from tests.support.fakes.github import API, GitHubApiFake, github_json
from tests.support.fakes.keyring import FakeKeyring

APP_ID = "1001"
# A Client ID in the form that GitHub gives a new App. It is no real App's.
CLIENT_ID = "Iv23liExampleClient01"
INSTALLATION_ID = "42"
MINT = f"/app/installations/{INSTALLATION_ID}/access_tokens"
TOKEN = "ghs_renovate0123456789abcdefghijklmnopqrstuv"
ID_VARIABLE = "DEVOPS_CLI_RENOVATE_GITHUB_APP_ID"
INSTALLATION_VARIABLE = "DEVOPS_CLI_RENOVATE_GITHUB_APP_INSTALLATION_ID"
KEY_VARIABLE = "DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY"
# The repository permissions that Renovate needs (#4893 owner step 1), and no other one.
RENOVATE_PERMISSIONS = {
    "administration": "read",
    "checks": "write",
    "statuses": "write",
    "contents": "write",
    "vulnerability_alerts": "read",
    "issues": "write",
    "metadata": "read",
    "pull_requests": "write",
    "workflows": "write",
}


@pytest.fixture(scope="module")
def app_key() -> rsa.RSAPrivateKey:
    """The Renovate App's private key, made for this run."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem(key: rsa.RSAPrivateKey) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture
def renovate_app(
    github_api: GitHubApiFake,
    keyring_store: FakeKeyring,
    monkeypatch: pytest.MonkeyPatch,
    app_key: rsa.RSAPrivateKey,
) -> Iterator[GitHubApiFake]:
    """The environment holds the three settings of the Renovate App, as the init container gets
    them from Secret `devops/renovate`. The keyring is empty, as in a pod."""
    monkeypatch.setenv(ID_VARIABLE, APP_ID)
    monkeypatch.setenv(INSTALLATION_VARIABLE, INSTALLATION_ID)
    monkeypatch.setenv(KEY_VARIABLE, _pem(app_key))
    yield github_api


def _minted(token: str = TOKEN) -> Any:
    """GitHub's answer to the exchange: a token that GitHub ends after one hour."""
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = {"token": token, "expires_at": expires_at, "permissions": RENOVATE_PERMISSIONS}
    return github_json(answer, status=201)


@pytest.mark.parametrize(
    ("variable", "in_file", "issuer"),
    [
        (APP_ID, None, APP_ID),
        (CLIENT_ID, None, CLIENT_ID),
        (None, int(APP_ID), APP_ID),
    ],
    ids=["app-id-variable", "client-id-variable", "app-id-in-config-file"],
)
def test_the_token_request_asks_for_exactly_the_renovate_permissions(
    renovate_app: GitHubApiFake,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    app_key: rsa.RSAPrivateKey,
    variable: str | None,
    in_file: int | None,
    issuer: str,
) -> None:
    """The body names the 9 permissions of Renovate and no other one. The App's key signs the
    JWT of the request, and its issuer is the setting as given: GitHub takes the App ID or the
    App's Client ID there."""
    if variable is None:
        monkeypatch.delenv(ID_VARIABLE)
        config(renovate={"github_app_id": in_file})
    else:
        monkeypatch.setenv(ID_VARIABLE, variable)
    renovate_app.route("POST", MINT, _minted())

    result = cli("gh", "app-token", "--app", "renovate", "--write", str(tmp_path / "token"))

    scheme, _, bearer = renovate_app.sent[0].headers["authorization"].partition(" ")
    claims = jwt.decode(bearer, app_key.public_key(), algorithms=["RS256"])
    assert (
        result.exit_code,
        renovate_app.requested,
        json.loads(renovate_app.sent[0].content),
        (scheme.lower(), claims["iss"]),
    ) == (
        0,
        [f"POST {API}{MINT}"],
        {"permissions": RENOVATE_PERMISSIONS},
        ("bearer", issuer),
    ), result.output


def test_the_token_file_holds_only_the_token_with_mode_0600(
    renovate_app: GitHubApiFake, cli: Callable[..., Any], tmp_path: Path
) -> None:
    """A file that other users can read is replaced: the new file has mode 0600 and holds the
    token with no newline, so `config.js` can read it as is."""
    renovate_app.route("POST", MINT, _minted())
    token_file = tmp_path / "token"
    token_file.write_text("old", encoding="utf-8")
    token_file.chmod(0o644)

    result = cli("gh", "app-token", "--app", "renovate", "--write", str(token_file))

    assert (
        result.exit_code,
        token_file.read_text(encoding="utf-8"),
        stat.S_IMODE(token_file.stat().st_mode),
    ) == (0, TOKEN, 0o600), result.output


def test_the_token_is_in_no_output_or_log_line(
    renovate_app: GitHubApiFake,
    cli: Callable[..., Any],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The command names the file and when GitHub ends the token, and never the token."""
    renovate_app.route("POST", MINT, _minted())
    caplog.set_level(logging.DEBUG)
    token_file = tmp_path / "token"

    result = cli("gh", "app-token", "--app", "renovate", "--write", str(token_file))

    logged = [record.getMessage() for record in caplog.records]
    assert (
        result.exit_code,
        TOKEN in result.stdout,
        TOKEN in result.stderr,
        [line for line in logged if TOKEN in line],
        str(token_file) in result.output,
        "GitHub ends the token at" in result.output,
    ) == (0, False, False, [], True, True), result.output


@pytest.mark.parametrize("flag_first", [False, True], ids=["command-flag", "global-flag"])
def test_the_dry_run_sends_no_request_and_shows_the_token_as_a_placeholder(
    renovate_app: GitHubApiFake,
    keyring_store: FakeKeyring,
    cli: Callable[..., Any],
    tmp_path: Path,
    flag_first: bool,
) -> None:
    """The dry run sends nothing, reads no keyring and writes no file. It shows the request with
    its body, and the token that a run writes as a placeholder."""
    token_file = tmp_path / "token"
    command = ["gh", "app-token", "--app", "renovate", "--write", str(token_file)]
    argv = ["--dry-run", *command] if flag_first else [*command, "--dry-run"]

    result = cli(argv)

    assert (
        result.exit_code,
        renovate_app.requested,
        keyring_store.reads,
        token_file.exists(),
        f"POST {API}{MINT}" in result.output,
        '"vulnerability_alerts": "read"' in result.output,
        f"<installation-token> to {token_file} with mode 0600" in result.output,
    ) == (0, [], [], False, True, True, True), result.output


@pytest.mark.parametrize(
    ("unset", "setting"),
    [
        (ID_VARIABLE, "renovate.github_app_id"),
        (INSTALLATION_VARIABLE, "renovate.github_app_installation_id"),
        (KEY_VARIABLE, "renovate.github_app_private_key"),
    ],
)
def test_a_missing_setting_fails_naming_the_setting(
    renovate_app: GitHubApiFake,
    cli: Callable[..., Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unset: str,
    setting: str,
) -> None:
    """Each setting that is not set is named with its variable, and nothing is sent or written."""
    monkeypatch.delenv(unset)
    token_file = tmp_path / "token"

    result = cli("gh", "app-token", "--app", "renovate", "--write", str(token_file))

    assert (
        result.exit_code,
        f"these settings are not set: {setting}." in result.output,
        unset in result.output,
        renovate_app.requested,
        token_file.exists(),
    ) == (1, True, True, [], False), result.output


def test_a_refused_permission_names_each_permission_and_writes_no_file(
    renovate_app: GitHubApiFake, cli: Callable[..., Any], tmp_path: Path
) -> None:
    """GitHub refuses with HTTP 422 a permission that the installation does not grant, and its
    reply does not say which. The error names each permission that the token asks for."""
    renovate_app.route(
        "POST", MINT, github_json({"message": "There is at least one permission"}, status=422)
    )
    token_file = tmp_path / "token"

    result = cli("gh", "app-token", "--app", "renovate", "--write", str(token_file))

    assert (
        result.exit_code,
        "GitHub App dan-petty-renovate[bot] has no installation token" in result.output,
        "vulnerability_alerts (read)" in result.output,
        token_file.exists(),
    ) == (1, True, True, False), result.output
