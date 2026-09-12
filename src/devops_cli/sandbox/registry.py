"""Persistent JSON instance registry for workload sandbox lifecycles."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from devops_cli.config.defaults import DEFAULT_SANDBOX_INSTANCES_FILE
from devops_cli.exceptions.sandbox import SandboxNotFoundError
from devops_cli.sandbox.models import SandboxInstance, SandboxStatus

logger = logging.getLogger(__name__)


def get_default_sandbox_registry_path() -> Path:
    """Resolve default sandbox registry file path honoring DEVOPS_CLI_DATA_DIR."""
    env_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if env_dir:
        return Path(env_dir) / "sandbox" / "instances.json"
    return DEFAULT_SANDBOX_INSTANCES_FILE


class SandboxRegistry:
    """Thread-safe and process-safe persistent ledger for sandbox container instances."""

    def __init__(self, registry_file: Path | None = None) -> None:
        self.registry_file = registry_file or get_default_sandbox_registry_path()

    def _ensure_directory(self) -> None:
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)

    def list_instances(self) -> list[SandboxInstance]:
        """Read and deserialize all registered sandbox instances."""
        if not self.registry_file.exists():
            return []
        try:
            content = self.registry_file.read_text(encoding="utf-8")
            raw_list = json.loads(content)
            if not isinstance(raw_list, list):
                return []
            return [SandboxInstance.model_validate(item) for item in raw_list]
        except (json.JSONDecodeError, Exception) as exc:
            logger.debug("Failed reading sandbox registry %s: %s", self.registry_file, exc)
            return []

    def _save_instances(self, instances: list[SandboxInstance]) -> None:
        """Atomically persist sandbox instances list to disk."""
        self._ensure_directory()
        serialized = json.dumps(
            [inst.model_dump() for inst in instances],
            indent=2,
            ensure_ascii=False,
        )
        temp_dir = self.registry_file.parent
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tmp:
            tmp.write(serialized)
            tmp_path = Path(tmp.name)
        tmp_path.replace(self.registry_file)

    def get_instance(self, identifier: str) -> SandboxInstance | None:
        """Lookup an instance by unique instance_id or friendly name."""
        instances = self.list_instances()
        for inst in instances:
            if inst.instance_id == identifier or inst.name == identifier:
                return inst
        return None

    def register_instance(self, instance: SandboxInstance) -> None:
        """Add or overwrite an instance record in persistent registry."""
        instances = self.list_instances()
        filtered = [inst for inst in instances if inst.instance_id != instance.instance_id]
        filtered.append(instance)
        self._save_instances(filtered)

    def update_instance_status(
        self,
        instance_id: str,
        status: SandboxStatus,
        uptime_seconds: float | None = None,
    ) -> SandboxInstance:
        """Update runtime status and uptime for an existing sandbox instance."""
        instances = self.list_instances()
        target: SandboxInstance | None = None
        for inst in instances:
            if inst.instance_id == instance_id:
                inst.status = status
                if uptime_seconds is not None:
                    inst.uptime_seconds = uptime_seconds
                target = inst
                break

        if target is None:
            raise SandboxNotFoundError(
                f"Cannot update status; sandbox instance '{instance_id}' not found",
                identifier=instance_id,
            )

        self._save_instances(instances)
        return target

    def remove_instance(self, instance_id: str) -> bool:
        """Delete instance entry from the registry."""
        instances = self.list_instances()
        initial_len = len(instances)
        remaining = [
            inst
            for inst in instances
            if inst.instance_id != instance_id and inst.name != instance_id
        ]
        if len(remaining) == initial_len:
            return False
        self._save_instances(remaining)
        return True

    def get_allocated_host_ports(self) -> set[int]:
        """Collect host ports currently bound by active or pending sandboxes."""
        active_statuses = {SandboxStatus.PENDING, SandboxStatus.RUNNING}
        instances = self.list_instances()
        ports: set[int] = set()
        for inst in instances:
            if inst.status in active_statuses:
                for binding in inst.port_bindings:
                    ports.add(binding.host_port)
        return ports


__all__ = [
    "SandboxRegistry",
    "get_default_sandbox_registry_path",
]
