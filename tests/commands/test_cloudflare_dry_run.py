"""Tests for dry-run request plans and classifications across 10 Cloudflare commands.

Issue #2252: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.cloudflare import (
    access_policies,
    access_status,
    access_sync,
    cloudflare_service_status,
    cloudflare_status,
    dns_delete,
    dns_list,
    dns_sync,
    tunnel_routes,
    tunnel_sync,
)
from devops_cli.config.settings import Settings
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

CLOUDFLARE_COMMANDS = [
    ("cloudflare status", cloudflare_status, ["cloudflare", "status", "--dry-run"]),
    (
        "cloudflare service-status",
        cloudflare_service_status,
        ["cloudflare", "service-status", "--dry-run"],
    ),
    ("cloudflare dns list", dns_list, ["cloudflare", "dns", "list", "--dry-run"]),
    (
        "cloudflare dns sync",
        dns_sync,
        [
            "cloudflare",
            "dns",
            "sync",
            "--domain",
            "example.com",
            "--tunnel-cname",
            "cf-tunnel.example.com",
            "--dry-run",
        ],
    ),
    (
        "cloudflare dns delete",
        dns_delete,
        ["cloudflare", "dns", "delete", "test.example.com", "--dry-run"],
    ),
    (
        "cloudflare tunnel routes",
        tunnel_routes,
        ["cloudflare", "tunnel", "routes", "--tunnel-id", "test-tunnel", "--dry-run"],
    ),
    (
        "cloudflare tunnel sync",
        tunnel_sync,
        [
            "cloudflare",
            "tunnel",
            "sync",
            "--tunnel-id",
            "test-tunnel",
            "--domain",
            "example.com",
            "--dry-run",
        ],
    ),
    ("cloudflare access status", access_status, ["cloudflare", "access", "status", "--dry-run"]),
    (
        "cloudflare access sync",
        access_sync,
        [
            "cloudflare",
            "access",
            "sync",
            "--domain",
            "example.com",
            "--allowed-emails",
            "dev@example.com",
            "--dry-run",
        ],
    ),
    (
        "cloudflare access policies",
        access_policies,
        ["cloudflare", "access", "policies", "app-12345", "--dry-run"],
    ),
]


@pytest.fixture
def block_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real subprocess, socket, or HTTP client execution occurs during dry run."""

    def _fail_process(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected process invocation: {args}, {kwargs}")

    def _fail_socket(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected socket call: {args}, {kwargs}")

    def _fail_http(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected HTTP request: {args}, {kwargs}")

    monkeypatch.setattr(subprocess, "run", _fail_process)
    monkeypatch.setattr(subprocess, "Popen", _fail_process)
    monkeypatch.setattr(socket.socket, "connect", _fail_socket)
    monkeypatch.setattr(socket, "getaddrinfo", _fail_socket)
    monkeypatch.setattr(httpx2.Client, "send", _fail_http)
    monkeypatch.setattr(httpx2.Client, "request", _fail_http)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", _fail_http)


@pytest.fixture(autouse=True)
def mock_cloudflare_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide dummy settings so dry-run commands do not fail on missing tokens or domain."""
    dummy_settings = Settings()
    dummy_settings.cloudflare.account_id = "test-account-id"
    dummy_settings.cloudflare.zone_id = "test-zone-id"
    dummy_settings.cloudflare.domain = "example.com"
    dummy_settings.cloudflare.tunnel = "test-tunnel-id"

    monkeypatch.setattr(
        "devops_cli.commands.cloudflare.load_settings",
        lambda: dummy_settings,
    )
    monkeypatch.setattr(
        "devops_cli.commands.cloudflare.get_cloudflare_api_token",
        lambda _s: "test-token",
    )


def test_command_dry_run_class_declarations() -> None:
    """Criterion 1: all 10 Cloudflare commands declare request-plan."""
    for name, callback, _ in CLOUDFLARE_COMMANDS:
        cls = get_dry_run_class(callback)
        assert cls == "request-plan", (
            f"Expected '{name}' callback to declare dry_run_class('request-plan'), got '{cls}'"
        )


def test_gaps_file_does_not_contain_cloudflare_commands() -> None:
    """Criterion 1: all 10 Cloudflare commands are removed from dry_run_gaps.json."""
    gaps_path = Path("tests/fixtures/dry_run_gaps.json")
    assert gaps_path.exists()
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))

    expected_removed = [
        "cloudflare access policies",
        "cloudflare access status",
        "cloudflare access sync",
        "cloudflare dns delete",
        "cloudflare dns list",
        "cloudflare dns sync",
        "cloudflare service-status",
        "cloudflare status",
        "cloudflare tunnel routes",
        "cloudflare tunnel sync",
    ]
    remaining = [cmd for cmd in expected_removed if cmd in gaps]
    assert not remaining, f"Commands still present in dry_run_gaps.json: {remaining}"


@pytest.mark.parametrize("name,callback,argv", CLOUDFLARE_COMMANDS)
def test_cloudflare_commands_make_no_external_requests(
    block_external_calls: None,
    name: str,
    callback: Any,
    argv: list[str],
) -> None:
    """Criterion 2: devops <cmd> --dry-run and devops --dry-run <cmd> make no external calls and print plan."""
    # Test 1: devops <command> --dry-run
    res1 = runner.invoke(app, argv)
    assert res1.exit_code == 0, (
        f"{name} with --dry-run failed with code {res1.exit_code}: {res1.output}"
    )
    assert "1." in res1.output or "Planned" in res1.output or "Plan for" in res1.output, (
        f"{name} output missing request plan: {res1.output}"
    )

    # Test 2: devops --dry-run <command>
    root_argv = ["--dry-run", *[arg for arg in argv if arg != "--dry-run"]]
    res2 = runner.invoke(app, root_argv)
    assert res2.exit_code == 0, (
        f"{name} with root --dry-run failed with code {res2.exit_code}: {res2.output}"
    )
    assert "1." in res2.output or "Planned" in res2.output or "Plan for" in res2.output, (
        f"{name} root dry-run output missing request plan: {res2.output}"
    )


def test_cloudflare_json_dry_run_output(block_external_calls: None) -> None:
    """Criterion 3: request-plan commands with --format json or --json return dry_run: true and planned requests."""
    # 1. status
    res_status = runner.invoke(app, ["cloudflare", "status", "--format", "json", "--dry-run"])
    assert res_status.exit_code == 0, res_status.output
    data_status = json.loads(res_status.output)
    assert data_status.get("dry_run") is True
    assert "requests" in data_status
    assert "token" in data_status

    # 2. service-status
    res_svc = runner.invoke(app, ["cloudflare", "service-status", "--format", "json", "--dry-run"])
    assert res_svc.exit_code == 0, res_svc.output
    data_svc = json.loads(res_svc.output)
    assert data_svc.get("dry_run") is True
    assert "requests" in data_svc

    # 3. dns list
    res_dns_list = runner.invoke(
        app, ["cloudflare", "dns", "list", "--format", "json", "--dry-run"]
    )
    assert res_dns_list.exit_code == 0, res_dns_list.output
    data_dns_list = json.loads(res_dns_list.output)
    assert data_dns_list.get("dry_run") is True
    assert "requests" in data_dns_list

    # 4. dns sync
    res_dns_sync = runner.invoke(
        app,
        [
            "cloudflare",
            "dns",
            "sync",
            "--domain",
            "example.com",
            "--tunnel-cname",
            "cf.example.com",
            "--json",
            "--dry-run",
        ],
    )
    assert res_dns_sync.exit_code == 0, res_dns_sync.output
    data_dns_sync = json.loads(res_dns_sync.output)
    assert data_dns_sync.get("dry_run") is True
    assert "requests" in data_dns_sync

    # 5. tunnel sync
    res_tunnel_sync = runner.invoke(
        app,
        [
            "cloudflare",
            "tunnel",
            "sync",
            "--tunnel-id",
            "test-tunnel",
            "--domain",
            "example.com",
            "--format",
            "json",
            "--dry-run",
        ],
    )
    assert res_tunnel_sync.exit_code == 0, res_tunnel_sync.output
    data_tunnel_sync = json.loads(res_tunnel_sync.output)
    assert data_tunnel_sync.get("dry_run") is True
    assert "requests" in data_tunnel_sync

    # 6. access sync
    res_access_sync = runner.invoke(
        app,
        [
            "cloudflare",
            "access",
            "sync",
            "--domain",
            "example.com",
            "--allowed-emails",
            "user@example.com",
            "--format",
            "json",
            "--dry-run",
        ],
    )
    assert res_access_sync.exit_code == 0, res_access_sync.output
    data_access_sync = json.loads(res_access_sync.output)
    assert data_access_sync.get("dry_run") is True
    assert "requests" in data_access_sync


def test_dry_run_plans_match_client_calls() -> None:
    """Criterion 4: request plans match the HTTP methods and paths dispatched by CloudflareClient."""
    from devops_cli.cloudflare.cloudflare_plans import (
        plan_cloudflare_access_policies,
        plan_cloudflare_access_status,
        plan_cloudflare_access_sync,
        plan_cloudflare_dns_delete,
        plan_cloudflare_dns_list,
        plan_cloudflare_dns_sync,
        plan_cloudflare_status,
        plan_cloudflare_tunnel_routes,
        plan_cloudflare_tunnel_sync,
    )
    from devops_cli.config.constants import CONST_URL_CLOUDFLARE_API_BASE

    # 1. status
    p_status = plan_cloudflare_status(account_id="acc-1", zone_id="zone-1")
    assert p_status[0].method == "GET"
    assert p_status[0].target == f"{CONST_URL_CLOUDFLARE_API_BASE}/user/tokens/verify"
    assert p_status[1].method == "GET"
    assert p_status[1].target == f"{CONST_URL_CLOUDFLARE_API_BASE}/zones/zone-1"

    # 2. dns list
    p_dns_list = plan_cloudflare_dns_list(zone_id="zone-1", record_type="CNAME", name="app")
    assert p_dns_list[0].method == "GET"
    assert "zones/zone-1/dns_records" in p_dns_list[0].target
    assert "type=CNAME" in p_dns_list[0].target
    assert "name=app" in p_dns_list[0].target

    # 3. dns sync
    p_dns_sync = plan_cloudflare_dns_sync(
        domain="example.com",
        tunnel_id_or_cname="tunnel-uuid",
        subdomains=("app",),
        zone_id="zone-1",
        account_id="acc-1",
    )
    assert any(r.method == "GET" and "zones/zone-1/dns_records" in r.target for r in p_dns_sync)
    assert any(r.method == "POST" and "zones/zone-1/dns_records" in r.target for r in p_dns_sync)
    assert any(r.method == "PUT" and "zones/zone-1/dns_records" in r.target for r in p_dns_sync)

    # 4. dns delete
    p_dns_del = plan_cloudflare_dns_delete(
        targets=["app.example.com"],
        zone_id="zone-1",
    )
    assert p_dns_del[0].method == "GET"
    assert p_dns_del[1].method == "DELETE"
    assert "zones/zone-1/dns_records" in p_dns_del[1].target

    # 5. tunnel routes
    p_tr_uuid = plan_cloudflare_tunnel_routes(
        tunnel_id="f47ac10b-58cc-4372-a567-0e02b2c3d479", account_id="acc-1"
    )
    assert p_tr_uuid[-1].method == "GET"
    assert (
        "accounts/acc-1/cfd_tunnel/f47ac10b-58cc-4372-a567-0e02b2c3d479/configurations"
        in p_tr_uuid[-1].target
    )

    p_tr_name = plan_cloudflare_tunnel_routes(tunnel_id="my-tunnel", account_id="acc-1")
    assert p_tr_name[0].method == "GET"
    assert "accounts/acc-1/cfd_tunnel?name=my-tunnel" in p_tr_name[0].target
    assert "accounts/acc-1/cfd_tunnel/<tunnel-id>/configurations" in p_tr_name[1].target

    # 6. tunnel sync
    p_ts = plan_cloudflare_tunnel_sync(
        tunnel_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
        domain="example.com",
        service="http://svc:80",
        subdomains=("app",),
        account_id="acc-1",
    )
    assert p_ts[0].method == "GET"
    assert p_ts[1].method == "PUT"
    assert (
        "accounts/acc-1/cfd_tunnel/f47ac10b-58cc-4372-a567-0e02b2c3d479/configurations"
        in p_ts[1].target
    )
    assert p_ts[1].stdin is not None
    assert "http://svc:80" in p_ts[1].stdin

    # 7. access status
    p_as = plan_cloudflare_access_status(account_id="acc-1")
    assert p_as[0].method == "GET"
    assert "accounts/acc-1/access/apps" in p_as[0].target

    # 8. access sync
    p_async = plan_cloudflare_access_sync(
        domain="example.com",
        allowed_emails=["u@example.com"],
        bypass_ips=["1.2.3.4"],
        account_id="acc-1",
    )
    assert p_async[0].method == "GET"
    assert any(r.method == "POST" and "accounts/acc-1/access/apps" in r.target for r in p_async)
    assert any(
        r.method == "POST" and "policies" in r.target and "bypass" in (r.condition or "").lower()
        for r in p_async
    )

    # 9. access policies
    p_ap = plan_cloudflare_access_policies(app_id="app-1", account_id="acc-1")
    assert p_ap[0].method == "GET"
    assert "accounts/acc-1/access/apps/app-1/policies" in p_ap[0].target
