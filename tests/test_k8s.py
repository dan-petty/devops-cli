"""Unit tests for Kubernetes CLI commands (devops_cli.commands.k8s)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.dry_run import set_dry_run

runner = CliRunner()


def _mock_proc(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["kubectl"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_k8s_contexts_dry_run() -> None:
    """k8s contexts with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["contexts"])
        assert result.exit_code == 0
        assert "devops k8s contexts" in result.output
    finally:
        set_dry_run(False)


def test_k8s_status_dry_run() -> None:
    """k8s status with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "devops k8s status" in result.output
    finally:
        set_dry_run(False)


def test_k8s_bootstrap_dry_run() -> None:
    """k8s bootstrap with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["bootstrap"])
        assert result.exit_code == 0
        assert "devops k8s bootstrap" in result.output
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_dry_run() -> None:
    """k8s deploy-stack with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack"])
        assert result.exit_code == 0
        assert "devops k8s deploy-stack" in result.output
    finally:
        set_dry_run(False)


def test_k8s_teardown_stack_dry_run() -> None:
    """k8s teardown-stack with dry-run active must print dry-run Pydantic model notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["teardown-stack"])
        assert result.exit_code == 0
        assert "devops k8s teardown-stack" in result.output
    finally:
        set_dry_run(False)


@patch("devops_cli.commands.k8s._minikube_running", return_value=False)
def test_k8s_bootstrap_fails_when_minikube_stopped_and_no_auto_start(
    mock_running: MagicMock,
) -> None:
    """k8s bootstrap --no-auto-start must fail when minikube is not running."""
    result = runner.invoke(app, ["bootstrap", "--no-auto-start"])
    assert result.exit_code == 1
    assert "minikube is not running" in result.output


def test_k8s_configure_urls_dry_run() -> None:
    """k8s configure-urls with dry-run active must print dry-run notice."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["configure-urls"])
        assert result.exit_code == 0
        assert "devops k8s configure-urls" in result.output
    finally:
        set_dry_run(False)


@patch("devops_cli.commands.k8s._detect_service_url")
@patch("devops_cli.commands.k8s._cluster_reachable", return_value=True)
@patch("devops_cli.commands.k8s._minikube_running", return_value=True)
def test_k8s_configure_urls_success(
    mock_running: MagicMock,
    mock_cluster: MagicMock,
    mock_detect: MagicMock,
) -> None:
    """k8s configure-urls must query service URLs and update configuration."""

    def fake_detect(service: str, ns: str, context: str | None = None) -> str | None:
        return f"http://192.168.49.2:{30000 + len(service)}"

    set_dry_run(False)
    mock_detect.side_effect = fake_detect
    result = runner.invoke(app, ["configure-urls"])
    assert result.exit_code == 0
    assert "Configured Service Targets" in result.output


@patch("devops_cli.commands.k8s._cluster_reachable", return_value=False)
def test_k8s_deploy_stack_fails_when_cluster_unreachable(
    mock_cluster: MagicMock,
) -> None:
    """k8s deploy-stack must fail gracefully when cluster is unreachable."""
    set_dry_run(False)
    result = runner.invoke(app, ["deploy-stack", "--context", "homelab-k3s"])
    assert result.exit_code == 1
    assert "Kubernetes cluster is not reachable" in result.output


@patch("devops_cli.commands.k8s._verify_url_reachability")
def test_resolve_accessible_url_fallback(mock_verify: MagicMock) -> None:
    """_resolve_accessible_url falls back to localhost when minikube IP is unreachable."""
    from devops_cli.commands.k8s import _resolve_accessible_url

    def fake_verify(url: str, timeout: float = 0.8) -> bool:
        return "localhost" in url

    mock_verify.side_effect = fake_verify
    res = _resolve_accessible_url("http://192.168.49.2:30080")
    assert res == "http://localhost:30080"


def test_k8s_deploy_stack_llm_dry_run() -> None:
    """k8s deploy-stack --stack llm must include Ollama, Open-WebUI, Qdrant, and Valkey."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ollama" in result.output
        assert "open-webui" in result.output
        assert "qdrant" in result.output
        assert "valkey.yaml" in result.output
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_all_dry_run() -> None:
    """k8s deploy-stack --stack all must include both infra and llm components."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "all"])
        assert result.exit_code == 0
        assert "argocd" in result.output
        assert "kube-prometheus" in result.output
        assert "ollama" in result.output
        assert "valkey.yaml" in result.output
    finally:
        set_dry_run(False)


def test_k8s_teardown_stack_llm_dry_run() -> None:
    """k8s teardown-stack --stack llm must include LLM uninstalls and deletions."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["teardown-stack", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ollama" in result.output
        assert "valkey.yaml" in result.output
    finally:
        set_dry_run(False)


def test_k8s_deploy_stack_invalid_stack() -> None:
    """k8s deploy-stack with invalid stack option must exit code 1."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["deploy-stack", "--stack", "unknown-stack"])
        assert result.exit_code == 1
        assert "Invalid stack" in result.output
    finally:
        set_dry_run(False)


def test_k8s_port_forward_llm_dry_run() -> None:
    """k8s port-forward --stack llm must print LLM port forward targets."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["port-forward", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ollama.url" in result.output
        assert "valkey.url" in result.output
    finally:
        set_dry_run(False)


def test_k8s_configure_urls_llm_dry_run() -> None:
    """k8s configure-urls --stack llm must print LLM target URLs."""
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["configure-urls", "--stack", "llm"])
        assert result.exit_code == 0
        assert "ai.ollama_urls" in result.output
        assert "valkey.url" in result.output
    finally:
        set_dry_run(False)


@patch("devops_cli.commands.k8s._run_cmd")
def test_adopt_helm_resource_if_conflict(mock_run: MagicMock) -> None:
    """_adopt_helm_resource_if_conflict annotates and labels pre-existing K8s resources."""
    from devops_cli.commands.k8s import _adopt_helm_resource_if_conflict

    err = (
        'Error: unable to continue with install: Service "ollama" in namespace "llm" exists '
        "and cannot be imported into the current release: invalid ownership metadata; "
        'label validation error: missing key "app.kubernetes.io/managed-by": must be set to "Helm"'
    )
    res = _adopt_helm_resource_if_conflict(err, "ollama", "llm", context="homelab-k3s")
    assert res is True
    assert mock_run.call_count == 2


def test_k8s_apply_and_logs() -> None:
    """Verify k8s apply and logs commands."""
    with patch("devops_cli.commands.k8s._run_cmd") as mock_run:
        result = runner.invoke(app, ["apply", "k8s/infra.yaml", "--namespace", "default"])
        assert result.exit_code == 0
        mock_run.assert_called_once()

    with patch("devops_cli.commands.k8s._run_cmd") as mock_run:
        result = runner.invoke(app, ["logs", "my-pod", "-n", "default", "--tail", "50"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_k8s_contexts_and_switch() -> None:
    """Verify k8s contexts and switch-context commands."""
    mock_config = MagicMock()
    mock_config.list_kube_config_contexts.return_value = (
        [{"name": "minikube", "context": {"cluster": "minikube", "user": "minikube"}}],
        {"name": "minikube"},
    )
    with patch("devops_cli.commands.k8s._k8s_clients", return_value=(mock_config, MagicMock())):
        result = runner.invoke(app, ["contexts"])
        assert result.exit_code == 0
        assert "minikube" in result.output

    with patch("devops_cli.commands.k8s._run_cmd") as mock_run:
        result = runner.invoke(app, ["switch-context", "minikube"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_k8s_status() -> None:
    """Verify k8s status command with cluster nodes and pods."""
    mock_config = MagicMock()
    mock_client = MagicMock()
    core_api = MagicMock()
    node_mock = MagicMock()
    node_mock.metadata.name = "node-1"
    node_mock.metadata.labels = {}
    node_mock.status.conditions = []
    node_mock.status.node_info.kubelet_version = "v1.28.0"
    core_api.list_node.return_value.items = [node_mock]

    pod_mock = MagicMock()
    pod_mock.metadata.name = "pod-1"
    pod_mock.metadata.namespace = "default"
    pod_mock.status.phase = "Running"
    pod_mock.status.container_statuses = []
    core_api.list_pod_for_all_namespaces.return_value.items = [pod_mock]
    mock_client.CoreV1Api.return_value = core_api

    with patch("devops_cli.commands.k8s._k8s_clients", return_value=(mock_config, mock_client)):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "node-1" in result.output


def test_k8s_bootstrap_and_stacks(tmp_path: Path) -> None:
    """Verify k8s bootstrap, deploy-stack, and teardown-stack execution."""
    with (
        patch("devops_cli.commands.k8s.shutil.which", return_value="/usr/local/bin/minikube"),
        patch("devops_cli.commands.k8s._minikube_running", return_value=True),
        patch(
            "devops_cli.commands.k8s.run_subprocess",
            return_value=_mock_proc(0, "minikube is running"),
        ),
        patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "success")),
    ):
        result = runner.invoke(app, ["bootstrap", "--no-auto-start", "--stack", "infra"])
        assert result.exit_code == 0

    with (
        patch("devops_cli.commands.k8s.shutil.which", return_value="/usr/local/bin/helm"),
        patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "success")),
    ):
        result = runner.invoke(app, ["deploy-stack", "--stack", "infra"])
        assert result.exit_code == 0

    with (
        patch("devops_cli.commands.k8s.shutil.which", return_value="/usr/local/bin/helm"),
        patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "success")),
    ):
        result = runner.invoke(app, ["teardown-stack", "--stack", "infra"])
        assert result.exit_code == 0


def test_k8s_tls_secret_and_audit(tmp_path: Path) -> None:
    """Verify create-tls-secret and enable-tls commands."""
    cert_file = tmp_path / "tls.crt"
    key_file = tmp_path / "tls.key"
    cert_file.write_text("cert", encoding="utf-8")
    key_file.write_text("key", encoding="utf-8")

    with patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "success")):
        result = runner.invoke(
            app,
            [
                "create-tls-secret",
                "my-tls-secret",
                "--cert",
                str(cert_file),
                "--key",
                str(key_file),
            ],
        )
        assert result.exit_code == 0

    with patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "success")):
        result = runner.invoke(app, ["enable-tls", "--stack", "all"])
        assert result.exit_code == 0


def test_k8s_security_tools_and_scans(tmp_path: Path) -> None:
    """Verify lint, audit, check-deprecated, and validate commands."""
    from devops_cli.ai.review_schema import Finding

    mock_finding = Finding(
        category="security",
        severity="HIGH",
        location="deployment.yaml:10",
        title="Container running as root",
        fix="Set runAsNonRoot: true",
    )

    with patch("devops_cli.security.kubelinter.run_kubelinter_scan", return_value=[mock_finding]):
        res_lint = runner.invoke(app, ["lint", str(tmp_path)])
        assert res_lint.exit_code == 0

        res_lint_dry = runner.invoke(app, ["lint", str(tmp_path), "--dry-run"])
        assert res_lint_dry.exit_code == 0

    with patch("devops_cli.security.popeye.run_popeye_scan", return_value=[mock_finding]):
        res_audit = runner.invoke(app, ["audit"])
        assert res_audit.exit_code == 0

        res_audit_dry = runner.invoke(app, ["audit", "--dry-run"])
        assert res_audit_dry.exit_code == 0

    with patch("devops_cli.security.pluto.run_pluto_scan", return_value=[mock_finding]):
        res_pluto = runner.invoke(app, ["check-deprecated", str(tmp_path)])
        assert res_pluto.exit_code == 0

        res_pluto_dry = runner.invoke(app, ["check-deprecated", str(tmp_path), "--dry-run"])
        assert res_pluto_dry.exit_code == 0

    with patch(
        "devops_cli.security.kubeconform.run_kubeconform_validation", return_value=[mock_finding]
    ):
        res_val = runner.invoke(app, ["validate", str(tmp_path)])
        assert res_val.exit_code == 0

        res_val_json = runner.invoke(app, ["validate", str(tmp_path), "--json"])
        assert res_val_json.exit_code == 0


def test_k8s_apply_logs_and_urls(tmp_path: Path) -> None:
    """Verify apply, logs, and configure-urls commands."""
    with patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(0, "applied")):
        res_apply = runner.invoke(
            app, ["apply", "deploy.yaml", "--dry-run", "--namespace", "test-ns"]
        )
        assert res_apply.exit_code == 0

        res_apply_real = runner.invoke(app, ["apply", "deploy.yaml", "--namespace", "test-ns"])
        assert res_apply_real.exit_code == 0

    with patch("devops_cli.commands.k8s.run_subprocess", return_value=_mock_proc(0, "logs")):
        res_logs_f = runner.invoke(
            app, ["logs", "my-pod", "-c", "my-container", "-n", "test-ns", "--follow"]
        )
        assert res_logs_f.exit_code == 0

    with (
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch(
            "devops_cli.commands.k8s._detect_service_url", return_value="http://192.168.49.2:30080"
        ),
        patch(
            "devops_cli.commands.k8s._resolve_accessible_url", return_value="http://localhost:8080"
        ),
        patch("devops_cli.config.settings.save_settings"),
    ):
        res_urls = runner.invoke(app, ["configure-urls", "--stack", "infra"])
        assert res_urls.exit_code == 0


def test_k8s_helpers_and_error_branches(tmp_path: Path) -> None:
    """Verify k8s client error branches, URL detection helpers, and rbac-audit."""
    from devops_cli.commands.k8s import (
        _detect_service_url,
        _extract_first_node_ip,
        _parse_minikube_service_url,
        _resolve_k8s_node_port_url,
    )

    # 1. _parse_minikube_service_url
    assert (
        _parse_minikube_service_url("Starting...\nhttp://192.168.49.2:30000\nDone")
        == "http://192.168.49.2:30000"
    )
    assert _parse_minikube_service_url("No URLs here") is None

    # 2. _extract_first_node_ip
    node_data = {
        "status": {
            "addresses": [
                {"type": "InternalIP", "address": "192.168.49.2"},
                {"type": "Hostname", "address": "minikube"},
            ]
        }
    }
    assert _extract_first_node_ip(node_data) == "192.168.49.2"
    assert _extract_first_node_ip({}) is None

    # 3. _resolve_k8s_node_port_url
    import json

    mock_nodes_json = json.dumps({"items": [node_data]})
    with patch(
        "devops_cli.commands.k8s.run_subprocess", return_value=_mock_proc(0, mock_nodes_json)
    ):
        url = _resolve_k8s_node_port_url([], 30080)
        assert url == "http://192.168.49.2:30080"

    # 4. _detect_service_url with fallback
    with patch(
        "devops_cli.commands.k8s.run_subprocess",
        return_value=_mock_proc(0, "http://192.168.49.2:31434"),
    ):
        res_svc = _detect_service_url("ollama", "llm")
        assert res_svc == "http://192.168.49.2:31434"

    # 5. rbac-audit
    res_rbac = runner.invoke(app, ["rbac-audit", "--namespace", "kube-system"])
    assert res_rbac.exit_code == 0
    assert "cluster-admin-binding" in res_rbac.output

    # 6. create-tls-secret missing files
    res_missing_cert = runner.invoke(
        app,
        [
            "create-tls-secret",
            "my-secret",
            "--cert",
            str(tmp_path / "nonexistent.crt"),
            "--key",
            str(tmp_path / "key.pem"),
        ],
    )
    assert res_missing_cert.exit_code == 1

    # 7. contexts failure
    mock_cfg = MagicMock()
    mock_cfg.list_kube_config_contexts.side_effect = Exception("No kubeconfig")
    with patch("devops_cli.commands.k8s._k8s_clients", return_value=(mock_cfg, MagicMock())):
        res_ctx_fail = runner.invoke(app, ["contexts"])
        assert res_ctx_fail.exit_code == 1

    # 8. status failure
    mock_client = MagicMock()
    mock_client.CoreV1Api.side_effect = Exception("Cluster error")
    with patch("devops_cli.commands.k8s._k8s_clients", return_value=(mock_cfg, mock_client)):
        res_stat_fail = runner.invoke(app, ["status"])
        assert res_stat_fail.exit_code == 1

    # 9. port-forward command execution
    with (
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch("subprocess.Popen") as mock_popen,
        patch("time.sleep"),
        patch("devops_cli.commands.k8s.configure_urls"),
    ):
        res_pf = runner.invoke(app, ["port-forward", "--stack", "infra"])
        assert res_pf.exit_code == 0
        assert mock_popen.called


def test_k8s_extended_subcommands(tmp_path: Path) -> None:
    """Verify switch-context, teardown-stack, enable-tls, check-deprecated, lint, audit, and validate."""
    # 1. switch-context
    with patch(
        "devops_cli.commands.k8s.run_subprocess", return_value=_mock_proc(0, "Switched to minikube")
    ):
        res_switch = runner.invoke(app, ["switch-context", "minikube"])
        assert res_switch.exit_code == 0

    # 2. teardown-stack
    with (
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch("devops_cli.commands.k8s.run_subprocess", return_value=_mock_proc(0, "deleted")),
    ):
        res_td = runner.invoke(app, ["teardown-stack", "--stack", "infra"])
        assert res_td.exit_code == 0

    # 3. enable-tls
    tls_cert = tmp_path / "server.crt"
    tls_key = tmp_path / "server.key"
    tls_cert.write_text("CERT", encoding="utf-8")
    tls_key.write_text("KEY", encoding="utf-8")

    with (
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch(
            "devops_cli.commands.k8s.run_subprocess", return_value=_mock_proc(0, "secret created")
        ),
    ):
        res_tls = runner.invoke(
            app,
            [
                "enable-tls",
                "--stack",
                "infra",
                "--tls-dir",
                str(tmp_path),
            ],
        )
        assert res_tls.exit_code == 0

    # 4. lint, audit, check-deprecated, validate
    manifest = tmp_path / "deploy.yaml"
    manifest.write_text("apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8")

    with (
        patch("devops_cli.security.kubelinter.run_kubelinter_scan", return_value=[]),
        patch("devops_cli.security.popeye.run_popeye_scan", return_value=[]),
        patch("devops_cli.security.pluto.run_pluto_scan", return_value=[]),
        patch("devops_cli.security.kubeconform.run_kubeconform_validation", return_value=[]),
    ):
        res_lint = runner.invoke(app, ["lint", str(manifest)])
        assert res_lint.exit_code == 0

        res_audit = runner.invoke(app, ["audit"])
        assert res_audit.exit_code == 0

        res_depr = runner.invoke(app, ["check-deprecated", str(manifest)])
        assert res_depr.exit_code == 0

        res_val = runner.invoke(app, ["validate", str(manifest)])
        assert res_val.exit_code == 0


def test_k8s_service_url_helpers() -> None:
    from devops_cli.commands.k8s import (
        _extract_first_node_ip,
        _parse_minikube_service_url,
        _resolve_accessible_url,
        _resolve_k8s_node_port_url,
        _verify_url_reachability,
    )

    # 1. _parse_minikube_service_url
    assert _parse_minikube_service_url("") is None
    assert (
        _parse_minikube_service_url("Starting tunnel\nhttp://192.168.49.2:30001\nDone")
        == "http://192.168.49.2:30001"
    )

    # 2. _extract_first_node_ip
    node_data_ext = {
        "status": {
            "addresses": [
                {"type": "InternalIP", "address": "192.168.49.2"},
                {"type": "Hostname", "address": "minikube"},
            ]
        }
    }
    assert _extract_first_node_ip(node_data_ext) == "192.168.49.2"
    assert _extract_first_node_ip({}) is None

    # 3. _resolve_k8s_node_port_url
    nodes_json = json.dumps({"items": [node_data_ext]})
    with patch("devops_cli.commands.k8s.run_subprocess", return_value=_mock_proc(0, nodes_json)):
        url = _resolve_k8s_node_port_url([], 30080)
        assert url == "http://192.168.49.2:30080"

    # 4. _verify_url_reachability
    with patch("socket.create_connection", side_effect=OSError):
        assert _verify_url_reachability("http://nonexistent.local:80") is False

    # 5. _resolve_accessible_url
    assert _resolve_accessible_url(None) is None
    with patch("devops_cli.commands.k8s._verify_url_reachability", return_value=True):
        assert (
            _resolve_accessible_url("http://192.168.49.2:3000", preferred_localhost_ports=[3000])
            == "http://localhost:3000"
        )
        assert _resolve_accessible_url("http://192.168.49.2:3000") == "http://192.168.49.2:3000"


def test_k8s_bootstrap_openwebui() -> None:
    """Verify bootstrap-openwebui dry-run, success, and failure paths."""
    # Dry-run
    set_dry_run(True)
    try:
        res_dry = runner.invoke(app, ["bootstrap-openwebui", "--email", "admin@localhost"])
        assert res_dry.exit_code == 0
        assert "bootstrap_openwebui_admin" in res_dry.output
    finally:
        set_dry_run(False)

    # Success execution
    with patch("devops_cli.commands.k8s._run_cmd") as mock_cmd:
        mock_cmd.side_effect = [
            _mock_proc(0, "open-webui-0\n"),
            _mock_proc(0, "BOOTSTRAPPED_ADMIN\n"),
        ]
        res_ok = runner.invoke(
            app,
            [
                "bootstrap-openwebui",
                "--email",
                "admin@localhost",
                "--password",
                "admin123",
                "--context",
                "minikube",
            ],
        )
        assert res_ok.exit_code == 0
        assert "admin@localhost" in res_ok.output

    # Pod not found failure
    with patch("devops_cli.commands.k8s._run_cmd", return_value=_mock_proc(1, "")):
        res_fail = runner.invoke(app, ["bootstrap-openwebui"])
        assert res_fail.exit_code == 1
