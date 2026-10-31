"""Planned requests for HashiCorp Vault commands in dry-run mode.

A dry run makes zero external requests and returns ordered PlannedRequest items (#412, #886).
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from devops_cli.config.constants import (
    CONST_VAULT_PATH_APPROLE_LOGIN,
    CONST_VAULT_PATH_HEALTH,
    CONST_VAULT_PATH_KUBERNETES_LOGIN,
    CONST_VAULT_PATH_LEASE_REVOKE,
    CONST_VAULT_PATH_TOKEN_REVOKE_SELF,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.security.vault_broker import parse_vault_uri
from devops_cli.security.vault_http import vault_url


def plan_vault_status(vault_addr: str) -> list[PlannedRequest]:
    """Generate planned requests for vault status."""
    return [
        PlannedRequest(
            method="GET",
            target=vault_url(vault_addr, CONST_VAULT_PATH_HEALTH),
        )
    ]


def plan_vault_get(path: str, vault_addr: str) -> list[PlannedRequest]:
    """Generate planned requests for vault get."""
    clean_path, _ = parse_vault_uri(path)
    return [
        PlannedRequest(
            method="GET",
            target=vault_url(vault_addr, clean_path),
        )
    ]


def plan_vault_set(
    path: str,
    keys: Sequence[str],
    vault_addr: str,
) -> list[PlannedRequest]:
    """Generate planned requests for vault set."""
    clean_path, _ = parse_vault_uri(path)
    payload = {k: "<value>" for k in keys}
    return [
        PlannedRequest(
            method="POST",
            target=vault_url(vault_addr, clean_path),
            stdin=json.dumps({"data": payload}),
        )
    ]


def plan_vault_sync(path: str, vault_addr: str) -> list[PlannedRequest]:
    """Generate planned requests for vault sync."""
    clean_path, _ = parse_vault_uri(path)
    return [
        PlannedRequest(
            method="GET",
            target=vault_url(vault_addr, clean_path),
        )
    ]


def _secret_placeholder() -> str:
    return "<secret-id>"


def plan_vault_login(
    method: str,
    *,
    role: str | None = None,
    role_id: str | None = None,
    vault_addr: str,
) -> list[PlannedRequest]:
    """Generate planned requests for vault login."""
    if method == "kubernetes":
        return [
            PlannedRequest(
                method="POST",
                target=vault_url(vault_addr, CONST_VAULT_PATH_KUBERNETES_LOGIN),
                stdin=json.dumps({"role": role or "<role>", "jwt": "<jwt>"}),
            )
        ]
    return [
        PlannedRequest(
            method="POST",
            target=vault_url(vault_addr, CONST_VAULT_PATH_APPROLE_LOGIN),
            stdin=json.dumps(
                {"role_id": role_id or "<role-id>", "secret_id": _secret_placeholder()}
            ),
        )
    ]


def plan_vault_logout(vault_addr: str) -> list[PlannedRequest]:
    """Generate planned requests for vault logout."""
    return [
        PlannedRequest(
            method="POST",
            target=vault_url(vault_addr, CONST_VAULT_PATH_TOKEN_REVOKE_SELF),
        )
    ]


def plan_vault_leases(revoke: str, vault_addr: str) -> list[PlannedRequest]:
    """Generate planned requests for vault leases."""
    return [
        PlannedRequest(
            method="POST",
            target=vault_url(vault_addr, CONST_VAULT_PATH_LEASE_REVOKE),
            stdin=json.dumps({"lease_id": revoke}),
        )
    ]
