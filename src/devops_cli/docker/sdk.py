"""The docker SDK calls that devops-cli makes, as Protocols (#1316).

`DockerEngineService` builds the one SDK client of the process (`docker.DockerClient`) through a
`ClientFactory`, and every Docker call goes through that client: the service's own, the dashboard's
inventory, and `devops docker build` and `push`. These Protocols name each call with the signature
the SDK gives it. Most methods of the SDK's models take `**kwargs` and pass them to the low-level
`APIClient`, so their Protocols take `**kwargs` too: the SDK, not the type checker, refuses a
keyword that its `APIClient` method does not have.

The SDK has no type information, so a type checker cannot hold `docker.DockerClient` to these
Protocols. `tests/docker/test_engine_contract.py` holds the SDK client, over the Engine API's
recorded answers, and the fake in `tests/support/fakes/docker_engine.py` to the same calls.
"""

from __future__ import annotations

import builtins
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, Protocol


class EngineContainer(Protocol):
    """A container, as `containers.get`, `containers.create` and `containers.list` return it.

    `start`, `wait`, `logs`, `stats` and `remove` take the keywords of the SDK's low-level calls
    of the same name; `logs` and `stats` give a stream with `stream=True`. `logs` joins the frames
    of stdout and stderr, so `devops_cli.docker.engine.container_log_frames` reads a log that keeps
    them apart through `EngineApi.get`.
    """

    attrs: dict[str, Any]

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def status(self) -> str: ...

    def start(self, **kwargs: Any) -> None: ...

    def reload(self) -> None: ...

    def wait(self, **kwargs: Any) -> dict[str, Any]: ...

    def logs(self, **kwargs: Any) -> Any: ...

    def stats(self, **kwargs: Any) -> Any: ...

    def exec_run(
        self,
        cmd: str | Sequence[str],
        *,
        workdir: str | None = None,
        environment: Mapping[str, str] | Sequence[str] | None = None,
    ) -> tuple[int | None, Any]: ...

    def remove(self, **kwargs: Any) -> None: ...


class EngineContainers(Protocol):
    """`DockerClient.containers`: `get` raises `docker.errors.NotFound` for a missing container."""

    def get(self, container_id: str) -> EngineContainer: ...

    def list(
        self, all: bool = False, filters: Mapping[str, Any] | None = None
    ) -> builtins.list[EngineContainer]: ...

    def create(
        self, image: str, command: str | Sequence[str] | None = None, **kwargs: Any
    ) -> EngineContainer: ...

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]: ...


class EngineImage(Protocol):
    """An image, as `images.list` and `images.build` return it; `short_id` keeps `sha256:`."""

    attrs: dict[str, Any]

    @property
    def id(self) -> str: ...

    @property
    def short_id(self) -> str: ...

    @property
    def tags(self) -> list[str]: ...


class EngineImages(Protocol):
    """`DockerClient.images`: `push` gives a stream of status entries with `stream=True`."""

    def list(
        self, name: str | None = None, all: bool = False, filters: Mapping[str, Any] | None = None
    ) -> builtins.list[EngineImage]: ...

    def build(self, **kwargs: Any) -> tuple[EngineImage, Iterator[dict[str, Any]]]: ...

    def push(self, repository: str, tag: str | None = None, **kwargs: Any) -> Any: ...

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]: ...


class EngineNetwork(Protocol):
    """A network, as `networks.get`, `networks.create` and `networks.list` return it."""

    attrs: dict[str, Any]

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    def remove(self) -> None: ...


class EngineNetworks(Protocol):
    """`DockerClient.networks`: `get` raises `docker.errors.NotFound` for a missing network."""

    def get(self, network_id: str, **kwargs: Any) -> EngineNetwork: ...

    def create(self, name: str, **kwargs: Any) -> EngineNetwork: ...

    def list(self, **kwargs: Any) -> builtins.list[EngineNetwork]: ...

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]: ...


class EngineVolume(Protocol):
    """A volume, as `volumes.list` returns it; its name is its ID."""

    attrs: dict[str, Any]

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...


class EngineVolumes(Protocol):
    """`DockerClient.volumes`."""

    def list(self, **kwargs: Any) -> builtins.list[EngineVolume]: ...

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]: ...


class EngineApi(Protocol):
    """`DockerClient.api`: the low-level calls that take a container ID and no model.

    It is also the `requests.Session` that sends the SDK's requests to the engine: `get` takes
    the keywords of `requests.Session.get`, `base_url` and `api_version` give the start of each
    Engine API URL, and `timeout` is the client's timeout in seconds.
    """

    base_url: str
    timeout: int

    @property
    def api_version(self) -> str: ...

    def get(self, url: str, **kwargs: Any) -> Any: ...

    def stop(self, container: str, timeout: int | None = None) -> None: ...

    def remove_container(
        self, container: str, v: bool = False, link: bool = False, force: bool = False
    ) -> None: ...

    def prune_builds(self, **kwargs: Any) -> dict[str, Any]: ...


class EngineClient(Protocol):
    """`docker.DockerClient`: the collections, the daemon's facts and the low-level API.

    `ping` is `GET /_ping`, `info` is `GET /info`, `version` is `GET /version` and `df` is
    `GET /system/df`.
    """

    @property
    def containers(self) -> EngineContainers: ...

    @property
    def images(self) -> EngineImages: ...

    @property
    def networks(self) -> EngineNetworks: ...

    @property
    def volumes(self) -> EngineVolumes: ...

    @property
    def api(self) -> EngineApi: ...

    def ping(self) -> bool: ...

    def info(self) -> dict[str, Any]: ...

    def version(self) -> dict[str, Any]: ...

    def df(self) -> dict[str, Any]: ...

    def close(self) -> None: ...


# Builds the SDK client of a resolved endpoint from its keyword arguments: `base_url`, `timeout`
# and, for a TLS endpoint, `tls`. `docker.DockerClient` is the factory of a real engine; it reads
# `GET /version` before it returns, so an engine that does not answer fails here.
ClientFactory = Callable[..., EngineClient]


__all__ = [
    "ClientFactory",
    "EngineApi",
    "EngineClient",
    "EngineContainer",
    "EngineContainers",
    "EngineImage",
    "EngineImages",
    "EngineNetwork",
    "EngineNetworks",
    "EngineVolume",
    "EngineVolumes",
]
