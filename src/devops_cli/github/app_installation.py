"""The GitHub App that the roadmap Service and the cluster jobs act as (ADR 0015).

A process acts as the App when its environment holds the App's private key,
`DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, as Secret `devops/devops-cli` gives it to the
cluster's pods. The App's ID, its installation's ID and its slug come from `service.github_app`.
gidgethub signs a JWT with the key, and the process exchanges it for an installation token at
`POST /app/installations/<id>/access_tokens`, over the session's client, so the request goes to
GitHub's API origin only. The request asks for `CONST_GITHUB_APP_TOKEN_PERMISSIONS` only, the
permissions the roadmap jobs use, so the token carries no other permission that the installation
grants (#2473). A runner Job also sets `service.github_app.token_repository`, and then the request
names that one repository, so a step cannot push to another one (#2667). The implement job runs
no step without it. `gidgethub.apps.get_installation_access_token` sends no body, so the process
posts the request through gidgethub's `GitHubAPI`. `core.process` keeps the token, gives it to
every gh and git child and mints a new one before it expires. The App's login is its bot's,
`<slug>[bot]`: an installation token cannot read `GET /user`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from typing import Any

from devops_cli.config.constants import (
    CONST_GITHUB_APP_LEDGER_KEY,
    CONST_GITHUB_APP_PRIVATE_KEY_ENV,
    CONST_GITHUB_APP_TOKEN_PERMISSIONS,
    CONST_GITHUB_USER_AGENT,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import ERRORS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitHubApp:
    """One installation of a GitHub App, and the private key that signs its JWTs."""

    app_id: int
    installation_id: int
    slug: str
    private_key: str = field(repr=False)
    token_repository: str | None = None

    @property
    def bot_login(self) -> str:
        """The login of the App's bot, which GitHub shows as the author of its writes."""
        return f"{self.slug}[bot]"

    @property
    def ledger_key(self) -> str:
        """What names the installation's quota ledger and session: each of its tokens shares it."""
        return CONST_GITHUB_APP_LEDGER_KEY.format(installation_id=self.installation_id)


def configured_app() -> GitHubApp:
    """The App the process acts as: `service.github_app` and the private key of the environment.

    Raises ConfigurationError naming each setting that is not set.
    """
    from devops_cli.config.settings import load_settings

    config = load_settings().service.github_app
    wanted = (
        ("service.github_app.app_id", config.app_id),
        ("service.github_app.installation_id", config.installation_id),
        ("service.github_app.slug", config.slug),
    )
    missing = [option for option, value in wanted if not value]
    if config.app_id is None or config.installation_id is None or config.slug is None:
        raise ConfigurationError(
            ERRORS.git.github_app_settings_missing.format(
                key_env=CONST_GITHUB_APP_PRIVATE_KEY_ENV, settings=", ".join(missing)
            ),
            key=missing[0],
        )
    return GitHubApp(
        app_id=config.app_id,
        installation_id=config.installation_id,
        slug=config.slug,
        private_key=os.environ.get(CONST_GITHUB_APP_PRIVATE_KEY_ENV, ""),
        token_repository=config.token_repository,
    )


def mint_installation_token() -> tuple[str, str, datetime | None]:
    """A new installation token of the App and when it expires, or "" and why GitHub gave none.

    The token carries only `CONST_GITHUB_APP_TOKEN_PERMISSIONS`, and the log names the
    permissions of GitHub's reply, without their levels. A reply that grants more is no error.
    The reason names the request and GitHub's status, or says that the key could not sign a JWT;
    it never holds the key or a token. GitHub refuses with HTTP 422 a permission that the
    installation does not grant, and its reply does not say which, so the reason then names each
    permission that the token asks for. GitHub also refuses with HTTP 401, and the error message
    includes GitHub's reason.
    """
    import httpx2
    from gidgethub import HTTPException

    from devops_cli.exceptions.base import DevOpsCLIError
    from devops_cli.github.error_classifier import classify_http_error

    app = configured_app()
    if not _is_rsa_private_key(app.private_key):
        return "", _token_failed(app, ERRORS.git.github_app_key_unreadable), None
    try:
        answer = _exchange(app)
    except DevOpsCLIError as refusal:
        return "", _token_failed(app, refusal.message), None
    except (HTTPException, httpx2.HTTPError, ValueError, LookupError) as error:
        failure = classify_http_error(error, method="POST", path=_token_path(app))
        reason = failure.message
        if failure.details.get("status") == HTTPStatus.UNPROCESSABLE_ENTITY:
            reason = _not_granted(app, reason)
        elif failure.details.get("status") == HTTPStatus.UNAUTHORIZED:
            # Replace the generic 401 message with one that includes GitHub's reason and App-specific context
            reason = ERRORS.git.github_app_jwt_refused.format(
                request=f"POST {_token_path(app)}",
                reason=str(error)[:CONST_MAX_ERROR_DETAIL_LENGTH],
            )
        return "", _token_failed(app, reason), None
    try:
        token, expires_at = str(answer["token"]), datetime.fromisoformat(answer["expires_at"])
    except KeyError, TypeError, ValueError:
        return "", _token_failed(app, ERRORS.git.github_app_answer_unreadable), None
    granted = answer.get("permissions")
    logger.info(
        "GitHub App %s has a new installation token with these permissions: %s",
        app.bot_login,
        ", ".join(sorted(granted)) if isinstance(granted, dict) else "",
    )
    return token, "", expires_at


def _token_path(app: GitHubApp) -> str:
    """Where the App exchanges its JWT for an installation token."""
    return f"/app/installations/{app.installation_id}/access_tokens"


def _not_granted(app: GitHubApp, reason: str) -> str:
    """`reason` with what the installation must grant. A token for one repository (#2667, #2913)
    also needs the installation to include that repository, and GitHub's HTTP 422 does not say
    which of the two is missing."""
    if app.token_repository:
        return ERRORS.git.github_app_repository_not_granted.format(
            reason=reason, repository=app.token_repository, permissions=_asked_permissions()
        )
    return ERRORS.git.github_app_permissions_not_granted.format(
        reason=reason, permissions=_asked_permissions()
    )


def _asked_permissions() -> str:
    """Each permission that the token asks for, with its level, as an error names them."""
    return ", ".join(
        f"{name} ({level})" for name, level in sorted(CONST_GITHUB_APP_TOKEN_PERMISSIONS.items())
    )


def _is_rsa_private_key(pem: str) -> bool:
    """Whether `pem` is an RSA private key in PEM form, the only key GitHub gives an App, so
    gidgethub can sign the App's RS256 JWT with it."""
    from cryptography.exceptions import UnsupportedAlgorithm
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    try:
        key = load_pem_private_key(pem.encode("utf-8"), password=None)
    except ValueError, TypeError, UnsupportedAlgorithm:
        return False
    return isinstance(key, RSAPrivateKey)


def _token_failed(app: GitHubApp, reason: str) -> str:
    """Why the App has no installation token."""
    return ERRORS.git.github_app_token_failed.format(
        login=app.bot_login, reason=reason, key_env=CONST_GITHUB_APP_PRIVATE_KEY_ENV
    )


def _exchange(app: GitHubApp) -> dict[str, Any]:
    """GitHub's answer to the exchange of the App's JWT for an installation token that carries
    only `CONST_GITHUB_APP_TOKEN_PERMISSIONS` and, when `service.github_app.token_repository` is
    set, names only that repository (#2667).

    gidgethub signs the JWT with the App's ID and key. The exchange runs on a loop of its own, so
    a caller on any thread, an event loop's included, can wait for it.
    """
    from anyio.from_thread import start_blocking_portal
    from gidgethub.httpx import GitHubAPI

    from devops_cli.github.session_transport import session_client

    body: dict[str, Any] = {"permissions": dict(CONST_GITHUB_APP_TOKEN_PERMISSIONS)}
    if app.token_repository:
        body["repositories"] = [app.token_repository.partition("/")[2]]

    async def exchange() -> dict[str, Any]:
        async with session_client() as client:
            api = GitHubAPI(
                client,
                CONST_GITHUB_USER_AGENT,
                base_url=CONST_URL_GITHUB_API_BASE,
                app_id=str(app.app_id),
                private_key=app.private_key,
            )
            answer: dict[str, Any] = await api.post(_token_path(app), data=body)
            return answer

    with start_blocking_portal() as portal:
        return portal.call(exchange)
