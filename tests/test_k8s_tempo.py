"""Unit tests for Tempo Helm values, stack integration, and k8s command integration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _names_jaeger_outside_datasource_deletions(path: Path) -> bool:
    """Whether a file under k8s/ names Jaeger anywhere but in Grafana's `deleteDatasources`.

    Grafana deletes each datasource that list names when it starts, so a name there removes Jaeger
    and deploys nothing (#2036). Every other mention, a comment included, still counts.
    """
    text = path.read_text(encoding="utf-8").lower()
    if path != Path("k8s/monitoring/grafana-values.yaml"):
        return "jaeger" in text
    provisioning = yaml.safe_load(text)["datasources"]["datasources.yaml"]
    deleted = sum(entry["name"] == "jaeger" for entry in provisioning.get("deletedatasources", []))
    return text.count("jaeger") > deleted


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
        if path.is_file()
        and (
            path != Path("k8s/otel/values.yaml")
            or collector_values.get("config", {}).get("receivers", {}).get("jaeger") is not None
        )
        and _names_jaeger_outside_datasource_deletions(path)
    ]

    assert (
        tempo_release,
        tempo_values.get("persistence", {}).get("storageClassName"),
        tempo_values.get("tempo", {}).get("retention"),
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


def test_tempo_runs_the_charts_own_config_so_a_chart_bump_cannot_leave_a_stale_copy() -> None:
    """The values leave the chart's `config` template to the chart. Tempo 3 removed the `compactor`
    and `ingester` blocks, and a copy of the Tempo 2 template kept in the values made the pod exit
    at start (#1813). Retention is `tempo.retention`, which the chart turns into the block retention."""
    values = yaml.safe_load(Path("k8s/otel/tempo-values.yaml").read_text(encoding="utf-8"))

    assert (
        "config" in values,
        "compactor" in values.get("tempo", {}),
        values.get("tempo", {}).get("retention"),
    ) == (False, False, "168h")


def test_tempo_pod_meets_the_otel_namespaces_restricted_pod_security() -> None:
    """The otel namespace enforces PodSecurity restricted, so the chart's pod and its tempo
    container must set every control restricted requires, or no pod is ever admitted (#1627)."""
    namespaces = [
        doc
        for doc in yaml.safe_load_all(Path("k8s/namespaces.yaml").read_text(encoding="utf-8"))
        if doc and doc.get("kind") == "Namespace"
    ]
    otel_labels = next(n for n in namespaces if n["metadata"]["name"] == "otel")["metadata"][
        "labels"
    ]
    values = yaml.safe_load(Path("k8s/otel/tempo-values.yaml").read_text(encoding="utf-8"))
    pod = values.get("securityContext", {})
    container = values.get("tempo", {}).get("securityContext", {})

    assert (
        otel_labels.get("pod-security.kubernetes.io/enforce"),
        pod.get("runAsNonRoot"),
        pod.get("seccompProfile", {}).get("type"),
        container.get("allowPrivilegeEscalation"),
        container.get("capabilities", {}).get("drop"),
        container.get("readOnlyRootFilesystem"),
        values.get("tempo", {}).get("metricsGenerator", {}).get("enabled", False),
    ) == ("restricted", True, "RuntimeDefault", False, ["ALL"], True, False)


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
