"""Unit tests for Kubernetes stream-logs, diff-helm, and chaos commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.k8s.chaos import execute_chaos_experiment
from devops_cli.k8s.diff import diff_helm_release
from devops_cli.k8s.logs import stream_multi_pod_logs

runner = CliRunner()


def test_stream_multi_pod_logs_dry_run() -> None:
    rc = stream_multi_pod_logs("test-app", dry_run=True)
    assert rc == 0


@patch("shutil.which", return_value="/usr/local/bin/stern")
@patch("devops_cli.k8s.logs.run_subprocess")
def test_stream_multi_pod_logs_stern(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    rc = stream_multi_pod_logs("test-app", namespace="prod", follow=False)
    assert rc == 0
    assert mock_run.called


@patch("shutil.which", return_value=None)
@patch("devops_cli.k8s.logs.run_subprocess")
def test_stream_multi_pod_logs_kubectl_fallback(mock_run: MagicMock, mock_which: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    rc = stream_multi_pod_logs("test-app", namespace="default", follow=False)
    assert rc == 0
    assert mock_run.called


def test_diff_helm_release_dry_run(tmp_path: Path) -> None:
    chart = tmp_path / "mychart"
    chart.mkdir()
    rc, output = diff_helm_release("my-rel", chart, dry_run=True)
    assert rc == 0
    assert "Deployment" in output


@patch("devops_cli.k8s.diff.run_subprocess")
def test_diff_helm_release_live(mock_run: MagicMock, tmp_path: Path) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="No changes", stderr="")
    chart = tmp_path / "mychart"
    chart.mkdir()
    rc, output = diff_helm_release("my-rel", chart)
    assert rc == 0
    assert output == "No changes"


def test_execute_chaos_experiment_dry_run() -> None:
    result = execute_chaos_experiment("pod-kill", "web-app", dry_run=True)
    assert result.recovered_successfully is True
    assert result.pods_affected == 1


@patch("devops_cli.k8s.chaos.run_subprocess")
def test_execute_chaos_experiment_live(mock_run: MagicMock) -> None:
    # First get pods returns pod/web-app-123, delete returns 0, rollout returns 0
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="pod/web-app-123\n", stderr=""),
        MagicMock(returncode=0, stdout="", stderr=""),
        MagicMock(returncode=0, stdout="deployment successfully rolled out\n", stderr=""),
    ]
    result = execute_chaos_experiment("pod-kill", "web-app", duration_seconds=1)
    assert result.recovered_successfully is True
    assert result.pods_affected == 1


def test_cli_k8s_subcommands_dry_run() -> None:
    res_logs = runner.invoke(app, ["stream-logs", "test-app", "--dry-run"])
    assert res_logs.exit_code == 0

    res_diff = runner.invoke(app, ["diff-helm", "my-release", "--dry-run"])
    assert res_diff.exit_code == 0

    res_chaos = runner.invoke(app, ["chaos", "pod-kill", "--dry-run"])
    assert res_chaos.exit_code == 0

    res_pods = runner.invoke(app, ["pods", "--dry-run", "-n", "kube-system"])
    assert res_pods.exit_code == 0
    assert "list_k8s_pods" in res_pods.output


def test_k8s_pods_table_builder() -> None:
    import datetime

    from devops_cli.commands.k8s.diagnostics import _build_pods_table
    from devops_cli.output import format_timestamp_age

    # Test format_timestamp_age helper
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    assert format_timestamp_age(now_iso) != "—"
    assert format_timestamp_age("invalid-timestamp") == "—"

    mock_pod = MagicMock()
    mock_pod.metadata.namespace = "default"
    mock_pod.metadata.name = "web-123"
    mock_pod.metadata.creation_timestamp = datetime.datetime.now(datetime.UTC)
    mock_pod.status.phase = "Running"
    mock_pod.spec.containers = [MagicMock()]
    mock_status = MagicMock()
    mock_status.ready = True
    mock_status.restart_count = 0
    mock_pod.status.container_statuses = [mock_status]

    mock_v1 = MagicMock()
    mock_v1.list_namespaced_pod.return_value = MagicMock(items=[mock_pod])
    mock_v1.list_pod_for_all_namespaces.return_value = MagicMock(items=[mock_pod])

    with (
        patch("kubernetes.config.load_incluster_config", side_effect=Exception("No cluster")),
        patch("kubernetes.config.load_kube_config"),
        patch("kubernetes.client.CoreV1Api", return_value=mock_v1),
    ):
        table = _build_pods_table("default", label_selector=None, all_namespaces=False)
        assert table.row_count == 1

        table_all = _build_pods_table(None, label_selector="app=web", all_namespaces=True)
        assert table_all.row_count == 1


def test_build_pods_table_masks_credentials_in_exceptions() -> None:
    from devops_cli.commands.k8s.diagnostics import _build_pods_table

    with patch(
        "kubernetes.config.load_kube_config",
        side_effect=RuntimeError("Token secret_token_xyz123 failed"),
    ):
        table = _build_pods_table("default", None, False)
        rendered = str(table.rows)
        assert "secret_token_xyz123" not in rendered
