"""GitHub SSH key registration: authentication + commit signing."""

from __future__ import annotations

import json
import subprocess
from http import HTTPStatus

from devops_cli.config.constants import CONST_MAX_ERROR_DETAIL_LENGTH
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.exceptions.git import GitHubOperationError, GitHubScopeError
from devops_cli.github.error_classifier import classify_gh_failure, gh_http_status
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import GitHubSession, get_github_session


class SSHRegistrationError(RuntimeError):
    """Raised when SSH/signing key registration on GitHub fails."""


def register_key_on_github(pub_key: str, title: str) -> None:
    """Add *pub_key* to GitHub as both an auth key and a signing key, as the session's identity."""
    if _register_with_gh(pub_key, title):
        return
    try:
        session = get_github_session()
    except GitHubOperationError as exc:
        raise SSHRegistrationError(
            "No usable GitHub auth found for key registration. Run 'gh auth login'."
        ) from exc
    _register_with_token_api(session, pub_key, title)


def _register_with_token_api(session: GitHubSession, pub_key: str, title: str) -> None:
    """Register through PyGithub and the REST API with the session's token."""
    client = session.client

    # Authentication key — skip if an identical key body already exists
    key_body = " ".join(pub_key.split()[:2])  # "ssh-ed25519 <base64>"
    existing = client.get_user_ssh_keys()
    if not any(" ".join(k.key.split()[:2]) == key_body for k in existing):
        client.add_user_ssh_key(title=title, key=pub_key)

    # Signing key (separate endpoint, not yet in PyGithub)
    _add_signing_key(session, pub_key, title)


def _register_with_gh(pub_key: str, title: str) -> bool:
    """Register keys via GitHub CLI auth context. Returns True on success/path used."""
    if not _gh_auth_ok():
        return False

    key_body = " ".join(pub_key.split()[:2])
    existing_auth = _gh_list_keys("/user/keys")
    if (existing_auth is not None and key_body not in existing_auth) or existing_auth is None:
        _gh_add_key("/user/keys", pub_key, title)

    existing_signing = _gh_list_keys("/user/ssh_signing_keys")
    if existing_signing is None or key_body not in existing_signing:
        _gh_add_key("/user/ssh_signing_keys", pub_key, title)

    return True


def _gh_auth_ok() -> bool:
    try:
        result = run_gh(
            ["auth", "status"],
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        return False
    return result.returncode == 0


def _gh_list_keys(endpoint: str) -> set[str] | None:
    try:
        result = run_gh(
            ["api", endpoint],
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        return None

    if result.returncode != 0:
        return None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, list):
        return None

    keys: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        key_text = item.get("key")
        if isinstance(key_text, str):
            keys.add(" ".join(key_text.split()[:2]))
    return keys


def _gh_add_key(endpoint: str, pub_key: str, title: str) -> None:
    try:
        result = run_gh(
            [
                "api",
                "--method",
                "POST",
                endpoint,
                "-f",
                f"title={title}",
                "-f",
                f"key={pub_key}",
            ],
            quiet=True,
            check=False,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        raise SSHRegistrationError(f"GitHub CLI key registration failed: {exc}") from exc

    if result.returncode == 0:
        return

    # gh writes the failure to stderr; stdout holds GitHub's answer.
    said = result.stderr or ""
    if gh_http_status(said) == HTTPStatus.UNPROCESSABLE_ENTITY and _registered_after_422(
        endpoint, pub_key
    ):
        return

    refused = classify_gh_failure(said, exit_code=result.returncode, operation="ssh_key_upload")
    if isinstance(refused, GitHubScopeError):
        raise SSHRegistrationError(
            "GitHub CLI auth is missing required scopes. "
            "Run: gh auth refresh -h github.com "
            "-s admin:public_key,write:ssh_signing_key"
        ) from refused

    raise SSHRegistrationError(_registration_failure(result)) from refused


def _registered_after_422(endpoint: str, pub_key: str) -> bool:
    """Whether a key GitHub answered 422 for is registered at `endpoint`. GitHub answers 422 for
    a key it already holds, but also for one it rejects as invalid and one in use on another
    account, so the keys are listed again: a listed key, or a list that can't be read, is
    registered."""
    listed = _gh_list_keys(endpoint)
    return listed is None or " ".join(pub_key.split()[:2]) in listed


def _registration_failure(result: subprocess.CompletedProcess[str]) -> str:
    """What gh wrote for a failed key upload, with the reasons GitHub gave in its answer."""
    said = result.stderr.strip() or result.stdout.strip() or "gh api failed"
    reasons = _github_reasons(result.stdout or "")
    return f"{said}: {reasons}" if reasons else said


def _github_reasons(answer: str) -> str:
    """The `errors[].message` of GitHub's validation answer, for display only, at most
    `CONST_MAX_ERROR_DETAIL_LENGTH` characters; empty when the answer holds none."""
    try:
        decoded = json.loads(answer)
    except json.JSONDecodeError:
        return ""
    errors = decoded.get("errors") if isinstance(decoded, dict) else None
    if not isinstance(errors, list):
        return ""
    reasons = [error.get("message") for error in errors if isinstance(error, dict)]
    said = "; ".join(reason for reason in reasons if isinstance(reason, str))
    return said[:CONST_MAX_ERROR_DETAIL_LENGTH]


def _add_signing_key(session: GitHubSession, pub_key: str, title: str) -> None:
    """Register the key as a GitHub SSH signing key; GitHub's 422 means it already is one."""
    try:
        session.rest("POST", "/user/ssh_signing_keys", body={"title": title, "key": pub_key})
    except GitHubOperationError as exc:
        if exc.details.get("status") != HTTPStatus.UNPROCESSABLE_ENTITY:
            raise
