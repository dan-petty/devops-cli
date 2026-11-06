"""Sandbox models: serialization, secret masking, validation rules and deploy config."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.exceptions.sandbox import (
    SandboxError,
)
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    PortBinding,
    SandboxDeployConfig,
    SandboxExecResult,
    SandboxInstance,
    SandboxPolicy,
    SandboxStatus,
)


def test_sandbox_models_serialization(tmp_path: Path) -> None:
    """Test round-trip serialization of SandboxInstance and related models."""
    port_binding = PortBinding(container_port=8080, host_port=18080, protocol="tcp")
    instance = SandboxInstance(
        instance_id="sandbox-test-123456",
        container_id="cont-abc-123",
        name="test-web",
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        port_bindings=[port_binding],
        workspace_dir=str(tmp_path / "workspace"),
        created_at="2026-09-11T20:00:00Z",
        uptime_seconds=120.5,
        metadata={"managed_by": "devops-cli"},
    )

    data = instance.model_dump()
    assert data["instance_id"] == "sandbox-test-123456"
    assert data["status"] == "running"
    assert len(data["port_bindings"]) == 1
    assert data["port_bindings"][0]["host_port"] == 18080

    restored = SandboxInstance.model_validate(data)
    assert restored.instance_id == instance.instance_id
    assert restored.port_bindings[0].container_port == 8080


def test_sandbox_models_secret_masking(tmp_path: Path) -> None:
    """Verify SandboxExecResult, SandboxLogLine, and PanicIncident mask secret tokens."""
    from devops_cli.sandbox.models import (
        PanicIncident,
        PanicType,
        SandboxLogLine,
    )

    raw_secret = "ghp_secrettoken1234567890abcdefghijklmn"
    exec_result = SandboxExecResult(
        instance_id="sb-1",
        command=["echo", "secret"],
        exit_code=0,
        stdout=f"Output with {raw_secret}",
        stderr=f"Error with {raw_secret}",
    )
    assert raw_secret not in exec_result.stdout
    assert "<masked-github-token>" in exec_result.stdout
    assert raw_secret not in exec_result.stderr
    assert "<masked-github-token>" in exec_result.stderr

    log_line = SandboxLogLine(
        content=f"Log containing {raw_secret}",
    )
    assert raw_secret not in log_line.content
    assert "<masked-github-token>" in log_line.content

    panic = PanicIncident(
        incident_id="pi-1",
        instance_id="sb-1",
        container_id="c-1",
        panic_type=PanicType.PYTHON_TRACEBACK,
        message=f"Panic with {raw_secret}",
        stacktrace=[f"File {raw_secret}.py"],
        archived_path=f"{tmp_path}/{raw_secret}.log",
        archive_error=f"Failed with {raw_secret}",
    )
    assert raw_secret not in panic.message
    assert raw_secret not in panic.stacktrace[0]
    assert raw_secret not in (panic.archived_path or "")
    assert raw_secret not in (panic.archive_error or "")


def test_exception_truncation() -> None:
    """Verify bounded string truncation in sandbox exceptions."""
    long_str = "x" * 500
    err = SandboxError("test error", instance_id=long_str, details={"key": long_str})
    assert len(err.details["instance_id"]) <= 256
    assert err.details["instance_id"].endswith("...")
    assert len(err.details["key"]) <= 256


def test_sandbox_models_validation_rules() -> None:
    """Test model validation constraints: network mode, read_only, and port bounds."""

    # Network mode host rejected
    with pytest.raises(ValidationError, match="Network mode 'host' violates sandbox"):
        SandboxDeployConfig(network_mode="host")

    # Network mode bridge and none accepted
    cfg_bridge = SandboxDeployConfig(network_mode="bridge")
    assert cfg_bridge.network_mode == "bridge"
    cfg_none = SandboxDeployConfig(network_mode="none")
    assert cfg_none.network_mode == "none"

    # read_only False rejected
    with pytest.raises(ValidationError, match="read-only root filesystem"):
        SandboxDeployConfig(read_only=False)

    # Invalid port numbers rejected
    with pytest.raises(ValidationError, match="Port must be between 1 and 65535"):
        PortBinding(container_port=0, host_port=8080)
    with pytest.raises(ValidationError, match="Port must be between 1 and 65535"):
        PortBinding(container_port=80, host_port=70000)
    with pytest.raises(ValidationError, match="Container port must be between 1 and 65535"):
        SandboxDeployConfig(ports=[80, 99999])


def test_sandbox_deploy_config_policy_integration() -> None:
    """Verify that SandboxDeployConfig carries policy and generates matching declared security."""
    custom_policy = SandboxPolicy(pids_limit=128, read_only=True)
    cfg = SandboxDeployConfig(policy=custom_policy, read_only=True)

    assert (
        cfg.policy.pids_limit,
        cfg.policy.read_only,
        WorkloadSandboxEngine.declared_controls(cfg)["pids_limit"],
    ) == (128, True, 128)
