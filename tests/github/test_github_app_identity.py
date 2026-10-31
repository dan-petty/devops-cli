"""A process whose environment holds a GitHub App's private key acts as that App (#1647, ADR 0015).

GitHub is faked at the HTTP edge (`github_api`), gh and git at `subprocess.run`, and the App's
private key is an RSA key each test run generates. Settings come from the `config` fixture.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from devops_cli.config.constants import CONST_GH_CLI, CONST_GITHUB_APP_PRIVATE_KEY_ENV
from devops_cli.config.settings import GitHubAppConfig, load_settings
from devops_cli.core.process import github_token, run_subprocess
from devops_cli.exceptions import ConfigurationError
from devops_cli.exceptions.git import GitHubUnauthenticatedError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session, reset_github_session
from tests.support.fakes.github import API, GitHubApiFake, github_json, quota_headers

APP_SETTINGS = {"app_id": 1001, "installation_id": 42, "slug": "devops-roadmap"}
BOT_LOGIN = "devops-roadmap[bot]"
APP_LOGGER = "devops_cli.github.app_installation"
MINT = "/app/installations/42/access_tokens"
REPO = "/repos/example-org/app"
# The permissions the roadmap jobs use (ADR 0015), which each token asks for.
ROADMAP_PERMISSIONS = {
    "issues": "write",
    "pull_requests": "write",
    "contents": "write",
    "checks": "read",
    "actions": "read",
    "metadata": "read",
}


@pytest.fixture(scope="module")
def app_key() -> rsa.RSAPrivateKey:
    """The App's private key, made for this run."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem(key: rsa.RSAPrivateKey) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture
def app_identity(
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    app_key: rsa.RSAPrivateKey,
) -> GitHubApiFake:
    """The process acts as App 1001, installation 42: its settings are set, and its environment
    holds the App's key, as the cluster's Secret gives it. The installation's quota is fresh."""
    config(service={"github_app": APP_SETTINGS})
    monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, _pem(app_key))
    reset_github_session()
    get_github_rate_limiter().update_quota(
        "core", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )
    return github_api


def _installation_token(
    token: str, expires_in: timedelta, permissions: dict[str, str] | None = None
) -> httpx2.Response:
    """GitHub's answer to the exchange: the token, when it expires and, when given, the
    permissions it carries."""
    expires_at = (datetime.now(UTC) + expires_in).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer: dict[str, Any] = {"token": token, "expires_at": expires_at}
    if permissions is not None:
        answer["permissions"] = permissions
    return github_json(answer, status=201)


def _finished(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout="", stderr="")


def test_the_app_mints_an_installation_token_and_a_new_one_before_it_expires(
    app_identity: GitHubApiFake, app_key: rsa.RSAPrivateKey
) -> None:
    """The first gh child gets a token minted with the App's JWT. That token expires within the
    renewal margin, so the next child gets a new one, which a third child reuses."""
    app_identity.route(
        "POST",
        MINT,
        _installation_token("ghs_first", timedelta(minutes=5)),
        _installation_token("ghs_second", timedelta(hours=1)),
    )
    with patch("subprocess.run", side_effect=_finished) as run:
        for _ in range(3):
            run_subprocess([CONST_GH_CLI, "issue", "list"])
    scheme, _, bearer = app_identity.sent[0].headers["authorization"].partition(" ")
    claims = jwt.decode(bearer, app_key.public_key(), algorithms=["RS256"])
    assert (
        [call.kwargs["env"].get("GH_TOKEN") for call in run.call_args_list],
        app_identity.requested,
        (scheme.lower(), claims["iss"]),
    ) == (
        ["ghs_first", "ghs_second", "ghs_second"],
        [f"POST {API}{MINT}"] * 2,
        ("bearer", "1001"),
    )


def test_the_token_request_asks_only_for_the_permissions_the_roadmap_jobs_use(
    app_identity: GitHubApiFake,
) -> None:
    """The installation may grant more, but the exchange's body names only the roadmap jobs'
    permissions, so the token carries no other one (#2473)."""
    app_identity.route("POST", MINT, _installation_token("ghs_first", timedelta(hours=1)))
    github_token()
    assert json.loads(app_identity.sent[0].content) == {"permissions": ROADMAP_PERMISSIONS}


def test_a_runner_job_asks_for_a_token_that_names_one_repository(
    app_identity: GitHubApiFake, config: Callable[..., Path]
) -> None:
    """A Job holds the setting `service.github_app.token_repository`, so its token names the
    repository by name and a step cannot push to another one (#2667)."""
    config(service={"github_app": {**APP_SETTINGS, "token_repository": "example-org/app"}})
    reset_github_session()
    app_identity.route("POST", MINT, _installation_token("ghs_first", timedelta(hours=1)))
    github_token()
    assert json.loads(app_identity.sent[0].content) == {
        "permissions": ROADMAP_PERMISSIONS,
        "repositories": ["app"],
    }


def test_the_variable_of_the_job_sets_the_repository_of_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY", "example-org/app")
    assert load_settings().service.github_app.token_repository == "example-org/app"


@pytest.mark.parametrize(
    "value",
    [
        "app",
        "a/b/c",
        "/app",
        "example-org/",
        "has space/app",
        "../..",
        "./app",
        "owner/.",
        "owner/..",
    ],
)
def test_a_token_repository_that_is_not_owner_slash_name_is_refused(value: str) -> None:
    with pytest.raises(ValidationError) as raised:
        GitHubAppConfig(token_repository=value)
    assert len(raised.value.errors()) > 0


def test_a_reply_that_grants_more_keeps_the_token_and_logs_only_the_permission_names(
    app_identity: GitHubApiFake, caplog: pytest.LogCaptureFixture
) -> None:
    """GitHub's reply names the token's permissions. A reply that grants one more is no error,
    and the log names the permissions but not their levels or the token."""
    granted = {**ROADMAP_PERMISSIONS, "administration": "write"}
    app_identity.route(
        "POST", MINT, _installation_token("ghs_first", timedelta(hours=1), permissions=granted)
    )
    with caplog.at_level(logging.INFO, logger=APP_LOGGER):
        token = github_token()
    assert token == "ghs_first"
    assert [record for record in caplog.record_tuples if record[0] == APP_LOGGER] == [
        (
            APP_LOGGER,
            logging.INFO,
            "GitHub App devops-roadmap[bot] has a new installation token with these permissions: "
            "actions, administration, checks, contents, issues, metadata, pull_requests",
        )
    ]


def test_an_installation_without_a_requested_permission_fails_naming_the_permissions(
    app_identity: GitHubApiFake,
) -> None:
    """GitHub refuses a permission that the installation does not grant with HTTP 422, and its
    reply does not say which one, so the error names each permission that the token asks for."""
    app_identity.route(
        "POST",
        MINT,
        github_json(
            {"message": "The permissions requested are not granted to this installation."},
            status=422,
        ),
    )
    with pytest.raises(GitHubUnauthenticatedError) as raised:
        github_token()
    assert raised.value.to_dict() == {
        "error_code": "GITHUB_UNAUTHENTICATED",
        "message": "GitHub App devops-roadmap[bot] has no installation token: GitHub refused "
        "POST /app/installations/42/access_tokens (HTTP 422): The permissions requested are not "
        "granted to this installation. The installation must grant each permission that the "
        "token asks for: actions (read), checks (read), contents (write), issues (write), "
        "metadata (read), pull_requests (write). Check the App ID, the installation ID and the "
        "private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY.",
        "exit_code": 1,
        "details": {"operation": "gh_auth_token"},
    }


def test_a_runner_job_whose_repository_the_installation_lacks_fails_naming_the_repository(
    app_identity: GitHubApiFake, config: Callable[..., Path]
) -> None:
    """GitHub refuses a token for a repository that the installation does not cover with HTTP
    422. The Job then fails in its pod, and the error names the repository, so a person who
    started the Job from a workstation sees why in its log (#2913)."""
    config(service={"github_app": {**APP_SETTINGS, "token_repository": "example-org/app"}})
    reset_github_session()
    app_identity.route(
        "POST",
        MINT,
        github_json(
            {
                "message": "There is at least one repository that does not exist or is not "
                "accessible to the parent installation."
            },
            status=422,
        ),
    )
    with pytest.raises(GitHubUnauthenticatedError) as raised:
        github_token()
    message = raised.value.message
    assert (
        "(HTTP 422): There is at least one repository that does not exist" in message,
        "The installation must include repository example-org/app" in message,
        "grant each permission that the token asks for" in message,
    ) == (True, True, True)


def test_the_apps_login_is_its_bot_and_no_get_user_is_sent(app_identity: GitHubApiFake) -> None:
    """The App's login comes from its slug; the session asks GitHub nothing for it."""
    assert (get_github_session().login, app_identity.requested) == (BOT_LOGIN, [])


def test_every_installation_token_keeps_the_installations_session_and_ledger(
    app_identity: GitHubApiFake,
) -> None:
    """A new token keeps the session and the quota ledger: a ledger keyed by the token would hold
    no quota for the second token, and its pacing would ask gh, which the fake refuses."""
    app_identity.route(
        "POST",
        MINT,
        _installation_token("ghs_first", timedelta(minutes=5)),
        _installation_token("ghs_second", timedelta(hours=1)),
    )
    app_identity.route(
        "GET",
        REPO,
        github_json({"id": 1}, headers=quota_headers(4999)),
        github_json({"id": 1}, headers=quota_headers(4998)),
    )
    session = get_github_session()
    session.rest("GET", REPO)
    session.rest("GET", REPO)
    reads = [r for r in app_identity.sent if r.method == "GET"]
    assert (
        [read.headers["authorization"] for read in reads],
        get_github_session() is session,
        get_github_rate_limiter().get_quota("core").remaining,
    ) == (["token ghs_first", "token ghs_second"], True, 4998)


def test_the_apps_commit_email_carries_its_bots_account_id(app_identity: GitHubApiFake) -> None:
    """GitHub links a bot's commits to it through `<id>+<login>@users.noreply.github.com`."""
    app_identity.route("POST", MINT, _installation_token("ghs_first", timedelta(hours=1)))
    app_identity.route(
        "GET", "/users/devops-roadmap%5Bbot%5D", github_json({"id": 7, "login": BOT_LOGIN})
    )
    assert get_github_session().commit_email == f"7+{BOT_LOGIN}@users.noreply.github.com"


def test_without_the_key_in_its_environment_the_process_keeps_ghs_login(
    github_api: GitHubApiFake, config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A workstation holds the App's settings to render the ConfigMap, and its key only in the
    keyring, so it acts as the person's gh login and mints nothing."""
    config(service={"github_app": APP_SETTINGS})
    monkeypatch.delenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, raising=False)
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    assert (get_github_session().login, github_api.requested) == (
        "octocat",
        [f"GET {API}/user"],
    )


def test_the_key_without_the_apps_settings_fails_naming_them(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch, app_key: rsa.RSAPrivateKey
) -> None:
    """A key in the environment makes the process the App, so a missing setting fails closed."""
    config(service={"github_app": {"slug": "devops-roadmap"}})
    monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, _pem(app_key))
    reset_github_session()
    with pytest.raises(ConfigurationError) as raised:
        github_token()
    assert raised.value.to_dict() == {
        "error_code": "CONFIGURATION_ERROR",
        "message": "The environment holds DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY, so this "
        "process acts as a GitHub App, but these settings are not set: service.github_app.app_id, "
        "service.github_app.installation_id. Set them with 'devops config set'.",
        "exit_code": 1,
        "details": {"key": "service.github_app.app_id"},
    }


def test_a_refused_exchange_raises_the_unauthenticated_error_with_githubs_status(
    app_identity: GitHubApiFake,
) -> None:
    """GitHub's refusal of the JWT leaves the process without a token, and says why."""
    app_identity.route(
        "POST",
        MINT,
        github_json({"message": "A JSON web token could not be decoded"}, status=401),
    )
    with pytest.raises(GitHubUnauthenticatedError) as raised:
        github_token()
    assert (BOT_LOGIN in raised.value.message, "401" in raised.value.message) == (True, True)


def test_a_key_that_is_no_rsa_key_fails_before_any_request(
    app_identity: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A key that cannot sign a JWT sends nothing, and the error never quotes the key."""
    monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, "not-a-pem-key")
    with pytest.raises(GitHubUnauthenticatedError) as raised:
        github_token()
    assert raised.value.to_dict() == {
        "error_code": "GITHUB_UNAUTHENTICATED",
        "message": "GitHub App devops-roadmap[bot] has no installation token: the private key is "
        "not an RSA private key in PEM form. Check the App ID, the installation ID and the "
        "private key in DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY.",
        "exit_code": 1,
        "details": {"operation": "gh_auth_token"},
    }
    assert app_identity.requested == []
