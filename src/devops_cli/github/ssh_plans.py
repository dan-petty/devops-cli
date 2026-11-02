"""Planned requests for `devops ssh register` and `devops ssh rotate` (#412, #886, #2258).

A dry run makes zero external requests and returns ordered PlannedRequest items. The key
requests come from `key_requests`, which `register_key_on_github` sends, and the `git config`
commands from `git_signing_commands`, which `configure_git_signing` runs, so the plan cannot
drift from the run.
"""

from __future__ import annotations

import json
from pathlib import Path

from devops_cli.crypto.ssh_keys import git_signing_commands
from devops_cli.dry_run.requests import PlannedRequest, both
from devops_cli.github.ssh import key_requests

PUBLIC_KEY_PLACEHOLDER = "<public key>"


def plan_register(key_path: Path | str, title: str, condition: str = "") -> list[PlannedRequest]:
    """The two key registrations, the read of each listing that GitHub's 422 answer asks for,
    and the `git config` commands that point signing at `key_path`, in the order of the run.
    `condition`, when set, applies to every request."""
    requests: list[PlannedRequest] = []
    for endpoint, body in key_requests(PUBLIC_KEY_PLACEHOLDER, title):
        requests.append(
            PlannedRequest(
                method="POST",
                target=endpoint,
                stdin=json.dumps(body),
                condition=condition,
            )
        )
        requests.append(
            PlannedRequest(
                method="GET",
                target=endpoint,
                condition=both(condition, f"GitHub answers the POST {endpoint} with HTTP 422"),
                repeat="for each next page of the listing",
            )
        )
    requests.extend(
        PlannedRequest(method="git", target="config", argv=tuple(command), condition=condition)
        for command in git_signing_commands(Path(key_path))
    )
    return requests


def plan_rotate(key_path: Path, title: str) -> list[PlannedRequest]:
    """The requests of `plan_register` for the new key, which the run makes only when it
    rotates."""
    return plan_register(
        key_path,
        title,
        condition="the newest key is older than the rotation age or --force is set",
    )
