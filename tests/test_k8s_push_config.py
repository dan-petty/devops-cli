"""Tests for `devops k8s push-config` and stack deployment ConfigMap synchronization."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from devops_cli.commands.k8s.cluster_config_push import push_config
from devops_cli.commands.k8s.stack_lifecycle import deploy_stack

runner = CliRunner()
_app = typer.Typer()
_app.command("push-config")(push_config)
_app.command("deploy-stack")(deploy_stack)


def test_push_config_dry_run(tmp_path: Path) -> None:
    """Verify push-config --dry-run prints dry run plan and makes no cluster changes."""
    k8s_dir = tmp_path / "k8s"
    devops_dir = k8s_dir / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: devops-cli-config\n"
        "  namespace: devops\ndata:\n  devops-cli.yaml: |\n    service:\n"
        "      repos:\n        - owner/repo\n      machine_account: devops-bot\n",
        encoding="utf-8",
    )

    result = runner.invoke(_app, ["push-config", "--k8s-dir", str(k8s_dir), "--dry-run"])

    assert (
        result.exit_code,
        "devops k8s push-config" in result.output,
        "apply_configmap" in result.output,
    ) == (0, True, True)


def test_push_config_unreachable_cluster(tmp_path: Path) -> None:
    """Verify push-config exits with code 1 when target cluster is unreachable."""
    k8s_dir = tmp_path / "k8s"
    devops_dir = k8s_dir / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.yaml").write_text("apiVersion: v1\n", encoding="utf-8")

    with patch("devops_cli.commands.k8s.cluster_runtime._cluster_reachable", return_value=False):
        result = runner.invoke(_app, ["push-config", "--k8s-dir", str(k8s_dir)])

        assert (
            result.exit_code,
            "Kubernetes cluster is not reachable" in result.output,
        ) == (1, True)


def test_push_config_success_with_restart(tmp_path: Path) -> None:
    """Verify push-config applies ConfigMap and triggers rollout restart."""
    with (
        patch("devops_cli.commands.k8s.cluster_runtime._cluster_reachable", return_value=True),
        patch(
            "devops_cli.commands.k8s.cluster_config_push.push_devops_configmap",
            return_value="configmap/devops-cli-config configured",
        ) as mock_push,
        patch(
            "devops_cli.commands.k8s.cluster_runtime._run_cmd",
            return_value=MagicMock(returncode=0, stdout="", stderr=""),
        ) as mock_run,
    ):
        result = runner.invoke(
            _app,
            ["push-config", "--k8s-dir", str(tmp_path), "--context", "homelab-ctx"],
        )

        assert (
            result.exit_code,
            mock_push.call_count,
            mock_push.call_args[1]["context"],
            mock_run.call_count,
            mock_run.call_args[0][0],
            "ConfigMap updated: configmap/devops-cli-config configured" in result.output,
            "Restarted deployment/roadmap-service" in result.output,
        ) == (
            0,
            1,
            "homelab-ctx",
            1,
            [
                "kubectl",
                "rollout",
                "restart",
                "deployment/roadmap-service",
                "-n",
                "devops",
                "--context",
                "homelab-ctx",
            ],
            True,
            True,
        )


def test_push_config_no_restart(tmp_path: Path) -> None:
    """Verify push-config --no-restart skips deployment rollout restart."""
    with (
        patch("devops_cli.commands.k8s.cluster_runtime._cluster_reachable", return_value=True),
        patch(
            "devops_cli.commands.k8s.cluster_config_push.push_devops_configmap",
            return_value="configmap/devops-cli-config unchanged",
        ) as mock_push,
        patch("devops_cli.commands.k8s.cluster_runtime._run_cmd") as mock_run,
    ):
        result = runner.invoke(
            _app,
            ["push-config", "--k8s-dir", str(tmp_path), "--no-restart"],
        )

        assert (
            result.exit_code,
            mock_push.call_count,
            mock_run.call_count,
            "ConfigMap updated: configmap/devops-cli-config unchanged" in result.output,
        ) == (0, 1, 0, True)


def test_push_config_restart_failure_logs_warning(tmp_path: Path) -> None:
    """Verify push-config logs warning when rollout restart returns non-zero."""
    with (
        patch("devops_cli.commands.k8s.cluster_runtime._cluster_reachable", return_value=True),
        patch(
            "devops_cli.commands.k8s.cluster_config_push.push_devops_configmap",
            return_value="configmap/devops-cli-config configured",
        ),
        patch(
            "devops_cli.commands.k8s.cluster_runtime._run_cmd",
            return_value=MagicMock(returncode=1, stdout="", stderr="deployment not found"),
        ),
    ):
        result = runner.invoke(_app, ["push-config", "--k8s-dir", str(tmp_path)])

        assert (
            result.exit_code,
            "Failed to restart deployment/roadmap-service: deployment not found" in result.output,
        ) == (0, True)


def test_deploy_stack_argo_managed_pushes_devops_configmap(tmp_path: Path) -> None:
    """Verify deploy-stack pushes devops-cli-config ConfigMap in Argo-managed clusters."""
    with (
        patch("devops_cli.commands.k8s.stack_lifecycle.require_keyring_for_push"),
        patch("devops_cli.commands.k8s.stack_lifecycle._verify_cluster_ready"),
        patch(
            "devops_cli.commands.k8s.stack_lifecycle._is_cluster_argo_managed", return_value=True
        ),
        patch("devops_cli.commands.k8s.stack_lifecycle.push_for_stacks"),
        patch(
            "devops_cli.k8s.configmap.push_devops_configmap",
            return_value="configmap/devops-cli-config configured",
        ) as mock_push_cfg,
    ):
        result = runner.invoke(
            _app,
            ["deploy-stack", "--stack", "devops", "--k8s-dir", str(tmp_path), "--no-push-secrets"],
        )

        assert (
            result.exit_code,
            mock_push_cfg.call_count,
            "Pushing devops-cli-config ConfigMap..." in result.output,
            "Argo CD manages the cluster" in result.output,
        ) == (0, 1, True, True)
