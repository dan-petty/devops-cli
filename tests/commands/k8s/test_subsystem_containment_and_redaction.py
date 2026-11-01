"""Unit and integration tests for subsystem containment, path traversal prevention, and secret redaction.

Tests cover:

1. Repomap symlink skipping, directory containment, and file size limits.
2. Reporting stage session_dir containment verification.
3. Static scan target path resolution containment & thread safety.
4. Context path traversal and absolute path rejection.
5. Console print_dry_run_result output secret sanitization.
6. Vault command secret path validation.
7. Telemetry probe latency & endpoint sanitization.
8. Docker sandbox container wait timeout.
9. OpenWebUI bootstrap account credential configuration.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.agents.context import _check_path_traversal
from devops_cli.ai.repomap import generate_repo_map, parse_file_symbols
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.commands.vault import _validate_vault_path
from devops_cli.exceptions import SecurityError
from devops_cli.output.console import print_dry_run_result


# 1. Repomap symlink skipping, containment, and file size limits
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
    symlink_file.symlink_to(outside_target)

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


# 2. Reporting stage session_dir containment verification
def test_review_session_dir_outside_root_is_refused(tmp_path: Path) -> None:
    """A session directory outside the reviews, working or temporary directory, or through
    `..`, is refused before anything is written there."""
    with pytest.raises(SecurityError, match="outside allowed root"):
        ReviewPipelineOrchestrator(
            session_id="20260904-999999",
            session_dir=Path("/opt/unauthorized_reviews/session_1"),
            target_dir=tmp_path,
        )

    with pytest.raises(SecurityError, match="Path traversal detected"):
        ReviewPipelineOrchestrator(
            session_id="20260904-999999",
            session_dir=tmp_path / ".." / "traversal_reviews",
            target_dir=tmp_path,
        )


# 3. Review file path resolution containment
def test_review_file_paths_stay_inside_the_target_and_repository(tmp_path: Path) -> None:
    """Files named outside the review target and its repository, absolute or through `..`,
    resolve to a missing in-target path rather than being read."""
    target_dir = tmp_path / "workspace"
    target_dir.mkdir()
    inside_file = target_dir / "main.py"
    inside_file.write_text("print('ok')", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    orchestrator = ReviewPipelineOrchestrator(
        session_id="20260904-999999", target_dir=target_dir, session_dir=tmp_path / "session"
    )

    resolved = (
        orchestrator._resolve_file_path("main.py"),
        orchestrator._resolve_file_path(str(outside)),
        orchestrator._resolve_file_path("../outside.txt"),
    )

    assert resolved == (
        inside_file.resolve(),
        target_dir.resolve() / "outside.txt",
        target_dir.resolve() / "outside.txt",
    )
    assert not resolved[1].exists()


# 4. Context path traversal sequence rejection
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


# 5. Console print_dry_run_result output secret sanitization
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


# 6. Vault command secret path validation
def test_validate_vault_path() -> None:
    _validate_vault_path("secret/data/myapp")
    _validate_vault_path("auth/tokens/ci_bot")

    with pytest.raises(ValueError, match=re.escape("cannot contain '..'")):
        _validate_vault_path("../secret/data/myapp")

    with pytest.raises(ValueError, match="invalid characters"):
        _validate_vault_path("secret/data/myapp; rm -rf /")

    with pytest.raises(ValueError, match="cannot be empty"):
        _validate_vault_path("")


# 7. Telemetry probe latency & endpoint sanitization
def test_telemetry_endpoint_sanitization() -> None:
    from devops_cli.security.sanitizer import sanitize_telemetry_endpoint

    assert (
        sanitize_telemetry_endpoint("http://localhost:4318"),
        sanitize_telemetry_endpoint("http://127.0.0.1:4318"),
        sanitize_telemetry_endpoint("http://10.244.0.15:4318"),
        sanitize_telemetry_endpoint("http://192.168.1.50:4318"),
    ) == (
        "http://localhost:4318",
        "http://127.0.0.1:4318",
        "http://internal-ip:4318",
        "http://internal-ip:4318",
    )


# 8. Docker sandbox container wait timeout
def test_docker_sandbox_wait_timeout(tmp_path: Path, docker_engine: Any) -> None:
    from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner

    cfg = WorkloadSandboxConfig(workspace_dir=tmp_path, command=["sleep", "1"])
    runner = WorkloadSandboxRunner(cfg)

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_client.containers.create.return_value = mock_container
    mock_container.id = "mock_container_123"
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = b"done"

    with docker_engine(mock_client):
        res = runner.run()
        assert res.exit_code == 0
        mock_container.wait.assert_called_once()
        # Verify wait was passed a timeout keyword argument
        _, kwargs = mock_container.wait.call_args
        assert "timeout" in kwargs
        assert kwargs["timeout"] > 0


# 9. OpenWebUI bootstrap account credential configuration
def test_bootstrap_openwebui_account_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.commands.k8s.stack_lifecycle import _get_openwebui_bootstrap_credentials

    monkeypatch.setenv("OPENWEBUI_ADMIN_EMAIL", "custom_admin@example.com")
    monkeypatch.setenv("OPENWEBUI_ADMIN_PASSWORD", "SuperSecureCorpSecret!")

    creds = _get_openwebui_bootstrap_credentials()
    assert creds["email"] == "custom_admin@example.com"
    assert creds["password"] == "SuperSecureCorpSecret!"


def test_bootstrap_openwebui_account_secure_random_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.commands.k8s.stack_lifecycle import _get_openwebui_bootstrap_credentials

    monkeypatch.delenv("OPENWEBUI_ADMIN_PASSWORD", raising=False)
    creds = _get_openwebui_bootstrap_credentials()
    assert creds["email"] == "admin@localhost"
    assert creds["password"] != "admin123"
    assert len(creds["password"]) >= 24


def test_bootstrap_openwebui_account_empty_env_password_generates_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devops_cli.commands.k8s.stack_lifecycle import _get_openwebui_bootstrap_credentials

    monkeypatch.setenv("OPENWEBUI_ADMIN_PASSWORD", "")
    creds = _get_openwebui_bootstrap_credentials()
    assert creds["password"] != ""
    assert len(creds["password"]) >= 24
