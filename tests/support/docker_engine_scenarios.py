"""The scenarios of the Docker engine's contract suite: SDK calls, and what each one shows (#1316).

Each scenario makes the calls of `devops_cli.docker.sdk` on an `EngineClient` and returns what a
caller sees, with the parts that differ between engines and runs left out: IDs, times, byte
counts, and the order of the lines of stdout and stderr in one log.
`tests/docker/test_engine_contract.py` runs each scenario over `DockerEngineFake` and over the
docker SDK client reading the Engine API's recorded answers. `tests/support/docker_engine_recording`
records those answers by running the same scenarios over a real engine.

`seed_fake` gives the fake what the scenario expects of the engine before it runs: what a command
prints and exits with, a volume. `prepare` and `clean` do the same on a real engine through a
client that the recording does not record, and remove what the scenario leaves behind. Every
object a scenario makes is named with `PREFIX`, so the recording keeps those and nothing else.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import docker

from tests.support.fakes.docker_engine import DockerEngineFake

if TYPE_CHECKING:
    # Only a type: the fail-to-pass replay loads this plugin on a base without the module.
    from devops_cli.docker.sdk import EngineClient

PREFIX = "devops-contract"
IMAGE = "alpine:3"
EXIT_NAME = f"{PREFIX}-exit"
EXIT_COMMAND = ["sh", "-c", "echo hello; echo oops >&2; exit 2"]
RUN_NAME = f"{PREFIX}-run"
EXEC_COMMAND = ["sh", "-c", "echo hi; exit 3"]
NETWORK_NAME = f"{PREFIX}-net"
VOLUME_NAME = f"{PREFIX}-vol"
BUILD_TAG = f"{PREFIX}-build:1"
ABSENT = f"{PREFIX}-absent"
# The sections of a stats frame that the service's projection reads.
STATS_SECTIONS = frozenset({"cpu_stats", "precpu_stats", "memory_stats", "pids_stats"})
# The sections of `GET /system/df` that the service and the dashboard read.
DISK_SECTIONS = frozenset({"LayersSize", "Images", "Containers", "Volumes", "BuildCache"})
_DOCKERFILE = f"FROM {IMAGE}\nLABEL devops.contract=build\n"


def _refusal(call: Callable[[], Any]) -> tuple[str, int | None, str]:
    """The SDK error a call raises: its class, the reply's status and the daemon's reason."""
    try:
        call()
    except docker.errors.APIError as exc:
        return type(exc).__name__, exc.status_code, str(exc.explanation)
    return "none", None, ""


def daemon_facts(client: EngineClient) -> tuple[Any, ...]:
    """The daemon answers a ping, and reports its security options, PID limit and engine."""
    info, version = client.info(), client.version()
    components = [str(part.get("Name")) for part in version.get("Components") or []]
    return (
        client.ping(),
        isinstance(info.get("SecurityOptions"), list),
        isinstance(info.get("PidsLimit"), bool),
        "IndexServerAddress" in info,
        "Engine" in components,
        isinstance(version.get("ApiVersion"), str),
    )


def container_runs_to_exit(client: EngineClient) -> tuple[Any, ...]:
    """A container prints to both streams and exits; its logs, state and listing show it."""
    container = client.containers.create(
        IMAGE, EXIT_COMMAND, name=EXIT_NAME, labels={"devops.contract": "exit"}
    )
    container.start()
    status = container.wait(timeout=30)["StatusCode"]
    # The engine reads stdout and stderr from two pipes, so the order of their lines in one log
    # can differ from run to run; the lines are compared as a sorted list.
    both = container.logs(stdout=True, stderr=True, stream=False, tail="all", timestamps=False)
    out = b"".join(container.logs(stdout=True, stderr=False, stream=True, follow=False))
    err = container.logs(stdout=False, stderr=True)
    container.reload()
    listed = [c.name for c in client.containers.list(all=True, filters={"name": EXIT_NAME})]
    found = client.containers.get(container.id[:12]).name
    client.api.remove_container(container.id, force=True)
    return (
        status,
        sorted(both.splitlines(keepends=True)),
        out,
        err,
        container.status,
        container.attrs["State"]["ExitCode"],
        container.attrs["Config"]["Labels"],
        listed,
        found,
        _refusal(lambda: client.containers.get(container.id))[:2],
    )


def container_execs_and_reports_stats(client: EngineClient) -> tuple[Any, ...]:
    """A running container runs a command, streams stats frames, and stops when told to."""
    container = client.containers.create(IMAGE, ["sleep", "30"], name=RUN_NAME)
    container.start()
    container.reload()
    running = container.status
    exit_code, output = container.exec_run(
        EXEC_COMMAND, workdir="/", environment={"DEVOPS_CONTRACT": "1"}
    )
    stream = container.stats(stream=True, decode=True)
    frames = [next(stream), next(stream)]
    stream.close()
    one = container.stats(stream=False)
    client.api.stop(container.id, timeout=1)
    container.reload()
    stopped = (container.status, container.attrs["State"]["ExitCode"])
    refused = _refusal(lambda: container.exec_run(["true"]))[:2]
    client.api.remove_container(container.id, force=True)
    return (
        running,
        (exit_code, output),
        all(STATS_SECTIONS <= set(frame) for frame in frames),
        STATS_SECTIONS <= set(one),
        stopped,
        refused,
    )


def missing_objects(client: EngineClient) -> tuple[Any, ...]:
    """A container, a network and an image that do not exist are refused with 404."""
    return (
        _refusal(lambda: client.containers.get(ABSENT)),
        _refusal(lambda: client.api.stop(ABSENT, timeout=1)),
        _refusal(lambda: client.api.remove_container(ABSENT, force=True)),
        _refusal(lambda: client.networks.get(ABSENT)),
        _refusal(lambda: client.containers.create(f"{ABSENT}:never", ["true"])),
    )


def internal_network(client: EngineClient) -> tuple[Any, ...]:
    """An internal bridge network is made, read, listed and removed."""
    made = client.networks.create(NETWORK_NAME, driver="bridge", internal=True)
    read = client.networks.get(NETWORK_NAME)
    listed = sorted(
        network.name for network in client.networks.list() if network.name.startswith(PREFIX)
    )
    taken = _refusal(lambda: client.networks.create(NETWORK_NAME, driver="bridge"))[:2]
    read.remove()
    return (
        made.name,
        read.attrs["Internal"],
        read.attrs["Driver"],
        listed,
        taken,
        _refusal(lambda: client.networks.get(NETWORK_NAME))[:2],
    )


def inventory(client: EngineClient) -> tuple[Any, ...]:
    """The images of a repository, the volumes and the disk use list what the engine holds."""
    tags = sorted(tag for image in client.images.list(name="alpine") for tag in image.tags)
    volumes = sorted(v.name for v in client.volumes.list() if v.name.startswith(PREFIX))
    usage = client.df()
    return (
        IMAGE in tags,
        volumes,
        DISK_SECTIONS <= set(usage),
        all(isinstance(usage[section], list) for section in DISK_SECTIONS - {"LayersSize"}),
    )


def prunes(client: EngineClient) -> tuple[Any, ...]:
    """Each prune reports what it removed; with nothing to remove, nothing and no bytes."""
    replies = (
        client.api.prune_builds(),
        client.containers.prune(),
        client.networks.prune(),
        client.images.prune(),
        client.volumes.prune(),
    )
    return tuple((sorted(reply), reply.get("SpaceReclaimed")) for reply in replies)


def build_and_push(client: EngineClient) -> tuple[Any, ...]:
    """An image is built from a context and tagged; a push of an image that is not local fails."""
    with tempfile.TemporaryDirectory() as context:
        (Path(context) / "Dockerfile").write_text(_DOCKERFILE, encoding="utf-8")
        image, log = client.images.build(path=context, tag=BUILD_TAG, rm=True, nocache=True)
    entries = list(client.images.push(ABSENT, tag="1", stream=True, decode=True))
    return (
        BUILD_TAG in image.tags,
        image.short_id.startswith("sha256:") and len(image.short_id) == 19,
        any("stream" in entry for entry in log),
        "error" in entries[-1],
    )


def _seed_nothing(fake: DockerEngineFake) -> None:
    """The scenario expects only what the fake holds from the start."""


def _seed_exit(fake: DockerEngineFake) -> None:
    fake.script_run(EXIT_NAME, stdout=b"hello\n", stderr=b"oops\n", exit_code=2)


def _seed_exec(fake: DockerEngineFake) -> None:
    fake.script_exec(RUN_NAME, EXEC_COMMAND, exit_code=3, output=b"hi\n")


def _seed_volume(fake: DockerEngineFake) -> None:
    fake.add_volume(VOLUME_NAME)


def _prepare_volume(real: Any) -> None:
    real.volumes.create(VOLUME_NAME)


def _clean(real: Any) -> None:
    """Remove every object a scenario made on a real engine."""
    for container in real.containers.list(all=True, filters={"name": PREFIX}):
        container.remove(force=True)
    for network in real.networks.list(names=[NETWORK_NAME]):
        network.remove()
    for volume in real.volumes.list(filters={"name": PREFIX}):
        volume.remove(force=True)
    for image in real.images.list(name=BUILD_TAG.split(":", 1)[0]):
        real.images.remove(image.id, force=True)


@dataclass(frozen=True)
class EngineScenario:
    """A scenario: its calls, what the fake must hold, and the setup of a real engine."""

    name: str
    run: Callable[[EngineClient], tuple[Any, ...]]
    seed_fake: Callable[[DockerEngineFake], None] = _seed_nothing
    prepare: Callable[[Any], None] = _clean
    clean: Callable[[Any], None] = _clean


def _prepare_and_add_volume(real: Any) -> None:
    _clean(real)
    _prepare_volume(real)


SCENARIOS: tuple[EngineScenario, ...] = (
    EngineScenario("daemon_facts", daemon_facts),
    EngineScenario("container_runs_to_exit", container_runs_to_exit, _seed_exit),
    EngineScenario(
        "container_execs_and_reports_stats", container_execs_and_reports_stats, _seed_exec
    ),
    EngineScenario("missing_objects", missing_objects),
    EngineScenario("internal_network", internal_network),
    EngineScenario("inventory", inventory, _seed_volume, _prepare_and_add_volume),
    EngineScenario("prunes", prunes),
    EngineScenario("build_and_push", build_and_push),
)
