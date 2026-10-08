"""Unit tests for Grafana CLI commands and dashboard sync."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.grafana import app as grafana_app
from devops_cli.config.settings import Settings
from devops_cli.main import app as main_app

runner = CliRunner()


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


def test_grafana_dashboards_sync_dry_run() -> None:
    """Verify grafana dashboards sync in dry-run mode."""
    result = runner.invoke(main_app, ["--dry-run", "grafana", "dashboards", "sync"])
    assert result.exit_code == 0
    assert "Would run delegated command: devops grafana dashboards sync" in result.output


def test_grafana_dashboards_sync_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify successful sync of dashboards with mock Grafana API."""
    import httpx2

    mock_settings = Settings()
    mock_settings.grafana.url = "http://localhost:3000"
    mock_settings.ai.allow_private_network = True
    monkeypatch.setattr("devops_cli.commands.grafana.load_settings", lambda: mock_settings)

    class DummyResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, str]:
            return {"slug": "test-dashboard", "status": "success"}

    class DummyClient:
        def __enter__(self) -> DummyClient:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def post(self, url: str, **kwargs: object) -> DummyResponse:
            return DummyResponse()

    monkeypatch.setattr(httpx2, "Client", lambda *args, **kwargs: DummyClient())

    result = runner.invoke(grafana_app, ["dashboards", "sync"])
    assert result.exit_code == 0
    assert "Dashboard sync completed" in result.output


class StubGrafana:
    """A Grafana that answers each dashboard post by uid and records every request.

    `provisioned` is the `meta.provisioned` a dashboard lookup returns; `None` fails the lookup.
    """

    def __init__(self, post_status: dict[str, int], provisioned: bool | None = False) -> None:
        self.post_status = post_status
        self.provisioned = provisioned
        self.requests: list[tuple[str, str]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET":
            uid = request.url.path.rsplit("/", 1)[-1]
            self.requests.append(("GET", uid))
            if self.provisioned is None:
                return httpx2.Response(404, json={"message": "Dashboard not found"})
            return httpx2.Response(
                200, json={"dashboard": {"uid": uid}, "meta": {"provisioned": self.provisioned}}
            )
        uid = json.loads(request.content)["dashboard"]["uid"]
        self.requests.append(("POST", uid))
        status = self.post_status.get(uid, 200)
        return httpx2.Response(status, json={"status": "success" if status == 200 else "error"})


def _sync_against(
    stub: StubGrafana, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, str]:
    """Sync three dashboards, `a`, `b` and `c`, to the stub; return the exit code and output."""
    for uid in ("a", "b", "c"):
        (tmp_path / f"{uid}.json").write_text(
            json.dumps({"uid": uid, "title": f"Dashboard {uid}", "panels": []}), encoding="utf-8"
        )
    real_client = httpx2.Client
    monkeypatch.setattr("devops_cli.commands.grafana.load_settings", Settings)
    monkeypatch.setattr(
        "devops_cli.commands.grafana._client_args",
        lambda settings: ("http://example.com", {"Content-Type": "application/json"}),
    )
    monkeypatch.setattr(
        httpx2,
        "Client",
        lambda *args, **kwargs: real_client(transport=httpx2.MockTransport(stub)),
    )
    result = runner.invoke(grafana_app, ["dashboards", "sync", "--dir", str(tmp_path)])
    return result.exit_code, result.output


def test_sync_tries_every_dashboard_and_fails_when_one_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a 500 on one dashboard still posts the others, then exits 1 with the counts."""
    stub = StubGrafana({"b": 500})

    exit_code, output = _sync_against(stub, tmp_path, monkeypatch)

    assert (exit_code, stub.requests, "2 synced, 0 skipped, 1 failed" in output) == (
        1,
        [("POST", "a"), ("POST", "b"), ("POST", "c")],
        True,
    )


@pytest.mark.parametrize(
    ("provisioned", "exit_code", "counts"),
    [
        (True, 0, "2 synced, 1 skipped, 0 failed"),
        (False, 1, "2 synced, 0 skipped, 1 failed"),
        (None, 1, "2 synced, 0 skipped, 1 failed"),
    ],
    ids=["provisioned", "not-provisioned", "lookup-fails"],
)
def test_sync_skips_a_dashboard_grafana_holds_as_provisioned(
    provisioned: bool | None,
    exit_code: int,
    counts: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a 400 on a provisioned dashboard counts as skipped, read from `meta.provisioned`.

    The Grafana sidecar provisions the stack's dashboards, and Grafana refuses an API save
    over a provisioned uid; a 400 on any other dashboard, or one whose lookup fails, is still a
    failure.
    """
    stub = StubGrafana({"b": 400}, provisioned=provisioned)

    result = _sync_against(stub, tmp_path, monkeypatch)

    assert (result[0], stub.requests, counts in result[1], "b.json" in result[1]) == (
        exit_code,
        [("POST", "a"), ("POST", "b"), ("GET", "b"), ("POST", "c")],
        True,
        True,
    )


def test_grafana_commands_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify grafana dashboards list, export, import, search, datasources, and alerts execution."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_dashboards = [
        {
            "uid": "cluster-overview",
            "title": "Cluster Overview",
            "folderTitle": "General",
            "url": "/d/cluster",
            "type": "dash-db",
        }
    ]
    mock_datasources = [
        {
            "name": "Prometheus",
            "type": "prometheus",
            "url": "http://prometheus:9090",
            "isDefault": True,
        }
    ]
    mock_alerts = [
        {
            "uid": "alert-1",
            "title": "High CPU",
            "folderUID": "general",
            "condition": "A",
        }
    ]
    mock_dashboard_detail = {
        "dashboard": {
            "title": "Exported Dash",
            "panels": [],
        },
        "meta": {},
    }

    mock_settings = Settings()
    mock_settings.grafana.url = "http://localhost:3000"
    mock_settings.ai.allow_private_network = True

    endpoint_map = {
        "dashboards/uid": mock_dashboard_detail,
        "search": mock_dashboards,
        "datasources": mock_datasources,
        "alert-rules": mock_alerts,
    }

    def mock_get(*args: object, **kwargs: object) -> MagicMock:
        resp = MagicMock(status_code=200)
        url_str = next(
            (
                str(a)
                for a in (*args, kwargs.get("url", ""))
                if "http" in str(a) or "/api/" in str(a)
            ),
            "",
        )
        resp.json.return_value = next(
            (val for key, val in endpoint_map.items() if key in url_str), []
        )
        return resp

    def mock_post(*args: object, **kwargs: object) -> MagicMock:
        return MagicMock(
            status_code=200, json=lambda: {"slug": "imported-dash", "status": "success"}
        )

    monkeypatch.chdir(tmp_path)
    sample_dash_file = tmp_path / "dash.json"
    sample_dash_file.write_text(
        json.dumps({"title": "Sample Dashboard", "panels": []}), encoding="utf-8"
    )
    export_out = tmp_path / "test_exported.json"

    with (
        patch("devops_cli.commands.grafana.httpx2.Client.get", side_effect=mock_get),
        patch("devops_cli.commands.grafana.httpx2.Client.post", side_effect=mock_post),
        patch("devops_cli.commands.grafana.load_settings", return_value=mock_settings),
    ):
        res_list = runner.invoke(grafana_app, ["dashboards", "list"])
        res_export = runner.invoke(
            grafana_app,
            ["dashboards", "export", "cluster-overview", "--output", str(export_out)],
        )
        export_created = export_out.exists()
        res_import = runner.invoke(grafana_app, ["dashboards", "import", str(sample_dash_file)])
        res_search = runner.invoke(grafana_app, ["search", "--query", "cluster"])
        res_ds = runner.invoke(grafana_app, ["datasources"])
        res_alerts = runner.invoke(grafana_app, ["alerts"])

        assert (
            res_list.exit_code,
            res_export.exit_code,
            export_created,
            res_import.exit_code,
            res_search.exit_code,
            res_ds.exit_code,
            res_alerts.exit_code,
        ) == (0, 0, True, 0, 0, 0, 0)


@pytest.mark.usefixtures("public_dns")
def test_grafana_client_args_masked_token_fallback() -> None:
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
