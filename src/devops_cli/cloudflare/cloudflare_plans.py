"""Planned requests for Cloudflare commands in dry-run mode.

A dry run makes zero external requests and returns ordered PlannedRequest items (#412, #886).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from urllib.parse import urlencode

from devops_cli.cloudflare.client import (
    _build_dns_records_params,
    _build_policy_include_rules,
    _is_uuid,
)
from devops_cli.config.constants import (
    CONST_CLOUDFLARE_ALLOW_POLICY_NAME,
    CONST_CLOUDFLARE_BYPASS_POLICY_NAME,
    CONST_CLOUDFLARE_CATCHALL_SERVICE,
    CONST_CLOUDFLARE_CFARGOTUNNEL_SUFFIX,
    CONST_CLOUDFLARE_DEFAULT_SERVICE,
    CONST_CLOUDFLARE_DEFAULT_SESSION_DURATION,
    CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS,
    CONST_CLOUDFLARE_RECORD_COMMENT,
    CONST_URL_CLOUDFLARE_API_BASE,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.telemetry.service_status import service_status_requests


def _format_subdomain(sub: str, domain: str) -> str:
    """Format full hostname for a given subdomain and domain."""
    if sub == "@":
        return domain
    if sub == "*":
        return f"*.{domain}"
    return f"{sub}.{domain}"


def plan_cloudflare_status(
    account_id: str | None = None,
    zone_id: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for inspecting Cloudflare status."""
    requests = [
        PlannedRequest(
            method="GET",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/user/tokens/verify",
        )
    ]
    zid = zone_id or "<zone-id>"
    requests.append(
        PlannedRequest(
            method="GET",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/zones/{zid}",
            condition="when zone ID is configured or passed",
        )
    )
    return requests


def plan_cloudflare_service_status() -> list[PlannedRequest]:
    """Generate planned requests for Cloudflare operational service status."""
    return service_status_requests(("cloudflare",))


def plan_cloudflare_dns_list(
    zone_id: str | None = None,
    record_type: str | None = None,
    name: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for listing DNS records."""
    zid = zone_id or "<zone-id>"
    params = _build_dns_records_params(record_type, name)
    query = urlencode(params)
    target = f"{CONST_URL_CLOUDFLARE_API_BASE}/zones/{zid}/dns_records?{query}"
    return [
        PlannedRequest(
            method="GET",
            target=target,
        )
    ]


def plan_cloudflare_dns_sync(
    domain: str,
    tunnel_id_or_cname: str,
    subdomains: Sequence[str] | None = None,
    zone_id: str | None = None,
    account_id: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for synchronizing DNS records to a tunnel."""
    requests: list[PlannedRequest] = []
    aid = account_id or "<account-id>"
    zid = zone_id or "<zone-id>"

    if CONST_CLOUDFLARE_CFARGOTUNNEL_SUFFIX in tunnel_id_or_cname:
        target_cname = tunnel_id_or_cname
    elif _is_uuid(tunnel_id_or_cname):
        target_cname = f"{tunnel_id_or_cname}{CONST_CLOUDFLARE_CFARGOTUNNEL_SUFFIX}"
    else:
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/cfd_tunnel?name={tunnel_id_or_cname}&is_deleted=false",
            )
        )
        target_cname = f"<tunnel-id>{CONST_CLOUDFLARE_CFARGOTUNNEL_SUFFIX}"

    dns_params = urlencode({"per_page": 100, "page": 1, "type": "CNAME"})
    requests.append(
        PlannedRequest(
            method="GET",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/zones/{zid}/dns_records?{dns_params}",
        )
    )

    subs = subdomains if subdomains is not None else CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS
    for sub in subs:
        rec_name = _format_subdomain(sub, domain)
        payload = json.dumps(
            {
                "type": "CNAME",
                "name": rec_name,
                "content": target_cname,
                "proxied": True,
                "ttl": 1,
                "comment": CONST_CLOUDFLARE_RECORD_COMMENT,
            },
            indent=2,
        )
        requests.append(
            PlannedRequest(
                method="POST",
                target=f"{CONST_URL_CLOUDFLARE_API_BASE}/zones/{zid}/dns_records",
                stdin=payload,
                condition=f"when DNS record '{rec_name}' does not exist",
            )
        )
        requests.append(
            PlannedRequest(
                method="PUT",
                target=f"{CONST_URL_CLOUDFLARE_API_BASE}/zones/{zid}/dns_records/<record-id>",
                stdin=payload,
                condition=f"when DNS record '{rec_name}' drifts from '{target_cname}'",
            )
        )
    return requests


def plan_cloudflare_dns_delete(
    targets: Sequence[str],
    domain: str | None = None,
    zone_id: str | None = None,
    record_type: str | None = None,
    force: bool = False,
) -> list[PlannedRequest]:
    """Generate planned requests for deleting DNS records."""
    zid = zone_id or "<zone-id>"
    params: dict[str, str | int] = {"per_page": 100, "page": 1}
    if record_type:
        params["type"] = record_type
    query = urlencode(params)
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="GET",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/zones/{zid}/dns_records?{query}",
        )
    ]
    for target in targets:
        requests.append(
            PlannedRequest(
                method="DELETE",
                target=f"{CONST_URL_CLOUDFLARE_API_BASE}/zones/{zid}/dns_records/<record-id>",
                condition=f"when DNS record matching '{target}' exists",
            )
        )
    return requests


def plan_cloudflare_tunnel_routes(
    tunnel_id: str,
    account_id: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for retrieving tunnel ingress routes."""
    requests: list[PlannedRequest] = []
    aid = account_id or "<account-id>"
    if not _is_uuid(tunnel_id):
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/cfd_tunnel?name={tunnel_id}&is_deleted=false",
            )
        )
        resolved_id = "<tunnel-id>"
    else:
        resolved_id = tunnel_id

    requests.append(
        PlannedRequest(
            method="GET",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/cfd_tunnel/{resolved_id}/configurations",
        )
    )
    return requests


def plan_cloudflare_tunnel_sync(
    tunnel_id: str,
    domain: str,
    service: str = CONST_CLOUDFLARE_DEFAULT_SERVICE,
    subdomains: Sequence[str] | None = None,
    account_id: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for synchronizing tunnel ingress configuration."""
    requests: list[PlannedRequest] = []
    aid = account_id or "<account-id>"
    if not _is_uuid(tunnel_id):
        requests.append(
            PlannedRequest(
                method="GET",
                target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/cfd_tunnel?name={tunnel_id}&is_deleted=false",
            )
        )
        resolved_id = "<tunnel-id>"
    else:
        resolved_id = tunnel_id

    requests.append(
        PlannedRequest(
            method="GET",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/cfd_tunnel/{resolved_id}/configurations",
        )
    )

    subs = subdomains if subdomains is not None else CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS
    ingress_payload = [
        {"service": service, "hostname": _format_subdomain(sub, domain)} for sub in subs
    ]
    ingress_payload.append({"service": CONST_CLOUDFLARE_CATCHALL_SERVICE})
    put_body = json.dumps({"config": {"ingress": ingress_payload}}, indent=2)

    requests.append(
        PlannedRequest(
            method="PUT",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/cfd_tunnel/{resolved_id}/configurations",
            stdin=put_body,
        )
    )
    return requests


def plan_cloudflare_access_status(
    account_id: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for listing Cloudflare Access applications."""
    aid = account_id or "<account-id>"
    params = urlencode({"per_page": 20, "page": 1})
    return [
        PlannedRequest(
            method="GET",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/access/apps?{params}",
        )
    ]


def plan_cloudflare_access_sync(
    domain: str,
    allowed_emails: Sequence[str] | None = None,
    bypass_ips: Sequence[str] | None = None,
    account_id: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for synchronizing Cloudflare Access application and policies."""
    aid = account_id or "<account-id>"
    params = urlencode({"per_page": 20, "page": 1})
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="GET",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/access/apps?{params}",
        )
    ]

    app_payload = json.dumps(
        {
            "name": "Homelab Ingress",
            "domain": domain,
            "type": "self_hosted",
            "session_duration": CONST_CLOUDFLARE_DEFAULT_SESSION_DURATION,
        },
        indent=2,
    )
    requests.append(
        PlannedRequest(
            method="POST",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/access/apps",
            stdin=app_payload,
            condition=f"when application for domain '{domain}' does not exist",
        )
    )

    requests.append(
        PlannedRequest(
            method="GET",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/access/apps/<app-id>/policies",
        )
    )

    allow_rules = _build_policy_include_rules(allowed_emails, None)
    allow_payload = json.dumps(
        {
            "name": CONST_CLOUDFLARE_ALLOW_POLICY_NAME,
            "decision": "allow",
            "include": allow_rules,
        },
        indent=2,
    )
    requests.append(
        PlannedRequest(
            method="POST",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/access/apps/<app-id>/policies",
            stdin=allow_payload,
            condition=f"when policy '{CONST_CLOUDFLARE_ALLOW_POLICY_NAME}' does not exist",
        )
    )
    requests.append(
        PlannedRequest(
            method="PUT",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/access/apps/<app-id>/policies/<policy-id>",
            stdin=allow_payload,
            condition=f"when policy '{CONST_CLOUDFLARE_ALLOW_POLICY_NAME}' exists",
        )
    )

    if bypass_ips:
        bypass_rules = _build_policy_include_rules(None, bypass_ips)
        bypass_payload = json.dumps(
            {
                "name": CONST_CLOUDFLARE_BYPASS_POLICY_NAME,
                "decision": "bypass",
                "include": bypass_rules,
            },
            indent=2,
        )
        requests.append(
            PlannedRequest(
                method="POST",
                target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/access/apps/<app-id>/policies",
                stdin=bypass_payload,
                condition=f"when policy '{CONST_CLOUDFLARE_BYPASS_POLICY_NAME}' does not exist",
            )
        )
        requests.append(
            PlannedRequest(
                method="PUT",
                target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/access/apps/<app-id>/policies/<bypass-policy-id>",
                stdin=bypass_payload,
                condition=f"when policy '{CONST_CLOUDFLARE_BYPASS_POLICY_NAME}' exists",
            )
        )

    return requests


def plan_cloudflare_access_policies(
    app_id: str,
    account_id: str | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for retrieving Access policies."""
    aid = account_id or "<account-id>"
    return [
        PlannedRequest(
            method="GET",
            target=f"{CONST_URL_CLOUDFLARE_API_BASE}/accounts/{aid}/access/apps/{app_id}/policies",
        )
    ]
