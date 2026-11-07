"""Unit tests for Minikube GPU detection, cluster bootstrap, and NodePort reachability fallback.

Validates:
- Automated GPU detection via nvidia-smi with --driver=docker --cni=calico --addons=storage-provisioner-rancher --gpus=all
- Clean fallback to CPU-only mode (--driver=docker --cni=calico --addons=storage-provisioner-rancher)
- Dynamic NodePort socket reachability verification and localhost fallback
- Endpoint persistence for ArgoCD, Grafana, Tempo, Ollama, Open-WebUI, Qdrant, and Valkey
- Bootstrap command execution and automated configure-urls integration
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
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
from devops_cli.config.defaults import DEFAULT_OLLAMA_CLUSTER_SERVICE
from tests.support.config_writes import written_keys
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.kubernetes import FakeCluster, service
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.k8s_commands import (
    calls_starting,
    install_kubectl_world,
    minikube_running,
    minikube_starts_on_demand,
    minikube_stopped,
    stock_push_keyring,
)
from tests.support.tcp_probe import TcpProbe

runner = CliRunner()

_START_FLAGS = ("--driver=docker", "--cni=calico", "--addons=storage-provisioner-rancher")
_START_CPU_ONLY = ("minikube", "start", *_START_FLAGS)
_START_WITH_GPU = ("minikube", "start", *_START_FLAGS, "--gpus=all")


def _nvidia_smi_present(monkeypatch: pytest.MonkeyPatch, present: bool) -> None:
    """Make the lookup of nvidia-smi on PATH find it, or find nothing, as the host decides."""
    monkeypatch.setattr(
        shutil, "which", lambda cmd, *a, **k: f"/usr/bin/{cmd}" if present else None
    )


# =============================================================================
# 1. GPU Detection & Minikube Startup Tests
# =============================================================================


def test_start_minikube_with_gpu(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When nvidia-smi is present, start Minikube with --driver=docker --cni=calico --addons=storage-provisioner-rancher --gpus=all."""
    _nvidia_smi_present(monkeypatch, True)
    minikube_running(process_fake)

    success, msg = _start_minikube(dry_run=False)

    assert (success, msg) == (
        True,
        "Started Minikube cluster (--driver=docker --cni=calico --addons=storage-provisioner-rancher --gpus=all)",
    )
    assert calls_starting(process_fake, "minikube", "start") == [_START_WITH_GPU]


def test_start_minikube_gpu_fallback_to_cpu(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When GPU start fails, fall back cleanly to CPU mode (--driver=docker --cni=calico --addons=storage-provisioner-rancher)."""
    _nvidia_smi_present(monkeypatch, True)
    minikube_running(process_fake)
    process_fake.answer(
        lambda call: call.argv == _START_WITH_GPU,
        ProcessAnswer(returncode=1, stderr="NVIDIA runtime error"),
    )

    success, msg = _start_minikube(dry_run=False)

    assert (success, msg) == (
        True,
        "Started Minikube cluster (--driver=docker --cni=calico --addons=storage-provisioner-rancher)",
    )
    assert calls_starting(process_fake, "minikube", "start") == [_START_WITH_GPU, _START_CPU_ONLY]


def test_start_minikube_cpu_only(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When nvidia-smi is absent, start Minikube directly with --driver=docker --cni=calico --addons=storage-provisioner-rancher."""
    _nvidia_smi_present(monkeypatch, False)
    minikube_running(process_fake)

    success, msg = _start_minikube(dry_run=False)

    assert (success, msg) == (
        True,
        "Started Minikube cluster (--driver=docker --cni=calico --addons=storage-provisioner-rancher)",
    )
    assert calls_starting(process_fake, "minikube", "start") == [_START_CPU_ONLY]


def test_start_minikube_dry_run_with_gpu(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dry run with GPU reports GPU driver options."""
    _nvidia_smi_present(monkeypatch, True)

    success, msg = _start_minikube(dry_run=True)

    assert (success, msg, process_fake.calls) == (
        True,
        "Started Minikube cluster (--driver=docker --cni=calico --addons=storage-provisioner-rancher --gpus=all)",
        [],
    )


def test_start_minikube_dry_run_without_gpu(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dry run without GPU reports standard docker driver options."""
    _nvidia_smi_present(monkeypatch, False)

    success, msg = _start_minikube(dry_run=True)

    assert (success, msg, process_fake.calls) == (
        True,
        "Started Minikube cluster (--driver=docker --cni=calico --addons=storage-provisioner-rancher)",
        [],
    )


def test_start_minikube_total_failure(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When startup fails, return False with failure message."""
    _nvidia_smi_present(monkeypatch, False)
    minikube_stopped(process_fake)
    process_fake.answer("minikube start", ProcessAnswer(returncode=1))

    success, msg = _start_minikube(dry_run=False)

    assert (success, msg) == (False, "Failed to start Minikube cluster")


def test_start_minikube_pins_calico_cni_argv_and_help_text_matches(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Offline test pins minikube start argv to include --cni=calico and help text documents Calico."""
    from devops_cli.commands.k8s import app
    from devops_cli.lang import HELP

    # Verify HELP.k8s.bootstrap documents Calico
    assert "Calico" in HELP.k8s.bootstrap

    # Verify devops k8s bootstrap command help documents Calico
    help_res = runner.invoke(app, ["bootstrap", "--help"])
    assert help_res.exit_code == 0
    assert "Calico" in help_res.output

    # Verify minikube start argv contains --cni=calico
    _nvidia_smi_present(monkeypatch, False)
    minikube_running(process_fake)
    success, msg = _start_minikube(dry_run=False)
    assert success is True
    assert "--cni=calico" in msg
    assert calls_starting(process_fake, "minikube", "start") == [_START_CPU_ONLY]


def test_minikube_start_hints_name_the_local_path_addon() -> None:
    """The hints that tell a person to start Minikube by hand name the local-path addon."""
    from devops_cli.lang import MESSAGES

    assert "--addons=storage-provisioner-rancher" in MESSAGES.k8s.start_minikube_tip
    assert "--addons=storage-provisioner-rancher" in MESSAGES.k8s.minikube_not_running


# =============================================================================
# 2. Bootstrap Command & Lifecycle Tests
# =============================================================================


def test_k8s_bootstrap_autostarts_and_configures_urls(
    process_fake: ProcessFake,
    cluster: FakeCluster,
    keyring_store: FakeKeyring,
    tcp_probe: TcpProbe,
) -> None:
    """k8s bootstrap autostarts minikube, deploys stack, and configures URLs."""
    install_kubectl_world(process_fake)
    stock_push_keyring(keyring_store)
    minikube_starts_on_demand(process_fake)

    res = runner.invoke(app, ["bootstrap", "--auto-start", "--stack", "infra"])

    assert res.exit_code == 0
    assert (
        calls_starting(process_fake, "minikube", "start") != [],
        calls_starting(process_fake, "helm", "upgrade") != [],
        calls_starting(process_fake, "minikube", "service") != [],
    ) == (True, True, True)


def test_k8s_bootstrap_when_already_running(
    process_fake: ProcessFake,
    cluster: FakeCluster,
    keyring_store: FakeKeyring,
    tcp_probe: TcpProbe,
) -> None:
    """k8s bootstrap updates context when already running and configures URLs."""
    install_kubectl_world(process_fake)
    stock_push_keyring(keyring_store)
    minikube_running(process_fake)

    res = runner.invoke(app, ["bootstrap", "--stack", "llm"])

    assert res.exit_code == 0
    assert (
        calls_starting(process_fake, "minikube", "update-context") != [],
        calls_starting(process_fake, "helm", "upgrade") != [],
        calls_starting(process_fake, "minikube", "service") != [],
    ) == (True, True, True)


def test_k8s_bootstrap_fails_when_start_fails(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """k8s bootstrap exits with code 1 when minikube start fails."""
    _nvidia_smi_present(monkeypatch, False)
    minikube_stopped(process_fake)
    process_fake.answer("minikube start", ProcessAnswer(returncode=1))

    res = runner.invoke(app, ["bootstrap", "--auto-start"])

    assert res.exit_code == 1
    assert calls_starting(process_fake, "helm") == []


# =============================================================================
# 3. Dynamic NodePort Reachability & Fallback Tests
# =============================================================================


def test_verify_url_reachability_invalid_host() -> None:
    """Invalid host returns False without raising unhandled exception."""
    assert _verify_url_reachability("http://:8080") is False


def test_verify_url_reachability_success(tcp_probe: TcpProbe) -> None:
    """Reachable socket returns True."""
    tcp_probe.listen("example.com", 8080)

    assert _verify_url_reachability("http://example.com:8080") is True


def test_verify_url_reachability_failure(tcp_probe: TcpProbe) -> None:
    """Connection failure returns False cleanly."""
    assert _verify_url_reachability("http://example.com:8080") is False
    assert tcp_probe.probed == [("example.com", 8080)]


def test_check_preferred_ports_reachable(tcp_probe: TcpProbe) -> None:
    """_check_preferred_ports returns first reachable candidate."""
    tcp_probe.listen("localhost", 8080)

    res = _check_preferred_ports("http", [9090, 8080, 7070])

    assert res == "http://localhost:8080"


def test_check_preferred_ports_none_reachable(tcp_probe: TcpProbe) -> None:
    """_check_preferred_ports returns None when no candidate responds."""
    assert _check_preferred_ports("http", [9090, 8080]) is None


def test_resolve_loopback_fallback_127_reachable(tcp_probe: TcpProbe) -> None:
    """_resolve_loopback_fallback returns 127.0.0.1 if localhost probe fails."""
    tcp_probe.listen("127.0.0.1", 31434)

    res = _resolve_loopback_fallback("http", 31434)

    assert res == "http://127.0.0.1:31434"


def test_resolve_loopback_fallback_defaults_to_localhost(tcp_probe: TcpProbe) -> None:
    """_resolve_loopback_fallback defaults to localhost when neither is yet active."""
    res = _resolve_loopback_fallback("http", 31434)

    assert res == "http://localhost:31434"


def test_resolve_accessible_url_reachable_detected(tcp_probe: TcpProbe) -> None:
    """When detected URL is reachable, retain original URL directly."""
    tcp_probe.listen("example.com", 30080)

    res = _resolve_accessible_url("http://example.com:30080")

    assert res == "http://example.com:30080"


def test_resolve_accessible_url_unreachable_nodeport_fallback(tcp_probe: TcpProbe) -> None:
    """When internal Minikube IP is unreachable, fall back to localhost:<nodePort>."""
    tcp_probe.listen("localhost", 31434)

    res = _resolve_accessible_url("http://192.0.2.2:31434")

    assert res == "http://localhost:31434"


def test_resolve_accessible_url_preserves_the_valkey_scheme(tcp_probe: TcpProbe) -> None:
    """Preserve the valkey:// scheme for Valkey cache endpoints."""
    tcp_probe.listen("localhost", 30379)

    res = _resolve_accessible_url("valkey://192.0.2.2:30379")

    assert res == "valkey://localhost:30379"


# =============================================================================
# 4. configure_urls Settings Persistence Tests
# =============================================================================


def test_configure_urls_persists_all_llm_endpoints(
    cluster: FakeCluster,
    process_fake: ProcessFake,
    tcp_probe: TcpProbe,
    config: Callable[..., Path],
    isolate_devops_cli_config: Path,
) -> None:
    """configure_urls persists Ollama, Open-WebUI, Qdrant, and Valkey to Settings."""
    config(valkey={"url": None})
    ports = {
        DEFAULT_OLLAMA_CLUSTER_SERVICE: 11434,
        "open-webui": 8080,
        "qdrant": 6333,
        "valkey": 6379,
    }
    cluster.core.answers["list_namespaced_service"] = [
        service(name, "llm", port=port, load_balancer="192.0.2.2") for name, port in ports.items()
    ]

    configure_urls(stack="llm")

    saved = yaml.safe_load(isolate_devops_cli_config.read_text(encoding="utf-8"))
    assert (
        saved["ai"]["ollama_urls"],
        saved["open_webui"]["url"],
        saved["qdrant"]["url"],
        saved["valkey"]["url"],
    ) == (
        ["http://localhost:11434"],
        "http://localhost:8080",
        "http://localhost:6333",
        "valkey://localhost:6379",
    )


def test_configure_urls_persists_all_infra_endpoints(
    cluster: FakeCluster,
    process_fake: ProcessFake,
    tcp_probe: TcpProbe,
    isolate_devops_cli_config: Path,
    isolate_data_dir: Path,
) -> None:
    """configure_urls writes the ArgoCD, Grafana, Prometheus, Pyroscope, Tempo and OTLP URLs that it
    detects into the config file, and no other key."""
    services = [
        ("argocd-server", "argocd", 8080),
        ("grafana", "monitoring", 3000),
        ("prometheus-server", "monitoring", 9090),
        ("tempo", "otel", 3201),
        ("pyroscope", "monitoring", 4041),
    ]
    cluster.core.answers["list_namespaced_service"] = [
        service(name, namespace, port=port, load_balancer="192.0.2.2")
        for name, namespace, port in services
    ]

    configure_urls(stack="infra")

    saved = yaml.safe_load(isolate_devops_cli_config.read_text(encoding="utf-8"))
    assert (
        saved["argocd"]["url"],
        saved["grafana"]["url"],
        saved["prometheus"]["url"],
        saved["tempo"]["url"],
        written_keys(isolate_data_dir),
    ) == (
        "http://localhost:8080",
        "http://localhost:3000",
        "http://localhost:9090",
        "http://localhost:3201",
        [
            [
                "argocd.url",
                "grafana.url",
                "prometheus.url",
                "pyroscope.url",
                "telemetry.endpoint",
                "tempo.url",
            ]
        ],
    )


def test_resolve_accessible_url_none_detected_with_the_valkey_scheme(
    tcp_probe: TcpProbe,
) -> None:
    """When detected_url is None, default_scheme=valkey probes and returns a valkey:// fallback."""
    tcp_probe.listen("localhost", 6379)

    res = _resolve_accessible_url(None, preferred_localhost_ports=[6379], default_scheme="valkey")

    assert res == "valkey://localhost:6379"
