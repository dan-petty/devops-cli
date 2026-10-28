"""The GitHub App that the roadmap Service and the cluster jobs act as (ADR 0015).

A process acts as the App when its environment holds the App's private key,
`DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, as Secret `devops/devops-cli` gives it to the
cluster's pods. The App's ID, its installation's ID and its slug come from `service.github_app`.
gidgethub signs a JWT with the key and exchanges it for an installation token
(`gidgethub.apps.get_installation_access_token`), over the session's client, so the request goes
to GitHub's API origin only. `core.process` keeps the token, gives it to every gh and git child
and mints a new one before it expires. The App's login is its bot's, `<slug>[bot]`: an
installation token cannot read `GET /user`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from devops_cli.config import options as opt
from devops_cli.config.constants import (
    CONST_GITHUB_APP_LEDGER_KEY,
    CONST_GITHUB_APP_PRIVATE_KEY_ENV,
    CONST_GITHUB_USER_AGENT,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import ERRORS


@dataclass(frozen=True)
class GitHubApp:
    """One installation of a GitHub App, and the private key that signs its JWTs."""

    app_id: int
    installation_id: int
    slug: str
    private_key: str = field(repr=False)

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
        (opt.SERVICE_GITHUB_APP_APP_ID, config.app_id),
        (opt.SERVICE_GITHUB_APP_INSTALLATION_ID, config.installation_id),
        (opt.SERVICE_GITHUB_APP_SLUG, config.slug),
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
    )


def mint_installation_token() -> tuple[str, str, datetime | None]:
    """A new installation token of the App and when it expires, or "" and why GitHub gave none.

    The reason names the request and GitHub's status, or says that the key could not sign a JWT;
    it never holds the key or a token.
    """
    import httpx2
    from gidgethub import HTTPException

    from devops_cli.exceptions.base import DevOpsCLIError
    from devops_cli.github.error_classifier import classify_http_error

    app = configured_app()
    if not _is_rsa_private_key(app.private_key):
        return "", _token_failed(app, ERRORS.git.github_app_key_unreadable), None
    path = f"/app/installations/{app.installation_id}/access_tokens"
    try:
        answer = _exchange(app)
    except DevOpsCLIError as refusal:
        return "", _token_failed(app, refusal.message), None
    except (HTTPException, httpx2.HTTPError, ValueError, LookupError) as error:
        failure = classify_http_error(error, method="POST", path=path)
        return "", _token_failed(app, failure.message), None
    try:
        return str(answer["token"]), "", datetime.fromisoformat(answer["expires_at"])
    except KeyError, TypeError, ValueError:
        return "", _token_failed(app, ERRORS.git.github_app_answer_unreadable), None


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
    """GitHub's answer to the exchange of the App's JWT for an installation token.

    It runs on a loop of its own, so a caller on any thread, an event loop's included, can wait
    for it.
    """
    from anyio.from_thread import start_blocking_portal
    from gidgethub.apps import get_installation_access_token
    from gidgethub.httpx import GitHubAPI

    from devops_cli.github.session_transport import session_client

    async def exchange() -> dict[str, Any]:
        async with session_client() as client:
            api = GitHubAPI(client, CONST_GITHUB_USER_AGENT, base_url=CONST_URL_GITHUB_API_BASE)
            return await get_installation_access_token(
                api,
                installation_id=str(app.installation_id),
                app_id=str(app.app_id),
                private_key=app.private_key,
            )

    with start_blocking_portal() as portal:
        return portal.call(exchange)
