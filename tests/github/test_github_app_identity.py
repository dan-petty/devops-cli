"""A process whose environment holds a GitHub App's private key acts as that App (#1647, ADR 0015).

GitHub is faked at the HTTP edge (`github_api`), gh and git at the process edge
(`faked_children`), and the App's private key is an RSA key each test run generates. Settings come
from the `config` fixture.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from devops_cli.commands.research import _optional_github_token
from devops_cli.config.constants import CONST_GH_CLI, CONST_GITHUB_APP_PRIVATE_KEY_ENV
from devops_cli.config.settings import GitHubAppConfig, load_settings
from devops_cli.core.process import github_token, run_subprocess
from devops_cli.exceptions import ConfigurationError
from devops_cli.exceptions.git import (
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session, reset_github_session
from devops_cli.roadmap.run import identity_refused
from devops_cli.server.service import RoundPause
from devops_cli.telemetry.instruments import GITHUB_REQUESTS_TOTAL
from tests.support.fakes.github import API, GitHubApiFake, github_json, quota_headers
from tests.support.fakes.otlp import FakeCollector
from tests.support.github_identity import faked_children, token_seen

APP_SETTINGS = {"app_id": 1001, "installation_id": 42, "slug": "devops-roadmap"}
BOT_LOGIN = "devops-roadmap[bot]"
APP_LOGGER = "devops_cli.github.app_installation"
MINT = "/app/installations/42/access_tokens"
REPO = "/repos/example-org/app"
# The permissions the roadmap jobs use (ADR 0015), which the token of a runner Job asks for.
JOB_PERMISSIONS = {
    "issues": "write",
    "pull_requests": "write",
    "contents": "write",
    "checks": "read",
    "actions": "read",
    "metadata": "read",
    "workflows": "write",
}
# A token that names no repository, as the Service mints, also asks for those of the metrics row.
ROADMAP_PERMISSIONS = {**JOB_PERMISSIONS, "repository_hooks": "read", "administration": "read"}
# The drift check, the nightly Job of `devops repos onboard --all --plan` (#6783), asks for the
# permissions of the GETs of its rows. GitHub gives the merge settings only with Contents write, and
# the bypass actors of a ruleset only with Administration write (#6888).
DRIFT_PERMISSIONS = {
    "actions": "read",
    "administration": "write",
    "checks": "read",
    "contents": "write",
    "environments": "read",
    "issues": "read",
    "metadata": "read",
    "pull_requests": "read",
    "secrets": "read",
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
    tokens: list[str | None] = []

    def child(*_args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        tokens.append(token_seen(kwargs["env"]))
        return _finished()

    with faked_children(side_effect=child):
        for _ in range(3):
            run_subprocess([CONST_GH_CLI, "issue", "list"])
    scheme, _, bearer = app_identity.sent[0].headers["authorization"].partition(" ")
    claims = jwt.decode(bearer, app_key.public_key(), algorithms=["RS256"])
    assert (
        tokens,
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


def test_a_runner_job_asks_for_a_token_that_names_one_repository_and_no_metrics_permission(
    app_identity: GitHubApiFake, config: Callable[..., Path]
) -> None:
    """A Job holds the setting `service.github_app.token_repository`, so its token names the
    repository by name and a step cannot push to another one (#2667). No step reads a hook or the
    traffic, so the token asks for neither `repository_hooks` nor `administration`, and a step
    cannot read the hook URLs, the deliveries or the settings of the repository (#5058)."""
    config(service={"github_app": {**APP_SETTINGS, "token_repository": "example-org/app"}})
    reset_github_session()
    app_identity.route("POST", MINT, _installation_token("ghs_first", timedelta(hours=1)))
    github_token()
    assert json.loads(app_identity.sent[0].content) == {
        "permissions": JOB_PERMISSIONS,
        "repositories": ["app"],
    }


def test_the_drift_check_asks_for_its_own_permissions(
    app_identity: GitHubApiFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The drift Job sets `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK`, so its token asks for the
    drift set only: Contents write and Administration write, and read for each other permission
    (#6783, #6888)."""
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK", "true")
    reset_github_session()
    app_identity.route("POST", MINT, _installation_token("ghs_first", timedelta(hours=1)))
    github_token()
    assert json.loads(app_identity.sent[0].content) == {"permissions": DRIFT_PERMISSIONS}


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
    and the log names the permissions but not their levels or the token. The token asks for no
    `pages`, so the reply grants one more (#4757)."""
    granted = {**ROADMAP_PERMISSIONS, "pages": "write"}
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
            "actions, administration, checks, contents, issues, metadata, pages, pull_requests, "
            "repository_hooks, workflows",
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
        "token asks for: actions (read), administration (read), checks (read), contents (write), "
        "issues (write), metadata (read), pull_requests (write), repository_hooks (read), "
        "workflows (write). Check the App ID, the installation ID and the private key in "
        "DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY.",
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
        "repository_hooks" in message or "administration" in message,
    ) == (True, True, True, False)


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
    assert raised.value.to_dict() == {
        "error_code": "GITHUB_UNAUTHENTICATED",
        "message": "GitHub App devops-roadmap[bot] has no installation token: GitHub refused the "
        "App's JWT for POST /app/installations/42/access_tokens (HTTP 401): A JSON web token could "
        "not be decoded. Check the App ID, the installation ID and the private key in "
        "DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY.",
        "exit_code": 1,
        "details": {"operation": "gh_auth_token"},
    }


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


@pytest.mark.parametrize(
    ("answer", "error", "halted"),
    [
        (github_json({"message": "No answer"}, status=502), GitHubUnreadError, False),
        (
            github_json({"message": "Too many"}, status=429, headers={"retry-after": "30"}),
            GitHubRateLimitError,
            False,
        ),
        (
            github_json(
                {"message": "You have exceeded a secondary rate limit"},
                status=403,
                headers={**quota_headers(4999), "retry-after": "60"},
            ),
            GitHubRateLimitError,
            False,
        ),
        (
            github_json(
                {"message": "API rate limit exceeded"}, status=403, headers=quota_headers(0)
            ),
            GitHubRateLimitError,
            False,
        ),
        (github_json({"message": "Bad credentials"}, status=401), GitHubUnauthenticatedError, True),
        (
            github_json({"message": "Sorry. Your account was suspended."}, status=403),
            GitHubUnauthenticatedError,
            True,
        ),
    ],
    ids=["no-answer", "429", "secondary-limit", "no-quota", "refused", "suspended"],
)
def test_a_lane_fetch_halts_the_service_only_when_github_refuses_the_mint(
    app_identity: GitHubApiFake,
    answer: httpx2.Response,
    error: type[GitHubOperationError],
    halted: bool,
) -> None:
    """A mint that GitHub does not answer, or that it rate-limits, fails the round of the lane, and
    the next round mints again. Only a refusal of the App halts every lane of the Service (#6671)."""
    app_identity.route("POST", MINT, answer)
    pause = RoundPause(
        clock=lambda: datetime.now(UTC), refusal=identity_refused, identity="devops-roadmap[bot]"
    )
    with faked_children(side_effect=_finished) as run:
        with pytest.raises(GitHubOperationError, match="has no installation token") as raised:
            run_subprocess(["git", "fetch", "origin"])
    pause.after(raised.value, "example-org/repo1")
    assert (type(raised.value), pause.halted(), run.call_args_list) == (error, halted, [])


_NO_ANSWER = github_json({"message": "No answer"}, status=502)
_RATE_LIMITED = github_json({"message": "Too many"}, status=429, headers={"retry-after": "30"})


@pytest.mark.parametrize("answer", [_NO_ANSWER, _RATE_LIMITED], ids=["no-answer", "429"])
def test_research_reads_the_advisories_with_no_token_when_github_gives_no_token(
    app_identity: GitHubApiFake, answer: httpx2.Response
) -> None:
    """The advisories are public, so research goes on with no token, as it does after a refusal
    (#6671)."""
    app_identity.route("POST", MINT, answer)
    assert _optional_github_token() is None


@pytest.mark.parametrize("answer", [_NO_ANSWER, _RATE_LIMITED], ids=["no-answer", "429"])
@pytest.mark.parametrize(
    ("left", "second"),
    [(timedelta(minutes=5), "ghs_first"), (timedelta(seconds=-1), "raised")],
    ids=["kept-token-valid", "kept-token-expired"],
)
def test_a_failed_renewal_uses_the_kept_token_until_it_expires(
    app_identity: GitHubApiFake, left: timedelta, second: str, answer: httpx2.Response
) -> None:
    """The first token is due for renewal at once. GitHub gives no renewal, so the
    second fetch gets the kept token while it is valid, and fails when it expired. Renewal stays
    due, so the third fetch mints again (#6671)."""
    app_identity.route(
        "POST",
        MINT,
        _installation_token("ghs_first", left),
        answer,
        _installation_token("ghs_second", timedelta(hours=1)),
    )
    tokens: list[str | None] = []

    def child(*_args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        tokens.append(token_seen(kwargs["env"]))
        return _finished()

    with faked_children(side_effect=child):
        for _ in range(3):
            try:
                run_subprocess(["git", "fetch", "origin"])
            except GitHubUnreadError, GitHubRateLimitError:
                tokens.append("raised")
    assert (tokens, len(app_identity.requested)) == (["ghs_first", second, "ghs_second"], 3)


def test_an_app_request_whose_token_is_refused_counts_once_with_status_none(
    app_identity: GitHubApiFake, otlp: FakeCollector
) -> None:
    """The request waits its turn on the ledger before its token is minted. A refused mint still
    counts the paced request with status none, and the refusal reaches the caller (#3497)."""
    app_identity.route("POST", MINT, github_json({"message": "Bad credentials"}, status=401))

    with pytest.raises(GitHubUnauthenticatedError) as raised:
        get_github_session().rest("GET", "/user")

    assert (
        (type(raised.value), raised.value.error_code, raised.value.exit_code),
        otlp.points(GITHUB_REQUESTS_TOTAL.name),
    ) == (
        (GitHubUnauthenticatedError, "GITHUB_UNAUTHENTICATED", 1),
        [
            (
                {
                    "resource": "core",
                    "method": "GET",
                    "status": "none",
                    "repo": "other",
                    "row": "other",
                },
                1.0,
            )
        ],
    )


def test_configured_app_accepts_explicit_permissions_and_read_only_wins(
    app_identity: GitHubApiFake, config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`configured_app(permissions=...)` sends those permissions instead of
    `CONST_GITHUB_APP_TOKEN_PERMISSIONS`, while `service.github_app.read_only` keeps the read-only
    set (#6780)."""
    from devops_cli.config.constants import CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS
    from devops_cli.github.app_installation import configured_app, mint_installation_token

    app_identity.route("POST", MINT, _installation_token("ghs_prepare", timedelta(hours=1)))
    token, _, _ = mint_installation_token(
        configured_app(permissions=CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS)
    )
    assert (token, json.loads(app_identity.sent[0].content)) == (
        "ghs_prepare",
        {
            "permissions": {
                "contents": "read",
                "pull_requests": "read",
                "issues": "write",
                "checks": "read",
                "actions": "read",
            }
        },
    )

    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_READ_ONLY", "true")
    app_identity.route("POST", MINT, _installation_token("ghs_ro", timedelta(hours=1)))
    token_ro, _, _ = mint_installation_token(
        configured_app(permissions=CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS)
    )
    assert (token_ro, json.loads(app_identity.sent[1].content)) == (
        "ghs_ro",
        {"permissions": READ_PERMISSIONS},
    )


def test_token_permissions_scope_mints_prepare_and_publish_tokens_by_workflow_flag(
    app_identity: GitHubApiFake,
) -> None:
    """`token_permissions_scope` updates `_session_github_token` when phase permissions change and
    `publish_token_permissions` omits `workflows` unless `workflows=True` (#6780)."""
    from devops_cli.config.constants import (
        CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS,
        publish_token_permissions,
    )
    from devops_cli.core.process import token_permissions_scope

    app_identity.route(
        "POST",
        MINT,
        _installation_token("ghs_prep", timedelta(hours=1)),
        _installation_token("ghs_pub", timedelta(hours=1)),
        _installation_token("ghs_pub_wf", timedelta(hours=1)),
    )

    with token_permissions_scope(CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS):
        prep_token = github_token()
        with token_permissions_scope(publish_token_permissions(workflows=False)):
            pub_token = github_token()
            with token_permissions_scope(publish_token_permissions(workflows=True)):
                pub_wf_token = github_token()

    prep_perms = json.loads(app_identity.sent[0].content)["permissions"]
    pub_perms = json.loads(app_identity.sent[1].content)["permissions"]
    pub_wf_perms = json.loads(app_identity.sent[2].content)["permissions"]
    assert (
        (prep_token, pub_token, pub_wf_token),
        prep_perms,
        ("workflows" in pub_perms, pub_perms["contents"], pub_perms["pull_requests"]),
        pub_wf_perms.get("workflows"),
    ) == (
        ("ghs_prep", "ghs_pub", "ghs_pub_wf"),
        {
            "contents": "read",
            "pull_requests": "read",
            "issues": "write",
            "checks": "read",
            "actions": "read",
        },
        (False, "write", "write"),
        "write",
    )


def test_adr_0030_has_no_deferred_token_sentence() -> None:
    """ADR 0030 no longer claims one process keeps `workflows: write` until #3700 (#6780)."""
    import re

    from tests.support.paths import REPO_ROOT

    adr = REPO_ROOT / "docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md"
    text = adr.read_text(encoding="utf-8")
    assert not re.search(r"Until #3700.*token|token keeps `workflows: write`", text)


def test_stage_job_phases_scope_token_permissions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`stage` `prepare` and `publish` bind their respective token permissions (#6780)."""
    from types import SimpleNamespace

    from devops_cli.config.constants import (
        CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS,
        publish_token_permissions,
    )
    from devops_cli.core.process import active_token_permissions
    from devops_cli.roadmap.phases.files import RunFolders
    from devops_cli.roadmap.stage import stage_job_phases
    from devops_cli.roadmap.stage.stage import StageResult

    seen: list[tuple[str, dict[str, str] | None]] = []
    monkeypatch.setattr(stage_job_phases, "require_job_token_scope", lambda _repo: None)
    monkeypatch.setattr(
        stage_job_phases,
        "load_settings",
        lambda: SimpleNamespace(
            roadmap=SimpleNamespace(
                stage=SimpleNamespace(
                    github_requests_per_hour=100,
                    job="stage",
                    time_budget_seconds=10,
                    job_deadline=None,
                )
            )
        ),
    )
    monkeypatch.setattr(stage_job_phases, "known_job", lambda *_a, **_k: False)
    monkeypatch.setattr(stage_job_phases, "job_time_budget", lambda *_a, **_k: 0)

    def fake_deadline_end(*_a: object, **_k: object) -> stage_job_phases.StageJobRun:
        seen.append(("stage_prepare", active_token_permissions()))
        return stage_job_phases.StageJobRun(
            stage_job_phases.StageJobExit.RESULT,
            StageResult.STAGED,
            SimpleNamespace(spent=lambda: 0),
        )

    def fake_read_stage_state(*_a: object, **_k: object) -> stage_job_phases.StageState:
        seen.append(("stage_publish", active_token_permissions()))
        return stage_job_phases.StageState(
            repo="o/r",
            item=1,
            job="stage",
            ended=True,
            end=stage_job_phases.StageJobExit.RESULT,
            result=StageResult.STAGED,
            requests=0,
        )

    monkeypatch.setattr(stage_job_phases, "deadline_end", fake_deadline_end)
    monkeypatch.setattr(stage_job_phases, "_write_state", lambda *_a, **_k: None)
    stage_job_phases.prepare_stage_job(
        SimpleNamespace(), RunFolders(tmp_path / "stage-prep"), repo="o/r", item=1
    )

    monkeypatch.setattr(stage_job_phases, "read_stage_state", fake_read_stage_state)
    stage_job_phases.publish_stage_job(
        SimpleNamespace(), RunFolders(tmp_path / "stage-pub"), repo="o/r", item=1
    )

    assert seen == [
        ("stage_prepare", CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS),
        ("stage_publish", publish_token_permissions(workflows=False)),
    ]


def test_fix_checks_phases_scope_token_permissions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`fix-checks` binds `prepare` on prepare, `workflows=False` on ambient `publish`, and
    `workflows=True` during push only when workflow paths are present (#6780)."""
    from types import SimpleNamespace

    from devops_cli.config.constants import (
        CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS,
        publish_token_permissions,
    )
    from devops_cli.core.process import active_token_permissions
    from devops_cli.github.client import PullStatus
    from devops_cli.roadmap.phases.files import OutcomeKind, RunFolders
    from devops_cli.roadmap.phases.publish import NewTree, Published, PublishTarget
    from devops_cli.roadmap.steps import fix_checks_phases
    from devops_cli.roadmap.steps.fix_checks import (
        FixChecksReport,
        FixChecksResult,
        Fixed,
        FixRound,
        PullCheckout,
        Repair,
    )
    from devops_cli.roadmap.steps.fix_checks_phases import FixTier

    seen: list[tuple[str, dict[str, str] | None]] = []

    def _repair(
        workflows: tuple[str, ...] = (),
        publish: Callable[
            [PublishTarget, Sequence[tuple[bytes, str]], Callable[[NewTree], None]],
            Published | None,
        ]
        | None = None,
    ) -> Repair:
        return Repair(
            checkout=lambda *_a: PullCheckout(path=tmp_path),
            tier1=lambda *_a: Fixed(done=True),
            model=lambda _reader: lambda *_a: Fixed(done=True),
            patch=lambda *_a: None,
            publish=publish or (lambda *_a: Published(commit="b" * 40, paths=())),
            author=lambda: ("bot[bot]", "bot@example.com"),
            rebase=lambda *_a: Fixed(done=True),
            workflows=lambda *_a: workflows,
        )

    def fake_judge_round(*_a: object, **_k: object) -> FixChecksReport:
        seen.append(("fix_checks_prepare", active_token_permissions()))
        return FixChecksReport(repo="o/r", pull=2, result=FixChecksResult.SKIPPED, head="a" * 40)

    monkeypatch.setattr(fix_checks_phases, "judge_round", fake_judge_round)
    fix_checks_phases.prepare_phase(
        SimpleNamespace(),
        SimpleNamespace(),
        "o/r",
        2,
        head=None,
        check=None,
        repair=_repair(),
        folders=RunFolders(tmp_path / "fc-prep"),
    )

    status = PullStatus(
        number=2,
        state="open",
        head_sha="a" * 40,
        head_ref="feat/2-x",
        base_ref="main",
        mergeable=True,
    )
    facts = FixRound(
        repo="o/r",
        pull=2,
        status=status,
        item_num=2,
        item=None,
        heads=(),
        check="ci",
        errors=1,
        rounds=0,
    )
    original_target = fix_checks_phases._target

    def capture_ambient_target(
        repair_arg: Repair, facts_arg: FixRound, base_arg: str
    ) -> PublishTarget:
        seen.append(("fix_checks_publish_ambient", active_token_permissions()))
        return original_target(repair_arg, facts_arg, base_arg)

    monkeypatch.setattr(fix_checks_phases, "_live_round", lambda *_a, **_k: facts)
    monkeypatch.setattr(
        fix_checks_phases,
        "read_outcome",
        lambda _f: SimpleNamespace(
            kind=OutcomeKind.DONE,
            result=FixChecksResult.REPAIRED.value,
            detail=FixTier.TIER1.value,
            reason="",
            files=[],
        ),
    )
    monkeypatch.setattr(fix_checks_phases, "_branch_patches", lambda *_a: [])
    monkeypatch.setattr(fix_checks_phases, "_read_patch", lambda *_a: b"diff")
    monkeypatch.setattr(fix_checks_phases, "record_outcome", lambda *_a, **_k: None)
    monkeypatch.setattr(fix_checks_phases, "named_files", lambda *_a, **_k: "")
    monkeypatch.setattr(fix_checks_phases, "_target", capture_ambient_target)

    def run_publish(workflows: tuple[str, ...]) -> None:
        def fake_publish(
            _target: PublishTarget,
            _patches: Sequence[tuple[bytes, str]],
            _before: Callable[[NewTree], None],
        ) -> Published:
            tag = "fix_checks_publish_wf" if workflows else "fix_checks_publish_no_wf"
            seen.append((tag, active_token_permissions()))
            return Published(commit="b" * 40, paths=("src/a.py",))

        judged_round = fix_checks_phases.JudgedRound("o/r", 2, 2, status, "ci", 1, "")
        fix_checks_phases.publish_round(
            SimpleNamespace(),
            SimpleNamespace(),
            judged_round,
            RunFolders(tmp_path / ("fc-pub-wf" if workflows else "fc-pub")),
            _repair(workflows=workflows, publish=fake_publish),
        )

    run_publish(())
    run_publish((".github/workflows/ci.yml",))

    assert seen == [
        ("fix_checks_prepare", CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS),
        ("fix_checks_publish_ambient", publish_token_permissions(workflows=False)),
        ("fix_checks_publish_no_wf", publish_token_permissions(workflows=False)),
        ("fix_checks_publish_ambient", publish_token_permissions(workflows=False)),
        ("fix_checks_publish_wf", publish_token_permissions(workflows=True)),
    ]


def test_fix_conflict_phases_scope_token_permissions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`fix-conflict` binds `prepare` on prepare, `workflows=False` on ambient `publish`, and
    `workflows=True` during push only when workflow paths are present (#6780)."""
    from types import SimpleNamespace

    from devops_cli.config.constants import (
        CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS,
        publish_token_permissions,
    )
    from devops_cli.core.process import active_token_permissions
    from devops_cli.github.client import PullStatus
    from devops_cli.roadmap.phases.files import OutcomeKind, RunFolders
    from devops_cli.roadmap.steps import fix_conflict_phases
    from devops_cli.roadmap.steps.fix_conflict import (
        ConflictRound,
        FixConflictReport,
        FixConflictResult,
    )

    seen: list[tuple[str, dict[str, str] | None]] = []

    def fake_admit_round(*_a: object, **_k: object) -> FixConflictReport:
        seen.append(("fix_conflict_prepare", active_token_permissions()))
        return FixConflictReport(
            repo="o/r", pull=3, result=FixConflictResult.STOPPED, reason="done"
        )

    monkeypatch.setattr(fix_conflict_phases.fix_conflict, "admit_round", fake_admit_round)
    fix_conflict_phases.prepare_phase(
        SimpleNamespace(),
        SimpleNamespace(),
        "o/r",
        3,
        head=None,
        folders=RunFolders(tmp_path / "fconf-prep"),
    )

    monkeypatch.setattr(
        fix_conflict_phases,
        "read_outcome",
        lambda _f: SimpleNamespace(
            kind=OutcomeKind.DONE, result=FixConflictResult.RESOLVED.value, reason=""
        ),
    )
    monkeypatch.setattr(
        fix_conflict_phases,
        "get_github_session",
        lambda: SimpleNamespace(login="bot[bot]", commit_email="bot@example.com"),
    )
    monkeypatch.setattr(fix_conflict_phases, "_patches", lambda *_a: [])
    monkeypatch.setattr(
        fix_conflict_phases.fix_conflict, "record_fix_conflict_marks", lambda *_a, **_k: None
    )

    status = PullStatus(
        number=3,
        state="open",
        head_sha="a" * 40,
        head_ref="feat/3-x",
        base_ref="main",
        mergeable=False,
    )

    def run_publish(workflows: tuple[str, ...]) -> None:
        def fake_merged(_repo: str, _default: str, _num: int) -> tuple[str, ...]:
            seen.append(("fix_conflict_publish_ambient", active_token_permissions()))
            return workflows

        def fake_publish_patch(
            _target: object, _patches: object, before_push: object = None
        ) -> SimpleNamespace:
            tag = "fix_conflict_publish_wf" if workflows else "fix_conflict_publish_no_wf"
            seen.append((tag, active_token_permissions()))
            return SimpleNamespace(commit="c" * 40)

        monkeypatch.setattr(fix_conflict_phases, "merged_workflows", fake_merged)
        monkeypatch.setattr(fix_conflict_phases, "publish_patch", fake_publish_patch)
        round_obj = ConflictRound(
            "o/r", 3, status, 3, SimpleNamespace(title="T"), SimpleNamespace(), 0, ()
        )
        prepared = fix_conflict_phases.PreparedRound(round_obj, "a" * 40, ("a.py",), "k", 1)
        fix_conflict_phases.publish_round(
            SimpleNamespace(item=lambda _n: SimpleNamespace(title="T")),
            SimpleNamespace(),
            prepared,
            RunFolders(tmp_path / ("fconf-pub-wf" if workflows else "fconf-pub")),
        )

    run_publish(())
    run_publish((".github/workflows/ci.yml",))

    assert seen == [
        ("fix_conflict_prepare", CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS),
        ("fix_conflict_publish_ambient", publish_token_permissions(workflows=False)),
        ("fix_conflict_publish_no_wf", publish_token_permissions(workflows=False)),
        ("fix_conflict_publish_ambient", publish_token_permissions(workflows=False)),
        ("fix_conflict_publish_wf", publish_token_permissions(workflows=True)),
    ]
