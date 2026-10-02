"""Background daemon process management for Kubernetes port-forwarding."""

from __future__ import annotations

import fcntl
import json
import logging
import os
import signal
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.output.file_writer import write_json_file

logger = logging.getLogger(__name__)

_DEFAULT_STATE_FILE = Path(".data/k8s/port_forwards.json")
_PROC_ROOT = Path("/proc")


def process_start_ticks(pid: int) -> int | None:
    """Return when a process started, in clock ticks after boot (field 22 of /proc/<pid>/stat).

    A pid alone does not name a process: once it exits, the kernel hands the pid to a later
    one. The pid and its start time together do. None when the process does not exist or
    /proc cannot be read.
    """
    try:
        stat = (_PROC_ROOT / str(pid) / "stat").read_bytes()
    except OSError:
        return None
    # The command name (field 2) is parenthesised and may itself hold spaces or ")", so the
    # fields are counted from the last ")". State, field 3, is at index 0 and field 22 at 19.
    return int(stat[stat.rindex(b")") + 2 :].split()[19])


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
    # When the process started, from `process_start_ticks`; None where /proc cannot be read.
    start_ticks: int | None

    @property
    def is_alive(self) -> bool:
        """Check whether the recorded forward is still running.

        Where /proc can be read, the pid must still carry the start time recorded at launch,
        so a pid the kernel has since handed to another process does not count. Elsewhere the
        pid only has to exist.
        """
        if (_PROC_ROOT / "self" / "stat").is_file():
            return self.start_ticks is not None and (
                process_start_ticks(self.pid) == self.start_ticks
            )
        try:
            os.kill(self.pid, 0)
            return True
        except OSError:
            return False


def _running(forwards: list[PortForwardInfo]) -> list[PortForwardInfo]:
    """Keep the forwards whose process is still running, never pid 0 or 1."""
    return [forward for forward in forwards if forward.pid > 1 and forward.is_alive]


def _terminate_process_group(pid: int) -> bool:
    """Signal a forward's whole process group, falling back to the process itself.

    A forward is started in its own session, so `kubectl` is a group leader and anything it
    spawned shares its group. Signalling only the pid left those children running and the
    local port held, which reads as "stopped" in the daemon listing while the port is still
    bound. The fallback covers a forward recorded before sessions were used, whose pid is
    still in this process's own group -- signalling that group would kill the CLI.
    """
    try:
        group = os.getpgid(pid)
    except OSError, ProcessLookupError:
        return False

    if group == os.getpgid(0):
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except (OSError, ProcessLookupError) as exc:
            logger.debug("Process %s already stopped: %s", pid, exc)
            return False

    try:
        os.killpg(group, signal.SIGTERM)
        return True
    except (OSError, ProcessLookupError) as exc:
        logger.debug("Process group %s already stopped: %s", group, exc)
        return False


class PortForwardDaemonManager:
    """Manages the lifecycle and state persistence of background kubectl port-forwards.

    Every change to the state file reads it, changes the list and saves it. Two runs doing
    that at once, such as `port-forward -s infra` beside `-s llm`, would each save over the
    other's records, so each sequence holds `locked()` from its load to its save.
    """

    def __init__(self, state_file: Path | None = None) -> None:
        self.state_file = state_file or _DEFAULT_STATE_FILE

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Hold the exclusive lock on the state file's sibling `.lock` file.

        Not reentrant: the lock belongs to an open file, so taking it again, even within one
        process, waits on itself.
        """
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(
            self.state_file.with_suffix(".lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
        )
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(lock_fd)

    def _read(self) -> list[PortForwardInfo]:
        """Return every recorded forward, running or not."""
        if not self.state_file.is_file() or self.state_file.is_symlink():
            return []

        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            return [PortForwardInfo(**item) for item in raw]
        except Exception as exc:
            logger.debug("Failed reading port-forward state file: %s", exc)
            return []

    def load_forwards(self) -> list[PortForwardInfo]:
        """Return the recorded forwards that are still running. Call it under `locked()`."""
        return _running(self._read())

    def save_forwards(self, forwards: list[PortForwardInfo]) -> None:
        """Replace the state file with a new one in a single step. Call it under `locked()`."""
        if self.state_file.is_symlink():
            logger.warning("Refusing to write port-forward state to symlink: %s", self.state_file)
            return
        write_json_file(self.state_file, forwards, atomic=True)

    def list_forwards(self) -> list[PortForwardInfo]:
        """Return the running forwards, dropping the records of any that have stopped.

        With no state file there is nothing to prune, so a status check creates no directory
        or lock file where it runs.
        """
        if not self.state_file.is_file():
            return []
        with self.locked():
            recorded = self._read()
            running = _running(recorded)
            if len(running) != len(recorded):
                self.save_forwards(running)
            return running

    def stop_forwards(self, service_filter: str | None = None) -> int:
        """Terminate active port-forward processes matching optional service filter."""
        with self.locked():
            stopped_count = 0
            remaining: list[PortForwardInfo] = []

            for f in self.load_forwards():
                if service_filter and service_filter.lower() not in f.service.lower():
                    remaining.append(f)
                    continue

                if _terminate_process_group(f.pid):
                    stopped_count += 1

            self.save_forwards(remaining)
            return stopped_count


_GLOBAL_DAEMON_MANAGER: PortForwardDaemonManager | None = None


def get_daemon_manager() -> PortForwardDaemonManager:
    """Return singleton PortForwardDaemonManager instance."""
    global _GLOBAL_DAEMON_MANAGER
    if _GLOBAL_DAEMON_MANAGER is None:
        _GLOBAL_DAEMON_MANAGER = PortForwardDaemonManager()
    return _GLOBAL_DAEMON_MANAGER
