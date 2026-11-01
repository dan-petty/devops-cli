"""Consolidated native Kubernetes service layer eliminating subprocess overhead."""

from __future__ import annotations

import codecs
import contextlib
import logging
import time
from collections.abc import Iterator
from typing import Any, Literal

from devops_cli.config.defaults import (
    DEFAULT_K8S_CACHE_TTL_SECONDS,
    DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_LOG_MAX_LINE_CHARS,
    DEFAULT_LOG_TAIL_LINES,
)
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.api import (
    CoreApi,
    CustomObjectsApi,
    KubernetesApis,
    KubernetesApiSource,
    KubernetesClientSource,
    api_error_type,
)
from devops_cli.k8s.context import resolve_context
from devops_cli.security.sanitizer import mask_secrets

logger = logging.getLogger(__name__)

_VersionProbe = Literal["ok", "refused", "down"]


def _extract_line(buffer: str, max_line_chars: int) -> tuple[str | None, str]:
    """Extract one line if a newline or length boundary is met."""
    idx = buffer.find("\n")
    if 0 <= idx <= max_line_chars:
        return buffer[:idx], buffer[idx + 1 :]
    if idx > max_line_chars or len(buffer) > max_line_chars:
        return buffer[:max_line_chars], buffer[max_line_chars:]
    return None, buffer


def _flush_buffer(buffer: str, max_line_chars: int) -> Iterator[str]:
    """Yield remaining buffer sliced to max_line_chars."""
    while len(buffer) > max_line_chars:
        yield buffer[:max_line_chars]
        buffer = buffer[max_line_chars:]
    if buffer:
        yield buffer


class PodLogStream:
    """A followed pod log: its lines as they arrive, and `close` to stop reading them.

    A followed read blocks until the container writes again, which for a quiet container
    may be never. `close` may be called from any thread: it shuts the socket for reading,
    which ends a blocked read at once, and the reader then closes the response and returns
    its connection, as the client's own watch does.
    """

    def __init__(self, response: Any, max_line_chars: int = DEFAULT_LOG_MAX_LINE_CHARS) -> None:
        self._response = response
        self._max_line_chars = max_line_chars

    def __iter__(self) -> Iterator[str]:
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        buffer = ""
        try:
            for chunk in self._response.stream():
                text = (
                    decoder.decode(chunk, final=False) if isinstance(chunk, bytes) else str(chunk)
                )
                buffer += text
                while True:
                    line, buffer = _extract_line(buffer, self._max_line_chars)
                    if line is None:
                        break
                    yield line
            buffer += decoder.decode(b"", final=True)
            yield from _flush_buffer(buffer, self._max_line_chars)
        finally:
            self._response.close()
            self._response.release_conn()

    def close(self) -> None:
        """Stop the read, from any thread.

        urllib3 refuses to shut the socket once the stream has ended and the response is
        closed, when there is nothing left to stop.
        """
        with contextlib.suppress(OSError, RuntimeError, ValueError):
            self._response.shutdown()


def read_pod_log_text(
    core: CoreApi, name: str, namespace: str, *, tail_lines: int, **kwargs: Any
) -> str:
    """The tail of the log of pod `name` as the text that the pod wrote: UTF-8, with a byte that
    is not UTF-8 replaced, and with its real line breaks.

    A plain `read_namespaced_pod_log` cannot give this. The response type of the call is `str`,
    so the client skips the decode of the body and ends in `str(bytes)`: the log arrives as the
    text `b'...\\n...'`, and a log that is valid JSON arrives as the repr of a Python value
    (`kubernetes` 36.0.3). The call here asks for the raw response, reads its bytes and decodes
    them one time. `kwargs` go to the call, for example `_request_timeout`. An API error is not
    caught: the caller names it.
    """
    response = core.read_namespaced_pod_log(
        name, namespace, tail_lines=tail_lines, _preload_content=False, **kwargs
    )
    try:
        raw = b"".join(response.stream())
    finally:
        response.close()
        response.release_conn()
    return raw.decode("utf-8", errors="replace")


def _first_node_address(nodes: list[Any]) -> str | None:
    """Return the first internal or external address of the nodes, in their order."""
    for node in nodes:
        for addr in node.status.addresses or []:
            if addr.type in ("InternalIP", "ExternalIP") and addr.address:
                return str(addr.address)
    return None


class KubernetesService:
    """The process's one way to the Kubernetes API, without kubectl subprocesses.

    It takes its API objects from a `KubernetesApiSource` (`k8s/api.py`): the official client in
    production, a test's fake cluster through `install`. It connects once for each resolved
    context and caches the API objects and some answers.
    """

    _instance: KubernetesService | None = None

    def __init__(self, source: KubernetesApiSource | None = None) -> None:
        self._source: KubernetesApiSource = source or KubernetesClientSource()
        self._apis: KubernetesApis | None = None
        self._active_context: str | None = None
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl: float = DEFAULT_K8S_CACHE_TTL_SECONDS

    @classmethod
    def get_instance(cls) -> KubernetesService:
        """Retrieve the singleton KubernetesService instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def install(cls, source: KubernetesApiSource) -> KubernetesService:
        """Make the process's service one that takes its API objects from `source`.

        It stays until `reset_instance`, after which `get_instance` builds a service over the
        official client again.
        """
        cls._instance = cls(source)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Drop the process's service, and with it a source that `install` gave it."""
        cls._instance = None

    def load_config(self, context: str | None = None) -> bool:
        """Connect to the resolved context, once, and report whether a connection exists."""
        # Resolved before the cache is consulted: an explicit argument and the configured
        # context must not be treated as different cache keys when they name the same
        # cluster, and a caller passing None must not be served a client built for
        # whatever context happened to be current earlier in the process.
        resolved = resolve_context(context)

        if self._apis is not None and self._active_context == resolved:
            return True

        try:
            self._apis = self._source.connect(resolved)
        except Exception as exc:
            logger.debug("Failed to initialize Kubernetes API client: %s", exc)
            self._apis = None
            return False
        self._active_context = resolved
        return True

    def _connected(self, context: str | None, failure: str) -> KubernetesApis:
        if not self.load_config(context=context) or self._apis is None:
            raise KubernetesContextError(failure, context=context)
        return self._apis

    def core_api(self, context: str | None = None) -> CoreApi:
        """Return the core API object of the resolved context, connecting first."""
        return self._connected(context, "Kubernetes client configuration is not available.").core

    def configuration(self, context: str | None = None) -> Any:
        """Return the client configuration of the resolved context, connecting first."""
        return self._connected(
            context, "Kubernetes client configuration is not available."
        ).configuration

    def custom_objects_api(self, context: str | None = None) -> CustomObjectsApi:
        """Return the CustomObjectsApi client used to manipulate CRDs in-process."""
        return self._connected(
            context, "Cannot reach the Kubernetes API server to manipulate custom resources"
        ).custom_objects

    def _probe_version(self, context: str | None, timeout: float) -> tuple[_VersionProbe, Any]:
        """Ask the API server of `context` for `/version`.

        "ok" with the version info; "refused" when the API server answered with an error status,
        such as 401 for a refused credential; "down" when no answer came.
        """
        if not self.load_config(context=context) or self._apis is None:
            return "down", None
        try:
            return "ok", self._apis.version.get_code(_request_timeout=timeout)
        except api_error_type():
            return "refused", None
        except Exception as exc:
            logger.debug("Cluster reachability probe failed: %s", exc)
            return "down", None

    def is_cluster_reachable(
        self,
        context: str | None = None,
        timeout: float = DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
    ) -> bool:
        """Probe cluster reachability directly via in-process API call without subprocesses."""
        cache_key = f"reachability:{context or 'default'}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return bool(cached)

        outcome, info = self._probe_version(context, timeout)
        if outcome != "ok":
            self._set_cached(cache_key, False, ttl=2.0)
            return False
        version_str = (
            getattr(info, "git_version", "")
            or (info.get("git_version") if isinstance(info, dict) else "")
            or ""
        )
        self._set_cached(cache_key, True, ttl=self._cache_ttl)
        if version_str:
            self._set_cached(
                f"server_version:{context or 'default'}",
                version_str,
                ttl=self._cache_ttl,
            )
        return True

    def api_server_answers(
        self,
        context: str | None = None,
        timeout: float = DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
    ) -> bool:
        """Whether the API server of `context` answers `GET /version` with any HTTP status.

        A 401 or a 403 counts: the request reached the API server, which refused the
        credential. A connection that fails or times out does not count. Nothing is cached, so
        each call asks again.
        """
        outcome, _ = self._probe_version(context, timeout)
        return outcome != "down"

    def server_version(
        self,
        context: str | None = None,
        timeout: float = DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
    ) -> str:
        """Return the Kubernetes control plane version string, caching the result."""
        cache_key = f"server_version:{context or 'default'}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return str(cached)

        if not self.is_cluster_reachable(context=context, timeout=timeout):
            return ""

        return str(self._get_cached(cache_key) or "")

    def list_contexts(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """List available contexts and identify the active one without spawning kubectl."""
        return self._source.contexts()

    def switch_context(self, name: str) -> None:
        """Point the in-process clients at the kubeconfig context `name`.

        `kubectl config use-context` owns the kubeconfig, so this writes no file: it checks that
        the kubeconfig names the context, drops the clients and the cached answers, and connects
        to the context.
        """
        contexts, _ = self.list_contexts()
        if name not in {ctx.get("name") for ctx in contexts}:
            raise KubernetesContextError(
                f"Context '{name}' does not exist in the kubeconfig.", context=name
            )
        self._apis = None
        self._active_context = None
        self._cache.clear()
        if not self.load_config(context=name):
            raise KubernetesContextError(f"Failed to connect to context '{name}'.", context=name)

    def list_nodes(self, context: str | None = None) -> list[Any]:
        """Fetch cluster node objects using native API client with caching."""
        cache_key = f"nodes:{context or 'default'}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return list(cached)

        core = self.core_api(context)
        try:
            node_list = core.list_node()
            items = list(node_list.items)
            self._set_cached(cache_key, items, ttl=self._cache_ttl)
            return items
        except Exception as exc:
            raise KubernetesContextError(
                f"Failed to query cluster nodes: {mask_secrets(str(exc))}"
            ) from exc

    def list_pods(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
        all_namespaces: bool = False,
        context: str | None = None,
    ) -> list[Any]:
        """Fetch pod objects using in-process API client without spawning kubectl."""
        core = self.core_api(context)
        kwargs: dict[str, Any] = {}
        if label_selector:
            kwargs["label_selector"] = label_selector

        try:
            if all_namespaces:
                pod_list = core.list_pod_for_all_namespaces(**kwargs)
            else:
                ns = namespace or "default"
                pod_list = core.list_namespaced_pod(namespace=ns, **kwargs)
            return list(pod_list.items)
        except Exception as exc:
            raise KubernetesContextError(f"Failed to query pods: {mask_secrets(str(exc))}") from exc

    def read_pod_logs(
        self,
        pod: str,
        namespace: str = "default",
        container: str | None = None,
        tail_lines: int = DEFAULT_LOG_TAIL_LINES,
        follow: bool = False,
        context: str | None = None,
    ) -> PodLogStream:
        """Read pod logs natively via CoreV1Api without spawning kubectl logs."""
        core = self.core_api(context)
        bounded_tail = max(1, min(tail_lines, 10000))
        kwargs: dict[str, Any] = {
            "name": pod,
            "namespace": namespace,
            "tail_lines": bounded_tail,
            "follow": follow,
            "_preload_content": False,
        }
        if container:
            kwargs["container"] = container

        try:
            resp = core.read_namespaced_pod_log(**kwargs)
            return PodLogStream(resp)
        except Exception as exc:
            raise KubernetesContextError(
                f"Failed to read pod logs for '{pod}': {mask_secrets(str(exc))}"
            ) from exc

    def resolve_service_endpoint(
        self,
        service: str,
        namespace: str = "default",
        context: str | None = None,
    ) -> str | None:
        """Resolve a service reachable endpoint natively from V1Service and node IPs."""
        if not self.load_config(context=context) or self._apis is None:
            return None

        try:
            svc = self._apis.core.read_namespaced_service(name=service, namespace=namespace)
            ingress = (
                svc.status.load_balancer.ingress
                if svc.status and svc.status.load_balancer
                else None
            )
            port = svc.spec.ports[0].port if svc.spec and svc.spec.ports else None
            node_port = svc.spec.ports[0].node_port if svc.spec and svc.spec.ports else None

            if ingress and port:
                lb_host = ingress[0].ip or ingress[0].hostname
                if lb_host:
                    import httpx2

                    return str(httpx2.URL(scheme="http", host=lb_host, port=int(port)))

            if node_port:
                address = _first_node_address(self.list_nodes(context=context))
                if address:
                    import httpx2

                    return str(httpx2.URL(scheme="http", host=address, port=int(node_port)))
        except Exception as exc:
            logger.debug("Failed to resolve service endpoint for %s: %s", service, exc)

        return None

    def _get_cached(self, key: str) -> Any | None:
        """Retrieve an unexpired value from the memory cache."""
        entry = self._cache.get(key)
        if not entry:
            return None
        expires_at, val = entry
        if time.time() < expires_at:
            return val
        self._cache.pop(key, None)
        return None

    def _set_cached(self, key: str, val: Any, ttl: float | None = None) -> None:
        """Store a value in the memory cache under its own expiry deadline.

        Callers pass a short `ttl` for negative results (such as a failed reachability
        probe) so they are retried promptly rather than pinned for the full cache TTL.
        """
        self._cache[key] = (time.time() + (self._cache_ttl if ttl is None else ttl), val)
