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

from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, Protocol


class EngineContainer(Protocol):
    """A container, as `containers.get`, `containers.create` and `containers.list` return it."""

    attrs: dict[str, Any]

    @property
    def id(self) -> str:
        """The full container ID."""
        ...

    @property
    def name(self) -> str:
        """The container name, without the leading slash."""
        ...

    @property
    def status(self) -> str:
        """The state of the container when it was last read, such as `running` or `exited`."""
        ...

    def start(self, **kwargs: Any) -> None:
        """Start the container (`POST /containers/{id}/start`)."""
        ...

    def reload(self) -> None:
        """Read the container's `attrs` again (`GET /containers/{id}/json`)."""
        ...

    def wait(self, **kwargs: Any) -> dict[str, Any]:
        """Block until the container stops, and return the daemon's `StatusCode` reply."""
        ...

    def logs(self, **kwargs: Any) -> Any:
        """The container's output: bytes, or a stream of bytes with `stream=True`."""
        ...

    def stats(self, **kwargs: Any) -> Any:
        """A resource sample, or a stream of samples with `stream=True`."""
        ...

    def exec_run(
        self,
        cmd: str | Sequence[str],
        *,
        workdir: str | None = None,
        environment: Mapping[str, str] | Sequence[str] | None = None,
    ) -> tuple[int | None, Any]:
        """Run a command in the running container, and return its exit code and output."""
        ...

    def remove(self, **kwargs: Any) -> None:
        """Remove the container (`DELETE /containers/{id}`)."""
        ...


class EngineContainers(Protocol):
    """`DockerClient.containers`."""

    def get(self, container_id: str) -> EngineContainer:
        """Read one container by ID or name; `docker.errors.NotFound` when there is none."""
        ...

    def list(
        self, all: bool = False, filters: Mapping[str, Any] | None = None
    ) -> list[EngineContainer]:
        """The running containers, or every container with `all=True`."""
        ...

    def create(
        self, image: str, command: str | Sequence[str] | None = None, **kwargs: Any
    ) -> EngineContainer:
        """Create a container from an image without starting it."""
        ...

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Remove the stopped containers."""
        ...


class EngineImage(Protocol):
    """An image, as `images.list` and `images.build` return it."""

    attrs: dict[str, Any]

    @property
    def id(self) -> str:
        """The image ID, `sha256:` and the digest."""
        ...

    @property
    def short_id(self) -> str:
        """The image ID cut to 12 characters of the digest after `sha256:`."""
        ...

    @property
    def tags(self) -> list[str]:
        """The image's tags, such as `alpine:3`."""
        ...


class EngineImages(Protocol):
    """`DockerClient.images`."""

    def list(
        self, name: str | None = None, all: bool = False, filters: Mapping[str, Any] | None = None
    ) -> list[EngineImage]:
        """The local images, or the images of one repository with `name`."""
        ...

    def build(self, **kwargs: Any) -> tuple[EngineImage, Iterator[dict[str, Any]]]:
        """Build an image, and return it with the build's log entries."""
        ...

    def push(self, repository: str, tag: str | None = None, **kwargs: Any) -> Any:
        """Push an image: the reply text, or a stream of status entries with `stream=True`."""
        ...

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Remove the dangling images."""
        ...


class EngineNetwork(Protocol):
    """A network, as `networks.get`, `networks.create` and `networks.list` return it."""

    attrs: dict[str, Any]

    @property
    def id(self) -> str:
        """The network ID."""
        ...

    @property
    def name(self) -> str:
        """The network name."""
        ...

    def remove(self) -> None:
        """Remove the network (`DELETE /networks/{id}`)."""
        ...


class EngineNetworks(Protocol):
    """`DockerClient.networks`."""

    def get(self, network_id: str, **kwargs: Any) -> EngineNetwork:
        """Read one network by ID or name; `docker.errors.NotFound` when there is none."""
        ...

    def create(self, name: str, **kwargs: Any) -> EngineNetwork:
        """Create a network, such as an internal bridge with `driver` and `internal`."""
        ...

    def list(self, **kwargs: Any) -> list[EngineNetwork]:
        """The networks."""
        ...

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Remove the networks that no container uses."""
        ...


class EngineVolume(Protocol):
    """A volume, as `volumes.list` returns it."""

    attrs: dict[str, Any]

    @property
    def id(self) -> str:
        """The volume name, which is its ID."""
        ...

    @property
    def name(self) -> str:
        """The volume name."""
        ...


class EngineVolumes(Protocol):
    """`DockerClient.volumes`."""

    def list(self, **kwargs: Any) -> list[EngineVolume]:
        """The volumes."""
        ...

    def prune(self, filters: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Remove the volumes that no container uses."""
        ...


class EngineApi(Protocol):
    """`DockerClient.api`: the low-level calls that take a container ID and no model."""

    def stop(self, container: str, timeout: int | None = None) -> None:
        """Stop a container."""
        ...

    def remove_container(
        self, container: str, v: bool = False, link: bool = False, force: bool = False
    ) -> None:
        """Remove a container."""
        ...

    def prune_builds(self, **kwargs: Any) -> dict[str, Any]:
        """Remove the build cache that no build uses."""
        ...


class EngineClient(Protocol):
    """`docker.DockerClient`: the collections, the daemon facts and the low-level API."""

    @property
    def containers(self) -> EngineContainers:
        """The containers."""
        ...

    @property
    def images(self) -> EngineImages:
        """The images."""
        ...

    @property
    def networks(self) -> EngineNetworks:
        """The networks."""
        ...

    @property
    def volumes(self) -> EngineVolumes:
        """The volumes."""
        ...

    @property
    def api(self) -> EngineApi:
        """The low-level API client."""
        ...

    def ping(self) -> bool:
        """Whether the daemon answers `GET /_ping`."""
        ...

    def info(self) -> dict[str, Any]:
        """The daemon's facts (`GET /info`)."""
        ...

    def version(self) -> dict[str, Any]:
        """The daemon's version and components (`GET /version`)."""
        ...

    def df(self) -> dict[str, Any]:
        """The daemon's disk use (`GET /system/df`)."""
        ...

    def close(self) -> None:
        """Close the client's connections."""
        ...


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
