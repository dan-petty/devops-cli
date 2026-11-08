"""Unit tests for Cloudflare client and CLI commands."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.cloudflare.client import CloudflareClient
from devops_cli.exceptions.cloudflare import CloudflareAPIError, CloudflareAuthError
from tests.support.fakes.dial import record_connects
from tests.support.fakes.dns import DnsFake
from tests.support.fakes.http import RecordedRequest, WebFake

API_PATH = "/client/v4"
ACCOUNT = "test-account-123"
ZONE = "test-zone-456"
TUNNEL_ID = "a40935f3-b56c-4a96-a7a5-a409ff330b0a"
APPS = f"/accounts/{ACCOUNT}/access/apps"
MANAGED = "Managed by devops-cli"


def envelope(result: Any) -> dict[str, Any]:
    """The body that the Cloudflare API v4 wraps around every result."""
    return {"success": True, "result": result}


def created(identifier: str) -> Callable[[httpx2.Request], httpx2.Response]:
    """An answer that echoes the posted body as a new object with the given id."""

    def answer(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200, json=envelope({**json.loads(request.content), "id": identifier})
        )

    return answer


def echo_configuration(request: httpx2.Request) -> httpx2.Response:
    """The answer of the API to a PUT of a tunnel configuration: the stored configuration."""
    config = json.loads(request.content)["config"]
    return httpx2.Response(200, json=envelope({"config": config, "version": 2}))


def cloudflare_api(web: WebFake, routes: Mapping[tuple[str, str], Any]) -> None:
    """Serve `routes` as the Cloudflare API v4: a (method, path) pair answers with its result in
    the API's envelope, or with the response that a callable gives. A path with no route answers
    404, so a request the test did not expect fails the test."""

    def serve(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path.removeprefix(API_PATH)
        if (key := (request.method, path)) not in routes:
            message = f"{request.method} {path} is not served"
            return httpx2.Response(404, json={"success": False, "errors": [{"message": message}]})
        answer = routes[key]
        return answer(request) if callable(answer) else httpx2.Response(200, json=envelope(answer))

    web.serve(serve)


def sent(web: WebFake, method: str) -> list[RecordedRequest]:
    """The requests of one method that the API received, in order."""
    return [request for request in web.recorded if request.method == method]


def deleted_ids(web: WebFake) -> list[str]:
    """The record IDs a command deleted, in order."""
    return [request.url.rsplit("/", 1)[1] for request in sent(web, "DELETE")]


@pytest.fixture
def cloudflare_zone(
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    keyring_store: Any,
    web: WebFake,
) -> WebFake:
    """The settings of a zone with standardized dummy hostnames, an API token, and the web fake."""
    config(
        cloudflare={
            "domain": "example.com",
            "tunnel": "homelab",
            "account_id": ACCOUNT,
            "zone_id": ZONE,
        }
    )
    monkeypatch.setenv("DEVOPS_CLI_CLOUDFLARE_API_TOKEN", "cf-test")
    return web


def test_cloudflare_client_verify_token_success(web: WebFake) -> None:
    """Verify successful token verification."""
    client = CloudflareClient(token="test-token")
    reply = {
        "success": True,
        "result": {"id": "token-id-1", "status": "active"},
    }
    web.serve(lambda request: httpx2.Response(200, json=reply))
    res = client.verify_token()
    assert (res.id, res.status) == ("token-id-1", "active")


def test_cloudflare_client_auth_error(web: WebFake) -> None:
    """Verify authentication failure raises CloudflareAuthError."""
    client = CloudflareClient(token="invalid-token")
    web.serve(lambda request: httpx2.Response(401, json={}))
    with pytest.raises(CloudflareAuthError) as raised:
        client.verify_token()
    assert raised.value.error_code == "CLOUDFLARE_AUTH_ERROR"


def test_cloudflare_client_get_zone(web: WebFake) -> None:
    """Verify zone details retrieval."""
    client = CloudflareClient(token="test-token", zone_id="zone-123")
    reply = {
        "success": True,
        "result": {
            "id": "zone-123",
            "name": "example.com",
            "status": "active",
            "paused": False,
            "name_servers": ["ns1", "ns2"],
        },
    }
    web.serve(lambda request: httpx2.Response(200, json=reply))
    zone = client.get_zone()
    assert (zone.id, zone.name, zone.status, zone.name_servers) == (
        "zone-123",
        "example.com",
        "active",
        ["ns1", "ns2"],
    )


def test_cloudflare_client_list_dns_records(web: WebFake) -> None:
    """Verify listing DNS records."""
    client = CloudflareClient(token="test-token", zone_id="zone-123")
    reply = {
        "success": True,
        "result": [
            {
                "id": "rec-1",
                "type": "CNAME",
                "name": "example.com",
                "content": "target.cfargotunnel.com",
                "proxiable": True,
                "proxied": True,
                "ttl": 1,
            }
        ],
    }
    web.serve(lambda request: httpx2.Response(200, json=reply))
    records = client.list_dns_records()
    assert (len(records), records[0].name, records[0].proxied) == (1, "example.com", True)


def test_cloudflare_client_resolve_tunnel_id_by_name(web: WebFake) -> None:
    """Verify resolution of named tunnel to UUID."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    reply = {
        "success": True,
        "result": [{"id": "a40935f3-b56c-4a96-a7a5-a409ff330b0a", "name": "homelab"}],
    }
    web.serve(lambda request: httpx2.Response(200, json=reply))
    resolved = client.resolve_tunnel_id("homelab")
    assert resolved == "a40935f3-b56c-4a96-a7a5-a409ff330b0a"


def test_cloudflare_client_resolve_tunnel_id_passthrough_uuid() -> None:
    """Verify UUID is returned directly without API lookup."""
    client = CloudflareClient(token="test-token")
    uuid_str = "a40935f3-b56c-4a96-a7a5-a409ff330b0a"
    assert client.resolve_tunnel_id(uuid_str) == uuid_str


def test_cloudflare_client_sync_dns_records(web: WebFake) -> None:
    """Verify DNS record synchronization creates and leaves unchanged records."""
    client = CloudflareClient(token="test-token", zone_id="zone-123")
    existing_rec = {
        "id": "rec-1",
        "type": "CNAME",
        "name": "example.com",
        "content": "target.cfargotunnel.com",
        "proxied": True,
    }
    cloudflare_api(
        web,
        {
            ("GET", "/zones/zone-123/dns_records"): [existing_rec],
            ("POST", "/zones/zone-123/dns_records"): created("rec-2"),
        },
    )

    summary = client.sync_dns_records(
        domain="example.com",
        tunnel_id_or_cname="target.cfargotunnel.com",
        subdomains=["@", "chat"],
    )

    assert (summary.get("example.com"), summary.get("chat.example.com")) == (
        "unchanged",
        "created",
    )
    assert [request.json["name"] for request in sent(web, "POST")] == ["chat.example.com"]


def test_cloudflare_client_sync_tunnel_routes(web: WebFake) -> None:
    """Verify tunnel routes synchronization includes routes and catch-all 404."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    configurations = f"/accounts/acc-1/cfd_tunnel/{TUNNEL_ID}/configurations"
    cloudflare_api(
        web,
        {
            ("GET", configurations): {"config": {"ingress": []}},
            ("PUT", configurations): echo_configuration,
        },
    )

    cfg = client.sync_tunnel_routes(
        tunnel_id=TUNNEL_ID,
        domain="example.com",
        service="http://traefik:80",
        subdomains=["@"],
    )

    assert (len(cfg.ingress), cfg.ingress[-1].service) == (2, "http_status:404")
    assert len(sent(web, "PUT")) == 1


def test_cli_cloudflare_status_command(cli: Callable[..., Any], cloudflare_zone: WebFake) -> None:
    """Verify devops cloudflare status command output."""
    cloudflare_api(
        cloudflare_zone,
        {
            ("GET", "/user/tokens/verify"): {"id": "token-1", "status": "active"},
            ("GET", f"/zones/{ZONE}"): {
                "id": ZONE,
                "name": "example.com",
                "status": "active",
                "name_servers": ["ns1", "ns2"],
            },
        },
    )

    result = cli("cloudflare", "status")

    assert (result.exit_code, "active" in result.output, "example.com" in result.output) == (
        0,
        True,
        True,
    )


def test_cli_cloudflare_status_json_output(
    cli: Callable[..., Any], cloudflare_zone: WebFake
) -> None:
    """Verify devops cloudflare status --json output."""
    cloudflare_api(
        cloudflare_zone,
        {
            ("GET", "/user/tokens/verify"): {"id": "token-1", "status": "active"},
            ("GET", f"/zones/{ZONE}"): {
                "id": ZONE,
                "name": "example.com",
                "status": "active",
                "name_servers": ["ns1", "ns2"],
            },
        },
    )

    result = cli("cloudflare", "status", "--json")

    assert (result.exit_code, '"status": "active"' in result.output) == (0, True)


def test_cli_cloudflare_dns_list(cli: Callable[..., Any], cloudflare_zone: WebFake) -> None:
    """Verify devops cloudflare dns list command."""
    record = {
        "id": "rec-1",
        "type": "CNAME",
        "name": "example.com",
        "content": "target.cfargotunnel.com",
        "proxied": True,
        "ttl": 1,
    }
    cloudflare_api(cloudflare_zone, {("GET", f"/zones/{ZONE}/dns_records"): [record]})

    result = cli("cloudflare", "dns", "list")

    assert (
        result.exit_code,
        "example.com" in result.output,
        "target.cfargotunnel.com" in result.output,
    ) == (
        0,
        True,
        True,
    )


def test_cli_cloudflare_dns_sync_dry_run(cli: Callable[..., Any], cloudflare_zone: WebFake) -> None:
    """Verify devops cloudflare dns sync --dry-run output."""
    result = cli("cloudflare", "dns", "sync", "--dry-run", "--subdomains", "@,chat")

    assert (result.exit_code, "DRY RUN" in result.output, "example.com" in result.output) == (
        0,
        True,
        True,
    )


def test_cli_cloudflare_tunnel_routes(cli: Callable[..., Any], cloudflare_zone: WebFake) -> None:
    """Verify devops cloudflare tunnel routes command."""
    cloudflare_api(
        cloudflare_zone,
        {
            ("GET", f"/accounts/{ACCOUNT}/cfd_tunnel"): [{"id": TUNNEL_ID, "name": "homelab"}],
            ("GET", f"/accounts/{ACCOUNT}/cfd_tunnel/{TUNNEL_ID}/configurations"): {
                "config": {
                    "ingress": [
                        {"hostname": "example.com", "service": "http://traefik:80"},
                        {"service": "http_status:404"},
                    ]
                }
            },
        },
    )

    result = cli("cloudflare", "tunnel", "routes")

    assert (
        result.exit_code,
        "http://traefik:80" in result.output,
        "http_status:404" in result.output,
    ) == (
        0,
        True,
        True,
    )


def test_cli_cloudflare_tunnel_sync_dry_run(
    cli: Callable[..., Any], cloudflare_zone: WebFake
) -> None:
    """Verify devops cloudflare tunnel sync --dry-run output."""
    result = cli("cloudflare", "tunnel", "sync", "--dry-run", "--subdomains", "@,chat")

    assert (
        result.exit_code,
        "DRY RUN" in result.output,
        "http_status:404" in result.output,
    ) == (
        0,
        True,
        True,
    )


def test_cli_cloudflare_missing_token_error(
    cli: Callable[..., Any], keyring_store: Any, web: WebFake
) -> None:
    """Verify error message when token is not configured."""
    result = cli("cloudflare", "status")

    assert (result.exit_code, "API token is not configured" in result.output, web.sent) == (
        1,
        True,
        [],
    )


def test_cli_cloudflare_dns_delete_dry_run(
    cli: Callable[..., Any], cloudflare_zone: WebFake
) -> None:
    """Verify devops cloudflare dns delete --dry-run output."""
    result = cli("cloudflare", "dns", "delete", "--dry-run", "example.com")

    assert (
        result.exit_code,
        "DRY RUN" in result.output,
        "DELETE" in result.output,
        cloudflare_zone.sent,
    ) == (0, True, True, [])


def test_cli_cloudflare_dns_delete_success(
    cli: Callable[..., Any], cloudflare_zone: WebFake
) -> None:
    """Verify devops cloudflare dns delete successfully deletes matched records."""
    record = {
        "id": "rec-1",
        "type": "CNAME",
        "name": "example.com",
        "content": "target.cfargotunnel.com",
        "proxied": True,
        "ttl": 1,
        "comment": MANAGED,
    }
    cloudflare_api(
        cloudflare_zone,
        {
            ("GET", f"/zones/{ZONE}/dns_records"): [record],
            ("DELETE", f"/zones/{ZONE}/dns_records/rec-1"): {"id": "rec-1"},
        },
    )

    result = cli("cloudflare", "dns", "delete", "example.com")

    assert (result.exit_code, "Deleted" in result.output, deleted_ids(cloudflare_zone)) == (
        0,
        True,
        ["rec-1"],
    )


def test_cli_cloudflare_dns_delete_passes_force_to_the_matching(
    cli: Callable[..., Any], cloudflare_zone: WebFake
) -> None:
    """Verify --force reaches the matching: only it deletes a record devops-cli does not manage."""
    record = {
        "id": "rec-unmanaged",
        "type": "CNAME",
        "name": "example.com",
        "content": "target.cfargotunnel.com",
        "comment": None,
    }
    cloudflare_api(
        cloudflare_zone,
        {
            ("GET", f"/zones/{ZONE}/dns_records"): [record],
            ("DELETE", f"/zones/{ZONE}/dns_records/rec-unmanaged"): {"id": "rec-unmanaged"},
        },
    )

    safe = cli("cloudflare", "dns", "delete", "example.com")
    deletes_after_safe = deleted_ids(cloudflare_zone)
    forced = cli("cloudflare", "dns", "delete", "--force", "example.com")

    assert (
        safe.exit_code,
        deletes_after_safe,
        forced.exit_code,
        deleted_ids(cloudflare_zone),
    ) == (0, [], 0, ["rec-unmanaged"])


def test_cli_cloudflare_dns_delete_passes_type_to_the_matching(
    cli: Callable[..., Any], cloudflare_zone: WebFake
) -> None:
    """Verify --type reaches the matching: only the record of that type is deleted."""
    records = [
        {
            "id": record_id,
            "type": record_type,
            "name": "example.com",
            "content": "target.cfargotunnel.com",
            "comment": MANAGED,
        }
        for record_id, record_type in (("rec-cname", "CNAME"), ("rec-a", "A"))
    ]
    cloudflare_api(
        cloudflare_zone,
        {
            ("GET", f"/zones/{ZONE}/dns_records"): records,
            ("DELETE", f"/zones/{ZONE}/dns_records/rec-a"): {"id": "rec-a"},
        },
    )

    result = cli("cloudflare", "dns", "delete", "--type", "A", "example.com")

    assert (result.exit_code, deleted_ids(cloudflare_zone)) == (0, ["rec-a"])


def test_cloudflare_client_list_dns_records_pagination(web: WebFake) -> None:
    """Verify list_dns_records pages through all results when total_pages > 1."""
    client = CloudflareClient(token="test-token", zone_id="zone-1")
    pages = {
        1: (
            [{"id": "rec-1", "type": "A", "name": "a.example.com", "content": "1.2.3.4"}],
            {"total_pages": 2, "page": 1, "per_page": 1},
        ),
        2: (
            [{"id": "rec-2", "type": "A", "name": "b.example.com", "content": "1.2.3.5"}],
            {"total_pages": 2, "page": 2, "per_page": 1},
        ),
    }

    def serve_page(request: httpx2.Request) -> httpx2.Response:
        result, info = pages[int(request.url.params["page"])]
        return httpx2.Response(200, json={**envelope(result), "result_info": info})

    cloudflare_api(web, {("GET", "/zones/zone-1/dns_records"): serve_page})

    records = client.list_dns_records()

    assert (len(records), records[0].id, records[1].id) == (2, "rec-1", "rec-2")


def test_cloudflare_client_sync_tunnel_routes_preserves_rules(web: WebFake) -> None:
    """Verify sync_tunnel_routes preserves custom rules and catch-all 404."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    configurations = f"/accounts/acc-1/cfd_tunnel/{TUNNEL_ID}/configurations"
    existing_cfg = {
        "config": {
            "warp-routing": {"enabled": True},
            "ingress": [
                {"hostname": "custom.example.com", "service": "http://custom:8080"},
                {"service": "http_status:404"},
            ],
        }
    }
    cloudflare_api(
        web,
        {("GET", configurations): existing_cfg, ("PUT", configurations): echo_configuration},
    )

    cfg = client.sync_tunnel_routes(
        tunnel_id=TUNNEL_ID,
        domain="example.com",
        service="http://traefik:80",
        subdomains=["@"],
    )

    assert (len(cfg.ingress), len(sent(web, "PUT"))) == (3, 1)


def test_cloudflare_client_sync_tunnel_routes_preserves_origin_request_and_warp_routing(
    web: WebFake,
) -> None:
    """Verify sync_tunnel_routes PUT payload preserves originRequest, custom catch-all, and warp-routing."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    configurations = f"/accounts/acc-1/cfd_tunnel/{TUNNEL_ID}/configurations"
    existing_cfg = {
        "config": {
            "warp-routing": {"enabled": True},
            "ingress": [
                {
                    "hostname": "custom.example.com",
                    "service": "http://custom:8080",
                    "originRequest": {
                        "noTLSVerify": True,
                        "httpHostHeader": "custom.example.com",
                    },
                },
                {"service": "http://custom-catchall:8080"},
            ],
        }
    }
    cloudflare_api(
        web,
        {("GET", configurations): existing_cfg, ("PUT", configurations): echo_configuration},
    )

    client.sync_tunnel_routes(
        tunnel_id=TUNNEL_ID,
        domain="example.com",
        service="http://traefik:80",
        subdomains=["@"],
    )

    put_calls = sent(web, "PUT")
    put_body = put_calls[0].json if put_calls else {}
    expected_put = {
        "config": {
            "warp-routing": {"enabled": True},
            "ingress": [
                {
                    "service": "http://custom:8080",
                    "hostname": "custom.example.com",
                    "originRequest": {
                        "noTLSVerify": True,
                        "httpHostHeader": "custom.example.com",
                    },
                },
                {
                    "service": "http://traefik:80",
                    "hostname": "example.com",
                },
                {"service": "http://custom-catchall:8080"},
            ],
        }
    }
    assert (len(put_calls), put_body) == (1, expected_put)


@pytest.mark.parametrize(
    ("existing", "subdomain", "order"),
    [
        (
            ["*.example.com", "example.com"],
            "k8s",
            ["k8s.example.com", "*.example.com", "example.com", None],
        ),
        (
            ["*.lab.example.com", "*.example.com"],
            "k8s.lab",
            ["k8s.lab.example.com", "*.lab.example.com", "*.example.com", None],
        ),
        (["a.example.com"], "k8s", ["a.example.com", "k8s.example.com", None]),
    ],
    ids=["under-a-wildcard", "under-the-nearest-wildcard", "no-wildcard"],
)
def test_a_new_hostname_goes_before_the_wildcard_cloudflared_would_match_it_to(
    web: WebFake, existing: list[str], subdomain: str, order: list[str | None]
) -> None:
    """cloudflared takes the first rule whose hostname matches, and `*.example.com` matches any
    name ending in `.example.com`: a host added after it would never be reached (#1595)."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    configurations = f"/accounts/acc-1/cfd_tunnel/{TUNNEL_ID}/configurations"
    current = {
        "config": {
            "ingress": [
                *({"hostname": host, "service": "http://traefik:80"} for host in existing),
                {"service": "http_status:404"},
            ]
        }
    }
    cloudflare_api(
        web,
        {("GET", configurations): current, ("PUT", configurations): echo_configuration},
    )

    client.sync_tunnel_routes(
        tunnel_id=TUNNEL_ID,
        domain="example.com",
        service="tcp://kubernetes.default.svc.cluster.local:443",
        subdomains=[subdomain],
    )

    (put,) = sent(web, "PUT")
    assert [rule.get("hostname") for rule in put.json["config"]["ingress"]] == order


def test_cloudflare_tunnel_sync_aborts_on_get_failure(
    cli: Callable[..., Any], cloudflare_zone: WebFake
) -> None:
    """When GET of current tunnel config fails, sync raises an error and sends no PUT request."""
    configurations = f"/accounts/{ACCOUNT}/cfd_tunnel/{TUNNEL_ID}/configurations"
    failure = httpx2.Response(
        400, json={"success": False, "errors": [{"message": "Failed reading tunnel config"}]}
    )
    cloudflare_api(
        cloudflare_zone,
        {
            ("GET", f"/accounts/{ACCOUNT}/cfd_tunnel"): [{"id": TUNNEL_ID, "name": "homelab"}],
            ("GET", configurations): lambda request: failure,
        },
    )

    result = cli("cloudflare", "tunnel", "sync")

    assert (
        result.exit_code != 0,
        sent(cloudflare_zone, "PUT"),
        "Failed reading tunnel config" in result.output,
    ) == (True, [], True)


def test_cloudflare_client_sync_tunnel_routes_aborts_on_get_failure(web: WebFake) -> None:
    """CloudflareClient.sync_tunnel_routes raises CloudflareAPIError on GET failure and does not call PUT."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    failure = httpx2.Response(
        400, json={"success": False, "errors": [{"message": "Network timeout"}]}
    )
    cloudflare_api(
        web,
        {
            ("GET", f"/accounts/acc-1/cfd_tunnel/{TUNNEL_ID}/configurations"): lambda request: (
                failure
            )
        },
    )

    with pytest.raises(CloudflareAPIError, match="Network timeout"):
        client.sync_tunnel_routes(tunnel_id=TUNNEL_ID, domain="example.com")

    assert sent(web, "PUT") == []


def test_cloudflare_tunnel_sync_dry_run_makes_no_network_requests(
    cli: Callable[..., Any], cloudflare_zone: WebFake
) -> None:
    """--dry-run makes zero network requests (neither GET nor PUT) and prints planned requests."""
    result = cli("cloudflare", "tunnel", "sync", "--dry-run", "--subdomains", "@,chat")

    assert (
        result.exit_code,
        len(cloudflare_zone.sent),
        "GET" in result.output,
        "PUT" in result.output,
        "accounts/test-account-123/cfd_tunnel" in result.output,
    ) == (0, 0, True, True, True)


def test_cloudflare_client_resolve_tunnel_id_filters_deleted_tunnels(web: WebFake) -> None:
    """resolve_tunnel_id excludes tunnels matching deleted-tunnel criteria."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    tunnels_resp = [
        {
            "id": "deleted-uuid-1",
            "name": "my-tunnel",
            "deleted_at": "2026-01-01T00:00:00Z",
            "is_deleted": True,
        },
        {
            "id": "deleted-uuid-2",
            "name": "my-tunnel",
            "deleted_at": "2026-02-01T00:00:00Z",
            "is_deleted": False,
        },
        {
            "id": "active-uuid-3",
            "name": "my-tunnel",
            "deleted_at": None,
            "is_deleted": False,
        },
    ]
    cloudflare_api(web, {("GET", "/accounts/acc-1/cfd_tunnel"): tunnels_resp})

    resolved = client.resolve_tunnel_id("my-tunnel")

    assert resolved == "active-uuid-3"


def test_cli_cloudflare_dns_delete_not_found(
    cli: Callable[..., Any], cloudflare_zone: WebFake
) -> None:
    """Verify devops cloudflare dns delete when record is not found."""
    cloudflare_api(cloudflare_zone, {("GET", f"/zones/{ZONE}/dns_records"): []})

    result = cli("cloudflare", "dns", "delete", "example.com")

    assert (
        result.exit_code,
        "Records not found: example.com" in result.output,
    ) == (0, True)


def test_cloudflare_client_list_access_applications(web: WebFake) -> None:
    """Verify listing Cloudflare Access applications."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    reply = {
        "success": True,
        "result": [
            {
                "id": "app-1",
                "name": "Homelab Ingress",
                "domain": "example.com",
                "type": "self_hosted",
                "session_duration": "24h",
            }
        ],
    }
    web.serve(lambda request: httpx2.Response(200, json=reply))
    apps = client.list_access_applications()
    assert (len(apps), apps[0].id, apps[0].domain) == (1, "app-1", "example.com")


def test_cloudflare_client_sync_access_application(web: WebFake) -> None:
    """Verify synchronizing an Access application creates app and policy."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    cloudflare_api(
        web,
        {
            ("GET", "/accounts/acc-1/access/apps"): [],
            ("POST", "/accounts/acc-1/access/apps"): created("app-1"),
            ("GET", "/accounts/acc-1/access/apps/app-1/policies"): [],
            ("POST", "/accounts/acc-1/access/apps/app-1/policies"): created("pol-1"),
        },
    )

    res = client.sync_access_application(
        domain="example.com",
        allowed_emails=["user@example.com"],
    )

    assert (res.get("app_id"), res.get("app_action"), res.get("policy_id")) == (
        "app-1",
        "created",
        "pol-1",
    )
    assert [request.json["domain"] for request in sent(web, "POST")[:1]] == ["example.com"]


def test_cli_cloudflare_access_status(cli: Callable[..., Any], cloudflare_zone: WebFake) -> None:
    """Verify devops cloudflare access status command."""
    application = {
        "id": "app-1",
        "name": "Homelab Ingress",
        "domain": "example.com",
        "session_duration": "24h",
    }
    cloudflare_api(cloudflare_zone, {("GET", APPS): [application]})

    result = cli("cloudflare", "access", "status")

    assert (
        result.exit_code,
        "Homelab Ingress" in result.output,
        "example.com" in result.output,
    ) == (0, True, True)


def test_cli_cloudflare_access_sync_dry_run(
    cli: Callable[..., Any], cloudflare_zone: WebFake, config: Callable[..., Path]
) -> None:
    """Verify devops cloudflare access sync --dry-run command."""
    config(cloudflare={"access": {"allowed_emails": ["admin@example.com"]}})

    result = cli("cloudflare", "access", "sync", "--dry-run")

    assert (
        result.exit_code,
        "DRY RUN" in result.output,
        "admin@example.com" in result.output,
    ) == (0, True, True)


def test_cli_cloudflare_access_sync_success(
    cli: Callable[..., Any], cloudflare_zone: WebFake, config: Callable[..., Path]
) -> None:
    """Verify devops cloudflare access sync successfully syncs application."""
    config(cloudflare={"access": {"allowed_emails": ["admin@example.com"]}})
    cloudflare_api(
        cloudflare_zone,
        {
            ("GET", APPS): [],
            ("POST", APPS): created("app-1"),
            ("GET", f"{APPS}/app-1/policies"): [],
            ("POST", f"{APPS}/app-1/policies"): created("pol-1"),
        },
    )

    result = cli("cloudflare", "access", "sync")

    assert (
        result.exit_code,
        "Configured Cloudflare Access application" in result.output,
        [request.url.rsplit("/", 3)[-1] for request in sent(cloudflare_zone, "POST")],
    ) == (0, True, ["apps", "policies"])


def test_normalize_ip_cidr_variants(web: WebFake) -> None:
    """Verify IP normalization converts addresses and networks to CIDR notation."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    policies = "/accounts/acc-1/access/apps/app-1/policies"
    cloudflare_api(web, {("GET", policies): [], ("POST", policies): created("pol-1")})

    client.create_or_update_access_policy(
        app_id="app-1",
        name="bypass",
        bypass_ips=["198.51.100.1", "198.51.100.0/24", "2001:db8::1", "2001:DB8::1"],
        decision="bypass",
    )

    assert [rule["ip"]["ip"] for rule in sent(web, "POST")[0].json["include"]] == [
        "198.51.100.1/32",
        "198.51.100.0/24",
        "2001:db8::1/128",
        "2001:db8::1/128",
    ]
    for invalid in ("not-an-ip", "fe80::1%eth0/128"):
        with pytest.raises(CloudflareAPIError) as raised:
            client.create_or_update_access_policy(
                app_id="app-1", name="bypass", bypass_ips=[invalid], decision="bypass"
            )
        assert raised.value.error_code == "CLOUDFLARE_API_ERROR"
    assert len(sent(web, "POST")) == 1


def test_cloudflare_client_sync_access_with_bypass_ips(web: WebFake) -> None:
    """Verify synchronizing an Access application creates bypass policy for homelab IP."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    policies = "/accounts/acc-1/access/apps/app-1/policies"
    ids = {"Allow homelab authorized emails": "pol-allow", "homelab-public-ip-bypass": "pol-bypass"}

    def create_policy(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        return httpx2.Response(200, json=envelope({**body, "id": ids[body["name"]]}))

    existing_app = {"id": "app-1", "name": "Homelab Ingress", "domain": "example.com"}
    cloudflare_api(
        web,
        {
            ("GET", "/accounts/acc-1/access/apps"): [existing_app],
            ("GET", policies): [],
            ("POST", policies): create_policy,
        },
    )

    res = client.sync_access_application(
        domain="example.com",
        allowed_emails=["user@example.com"],
        bypass_ips=["198.51.100.1"],
    )

    assert (
        res.get("app_id"),
        res.get("app_action"),
        res.get("policy_id"),
        res.get("bypass_policy_id"),
        res.get("bypass_ips"),
        len(sent(web, "POST")),
    ) == (
        "app-1",
        "existing",
        "pol-allow",
        "pol-bypass",
        ["198.51.100.1"],
        2,
    )


def test_cli_cloudflare_access_sync_with_bypass_ips(
    cli: Callable[..., Any], cloudflare_zone: WebFake, config: Callable[..., Path]
) -> None:
    """Verify CLI access sync propagates --bypass-ips and displays bypass output."""
    config(cloudflare={"access": {"allowed_emails": ["admin@example.com"]}})
    cloudflare_api(
        cloudflare_zone,
        {
            ("GET", APPS): [],
            ("POST", APPS): created("app-1"),
            ("GET", f"{APPS}/app-1/policies"): [],
            ("POST", f"{APPS}/app-1/policies"): created("pol-bypass-1"),
        },
    )

    result = cli("cloudflare", "access", "sync", "--bypass-ips", "198.51.100.1")

    bypass = [
        request.json["include"]
        for request in sent(cloudflare_zone, "POST")
        if request.json.get("decision") == "bypass"
    ]
    assert (
        result.exit_code,
        "Public IP bypass: 198.51.100.1" in result.output,
        "homelab-public-ip-bypass" in result.output,
        bypass,
    ) == (0, True, True, [[{"ip": {"ip": "198.51.100.1/32"}}]])


def test_cli_cloudflare_access_sync_settings_bypass_ip(
    cli: Callable[..., Any], cloudflare_zone: WebFake, config: Callable[..., Path]
) -> None:
    """Verify CLI access sync resolves bypass IP from settings.cloudflare.public_ip_bypass."""
    config(
        cloudflare={
            "access": {"allowed_emails": ["admin@example.com"]},
            "public_ip_bypass": "198.51.100.5",
        }
    )
    application = {"id": "app-1", "name": "Homelab Ingress", "domain": "example.com"}
    cloudflare_api(
        cloudflare_zone,
        {
            ("GET", APPS): [application],
            ("GET", f"{APPS}/app-1/policies"): [],
            ("POST", f"{APPS}/app-1/policies"): created("pol-bypass-2"),
        },
    )

    result = cli("cloudflare", "access", "sync")

    bypass = [
        request.json["include"]
        for request in sent(cloudflare_zone, "POST")
        if request.json.get("decision") == "bypass"
    ]
    assert (result.exit_code, bypass) == (0, [[{"ip": {"ip": "198.51.100.5/32"}}]])


def test_cli_cloudflare_access_policies(cli: Callable[..., Any], cloudflare_zone: WebFake) -> None:
    """Verify devops cloudflare access policies lists application policies."""
    policies = [
        {
            "id": "989871c6-c652-45c6-b8f0-b56e761afc35",
            "name": "homelab-public-ip-bypass",
            "decision": "bypass",
            "include": [{"ip": {"ip": "198.51.100.1/32"}}],
        },
        {
            "id": "pol-allow",
            "name": "Allow homelab authorized emails",
            "decision": "allow",
            "include": [{"email": {"email": "user@example.com"}}],
        },
    ]
    cloudflare_api(cloudflare_zone, {("GET", f"{APPS}/app-123/policies"): policies})

    result = cli("cloudflare", "access", "policies", "app-123")

    assert (
        result.exit_code,
        "homelab-public-ip-bypass" in result.output,
        "bypass" in result.output,
        "Allow homelab authorized emails" in result.output,
    ) == (0, True, True, True)


def test_cloudflare_client_sync_access_application_finds_page_two_app(web: WebFake) -> None:
    """With an existing application on page 2 of a two-page answer, sync finds it and creates nothing."""
    client = CloudflareClient(token="test-token", account_id="acc-1")

    app1_page = {
        "success": True,
        "result": [
            {
                "id": "app-1",
                "name": "App 1",
                "domain": "other.example.com",
                "type": "self_hosted",
                "session_duration": "24h",
            }
        ],
        "result_info": {
            "page": 1,
            "per_page": 1,
            "total_pages": 2,
            "count": 1,
            "total_count": 2,
        },
    }
    app2_page = {
        "success": True,
        "result": [
            {
                "id": "app-2",
                "name": "Homelab Ingress",
                "domain": "example.com",
                "type": "self_hosted",
                "session_duration": "24h",
            }
        ],
        "result_info": {
            "page": 2,
            "per_page": 1,
            "total_pages": 2,
            "count": 1,
            "total_count": 2,
        },
    }
    policy_list = {
        "success": True,
        "result": [
            {
                "id": "pol-1",
                "name": "Allow homelab authorized emails",
                "decision": "allow",
                "include": [{"email": {"email": "admin@example.com"}}],
            }
        ],
        "result_info": {
            "page": 1,
            "per_page": 10,
            "total_pages": 1,
            "count": 1,
            "total_count": 1,
        },
    }
    policy_update = {
        "success": True,
        "result": {
            "id": "pol-1",
            "name": "Allow homelab authorized emails",
            "decision": "allow",
            "include": [{"email": {"email": "admin@example.com"}}],
        },
    }

    def serve(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/access/apps"):
            assert request.method == "GET", (
                "Should only GET access/apps, never POST to create a duplicate"
            )
            page = int(request.url.params.get("page", 1))
            return httpx2.Response(200, json=app1_page if page == 1 else app2_page)
        if "/policies" in request.url.path:
            return httpx2.Response(
                200, json=policy_update if request.method == "PUT" else policy_list
            )
        return httpx2.Response(200, json={"success": True, "result": {}})

    web.serve(serve)
    res = client.sync_access_application(
        domain="example.com",
        allowed_emails=["admin@example.com"],
    )
    assert res["app_id"] == "app-2"
    assert res["app_action"] == "existing"


def test_cloudflare_client_get_access_policies_paginated(web: WebFake) -> None:
    """Access policies spread over two pages are all returned."""
    client = CloudflareClient(token="test-token", account_id="acc-1")

    page1 = {
        "success": True,
        "result": [
            {
                "id": "pol-1",
                "name": "Policy 1",
                "decision": "allow",
                "include": [{"email": {"email": "admin@example.com"}}],
            }
        ],
        "result_info": {
            "page": 1,
            "per_page": 1,
            "total_pages": 2,
            "count": 1,
            "total_count": 2,
        },
    }
    page2 = {
        "success": True,
        "result": [
            {
                "id": "pol-2",
                "name": "Policy 2",
                "decision": "bypass",
                "include": [{"ip": {"ip": "192.0.2.1/32"}}],
            }
        ],
        "result_info": {
            "page": 2,
            "per_page": 1,
            "total_pages": 2,
            "count": 1,
            "total_count": 2,
        },
    }

    web.serve(
        lambda request: httpx2.Response(
            200, json=page1 if int(request.url.params.get("page", 1)) == 1 else page2
        )
    )
    policies = client.get_access_policies("app-1")
    assert len(policies) == 2
    assert [p.id for p in policies] == ["pol-1", "pol-2"]


def test_cloudflare_client_request_retries_429_with_retry_after(web: WebFake) -> None:
    """A 429 with Retry-After: 1 followed by a 200 succeeds without a real sleep: the test injects tenacity's sleep."""
    sleep_calls: list[float] = []

    def mock_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    client = CloudflareClient(token="test-token", sleep=mock_sleep)

    rate_limited = httpx2.Response(
        429,
        headers={"retry-after": "1"},
        json={"success": False, "errors": [{"message": "Rate limit exceeded"}]},
    )
    accepted = httpx2.Response(
        200, json={"success": True, "result": {"id": "token-123", "status": "active"}}
    )
    answers = iter([rate_limited, accepted])
    web.serve(lambda request: next(answers))

    res = client.verify_token()
    assert (res.id, res.status) == ("token-123", "active")
    assert len(web.sent) == 2
    assert sleep_calls == [1.0]


def test_cloudflare_client_request_does_not_retry_403(web: WebFake) -> None:
    """A 403 is not retried."""
    sleep_calls: list[float] = []

    def mock_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    client = CloudflareClient(token="test-token", sleep=mock_sleep)

    web.serve(
        lambda request: httpx2.Response(
            403, json={"success": False, "errors": [{"message": "Forbidden"}]}
        )
    )

    with pytest.raises(CloudflareAuthError) as raised:
        client.verify_token()
    assert raised.value.error_code == "CLOUDFLARE_AUTH_ERROR"
    assert len(web.sent) == 1
    assert len(sleep_calls) == 0


@pytest.mark.usefixtures("keyring_store")
@pytest.mark.parametrize(
    "argv",
    [
        ["status"],
        ["dns", "list", "--zone-id", "zone-1"],
        ["tunnel", "routes", "--tunnel-id", "f47ac10b-58cc-4372-a567-0e02b2c3d479", "-a", "acct-1"],
        ["access", "status", "--account-id", "acct-1"],
    ],
    ids=["status", "dns", "tunnel", "access"],
)
def test_cli_cloudflare_refused_address_is_reported(
    monkeypatch: pytest.MonkeyPatch, cli: Any, argv: list[str], dns: DnsFake
) -> None:
    """A private answer for the API host is refused, and each command reports the refusal.

    The client dials only public addresses (#2430), so the token never reaches 10.0.0.1. A
    command of each Cloudflare command group prints the message of `SSRFBlockedError` and exits
    with its exit code, 2, with no traceback. The socket gets neither 10.0.0.1 nor the API host
    name: a client that gives the socket the name lets the socket resolve it to 10.0.0.1 with no
    check. Only dials to these two count, because the telemetry exporter of the test
    configuration can dial its collector from a background thread.
    """
    dns.script("api.cloudflare.com", ["10.0.0.1"])
    recorder = record_connects(monkeypatch, [])

    result = cli("cloudflare", *argv, env={"DEVOPS_CLI_CLOUDFLARE_API_TOKEN": "cf-test"})

    assert (
        result.exit_code,
        type(result.exception),
        "SSRF blocked" in result.output,
        [host for host, _ in recorder.dialled if host in {"10.0.0.1", "api.cloudflare.com"}],
    ) == (2, SystemExit, True, [])
