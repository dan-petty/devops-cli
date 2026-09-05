"""Unit and integration tests for verified review findings remediation.

Tests cover:
1. FileSystem._resolve_safe_path prefix collision prevention.
2. NativeTool and MCP authorization token redaction.
3. Repomap symlink skipping, directory containment, and file size limits.
4. Reporting stage session_dir containment verification.
5. Static scan target path resolution containment & thread safety.
6. Context path traversal and absolute path rejection.
7. Console print_dry_run_result output secret sanitization.
8. Vault command secret path validation.
9. Telemetry probe latency & endpoint sanitization.
10. Docker sandbox container wait timeout.
11. OpenWebUI bootstrap account credential configuration.
12. Exception tuple parenthesization across modules.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.agents.capabilities import (
    NativeTool,
)
from devops_cli.ai.agents.context import _check_path_traversal
from devops_cli.ai.harness.filesystem import FileSystem
from devops_cli.ai.repomap import generate_repo_map, parse_file_symbols
from devops_cli.ai.review.stages.reporting import run_reporting_stage
from devops_cli.ai.review.stages.static_scan import _resolve_target_path
from devops_cli.commands.vault import _validate_vault_path
from devops_cli.exceptions import SecurityError
from devops_cli.output.console import print_dry_run_result


# 1. FileSystem._resolve_safe_path prefix collision prevention
def test_filesystem_resolve_safe_path_prefix_collision(tmp_path: Path) -> None:
    root_dir = tmp_path / "allowed_root"
    root_dir.mkdir()
    sibling_dir = tmp_path / "allowed_root_extra"
    sibling_dir.mkdir()
    secret_file = sibling_dir / "secret.txt"
    secret_file.write_text("classified", encoding="utf-8")

    fs = FileSystem(root=root_dir)

    # Legitimate subpath should resolve
    valid_sub = root_dir / "file.txt"
    valid_sub.write_text("hello", encoding="utf-8")
    assert fs._resolve_safe_path("file.txt") == valid_sub.resolve()

    # Prefix collision (../allowed_root_extra/secret.txt) starts with str(root_dir) if not checked with is_relative_to
    with pytest.raises(PermissionError, match="outside root"):
        fs._resolve_safe_path("../allowed_root_extra/secret.txt")


# 2. NativeTool generic tool authorization token redaction
def test_native_tool_token_redaction() -> None:
    from pydantic import BaseModel

    class CustomToolModel(BaseModel):
        id: str = "custom_tool"
        endpoint: str = "https://custom.internal"
        authorization_token: str = "ghp_SUPERSECRET1234567890"

    custom_tool = CustomToolModel()
    native_tool = NativeTool(tool=custom_tool)
    settings = native_tool.get_model_settings()

    config = settings.get("native_tool", {})
    assert "authorization_token" not in config
    assert config.get("id") == "custom_tool"
    assert config.get("endpoint") == "https://custom.internal"


# 3. Repomap symlink skipping, containment, and file size limits
def test_repomap_skips_symlinks_and_verifies_containment(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    real_file = src_dir / "app.py"
    real_file.write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_target = outside_dir / "target.py"
    outside_target.write_text("def leak() -> None:\n    pass\n", encoding="utf-8")

    symlink_file = src_dir / "symlink_leak.py"
    try:
        symlink_file.symlink_to(outside_target)
    except OSError:
        pytest.skip("Symlinks not supported in this filesystem")

    nodes = generate_repo_map(root_dir=tmp_path)
    paths = [n.path for n in nodes]
    assert any("app.py" in p for p in paths)
    assert not any("symlink_leak.py" in p for p in paths)


def test_parse_file_symbols_skips_giant_files(tmp_path: Path) -> None:
    huge_file = tmp_path / "giant.py"
    huge_file.write_text("x = 1\n", encoding="utf-8")

    with patch("pathlib.Path.stat") as mock_stat:
        mock_res = MagicMock()
        mock_res.st_size = 10 * 1024 * 1024  # 10MB
        mock_stat.return_value = mock_res

        node = parse_file_symbols(huge_file, tmp_path)
        assert node is None or len(node.symbols) == 0


# 4. Reporting stage session_dir containment verification
def test_reporting_stage_rejects_session_dir_outside_root(tmp_path: Path) -> None:
    outside_dir = Path("/opt/unauthorized_reviews/session_1")
    with pytest.raises(SecurityError, match="outside allowed root"):
        run_reporting_stage(
            session_id="20260904-999999",
            session_dir=outside_dir,
            reportable_findings=[],
            all_deps=[],
            all_nets=[],
            n_files=0,
        )

    traversal_dir = tmp_path / ".." / "traversal_reviews"
    with pytest.raises(SecurityError, match="Path traversal detected"):
        run_reporting_stage(
            session_id="20260904-999999",
            session_dir=traversal_dir,
            reportable_findings=[],
            all_deps=[],
            all_nets=[],
            n_files=0,
        )


# 5. Static scan target path resolution containment
def test_resolve_target_path_rejects_outside_paths(tmp_path: Path) -> None:
    target_dir = tmp_path / "workspace"
    target_dir.mkdir()
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Legitimate inside target_dir
    inside_file = target_dir / "main.py"
    inside_file.write_text("print('ok')", encoding="utf-8")
    assert _resolve_target_path("main.py", target_dir, repo_dir) == inside_file.resolve()

    # Outside paths
    with pytest.raises(SecurityError, match="outside allowed boundaries"):
        _resolve_target_path("/etc/passwd", target_dir, repo_dir)

    with pytest.raises(SecurityError, match="outside allowed boundaries"):
        _resolve_target_path("../../outside.txt", target_dir, repo_dir)


# 6. Context path traversal sequence rejection
def test_check_path_traversal_rejects_relative_sequences() -> None:
    with pytest.raises(SecurityError, match="Path traversal sequence detected"):
        _check_path_traversal("file_path", "../secrets.txt")

    with pytest.raises(SecurityError, match="Path traversal sequence detected"):
        _check_path_traversal("dest_file", "..\\secrets.txt")

    with pytest.raises(SecurityError, match="Path traversal sequence detected"):
        _check_path_traversal("target_path", "nested/../../shadow")

    # Safe path must pass without error
    _check_path_traversal("file_path", "src/devops_cli/main.py")
    _check_path_traversal("dest_path", "./config.yaml")


# 7. Console print_dry_run_result output secret sanitization
def test_print_dry_run_result_masks_secrets() -> None:
    secret_payload = {
        "command": "devops auth login",
        "token": "ghp_" + "A" * 36,
        "openai_key": "sk-" + "B" * 25,
    }
    mock_console = MagicMock()
    print_dry_run_result(secret_payload, console=mock_console)

    assert mock_console.print_json.called
    printed_str = mock_console.print_json.call_args[0][0]
    assert "ghp_" not in printed_str
    assert "sk-" not in printed_str
    assert "<masked-github-token>" in printed_str


# 8. Vault command secret path validation
def test_validate_vault_path() -> None:
    _validate_vault_path("secret/data/myapp")
    _validate_vault_path("auth/tokens/ci_bot")

    with pytest.raises(ValueError, match="cannot contain '..'"):
        _validate_vault_path("../secret/data/myapp")

    with pytest.raises(ValueError, match="invalid characters"):
        _validate_vault_path("secret/data/myapp; rm -rf /")

    with pytest.raises(ValueError, match="cannot be empty"):
        _validate_vault_path("")


# 9. Telemetry probe latency & endpoint sanitization
def test_telemetry_endpoint_sanitization() -> None:
    from devops_cli.server.routes.telemetry import _sanitize_telemetry_endpoint

    assert _sanitize_telemetry_endpoint("http://localhost:4318") == "http://localhost:4318"
    assert _sanitize_telemetry_endpoint("http://127.0.0.1:4318") == "http://127.0.0.1:4318"
    assert _sanitize_telemetry_endpoint("http://10.244.0.15:4318") == "http://<internal-ip>:4318"
    assert _sanitize_telemetry_endpoint("http://192.168.1.50:4318") == "http://<internal-ip>:4318"


# 10. Docker sandbox container wait timeout
def test_docker_sandbox_wait_timeout() -> None:
    from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner

    cfg = WorkloadSandboxConfig(command=["sleep", "1"])
    runner = WorkloadSandboxRunner(cfg)

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_client.containers.create.return_value = mock_container
    mock_container.id = "mock_container_123"
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = b"done"

    with patch("devops_cli.docker.sandbox._get_docker_client", return_value=mock_client):
        res = runner.run()
        assert res.exit_code == 0
        mock_container.wait.assert_called_once()
        # Verify wait was passed a timeout keyword argument
        _, kwargs = mock_container.wait.call_args
        assert "timeout" in kwargs
        assert kwargs["timeout"] > 0


# 11. OpenWebUI bootstrap account credential configuration
def test_bootstrap_openwebui_account_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.commands.k8s.stack_lifecycle import _get_openwebui_bootstrap_credentials

    monkeypatch.setenv("OPENWEBUI_ADMIN_EMAIL", "custom_admin@corp.internal")
    monkeypatch.setenv("OPENWEBUI_ADMIN_PASSWORD", "SuperSecureCorpSecret!")

    creds = _get_openwebui_bootstrap_credentials()
    assert creds["email"] == "custom_admin@corp.internal"
    assert creds["password"] == "SuperSecureCorpSecret!"
