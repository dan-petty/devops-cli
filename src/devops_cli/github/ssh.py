"""GitHub SSH key registration: authentication + commit signing."""

from __future__ import annotations

import json
import subprocess

import httpx2

from devops_cli.config.constants import CONST_URL_GITHUB_API_BASE
from devops_cli.github.client import GitHubClient


class SSHRegistrationError(RuntimeError):
    """Raised when SSH/signing key registration on GitHub fails."""


def register_key_on_github(pub_key: str, title: str, token: str | None = None) -> None:
    """Add *pub_key* to GitHub as both an auth key and a signing key."""
    if _register_with_gh(pub_key, title):
        return

    if token:
        _register_with_token_api(token, pub_key, title)
        return

    raise SSHRegistrationError(
        "No usable GitHub auth found for key registration. "
        "Run 'gh auth login' or configure DEVOPS_CLI_GITHUB_TOKEN."
    )


def _register_with_token_api(token: str, pub_key: str, title: str) -> None:
    """Register using token-backed PyGithub + REST API fallback."""
    client = GitHubClient(token)

    # Authentication key — skip if an identical key body already exists
    key_body = " ".join(pub_key.split()[:2])  # "ssh-ed25519 <base64>"
    existing = client.get_user_ssh_keys()
    if not any(" ".join(k.key.split()[:2]) == key_body for k in existing):
        client.add_user_ssh_key(title=title, key=pub_key)

    # Signing key (separate endpoint, not yet in PyGithub)
    _add_signing_key(token, pub_key, title)


def _register_with_gh(pub_key: str, title: str) -> bool:
    """Register keys via GitHub CLI auth context. Returns True on success/path used."""
    if not _gh_auth_ok():
        return False

    key_body = " ".join(pub_key.split()[:2])
    existing_auth = _gh_list_keys("/user/keys")
    if existing_auth is not None and key_body not in existing_auth:
        _gh_add_key("/user/keys", pub_key, title)
    elif existing_auth is None:
        _gh_add_key("/user/keys", pub_key, title)

    existing_signing = _gh_list_keys("/user/ssh_signing_keys")
    if existing_signing is not None and key_body not in existing_signing:
        _gh_add_key("/user/ssh_signing_keys", pub_key, title)
    elif existing_signing is None:
        _gh_add_key("/user/ssh_signing_keys", pub_key, title)

    return True


def _gh_auth_ok() -> bool:
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        return False
    return result.returncode == 0


def _gh_list_keys(endpoint: str) -> set[str] | None:
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
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
        result = subprocess.run(
            [
                "gh",
                "api",
                "--method",
                "POST",
                endpoint,
                "-f",
                f"title={title}",
                "-f",
                f"key={pub_key}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        raise SSHRegistrationError(f"GitHub CLI key registration failed: {exc}") from exc

    if result.returncode == 0:
        return

    combined = f"{result.stdout}\n{result.stderr}".lower()
    if "already" in combined and "key" in combined:
        return

    if "needs the" in combined and "scope" in combined:
        raise SSHRegistrationError(
            "GitHub CLI auth is missing required scopes. "
            "Run: gh auth refresh -h github.com "
            "-s admin:public_key,write:ssh_signing_key"
        )

    raise SSHRegistrationError(result.stderr.strip() or result.stdout.strip() or "gh api failed")


def _add_signing_key(token: str, pub_key: str, title: str) -> None:
    """Register the key as a GitHub SSH signing key via the REST API."""
    with httpx2.Client() as client:
        resp = client.post(
            f"{CONST_URL_GITHUB_API_BASE}/user/ssh_signing_keys",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"title": title, "key": pub_key},
            timeout=30,
        )
        # 422 Unprocessable Entity means the key already exists — that's fine
        if resp.status_code not in (201, 422):
            resp.raise_for_status()
