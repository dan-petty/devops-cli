"""The Docker engine faked in memory, as the docker SDK client sees it (#1316, ADR 0007).

`DockerEngineFake` stands in for `docker.DockerClient` behind `DockerEngineService`, which builds
its client through the `ClientFactory` that `DockerEngineService.install` gives it. The service's
own code runs for real: the endpoint check, the projections into typed models, the cache and the
mapping of SDK errors onto `DockerEngineError`. The fake answers the calls that
`devops_cli.docker.sdk` names, with the results and the `docker.errors` that the SDK gives over a
real engine, and keeps each call in `calls`.

A test gives the fake its state: images, containers and what each one prints and exits with,
networks, volumes, build cache and the daemon's facts. A container whose run is scripted with
`script_run` exits when it starts; any other container runs until it is stopped. `unreachable`
makes the factory fail as the SDK fails when no daemon answers, and every later call fail as a
dropped connection does.

`tests/docker/test_engine_contract.py` runs the same calls over this fake and over the SDK client
reading the Engine API's recorded answers, and both must agree.
"""

from __future__ import annotations

import hashlib
import io
import itertools
import json
import re
import struct
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import docker
import pytest
import requests
from docker.models.containers import ExecResult

from devops_cli.docker.engine import DockerEngineService

# The Engine API version that the fake speaks; the SDK names it in each request's URL.
ENGINE_API_VERSION = "1.56"
# The time the fake gives every event, in the form the Engine API uses.
EPOCH = "2026-10-28T00:00:00.000000000Z"
NEVER = "0001-01-01T00:00:00Z"
# The exit code of a container that `docker stop` kills after its grace time.
STOPPED_EXIT_CODE = 137
# Why the connection fails when no daemon listens on the socket, as the SDK words it.
REFUSED = "('Connection aborted.', ConnectionRefusedError(111, 'Connection refused'))"
# The SDK's own error when no daemon answers its first request, `GET /version`.
UNREACHABLE_MESSAGE = f"Error while fetching server API version: {REFUSED}"
# The keywords of the SDK's low-level `logs` and `stats`; the models pass theirs on unchanged.
_LOGS_KEYWORDS = frozenset(
    {"stdout", "stderr", "stream", "timestamps", "tail", "since", "follow", "until"}
)
_STATS_KEYWORDS = frozenset({"decode", "stream", "one_shot"})
_DEFAULT_NETWORKS = ("bridge", "host", "none")
# The label an engine puts on a volume it made without a name; a volume prune removes those.
ANONYMOUS_VOLUME_LABEL = "com.docker.volume.anonymous"
_STDOUT = "stdout"
_STDERR = "stderr"
# The number of each stream in the header of a multiplexed log frame, and the header's form.
_STREAM_NUMBERS = {_STDOUT: 1, _STDERR: 2}
_LOG_FRAME_HEADER = struct.Struct(">BxxxL")
# The time the fake puts before each frame of a log read with `timestamps=1`, as an engine does.
LOG_TIME = b"2026-10-28T00:00:00.000000000Z "
# The path of the one request that `EngineApi.get` serves.
_LOGS_PATH = re.compile(r"/v[\d.]+/containers/(?P<container>[^/]+)/logs")


def _digest(*parts: object) -> str:
    """A 64-character hex ID, the form of every Engine API ID."""
    return hashlib.sha256("/".join(str(part) for part in parts).encode()).hexdigest()


def _api_error(
    error: type[docker.errors.APIError], status: int, reason: str, path: str, explanation: str
) -> docker.errors.APIError:
    """The SDK error for an Engine API reply, with the text the SDK gives it."""
    response = requests.Response()
    response.status_code = status
    response.reason = reason
    response.url = f"http+docker://localhost/v{ENGINE_API_VERSION}{path}"
    return error(
        requests.exceptions.HTTPError(response=response),
        response=response,
        explanation=explanation,
    )


def _refuse_keywords(method: str, given: Mapping[str, Any], allowed: frozenset[str]) -> None:
    """Fail as the SDK's low-level method fails for a keyword it does not take."""
    unknown = sorted(set(given) - allowed)
    if unknown:
        raise TypeError(
            f"ContainerApiMixin.{method}() got an unexpected keyword argument '{unknown[0]}'"
        )


def _default_stats(pids: int) -> dict[str, Any]:
    """A stats frame of an idle container, with the sections the Engine API sends."""
    return {
        "read": EPOCH,
        "preread": EPOCH,
        "pids_stats": {"current": pids},
        "blkio_stats": {"io_service_bytes_recursive": []},
        "cpu_stats": {
            "cpu_usage": {"total_usage": 2_000_000},
            "system_cpu_usage": 1_000_000_000,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 1_000_000},
            "system_cpu_usage": 900_000_000,
            "online_cpus": 2,
        },
        "memory_stats": {"usage": 1_048_576, "limit": 2_147_483_648, "stats": {}},
        "networks": {"eth0": {"rx_bytes": 1_024, "tx_bytes": 512}},
    }


@dataclass(frozen=True)
class EngineCall:
    """One call the fake answered: its name, such as `containers.create`, and its arguments."""

    name: str
    args: tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class ScriptedRun:
    """What a container prints and exits with when it starts."""

    frames: list[tuple[str, bytes]]
    exit_code: int


class _StatsStream:
    """A stats stream: its frames, and `close`, which the SDK's stream has and which is kept."""

    def __init__(self, engine: DockerEngineFake, container_id: str, frames: Sequence[Any]) -> None:
        self._engine = engine
        self._container_id = container_id
        self._frames = iter(frames)

    def __iter__(self) -> _StatsStream:
        return self

    def __next__(self) -> Any:
        return next(self._frames)

    def close(self) -> None:
        """Close the stream."""
        self._engine.record("container.stats.close", (self._container_id,))


class FakeContainer:
    """A container, as the SDK's `Container` model shows it."""

    def __init__(self, engine: DockerEngineFake, container_id: str) -> None:
        self._engine = engine
        self._container_id = container_id
        self.attrs: dict[str, Any] = engine.container_attrs(container_id)

    @property
    def id(self) -> str:
        """The full container ID."""
        return self._container_id

    @property
    def short_id(self) -> str:
        """The container ID cut to 12 characters."""
        return self._container_id[:12]

    @property
    def name(self) -> str:
        """The container name, without the leading slash."""
        return str(self.attrs["Name"]).lstrip("/")

    @property
    def status(self) -> str:
        """The state when the container was last read."""
        return str(self.attrs["State"]["Status"])

    def start(self, **kwargs: Any) -> None:
        """Start the container: a scripted run exits at once, any other one runs."""
        self._engine.record("container.start", (self._container_id,), kwargs)
        self._engine.start(self._container_id)

    def reload(self) -> None:
        """Read the container's state again."""
        self._engine.record("container.reload", (self._container_id,))
        self.attrs = self._engine.container_attrs(self._container_id)

    def wait(self, **kwargs: Any) -> dict[str, Any]:
        """The exit code of a container that stopped; a running one times the read out."""
        self._engine.record("container.wait", (self._container_id,), kwargs)
        return self._engine.wait(self._container_id)

    def logs(self, **kwargs: Any) -> Any:
        """The output of the container's run, as the SDK joins the frames of each stream."""
        self._engine.record("container.logs", (self._container_id,), kwargs)
        _refuse_keywords("logs", kwargs, _LOGS_KEYWORDS)
        chunks = self._engine.log_chunks(
            self._container_id,
            stdout=bool(kwargs.get("stdout", True)),
            stderr=bool(kwargs.get("stderr", True)),
            tail=kwargs.get("tail", "all"),
        )
        if kwargs.get("stream"):
            return iter(chunks)
        return b"".join(chunks)

    def stats(self, **kwargs: Any) -> Any:
        """One stats frame, or with `stream=True` the frames the Engine API sends each second."""
        self._engine.record("container.stats", (self._container_id,), kwargs)
        _refuse_keywords("stats", kwargs, _STATS_KEYWORDS)
        frames = self._engine.stats_frames(self._container_id)
        if not kwargs.get("stream", True):
            return frames[-1]
        if kwargs.get("decode"):
            return _StatsStream(self._engine, self._container_id, frames)
        return _StatsStream(
            self._engine, self._container_id, [json.dumps(f).encode() + b"\n" for f in frames]
        )

    def exec_run(
        self,
        cmd: str | Sequence[str],
        *,
        workdir: str | None = None,
        environment: Mapping[str, str] | Sequence[str] | None = None,
    ) -> ExecResult:
        """The scripted result of a command in the running container."""
        self._engine.record(
            "container.exec_run",
            (self._container_id, cmd),
            {"workdir": workdir, "environment": environment},
        )
        return self._engine.exec_run(self._container_id, cmd)

    def remove(self, **kwargs: Any) -> None:
        """Remove the container."""
        self._engine.record("container.remove", (self._container_id,), kwargs)
        self._engine.remove_container(self._container_id, force=bool(kwargs.get("force")))


class FakeImage:
    """An image, as the SDK's `Image` model shows it."""

    def __init__(self, attrs: dict[str, Any]) -> None:
        self.attrs = attrs

    @property
    def id(self) -> str:
        """The image ID, `sha256:` and the digest."""
        return str(self.attrs["Id"])

    @property
    def short_id(self) -> str:
        """`sha256:` and 12 characters of the digest, as the SDK cuts it."""
        return self.id[:19]

    @property
    def tags(self) -> list[str]:
        """The image's tags, without `<none>:<none>`."""
        return [tag for tag in self.attrs.get("RepoTags") or [] if tag != "<none>:<none>"]


class FakeNetwork:
    """A network, as the SDK's `Network` model shows it."""

    def __init__(self, engine: DockerEngineFake, attrs: dict[str, Any]) -> None:
        self._engine = engine
        self.attrs = attrs

    @property
    def id(self) -> str:
        """The network ID."""
        return str(self.attrs["Id"])

    @property
    def name(self) -> str:
        """The network name."""
        return str(self.attrs["Name"])

    def remove(self) -> None:
        """Remove the network."""
        self._engine.record("network.remove", (self.id,))
        self._engine.remove_network(self.id)


class FakeVolume:
    """A volume, as the SDK's `Volume` model shows it."""

    def __init__(self, attrs: dict[str, Any]) -> None:
        self.attrs = attrs

    @property
    def id(self) -> str:
        """The volume name, which is its ID."""
        return str(self.attrs["Name"])

    @property
    def name(self) -> str:
        """The volume name."""
        return str(self.attrs["Name"])


class FakeContainers:
    """`DockerClient.containers`."""

    def __init__(self, engine: DockerEngineFake) -> None:
        self._engine = engine

    def get(self, container_id: str) -> FakeContainer:
        """One container by ID, ID prefix or name."""
        self._engine.record("containers.get", (container_id,))
        return FakeContainer(self._engine, self._engine.find_container(container_id))

    def list(
        self, all: bool = False, filters: Mapping[str, Any] | None = None
    ) -> list[FakeContainer]:
        """The running containers, or every one with `all=True`, by the `name` filter."""
        self._engine.record("containers.list", (), {"all": all, "filters": filters})
        return [
            FakeContainer(self._engine, container_id)
            for container_id in self._engine.list_containers(all_containers=all, filters=filters)
        ]

    def create(
        self, image: str, command: str | Sequence[str] | None = None, **kwargs: Any
    ) -> FakeContainer:
        """Create a container from a local image."""
        self._engine.record("containers.create", (image,), {"command": command, **kwargs})
        return FakeContainer(self._engine, self._engine.create_container(image, command, kwargs))

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Remove the stopped containers."""
        self._engine.record("containers.prune", (), {"filters": filters})
        return self._engine.prune_containers()


class FakeImages:
    """`DockerClient.images`."""

    def __init__(self, engine: DockerEngineFake) -> None:
        self._engine = engine

    def list(
        self, name: str | None = None, all: bool = False, filters: Mapping[str, Any] | None = None
    ) -> list[FakeImage]:
        """The local images, or those of one repository or reference."""
        self._engine.record("images.list", (), {"name": name, "all": all, "filters": filters})
        return [FakeImage(attrs) for attrs in self._engine.list_images(name)]

    def build(self, **kwargs: Any) -> tuple[FakeImage, Iterator[dict[str, Any]]]:
        """Build an image from the scripted steps, tagged with `tag`."""
        self._engine.record("images.build", (), kwargs)
        attrs, log = self._engine.build_image(kwargs.get("tag"))
        return FakeImage(attrs), iter(log)

    def push(self, repository: str, tag: str | None = None, **kwargs: Any) -> Any:
        """Push an image: an image that is not local ends the stream with an error entry."""
        self._engine.record("images.push", (repository,), {"tag": tag, **kwargs})
        entries = self._engine.push_entries(repository, tag)
        if kwargs.get("stream"):
            if kwargs.get("decode"):
                return iter(entries)
            return iter(json.dumps(entry).encode() + b"\r\n" for entry in entries)
        return "".join(json.dumps(entry) + "\r\n" for entry in entries)

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Remove the dangling images: those with no tag."""
        self._engine.record("images.prune", (), {"filters": filters})
        return self._engine.prune_images()


class FakeNetworks:
    """`DockerClient.networks`."""

    def __init__(self, engine: DockerEngineFake) -> None:
        self._engine = engine

    def get(self, network_id: str, **kwargs: Any) -> FakeNetwork:
        """One network by ID or name."""
        self._engine.record("networks.get", (network_id,), kwargs)
        return FakeNetwork(self._engine, self._engine.find_network(network_id))

    def create(self, name: str, **kwargs: Any) -> FakeNetwork:
        """Create a network."""
        self._engine.record("networks.create", (name,), kwargs)
        return FakeNetwork(self._engine, self._engine.create_network(name, kwargs))

    def list(self, **kwargs: Any) -> list[FakeNetwork]:
        """The networks, or those whose names `names` holds."""
        self._engine.record("networks.list", (), kwargs)
        names = kwargs.get("names")
        return [
            FakeNetwork(self._engine, attrs)
            for attrs in self._engine.network_state.values()
            if not names or attrs["Name"] in names
        ]

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Remove the networks that no container uses."""
        self._engine.record("networks.prune", (), {"filters": filters})
        return self._engine.prune_networks()


class FakeVolumes:
    """`DockerClient.volumes`."""

    def __init__(self, engine: DockerEngineFake) -> None:
        self._engine = engine

    def list(self, **kwargs: Any) -> list[FakeVolume]:
        """The volumes."""
        self._engine.record("volumes.list", (), kwargs)
        return [FakeVolume(attrs) for attrs in self._engine.volume_state.values()]

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Remove the anonymous volumes, as an engine does by default."""
        self._engine.record("volumes.prune", (), {"filters": filters})
        return self._engine.prune_volumes()


class _LogReply:
    """A streamed log reply: the body as the engine sends it, read as `requests` reads it."""

    def __init__(self, engine: DockerEngineFake, container_id: str, body: bytes) -> None:
        self._engine = engine
        self._container_id = container_id
        self.raw = io.BytesIO(body)

    def raise_for_status(self) -> None:
        """The reply of a container that exists is `200 OK`."""

    def iter_content(self, chunk_size: int | None = None) -> Iterator[bytes]:
        """The body in chunks, as a streamed reply gives it."""
        yield from iter(lambda: self.raw.read(chunk_size or 4096), b"")

    def close(self) -> None:
        """Close the reply."""
        self._engine.record("logs.close", (self._container_id,))


class FakeApi:
    """`DockerClient.api`: the low-level calls that take a container ID, and the session that
    sends a log read (`GET /containers/{id}/logs` with `stream=True`)."""

    base_url = "http+docker://localhost"
    timeout = 60

    def __init__(self, engine: DockerEngineFake) -> None:
        self._engine = engine

    @property
    def api_version(self) -> str:
        """The Engine API version the client speaks."""
        return ENGINE_API_VERSION

    def get(self, url: str, **kwargs: Any) -> _LogReply:
        """The streamed log of a container; the fake serves no other request of the session."""
        self._engine.record("api.get", (url,), kwargs)
        match = _LOGS_PATH.fullmatch(urlsplit(url).path)
        if match is None or not kwargs.get("stream"):
            raise NotImplementedError(f"DockerEngineFake serves no GET {url} with {kwargs}")
        container_id = self._engine.find_container(match["container"])
        body = self._engine.log_body(container_id, kwargs.get("params") or {})
        return _LogReply(self._engine, container_id, body)

    def stop(self, container: str, timeout: int | None = None) -> None:
        """Stop a container; a running one is killed after its grace time."""
        self._engine.record("api.stop", (container,), {"timeout": timeout})
        self._engine.stop(self._engine.find_container(container))

    def remove_container(
        self, container: str, v: bool = False, link: bool = False, force: bool = False
    ) -> None:
        """Remove a container."""
        self._engine.record(
            "api.remove_container", (container,), {"v": v, "link": link, "force": force}
        )
        self._engine.remove_container(self._engine.find_container(container), force=force)

    def prune_builds(self, **kwargs: Any) -> dict[str, Any]:
        """Remove the build cache that no build uses."""
        self._engine.record("api.prune_builds", (), kwargs)
        return self._engine.prune_build_cache()


class DockerEngineFake:
    """An in-memory Docker engine behind the SDK client's calls."""

    def __init__(self) -> None:
        self.calls: list[EngineCall] = []
        self._failures: dict[str, tuple[BaseException, int | None]] = {}
        self.container_sizes: dict[str, int] = {}
        self.factory_params: list[dict[str, Any]] = []
        self.unreachable = False
        self.closed = False
        self.info_data: dict[str, Any] = {
            "ServerVersion": "29.9.2",
            "OSType": "linux",
            "SecurityOptions": ["name=seccomp,profile=builtin", "name=cgroupns"],
            "PidsLimit": True,
            "IndexServerAddress": "https://index.docker.io/v1/",
            "RegistryConfig": {"Mirrors": [], "IndexConfigs": {}},
        }
        self.version_data: dict[str, Any] = {
            "Version": "29.9.2",
            "ApiVersion": ENGINE_API_VERSION,
            "MinAPIVersion": "1.40",
            "Components": [{"Name": "Engine", "Version": "29.9.2"}],
        }
        self.container_state: dict[str, dict[str, Any]] = {}
        self.image_state: dict[str, dict[str, Any]] = {}
        self.network_state: dict[str, dict[str, Any]] = {}
        self.volume_state: dict[str, dict[str, Any]] = {}
        self.build_cache: list[dict[str, Any]] = []
        self.runs: dict[str, ScriptedRun] = {}
        self.execs: dict[tuple[str, tuple[str, ...]], tuple[int, bytes]] = {}
        self.stats: dict[str, list[dict[str, Any]]] = {}
        self._serial = itertools.count(1)
        for name in _DEFAULT_NETWORKS:
            self.add_network(name, driver=name if name != "none" else "null")

    # -- The client ---------------------------------------------------------------

    def client_factory(self, **params: Any) -> DockerEngineFake:
        """The `ClientFactory` that `DockerEngineService.install` takes: the fake itself."""
        self.factory_params.append(params)
        if self.unreachable:
            raise docker.errors.DockerException(UNREACHABLE_MESSAGE)
        self.closed = False
        return self

    @property
    def containers(self) -> FakeContainers:
        """The containers."""
        return FakeContainers(self)

    @property
    def images(self) -> FakeImages:
        """The images."""
        return FakeImages(self)

    @property
    def networks(self) -> FakeNetworks:
        """The networks."""
        return FakeNetworks(self)

    @property
    def volumes(self) -> FakeVolumes:
        """The volumes."""
        return FakeVolumes(self)

    @property
    def api(self) -> FakeApi:
        """The low-level API."""
        return FakeApi(self)

    def ping(self) -> bool:
        """Whether the daemon answers."""
        self.record("ping")
        return True

    def info(self) -> dict[str, Any]:
        """The daemon's facts."""
        self.record("info")
        return dict(self.info_data)

    def version(self) -> dict[str, Any]:
        """The daemon's version and components."""
        self.record("version")
        return dict(self.version_data)

    def df(self) -> dict[str, Any]:
        """The daemon's disk use: images, containers, volumes and build cache."""
        self.record("df")
        return {
            "LayersSize": sum(int(attrs.get("Size", 0)) for attrs in self.image_state.values()),
            "Images": [dict(attrs) for attrs in self.image_state.values()],
            "Containers": [self._summary(container_id) for container_id in self.container_state],
            "Volumes": [dict(attrs) for attrs in self.volume_state.values()],
            "BuildCache": [dict(entry) for entry in self.build_cache],
        }

    def close(self) -> None:
        """Close the client."""
        self.record("close")
        self.closed = True

    def record(
        self, name: str, args: tuple[Any, ...] = (), kwargs: Mapping[str, Any] | None = None
    ) -> None:
        """Keep a call, and fail it as a dropped connection does when the daemon has gone."""
        self.calls.append(EngineCall(name, args, dict(kwargs or {})))
        if self.unreachable:
            raise requests.exceptions.ConnectionError(REFUSED)
        failure = self._failures.get(name)
        if failure is None:
            return
        error, times = failure
        if times is not None:
            if times <= 1:
                del self._failures[name]
            else:
                self._failures[name] = (error, times - 1)
        raise error

    def fail(self, name: str, error: BaseException, *, times: int | None = None) -> None:
        """Make the call named `name` raise `error`, every time or the next `times` times."""
        self._failures[name] = (error, times)

    def call_names(self) -> list[str]:
        """The names of the calls the fake answered, in order."""
        return [call.name for call in self.calls]

    # -- State a test gives -------------------------------------------------------

    def add_image(self, *tags: str, size: int = 8_000_000, labels: dict[str, str] | None = None):
        """Add a local image with its tags, and return its attributes."""
        image_id = f"sha256:{_digest('image', *tags)}"
        attrs = {
            "Id": image_id,
            "RepoTags": list(tags),
            "RepoDigests": [],
            "Created": EPOCH,
            "Size": size,
            "Labels": dict(labels or {}),
            "Config": {"Labels": dict(labels or {})},
        }
        self.image_state[image_id] = attrs
        return attrs

    def add_container(
        self,
        name: str,
        image: str = "alpine:3",
        *,
        command: Sequence[str] = ("sleep", "30"),
        running: bool = True,
        labels: Mapping[str, str] | None = None,
        size: int = 0,
    ) -> str:
        """Add a container that runs, or one that exited, with `size` bytes it wrote; return its ID."""
        container_id = self._new_container(name, image, list(command), {"labels": labels})
        self.container_sizes[container_id] = size
        if running:
            self._set_running(container_id)
        else:
            self._set_exited(container_id, 0)
        return container_id

    def add_network(self, name: str, *, driver: str = "bridge", internal: bool = False) -> str:
        """Add a network, and return its ID."""
        network_id = _digest("network", name)
        self.network_state[network_id] = {
            "Name": name,
            "Id": network_id,
            "Created": EPOCH,
            "Scope": "local",
            "Driver": driver,
            "Internal": internal,
            "Attachable": False,
            "Labels": {},
            "Containers": {},
        }
        return network_id

    def add_volume(
        self,
        name: str,
        *,
        labels: Mapping[str, str] | None = None,
        anonymous: bool = False,
        size: int = 0,
    ) -> None:
        """Add a volume; an anonymous one is what a volume prune removes."""
        marked = {ANONYMOUS_VOLUME_LABEL: ""} if anonymous else {}
        self.volume_state[name] = {
            "Name": name,
            "UsageData": {"Size": size, "RefCount": 0},
            "Driver": "local",
            "Mountpoint": f"/var/lib/docker/volumes/{name}/_data",
            "Labels": {**dict(labels or {}), **marked},
            "Scope": "local",
            "CreatedAt": EPOCH,
        }

    def add_build_cache(
        self, cache_type: str = "regular", *, size: int = 4_096, in_use: bool = False
    ) -> str:
        """Add a BuildKit cache record, and return its ID."""
        cache_id = _digest("cache", len(self.build_cache))[:25]
        self.build_cache.append(
            {
                "ID": cache_id,
                "Parents": None,
                "Type": cache_type,
                "Description": f"{cache_type} record",
                "InUse": in_use,
                "Shared": False,
                "Size": size,
                "CreatedAt": EPOCH,
                "LastUsedAt": EPOCH,
                "UsageCount": 1,
            }
        )
        return cache_id

    def script_run(
        self,
        name: str,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        exit_code: int = 0,
        frames: Sequence[tuple[str, bytes]] | None = None,
    ) -> None:
        """Make the container named `name` print and exit with this when it starts."""
        written = (
            list(frames)
            if frames is not None
            else [(stream, data) for stream, data in ((_STDOUT, stdout), (_STDERR, stderr)) if data]
        )
        self.runs[name] = ScriptedRun(written, exit_code)

    def script_exec(
        self, name: str, cmd: Sequence[str], *, exit_code: int = 0, output: bytes = b""
    ) -> None:
        """Make a command in the container named `name` exit with this code and output."""
        self.execs[(name, tuple(cmd))] = (exit_code, output)

    def script_stats(self, name: str, frames: Sequence[Mapping[str, Any]]) -> None:
        """Make the container named `name` report these stats frames."""
        self.stats[name] = [dict(frame) for frame in frames]

    def set_podman(self, version: str = "5.6.2") -> None:
        """Answer as a Podman engine of `version` does: its version names the Podman component."""
        self.version_data["Components"] = [{"Name": "Podman Engine", "Version": version}]

    # -- Containers ---------------------------------------------------------------

    def container_attrs(self, container_id: str) -> dict[str, Any]:
        """The inspect payload of a container, as `GET /containers/{id}/json` gives it."""
        return json.loads(json.dumps(self.container_state[container_id]))

    def find_container(self, ref: str) -> str:
        """The ID of the container that an ID, an ID prefix or a name names."""
        for container_id, attrs in self.container_state.items():
            if ref in (container_id, attrs["Name"].lstrip("/")) or (
                len(ref) >= 12 and container_id.startswith(ref)
            ):
                return container_id
        raise _api_error(
            docker.errors.NotFound,
            404,
            "Not Found",
            f"/containers/{ref}/json",
            f"No such container: {ref}",
        )

    def list_containers(
        self, *, all_containers: bool, filters: Mapping[str, Any] | None
    ) -> list[str]:
        """The IDs of the containers that `docker ps` with these options shows."""
        name = (filters or {}).get("name")
        return [
            container_id
            for container_id, attrs in self.container_state.items()
            if (all_containers or attrs["State"]["Running"])
            and (not name or str(name) in attrs["Name"])
        ]

    def create_container(
        self, image: str, command: str | Sequence[str] | None, options: Mapping[str, Any]
    ) -> str:
        """Create a container from a local image, refusing a missing image and a taken name."""
        if not self.list_images(image):
            raise _api_error(
                docker.errors.ImageNotFound,
                404,
                "Not Found",
                "/containers/create",
                f"No such image: {image}",
            )
        name = str(options.get("name") or f"fake_{next(self._serial)}")
        if any(attrs["Name"] == f"/{name}" for attrs in self.container_state.values()):
            raise _api_error(
                docker.errors.APIError,
                409,
                "Conflict",
                "/containers/create",
                f'Conflict. The container name "/{name}" is already in use.',
            )
        argv = [command] if isinstance(command, str) else list(command or [])
        return self._new_container(name, image, argv, options)

    def start(self, container_id: str) -> None:
        """Run a container: a scripted run exits at once, any other one keeps running."""
        name = self.container_state[container_id]["Name"].lstrip("/")
        run = self.runs.get(name)
        if run is None:
            self._set_running(container_id)
            return
        self._set_exited(container_id, run.exit_code)

    def stop(self, container_id: str) -> None:
        """Stop a container; a running one exits with the code of a killed process."""
        if self.container_state[container_id]["State"]["Running"]:
            self._set_exited(container_id, STOPPED_EXIT_CODE)

    def wait(self, container_id: str) -> dict[str, Any]:
        """The exit code of a stopped container; a running one times out the read."""
        state = self.container_state[container_id]["State"]
        if state["Running"]:
            raise requests.exceptions.ReadTimeout(
                "UnixHTTPConnectionPool(host='localhost', port=None): Read timed out."
            )
        return {"Error": None, "StatusCode": state["ExitCode"]}

    def log_frames(
        self, container_id: str, *, stdout: bool, stderr: bool, tail: Any
    ) -> list[tuple[str, bytes]]:
        """The `(stream, bytes)` frames of the selected streams of a container's log, in order.

        Each scripted frame is one entry of the log, so `tail` counts frames.
        """
        name = self.container_state[container_id]["Name"].lstrip("/")
        run = self.runs.get(name)
        wanted = {stream for stream, on in ((_STDOUT, stdout), (_STDERR, stderr)) if on}
        frames = [
            (stream, data) for stream, data in (run.frames if run else []) if stream in wanted
        ]
        if isinstance(tail, int) and tail >= 0:
            return frames[len(frames) - tail :] if tail else []
        return frames

    def log_chunks(
        self, container_id: str, *, stdout: bool, stderr: bool, tail: Any
    ) -> list[bytes]:
        """The payload of each log frame of the selected streams, as the SDK reads them."""
        frames = self.log_frames(container_id, stdout=stdout, stderr=stderr, tail=tail)
        return [data for _, data in frames]

    def log_body(self, container_id: str, params: Mapping[str, Any]) -> bytes:
        """The body of `GET /containers/{id}/logs`: the multiplexed frames that the query selects,
        or, for a container with a TTY, their bytes with no headers."""
        frames = self.log_frames(
            container_id,
            stdout=bool(params.get("stdout")),
            stderr=bool(params.get("stderr")),
            tail=params.get("tail", "all"),
        )
        if params.get("timestamps"):
            frames = [(stream, LOG_TIME + data) for stream, data in frames]
        if self.container_state[container_id]["Config"]["Tty"]:
            return b"".join(data for _, data in frames)
        return b"".join(
            _LOG_FRAME_HEADER.pack(_STREAM_NUMBERS[stream], len(data)) + data
            for stream, data in frames
        )

    def stats_frames(self, container_id: str) -> list[dict[str, Any]]:
        """The stats frames of a container: the scripted ones, or two idle ones."""
        name = self.container_state[container_id]["Name"].lstrip("/")
        return self.stats.get(name) or [_default_stats(1), _default_stats(1)]

    def exec_run(self, container_id: str, cmd: str | Sequence[str]) -> ExecResult:
        """The scripted result of a command; a container that does not run refuses it."""
        attrs = self.container_state[container_id]
        if not attrs["State"]["Running"]:
            raise _api_error(
                docker.errors.APIError,
                409,
                "Conflict",
                f"/containers/{container_id}/exec",
                f"container {container_id} is not running",
            )
        argv = (cmd,) if isinstance(cmd, str) else tuple(cmd)
        exit_code, output = self.execs.get((attrs["Name"].lstrip("/"), argv), (0, b""))
        return ExecResult(exit_code, output)

    def remove_container(self, container_id: str, *, force: bool) -> None:
        """Remove a container; a running one only with `force`."""
        if self.container_state[container_id]["State"]["Running"] and not force:
            raise _api_error(
                docker.errors.APIError,
                409,
                "Conflict",
                f"/containers/{container_id}",
                f"cannot remove container {container_id}: container is running",
            )
        del self.container_state[container_id]

    def prune_containers(self) -> dict[str, Any]:
        """Remove the containers that do not run."""
        stopped = [
            container_id
            for container_id, attrs in self.container_state.items()
            if not attrs["State"]["Running"]
        ]
        for container_id in stopped:
            del self.container_state[container_id]
        reclaimed = sum(self.container_sizes.pop(container_id, 0) for container_id in stopped)
        return {"ContainersDeleted": stopped or None, "SpaceReclaimed": reclaimed}

    def prune_images(self) -> dict[str, Any]:
        """Remove the images with no tag, and report their bytes."""
        dangling = [attrs for attrs in self.image_state.values() if not attrs["RepoTags"]]
        for attrs in dangling:
            del self.image_state[attrs["Id"]]
        return {
            "ImagesDeleted": [{"Deleted": attrs["Id"]} for attrs in dangling] or None,
            "SpaceReclaimed": sum(int(attrs["Size"]) for attrs in dangling),
        }

    def prune_volumes(self) -> dict[str, Any]:
        """Remove the anonymous volumes, and report their bytes."""
        anonymous = [
            attrs
            for attrs in self.volume_state.values()
            if ANONYMOUS_VOLUME_LABEL in attrs["Labels"]
        ]
        for attrs in anonymous:
            del self.volume_state[attrs["Name"]]
        return {
            "VolumesDeleted": [attrs["Name"] for attrs in anonymous] or None,
            "SpaceReclaimed": sum(int(attrs["UsageData"]["Size"]) for attrs in anonymous),
        }

    # -- Images, networks and build cache -----------------------------------------

    def list_images(self, name: str | None) -> list[dict[str, Any]]:
        """The images whose repository or reference `name` names, or every image."""
        if not name:
            return list(self.image_state.values())
        return [
            attrs
            for attrs in self.image_state.values()
            if any(tag == name or tag.split(":", 1)[0] == name for tag in attrs["RepoTags"])
        ]

    def build_image(self, tag: str | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """An image built from one step, tagged with `tag`, and the build's log."""
        attrs = self.add_image(*([tag] if tag else []))
        log = [
            {"stream": "Step 1/1 : FROM alpine:3"},
            {"stream": "\n"},
            {"aux": {"ID": attrs["Id"]}},
            {"stream": f"Successfully built {attrs['Id'][7:19]}\n"},
        ]
        return attrs, log

    def push_entries(self, repository: str, tag: str | None) -> list[dict[str, Any]]:
        """The status entries of a push; an image that is not local ends with an error."""
        reference = f"{repository}:{tag}" if tag else repository
        if self.list_images(reference):
            return [{"status": "Pushed"}]
        message = f"An image does not exist locally with the tag: {repository}"
        return [
            {"status": f"The push refers to repository [docker.io/library/{repository}]"},
            {"errorDetail": {"message": message}, "error": message},
        ]

    def find_network(self, ref: str) -> dict[str, Any]:
        """The network that an ID or a name names."""
        for network_id, attrs in self.network_state.items():
            if ref in (network_id, attrs["Name"]):
                return attrs
        raise _api_error(
            docker.errors.NotFound,
            404,
            "Not Found",
            f"/networks/{ref}",
            f"network {ref} not found",
        )

    def create_network(self, name: str, options: Mapping[str, Any]) -> dict[str, Any]:
        """Create a network, refusing a taken name."""
        if any(attrs["Name"] == name for attrs in self.network_state.values()):
            raise _api_error(
                docker.errors.APIError,
                409,
                "Conflict",
                "/networks/create",
                f"network with name {name} already exists",
            )
        network_id = self.add_network(
            name,
            driver=str(options.get("driver") or "bridge"),
            internal=bool(options.get("internal")),
        )
        return self.network_state[network_id]

    def remove_network(self, network_id: str) -> None:
        """Remove a network."""
        self.find_network(network_id)
        del self.network_state[network_id]

    def prune_networks(self) -> dict[str, Any]:
        """Remove the networks that are not the engine's own."""
        removed = [
            attrs["Name"]
            for attrs in self.network_state.values()
            if attrs["Name"] not in _DEFAULT_NETWORKS
        ]
        self.network_state = {
            network_id: attrs
            for network_id, attrs in self.network_state.items()
            if attrs["Name"] in _DEFAULT_NETWORKS
        }
        return {"NetworksDeleted": removed or None}

    def prune_build_cache(self) -> dict[str, Any]:
        """Remove the cache records no build uses, and report the bytes freed."""
        unused = [entry for entry in self.build_cache if not entry["InUse"]]
        self.build_cache = [entry for entry in self.build_cache if entry["InUse"]]
        return {
            "CachesDeleted": [entry["ID"] for entry in unused] or None,
            "SpaceReclaimed": sum(int(entry["Size"]) for entry in unused),
        }

    # -- Inside -------------------------------------------------------------------

    def _new_container(
        self, name: str, image: str, argv: list[str], options: Mapping[str, Any]
    ) -> str:
        container_id = _digest("container", name, next(self._serial))
        self.container_state[container_id] = {
            "Id": container_id,
            "Name": f"/{name}",
            "Created": EPOCH,
            "Image": image,
            "State": {
                "Status": "created",
                "Running": False,
                "ExitCode": 0,
                "StartedAt": NEVER,
                "FinishedAt": NEVER,
            },
            "Config": {
                "Image": image,
                "Cmd": argv,
                "Labels": dict(options.get("labels") or {}),
                "Tty": bool(options.get("tty")),
            },
            "HostConfig": {"NetworkMode": str(options.get("network_mode") or "bridge")},
            "NetworkSettings": {"Ports": {}},
        }
        return container_id

    def _set_running(self, container_id: str) -> None:
        state = self.container_state[container_id]["State"]
        state.update(Status="running", Running=True, ExitCode=0, StartedAt=EPOCH)

    def _set_exited(self, container_id: str, exit_code: int) -> None:
        state = self.container_state[container_id]["State"]
        state.update(
            Status="exited",
            Running=False,
            ExitCode=exit_code,
            StartedAt=EPOCH if state["StartedAt"] == NEVER else state["StartedAt"],
            FinishedAt=EPOCH,
        )

    def _summary(self, container_id: str) -> dict[str, Any]:
        attrs = self.container_state[container_id]
        return {
            "Id": container_id,
            "Names": [attrs["Name"]],
            "Image": attrs["Config"]["Image"],
            "State": attrs["State"]["Status"],
            "Labels": attrs["Config"]["Labels"],
        }


@pytest.fixture
def docker_daemon(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[DockerEngineFake]:
    """`DockerEngineService` over an in-memory engine that holds `alpine:3`.

    The endpoint is a socket path under the test's own directory that nothing serves, so the
    service resolves and checks it as it does a real one. The service is reset after the test.
    """
    for name in (
        "CONTAINER_HOST",
        "CONTAINER_CONNECTION",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DOCKER_HOST", f"unix://{tmp_path / 'docker.sock'}")
    fake = DockerEngineFake()
    fake.add_image("alpine:3", "alpine:latest")
    DockerEngineService.install(fake.client_factory)
    yield fake
    DockerEngineService.reset_instance()


@contextmanager
def _installed_docker_client(client: Any) -> Iterator[Any]:
    """Make `client` the SDK client of the process-wide DockerEngineService.

    The floor resets the service after the test, so the block leaves the client installed and
    unclosed for the test's assertions on its calls.
    """
    from devops_cli.docker.engine import DockerEngineService

    yield DockerEngineService.install(lambda **_params: client)


@pytest.fixture
def docker_engine():
    """Provide a factory that installs a test's own SDK client in the Docker engine service.

    Its users pass the clients they build until their package's tests move to `docker_daemon`,
    the in-memory engine of `tests/support/fakes/docker_engine.py` (#1316).
    """
    return _installed_docker_client


def _build_specced_docker_client() -> Any:
    from unittest.mock import create_autospec

    import docker
    from docker.models.containers import ContainerCollection
    from docker.models.images import ImageCollection
    from docker.models.networks import NetworkCollection
    from docker.models.volumes import VolumeCollection

    client = create_autospec(docker.DockerClient, instance=True)
    client.containers = create_autospec(ContainerCollection, instance=True)
    client.images = create_autospec(ImageCollection, instance=True)
    client.networks = create_autospec(NetworkCollection, instance=True)
    client.volumes = create_autospec(VolumeCollection, instance=True)
    client.api = create_autospec(docker.APIClient, instance=True)
    return client


@pytest.fixture
def docker_client() -> Any:
    """Return an autospecced DockerClient instance with specced collections and api."""
    return _build_specced_docker_client()


@pytest.fixture
def docker_endpoint_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unserved_side_channel_port: int
):
    """Provide an isolated environment for Docker endpoint resolution tests (#1108)."""
    import hashlib
    import json

    from devops_cli.config.settings import reset_settings_cache
    from devops_cli.docker.engine import DockerEngineService

    monkeypatch.delenv("CONTAINER_HOST", raising=False)
    monkeypatch.delenv("CONTAINER_CONNECTION", raising=False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    monkeypatch.delenv("DOCKER_TLS_VERIFY", raising=False)
    monkeypatch.delenv("DOCKER_CERT_PATH", raising=False)
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)

    fake_run_user = tmp_path / "run_user"
    fake_rootful = tmp_path / "run_podman" / "podman.sock"
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(fake_run_user))
    monkeypatch.setattr("devops_cli.docker.engine.CONST_RUN_USER_BASE", fake_run_user)
    monkeypatch.setattr("devops_cli.docker.engine.CONST_PODMAN_ROOTFUL_SOCKET_PATH", fake_rootful)

    endpoint_config = tmp_path / "devops_endpoint_config.yaml"
    endpoint_config.write_text(
        f"telemetry:\n  enabled: false\n  endpoint: http://127.0.0.1:{unserved_side_channel_port}\n"
        "ai:\n  allow_private_network: false\n  rag:\n    enabled: false\n"
        "qdrant:\n  url: http://localhost:6333\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(endpoint_config))
    reset_settings_cache()

    config_file = tmp_path / "config.json"
    config_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("DOCKER_CONFIG", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    DockerEngineService.reset_instance()

    def write_context(name: str, host: str, skip_tls_verify: bool = False) -> Path:
        name_hash = hashlib.sha256(name.encode("utf-8")).hexdigest()
        meta_dir = tmp_path / "contexts" / "meta" / name_hash
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "Name": name,
            "Metadata": {},
            "Endpoints": {
                "docker": {
                    "Host": host,
                    "SkipTLSVerify": skip_tls_verify,
                }
            },
        }
        meta_path = meta_dir / "meta.json"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        return meta_path

    write_context.tmp_path = tmp_path  # type: ignore[attr-defined]
    write_context.config_file = config_file  # type: ignore[attr-defined]
    write_context.write_context = write_context  # type: ignore[attr-defined]
    write_context.run_user_base = fake_run_user  # type: ignore[attr-defined]
    write_context.rootful_socket = fake_rootful  # type: ignore[attr-defined]
    yield write_context
    DockerEngineService.reset_instance()
    reset_settings_cache()
