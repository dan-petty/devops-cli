"""Host port availability and allocation for sandbox port bindings."""

from __future__ import annotations

import socket

import pytest

from devops_cli.exceptions.sandbox import (
    SandboxPortAllocationError,
)
from devops_cli.sandbox.ports import (
    allocate_ports,
    find_available_port,
    is_port_available,
)


def test_port_availability_check() -> None:
    """Test is_port_available helper on free and bound ports."""
    # Binding to a port to simulate in-use port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    bound_port = sock.getsockname()[1]

    try:
        assert not is_port_available(bound_port)
    finally:
        sock.close()

    # Free port should now be available (or another ephemeral port)
    assert is_port_available(bound_port)


def test_find_available_port_with_reserved_ports() -> None:
    """find_available_port respects reserved ports and bounded range."""
    reserved = {10000, 10001, 10002}
    port = find_available_port(reserved_ports=reserved, start=10000, end=10005)
    assert port not in reserved
    assert 10000 <= port <= 10005


def test_find_available_port_exhaustion_raises_error() -> None:
    """find_available_port raises SandboxPortAllocationError when range exhausted."""
    reserved = {10000, 10001}
    with pytest.raises(SandboxPortAllocationError, match="exhausted"):
        find_available_port(reserved_ports=reserved, start=10000, end=10001)


def test_allocate_ports_success() -> None:
    """allocate_ports assigns non-conflicting host ports for container ports."""
    bindings = allocate_ports([80, 443], reserved_ports={10000})
    assert len(bindings) == 2
    assert bindings[0].container_port == 80
    assert bindings[1].container_port == 443
    assert bindings[0].host_port != bindings[1].host_port
    assert bindings[0].host_port != 10000


def test_ports_boundary_check() -> None:
    """is_port_available returns False on out-of-range ports."""
    assert is_port_available(0) is False
    assert is_port_available(70000) is False
