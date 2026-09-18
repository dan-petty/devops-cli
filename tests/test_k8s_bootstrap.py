"""Unit tests for Minikube GPU detection, cluster bootstrap, and NodePort reachability fallback.

Validates:
- Automated GPU detection via nvidia-smi with --driver=docker --gpus=all
- Clean fallback to CPU-only mode (--driver=docker)
- Dynamic NodePort socket reachability verification and localhost fallback
- Endpoint persistence for ArgoCD, Grafana, Jaeger, Ollama, Open-WebUI, Qdrant, and Valkey
- Bootstrap command execution and automated configure-urls integration
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.commands.k8s.cluster_runtime import _start_minikube
from devops_cli.commands.k8s.networking import (
    _check_preferred_ports,
    _resolve_accessible_url,
    _resolve_loopback_fallback,
    _verify_url_reachability,
    configure_urls,
)
from devops_cli.config.settings import Settings, ValkeyConfig

runner = CliRunner()


def _mock_completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    """Helper to construct CompletedProcess instances."""
    return subprocess.CompletedProcess(
        args=["mock"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# =============================================================================
# 1. GPU Detection & Minikube Startup Tests
# =============================================================================


@patch("shutil.which", return_value="/usr/bin/nvidia-smi")
@patch("devops_cli.commands.k8s.cluster_runtime._run_cmd")
@patch("devops_cli.commands.k8s.cluster_runtime._minikube_running", return_value=True)
def test_start_minikube_with_gpu(
    mock_running: MagicMock, mock_cmd: MagicMock, mock_which: MagicMock
) -> None:
    """When nvidia-smi is present, start Minikube with --driver=docker --gpus=all."""
    mock_cmd.return_value = _mock_completed(returncode=0)
    success, msg = _start_minikube(dry_run=False)

    assert (success, msg) == (
        True,
        "Started Minikube cluster (--driver=docker --gpus=all)",
    )
    mock_cmd.assert_any_call(["minikube", "start", "--driver=docker", "--gpus=all"], check=False)


@patch("shutil.which", return_value="/usr/bin/nvidia-smi")
@patch("devops_cli.commands.k8s.cluster_runtime._run_cmd")
@patch("devops_cli.commands.k8s.cluster_runtime._minikube_running")
def test_start_minikube_gpu_fallback_to_cpu(
    mock_running: MagicMock, mock_cmd: MagicMock, mock_which: MagicMock
) -> None:
    """When GPU start fails, fall back cleanly to CPU mode (--driver=docker)."""
    mock_cmd.side_effect = [
        _mock_completed(returncode=1, stderr="NVIDIA runtime error"),
        _mock_completed(returncode=0),
        _mock_completed(returncode=0),
    ]
    mock_running.return_value = True

    success, msg = _start_minikube(dry_run=False)

    assert (success, msg) == (True, "Started Minikube cluster (--driver=docker)")
    mock_cmd.assert_any_call(["minikube", "start", "--driver=docker"], check=False)


@patch("shutil.which", return_value=None)
@patch("devops_cli.commands.k8s.cluster_runtime._run_cmd")
@patch("devops_cli.commands.k8s.cluster_runtime._minikube_running", return_value=True)
def test_start_minikube_cpu_only(
    mock_running: MagicMock, mock_cmd: MagicMock, mock_which: MagicMock
) -> None:
    """When nvidia-smi is absent, start Minikube directly with --driver=docker."""
    mock_cmd.return_value = _mock_completed(returncode=0)
    success, msg = _start_minikube(dry_run=False)

    assert (success, msg) == (True, "Started Minikube cluster (--driver=docker)")
    mock_cmd.assert_any_call(["minikube", "start", "--driver=docker"], check=False)


@patch("shutil.which", return_value="/usr/bin/nvidia-smi")
def test_start_minikube_dry_run_with_gpu(mock_which: MagicMock) -> None:
    """Dry run with GPU reports GPU driver options."""
    success, msg = _start_minikube(dry_run=True)
    assert (success, msg) == (
        True,
        "Started Minikube cluster (--driver=docker --gpus=all)",
    )


@patch("shutil.which", return_value=None)
def test_start_minikube_dry_run_without_gpu(mock_which: MagicMock) -> None:
    """Dry run without GPU reports standard docker driver options."""
    success, msg = _start_minikube(dry_run=True)
    assert (success, msg) == (
        True,
        "Started Minikube cluster (--driver=docker)",
    )


@patch("shutil.which", return_value=None)
@patch("devops_cli.commands.k8s.cluster_runtime._run_cmd")
@patch("devops_cli.commands.k8s.cluster_runtime._minikube_running", return_value=False)
def test_start_minikube_total_failure(
    mock_running: MagicMock, mock_cmd: MagicMock, mock_which: MagicMock
) -> None:
    """When startup fails, return False with failure message."""
    mock_cmd.return_value = _mock_completed(returncode=1)
    success, msg = _start_minikube(dry_run=False)
    assert (success, msg) == (False, "Failed to start Minikube cluster")


# =============================================================================
# 2. Bootstrap Command & Lifecycle Tests
# =============================================================================


@patch("devops_cli.commands.k8s.bootstrap.net.configure_urls")
@patch("devops_cli.commands.k8s.bootstrap.stack_life.deploy_stack")
@patch(
    "devops_cli.commands.k8s.bootstrap.runtime._start_minikube",
    return_value=(True, "Started Minikube cluster (--driver=docker --gpus=all)"),
)
@patch("devops_cli.commands.k8s.bootstrap.runtime._minikube_running", return_value=False)
def test_k8s_bootstrap_autostarts_and_configures_urls(
    mock_running: MagicMock,
    mock_start: MagicMock,
    mock_deploy: MagicMock,
    mock_config: MagicMock,
) -> None:
    """k8s bootstrap autostarts minikube, deploys stack, and configures URLs."""
    res = runner.invoke(app, ["bootstrap", "--auto-start", "--stack", "infra"])
    assert res.exit_code == 0
    assert (
        mock_start.called,
        mock_deploy.called,
        mock_config.called,
    ) == (True, True, True)


@patch("devops_cli.commands.k8s.bootstrap.net.configure_urls")
@patch("devops_cli.commands.k8s.bootstrap.stack_life.deploy_stack")
@patch("devops_cli.commands.k8s.bootstrap.runtime._run_cmd")
@patch("devops_cli.commands.k8s.bootstrap.runtime._minikube_running", return_value=True)
def test_k8s_bootstrap_when_already_running(
    mock_running: MagicMock,
    mock_cmd: MagicMock,
    mock_deploy: MagicMock,
    mock_config: MagicMock,
) -> None:
    """k8s bootstrap updates context when already running and configures URLs."""
    res = runner.invoke(app, ["bootstrap", "--stack", "llm"])
    assert res.exit_code == 0
    assert (
        mock_cmd.called,
        mock_deploy.called,
        mock_config.called,
    ) == (True, True, True)


@patch(
    "devops_cli.commands.k8s.bootstrap.runtime._start_minikube",
    return_value=(False, "Failed to start Minikube cluster"),
)
@patch("devops_cli.commands.k8s.bootstrap.runtime._minikube_running", return_value=False)
def test_k8s_bootstrap_fails_when_start_fails(
    mock_running: MagicMock,
    mock_start: MagicMock,
) -> None:
    """k8s bootstrap exits with code 1 when minikube start fails."""
    res = runner.invoke(app, ["bootstrap", "--auto-start"])
    assert res.exit_code == 1


# =============================================================================
# 3. Dynamic NodePort Reachability & Fallback Tests
# =============================================================================


def test_verify_url_reachability_invalid_host() -> None:
    """Invalid host returns False without raising unhandled exception."""
    assert _verify_url_reachability("http://:8080") is False


@patch("socket.create_connection")
def test_verify_url_reachability_success(mock_conn: MagicMock) -> None:
    """Reachable socket returns True."""
    mock_conn.return_value.__enter__.return_value = MagicMock()
    assert _verify_url_reachability("http://example.com:8080") is True


@patch("socket.create_connection", side_effect=OSError("Connection refused"))
def test_verify_url_reachability_failure(mock_conn: MagicMock) -> None:
    """Connection failure returns False cleanly."""
    assert _verify_url_reachability("http://example.com:8080") is False


@patch(
    "devops_cli.commands.k8s.networking._verify_url_reachability",
    side_effect=lambda url: "localhost:8080" in url,
)
def test_check_preferred_ports_reachable(mock_probe: MagicMock) -> None:
    """_check_preferred_ports returns first reachable candidate."""
    res = _check_preferred_ports("http", [9090, 8080, 7070])
    assert res == "http://localhost:8080"


@patch("devops_cli.commands.k8s.networking._verify_url_reachability", return_value=False)
def test_check_preferred_ports_none_reachable(mock_probe: MagicMock) -> None:
    """_check_preferred_ports returns None when no candidate responds."""
    assert _check_preferred_ports("http", [9090, 8080]) is None


@patch(
    "devops_cli.commands.k8s.networking._verify_url_reachability",
    side_effect=lambda url: "127.0.0.1:31434" in url,
)
def test_resolve_loopback_fallback_127_reachable(mock_probe: MagicMock) -> None:
    """_resolve_loopback_fallback returns 127.0.0.1 if localhost probe fails."""
    res = _resolve_loopback_fallback("http", 31434)
    assert res == "http://127.0.0.1:31434"


@patch("devops_cli.commands.k8s.networking._verify_url_reachability", return_value=False)
def test_resolve_loopback_fallback_defaults_to_localhost(mock_probe: MagicMock) -> None:
    """_resolve_loopback_fallback defaults to localhost when neither is yet active."""
    res = _resolve_loopback_fallback("http", 31434)
    assert res == "http://localhost:31434"


@patch("devops_cli.commands.k8s.networking._verify_url_reachability", return_value=True)
def test_resolve_accessible_url_reachable_detected(mock_probe: MagicMock) -> None:
    """When detected URL is reachable, retain original URL directly."""
    res = _resolve_accessible_url("http://example.com:30080")
    assert res == "http://example.com:30080"


@patch(
    "devops_cli.commands.k8s.networking._verify_url_reachability",
    side_effect=lambda url: "localhost:31434" in url,
)
def test_resolve_accessible_url_unreachable_nodeport_fallback(mock_probe: MagicMock) -> None:
    """When internal Minikube IP is unreachable, fall back to localhost:<nodePort>."""
    res = _resolve_accessible_url("http://192.0.2.2:31434")
    assert res == "http://localhost:31434"


@patch(
    "devops_cli.commands.k8s.networking._verify_url_reachability",
    side_effect=lambda url: "localhost:30379" in url,
)
def test_resolve_accessible_url_preserves_tcp_scheme(mock_probe: MagicMock) -> None:
    """Preserve tcp:// scheme for Valkey cache endpoints."""
    res = _resolve_accessible_url("tcp://192.0.2.2:30379")
    assert res == "tcp://localhost:30379"


# =============================================================================
# 4. configure_urls Settings Persistence Tests
# =============================================================================


@patch("devops_cli.commands.k8s.networking.save_settings")
@patch("devops_cli.commands.k8s.networking.load_settings")
@patch("devops_cli.commands.k8s.networking.runtime._cluster_reachable", return_value=True)
@patch("devops_cli.commands.k8s.networking._detect_service_url")
@patch("devops_cli.commands.k8s.networking._resolve_accessible_url")
def test_configure_urls_persists_all_llm_endpoints(
    mock_resolve: MagicMock,
    mock_detect: MagicMock,
    mock_reach: MagicMock,
    mock_load: MagicMock,
    mock_save: MagicMock,
) -> None:
    """configure_urls persists Ollama, Open-WebUI, Qdrant, and Valkey to Settings."""
    settings = Settings()
    mock_load.return_value = settings
    mock_detect.side_effect = lambda svc, ns, context=None: f"http://192.0.2.2:{svc}"
    mock_resolve.side_effect = lambda detected, preferred_localhost_ports=None, **kwargs: (
        "tcp://localhost:6379"
        if "valkey" in str(detected)
        else f"http://localhost:{str(detected).split(':')[-1]}"
    )

    configure_urls(stack="llm")

    assert mock_save.called
    assert (
        settings.ai.ollama_urls,
        settings.open_webui.url,
        settings.qdrant.url,
        settings.valkey.url,
        settings.valkey.port,
    ) == (
        ["http://localhost:ollama"],
        "http://localhost:open-webui",
        "http://localhost:qdrant",
        "tcp://localhost:6379",
        6379,
    )


@patch("devops_cli.commands.k8s.networking.save_settings")
@patch("devops_cli.commands.k8s.networking.load_settings")
@patch("devops_cli.commands.k8s.networking.runtime._cluster_reachable", return_value=True)
@patch("devops_cli.commands.k8s.networking._detect_service_url")
@patch("devops_cli.commands.k8s.networking._resolve_accessible_url")
def test_configure_urls_persists_all_infra_endpoints(
    mock_resolve: MagicMock,
    mock_detect: MagicMock,
    mock_reach: MagicMock,
    mock_load: MagicMock,
    mock_save: MagicMock,
) -> None:
    """configure_urls persists ArgoCD, Grafana, Prometheus, and Jaeger to Settings."""
    settings = Settings()
    mock_load.return_value = settings
    mock_detect.side_effect = lambda svc, ns, context=None: f"http://192.0.2.2:{svc}"
    mock_resolve.side_effect = lambda detected, preferred_localhost_ports=None: (
        f"http://localhost:{str(detected).split(':')[-1]}"
    )

    configure_urls(stack="infra")

    assert mock_save.called
    assert (
        settings.argocd.url,
        settings.grafana.url,
        settings.prometheus.url,
        settings.jaeger.url,
    ) == (
        "http://localhost:argocd-server",
        "http://localhost:kube-prometheus-grafana",
        "http://localhost:kube-prometheus-kube-prome-prometheus",
        "http://localhost:jaeger",
    )


@patch(
    "devops_cli.commands.k8s.networking._verify_url_reachability",
    side_effect=lambda url: "localhost:6379" in url,
)
def test_resolve_accessible_url_none_detected_with_tcp_scheme(mock_probe: MagicMock) -> None:
    """When detected_url is None, default_scheme=tcp probes and returns tcp:// fallback."""
    res = _resolve_accessible_url(None, preferred_localhost_ports=[6379], default_scheme="tcp")
    assert res == "tcp://localhost:6379"


def test_valkey_config_url_normalization_with_userinfo() -> None:
    """Extract password securely from url without leaking credentials into host."""
    cfg = ValkeyConfig.model_validate({"url": "tcp://:super-secret@localhost:6379"})
    assert (cfg.host, cfg.port, cfg.password) == ("localhost:6379", 6379, "super-secret")


def test_valkey_config_url_normalization_ipv6() -> None:
    """Format IPv6 addresses with brackets correctly."""
    cfg = ValkeyConfig.model_validate({"url": "tcp://[::1]:6380"})
    assert (cfg.host, cfg.port) == ("[::1]:6380", 6380)


def test_valkey_config_url_normalization_with_path() -> None:
    """Strip url paths when deriving host and port."""
    cfg = ValkeyConfig.model_validate({"url": "valkey://example.com:6381/0"})
    assert (cfg.host, cfg.port) == ("example.com:6381", 6381)
