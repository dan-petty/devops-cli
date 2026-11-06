"""Tests for the connection lifecycle and the response cache of `DockerEngineService`.

The service runs over `docker_daemon`, the in-memory engine of
`tests/support/fakes/docker_engine.py` (#1316). Time is `ClockFake`, so a cache lifetime ends
when a test moves the clock.
"""

from __future__ import annotations

from devops_cli.config.defaults import DEFAULT_DOCKER_CACHE_TTL_SECONDS
from devops_cli.docker.engine import (
    DockerEngineService,
    get_engine,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.docker_engine import DockerEngineFake


def test_close_releases_socket_and_clears_cache(docker_daemon: DockerEngineFake) -> None:
    """Closing the service closes the client and drops memoised responses, so the next call
    builds a new client and reads the engine again."""
    engine = get_engine()
    engine.build_cache()
    engine.close()
    closed = docker_daemon.closed
    engine.build_cache()

    assert (closed, docker_daemon.call_names().count("df"), len(docker_daemon.factory_params)) == (
        True,
        2,
        2,
    )


def test_singleton_instance_reuse_and_reset() -> None:
    """The engine singleton is shared process-wide and resettable for test isolation."""
    DockerEngineService.reset_instance()
    first = get_engine()
    shared = first is get_engine()
    DockerEngineService.reset_instance()

    assert (shared, get_engine() is first) == (True, False)


def test_ping_caches_reachability(docker_daemon: DockerEngineFake) -> None:
    """Daemon liveness probes are TTL-cached so repeated commands avoid extra round-trips."""
    engine = get_engine()
    assert ((engine.ping(), engine.ping()), docker_daemon.call_names().count("ping")) == (
        (True, True),
        1,
    )


def test_ping_returns_false_when_daemon_down(docker_daemon: DockerEngineFake) -> None:
    """A failing socket ping reports the daemon as unreachable rather than raising."""
    docker_daemon.fail("ping", RuntimeError("connection refused"))
    assert get_engine().ping() is False


def test_cache_entry_expires(docker_daemon: DockerEngineFake, clock: ClockFake) -> None:
    """A memoised ping is asked again once its TTL elapses."""
    engine = get_engine()
    engine.ping()
    clock.shift(DEFAULT_DOCKER_CACHE_TTL_SECONDS - 0.1)
    engine.ping()
    within = docker_daemon.call_names().count("ping")
    clock.shift(0.2)
    engine.ping()

    assert (within, docker_daemon.call_names().count("ping")) == (1, 2)
