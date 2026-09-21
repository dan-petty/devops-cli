"""Unified in-process Docker Engine API service over the daemon socket.

Every Docker interaction in the codebase funnels through :class:`DockerEngineService`,
which speaks the Engine API directly over the daemon Unix domain socket (or a validated
TCP endpoint) instead of spawning `docker` CLI subprocesses and scraping their stdout.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from typing import Any, ClassVar

from devops_cli.config.constants import (
    CONST_DOCKER_BUILD_CACHE_TYPES,
    CONST_DOCKER_DF_BUILD_CACHE_KEY,
    CONST_DOCKER_HOST_ENV_VAR,
    CONST_DOCKER_NETWORK_HOST_SCHEMES,
    CONST_DOCKER_UNIX_SOCKET_URL,
)
from devops_cli.config.defaults import (
    DEFAULT_DOCKER_CACHE_TTL_SECONDS,
    DEFAULT_DOCKER_PING_TIMEOUT_SECONDS,
    DEFAULT_DOCKER_STOP_TIMEOUT_SECONDS,
    DEFAULT_DOCKER_TIMEOUT_SECONDS,
)
from devops_cli.exceptions.docker import DockerDaemonUnavailableError, DockerEngineError
from devops_cli.models.docker import (
    BuildCacheRecord,
    BuildCacheReport,
    ContainerState,
    ContainerStatEntry,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Engine API Payload Projection Helpers
# =============================================================================


def decode_stream(raw: Any) -> str:
    """Decode an Engine API byte stream into text, tolerating invalid encodings."""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return "" if raw is None else str(raw)


def _cpu_percentage(stats: dict[str, Any]) -> float:
    """Derive CPU utilisation percentage from consecutive Engine API CPU samples."""
    cpu_stats = stats.get("cpu_stats", {}) or {}
    precpu_stats = stats.get("precpu_stats", {}) or {}
    cpu_usage = cpu_stats.get("cpu_usage", {}) or {}
    pre_usage = precpu_stats.get("cpu_usage", {}) or {}

    cpu_delta = cpu_usage.get("total_usage", 0) - pre_usage.get("total_usage", 0)
    system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
    num_cpus = cpu_stats.get("online_cpus") or len(cpu_usage.get("percpu_usage", [1])) or 1

    if system_delta <= 0 or cpu_delta <= 0:
        return 0.0
    return round(float(cpu_delta) / float(system_delta) * float(num_cpus) * 100.0, 2)


def _memory_usage(stats: dict[str, Any]) -> tuple[int, int, float]:
    """Extract cache-adjusted memory usage, limit, and utilisation percentage."""
    memory_stats = stats.get("memory_stats", {}) or {}
    usage = int(memory_stats.get("usage", 0) or 0)
    cache = int((memory_stats.get("stats", {}) or {}).get("cache", 0) or 0)
    limit = int(memory_stats.get("limit", 0) or 0)
    net_usage = max(0, usage - cache)
    percentage = round(net_usage / limit * 100.0, 2) if limit > 0 else 0.0
    return net_usage, limit, percentage


def _network_io(stats: dict[str, Any]) -> tuple[int, int]:
    """Sum ingress and egress byte counters across every container interface."""
    networks = stats.get("networks", {}) or {}
    rx = sum(int((iface or {}).get("rx_bytes", 0) or 0) for iface in networks.values())
    tx = sum(int((iface or {}).get("tx_bytes", 0) or 0) for iface in networks.values())
    return rx, tx


def _block_io(stats: dict[str, Any]) -> tuple[int, int]:
    """Sum cgroup block device read and write byte counters."""
    entries = (stats.get("blkio_stats", {}) or {}).get("io_service_bytes_recursive") or []
    totals = {"read": 0, "write": 0}
    for entry in entries:
        op = str((entry or {}).get("op", "")).lower()
        if op in totals:
            totals[op] += int((entry or {}).get("value", 0) or 0)
    return totals["read"], totals["write"]


def project_container_stats(
    container_id: str, name: str, stats: dict[str, Any]
) -> ContainerStatEntry:
    """Project a raw Engine API stats frame into a typed resource sample."""
    memory_usage, memory_limit, memory_percentage = _memory_usage(stats)
    net_rx, net_tx = _network_io(stats)
    block_read, block_write = _block_io(stats)
    return ContainerStatEntry(
        container_id=container_id,
        name=name,
        cpu_percentage=_cpu_percentage(stats),
        memory_usage_bytes=memory_usage,
        memory_limit_bytes=memory_limit,
        memory_percentage=memory_percentage,
        net_io_in_bytes=net_rx,
        net_io_out_bytes=net_tx,
        block_io_read_bytes=block_read,
        block_io_write_bytes=block_write,
        pids_count=int(((stats.get("pids_stats", {}) or {}).get("current", 0)) or 0),
    )


def _section(attrs: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a named Engine API inspect section, normalising absent or null sections."""
    section = attrs.get(key)
    return section if isinstance(section, dict) else {}


def _project_port_bindings(network_settings: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Project published port bindings into plain string mappings keyed by container port."""
    ports = _section(network_settings, "Ports")
    return {
        str(port): [{str(k): str(v) for k, v in binding.items()} for binding in bindings or []]
        for port, bindings in ports.items()
    }


def project_container_state(attrs: dict[str, Any]) -> ContainerState:
    """Project a raw Engine API inspect payload into a typed container state model."""
    state = _section(attrs, "State")
    config = _section(attrs, "Config")
    health = _section(state, "Health").get("Status")

    return ContainerState(
        container_id=str(attrs.get("Id", "")),
        name=str(attrs.get("Name", "")).lstrip("/"),
        image=str(config.get("Image") or attrs.get("Image", "")),
        status=str(state.get("Status", "")),
        running=bool(state.get("Running", False)),
        exit_code=state.get("ExitCode"),
        health=str(health) if health else None,
        created_at=str(attrs.get("Created", "")),
        started_at=state.get("StartedAt"),
        network_mode=str(_section(attrs, "HostConfig").get("NetworkMode", "")),
        labels={str(k): str(v) for k, v in _section(config, "Labels").items()},
        ports=_project_port_bindings(_section(attrs, "NetworkSettings")),
    )


def _project_build_cache_record(entry: dict[str, Any]) -> BuildCacheRecord:
    """Project a single `GET /system/df` BuildKit cache entry into a typed record."""
    cache_type = str(entry.get("Type", "") or "")
    if cache_type and cache_type not in CONST_DOCKER_BUILD_CACHE_TYPES:
        logger.debug("Unrecognised BuildKit cache record type reported by daemon: %s", cache_type)
    return BuildCacheRecord(
        cache_id=str(entry.get("ID", "")),
        parent=entry.get("Parent") or None,
        cache_type=cache_type,
        description=str(entry.get("Description", "") or ""),
        in_use=bool(entry.get("InUse", False)),
        shared=bool(entry.get("Shared", False)),
        size_bytes=int(entry.get("Size", 0) or 0),
        usage_count=int(entry.get("UsageCount", 0) or 0),
        created_at=str(entry.get("CreatedAt", "") or ""),
        last_used_at=entry.get("LastUsedAt") or None,
    )


def build_cache_report(entries: list[dict[str, Any]]) -> BuildCacheReport:
    """Aggregate raw BuildKit cache entries into a multi-stage cache efficiency report."""
    records = [_project_build_cache_record(entry) for entry in entries]
    total_bytes = sum(record.size_bytes for record in records)
    reclaimable = sum(record.size_bytes for record in records if not record.in_use)
    reused_bytes = sum(record.size_bytes for record in records if record.usage_count > 0)
    return BuildCacheReport(
        records=records,
        total_bytes=total_bytes,
        reclaimable_bytes=reclaimable,
        in_use_count=sum(1 for record in records if record.in_use),
        shared_count=sum(1 for record in records if record.shared),
        reuse_ratio=round(reused_bytes / total_bytes, 4) if total_bytes > 0 else 0.0,
    )


# =============================================================================
# Docker Engine Service
# =============================================================================


class DockerEngineService:
    """Consolidated, high-performance in-process Docker Engine API service.

    Caches the daemon socket connection so repeated container, image, network, and
    build-cache operations reuse a single negotiated Engine API client, and projects
    every response into typed Pydantic models rather than scraped CLI output.
    """

    _instance: ClassVar[DockerEngineService | None] = None

    def __init__(self) -> None:
        self._client: Any = None
        self._host: str | None = None
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl: float = DEFAULT_DOCKER_CACHE_TTL_SECONDS

    @classmethod
    def get_instance(cls) -> DockerEngineService:
        """Retrieve the process-wide singleton engine service."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton for clean test fixture isolation."""
        if cls._instance is not None:
            cls._instance.close()
        cls._instance = None

    # -- Connection lifecycle -------------------------------------------------

    def resolve_host(self) -> str:
        """Resolve the effective daemon endpoint, validating network hosts against SSRF."""
        docker_host = os.environ.get(CONST_DOCKER_HOST_ENV_VAR, "").strip()
        if not docker_host:
            return CONST_DOCKER_UNIX_SOCKET_URL
        if docker_host.startswith(CONST_DOCKER_NETWORK_HOST_SCHEMES):
            self._validate_network_host(docker_host)
        return docker_host

    @staticmethod
    def _validate_network_host(docker_host: str) -> None:
        """Enforce egress guardrails on a TCP/HTTP Docker daemon endpoint."""
        from devops_cli.config.settings import load_settings
        from devops_cli.core.validation import validate_service_url

        settings = load_settings()
        http_url = docker_host.replace("tcp://", "http://", 1)
        validate_service_url(http_url, "Docker Host", allow=settings.ai.allow_private_network)

    def client(self) -> Any:
        """Return the cached Engine API client, negotiating the daemon socket on first use."""
        if self._client is not None:
            return self._client

        host = self.resolve_host()
        try:
            import docker  # type: ignore[import-untyped]

            self._client = docker.from_env(timeout=int(DEFAULT_DOCKER_TIMEOUT_SECONDS))
        except Exception as exc:
            raise DockerDaemonUnavailableError(
                f"Cannot connect to the Docker daemon: {exc}", host=host
            ) from exc

        self._host = host
        return self._client

    def close(self) -> None:
        """Release the cached Engine API socket connection and drop memoised responses."""
        client, self._client, self._host = self._client, None, None
        self._cache.clear()
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                logger.debug("Docker Engine client close failed: %s", exc)

    def ping(self, timeout: float = DEFAULT_DOCKER_PING_TIMEOUT_SECONDS) -> bool:
        """Probe daemon liveness via a zero-overhead Engine API socket ping."""
        cached = self._get_cached("ping")
        if cached is not None:
            return bool(cached)
        try:
            reachable = bool(self.client().ping())
        except Exception as exc:
            logger.debug("Docker daemon ping failed after %.1fs budget: %s", timeout, exc)
            reachable = False
        self._set_cached("ping", reachable, ttl=self._cache_ttl if reachable else 2.0)
        return reachable

    # -- Response cache -------------------------------------------------------

    def _get_cached(self, key: str) -> Any:
        """Return a memoised Engine API response when still within its TTL window."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._cache.pop(key, None)
            return None
        return value

    def _set_cached(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Memoise an Engine API response for the given lifetime."""
        self._cache[key] = (time.monotonic() + (self._cache_ttl if ttl is None else ttl), value)

    # -- Container introspection ---------------------------------------------

    def get_container(self, container_id: str) -> Any:
        """Fetch the raw Engine API container handle for lifecycle operations."""
        try:
            return self.client().containers.get(container_id)
        except DockerEngineError:
            raise
        except Exception as exc:
            raise DockerEngineError(
                f"Container lookup failed: {exc}", container_id=container_id
            ) from exc

    def list_containers(
        self, *, all_containers: bool = False, name: str | None = None
    ) -> list[ContainerState]:
        """List containers as typed state models, optionally filtered by name."""
        filters = {"name": name} if name else None
        try:
            containers = self.client().containers.list(all=all_containers, filters=filters)
        except DockerEngineError:
            raise
        except Exception as exc:
            raise DockerEngineError(f"Container listing failed: {exc}") from exc
        return [project_container_state(getattr(c, "attrs", {}) or {}) for c in containers]

    def inspect_container(self, container_id: str) -> ContainerState:
        """Inspect a container and project the Engine API payload into a typed model."""
        container = self.get_container(container_id)
        return project_container_state(getattr(container, "attrs", {}) or {})

    def container_stats(self, container_id: str) -> ContainerStatEntry:
        """Capture a single typed resource utilisation sample for a container."""
        container = self.get_container(container_id)
        try:
            stats = container.stats(stream=False)
        except Exception as exc:
            raise DockerEngineError(
                f"Container stats capture failed: {exc}", container_id=container_id
            ) from exc
        name = getattr(container, "name", "") or container_id
        return project_container_stats(container_id, name, stats or {})

    def stream_container_stats(
        self, container_id: str, *, samples: int | None = None
    ) -> Iterator[ContainerStatEntry]:
        """Stream typed cgroup resource samples straight off the Engine API stats socket."""
        container = self.get_container(container_id)
        name = getattr(container, "name", "") or container_id
        try:
            stream = container.stats(stream=True, decode=True)
        except Exception as exc:
            raise DockerEngineError(
                f"Container stats stream failed: {exc}", container_id=container_id
            ) from exc
        for index, frame in enumerate(stream):
            if samples is not None and index >= samples:
                return
            yield project_container_stats(container_id, name, frame or {})

    # -- Container lifecycle --------------------------------------------------

    def create_container(self, **create_kwargs: Any) -> Any:
        """Create a container over the Engine API socket without spawning `docker run`."""
        try:
            return self.client().containers.create(**create_kwargs)
        except DockerEngineError:
            raise
        except Exception as exc:
            raise DockerEngineError(
                f"Container creation failed: {exc}", image=str(create_kwargs.get("image", ""))
            ) from exc

    def remove_container(self, container_id: str, *, force: bool = True) -> None:
        """Remove a container via a direct Engine API call, tolerating an already-reaped one."""
        try:
            self.client().api.remove_container(container_id, force=force)
        except Exception as exc:
            logger.debug("Container %s removal failed: %s", container_id, exc)

    def stop_container(
        self, container_id: str, *, timeout: int = DEFAULT_DOCKER_STOP_TIMEOUT_SECONDS
    ) -> None:
        """Stop and remove a container through direct Engine API calls without re-inspecting it."""
        try:
            api = self.client().api
            api.stop(container_id, timeout=timeout)
            api.remove_container(container_id, force=True)
        except DockerEngineError:
            raise
        except Exception as exc:
            raise DockerEngineError(
                f"Container termination failed: {exc}", container_id=container_id
            ) from exc

    def exec_in_container(
        self, container_id: str, command: list[str], *, workdir: str | None = None
    ) -> tuple[int, str]:
        """Execute a command inside a running container and return its status and output."""
        container = self.get_container(container_id)
        try:
            exit_code, output = container.exec_run(command, workdir=workdir)
        except Exception as exc:
            raise DockerEngineError(
                f"Container exec failed: {exc}", container_id=container_id
            ) from exc
        return int(exit_code or 0), decode_stream(output)

    def container_logs(
        self,
        container_id: str,
        *,
        tail: int | None = None,
        timestamps: bool = False,
        follow: bool = False,
    ) -> str:
        """Fetch container logs over the Engine API with stream fidelity preserved."""
        container = self.get_container(container_id)
        try:
            raw = container.logs(
                stdout=True,
                stderr=True,
                tail=tail if tail is not None else "all",
                timestamps=timestamps,
                follow=follow,
            )
        except Exception as exc:
            raise DockerEngineError(
                f"Container log retrieval failed: {exc}", container_id=container_id
            ) from exc
        return decode_stream(raw)

    def container_log_stream(
        self,
        container_id: str,
        *,
        tail: int | str = "all",
        timestamps: bool = False,
        follow: bool = False,
    ) -> Any:
        """Open a demultiplexed Engine API log stream preserving stdout/stderr separation."""
        container = self.get_container(container_id)
        try:
            return container.logs(
                stdout=True,
                stderr=True,
                stream=follow,
                follow=follow,
                tail=tail,
                timestamps=timestamps,
                demux=True,
            )
        except Exception as exc:
            raise DockerEngineError(
                f"Container log stream failed: {exc}", container_id=container_id
            ) from exc

    def wait_container(self, container_id: str, *, timeout: float) -> int:
        """Block until a container exits and return its status code."""
        container = self.get_container(container_id)
        result = container.wait(timeout=int(timeout))
        if isinstance(result, dict):
            return int(result.get("StatusCode", 0))
        return int(result)

    # -- Networks -------------------------------------------------------------

    def ensure_internal_network(self, name: str) -> bool:
        """Ensure an internal (egress-denied) bridge network exists, recreating drifted ones."""
        try:
            client = self.client()
        except DockerDaemonUnavailableError as exc:
            logger.debug("Cannot ensure internal network %s; daemon unavailable: %s", name, exc)
            return False

        try:
            network = client.networks.get(name)
            if (getattr(network, "attrs", {}) or {}).get("Internal") is True:
                return True
            network.remove()
        except Exception as exc:
            logger.debug("Internal network %s absent or non-conforming: %s", name, exc)

        try:
            client.networks.create(name, driver="bridge", internal=True)
            return True
        except Exception as exc:
            logger.debug("Internal network %s creation failed: %s", name, exc)
            return False

    # -- Images & BuildKit cache introspection --------------------------------

    def list_images(self, *, name: str | None = None) -> list[Any]:
        """List local images through the Engine API."""
        try:
            return list(self.client().images.list(name=name))
        except DockerEngineError:
            raise
        except Exception as exc:
            raise DockerEngineError(f"Image listing failed: {exc}") from exc

    def disk_usage(self) -> dict[str, Any]:
        """Query the Engine API disk-usage endpoint (`GET /system/df`)."""
        cached = self._get_cached("disk_usage")
        if cached is not None:
            return dict(cached)
        try:
            usage = self.client().df()
        except DockerEngineError:
            raise
        except Exception as exc:
            raise DockerEngineError(f"Engine disk usage query failed: {exc}") from exc
        usage = dict(usage or {})
        self._set_cached("disk_usage", usage)
        return usage

    def build_cache(self) -> BuildCacheReport:
        """Introspect BuildKit multi-stage layer cache occupancy and reuse efficiency."""
        entries = self.disk_usage().get(CONST_DOCKER_DF_BUILD_CACHE_KEY) or []
        return build_cache_report([dict(entry) for entry in entries])

    def prune_build_cache(self) -> int:
        """Reclaim unused BuildKit cache records and report the bytes freed."""
        try:
            result = self.client().api.prune_builds()
        except DockerEngineError:
            raise
        except Exception as exc:
            raise DockerEngineError(f"Build cache prune failed: {exc}") from exc
        self._cache.pop("disk_usage", None)
        return int((result or {}).get("SpaceReclaimed", 0) or 0)


def get_engine() -> DockerEngineService:
    """Return the process-wide Docker Engine API service singleton."""
    return DockerEngineService.get_instance()


__all__ = [
    "DockerEngineService",
    "decode_stream",
    "build_cache_report",
    "get_engine",
    "project_container_state",
    "project_container_stats",
]
