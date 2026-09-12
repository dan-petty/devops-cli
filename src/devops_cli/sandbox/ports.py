"""Dynamic host port allocation manager for workload sandboxes."""

from __future__ import annotations

import logging
import socket
from typing import Final

from devops_cli.exceptions.sandbox import SandboxPortAllocationError
from devops_cli.sandbox.models import PortBinding

logger = logging.getLogger(__name__)

DEFAULT_SANDBOX_PORT_RANGE_START: Final[int] = 10000
DEFAULT_SANDBOX_PORT_RANGE_END: Final[int] = 60000


def _probe_socket_bind(host: str, port: int) -> bool:
    """Check if a port can be bound on the given host address."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def is_port_available(port: int, hosts: tuple[str, ...] = ("127.0.0.1", "0.0.0.0")) -> bool:
    """Verify that a candidate host port is free for binding across standard interfaces."""
    if not (1 <= port <= 65535):
        return False
    return all(_probe_socket_bind(h, port) for h in hosts)


def find_available_port(
    reserved_ports: set[int] | None = None,
    start: int = DEFAULT_SANDBOX_PORT_RANGE_START,
    end: int = DEFAULT_SANDBOX_PORT_RANGE_END,
) -> int:
    """Find next available host port within range, avoiding reserved ports."""
    reserved = reserved_ports or set()
    for candidate in range(start, end + 1):
        if candidate in reserved:
            continue
        if is_port_available(candidate):
            return candidate

    raise SandboxPortAllocationError(
        f"Dynamic port range [{start}-{end}] exhausted; no available host port found",
        details={"start": start, "end": end, "reserved_count": len(reserved)},
    )


def allocate_ports(
    container_ports: list[int],
    reserved_ports: set[int] | None = None,
    start: int = DEFAULT_SANDBOX_PORT_RANGE_START,
    end: int = DEFAULT_SANDBOX_PORT_RANGE_END,
) -> list[PortBinding]:
    """Allocate non-conflicting host port bindings for requested container ports."""
    reserved = set(reserved_ports) if reserved_ports else set()
    bindings: list[PortBinding] = []

    for c_port in container_ports:
        host_port = find_available_port(reserved_ports=reserved, start=start, end=end)
        reserved.add(host_port)
        bindings.append(PortBinding(container_port=c_port, host_port=host_port, protocol="tcp"))

    return bindings


__all__ = [
    "DEFAULT_SANDBOX_PORT_RANGE_END",
    "DEFAULT_SANDBOX_PORT_RANGE_START",
    "allocate_ports",
    "find_available_port",
    "is_port_available",
]
