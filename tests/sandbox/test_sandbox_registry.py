"""The persistent sandbox registry: records, ports held, and a corrupt file."""

from __future__ import annotations

from pathlib import Path

from devops_cli.sandbox.models import (
    PortBinding,
    SandboxInstance,
    SandboxStatus,
)
from devops_cli.sandbox.registry import SandboxRegistry


def test_sandbox_registry_crud(tmp_path: Path) -> None:
    """Test registry CRUD operations and persistence across instances."""
    registry_file = tmp_path / "sandbox" / "instances.json"
    reg = SandboxRegistry(registry_file=registry_file)

    assert reg.list_instances() == []
    assert reg.get_allocated_host_ports() == set()

    inst = SandboxInstance(
        instance_id="sb-test-1",
        container_id="cid-1",
        name="svc-1",
        image="alpine:latest",
        status=SandboxStatus.RUNNING,
        port_bindings=[PortBinding(container_port=80, host_port=10080)],
        workspace_dir=str(tmp_path),
        created_at="2026-09-11T20:00:00Z",
    )

    reg.register_instance(inst)
    assert registry_file.exists()

    loaded = reg.get_instance("sb-test-1")
    assert loaded is not None
    assert loaded.name == "svc-1"
    assert reg.get_allocated_host_ports() == {10080}

    # Query by name
    by_name = reg.get_instance("svc-1")
    assert by_name is not None
    assert by_name.instance_id == "sb-test-1"

    # Update status
    updated = reg.update_instance_status("sb-test-1", SandboxStatus.STOPPED, uptime_seconds=42.0)
    assert updated.status == SandboxStatus.STOPPED
    assert updated.uptime_seconds == 42.0
    # Stopped instances do not reserve host ports
    assert reg.get_allocated_host_ports() == set()

    # Remove
    assert reg.remove_instance("sb-test-1") is True
    assert reg.get_instance("sb-test-1") is None
    assert reg.remove_instance("sb-test-1") is False


def test_sandbox_registry_corrupted_file_handling(tmp_path: Path) -> None:
    """Registry safely handles corrupted JSON files by returning empty list."""
    registry_file = tmp_path / "corrupted.json"
    registry_file.write_text("invalid json content! { [", encoding="utf-8")
    reg = SandboxRegistry(registry_file=registry_file)
    assert reg.list_instances() == []


def test_registry_reserve_and_register_pending(tmp_path: Path) -> None:
    """Registry reserve_and_register_pending atomically assigns ports and saves pending instance."""
    reg = SandboxRegistry(tmp_path / "reg.json")
    inst1, bindings1 = reg.reserve_and_register_pending(
        instance_id="sb-1",
        name="test-1",
        image="alpine",
        workspace_dir=str(tmp_path),
        requested_ports=[8080],
        now_str="2026-09-12T06:00:00Z",
    )
    assert inst1.status == SandboxStatus.PENDING
    assert len(bindings1) == 1
    port1 = bindings1[0].host_port

    # Second allocation must atomically recognize port1 as reserved
    _inst2, bindings2 = reg.reserve_and_register_pending(
        instance_id="sb-2",
        name="test-2",
        image="alpine",
        workspace_dir=str(tmp_path),
        requested_ports=[8080],
        now_str="2026-09-12T06:00:00Z",
    )
    port2 = bindings2[0].host_port
    assert port1 != port2
    assert reg.get_allocated_host_ports() == {port1, port2}


def test_registry_corrupt_file_quarantine(tmp_path: Path) -> None:
    """Corrupt registry file is quarantined to .corrupt-* without clobbering."""
    reg_file = tmp_path / "instances.json"
    reg_file.write_text("{ corrupt invalid json content", encoding="utf-8")

    reg = SandboxRegistry(reg_file)
    # list_instances returns empty list and creates quarantine file
    instances = reg.list_instances()
    assert instances == []

    quarantine_files = list(tmp_path.glob("instances.json.corrupt-*"))
    assert len(quarantine_files) == 1
    assert "{ corrupt" in quarantine_files[0].read_text(encoding="utf-8")
