"""Background daemon process management for Kubernetes port-forwarding."""

from __future__ import annotations

import json
import logging
import os
import signal
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_DEFAULT_STATE_FILE = Path(".data/k8s/port_forwards.json")


class PortForwardInfo(BaseModel):
    """Metadata tracking a running background port-forward process."""

    pid: int
    service: str
    namespace: str
    local_port: int
    remote_port: int
    address: str = "127.0.0.1"
    stack: str = "infra"
    started_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def is_alive(self) -> bool:
        """Check if process is currently running."""
        try:
            os.kill(self.pid, 0)
            return True
        except OSError, ProcessLookupError:
            return False


class PortForwardDaemonManager:
    """Manages the lifecycle and state persistence of background kubectl port-forwards."""

    def __init__(self, state_file: Path | None = None) -> None:
        self.state_file = state_file or _DEFAULT_STATE_FILE

    def save_forwards(self, forwards: list[PortForwardInfo]) -> None:
        """Persist active forwards list to JSON file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = [f.model_dump(mode="json") for f in forwards]
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list_forwards(self) -> list[PortForwardInfo]:
        """Load and prune list of port forwards, returning only live processes."""
        if not self.state_file.is_file():
            return []

        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            items = [PortForwardInfo(**item) for item in raw]
        except Exception as exc:
            logger.debug("Failed reading port-forward state file: %s", exc)
            return []

        # Keep alive processes
        alive = [it for it in items if it.is_alive]
        if len(alive) != len(items):
            self.save_forwards(alive)
        return alive

    def stop_forwards(self, service_filter: str | None = None) -> int:
        """Terminate active port-forward processes matching optional service filter."""
        forwards = self.list_forwards()
        stopped_count = 0
        remaining: list[PortForwardInfo] = []

        for f in forwards:
            if service_filter and service_filter.lower() not in f.service.lower():
                remaining.append(f)
                continue

            try:
                os.kill(f.pid, signal.SIGTERM)
                stopped_count += 1
            except (OSError, ProcessLookupError) as exc:
                logger.debug("Process %s already stopped: %s", f.pid, exc)

        self.save_forwards(remaining)
        return stopped_count


_GLOBAL_DAEMON_MANAGER: PortForwardDaemonManager | None = None


def get_daemon_manager() -> PortForwardDaemonManager:
    """Return singleton PortForwardDaemonManager instance."""
    global _GLOBAL_DAEMON_MANAGER
    if _GLOBAL_DAEMON_MANAGER is None:
        _GLOBAL_DAEMON_MANAGER = PortForwardDaemonManager()
    return _GLOBAL_DAEMON_MANAGER
