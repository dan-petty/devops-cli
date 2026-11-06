"""Tests for the daemon facts of `DockerEngineService`: engine kind, rootless mode and security.

The service runs over `docker_daemon`, the in-memory engine of
`tests/support/fakes/docker_engine.py` (#1316). Time is `ClockFake`.
"""

from __future__ import annotations

from typing import Any

import pytest
from docker.errors import DockerException

from devops_cli.docker.engine import (
    DockerEngineService,
    get_engine,
)
from devops_cli.exceptions.docker import DockerDaemonUnavailableError
from devops_cli.models.docker import EngineSecurityInfo
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.docker_engine import DockerEngineFake

_BUILTIN_SECCOMP = "name=seccomp,profile=builtin"


def test_engine_kind_podman_and_docker(docker_daemon: DockerEngineFake) -> None:
    """kind() identifies Podman Engine via Components or falls back to Docker."""
    docker_engine_kind = (get_engine().kind(), get_engine().is_podman())
    podman = DockerEngineFake()
    podman.set_podman()
    DockerEngineService.install(podman.client_factory)

    assert (docker_engine_kind, (get_engine().kind(), get_engine().is_podman())) == (
        ("Docker", False),
        ("Podman", True),
    )


@pytest.mark.parametrize(
    ("security_options", "rootless"),
    [(["name=rootless", "name=seccomp"], True), (["name=apparmor"], False)],
    ids=["rootless", "rootful"],
)
def test_engine_is_rootless(
    docker_daemon: DockerEngineFake, security_options: list[str], rootless: bool
) -> None:
    """is_rootless() checks info()['SecurityOptions'] for name=rootless."""
    docker_daemon.info_data["SecurityOptions"] = security_options
    engine = get_engine()

    assert (engine.is_rootless(), engine.security_options()) == (rootless, security_options)


def test_engine_facts_memoized(docker_daemon: DockerEngineFake) -> None:
    """Engine facts (kind, is_rootless) are fetched once and memoized."""
    docker_daemon.set_podman()
    docker_daemon.info_data["SecurityOptions"] = ["name=rootless"]
    engine = get_engine()
    for _ in range(2):
        engine.kind()
        engine.is_rootless()

    assert (
        docker_daemon.call_names().count("version"),
        docker_daemon.call_names().count("info"),
    ) == (1, 1)


@pytest.mark.parametrize(
    ("daemon_info", "reported"),
    [
        pytest.param(
            {"SecurityOptions": [_BUILTIN_SECCOMP, "name=cgroupns"], "PidsLimit": True},
            EngineSecurityInfo(
                options=(_BUILTIN_SECCOMP, "name=cgroupns"), pids_limit_supported=True
            ),
            id="builtin-seccomp",
        ),
        pytest.param(
            {"SecurityOptions": ["name=seccomp,profile=unconfined"], "PidsLimit": True},
            EngineSecurityInfo(
                options=("name=seccomp,profile=unconfined",), pids_limit_supported=True
            ),
            id="unconfined-seccomp",
        ),
        pytest.param(
            {"SecurityOptions": ["name=rootless", _BUILTIN_SECCOMP], "PidsLimit": True},
            EngineSecurityInfo(
                options=("name=rootless", _BUILTIN_SECCOMP), pids_limit_supported=True
            ),
            id="rootless",
        ),
        pytest.param(
            {"SecurityOptions": [_BUILTIN_SECCOMP], "PidsLimit": False},
            EngineSecurityInfo(options=(_BUILTIN_SECCOMP,), pids_limit_supported=False),
            id="no-pids-limit",
        ),
        pytest.param(
            {"SecurityOptions": [], "PidsLimit": True},
            EngineSecurityInfo(options=(), pids_limit_supported=True),
            id="no-options",
        ),
        pytest.param({}, EngineSecurityInfo(), id="keys-omitted"),
        pytest.param(
            {"SecurityOptions": None, "PidsLimit": None},
            EngineSecurityInfo(),
            id="keys-null",
        ),
    ],
)
def test_security_info_reports_what_the_daemon_declares(
    docker_daemon: DockerEngineFake, daemon_info: dict[str, Any], reported: EngineSecurityInfo
) -> None:
    """The daemon's security options and pids-limit support are reported, and a key the daemon
    omits stays unreported rather than reading as a negative."""
    docker_daemon.info_data = daemon_info

    assert get_engine().security_info() == reported


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionError("connection refused: " + "x" * 1000),
        DockerException("api error"),
        DockerDaemonUnavailableError("socket gone", host="unix:///x"),
    ],
    ids=["socket-error", "docker-sdk-error", "daemon-unavailable"],
)
def test_security_info_never_raises_and_bounds_the_reason(
    docker_daemon: DockerEngineFake, failure: Exception
) -> None:
    """A daemon that cannot answer yields the reason, capped at 256 characters, and no facts."""
    docker_daemon.fail("info", failure)

    report = get_engine().security_info()

    assert (report, len(str(report.error)) <= 256) == (
        EngineSecurityInfo(error=str(failure)[:256]),
        True,
    )


def test_one_info_call_serves_the_security_facts(docker_daemon: DockerEngineFake) -> None:
    """security_info(), security_options() and is_rootless() read one cached info() answer."""
    docker_daemon.info_data = {"SecurityOptions": ["name=rootless"], "PidsLimit": True}
    engine = get_engine()

    assert (
        engine.security_info(),
        engine.security_options(),
        engine.is_rootless(),
        docker_daemon.call_names().count("info"),
    ) == (
        EngineSecurityInfo(options=("name=rootless",), pids_limit_supported=True),
        ["name=rootless"],
        True,
        1,
    )


def test_an_unreachable_daemon_reports_no_security_options_and_not_rootless(
    docker_daemon: DockerEngineFake,
) -> None:
    """Callers that only want the options or rootless flag keep the empty answer on failure."""
    docker_daemon.fail("info", OSError("down"))
    engine = get_engine()

    assert (engine.security_options(), engine.is_rootless()) == ([], False)


def test_security_info_failure_is_retried_after_two_seconds_and_success_after_the_ttl(
    docker_daemon: DockerEngineFake, clock: ClockFake
) -> None:
    """A failed answer is remembered for 2 s, like a failed ping, and a good one for the normal
    cache lifetime."""
    docker_daemon.fail("info", OSError("down"), times=1)
    docker_daemon.info_data = {"SecurityOptions": [_BUILTIN_SECCOMP], "PidsLimit": True}
    engine = get_engine()

    reads: list[tuple[float, bool, int]] = []
    at = 0.0
    for elapsed in (0.0, 1.9, 2.1, 4.0, 5.2, 7.5):
        clock.shift(elapsed - at)
        at = elapsed
        error = engine.security_info().error
        reads.append((elapsed, error is None, docker_daemon.call_names().count("info")))

    assert reads == [
        (0.0, False, 1),
        (1.9, False, 1),
        (2.1, True, 2),
        (4.0, True, 2),
        (5.2, True, 2),
        (7.5, True, 3),
    ]
