"""GitHub SSH key registration: authentication + commit signing."""

from __future__ import annotations

import httpx2

from devops_cli.github.client import GitHubClient


def register_key_on_github(token: str, pub_key: str, title: str) -> None:
    """Add *pub_key* to GitHub as both an auth key and a signing key."""
    client = GitHubClient(token)

    # Authentication key — skip if an identical key body already exists
    key_body = " ".join(pub_key.split()[:2])  # "ssh-ed25519 <base64>"
    existing = client.get_user_ssh_keys()
    if not any(" ".join(k["key"].split()[:2]) == key_body for k in existing):
        client.add_user_ssh_key(title=title, key=pub_key)

    # Signing key (separate endpoint, not yet in PyGithub)
    _add_signing_key(token, pub_key, title)


def _add_signing_key(token: str, pub_key: str, title: str) -> None:
    """Register the key as a GitHub SSH signing key via the REST API."""
    with httpx2.Client() as client:
        resp = client.post(
            "https://api.github.com/user/ssh_signing_keys",
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
