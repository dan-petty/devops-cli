"""An installation token of a named GitHub App, written to a file (#4897).

Self-hosted Renovate (#4893) acts as its own GitHub App, `dan-petty-renovate`, and takes only an
installation token, which GitHub ends after one hour. `devops gh app-token --app renovate --write
<path>` reads the App's ID or Client ID, its installation's ID and its private key from the
`renovate` settings, and `app_installation.mint_installation_token` mints a token that asks only
for `CONST_RENOVATE_GITHUB_APP_TOKEN_PERMISSIONS`. The token goes to a temporary file with mode
0600 in the directory of `<path>`, which then replaces `<path>`, so no reader sees a part of it or
another mode. The command prints the path and when GitHub ends the token, never the token. The
init container of the Renovate CronJob runs it, so only that container holds the App's key.

A dry run reads the two IDs from the settings and no credential: it shows the request with its
body, and the token that a run writes as a placeholder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from devops_cli.config.constants import (
    CONST_PERM_TOKEN_FILE,
    CONST_RENOVATE_GITHUB_APP_SLUG,
    CONST_RENOVATE_GITHUB_APP_TOKEN_PERMISSIONS,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import ConfigurationError
from devops_cli.github.app_installation import GitHubApp, installation_token_path
from devops_cli.lang import ERRORS, MESSAGES

_APP_ID_KEY = "renovate.github_app_id"
_INSTALLATION_ID_KEY = "renovate.github_app_installation_id"
_PRIVATE_KEY_KEY = "renovate.github_app_private_key"


class TokenApp(StrEnum):
    """The GitHub Apps whose installation token `devops gh app-token` writes."""

    RENOVATE = "renovate"


@dataclass(frozen=True)
class WrittenToken:
    """Where the token of an App went, and when GitHub ends it. It never holds the token."""

    login: str
    path: Path
    expires_at: datetime


def token_app(app: TokenApp, *, with_key: bool = True) -> GitHubApp:
    """The installation of `app` from its settings, with its private key when `with_key`.

    Raises ConfigurationError naming each setting that is not set, and its variable. Without
    `with_key`, as a dry run asks, no credential is read and the key is empty.
    """
    from devops_cli.config.env import env_var_for_option
    from devops_cli.config.settings import get_renovate_github_app_private_key, load_settings

    settings = load_settings()
    config = settings.renovate
    private_key = (get_renovate_github_app_private_key(settings) or "") if with_key else ""
    wanted = [
        (_APP_ID_KEY, config.github_app_id),
        (_INSTALLATION_ID_KEY, config.github_app_installation_id),
    ]
    if with_key:
        wanted.append((_PRIVATE_KEY_KEY, private_key.strip()))
    missing = [key for key, value in wanted if not value]
    if missing or config.github_app_id is None or config.github_app_installation_id is None:
        raise ConfigurationError(
            ERRORS.git.github_app_token_settings_missing.format(
                login=f"{CONST_RENOVATE_GITHUB_APP_SLUG}[bot]",
                settings=", ".join(missing),
                variables=", ".join(env_var_for_option(key) or key for key in missing),
            ),
            key=missing[0],
        )
    return GitHubApp(
        app_id=config.github_app_id,
        installation_id=config.github_app_installation_id,
        slug=CONST_RENOVATE_GITHUB_APP_SLUG,
        private_key=private_key,
        permissions=CONST_RENOVATE_GITHUB_APP_TOKEN_PERMISSIONS,
        key_source=_PRIVATE_KEY_KEY,
    )


def app_token_plan(app: TokenApp, path: Path) -> tuple[str, list[PlannedRequest], list[str]]:
    """The heading, the request and the notes of a dry run that writes the token of `app` to
    `path`. It sends nothing and reads no credential."""
    github_app = token_app(app, with_key=False)
    texts = MESSAGES.gh_app_token
    body = json.dumps({"permissions": dict(CONST_RENOVATE_GITHUB_APP_TOKEN_PERMISSIONS)}, indent=2)
    target = f"{CONST_URL_GITHUB_API_BASE}{installation_token_path(github_app.installation_id)}"
    request = PlannedRequest("POST", target, stdin=body)
    notes = [
        texts.plan_signed.format(app_id=github_app.app_id, key=_PRIVATE_KEY_KEY),
        texts.plan_written.format(path=path, mode=CONST_PERM_TOKEN_FILE),
    ]
    return texts.plan_title.format(login=github_app.bot_login), [request], notes


def write_app_token(app: TokenApp, path: Path) -> WrittenToken:
    """Mint an installation token of `app` and write it to `path` with mode 0600.

    Raises ConfigurationError for a setting that is not set, GitHubUnauthenticatedError with
    GitHub's reason when it refuses the token, GitHubUnreadError when GitHub does not answer, and
    GitHubRateLimitError when it rate-limits the exchange. Then `path` stays as it was.
    """
    from devops_cli.exceptions.git import GitHubUnauthenticatedError
    from devops_cli.github.app_installation import mint_installation_token
    from devops_cli.output.file_writer import write_text_file

    github_app = token_app(app)
    token, reason, expires_at = mint_installation_token(github_app)
    if not token or expires_at is None:
        raise GitHubUnauthenticatedError(reason, operation="gh_app_token")
    write_text_file(path, token, mode=CONST_PERM_TOKEN_FILE)
    return WrittenToken(login=github_app.bot_login, path=path, expires_at=expires_at)
