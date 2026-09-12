"""Tests for Kubernetes context management."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app

runner = CliRunner()


def test_k8s_contexts_dry_run() -> None:
    result = runner.invoke(app, ["contexts"], env={"DEVOPS_CLI_DRY_RUN": "true"})
    assert result.exit_code == 0
    assert "devops k8s contexts" in result.output


def test_k8s_switch_context_dry_run() -> None:
    result = runner.invoke(app, ["switch-context", "minikube"], env={"DEVOPS_CLI_DRY_RUN": "true"})
    assert result.exit_code == 0
    assert "switch_kube_config_context" in result.output
    assert "minikube" in result.output


def test_k8s_bootstrap_auto_start_failure() -> None:
    from unittest.mock import MagicMock, patch

    with (
        patch("devops_cli.commands.k8s._minikube_running", return_value=False),
        patch("shutil.which", return_value=None),
        patch(
            "devops_cli.commands.k8s._run_cmd",
            return_value=MagicMock(returncode=1, stdout="", stderr="error"),
        ),
    ):
        result = runner.invoke(app, ["bootstrap", "--auto-start"])
        assert result.exit_code == 1
        assert "Failed to start minikube" in result.output


def test_k8s_bootstrap_no_auto_start() -> None:
    from unittest.mock import patch

    with patch("devops_cli.commands.k8s._minikube_running", return_value=False):
        result = runner.invoke(app, ["bootstrap", "--no-auto-start"])
        assert result.exit_code == 1
        assert "minikube is not running" in result.output.lower()


def test_k8s_bootstrap_success(tmp_path: Path) -> None:
    from unittest.mock import patch

    manifest_dir = tmp_path / "k8s"
    manifest_dir.mkdir()

    with (
        patch("devops_cli.commands.k8s._minikube_running", return_value=True),
        patch("devops_cli.commands.k8s._run_cmd"),
        patch("devops_cli.commands.k8s.deploy_stack") as mock_deploy,
    ):
        result = runner.invoke(app, ["bootstrap", "--dir", str(manifest_dir), "--stack", "infra"])
        assert result.exit_code == 0
        assert mock_deploy.called


def test_k8s_apply_rejects_ssrf_and_private_metadata_urls() -> None:
    import pytest
    import typer

    from devops_cli.commands.k8s.cluster_context import apply

    with pytest.raises((ValueError, typer.Exit)):
        apply("http://169.254.169.254/latest/meta-data/")

    with pytest.raises((ValueError, typer.Exit)):
        apply("http://127.0.0.1:8080/manifest.yaml")


def test_k8s_apply_rejects_path_traversal() -> None:
    import pytest
    import typer

    from devops_cli.commands.k8s.cluster_context import apply

    with pytest.raises((ValueError, typer.Exit)):
        apply("../../sensitive/secret.yaml")


def test_k8s_config_default_context() -> None:
    from devops_cli.config.settings import Settings

    settings = Settings()
    assert hasattr(settings, "k8s")
    assert settings.k8s.context == "minikube"


def test_k8s_config_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.config.settings import load_settings

    monkeypatch.setenv("DEVOPS_CLI_K8S_CONTEXT", "production-cluster")
    settings = load_settings()
    assert settings.k8s.context == "production-cluster"


def test_k8s_config_get_set_show(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.commands.config import app as config_app

    cfg_file = tmp_path / "config.yaml"
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))

    res_set = runner.invoke(config_app, ["set", "k8s.context", "staging-cluster"])
    assert res_set.exit_code == 0
    assert "staging-cluster" in res_set.output

    res_get = runner.invoke(config_app, ["get", "k8s.context"])
    assert res_get.exit_code == 0
    assert "staging-cluster" in res_get.output

    res_show = runner.invoke(config_app, ["show"])
    assert res_show.exit_code == 0
    assert "k8s.context" in res_show.output
    assert "staging-cluster" in res_show.output


def test_should_autostart_minikube(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.commands.k8s.cluster_runtime import should_autostart_minikube

    monkeypatch.delenv("DEVOPS_MINIKUBE_AUTOSTART", raising=False)
    monkeypatch.delenv("DEVOPS_K8S_AUTOSTART_MINIKUBE", raising=False)

    # Configured context is minikube -> True
    assert should_autostart_minikube(target_context="minikube") is True

    # Configured context is minikube, but disabled via env -> False
    monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "false")
    assert should_autostart_minikube(target_context="minikube") is False

    monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "0")
    assert should_autostart_minikube(target_context="minikube") is False

    # Configured context is a different cluster -> False
    monkeypatch.delenv("DEVOPS_MINIKUBE_AUTOSTART", raising=False)
    assert should_autostart_minikube(target_context="external-cluster") is False

    # Configured context is different cluster, but explicitly enabled via DEVOPS_MINIKUBE_AUTOSTART -> True
    monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "true")
    assert should_autostart_minikube(target_context="external-cluster") is True

    # Configured context is different cluster, but explicitly enabled via DEVOPS_K8S_AUTOSTART_MINIKUBE -> True
    monkeypatch.delenv("DEVOPS_MINIKUBE_AUTOSTART", raising=False)
    monkeypatch.setenv("DEVOPS_K8S_AUTOSTART_MINIKUBE", "1")
    assert should_autostart_minikube(target_context="external-cluster") is True


def test_switch_context_minikube_autostarts_when_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import MagicMock, patch

    cfg_file = tmp_path / "config.yaml"
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))

    calls: list[list[str]] = []

    def mock_run_cmd(cmd: list[str], **kwargs: object) -> object:
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="OK", stderr="")

    def mock_minikube_running() -> bool:
        return any(c[:2] == ["minikube", "start"] for c in calls)

    with (
        patch(
            "devops_cli.commands.k8s.cluster_runtime._minikube_running",
            side_effect=mock_minikube_running,
        ),
        patch(
            "devops_cli.commands.k8s.cluster_context.runtime._minikube_running",
            side_effect=mock_minikube_running,
        ),
        patch("devops_cli.commands.k8s.cluster_context.runtime._run_cmd", side_effect=mock_run_cmd),
        patch("devops_cli.commands.k8s.cluster_runtime._run_cmd", side_effect=mock_run_cmd),
        patch("shutil.which", return_value="/usr/bin/minikube"),
    ):
        result = runner.invoke(app, ["switch-context", "minikube"])
        assert result.exit_code == 0
        # Verify minikube was started
        assert any(c[:2] == ["minikube", "start"] for c in calls)
        assert any(c == ["kubectl", "config", "use-context", "minikube"] for c in calls)


def test_switch_context_minikube_skips_start_when_already_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import MagicMock, patch

    cfg_file = tmp_path / "config.yaml"
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))

    calls: list[list[str]] = []

    def mock_run_cmd(cmd: list[str], **kwargs: object) -> object:
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="OK", stderr="")

    with (
        patch("devops_cli.commands.k8s.cluster_runtime._minikube_running", return_value=True),
        patch(
            "devops_cli.commands.k8s.cluster_context.runtime._minikube_running", return_value=True
        ),
        patch("devops_cli.commands.k8s.cluster_context.runtime._run_cmd", side_effect=mock_run_cmd),
    ):
        result = runner.invoke(app, ["switch-context", "minikube"])
        assert result.exit_code == 0
        # Verify minikube start was NOT called
        assert not any(c[:2] == ["minikube", "start"] for c in calls)
        assert any(c == ["kubectl", "config", "use-context", "minikube"] for c in calls)


def test_switch_context_other_cluster_does_not_start_minikube(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import MagicMock, patch

    cfg_file = tmp_path / "config.yaml"
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))

    calls: list[list[str]] = []

    def mock_run_cmd(cmd: list[str], **kwargs: object) -> object:
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="OK", stderr="")

    with (
        patch("devops_cli.commands.k8s.cluster_runtime._minikube_running", return_value=False),
        patch(
            "devops_cli.commands.k8s.cluster_context.runtime._minikube_running", return_value=False
        ),
        patch("devops_cli.commands.k8s.cluster_context.runtime._run_cmd", side_effect=mock_run_cmd),
    ):
        result = runner.invoke(app, ["switch-context", "production-cluster"])
        assert result.exit_code == 0
        # Verify minikube start was NOT called
        assert not any(c[:2] == ["minikube", "start"] for c in calls)
        assert any(c == ["kubectl", "config", "use-context", "production-cluster"] for c in calls)
