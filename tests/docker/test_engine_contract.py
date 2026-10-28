"""The contract of the Docker engine's fake: it answers the docker SDK's calls as an engine does (#1316).

Each scenario of `tests/support/docker_engine_scenarios.py` runs twice: once over
`DockerEngineFake`, and once through a real `docker.DockerClient` over the Engine API's answers,
recorded from Docker Engine 29.9.2 (API 1.56) on 2026-10-28 in
`tests/fixtures/docker_engine/recorded_exchanges.json`. `RecordedEngine` replays them in order on
a Unix socket the test binds, offline, and fails a request the recording does not hold. Both runs
must show what each case writes out; where they differ, the fake is wrong.

Covered: the daemon's ping, facts and version; a container that runs to its exit, with its logs
by stream, its state, its listing and its removal; a container's log read as `(stdout, stderr)`
frames with `tail`, `timestamps` and `follow`, and with a TTY; a running container's exec, stats
stream and stop; the 404 of a container, a network and an image that do not exist; an internal
network made, read, listed, refused a second time and removed; the images of a repository, the
volumes and the disk use; each prune; a build and a push that the engine refuses. Through `DockerEngineService`,
the service builds the SDK's own client of its endpoint and reads the same daemon facts as over
the fake, and an engine that does not answer fails alike over both.

Not recorded: a Podman engine, for want of one on the recording host (`set_podman` follows the
`Components` that Podman's `/version` names); a TLS endpoint; an engine that stops in the middle
of a session; and the `since` and `until` options of `logs`, which no caller uses.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import docker
import pytest

from devops_cli.docker.engine import DockerEngineService
from devops_cli.exceptions.docker import DockerDaemonUnavailableError
from devops_cli.models.docker import EngineSecurityInfo
from tests.support.docker_engine_replay import (
    RecordedEngine,
    load_record,
    scenario_exchanges,
    short_socket_dir,
)
from tests.support.docker_engine_scenarios import SCENARIOS, EngineScenario
from tests.support.fakes.docker_engine import DockerEngineFake

_ABSENT_CONTAINER = ("NotFound", 404, "No such container: devops-contract-absent")
EXPECTED: dict[str, tuple[Any, ...]] = {
    "daemon_facts": (True, True, True, True, True, True),
    "container_runs_to_exit": (
        2,
        [b"hello\n", b"oops\n"],
        b"hello\n",
        b"oops\n",
        "exited",
        2,
        {"devops.contract": "exit"},
        ["devops-contract-exit"],
        "devops-contract-exit",
        ("NotFound", 404),
    ),
    "log_frames_keep_their_stream": (
        [("stderr", b"oops"), ("stdout", b"hello")],
        1,
        True,
        [("stderr", b"oops"), ("stdout", b"hello")],
        [("stderr", b"oops"), ("stdout", b"hello")],
        [("stdout", b"hello"), ("stdout", b"oops")],
    ),
    "container_execs_and_reports_stats": (
        "running",
        (3, b"hi\n"),
        True,
        True,
        ("exited", 137),
        ("APIError", 409),
    ),
    "missing_objects": (
        _ABSENT_CONTAINER,
        _ABSENT_CONTAINER,
        _ABSENT_CONTAINER,
        ("NotFound", 404, "network devops-contract-absent not found"),
        ("ImageNotFound", 404, "No such image: devops-contract-absent:never"),
    ),
    "internal_network": (
        "devops-contract-net",
        True,
        "bridge",
        ["devops-contract-net"],
        ("APIError", 409),
        ("NotFound", 404),
    ),
    "inventory": (True, ["devops-contract-vol"], True, True),
    "prunes": (
        (["CachesDeleted", "SpaceReclaimed"], 0),
        (["ContainersDeleted", "SpaceReclaimed"], 0),
        (["NetworksDeleted"], None),
        (["ImagesDeleted", "SpaceReclaimed"], 0),
        (["SpaceReclaimed", "VolumesDeleted"], 0),
    ),
    "build_and_push": (True, True, True, True),
}


def _over_fake(scenario: EngineScenario) -> tuple[Any, ...]:
    fake = DockerEngineFake()
    fake.add_image("alpine:3", "alpine:latest")
    scenario.seed_fake(fake)
    return scenario.run(fake)


def _over_recording(scenario: EngineScenario) -> tuple[tuple[Any, ...], list[str], int]:
    with RecordedEngine(scenario_exchanges(scenario.name)) as engine:
        client = docker.DockerClient(base_url=engine.base_url, timeout=10)
        try:
            seen = scenario.run(client)
        finally:
            client.close()
    return seen, engine.unexpected, engine.remaining


def test_the_record_is_of_the_locked_docker_sdk() -> None:
    """Verify the recorded exchanges are those of the docker SDK that `uv.lock` installs."""
    assert (load_record()["sdk"], sorted(load_record()["scenarios"])) == (
        docker.__version__,
        sorted(scenario.name for scenario in SCENARIOS),
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
def test_the_fake_answers_each_scenario_as_the_recorded_engine(scenario: EngineScenario) -> None:
    """Verify the fake and the SDK over the recorded engine show the same, with no stray request."""
    assert (_over_fake(scenario), *_over_recording(scenario)) == (
        EXPECTED[scenario.name],
        EXPECTED[scenario.name],
        [],
        0,
    )


def _clear_endpoint_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CONTAINER_HOST", "CONTAINER_CONNECTION", "DOCKER_CONTEXT"):
        monkeypatch.delenv(name, raising=False)


def _daemon_facts(service: DockerEngineService) -> tuple[EngineSecurityInfo, str, bool]:
    """The facts in the order the `daemon_facts` scenario reads them: info, version, ping."""
    return service.security_info(), service.kind(), service.ping()


def test_the_service_builds_the_sdk_client_of_its_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the service, with the SDK's own client of its endpoint, reads the daemon's facts from
    the recorded engine as it reads them from the fake."""
    _clear_endpoint_settings(monkeypatch)
    with RecordedEngine(scenario_exchanges("daemon_facts")) as engine:
        monkeypatch.setenv("DOCKER_HOST", engine.base_url)
        service = DockerEngineService()
        try:
            over_sdk = _daemon_facts(service)
        finally:
            service.close()
    over_fake = _daemon_facts(DockerEngineService(DockerEngineFake().client_factory))

    facts = (
        EngineSecurityInfo(
            options=("name=seccomp,profile=builtin", "name=cgroupns"), pids_limit_supported=True
        ),
        "Docker",
        True,
    )
    assert (over_sdk, over_fake, engine.unexpected, engine.remaining) == (facts, facts, [], 0)


@pytest.fixture
def refusing_engine_socket() -> Iterator[Path]:
    """A socket path that this test binds and never listens on, so a connect is refused."""
    directory = short_socket_dir("dkx")
    path = directory / "engine.sock"
    with socket.socket(socket.AF_UNIX) as bound:
        bound.bind(str(path))
        yield path
    path.unlink(missing_ok=True)
    directory.rmdir()


def _service_failure(service: DockerEngineService) -> tuple[str, str, str | None, bool]:
    try:
        service.client()
    except DockerDaemonUnavailableError as exc:
        return type(exc).__name__, str(exc), exc.details.get("host"), service.ping()
    return "none", "", None, service.ping()


def test_an_engine_that_does_not_answer_fails_alike_through_the_service(
    monkeypatch: pytest.MonkeyPatch, refusing_engine_socket: Path
) -> None:
    """Verify the service reports the same refusal over the SDK client and over an unreachable fake."""
    _clear_endpoint_settings(monkeypatch)
    monkeypatch.setenv("DOCKER_HOST", f"unix://{refusing_engine_socket}")
    fake = DockerEngineFake()
    fake.unreachable = True
    over_sdk = _service_failure(DockerEngineService())
    over_fake = _service_failure(DockerEngineService(fake.client_factory))

    assert (over_sdk, over_fake) == (
        (
            "DockerDaemonUnavailableError",
            "DOCKER_HOST: Error while fetching server API version: "
            "('Connection aborted.', ConnectionRefusedError(111, 'Connection refused'))",
            "DOCKER_HOST",
            False,
        ),
    ) * 2
