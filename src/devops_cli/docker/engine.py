"""Unified in-process Docker Engine API service over the daemon socket.

Every Docker interaction in the codebase funnels through :class:`DockerEngineService`,
which speaks the Engine API directly over the daemon Unix domain socket (or a validated
TCP endpoint) instead of spawning `docker` CLI subprocesses and scraping their stdout.

The service is the seam of the Docker engine edge (#1316). It resolves and checks the endpoint,
and then builds the one SDK client of the process with a `ClientFactory` (`devops_cli.docker.sdk`),
`docker.DockerClient` unless `DockerEngineService.install` gives it another, such as a fake.
"""

from __future__ import annotations

import logging
import os
import struct
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import quote, urlsplit

from devops_cli.config.constants import (
    CONST_DOCKER_BUILD_CACHE_TYPES,
    CONST_DOCKER_DEFAULT_UNIX_SOCKET,
    CONST_DOCKER_DF_BUILD_CACHE_KEY,
    CONST_DOCKER_UNIX_ADAPTER_SCHEME,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_PODMAN_ENGINE_COMPONENT_NAME,
    CONST_PODMAN_ROOTFUL_SOCKET_PATH,
    CONST_PODMAN_SOCKET_RELATIVE_PATH,
    CONST_RUN_USER_BASE,
    CONST_SECURITY_OPT_ROOTLESS,
)
from devops_cli.config.defaults import (
    DEFAULT_DOCKER_CACHE_TTL_SECONDS,
    DEFAULT_DOCKER_FAILURE_CACHE_TTL_SECONDS,
    DEFAULT_DOCKER_PING_TIMEOUT_SECONDS,
    DEFAULT_DOCKER_STOP_TIMEOUT_SECONDS,
    DEFAULT_DOCKER_TIMEOUT_SECONDS,
)
from devops_cli.exceptions.docker import (
    DockerDaemonUnavailableError,
    DockerEngineError,
    DockerError,
)
from devops_cli.models.docker import (
    BuildCacheRecord,
    BuildCacheReport,
    ContainerState,
    ContainerStatEntry,
    DockerEndpoint,
    EngineSecurityInfo,
)

if TYPE_CHECKING:
    from devops_cli.docker.sdk import ClientFactory, EngineClient, EngineContainer, EngineImage

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


# The header of each frame of the Engine API's multiplexed stream: the stream (1 is stdout, 2 is
# stderr), three zero bytes, and the length of the frame's bytes ("Stream format" of the Engine
# API reference). A container with a TTY sends its output with no headers.
_LOG_FRAME_HEADER = struct.Struct(">BxxxL")


def container_log_frames(
    client: EngineClient,
    container: EngineContainer,
    *,
    tail: int | str = "all",
    timestamps: bool = False,
    follow: bool = False,
) -> Iterator[tuple[bytes | None, bytes | None]]:
    """Read a container's log as `(stdout, stderr)` frames, each with the bytes of one stream.

    The docker SDK's `logs` drops the stream of each frame, so the request goes through the SDK
    client's own session (`client.api`) with the query that `logs` sends. The request is sent
    before this returns, so a refused one raises the SDK's error here; the frames come from a
    generator that closes the reply when it ends. A followed log has no read timeout, as the SDK's
    own followed log has none.
    """
    from docker.errors import create_api_error_from_http_exception  # type: ignore[import-untyped]
    from requests.exceptions import HTTPError

    api = client.api
    response = api.get(
        f"{api.base_url}/v{api.api_version}/containers/{quote(container.id, safe='')}/logs",
        params={
            "stdout": 1,
            "stderr": 1,
            "timestamps": int(timestamps),
            "follow": int(follow),
            "tail": tail if tail == "all" or (isinstance(tail, int) and tail >= 0) else "all",
        },
        stream=True,
        timeout=(api.timeout, None) if follow else api.timeout,
    )
    try:
        response.raise_for_status()
    except HTTPError as exc:
        response.close()
        raise create_api_error_from_http_exception(exc) from exc
    return _log_frames(response, tty=bool(_section(container.attrs, "Config").get("Tty")))


def _log_frames(response: Any, *, tty: bool) -> Iterator[tuple[bytes | None, bytes | None]]:
    """The frames of a log reply; with a TTY, each chunk of the one raw stream is stdout."""
    from docker.utils.socket import demux_adaptor  # type: ignore[import-untyped]

    try:
        if tty:
            for chunk in response.iter_content(chunk_size=None):
                yield chunk, None
            return
        while header := response.raw.read(_LOG_FRAME_HEADER.size):
            stream, length = _LOG_FRAME_HEADER.unpack(header)
            if length:
                yield demux_adaptor(stream, response.raw.read(length))
    finally:
        response.close()


def _podman_rootless_socket_path() -> Path:
    """Derive the rootless Podman socket path from XDG_RUNTIME_DIR or the /run/user base."""
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        return Path(xdg) / CONST_PODMAN_SOCKET_RELATIVE_PATH
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    return CONST_RUN_USER_BASE / str(uid) / CONST_PODMAN_SOCKET_RELATIVE_PATH


def _find_podman_socket() -> Path | None:
    """Locate active rootless or rootful Podman socket, rootless taking precedence."""
    rootless = _podman_rootless_socket_path()
    if rootless.exists():
        return rootless
    rootful = CONST_PODMAN_ROOTFUL_SOCKET_PATH
    if rootful.exists() and os.access(rootful, os.R_OK | os.W_OK):
        return rootful
    return None


def _check_container_connection() -> None:
    """Raise configuration error if CONTAINER_CONNECTION is set."""
    if "CONTAINER_CONNECTION" in os.environ:
        raise DockerDaemonUnavailableError(
            "CONTAINER_CONNECTION: named connections are not supported; set CONTAINER_HOST instead",
            host="CONTAINER_CONNECTION",
        )


def _sdk_client(**params: Any) -> EngineClient:
    """Build the docker SDK client of an endpoint; it reads `GET /version` before it returns."""
    import docker  # type: ignore[import-untyped]

    client: EngineClient = docker.DockerClient(**params)
    return client


def _with_tls(env_tls: Any) -> dict[str, Any]:
    """Return dict with tls key if env_tls is provided."""
    return {"tls": env_tls} if env_tls is not None else {}


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

    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self._client_factory: ClientFactory = client_factory or _sdk_client
        self._client: EngineClient | None = None
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
    def install(cls, client_factory: ClientFactory) -> DockerEngineService:
        """Make a service that builds its SDK client with `client_factory` the process-wide one.

        The service still resolves and checks the endpoint first, and gives the factory the same
        keyword arguments as `docker.DockerClient`. `reset_instance` returns to the SDK's client.
        """
        cls.reset_instance()
        service = cls(client_factory)
        cls._instance = service
        return service

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton for clean test fixture isolation."""
        if cls._instance is not None:
            cls._instance.close()
        cls._instance = None

    # -- Connection lifecycle -------------------------------------------------

    @staticmethod
    def _context_endpoint(name: str, env_tls: Any) -> tuple[str, str, dict[str, Any]]:
        """Retrieve endpoint definition and TLS config for a named Docker context."""
        from docker import ContextAPI

        ctx = ContextAPI.get_context(name)
        if ctx is None:
            raise DockerDaemonUnavailableError(f'context "{name}": context not found', host=name)
        params: dict[str, Any] = {}
        tls = env_tls or ctx.TLSConfig
        if tls is not None:
            params["tls"] = tls
        return name, str(ctx.Host or ""), params

    @classmethod
    def _gather_endpoint(cls) -> tuple[str, str, dict[str, Any]]:
        """Gather the endpoint from the first winning source in priority order."""
        import docker.utils  # type: ignore[import-untyped]
        from docker import ContextAPI
        from docker.context.api import get_current_context_name  # type: ignore[import-untyped]

        _check_container_connection()

        env_params = docker.utils.kwargs_from_env(environment=os.environ)
        env_tls = env_params.get("tls")

        # 1. CONTAINER_HOST from environment
        container_host = os.environ.get("CONTAINER_HOST")
        if container_host is not None:
            return "CONTAINER_HOST", str(container_host), _with_tls(env_tls)

        # 2. DOCKER_HOST from kwargs_from_env
        if "base_url" in env_params:
            return "DOCKER_HOST", str(env_params["base_url"]), _with_tls(env_tls)

        # 3. DOCKER_CONTEXT from environment
        docker_context = os.environ.get("DOCKER_CONTEXT")
        if docker_context:
            source, raw, params = cls._context_endpoint(docker_context, env_tls)
            if docker_context == "default":
                source = CONST_DOCKER_DEFAULT_UNIX_SOCKET
            return source, raw, params

        # 4. currentContext in config.json when not "default"
        current_name = get_current_context_name()
        if current_name != "default":
            return cls._context_endpoint(current_name, env_tls)

        # 5. Podman user/rootful sockets
        podman_sock = _find_podman_socket()
        if podman_sock is not None:
            return str(podman_sock), f"unix://{podman_sock}", _with_tls(env_tls)

        # 6. Default context
        ctx = ContextAPI.DEFAULT_CONTEXT
        tls = env_tls or ctx.TLSConfig
        return (
            CONST_DOCKER_DEFAULT_UNIX_SOCKET,
            str(ctx.Host or f"unix://{CONST_DOCKER_DEFAULT_UNIX_SOCKET}"),
            _with_tls(tls),
        )

    @staticmethod
    def _parse_endpoint(source: str, raw: str, params: dict[str, Any]) -> str:
        """Normalise the raw daemon endpoint via docker-py's parse_host."""
        import docker.constants  # type: ignore[import-untyped]
        import docker.utils
        from docker.errors import DockerException

        try:
            return str(
                docker.utils.parse_host(
                    raw,
                    docker.constants.IS_WINDOWS_PLATFORM,
                    tls=bool(params.get("tls")),
                )
            )
        except (DockerException, ValueError) as exc:
            raise DockerDaemonUnavailableError(f"{source}: {exc}", host=source) from exc

    @staticmethod
    def _check_endpoint_egress(source: str, base_url: str) -> None:
        """Validate network endpoints against SSRF policies."""
        from devops_cli.config.settings import load_settings
        from devops_cli.core.validation import validate_service_url
        from devops_cli.exceptions import InvalidURLError, SSRFBlockedError

        scheme = urlsplit(base_url).scheme.lower()
        if scheme in ("http", "https"):
            settings = load_settings()
            try:
                validate_service_url(
                    base_url, "Docker Host", allow=settings.ai.allow_private_network
                )
            except (SSRFBlockedError, InvalidURLError) as exc:
                raise DockerDaemonUnavailableError(f"{source}: {exc}", host=source) from exc

    def resolve_host(self) -> DockerEndpoint:
        """Resolve the effective daemon endpoint, validating network hosts against SSRF.

        This pre-flight check inspects the chosen endpoint before docker-py's dialler
        (requests/urllib3) connects. Note that for endpoints given by hostname rather
        than IP literal, the host's resolved IP address can change between this check's
        DNS lookup and the subsequent dial.
        """
        source, raw, params = self._gather_endpoint()
        base_url = self._parse_endpoint(source, raw, params)
        self._check_endpoint_egress(source, base_url)
        params["base_url"] = base_url
        return DockerEndpoint(
            source=source,
            raw=raw,
            base_url=base_url,
            params=params,
        )

    def unix_socket_path(self) -> Path | None:
        """Return the unix socket path of the resolved endpoint, or None for a network host.

        docker-py's own `parse_host` and `UnixHTTPAdapter` derive the path from that endpoint.
        Nothing connects and no request is made, so a dry run may call this.
        """
        from docker.transport import UnixHTTPAdapter  # type: ignore[import-untyped]

        source, raw, params = self._gather_endpoint()
        base_url = self._parse_endpoint(source, raw, params)
        if urlsplit(base_url).scheme != CONST_DOCKER_UNIX_ADAPTER_SCHEME:
            return None
        return Path(UnixHTTPAdapter(base_url).socket_path)

    def client(self) -> EngineClient:
        """Return the cached Engine API client, negotiating the daemon socket on first use."""
        if self._client is not None:
            return self._client

        endpoint = self.resolve_host()
        try:
            client = self._client_factory(
                timeout=int(DEFAULT_DOCKER_TIMEOUT_SECONDS),
                **endpoint.params,
            )
        except Exception as exc:
            msg = f"{endpoint.source}: {exc}"
            if endpoint.source == CONST_DOCKER_DEFAULT_UNIX_SOCKET:
                msg = (
                    f"{msg}; set CONTAINER_HOST or DOCKER_HOST, "
                    "or run systemctl --user enable --now podman.socket"
                )
            raise DockerDaemonUnavailableError(msg, host=endpoint.source) from exc

        self._client = client
        self._host = endpoint.base_url
        return client

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
        self._set_cached(
            "ping",
            reachable,
            ttl=self._cache_ttl if reachable else DEFAULT_DOCKER_FAILURE_CACHE_TTL_SECONDS,
        )
        return reachable

    # -- Engine facts & security introspection --------------------------------

    def security_info(self) -> EngineSecurityInfo:
        """Report the daemon's security facts from one cached info() call.

        A daemon that cannot answer, because the socket, the SDK or the engine failed, does not
        raise: the answer carries the reason and is remembered briefly, so the facts and the
        reason for their absence are one answer.
        """
        from docker.errors import DockerException

        cached: EngineSecurityInfo | None = self._get_cached("security_info")
        if cached is not None:
            return cached
        try:
            info = self.client().info() or {}
            options, pids_limit = info.get("SecurityOptions"), info.get("PidsLimit")
            report = EngineSecurityInfo(
                options=None if options is None else tuple(str(opt) for opt in options),
                pids_limit_supported=None if pids_limit is None else bool(pids_limit),
            )
        except (DockerError, DockerException, OSError) as exc:
            logger.debug("Failed retrieving engine security info: %s", exc)
            report = EngineSecurityInfo(error=str(exc)[:CONST_MAX_ERROR_DETAIL_LENGTH])
        failed = report.error is not None
        self._set_cached(
            "security_info",
            report,
            ttl=DEFAULT_DOCKER_FAILURE_CACHE_TTL_SECONDS if failed else self._cache_ttl,
        )
        return report

    def security_options(self) -> list[str]:
        """Return the security options reported by the daemon info endpoint."""
        return list(self.security_info().options or ())

    def is_rootless(self) -> bool:
        """Report whether the underlying engine runs in rootless mode."""
        return CONST_SECURITY_OPT_ROOTLESS in self.security_options()

    def kind(self) -> str:
        """Report engine kind ('Podman' or 'Docker')."""
        cached = self._get_cached("engine_kind")
        if cached is not None:
            return str(cached)
        try:
            version_data = self.client().version() or {}
            components = version_data.get("Components") or []
            is_podman = any(
                comp.get("Name") == CONST_PODMAN_ENGINE_COMPONENT_NAME
                for comp in components
                if isinstance(comp, dict)
            )
            result = "Podman" if is_podman else "Docker"
        except (DockerError, OSError) as exc:
            logger.debug("Failed retrieving engine version components: %s", exc)
            result = "Docker"
        self._set_cached("engine_kind", result)
        return result

    def is_podman(self) -> bool:
        """Report whether the connected daemon is a Podman engine."""
        return self.kind() == "Podman"

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

    def get_container(self, container_id: str) -> EngineContainer:
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
        name = getattr(container, "name", "") or container_id
        try:
            stream = container.stats(stream=True, decode=True)
            if isinstance(stream, dict):
                second_frame = stream
            else:
                iterator = iter(stream)
                next(iterator, None)
                second_frame = next(iterator, {})
                close_fn = getattr(stream, "close", None)
                if callable(close_fn):
                    close_fn()
        except Exception as exc:
            raise DockerEngineError(
                f"Container stats capture failed: {exc}", container_id=container_id
            ) from exc
        return project_container_stats(container_id, name, second_frame or {})

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
        iterator = iter(stream)
        next(iterator, None)
        yielded = 0
        for frame in iterator:
            if samples is not None and yielded >= samples:
                close_fn = getattr(stream, "close", None)
                if callable(close_fn):
                    close_fn()
                return
            yielded += 1
            yield project_container_stats(container_id, name, frame or {})

    # -- Container lifecycle --------------------------------------------------

    def create_container(self, **create_kwargs: Any) -> EngineContainer:
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
        self,
        container_id: str,
        command: list[str],
        *,
        workdir: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        """Execute a command inside a running container and return its status and output.

        `environment` is added to the container's own for this command only.
        """
        container = self.get_container(container_id)
        try:
            exit_code, output = container.exec_run(
                command, workdir=workdir, environment=environment
            )
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
    ) -> Iterator[tuple[bytes | None, bytes | None]]:
        """Open a container's log as `(stdout, stderr)` frames, in the order the engine sent them."""
        container = self.get_container(container_id)
        try:
            return container_log_frames(
                self.client(), container, tail=tail, timestamps=timestamps, follow=follow
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

    def list_images(self, *, name: str | None = None) -> list[EngineImage]:
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

    def prune(self, *, volumes: bool = False) -> int:
        """Reclaim stopped containers, unused networks, dangling images, and optionally volumes."""
        try:
            client = self.client()
            reclaimed = _extract_reclaimed_bytes(client.containers.prune())
            reclaimed += _extract_reclaimed_bytes(client.networks.prune())
            reclaimed += _extract_reclaimed_bytes(client.images.prune())
            if volumes:
                reclaimed += _extract_reclaimed_bytes(client.volumes.prune())
        except DockerEngineError:
            raise
        except Exception as exc:
            raise DockerEngineError(f"Docker prune failed: {exc}") from exc
        self._cache.pop("disk_usage", None)
        return reclaimed


def _extract_reclaimed_bytes(reply: Any) -> int:
    """Extract SpaceReclaimed integer bytes from a daemon prune response dictionary."""
    if isinstance(reply, dict):
        space = reply.get("SpaceReclaimed")
        if isinstance(space, (int, float)):
            return int(space)
    return 0


def get_engine() -> DockerEngineService:
    """Return the process-wide Docker Engine API service singleton."""
    return DockerEngineService.get_instance()


__all__ = [
    "DockerEngineService",
    "build_cache_report",
    "container_log_frames",
    "decode_stream",
    "get_engine",
    "project_container_state",
    "project_container_stats",
]
