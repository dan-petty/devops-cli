"""Unit tests for upstream published service status monitoring and telemetry."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.cloudflare import app as cloudflare_app
from devops_cli.commands.gh import app as gh_app
from devops_cli.commands.status_cmd import app as status_app
from devops_cli.exceptions.telemetry import ServiceStatusError
from devops_cli.models.statuspage import (
    StatuspageComponent,
    StatuspageSummary,
)
from devops_cli.telemetry.metrics import InMemoryMetricsRegistry
from devops_cli.telemetry.service_status import (
    emit_service_status_telemetry,
    fetch_all_service_statuses,
    fetch_cloudflare_status,
    fetch_github_status,
    fetch_statuspage_summary,
    filter_key_components,
    format_status_badge,
    record_service_status_in_registry,
    render_statuspage_summary,
)

runner = CliRunner()

_MOCK_PAYLOAD_OPERATIONAL = {
    "page": {
        "id": "mockpage1",
        "name": "Mock Cloud",
        "url": "https://example.com",
        "time_zone": "Etc/UTC",
        "updated_at": "2026-10-05T12:00:00Z",
    },
    "status": {
        "indicator": "none",
        "description": "All Systems Operational",
    },
    "components": [
        {
            "id": "comp1",
            "name": "Git Operations",
            "status": "operational",
            "description": "Git repos",
            "group": False,
        },
        {
            "id": "comp2",
            "name": "Actions",
            "status": "operational",
            "description": "Workflows",
            "group": False,
        },
        {
            "id": "comp3",
            "name": "Tunnel",
            "status": "operational",
            "description": "Edge tunnel",
            "group": False,
        },
    ],
    "incidents": [],
}

_MOCK_PAYLOAD_DEGRADED = {
    "page": {
        "id": "mockpage2",
        "name": "Mock Degraded",
        "url": "https://example.com",
        "time_zone": "Etc/UTC",
        "updated_at": "2026-10-05T13:00:00Z",
    },
    "status": {
        "indicator": "major",
        "description": "Partial System Outage",
    },
    "components": [
        {
            "id": "comp1",
            "name": "Git Operations",
            "status": "operational",
            "description": "Git repos",
            "group": False,
        },
        {
            "id": "comp2",
            "name": "Actions",
            "status": "major_outage",
            "description": "Workflows",
            "group": False,
        },
    ],
    "incidents": [
        {
            "id": "inc1",
            "name": "Actions Disruption",
            "status": "investigating",
            "impact": "critical",
            "created_at": "2026-10-05T12:30:00Z",
            "updated_at": "2026-10-05T12:45:00Z",
            "shortlink": "https://example.com/inc1",
        }
    ],
}


def test_statuspage_models_properties() -> None:
    """Validate statuspage model fields, severity codes, and helper predicates."""
    summary_op = StatuspageSummary.model_validate(_MOCK_PAYLOAD_OPERATIONAL)
    summary_deg = StatuspageSummary.model_validate(_MOCK_PAYLOAD_DEGRADED)

    assert (
        summary_op.is_operational,
        summary_op.status.severity_code,
        len(summary_op.active_incidents),
        summary_deg.is_operational,
        summary_deg.status.severity_code,
        len(summary_deg.active_incidents),
        summary_deg.active_incidents[0].name,
    ) == (
        True,
        0,
        0,
        False,
        2,
        1,
        "Actions Disruption",
    )


def test_statuspage_component_status_codes() -> None:
    """Validate status codes for various operational levels."""
    c_op = StatuspageComponent(id="1", name="A", status="operational")
    c_deg = StatuspageComponent(id="2", name="B", status="degraded_performance")
    c_part = StatuspageComponent(id="3", name="C", status="partial_outage")
    c_maj = StatuspageComponent(id="4", name="D", status="major_outage")
    c_maint = StatuspageComponent(id="5", name="E", status="under_maintenance")

    assert (
        c_op.status_code,
        c_deg.status_code,
        c_part.status_code,
        c_maj.status_code,
        c_maint.status_code,
    ) == (0, 1, 2, 3, 1)


def test_format_status_badge() -> None:
    """Validate status formatting tags for indicators and component statuses."""
    b_op = format_status_badge("operational")
    b_min = format_status_badge("minor")
    b_maj = format_status_badge("major")
    b_crit = format_status_badge("critical")

    assert (
        "[bold green]" in b_op,
        "[bold yellow]" in b_min,
        "[bold red]" in b_maj,
        "[bold red reverse]" in b_crit,
    ) == (True, True, True, True)


def test_filter_key_components() -> None:
    """Validate component filtering for GitHub and Cloudflare platforms."""
    summary = StatuspageSummary.model_validate(_MOCK_PAYLOAD_OPERATIONAL)
    gh_comps = filter_key_components(summary, "github")
    cf_comps = filter_key_components(summary, "cloudflare")
    other_comps = filter_key_components(summary, "custom")

    assert (
        [c.name for c in gh_comps],
        [c.name for c in cf_comps],
        len(other_comps),
    ) == (
        ["Git Operations", "Actions"],
        ["Tunnel"],
        3,
    )


def test_fetch_statuspage_summary_success() -> None:
    """Validate fetching and parsing summary payload over mocked HTTP response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = _MOCK_PAYLOAD_OPERATIONAL
    mock_resp.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("devops_cli.telemetry.service_status.new_http_client", return_value=mock_client):
        summary = fetch_statuspage_summary("https://example.com/status")

    assert (
        summary.page.name,
        summary.status.indicator,
        len(summary.components),
    ) == ("Mock Cloud", "none", 3)


def test_fetch_statuspage_summary_http_error() -> None:
    """Validate exception handling when HTTP request fails."""
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx2.ConnectError("Connection refused")
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch("devops_cli.telemetry.service_status.new_http_client", return_value=mock_client):
        with pytest.raises(ServiceStatusError, match="HTTP request failed"):
            fetch_statuspage_summary("https://example.com/status")


def test_fetch_github_and_cloudflare_status() -> None:
    """Validate top-level fetch wrappers delegating to target URLs."""
    summary = StatuspageSummary.model_validate(_MOCK_PAYLOAD_OPERATIONAL)
    with patch(
        "devops_cli.telemetry.service_status.fetch_statuspage_summary", return_value=summary
    ):
        gh = fetch_github_status()
        cf = fetch_cloudflare_status()
        all_res = fetch_all_service_statuses()

    assert (
        gh.page.name,
        cf.page.name,
        set(all_res.keys()),
    ) == ("Mock Cloud", "Mock Cloud", {"github", "cloudflare"})


def test_record_service_status_in_registry() -> None:
    """Validate recording service status gauges in InMemoryMetricsRegistry."""
    summary = StatuspageSummary.model_validate(_MOCK_PAYLOAD_DEGRADED)
    reg = InMemoryMetricsRegistry()

    record_service_status_in_registry(summary, "github", registry=reg)

    svc_gauge = reg.get_gauge(
        "devops_cli_upstream_service_status", {"service": "github", "indicator": "major"}
    )
    comp_gauge = reg.get_gauge(
        "devops_cli_upstream_component_status",
        {"service": "github", "component": "Actions", "status": "major_outage"},
    )

    assert (svc_gauge, comp_gauge) == (2.0, 3.0)


def test_emit_service_status_telemetry() -> None:
    """Validate OpenTelemetry metric emission calls."""
    summary = StatuspageSummary.model_validate(_MOCK_PAYLOAD_OPERATIONAL)
    with patch("devops_cli.telemetry.service_status.emit") as mock_emit:
        emit_service_status_telemetry(summary, "github")

    assert mock_emit.call_count >= 1


def test_render_statuspage_summary(capsys: pytest.CaptureFixture[str]) -> None:
    """Validate panel and table rendering does not fail."""
    summary = StatuspageSummary.model_validate(_MOCK_PAYLOAD_DEGRADED)
    render_statuspage_summary(summary, "GitHub")
    captured = capsys.readouterr().out

    assert ("GitHub Operational Status" in captured, "Git Operations" in captured) == (True, True)


def test_devops_gh_status_cmd() -> None:
    """Validate devops gh status command output and options."""
    summary = StatuspageSummary.model_validate(_MOCK_PAYLOAD_OPERATIONAL)
    with patch("devops_cli.telemetry.service_status.fetch_github_status", return_value=summary):
        res_table = runner.invoke(gh_app, ["status"])
        res_json = runner.invoke(gh_app, ["status", "--json"])
        res_telemetry = runner.invoke(gh_app, ["status", "--emit-telemetry"])

    parsed_json = json.loads(res_json.output)

    assert (
        res_table.exit_code,
        "GitHub Operational Status" in res_table.output,
        res_json.exit_code,
        parsed_json["page"]["name"],
        res_telemetry.exit_code,
        "Emitted GitHub service status metrics to Prometheus." in res_telemetry.output,
    ) == (
        0,
        True,
        0,
        "Mock Cloud",
        0,
        True,
    )


def test_devops_cloudflare_service_status_cmd() -> None:
    """Validate devops cloudflare service-status command output and options."""
    summary = StatuspageSummary.model_validate(_MOCK_PAYLOAD_OPERATIONAL)
    with patch("devops_cli.telemetry.service_status.fetch_cloudflare_status", return_value=summary):
        res_table = runner.invoke(cloudflare_app, ["service-status"])
        res_json = runner.invoke(cloudflare_app, ["service-status", "--json"])
        res_telemetry = runner.invoke(cloudflare_app, ["service-status", "--emit-telemetry"])

    parsed_json = json.loads(res_json.output)

    assert (
        res_table.exit_code,
        "Cloudflare Operational Status" in res_table.output,
        res_json.exit_code,
        parsed_json["page"]["name"],
        res_telemetry.exit_code,
        "Emitted Cloudflare service status metrics to Prometheus." in res_telemetry.output,
    ) == (
        0,
        True,
        0,
        "Mock Cloud",
        0,
        True,
    )


def test_devops_status_cmd() -> None:
    """Validate devops status unified command output and service filters."""
    summary = StatuspageSummary.model_validate(_MOCK_PAYLOAD_OPERATIONAL)
    with (
        patch("devops_cli.telemetry.service_status.fetch_github_status", return_value=summary),
        patch("devops_cli.telemetry.service_status.fetch_cloudflare_status", return_value=summary),
    ):
        res_all = runner.invoke(status_app, [])
        res_gh = runner.invoke(status_app, ["--service", "github"])
        res_json = runner.invoke(status_app, ["--json"])
        res_telemetry = runner.invoke(status_app, ["--emit-telemetry"])
        res_invalid = runner.invoke(status_app, ["--service", "invalid_service"])

    parsed_json = json.loads(res_json.output)

    assert (
        res_all.exit_code,
        "Monitored Upstream Platforms Status" in res_all.output,
        res_gh.exit_code,
        "Github Operational Status" in res_gh.output,
        res_json.exit_code,
        set(parsed_json.keys()),
        res_telemetry.exit_code,
        "Emitted service status metrics to Prometheus." in res_telemetry.output,
        res_invalid.exit_code != 0,
    ) == (
        0,
        True,
        0,
        True,
        0,
        {"github", "cloudflare"},
        0,
        True,
        True,
    )
