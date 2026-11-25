"""Dry-run request plans for `devops store` subcommands (#412)."""

from __future__ import annotations

from collections.abc import Sequence

from devops_cli.dry_run.requests import PlannedRequest

_PLACEHOLDER_ENDPOINT = "<store.s3_endpoint>"
_PLACEHOLDER_KEY = "<bucket>/<kind-prefix><key>"


def plan_store_publish(kind: str, source: str, *, key: str | None = None) -> list[PlannedRequest]:
    """Return planned S3 and keyring operations for `devops store publish`."""
    target_key = key or "<filename>"
    return [
        PlannedRequest(method="keyring", target="store.access_key_id / store.secret_access_key"),
        PlannedRequest(method="S3 HEAD", target=f"{_PLACEHOLDER_ENDPOINT}/<{kind}>/{target_key}"),
        PlannedRequest(
            method="S3 PUT",
            target=f"{_PLACEHOLDER_ENDPOINT}/<{kind}>/{target_key} (from {source})",
            condition="remote sha256 differs",
        ),
        PlannedRequest(
            method="S3 LIST+PUT",
            target=f"{_PLACEHOLDER_ENDPOINT}/<{kind}>/index.{{json,html}}",
            condition="upload succeeded",
        ),
    ]


def plan_store_sync() -> list[PlannedRequest]:
    """Return planned requests for `devops store sync`."""
    return [
        PlannedRequest(method="keyring", target="store.access_key_id / store.secret_access_key"),
        PlannedRequest(
            method="S3 HEAD+PUT",
            target=f"{_PLACEHOLDER_ENDPOINT}/{_PLACEHOLDER_KEY}",
            repeat="once per entry in store/pending.jsonl",
        ),
    ]


def plan_store_ls(kind: str, *, prefix: str = "") -> list[PlannedRequest]:
    """Return planned requests for `devops store ls`."""
    return [
        PlannedRequest(method="keyring", target="store.access_key_id / store.secret_access_key"),
        PlannedRequest(
            method="S3 LIST",
            target=f"{_PLACEHOLDER_ENDPOINT}/<{kind}>/{prefix}",
        ),
    ]


def plan_store_get(kind: str, key: str) -> list[PlannedRequest]:
    """Return planned requests for `devops store get`."""
    return [
        PlannedRequest(method="keyring", target="store.access_key_id / store.secret_access_key"),
        PlannedRequest(method="S3 GET", target=f"{_PLACEHOLDER_ENDPOINT}/<{kind}>/{key}"),
    ]


def plan_store_url(kind: str, key: str) -> list[PlannedRequest]:
    """Return planned local resolution steps for `devops store url`."""
    return [
        PlannedRequest(
            method="CONFIG",
            target=f"<store.web_base_url>/<{kind}>/{key}",
            condition="kind visibility is web",
        ),
    ]


def plan_store_presign(kind: str, key: str, *, expires_in: int) -> list[PlannedRequest]:
    """Return planned local signing steps for `devops store presign`."""
    return [
        PlannedRequest(method="keyring", target="store.access_key_id / store.secret_access_key"),
        PlannedRequest(
            method="SIGV4 PRESIGN",
            target=f"{_PLACEHOLDER_ENDPOINT}/<{kind}>/{key}?X-Amz-Expires={expires_in}",
        ),
    ]


def plan_store_doctor(extra_endpoints: Sequence[str] = ()) -> list[PlannedRequest]:
    """Return planned canary requests for `devops store doctor`."""
    endpoints = [_PLACEHOLDER_ENDPOINT, *extra_endpoints]
    requests: list[PlannedRequest] = [
        PlannedRequest(method="keyring", target="store.access_key_id / store.secret_access_key"),
    ]
    for endpoint in endpoints:
        target = f"{endpoint}/reports-private/sessions/.doctor-canary/<uuid>.json"
        requests.extend(
            [
                PlannedRequest(method="S3 PUT", target=target),
                PlannedRequest(
                    method="S3 LIST", target=f"{endpoint}/reports-private/sessions/.doctor-canary/"
                ),
                PlannedRequest(method="S3 GET", target=target),
                PlannedRequest(method="SIGV4 PRESIGN", target=target),
                PlannedRequest(method="S3 DELETE", target=target),
            ]
        )
    return requests
