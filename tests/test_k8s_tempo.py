"""Unit tests for Tempo Helm values, stack integration, and k8s command integration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_tempo_stack_contract_and_datasource_links() -> None:
    """Verify Tempo Helm release, values, collector exporter, Grafana links, and zero Jaeger in k8s/."""
    from devops_cli.commands.k8s.stack_lifecycle import _HELM_RELEASES_BY_STACK
    from devops_cli.config.defaults import DEFAULT_K8S_DIR

    infra_releases = _HELM_RELEASES_BY_STACK["infra"]
    tempo_release = next((r for r in infra_releases if r["name"] == "tempo"), None)

    tempo_values = yaml.safe_load(Path("k8s/otel/tempo-values.yaml").read_text(encoding="utf-8"))
    collector_values = yaml.safe_load(Path("k8s/otel/values.yaml").read_text(encoding="utf-8"))
    grafana_values = yaml.safe_load(
        Path("k8s/monitoring/grafana-values.yaml").read_text(encoding="utf-8")
    )
    datasources = (
        grafana_values.get("datasources", {}).get("datasources.yaml", {}).get("datasources", [])
    )
    tempo_ds = next((ds for ds in datasources if ds.get("name") == "Tempo"), {})
    tempo_json_data = tempo_ds.get("jsonData", {})

    k8s_jaeger_refs = [
        str(path.relative_to(Path("k8s")))
        for path in sorted(Path("k8s").rglob("*"))
        if path.is_file() and "jaeger" in path.read_text(encoding="utf-8").lower()
    ]

    assert (
        tempo_release,
        tempo_values.get("persistence", {}).get("storageClassName"),
        tempo_values.get("tempo", {})
        .get("compactor", {})
        .get("compaction", {})
        .get("block_retention"),
        collector_values.get("config", {})
        .get("exporters", {})
        .get("otlp_grpc/tempo", {})
        .get("endpoint"),
        tempo_ds.get("uid"),
        tempo_json_data.get("tracesToLogsV2", {}).get("datasourceUid"),
        tempo_json_data.get("tracesToProfiles", {}).get("datasourceUid"),
        tempo_json_data.get("lokiSearch", {}).get("datasourceUid"),
        k8s_jaeger_refs,
    ) == (
        {
            "name": "tempo",
            "chart": "grafana-community/tempo",
            "namespace": "otel",
            "values": str(DEFAULT_K8S_DIR / "otel" / "tempo-values.yaml"),
            "version": "3.1.0",
        },
        "local-path",
        "168h",
        "tempo.otel.svc.cluster.local:4317",
        "tempo",
        "loki",
        "pyroscope",
        "loki",
        [],
    )


def test_k8s_port_forward_tempo_dry_run(runner: CliRunner) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        from devops_cli.commands.k8s import app as k8s_app

        result = runner.invoke(
            k8s_app,
            ["port-forward", "--stack", "infra"],
        )
        assert (
            result.exit_code,
            "tempo.url" in result.output,
            "3200" in result.output,
            "pyroscope.url" in result.output,
            "4040" in result.output,
        ) == (0, True, True, True, True)
    finally:
        set_dry_run(False)


def test_k8s_configure_urls_tempo_dry_run(runner: CliRunner) -> None:
    from devops_cli.dry_run import set_dry_run

    set_dry_run(True)
    try:
        from devops_cli.commands.k8s import app as k8s_app

        result = runner.invoke(
            k8s_app,
            ["configure-urls", "--stack", "infra"],
        )
        assert (
            result.exit_code,
            "tempo.url" in result.output,
            "pyroscope.url" in result.output,
        ) == (0, True, True)
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_shows_tempo_connection_info(runner: CliRunner) -> None:
    from unittest.mock import MagicMock, patch

    from devops_cli.commands.k8s import app as k8s_app
    from devops_cli.dry_run import set_dry_run

    set_dry_run(False)
    with (
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch("devops_cli.commands.k8s._run_cmd") as mock_run,
        patch("devops_cli.commands.k8s.port_forward"),
        patch(
            "devops_cli.k8s.credentials.sync_k8s_credentials",
            return_value={"argocd": True, "grafana": True},
        ),
    ):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = runner.invoke(k8s_app, ["deploy-stack", "--stack", "infra", "--no-push-secrets"])
        assert (
            result.exit_code,
            "Tempo HTTP API: http://localhost:3200 (namespace: otel)" in result.output,
            "Tempo OTLP Traces: localhost:4317 (gRPC) / localhost:4318 (HTTP)" in result.output,
            "Pyroscope UI: http://localhost:4040 (namespace: monitoring)" in result.output,
        ) == (0, True, True, True)
