"""Unit tests for Cloudflare client and CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.cloudflare.client import CloudflareClient
from devops_cli.commands.cloudflare import app
from devops_cli.config.settings import Settings
from devops_cli.exceptions.cloudflare import CloudflareAuthError
from devops_cli.models.cloudflare import (
    CloudflareAccessApplication,
    CloudflareAccessPolicy,
    CloudflareDNSRecord,
    CloudflareTokenStatus,
    CloudflareTunnelConfig,
    CloudflareTunnelIngressRule,
    CloudflareZone,
)

runner = CliRunner()


@pytest.fixture
def mock_settings() -> Settings:
    """Settings fixture with standardized dummy hostnames."""
    s = Settings()
    s.cloudflare.domain = "example.com"
    s.cloudflare.tunnel = "homelab"
    s.cloudflare.account_id = "test-account-123"
    s.cloudflare.zone_id = "test-zone-456"
    return s


def test_cloudflare_client_verify_token_success() -> None:
    """Verify successful token verification."""
    client = CloudflareClient(token="test-token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.json.return_value = {
        "success": True,
        "result": {"id": "token-id-1", "status": "active"},
    }

    with patch("httpx2.Client.request", return_value=mock_resp):
        res = client.verify_token()
        assert (res.id, res.status) == ("token-id-1", "active")


def test_cloudflare_client_auth_error() -> None:
    """Verify authentication failure raises CloudflareAuthError."""
    client = CloudflareClient(token="invalid-token")
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.is_success = False

    with patch("httpx2.Client.request", return_value=mock_resp):
        with pytest.raises(CloudflareAuthError):
            client.verify_token()


def test_cloudflare_client_get_zone() -> None:
    """Verify zone details retrieval."""
    client = CloudflareClient(token="test-token", zone_id="zone-123")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.json.return_value = {
        "success": True,
        "result": {
            "id": "zone-123",
            "name": "example.com",
            "status": "active",
            "paused": False,
            "name_servers": ["ns1", "ns2"],
        },
    }

    with patch("httpx2.Client.request", return_value=mock_resp):
        zone = client.get_zone()
        assert (zone.id, zone.name, zone.status, zone.name_servers) == (
            "zone-123",
            "example.com",
            "active",
            ["ns1", "ns2"],
        )


def test_cloudflare_client_list_dns_records() -> None:
    """Verify listing DNS records."""
    client = CloudflareClient(token="test-token", zone_id="zone-123")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.json.return_value = {
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

    with patch("httpx2.Client.request", return_value=mock_resp):
        records = client.list_dns_records()
        assert (len(records), records[0].name, records[0].proxied) == (1, "example.com", True)


def test_cloudflare_client_resolve_tunnel_id_by_name() -> None:
    """Verify resolution of named tunnel to UUID."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.json.return_value = {
        "success": True,
        "result": [{"id": "a40935f3-b56c-4a96-a7a5-a409ff330b0a", "name": "homelab"}],
    }

    with patch("httpx2.Client.request", return_value=mock_resp):
        resolved = client.resolve_tunnel_id("homelab")
        assert resolved == "a40935f3-b56c-4a96-a7a5-a409ff330b0a"


def test_cloudflare_client_resolve_tunnel_id_passthrough_uuid() -> None:
    """Verify UUID is returned directly without API lookup."""
    client = CloudflareClient(token="test-token")
    uuid_str = "a40935f3-b56c-4a96-a7a5-a409ff330b0a"
    assert client.resolve_tunnel_id(uuid_str) == uuid_str


def test_cloudflare_client_sync_dns_records() -> None:
    """Verify DNS record synchronization creates and leaves unchanged records."""
    client = CloudflareClient(token="test-token", zone_id="zone-123")
    existing_rec = CloudflareDNSRecord(
        id="rec-1",
        type="CNAME",
        name="example.com",
        content="target.cfargotunnel.com",
        proxied=True,
    )

    with (
        patch.object(client, "list_dns_records", return_value=[existing_rec]),
        patch.object(client, "create_dns_record") as mock_create,
    ):
        summary = client.sync_dns_records(
            domain="example.com",
            tunnel_id_or_cname="target.cfargotunnel.com",
            subdomains=["@", "chat"],
        )
        assert (summary.get("example.com"), summary.get("chat.example.com")) == (
            "unchanged",
            "created",
        )
        assert mock_create.call_count == 1


def test_cloudflare_client_sync_tunnel_routes() -> None:
    """Verify tunnel routes synchronization includes routes and catch-all 404."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    dummy_config = CloudflareTunnelConfig(
        tunnel_id="tunnel-1",
        ingress=[
            CloudflareTunnelIngressRule(hostname="example.com", service="http://traefik:80"),
            CloudflareTunnelIngressRule(service="http_status:404"),
        ],
    )

    with (
        patch.object(client, "resolve_tunnel_id", return_value="tunnel-1"),
        patch.object(client, "_request", return_value={"config": {"ingress": []}}),
        patch.object(
            client, "update_tunnel_configuration", return_value=dummy_config
        ) as mock_update,
    ):
        cfg = client.sync_tunnel_routes(
            tunnel_id="tunnel-1",
            domain="example.com",
            service="http://traefik:80",
            subdomains=["@"],
        )
        assert (len(cfg.ingress), cfg.ingress[-1].service) == (2, "http_status:404")
        assert mock_update.call_count == 1


def test_cli_cloudflare_status_command(mock_settings: Settings) -> None:
    """Verify devops cloudflare status command output."""
    mock_client = MagicMock()
    mock_client.account_id = "test-account-123"
    mock_client.zone_id = "test-zone-456"
    mock_client.verify_token.return_value = CloudflareTokenStatus(id="token-1", status="active")
    mock_client.get_zone.return_value = CloudflareZone(
        id="test-zone-456",
        name="example.com",
        status="active",
        name_servers=["ns1", "ns2"],
    )

    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["status"])
        assert (result.exit_code, "active" in result.output, "example.com" in result.output) == (
            0,
            True,
            True,
        )


def test_cli_cloudflare_status_json_output(mock_settings: Settings) -> None:
    """Verify devops cloudflare status --json output."""
    mock_client = MagicMock()
    mock_client.account_id = "test-account-123"
    mock_client.zone_id = "test-zone-456"
    mock_client.verify_token.return_value = CloudflareTokenStatus(id="token-1", status="active")
    mock_client.get_zone.return_value = CloudflareZone(
        id="test-zone-456",
        name="example.com",
        status="active",
        name_servers=["ns1", "ns2"],
    )

    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["status", "--json"])
        assert (result.exit_code, '"status": "active"' in result.output) == (0, True)


def test_cli_cloudflare_dns_list(mock_settings: Settings) -> None:
    """Verify devops cloudflare dns list command."""
    mock_client = MagicMock()
    mock_client.zone_id = "test-zone-456"
    mock_client.list_dns_records.return_value = [
        CloudflareDNSRecord(
            id="rec-1",
            type="CNAME",
            name="example.com",
            content="target.cfargotunnel.com",
            proxied=True,
            ttl=1,
        )
    ]

    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["dns", "list"])
        assert (
            result.exit_code,
            "example.com" in result.output,
            "target.cfargotunnel.com" in result.output,
        ) == (
            0,
            True,
            True,
        )


def test_cli_cloudflare_dns_sync_dry_run(mock_settings: Settings) -> None:
    """Verify devops cloudflare dns sync --dry-run output."""
    with patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings):
        result = runner.invoke(app, ["dns", "sync", "--dry-run", "--subdomains", "@,chat"])
        assert (result.exit_code, "DRY RUN" in result.output, "example.com" in result.output) == (
            0,
            True,
            True,
        )


def test_cli_cloudflare_tunnel_routes(mock_settings: Settings) -> None:
    """Verify devops cloudflare tunnel routes command."""
    mock_client = MagicMock()
    mock_client.get_tunnel_configuration.return_value = CloudflareTunnelConfig(
        tunnel_id="homelab",
        ingress=[
            CloudflareTunnelIngressRule(hostname="example.com", service="http://traefik:80"),
            CloudflareTunnelIngressRule(service="http_status:404"),
        ],
    )

    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["tunnel", "routes"])
        assert (
            result.exit_code,
            "http://traefik:80" in result.output,
            "http_status:404" in result.output,
        ) == (
            0,
            True,
            True,
        )


def test_cli_cloudflare_tunnel_sync_dry_run(mock_settings: Settings) -> None:
    """Verify devops cloudflare tunnel sync --dry-run output."""
    with patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings):
        result = runner.invoke(app, ["tunnel", "sync", "--dry-run", "--subdomains", "@,chat"])
        assert (
            result.exit_code,
            "DRY RUN" in result.output,
            "http_status:404" in result.output,
        ) == (
            0,
            True,
            True,
        )


def test_cli_cloudflare_missing_token_error() -> None:
    """Verify error message when token is not configured."""
    empty_settings = Settings()
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=empty_settings),
        patch("devops_cli.commands.cloudflare.get_cloudflare_api_token", return_value=None),
    ):
        result = runner.invoke(app, ["status"])
        assert (result.exit_code, "API token is not configured" in result.output) == (1, True)


def test_cli_cloudflare_dns_delete_dry_run(mock_settings: Settings) -> None:
    """Verify devops cloudflare dns delete --dry-run output."""
    mock_client = MagicMock()
    mock_client.list_dns_records.return_value = [
        CloudflareDNSRecord(
            id="rec-1",
            type="CNAME",
            name="example.com",
            content="target.cfargotunnel.com",
            proxied=True,
            ttl=1,
            comment="Managed by devops-cli",
        )
    ]
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["dns", "delete", "--dry-run", "example.com"])
        assert (
            result.exit_code,
            "DRY RUN" in result.output,
            "Would Delete" in result.output,
            mock_client.delete_dns_record.called,
        ) == (0, True, True, False)


def test_cli_cloudflare_dns_delete_success(mock_settings: Settings) -> None:
    """Verify devops cloudflare dns delete successfully deletes matched records."""
    mock_client = MagicMock()
    mock_client.list_dns_records.return_value = [
        CloudflareDNSRecord(
            id="rec-1",
            type="CNAME",
            name="example.com",
            content="target.cfargotunnel.com",
            proxied=True,
            ttl=1,
            comment="Managed by devops-cli",
        )
    ]
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["dns", "delete", "example.com"])
        assert (
            result.exit_code,
            "Deleted" in result.output,
            mock_client.delete_dns_record.call_count,
        ) == (0, True, 1)


def test_cli_cloudflare_dns_delete_unmanaged_protection(mock_settings: Settings) -> None:
    """Verify unmanaged records are protected without --force and deleted with --force."""
    mock_client = MagicMock()
    mock_client.list_dns_records.return_value = [
        CloudflareDNSRecord(
            id="rec-unmanaged",
            type="CNAME",
            name="example.com",
            content="target.cfargotunnel.com",
            proxied=True,
            ttl=1,
            comment=None,
        )
    ]
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        res_safe = runner.invoke(app, ["dns", "delete", "example.com"])
        res_force = runner.invoke(app, ["dns", "delete", "--force", "example.com"])

    assert (
        res_safe.exit_code,
        "Records not found: example.com" in res_safe.output,
        res_force.exit_code,
        "Deleted" in res_force.output,
        mock_client.delete_dns_record.call_count,
    ) == (0, True, 0, True, 1)


def test_cli_cloudflare_dns_delete_type_filtering(mock_settings: Settings) -> None:
    """Verify --type filters DNS deletions by record type."""
    mock_client = MagicMock()
    mock_client.list_dns_records.return_value = [
        CloudflareDNSRecord(
            id="rec-cname",
            type="CNAME",
            name="example.com",
            content="target.cfargotunnel.com",
            proxied=True,
            ttl=1,
            comment="Managed by devops-cli",
        ),
        CloudflareDNSRecord(
            id="rec-a",
            type="A",
            name="example.com",
            content="1.2.3.4",
            proxied=False,
            ttl=1,
            comment="Managed by devops-cli",
        ),
    ]
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        res = runner.invoke(app, ["dns", "delete", "--type", "A", "example.com"])

    assert (
        res.exit_code,
        mock_client.delete_dns_record.call_count,
        mock_client.delete_dns_record.call_args[0][0],
    ) == (0, 1, "rec-a")


def test_cloudflare_client_list_dns_records_pagination() -> None:
    """Verify list_dns_records pages through all results when total_pages > 1."""
    client = CloudflareClient(token="test-token", zone_id="zone-1")
    page1 = (
        [{"id": "rec-1", "type": "A", "name": "a.example.com", "content": "1.2.3.4"}],
        {"total_pages": 2, "page": 1, "per_page": 1},
    )
    page2 = (
        [{"id": "rec-2", "type": "A", "name": "b.example.com", "content": "1.2.3.5"}],
        {"total_pages": 2, "page": 2, "per_page": 1},
    )
    with patch.object(client, "_request", side_effect=[page1, page2]):
        records = client.list_dns_records()
    assert (len(records), records[0].id, records[1].id) == (2, "rec-1", "rec-2")


def test_cloudflare_client_sync_tunnel_routes_preserves_rules() -> None:
    """Verify sync_tunnel_routes preserves custom rules and catch-all 404."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    existing_cfg = {
        "config": {
            "warp-routing": {"enabled": True},
            "ingress": [
                {"hostname": "custom.example.com", "service": "http://custom:8080"},
                {"service": "http_status:404"},
            ],
        }
    }
    dummy_result = CloudflareTunnelConfig(
        tunnel_id="tunnel-1",
        ingress=[
            CloudflareTunnelIngressRule(
                hostname="custom.example.com", service="http://custom:8080"
            ),
            CloudflareTunnelIngressRule(hostname="example.com", service="http://traefik:80"),
            CloudflareTunnelIngressRule(service="http_status:404"),
        ],
    )
    with (
        patch.object(client, "resolve_tunnel_id", return_value="tunnel-1"),
        patch.object(client, "_request", return_value=existing_cfg),
        patch.object(
            client, "update_tunnel_configuration", return_value=dummy_result
        ) as mock_update,
    ):
        cfg = client.sync_tunnel_routes(
            tunnel_id="tunnel-1",
            domain="example.com",
            service="http://traefik:80",
            subdomains=["@"],
        )
    assert (len(cfg.ingress), mock_update.call_count) == (3, 1)


def test_cli_cloudflare_dns_delete_not_found(mock_settings: Settings) -> None:
    """Verify devops cloudflare dns delete when record is not found."""
    mock_client = MagicMock()
    mock_client.list_dns_records.return_value = []
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["dns", "delete", "example.com"])
        assert (
            result.exit_code,
            "Records not found: example.com" in result.output,
        ) == (0, True)


def test_cloudflare_client_list_access_applications() -> None:
    """Verify listing Cloudflare Access applications."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.json.return_value = {
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
    with patch("httpx2.Client.request", return_value=mock_resp):
        apps = client.list_access_applications()
        assert (len(apps), apps[0].id, apps[0].domain) == (1, "app-1", "example.com")


def test_cloudflare_client_sync_access_application() -> None:
    """Verify synchronizing an Access application creates app and policy."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    dummy_app = CloudflareAccessApplication(
        id="app-1",
        name="Homelab Ingress",
        domain="example.com",
    )
    dummy_policy = CloudflareAccessPolicy(
        id="pol-1",
        name="Allow homelab authorized emails",
        decision="allow",
        include=[{"email": "user@example.com"}],
    )
    with (
        patch.object(client, "list_access_applications", return_value=[]),
        patch.object(client, "create_access_application", return_value=dummy_app),
        patch.object(client, "create_or_update_access_policy", return_value=dummy_policy),
    ):
        res = client.sync_access_application(
            domain="example.com",
            allowed_emails=["user@example.com"],
        )
        assert (res.get("app_id"), res.get("app_action"), res.get("policy_id")) == (
            "app-1",
            "created",
            "pol-1",
        )


def test_cli_cloudflare_access_status(mock_settings: Settings) -> None:
    """Verify devops cloudflare access status command."""
    mock_client = MagicMock()
    mock_client.list_access_applications.return_value = [
        CloudflareAccessApplication(
            id="app-1",
            name="Homelab Ingress",
            domain="example.com",
            session_duration="24h",
        )
    ]
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["access", "status"])
        assert (
            result.exit_code,
            "Homelab Ingress" in result.output,
            "example.com" in result.output,
        ) == (0, True, True)


def test_cli_cloudflare_access_sync_dry_run(mock_settings: Settings) -> None:
    """Verify devops cloudflare access sync --dry-run command."""
    mock_settings.cloudflare.access.allowed_emails = ["admin@example.com"]
    with patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings):
        result = runner.invoke(app, ["access", "sync", "--dry-run"])
        assert (
            result.exit_code,
            "DRY RUN" in result.output,
            "admin@example.com" in result.output,
        ) == (0, True, True)


def test_cli_cloudflare_access_sync_success(mock_settings: Settings) -> None:
    """Verify devops cloudflare access sync successfully syncs application."""
    mock_settings.cloudflare.access.allowed_emails = ["admin@example.com"]
    mock_client = MagicMock()
    mock_client.sync_access_application.return_value = {
        "app_id": "app-1",
        "app_name": "Homelab Ingress",
        "domain": "example.com",
        "app_action": "created",
        "policy_id": "pol-1",
        "allowed_emails": ["admin@example.com"],
    }
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["access", "sync"])
        assert (
            result.exit_code,
            "Configured Cloudflare Access application" in result.output,
            mock_client.sync_access_application.call_count,
        ) == (0, True, 1)


def test_normalize_ip_cidr_variants() -> None:
    """Verify IP normalization converts addresses and networks to CIDR notation."""
    from devops_cli.cloudflare.client import _normalize_ip_cidr
    from devops_cli.exceptions.cloudflare import CloudflareAPIError

    assert (
        _normalize_ip_cidr("198.51.100.1"),
        _normalize_ip_cidr("198.51.100.0/24"),
        _normalize_ip_cidr("2001:db8::1"),
        _normalize_ip_cidr("2001:DB8::1"),
    ) == (
        "198.51.100.1/32",
        "198.51.100.0/24",
        "2001:db8::1/128",
        "2001:db8::1/128",
    )
    with pytest.raises(CloudflareAPIError):
        _normalize_ip_cidr("not-an-ip")
    with pytest.raises(CloudflareAPIError):
        _normalize_ip_cidr("fe80::1%eth0/128")


def test_cloudflare_client_sync_access_with_bypass_ips() -> None:
    """Verify synchronizing an Access application creates bypass policy for homelab IP."""
    client = CloudflareClient(token="test-token", account_id="acc-1")
    dummy_app = CloudflareAccessApplication(
        id="app-1",
        name="Homelab Ingress",
        domain="example.com",
    )
    dummy_allow = CloudflareAccessPolicy(
        id="pol-allow",
        name="Allow homelab authorized emails",
        decision="allow",
        include=[{"email": {"email": "user@example.com"}}],
    )
    dummy_bypass = CloudflareAccessPolicy(
        id="pol-bypass",
        name="homelab-public-ip-bypass",
        decision="bypass",
        include=[{"ip": {"ip": "198.51.100.1/32"}}],
    )
    with (
        patch.object(client, "list_access_applications", return_value=[dummy_app]),
        patch.object(
            client,
            "create_or_update_access_policy",
            side_effect=[dummy_allow, dummy_bypass],
        ) as mock_policy,
    ):
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
            mock_policy.call_count,
        ) == (
            "app-1",
            "existing",
            "pol-allow",
            "pol-bypass",
            ["198.51.100.1"],
            2,
        )


def test_cli_cloudflare_access_sync_with_bypass_ips(mock_settings: Settings) -> None:
    """Verify CLI access sync propagates --bypass-ips and displays bypass output."""
    mock_settings.cloudflare.access.allowed_emails = ["admin@example.com"]
    mock_client = MagicMock()
    mock_client.sync_access_application.return_value = {
        "app_id": "app-1",
        "app_name": "Homelab Ingress",
        "domain": "example.com",
        "app_action": "created",
        "policy_id": "pol-1",
        "allowed_emails": ["admin@example.com"],
        "bypass_ips": ["198.51.100.1/32"],
        "bypass_policy_id": "pol-bypass-1",
    }
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["access", "sync", "--bypass-ips", "198.51.100.1"])
        assert (
            result.exit_code,
            "Public IP bypass: 198.51.100.1/32" in result.output,
            "homelab-public-ip-bypass" in result.output,
            mock_client.sync_access_application.call_count,
        ) == (0, True, True, 1)


def test_cli_cloudflare_access_sync_settings_bypass_ip(mock_settings: Settings) -> None:
    """Verify CLI access sync resolves bypass IP from settings.cloudflare.public_ip_bypass."""
    mock_settings.cloudflare.access.allowed_emails = ["admin@example.com"]
    mock_settings.cloudflare.public_ip_bypass = "198.51.100.5"
    mock_client = MagicMock()
    mock_client.sync_access_application.return_value = {
        "app_id": "app-1",
        "app_name": "Homelab Ingress",
        "domain": "example.com",
        "app_action": "existing",
        "policy_id": "pol-1",
        "allowed_emails": ["admin@example.com"],
        "bypass_ips": ["198.51.100.5/32"],
        "bypass_policy_id": "pol-bypass-2",
    }
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["access", "sync"])
        assert (
            result.exit_code,
            mock_client.sync_access_application.call_args.kwargs.get("bypass_ips"),
        ) == (0, ["198.51.100.5"])


def test_cli_cloudflare_access_policies(mock_settings: Settings) -> None:
    """Verify devops cloudflare access policies lists application policies."""
    mock_client = MagicMock()
    mock_client.get_access_policies.return_value = [
        CloudflareAccessPolicy(
            id="989871c6-c652-45c6-b8f0-b56e761afc35",
            name="homelab-public-ip-bypass",
            decision="bypass",
            include=[{"ip": {"ip": "198.51.100.1/32"}}],
        ),
        CloudflareAccessPolicy(
            id="pol-allow",
            name="Allow homelab authorized emails",
            decision="allow",
            include=[{"email": {"email": "user@example.com"}}],
        ),
    ]
    with (
        patch("devops_cli.commands.cloudflare.load_settings", return_value=mock_settings),
        patch("devops_cli.commands.cloudflare._resolve_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["access", "policies", "app-123"])
        assert (
            result.exit_code,
            "homelab-public-ip-bypass" in result.output,
            "bypass" in result.output,
            "Allow homelab authorized emails" in result.output,
        ) == (0, True, True, True)
