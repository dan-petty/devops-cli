"""Tests for Kubernetes context management."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from tests.support.config_writes import written_keys
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessFake
from tests.support.k8s_commands import (
    answer_helm_version,
    calls_starting,
    install_kubectl_world,
    minikube_running,
    minikube_starts_on_demand,
    minikube_stopped,
    name_contexts,
    stock_push_keyring,
)
from tests.support.tcp_probe import TcpProbe

pytestmark = pytest.mark.usefixtures("keyring_store")

runner = CliRunner()


def test_k8s_contexts_dry_run() -> None:
    result = runner.invoke(app, ["contexts"], env={"DEVOPS_CLI_DRY_RUN": "true"})
    assert result.exit_code == 0
    assert "devops k8s contexts" in result.output


def test_k8s_switch_context_dry_run() -> None:
    result = runner.invoke(app, ["switch-context", "minikube"], env={"DEVOPS_CLI_DRY_RUN": "true"})
    assert result.exit_code == 0
    assert "use-context" in result.output
    assert "minikube" in result.output


def test_k8s_bootstrap_auto_start_failure(process_fake: ProcessFake) -> None:
    minikube_stopped(process_fake)

    result = runner.invoke(app, ["bootstrap", "--auto-start"])

    assert result.exit_code == 1
    assert "Failed to start minikube" in result.output
    assert calls_starting(process_fake, "minikube", "start") != []


def test_k8s_bootstrap_no_auto_start(process_fake: ProcessFake) -> None:
    minikube_stopped(process_fake)

    result = runner.invoke(app, ["bootstrap", "--no-auto-start"])

    assert result.exit_code == 1
    assert "minikube is not running" in result.output.lower()
    assert calls_starting(process_fake, "minikube", "start") == []


def test_k8s_bootstrap_success(
    tmp_path: Path,
    process_fake: ProcessFake,
    cluster: FakeCluster,
    keyring_store: FakeKeyring,
    tcp_probe: TcpProbe,
) -> None:
    manifest_dir = tmp_path / "k8s"
    manifest_dir.mkdir()
    install_kubectl_world(process_fake)
    stock_push_keyring(keyring_store)
    minikube_running(process_fake)

    result = runner.invoke(app, ["bootstrap", "--dir", str(manifest_dir), "--stack", "infra"])

    assert (
        result.exit_code,
        calls_starting(process_fake, "minikube", "update-context") != [],
        calls_starting(process_fake, "helm", "upgrade") != [],
        calls_starting(process_fake, "minikube", "service") != [],
    ) == (0, True, True, True)


def test_k8s_apply_rejects_ssrf_and_private_metadata_urls() -> None:
    import pytest
    import typer

    from devops_cli.commands.k8s.cluster_context import apply

    with pytest.raises((ValueError, typer.Exit)) as raised:
        apply("http://169.254.169.254/latest/meta-data/")
    assert str(raised.value) != "" or getattr(raised.value, "exit_code", 1) != 0

    with pytest.raises((ValueError, typer.Exit)) as raised:
        apply("http://127.0.0.1:8080/manifest.yaml")
    assert str(raised.value) != "" or getattr(raised.value, "exit_code", 1) != 0


def test_k8s_apply_rejects_path_traversal() -> None:
    import pytest
    import typer

    from devops_cli.commands.k8s.cluster_context import apply

    with pytest.raises((ValueError, typer.Exit)) as raised:
        apply("../../sensitive/secret.yaml")
    assert str(raised.value) != "" or getattr(raised.value, "exit_code", 1) != 0


def _forbid_subprocess(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("dry run started a child process")


def test_k8s_apply_dry_run_previews_and_starts_no_kubectl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`k8s apply --dry-run` renders the preview and starts no kubectl child."""
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("apiVersion: v1\nkind: ConfigMap\n", encoding="utf-8")

    monkeypatch.setattr("subprocess.run", _forbid_subprocess)
    monkeypatch.setattr("subprocess.Popen", _forbid_subprocess)

    result = runner.invoke(app, ["apply", str(manifest), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "devops k8s apply" in result.output
    assert "kubectl apply" in result.output

    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    env_result = runner.invoke(app, ["apply", str(manifest)])
    assert env_result.exit_code == 0, env_result.output
    assert "devops k8s apply" in env_result.output
    assert "kubectl apply" in env_result.output


def test_k8s_apply_template_dry_run_previews_and_starts_no_kubectl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`k8s apply --template --dry-run` renders the preview and starts no kubectl child."""
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "apiVersion: v1\nkind: ConfigMap\ndata:\n  host: example.com\n", encoding="utf-8"
    )

    monkeypatch.setattr("subprocess.run", _forbid_subprocess)
    monkeypatch.setattr("subprocess.Popen", _forbid_subprocess)

    result = runner.invoke(
        app, ["apply", str(manifest), "--template", "--domain", "example.com", "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert "devops k8s apply" in result.output
    assert "kubectl apply" in result.output


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

    monkeypatch.delenv("DEVOPS_CLI_K8S_CONTEXT", raising=False)
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("", encoding="utf-8")
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("k8s:\n  context: default\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))
    minikube_starts_on_demand(process_fake)

    result = runner.invoke(app, ["switch-context", "minikube"])

    assert result.exit_code == 0
    assert calls_starting(process_fake, "minikube", "start") != []
    assert calls_starting(process_fake, "kubectl", "config", "use-context") == [
        ("kubectl", "config", "use-context", "minikube")
    ]


def test_switch_context_minikube_skips_start_when_already_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("k8s:\n  context: default\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))
    minikube_running(process_fake)

    result = runner.invoke(app, ["switch-context", "minikube"])

    assert result.exit_code == 0
    assert calls_starting(process_fake, "minikube", "start") == []
    assert calls_starting(process_fake, "kubectl", "config", "use-context") == [
        ("kubectl", "config", "use-context", "minikube")
    ]


def test_switch_context_other_cluster_does_not_start_minikube(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolate_data_dir: Path,
    process_fake: ProcessFake,
) -> None:
    """The switch writes `k8s.context` alone into the config file."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("k8s:\n  context: default\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))
    minikube_stopped(process_fake)

    result = runner.invoke(app, ["switch-context", "production-cluster"])

    assert result.exit_code == 0
    assert calls_starting(process_fake, "minikube", "start") == []
    assert calls_starting(process_fake, "kubectl", "config", "use-context") == [
        ("kubectl", "config", "use-context", "production-cluster")
    ]
    assert (cfg_file.read_text(encoding="utf-8"), written_keys(isolate_data_dir)) == (
        "k8s:\n  context: production-cluster\n",
        [["k8s.context"]],
    )


def test_resolve_effective_context(
    monkeypatch: pytest.MonkeyPatch, isolate_devops_cli_config: Path
) -> None:
    from devops_cli.commands.k8s.cluster_runtime import resolve_effective_context
    from devops_cli.config.settings import reset_settings_cache

    # 1. Explicit context passed returns that context stripped
    assert resolve_effective_context("  custom-cluster  ") == "custom-cluster"

    # 2. None passed, loads from settings
    monkeypatch.setenv("DEVOPS_CLI_K8S_CONTEXT", "staging-cluster")
    assert resolve_effective_context(None) == "staging-cluster"
    assert resolve_effective_context("") == "staging-cluster"

    # 3. Settings load failure returns None
    monkeypatch.delenv("DEVOPS_CLI_K8S_CONTEXT")
    isolate_devops_cli_config.write_text("k8s: [unclosed", encoding="utf-8")
    reset_settings_cache()
    assert resolve_effective_context(None) is None


def test_should_autostart_minikube_fails_closed_on_config_error(
    monkeypatch: pytest.MonkeyPatch, isolate_devops_cli_config: Path
) -> None:
    from devops_cli.commands.k8s.cluster_runtime import should_autostart_minikube
    from devops_cli.config.settings import reset_settings_cache

    monkeypatch.delenv("DEVOPS_MINIKUBE_AUTOSTART", raising=False)
    monkeypatch.delenv("DEVOPS_K8S_AUTOSTART_MINIKUBE", raising=False)
    isolate_devops_cli_config.write_text("k8s: [unclosed", encoding="utf-8")
    reset_settings_cache()

    assert should_autostart_minikube(target_context=None) is False


def test_switch_context_dry_run_does_not_probe_minikube(process_fake: ProcessFake) -> None:
    result = runner.invoke(app, ["switch-context", "minikube"], env={"DEVOPS_CLI_DRY_RUN": "true"})

    assert (result.exit_code, process_fake.calls) == (0, [])


def test_switch_context_accepts_kubeconfig_names_and_rejects_injection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("k8s:\n  context: default\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))
    minikube_running(process_fake)

    # Valid complex context names: EKS ARN, GKE name with underscores, Kind with dashes, email
    complex_names = [
        "arn:aws:eks:us-east-1:123456789012:cluster/my-cluster",
        "gke_project-123_us-central1_prod-cluster",
        "admin@example.com",
        "kind-local-cluster",
    ]
    for cname in complex_names:
        result = runner.invoke(app, ["switch-context", cname])
        assert result.exit_code == 0
        assert ("kubectl", "config", "use-context", cname) in calls_starting(
            process_fake, "kubectl", "config", "use-context"
        )

    # Invalid context names with injection or empty strings should be rejected
    switched = len(calls_starting(process_fake, "kubectl", "config", "use-context"))
    bad_names = ["bad; rm -rf /", "cluster$(whoami)", "name with spaces", ""]
    for bname in bad_names:
        bad_res = runner.invoke(app, ["switch-context", bname])
        assert bad_res.exit_code != 0
    assert len(calls_starting(process_fake, "kubectl", "config", "use-context")) == switched


def test_sync_configured_k8s_context_warning_on_save_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    from devops_cli.commands.k8s.cluster_context import _sync_configured_k8s_context

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(blocker / "config.yaml"))

    _sync_configured_k8s_context("new-cluster")

    assert "failed to persist" in capfd.readouterr().out


def test_deploy_and_teardown_stack_use_effective_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
    cluster: FakeCluster,
) -> None:
    effective = "arn:aws:eks:us-east-1:123456789012:cluster/prod"
    monkeypatch.setenv("DEVOPS_CLI_K8S_CONTEXT", effective)
    name_contexts(cluster, effective)
    answer_helm_version(process_fake)
    manifest_dir = tmp_path / "k8s"
    manifest_dir.mkdir()

    # When context is None, deploy_stack resolves effective_context from settings
    res_deploy = runner.invoke(
        app,
        ["deploy-stack", "--stack", "logging", "--k8s-dir", str(manifest_dir)]
        + ["--no-wait", "--no-push-secrets"],
    )
    deployed = [call.argv for call in process_fake.calls]
    assert res_deploy.exit_code == 0
    assert any("--context" in argv and effective in argv for argv in deployed)
    assert any("--kube-context" in argv and effective in argv for argv in deployed)

    # Teardown stack also uses effective_context
    process_fake.calls.clear()
    res_teardown = runner.invoke(
        app, ["teardown-stack", "--stack", "logging", "--k8s-dir", str(manifest_dir)]
    )
    assert res_teardown.exit_code == 0
    assert any(
        "--kube-context" in call.argv and effective in call.argv for call in process_fake.calls
    )


def test_sync_configured_k8s_context_masks_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    from devops_cli.commands.k8s.cluster_context import _sync_configured_k8s_context

    secret_token = "ghp_secrettoken1234567890abcdefghijklmn"
    blocker = tmp_path / secret_token
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(blocker / "config.yaml"))

    _sync_configured_k8s_context("new-cluster")

    warning = capfd.readouterr().out
    assert "failed to persist" in warning
    assert secret_token not in warning
    assert "<masked-github-token>" in warning


def test_switch_context_honors_minikube_autostart_disabled(
    monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    monkeypatch.setenv("DEVOPS_MINIKUBE_AUTOSTART", "false")
    minikube_stopped(process_fake)

    res = runner.invoke(app, ["switch-context", "minikube"])

    assert res.exit_code == 0
    assert calls_starting(process_fake, "minikube", "start") == []


def test_k8s_run_cmd_kubeconfig_security(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.commands.k8s.cluster_runtime import _run_cmd
    from devops_cli.exceptions.security import SecurityError

    monkeypatch.setenv("KUBECONFIG", "../../../etc/kubeconfig")
    with pytest.raises(SecurityError) as raised:
        _run_cmd(["kubectl", "version"])
    assert raised.value.error_code == "SECURITY_ERROR"

    monkeypatch.setenv("KUBECONFIG", "/etc/kubernetes/admin.conf")
    with pytest.raises(SecurityError) as raised:
        _run_cmd(["kubectl", "version"])
    assert raised.value.error_code == "SECURITY_ERROR"


def test_switch_context_logs_service_realignment_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    process_fake: ProcessFake,
    cluster: FakeCluster,
) -> None:
    """A failed in-process client realignment is logged, not silently swallowed.

    The kubectl invocation is authoritative for the kubeconfig, so the command still
    succeeds; the diagnostic must survive for troubleshooting. The fake cluster names no
    context `staging`, so it refuses the realignment as a kubeconfig without it does.
    """
    import logging

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("k8s:\n  context: default\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg_file))

    with caplog.at_level(logging.WARNING):
        result = runner.invoke(app, ["switch-context", "staging"])

    assert result.exit_code == 0
    assert "Could not realign in-process Kubernetes client" in caplog.text
