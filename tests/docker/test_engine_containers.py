"""Tests for the containers of `DockerEngineService`: introspection, stats and lifecycle.

The service runs over `docker_daemon`, the in-memory engine of
`tests/support/fakes/docker_engine.py` (#1316).
"""

from __future__ import annotations

import pytest

from devops_cli.docker.engine import (
    get_engine,
)
from devops_cli.exceptions.docker import DockerEngineError
from tests.support.fakes.docker_engine import DockerEngineFake, EngineCall


def test_list_and_inspect_containers(docker_daemon: DockerEngineFake) -> None:
    """Containers are listed and inspected as typed state models."""
    container_id = docker_daemon.add_container("svc")
    docker_daemon.add_container("other")
    engine = get_engine()

    listed = engine.list_containers(name="svc")
    inspected = engine.inspect_container(container_id)

    assert (
        [state.name for state in listed],
        inspected.running,
        [call.kwargs for call in docker_daemon.calls if call.name == "containers.list"],
    ) == (["svc"], True, [{"all": False, "filters": {"name": "svc"}}])


def test_list_containers_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A daemon listing failure surfaces as a typed engine error."""
    docker_daemon.fail("containers.list", RuntimeError("daemon busy"))

    with pytest.raises(DockerEngineError, match="Container listing failed"):
        get_engine().list_containers()


def test_container_stats_and_stream(docker_daemon: DockerEngineFake) -> None:
    """Single-shot and streamed stats both yield typed resource samples."""
    frame = {"pids_stats": {"current": 3}, "memory_stats": {"usage": 100, "limit": 1000}}
    container_id = docker_daemon.add_container("svc")
    docker_daemon.script_stats("svc", [frame, frame, frame])
    engine = get_engine()

    single = engine.container_stats(container_id)
    streamed = list(engine.stream_container_stats(container_id, samples=2))

    assert (single.pids_count, len(streamed), streamed[0].name) == (3, 2, "svc")


def test_stream_container_stats_unbounded_drains_source(docker_daemon: DockerEngineFake) -> None:
    """Without a sample cap, the stats stream is drained to exhaustion after its first frame."""
    frame = {"pids_stats": {"current": 1}}
    container_id = docker_daemon.add_container("svc")
    docker_daemon.script_stats("svc", [frame, frame, frame])

    assert len(list(get_engine().stream_container_stats(container_id))) == 2


def test_container_stats_two_frames_first_empty_precpu(docker_daemon: DockerEngineFake) -> None:
    """container_stats discards the 1st frame, uses the 2nd, and closes the stream."""
    frame1 = {
        "pids_stats": {"current": 1},
        "cpu_stats": {"cpu_usage": {"total_usage": 1000}},
        "precpu_stats": {},
    }
    frame2 = {
        "pids_stats": {"current": 2},
        "cpu_stats": {
            "cpu_usage": {"total_usage": 2000, "percpu_usage": [2000]},
            "system_cpu_usage": 20000,
            "online_cpus": 1,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 1000},
            "system_cpu_usage": 10000,
        },
        "memory_stats": {"usage": 512, "limit": 1024},
    }
    container_id = docker_daemon.add_container("svc")
    docker_daemon.script_stats("svc", [frame1, frame2])

    stats = get_engine().container_stats(container_id)

    assert (
        stats.pids_count,
        stats.cpu_percentage > 0.0,
        "container.stats.close" in docker_daemon.call_names(),
    ) == (2, True, True)


def test_lifecycle_operations_use_direct_api_calls(docker_daemon: DockerEngineFake) -> None:
    """Stop, remove, exec, wait, and logs reach the engine, and stop and remove use the
    low-level calls that take the container ID."""
    running = docker_daemon.add_container("svc")
    docker_daemon.script_exec("svc", ["ls"], output=b"output\n")
    docker_daemon.script_run("job", stdout=b"log line\n", exit_code=7)
    engine = get_engine()
    job = engine.create_container(image="alpine:3", command=["sh"], name="job")
    job.start()

    exec_result = engine.exec_in_container(running, ["ls"], workdir="/app")
    exit_code = engine.wait_container(job.id, timeout=30)
    logs = engine.container_logs(job.id, tail=10)
    engine.stop_container(running, timeout=3)
    engine.remove_container(job.id)

    removal = {"v": False, "link": False, "force": True}
    assert (
        exec_result,
        exit_code,
        logs,
        [call for call in docker_daemon.calls if call.name.startswith("api.")],
        docker_daemon.container_state,
    ) == (
        (0, "output\n"),
        7,
        "log line\n",
        [
            EngineCall("api.stop", (running,), {"timeout": 3}),
            EngineCall("api.remove_container", (running,), removal),
            EngineCall("api.remove_container", (job.id,), removal),
        ],
        {},
    )


def test_exec_in_container_hands_its_environment_to_the_exec(
    docker_daemon: DockerEngineFake,
) -> None:
    """An exec's environment reaches the Engine API, and none is sent when the caller has none."""
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    running = docker_daemon.add_container("svc")
    engine = get_engine()

    engine.exec_in_container(running, ["env"], environment={"TRACEPARENT": traceparent})
    engine.exec_in_container(running, ["env"], workdir="/app")

    assert [call.kwargs for call in docker_daemon.calls if call.name == "container.exec_run"] == [
        {"workdir": None, "environment": {"TRACEPARENT": traceparent}},
        {"workdir": "/app", "environment": None},
    ]


def test_remove_container_tolerates_already_reaped(docker_daemon: DockerEngineFake) -> None:
    """Removing a container the daemon already reclaimed is not an error."""
    get_engine().remove_container("gone")

    assert docker_daemon.call_names()[-1] == "api.remove_container"


def test_stop_container_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A rejected stop surfaces as a typed, container-annotated engine error."""
    with pytest.raises(DockerEngineError, match="Container termination failed") as exc_info:
        get_engine().stop_container("missing")

    assert exc_info.value.details.get("container_id") == "missing"


def test_create_container_failure_records_image(docker_daemon: DockerEngineFake) -> None:
    """A failed creation annotates the offending image in the typed error."""
    with pytest.raises(DockerEngineError) as exc_info:
        get_engine().create_container(image="missing:latest")

    assert (
        exc_info.value.details.get("image"),
        "No such image: missing:latest" in str(exc_info.value),
    ) == ("missing:latest", True)


def test_container_logs_failure_is_typed(docker_daemon: DockerEngineFake) -> None:
    """A log retrieval failure surfaces as a typed engine error."""
    container_id = docker_daemon.add_container("svc")
    docker_daemon.fail("container.logs", RuntimeError("stream closed"))

    with pytest.raises(DockerEngineError, match="Container log retrieval failed"):
        get_engine().container_logs(container_id)
