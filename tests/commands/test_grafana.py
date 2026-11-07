"""Unit tests for Grafana CLI commands and dashboard sync."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx2
import pytest

from devops_cli.config.settings import Settings
from tests.support.fakes.dial import record_connects
from tests.support.fakes.dns import DnsFake
from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_dashboard_json_templates_valid() -> None:
    """Verify built-in Grafana dashboard templates are valid JSON."""
    dashboard_dir = Path("k8s/monitoring/dashboards")
    assert dashboard_dir.exists()

    json_files = list(dashboard_dir.glob("*.json"))
    assert len(json_files) >= 3

    for f in json_files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert "title" in data
        assert "panels" in data
        assert "uid" in data
        assert isinstance(data["panels"], list)


GRAFANA_ENV = {
    "DEVOPS_CLI_GRAFANA_URL": "http://example.com:3000",
    "DEVOPS_CLI_GRAFANA_TOKEN": "glsa-test",
}


def test_grafana_dashboards_sync_dry_run(cli: Callable[..., Any], web: WebFake) -> None:
    """Verify grafana dashboards sync in dry-run mode."""
    result = cli("--dry-run", "grafana", "dashboards", "sync")

    assert (result.exit_code, "devops grafana dashboards sync" in result.output, web.recorded) == (
        0,
        True,
        [],
    )


def test_grafana_dashboards_sync_success(cli: Callable[..., Any], web: WebFake) -> None:
    """Verify successful sync of the built-in dashboards: one save for each file."""
    web.serve(
        lambda request: httpx2.Response(200, json={"slug": "test-dashboard", "status": "success"})
    )

    result = cli("grafana", "dashboards", "sync", env=GRAFANA_ENV)

    saves = [request for request in web.sent if request.method == "POST"]
    assert (result.exit_code, "Dashboard sync completed" in result.output, len(saves) >= 3) == (
        0,
        True,
        True,
    )


def _sync_against(
    cli: Callable[..., Any],
    tmp_path: Path,
    web: WebFake,
    *,
    refused: str | None = None,
    provisioned: bool = False,
) -> tuple[int, str, list[tuple[str, str]]]:
    """Sync dashboards `a`, `b` and `c`; Grafana answers the save of `refused` with a 400."""
    for uid in ("a", "b", "c"):
        (tmp_path / f"{uid}.json").write_text(
            json.dumps({"uid": uid, "title": f"Dashboard {uid}", "panels": []}), encoding="utf-8"
        )
    requests: list[tuple[str, str]] = []

    def grafana(request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET":
            requests.append(("GET", request.url.path.rsplit("/", 1)[-1]))
            return httpx2.Response(
                200, json={"dashboard": {}, "meta": {"provisioned": provisioned}}
            )
        uid = json.loads(request.content)["dashboard"]["uid"]
        requests.append(("POST", uid))
        return httpx2.Response(400 if uid == refused else 200, json={})

    web.serve(grafana)
    result = cli("grafana", "dashboards", "sync", "--dir", str(tmp_path), env=GRAFANA_ENV)
    return result.exit_code, result.output, requests


def test_sync_tries_every_dashboard_and_fails_when_one_is_refused(
    cli: Callable[..., Any], tmp_path: Path, web: WebFake
) -> None:
    """A refused save of one dashboard still saves the others, then exits 1 with the counts."""
    exit_code, output, requests = _sync_against(cli, tmp_path, web, refused="b")

    assert (exit_code, requests, "2 synced, 0 skipped, 1 failed" in output) == (
        1,
        [("POST", "a"), ("POST", "b"), ("GET", "b"), ("POST", "c")],
        True,
    )


def test_sync_skips_a_dashboard_grafana_holds_as_provisioned(
    cli: Callable[..., Any], tmp_path: Path, web: WebFake
) -> None:
    """A refused save of a provisioned dashboard is a skip: the file is named, the exit is 0."""
    exit_code, output, _ = _sync_against(cli, tmp_path, web, refused="b", provisioned=True)

    assert (exit_code, "2 synced, 1 skipped, 0 failed" in output, "b.json" in output) == (
        0,
        True,
        True,
    )


def test_each_read_command_prints_what_grafana_holds_and_import_saves_a_dashboard(
    cli: Callable[..., Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, web: WebFake
) -> None:
    """The list, export, import, search, datasources and alerts commands each end with exit 0."""
    monkeypatch.chdir(tmp_path)
    holds = {
        "/api/dashboards/uid/cluster-overview": {"dashboard": {"title": "Exported"}, "meta": {}},
        "/api/search": [
            {"uid": "cluster-overview", "title": "Cluster Overview", "folderTitle": "General"}
        ],
        "/api/datasources": [
            {"name": "Prometheus", "type": "prometheus", "url": "http://prometheus:9090"}
        ],
        "/api/v1/provisioning/alert-rules": [
            {"uid": "alert-1", "title": "High CPU", "folderUID": "general", "condition": "A"}
        ],
    }
    web.serve(
        lambda request: httpx2.Response(
            200,
            json=holds.get(request.url.path, {"slug": "imported-dash"}),
        )
    )
    sample = tmp_path / "dash.json"
    sample.write_text(json.dumps({"title": "Sample", "panels": []}), encoding="utf-8")
    export_out = tmp_path / "exported.json"

    results = [
        cli("grafana", "dashboards", "list", env=GRAFANA_ENV),
        cli(
            "grafana",
            "dashboards",
            "export",
            "cluster-overview",
            "--output",
            str(export_out),
            env=GRAFANA_ENV,
        ),
        cli("grafana", "dashboards", "import", str(sample), env=GRAFANA_ENV),
        cli("grafana", "search", "--query", "cluster", env=GRAFANA_ENV),
        cli("grafana", "datasources", env=GRAFANA_ENV),
        cli("grafana", "alerts", env=GRAFANA_ENV),
    ]

    assert ([result.exit_code for result in results], json.loads(export_out.read_text())) == (
        [0] * 6,
        holds["/api/dashboards/uid/cluster-overview"],
    )
    assert "Cluster Overview" in results[0].output


def test_grafana_client_args_masked_token_fallback(dns: DnsFake) -> None:
    dns.answer_every_name()
    from devops_cli.commands.grafana import _client_args

    settings_masked = Settings()
    settings_masked.grafana.url = "http://example.com:3000"
    with (
        patch("devops_cli.commands.grafana.get_grafana_token", return_value="******"),
        patch(
            "devops_cli.k8s.credentials.get_or_mint_grafana_auth",
            return_value=("minted-token", None),
        ) as mock_mint,
    ):
        base_url, headers = _client_args(settings_masked)
        assert (
            base_url,
            headers.get("Authorization"),
            mock_mint.called,
        ) == ("http://example.com:3000", "Bearer minted-token", True)


def test_a_refused_grafana_address_ends_the_dashboard_sync_with_the_refusal(
    cli: Callable[..., Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dns: DnsFake
) -> None:
    """Old vs new (#2424): a refused address ends the sync with the refusal, not as a failed file.

    The connect refuses the private answer without the flag. The refusal applies to each file, so
    the sync stops at the first file and exits with the status of `SSRFBlockedError`
    (`SSRF_BLOCKED`, docs/ERRORS.md). Before, each file reported the refusal as a failed file, and
    the sync exited 1.
    """
    for uid in ("a", "b"):
        (tmp_path / f"{uid}.json").write_text(
            json.dumps({"uid": uid, "title": f"Dashboard {uid}", "panels": []}), encoding="utf-8"
        )
    dns.script("example.com", ["192.0.2.10"])
    recorder = record_connects(monkeypatch, [])

    result = cli(
        "grafana",
        "dashboards",
        "sync",
        "--dir",
        str(tmp_path),
        env={
            "DEVOPS_CLI_GRAFANA_URL": "http://example.com:3000",
            "DEVOPS_CLI_GRAFANA_TOKEN": "glsa-test",
            "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK": "false",
        },
    )

    assert (
        result.exit_code,
        type(result.exception),
        result.output.count("the loopback egress level refuses"),
        recorder.dialled,
    ) == (2, SystemExit, 1, [])
