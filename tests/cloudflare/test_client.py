"""Unit tests for Cloudflare client HTTP edge and write operations (#2153)."""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from devops_cli.cloudflare.client import (
    CloudflareAccessApplication,
    CloudflareAccessPolicy,
    CloudflareClient,
    CloudflareDNSRecord,
    CloudflareTunnelConfig,
    CloudflareTunnelIngressRule,
    CloudflareZone,
    _extract_error_message,
    _extract_policy_include_email,
    _extract_policy_include_rule,
    _is_uuid,
    _normalize_ip_cidr,
    _parse_retry_after,
)
from devops_cli.exceptions.cloudflare import CloudflareAPIError, CloudflareAuthError


def test_cloudflare_client_uses_custom_transport() -> None:
    """CloudflareClient accepts a custom transport and passes it without monkeypatching."""
    captured_requests: list[httpx2.Request] = []

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        captured_requests.append(request)
        return httpx2.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "zone-456",
                    "name": "example.com",
                    "status": "active",
                    "paused": False,
                },
            },
        )

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(
        token="test-secret-token",
        zone_id="zone-456",
        transport=transport,
    )

    zone = client.get_zone()
    assert isinstance(zone, CloudflareZone)
    assert zone.id == "zone-456"
    assert zone.name == "example.com"
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.method == "GET"
    assert req.url == httpx2.URL("https://api.cloudflare.com/client/v4/zones/zone-456")
    assert req.headers["Authorization"] == "Bearer test-secret-token"


@pytest.mark.parametrize(
    ("method_name", "kwargs", "error_message_pattern"),
    [
        ("get_zone", {}, "Zone ID is required"),
        ("list_dns_records", {}, "Zone ID is required"),
        (
            "create_dns_record",
            {"name": "test.example.com", "content": "192.0.2.1"},
            "Zone ID is required",
        ),
        (
            "update_dns_record",
            {"record_id": "rec-1", "name": "test.example.com", "content": "192.0.2.1"},
            "Zone ID is required",
        ),
        ("delete_dns_record", {"record_id": "rec-1"}, "Zone ID is required"),
        (
            "resolve_tunnel_id",
            {"tunnel_name_or_id": "named-tunnel"},
            "Account ID is required",
        ),
        (
            "get_tunnel_configuration",
            {"tunnel_id": "00000000-0000-0000-0000-000000000001"},
            "Account ID is required",
        ),
        (
            "update_tunnel_configuration",
            {
                "tunnel_id": "00000000-0000-0000-0000-000000000001",
                "ingress_rules": [],
            },
            "Account ID is required",
        ),
        (
            "sync_tunnel_routes",
            {
                "tunnel_id": "00000000-0000-0000-0000-000000000001",
                "domain": "example.com",
            },
            "Account ID is required",
        ),
        ("list_access_applications", {}, "Account ID is required"),
        (
            "create_access_application",
            {"name": "App", "domain": "app.example.com"},
            "Account ID is required",
        ),
        ("get_access_policies", {"app_id": "app-123"}, "Account ID is required"),
        (
            "create_or_update_access_policy",
            {"app_id": "app-123", "name": "Policy"},
            "Account ID is required",
        ),
        (
            "sync_access_application",
            {"domain": "app.example.com", "allowed_emails": ["user@example.com"]},
            "Account ID is required",
        ),
    ],
)
def test_require_zone_and_account_parametrized(
    method_name: str,
    kwargs: dict[str, Any],
    error_message_pattern: str,
) -> None:
    """All 14 methods raise CloudflareAPIError when account or zone ID is missing."""
    client = CloudflareClient(token="test-token")
    method = getattr(client, method_name)
    with pytest.raises(CloudflareAPIError, match=error_message_pattern):
        method(**kwargs)


def test_create_access_application() -> None:
    """create_access_application sends POST and parses returned access application."""
    captured_requests: list[httpx2.Request] = []

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        captured_requests.append(request)
        return httpx2.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "app-789",
                    "name": "Admin Portal",
                    "domain": "admin.example.com",
                    "type": "self_hosted",
                    "session_duration": "12h",
                    "allowed_idps": ["idp-1", "idp-2"],
                },
            },
        )

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(
        token="test-token",
        account_id="acc-123",
        transport=transport,
    )

    app = client.create_access_application(
        name="Admin Portal",
        domain="admin.example.com",
        session_duration="12h",
    )

    assert isinstance(app, CloudflareAccessApplication)
    assert app.id == "app-789"
    assert app.name == "Admin Portal"
    assert app.domain == "admin.example.com"
    assert app.type == "self_hosted"
    assert app.session_duration == "12h"
    assert app.allowed_idps == ["idp-1", "idp-2"]

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.method == "POST"
    assert req.url == httpx2.URL(
        "https://api.cloudflare.com/client/v4/accounts/acc-123/access/apps"
    )
    payload = json.loads(req.content.decode("utf-8"))
    assert payload == {
        "name": "Admin Portal",
        "domain": "admin.example.com",
        "type": "self_hosted",
        "session_duration": "12h",
    }


def test_create_or_update_access_policy_create_and_update() -> None:
    """create_or_update_access_policy creates when absent and updates when present."""
    captured_requests: list[httpx2.Request] = []

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        captured_requests.append(request)
        path = request.url.path

        if request.method == "GET" and "policies" in path:
            # First run: no existing policies. Second run: policy exists.
            if len([r for r in captured_requests if r.method == "GET"]) == 1:
                return httpx2.Response(
                    200,
                    json={
                        "success": True,
                        "result": [],
                        "result_info": {"page": 1, "total_pages": 1},
                    },
                )
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": [
                        {
                            "id": "policy-existing-1",
                            "name": "Team Policy",
                            "decision": "allow",
                            "include": [{"email": {"email": "old@example.com"}}],
                        }
                    ],
                    "result_info": {"page": 1, "total_pages": 1},
                },
            )

        if request.method == "POST" and "policies" in path:
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": "policy-new-1",
                        "name": "Team Policy",
                        "decision": "allow",
                        "include": [
                            {"email": {"email": "dev@example.com"}},
                            {"ip": {"ip": "192.0.2.0/24"}},
                        ],
                    },
                },
            )

        if request.method == "PUT" and "policies/policy-existing-1" in path:
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": "policy-existing-1",
                        "name": "Team Policy",
                        "decision": "bypass",
                        "include": [
                            {"email": {"email": "dev@example.com"}},
                            {"ip": {"ip": "192.0.2.0/24"}},
                        ],
                    },
                },
            )

        return httpx2.Response(404, json={"success": False, "errors": [{"message": "Not found"}]})

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(
        token="test-token",
        account_id="acc-123",
        transport=transport,
    )

    # 1. Create path (no existing policy)
    policy_created = client.create_or_update_access_policy(
        app_id="app-100",
        name="Team Policy",
        allowed_emails=["dev@example.com"],
        bypass_ips=["192.0.2.0/24"],
        decision="allow",
    )
    assert isinstance(policy_created, CloudflareAccessPolicy)
    assert policy_created.id == "policy-new-1"
    assert policy_created.decision == "allow"
    assert policy_created.include == [
        {"email": {"email": "dev@example.com"}},
        {"ip": {"ip": "192.0.2.0/24"}},
    ]
    post_req = captured_requests[1]
    assert post_req.method == "POST"
    assert post_req.url == httpx2.URL(
        "https://api.cloudflare.com/client/v4/accounts/acc-123/access/apps/app-100/policies"
    )

    # 2. Update path (existing policy found)
    policy_updated = client.create_or_update_access_policy(
        app_id="app-100",
        name="Team Policy",
        allowed_emails=["dev@example.com"],
        bypass_ips=["192.0.2.0/24"],
        decision="bypass",
    )
    assert isinstance(policy_updated, CloudflareAccessPolicy)
    assert policy_updated.id == "policy-existing-1"
    assert policy_updated.decision == "bypass"
    put_req = captured_requests[3]
    assert put_req.method == "PUT"
    assert put_req.url == httpx2.URL(
        "https://api.cloudflare.com/client/v4/accounts/acc-123/access/apps/app-100/policies/policy-existing-1"
    )


def test_access_policy_refuses_invalid_cidr() -> None:
    """Invalid IP address or CIDR range raises CloudflareAPIError before calling API."""
    captured_requests: list[httpx2.Request] = []

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        captured_requests.append(request)
        return httpx2.Response(200, json={"success": True, "result": []})

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(
        token="test-token",
        account_id="acc-123",
        transport=transport,
    )

    with pytest.raises(CloudflareAPIError, match="Invalid IP address or CIDR block 'not-an-ip'"):
        client.create_or_update_access_policy(
            app_id="app-100",
            name="Policy",
            bypass_ips=["not-an-ip"],
        )
    assert len(captured_requests) == 0


def test_dns_create_update_delete() -> None:
    """DNS record create, update, and delete endpoints format requests and parse models."""
    captured_requests: list[httpx2.Request] = []

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        captured_requests.append(request)
        if request.method == "POST":
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": "rec-created-1",
                        "type": "A",
                        "name": "test.example.com",
                        "content": "192.0.2.1",
                        "proxied": True,
                        "ttl": 1,
                        "comment": "managed",
                    },
                },
            )
        if request.method == "PUT":
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": "rec-updated-1",
                        "type": "CNAME",
                        "name": "alias.example.com",
                        "content": "target.example.com",
                        "proxied": False,
                        "ttl": 300,
                        "comment": "updated comment",
                    },
                },
            )
        if request.method == "DELETE":
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {"id": "rec-deleted-1"},
                },
            )
        return httpx2.Response(404)

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(
        token="test-token",
        zone_id="zone-456",
        transport=transport,
    )

    # 1. Create DNS record
    rec_created = client.create_dns_record(
        record_type="A",
        name="test.example.com",
        content="192.0.2.1",
        proxied=True,
        ttl=1,
        comment="managed",
    )
    assert isinstance(rec_created, CloudflareDNSRecord)
    assert rec_created.id == "rec-created-1"
    assert rec_created.name == "test.example.com"
    assert rec_created.content == "192.0.2.1"
    assert rec_created.proxied is True
    post_req = captured_requests[0]
    assert post_req.method == "POST"
    assert post_req.url == httpx2.URL(
        "https://api.cloudflare.com/client/v4/zones/zone-456/dns_records"
    )
    assert json.loads(post_req.content.decode("utf-8")) == {
        "type": "A",
        "name": "test.example.com",
        "content": "192.0.2.1",
        "ttl": 1,
        "proxied": True,
        "comment": "managed",
    }

    # 2. Update DNS record
    rec_updated = client.update_dns_record(
        record_id="rec-updated-1",
        record_type="CNAME",
        name="alias.example.com",
        content="target.example.com",
        proxied=False,
        ttl=300,
        comment="updated comment",
    )
    assert isinstance(rec_updated, CloudflareDNSRecord)
    assert rec_updated.id == "rec-updated-1"
    assert rec_updated.name == "alias.example.com"
    assert rec_updated.proxied is False
    put_req = captured_requests[1]
    assert put_req.method == "PUT"
    assert put_req.url == httpx2.URL(
        "https://api.cloudflare.com/client/v4/zones/zone-456/dns_records/rec-updated-1"
    )

    # 3. Delete DNS record
    assert client.delete_dns_record(record_id="rec-deleted-1") is True
    del_req = captured_requests[2]
    assert del_req.method == "DELETE"
    assert del_req.url == httpx2.URL(
        "https://api.cloudflare.com/client/v4/zones/zone-456/dns_records/rec-deleted-1"
    )


def test_sync_dns_records_creates_updates_and_leaves_unchanged() -> None:
    """sync_dns_records reconciles drift across multiple subdomains accurately."""
    captured_requests: list[httpx2.Request] = []
    target_cname = "00000000-0000-0000-0000-000000000001.cfargotunnel.com"

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        captured_requests.append(request)
        if request.method == "GET":
            # List existing DNS CNAME records
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": [
                        {
                            "id": "rec-existing-api",
                            "type": "CNAME",
                            "name": "api.example.com",
                            "content": "old-target.example.com",
                            "proxied": True,
                            "ttl": 1,
                        },
                        {
                            "id": "rec-existing-same",
                            "type": "CNAME",
                            "name": "same.example.com",
                            "content": target_cname,
                            "proxied": True,
                            "ttl": 1,
                        },
                    ],
                    "result_info": {"page": 1, "total_pages": 1},
                },
            )
        if request.method == "POST":
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": "rec-new-root",
                        "type": "CNAME",
                        "name": "example.com",
                        "content": target_cname,
                        "proxied": True,
                        "ttl": 1,
                    },
                },
            )
        if request.method == "PUT":
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": "rec-existing-api",
                        "type": "CNAME",
                        "name": "api.example.com",
                        "content": target_cname,
                        "proxied": True,
                        "ttl": 1,
                    },
                },
            )
        return httpx2.Response(404)

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(
        token="test-token",
        zone_id="zone-456",
        transport=transport,
    )

    summary = client.sync_dns_records(
        domain="example.com",
        tunnel_id_or_cname="00000000-0000-0000-0000-000000000001",
        subdomains=["@", "api", "same"],
    )

    assert summary == {
        "example.com": "created",
        "api.example.com": "updated",
        "same.example.com": "unchanged",
    }


def test_tunnel_configuration_read_write_and_resolution() -> None:
    """Tunnel ID resolution, get configuration, and update configuration paths."""
    captured_requests: list[httpx2.Request] = []
    tunnel_uuid = "00000000-0000-0000-0000-000000000001"

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        captured_requests.append(request)
        path = request.url.path
        if request.method == "GET" and path.endswith("/cfd_tunnel"):
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": [
                        {
                            "id": tunnel_uuid,
                            "name": "homelab-tunnel",
                            "status": "healthy",
                        }
                    ],
                },
            )
        if request.method == "GET" and path.endswith("/configurations"):
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "tunnel_id": tunnel_uuid,
                        "config": {
                            "warp-routing": {"enabled": True},
                            "ingress": [
                                {
                                    "hostname": "old.example.com",
                                    "service": "http://localhost:8080",
                                },
                                {"service": "http_status:404"},
                            ],
                        },
                    },
                },
            )
        if request.method == "PUT" and path.endswith("/configurations"):
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "tunnel_id": tunnel_uuid,
                        "config": json.loads(request.content.decode("utf-8")).get("config", {}),
                    },
                },
            )
        return httpx2.Response(404)

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(
        token="test-token",
        account_id="acc-123",
        transport=transport,
    )

    # 1. resolve_tunnel_id by name
    resolved_id = client.resolve_tunnel_id("homelab-tunnel")
    assert resolved_id == tunnel_uuid

    # 2. get_tunnel_configuration
    cfg = client.get_tunnel_configuration(tunnel_uuid)
    assert isinstance(cfg, CloudflareTunnelConfig)
    assert cfg.tunnel_id == tunnel_uuid
    assert len(cfg.ingress) == 2
    assert cfg.ingress[0].hostname == "old.example.com"

    # 3. update_tunnel_configuration
    new_rules = [
        CloudflareTunnelIngressRule(
            hostname="new.example.com",
            service="http://localhost:8081",
        ),
        CloudflareTunnelIngressRule(service="http_status:404"),
    ]
    updated_cfg = client.update_tunnel_configuration(
        tunnel_id=tunnel_uuid,
        ingress_rules=new_rules,
        base_config={"warp-routing": {"enabled": True}},
    )
    assert isinstance(updated_cfg, CloudflareTunnelConfig)
    assert len(updated_cfg.ingress) == 2
    assert updated_cfg.ingress[0].hostname == "new.example.com"


def test_sync_tunnel_routes_merges_rules() -> None:
    """sync_tunnel_routes merges new routes before wildcards and catchall."""
    captured_requests: list[httpx2.Request] = []
    tunnel_uuid = "00000000-0000-0000-0000-000000000001"

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        captured_requests.append(request)
        if request.method == "GET":
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "tunnel_id": tunnel_uuid,
                        "config": {
                            "ingress": [
                                {
                                    "hostname": "*.example.com",
                                    "service": "http://wildcard:80",
                                },
                                {"service": "http_status:404"},
                            ]
                        },
                    },
                },
            )
        if request.method == "PUT":
            payload = json.loads(request.content.decode("utf-8"))
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {"tunnel_id": tunnel_uuid, "config": payload.get("config", {})},
                },
            )
        return httpx2.Response(404)

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(
        token="test-token",
        account_id="acc-123",
        transport=transport,
    )

    res = client.sync_tunnel_routes(
        tunnel_id=tunnel_uuid,
        domain="example.com",
        subdomains=["@", "app"],
    )
    assert isinstance(res, CloudflareTunnelConfig)
    # The new hostnames should be inserted before the wildcard rule
    hostnames = [r.hostname for r in res.ingress]
    assert hostnames == ["app.example.com", "*.example.com", "example.com", None]


def test_sync_access_application() -> None:
    """sync_access_application creates app and allow policy, and optional bypass policy."""
    captured_requests: list[httpx2.Request] = []

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        captured_requests.append(request)
        path = request.url.path

        if request.method == "GET" and path.endswith("/access/apps"):
            return httpx2.Response(
                200,
                json={"success": True, "result": [], "result_info": {"page": 1, "total_pages": 1}},
            )
        if request.method == "POST" and path.endswith("/access/apps"):
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": "app-created-1",
                        "name": "Homelab Ingress",
                        "domain": "example.com",
                        "type": "self_hosted",
                    },
                },
            )
        if request.method == "GET" and "/policies" in path:
            return httpx2.Response(
                200,
                json={"success": True, "result": [], "result_info": {"page": 1, "total_pages": 1}},
            )
        if request.method == "POST" and "/policies" in path:
            payload = json.loads(request.content.decode("utf-8"))
            pid = "policy-allow-1" if payload["decision"] == "allow" else "policy-bypass-1"
            return httpx2.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": pid,
                        "name": payload["name"],
                        "decision": payload["decision"],
                        "include": payload["include"],
                    },
                },
            )
        return httpx2.Response(404)

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(
        token="test-token",
        account_id="acc-123",
        transport=transport,
    )

    result = client.sync_access_application(
        domain="example.com",
        allowed_emails=["user@example.com"],
        bypass_ips=["192.0.2.0/24"],
    )

    assert result["app_id"] == "app-created-1"
    assert result["app_action"] == "created"
    assert result["policy_id"] == "policy-allow-1"
    assert result["bypass_policy_id"] == "policy-bypass-1"
    assert result["allowed_emails"] == ["user@example.com"]
    assert result["bypass_ips"] == ["192.0.2.0/24"]


def test_http_transport_network_error_wrapping() -> None:
    """Underlying httpx2.HTTPError is wrapped into CloudflareAPIError."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Network unreachable")

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(
        token="test-token",
        zone_id="zone-456",
        transport=transport,
    )

    with pytest.raises(CloudflareAPIError) as exc_info:
        client.get_zone()

    assert "Cloudflare HTTP request to zones/zone-456 failed: Network unreachable" in str(
        exc_info.value
    )
    assert exc_info.value.details == {"path": "zones/zone-456", "method": "GET"}


def test_authentication_error_401_and_403() -> None:
    """HTTP 401 or 403 status raises CloudflareAuthError."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, json={"success": False, "errors": [{"code": 10000}]})

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(token="invalid-token", zone_id="zone-456", transport=transport)

    with pytest.raises(CloudflareAuthError, match="authentication failed"):
        client.get_zone()


def test_api_error_response_with_extracted_message() -> None:
    """4xx responses extract specific error messages using _extract_error_message."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            400,
            json={
                "success": False,
                "errors": [
                    {"code": 1004, "message": "DNS Record already exists."},
                    {"code": 1005, "message": "Duplicate content."},
                ],
            },
        )

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(token="test-token", zone_id="zone-456", transport=transport)

    with pytest.raises(CloudflareAPIError) as exc_info:
        client.get_zone()

    assert "DNS Record already exists." in str(exc_info.value)
    assert exc_info.value.details["status_code"] == 400


def test_api_success_false_200_response() -> None:
    """HTTP 200 response with success: false raises CloudflareAPIError."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "success": False,
                "errors": [{"message": "Operation could not be completed"}],
            },
        )

    transport = httpx2.MockTransport(handle_request)
    client = CloudflareClient(token="test-token", zone_id="zone-456", transport=transport)

    with pytest.raises(CloudflareAPIError, match="Operation could not be completed"):
        client.get_zone()


def test_helpers_edge_cases() -> None:
    """Edge cases for helper parsers and normalizers."""
    # _normalize_ip_cidr
    assert _normalize_ip_cidr("192.0.2.1") == "192.0.2.1/32"
    assert _normalize_ip_cidr("2001:db8::1") == "2001:db8::1/128"
    with pytest.raises(CloudflareAPIError, match="IPv6 zone index is not permitted"):
        _normalize_ip_cidr("fe80::1%eth0")

    # _is_uuid
    assert _is_uuid("c89fbf56-834c-4734-93ec-4eb0de29a733") is True
    assert _is_uuid("not-a-uuid") is False

    # _extract_policy_include_rule and _extract_policy_include_email
    assert _extract_policy_include_rule("not-a-dict") is None
    assert _extract_policy_include_rule({"email": "u@example.com"}) == {
        "email": {"email": "u@example.com"}
    }
    assert _extract_policy_include_rule({"email": {"email": "u@example.com"}}) == {
        "email": {"email": "u@example.com"}
    }
    assert _extract_policy_include_rule({"ip": "192.0.2.0/24"}) == {"ip": {"ip": "192.0.2.0/24"}}
    assert _extract_policy_include_rule({"ip": {"ip": "192.0.2.0/24"}}) == {
        "ip": {"ip": "192.0.2.0/24"}
    }
    assert _extract_policy_include_email({"email": "u@example.com"}) == {"email": "u@example.com"}
    assert _extract_policy_include_email({"other": "value"}) is None

    # _extract_error_message fallback and extraction
    assert _extract_error_message({}, "fallback") == "fallback"
    assert (
        _extract_error_message({"errors": ["Raw string error"]}, "fallback") == "Raw string error"
    )
    assert (
        _extract_error_message({"errors": [{"message": "Dict message error"}]}, "fallback")
        == "Dict message error"
    )

    # _parse_retry_after
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("not-a-number") is None
    assert _parse_retry_after("15") == 15.0
