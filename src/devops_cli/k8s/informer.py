"""Kubernetes Informer and event streaming watcher architecture."""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

from tenacity import Retrying, wait_exponential

from devops_cli.config.constants import (
    CONST_K8S_EVENT_DELETED,
    CONST_K8S_EVENT_MODIFIED,
    CONST_K8S_INFORMER_EVENTS,
)
from devops_cli.config.defaults import (
    DEFAULT_K8S_INFORMER_BACKOFF_MAX_SECONDS,
    DEFAULT_K8S_INFORMER_BACKOFF_MIN_SECONDS,
    DEFAULT_K8S_INFORMER_CACHE_MAX_ENTRIES,
    DEFAULT_K8S_INFORMER_RESYNC_SECONDS,
    DEFAULT_K8S_INFORMER_STOP_TIMEOUT_SECONDS,
    DEFAULT_K8S_STREAM_TIMEOUT_SECONDS,
)
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.service import KubernetesService
from devops_cli.models.k8s import K8sEvent, K8sInformerState, PodInfo

logger = logging.getLogger(__name__)


def _extract_event_metadata(obj: Any, default_namespace: str) -> tuple[str, str, str]:
    """Extract (name, namespace, status) from a Kubernetes object or dictionary.

    The watch lists pods, so an object's status is the one `kubectl get pods` prints: the
    phase alone reads Running for a pod whose container is crashlooping.
    """
    if isinstance(obj, dict):
        d_meta = obj.get("metadata")
        d_status = obj.get("status")
        name = str(d_meta.get("name") if isinstance(d_meta, dict) else "unknown")
        namespace = str(
            (d_meta.get("namespace") if isinstance(d_meta, dict) else None) or default_namespace
        )
        status = str((d_status.get("phase") if isinstance(d_status, dict) else None) or "Active")
        return name, namespace, status

    meta = getattr(obj, "metadata", None)
    name = str(getattr(meta, "name", "unknown") or "unknown")
    namespace = str(getattr(meta, "namespace", default_namespace) or default_namespace)
    return name, namespace, PodInfo.from_pod(obj).status


class ResourceInformer:
    """Watch-based resource informer maintaining in-memory cache of cluster objects."""

    def __init__(
        self,
        resource_kind: str = "Pod",
        namespace: str = "default",
        label_selector: str | None = None,
        service: KubernetesService | None = None,
    ) -> None:
        self.resource_kind = resource_kind
        self.namespace = namespace
        self.label_selector = label_selector
        self._service = service or KubernetesService.get_instance()
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._running: bool = False
        self._watcher: Any = None
        self._watch_thread: threading.Thread | None = None
        self._last_event_time: str | None = None
        self._synced: bool = False
        self._resource_version: str | None = None
        self._stop_event = threading.Event()

    def get_state(self) -> K8sInformerState:
        """Return snapshot summary of informer state."""
        with self._lock:
            return K8sInformerState(
                resource_kind=self.resource_kind,
                namespace=self.namespace,
                resource_count=len(self._cache),
                synced=self._synced,
                last_event_time=self._last_event_time,
            )

    def get_cached_resources(self) -> dict[str, Any]:
        """Return a copy of current in-memory resource cache."""
        with self._lock:
            return dict(self._cache)

    def stream_events(
        self,
        timeout_seconds: float = DEFAULT_K8S_STREAM_TIMEOUT_SECONDS,
        resource_version: str | None = None,
    ) -> Iterator[K8sEvent]:
        """Yield real-time cluster events over a Watch stream without polling."""
        from kubernetes import watch  # type: ignore[import-untyped]

        if not self._service.load_config():
            raise KubernetesContextError("Kubernetes client is not configured.")

        core_v1 = self._service.core_api()
        w = watch.Watch()
        # Publish the watcher so stop() can interrupt the blocking stream immediately
        # instead of waiting out the server-side resync timeout.
        self._watcher = w
        kwargs: dict[str, Any] = {"timeout_seconds": int(timeout_seconds)}
        if self.label_selector:
            kwargs["label_selector"] = self.label_selector
        effective_rv = resource_version if resource_version is not None else self._resource_version
        if effective_rv is not None:
            kwargs["resource_version"] = effective_rv

        stream = (
            w.stream(core_v1.list_pod_for_all_namespaces, **kwargs)
            if self.namespace == "" or self.namespace == "*"
            else w.stream(core_v1.list_namespaced_pod, namespace=self.namespace, **kwargs)
        )

        try:
            for raw_event in stream:
                obj = raw_event.get("object")
                if raw_event.get("type") == "ERROR":
                    code = getattr(obj, "code", None)
                    if not code and isinstance(obj, dict):
                        code = obj.get("code")
                    if code == 410 or str(code) == "410":
                        from kubernetes.client.rest import (  # type: ignore[import-untyped]
                            ApiException,
                        )

                        raise ApiException(status=410, reason="Gone")
                self._record_resource_version(raw_event, w)
                event = self._normalize_event(raw_event)
                self._update_cache(event, obj)
                yield event
        finally:
            self._watcher = None

    def _record_resource_version(self, raw_event: dict[str, Any], watcher: Any) -> None:
        """Record the latest observed resourceVersion from event or watcher."""
        obj = raw_event.get("object")
        meta = getattr(obj, "metadata", None)
        rv = getattr(meta, "resource_version", None)
        if not rv and isinstance(obj, dict):
            m = obj.get("metadata", {})
            rv = m.get("resourceVersion") or m.get("resource_version")
        if not rv:
            raw_obj = raw_event.get("raw_object")
            if isinstance(raw_obj, dict):
                m = raw_obj.get("metadata", {})
                rv = m.get("resourceVersion") or m.get("resource_version")
        if not rv and watcher is not None:
            rv = getattr(watcher, "resource_version", None)
        if rv:
            self._resource_version = str(rv)

    def start(self, on_event: Callable[[K8sEvent], None] | None = None) -> None:
        """Start informer background watcher thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._watch_thread = threading.Thread(
            target=self._run_watch_loop,
            args=(on_event,),
            daemon=True,
            name=f"k8s-informer-{self.resource_kind.lower()}-{self.namespace}",
        )
        self._watch_thread.start()

    def stop(self, timeout: float = DEFAULT_K8S_INFORMER_STOP_TIMEOUT_SECONDS) -> None:
        """Stop the informer, interrupting the watch stream and joining the worker thread."""
        self._running = False
        self._stop_event.set()
        watcher = self._watcher
        if watcher is not None:
            try:
                watcher.stop()
            except Exception as exc:
                logger.debug("Failed to stop watcher: %s", exc)

        thread, self._watch_thread = self._watch_thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.debug(
                    "Informer thread %s did not exit within %.1fs of stop()", thread.name, timeout
                )

    def _sleep_with_stop(self, duration: float) -> None:
        """Wait for the specified duration or until stop is signaled."""
        self._stop_event.wait(duration)

    def _fetch_pod_list(self) -> Any:
        """Fetch list of pods from the Kubernetes API server."""
        core_v1 = self._service.core_api()
        kwargs: dict[str, Any] = {}
        if self.label_selector:
            kwargs["label_selector"] = self.label_selector
        if self.namespace in ("", "*"):
            return core_v1.list_pod_for_all_namespaces(**kwargs)
        return core_v1.list_namespaced_pod(namespace=self.namespace, **kwargs)

    def _extract_list_resource_version(self, pod_list: Any) -> str | None:
        """Extract resource version from pod list metadata."""
        meta = getattr(pod_list, "metadata", None)
        rv = getattr(meta, "resource_version", None)
        if not rv and isinstance(meta, dict):
            rv = meta.get("resourceVersion") or meta.get("resource_version")
        if not rv:
            rv = getattr(pod_list, "resource_version", None)
        return str(rv) if rv else None

    def _relist(self) -> None:
        """Fetch full resource list to synchronize cache after expired watch bookmark."""
        if not self._service.load_config():
            return
        pod_list = self._fetch_pod_list()
        rv = self._extract_list_resource_version(pod_list)
        if rv:
            self._resource_version = rv

        items = getattr(pod_list, "items", None) or []
        with self._lock:
            self._cache.clear()
            for pod in items:
                name, namespace, _ = _extract_event_metadata(pod, self.namespace)
                key = f"{namespace}/{name}"
                self._cache[key] = pod
                while len(self._cache) > DEFAULT_K8S_INFORMER_CACHE_MAX_ENTRIES:
                    self._cache.popitem(last=False)
            self._synced = True

    def _stream_once(self, on_event: Callable[[K8sEvent], None] | None) -> None:
        """Consume one watch stream until closed or interrupted."""
        for event in self.stream_events(
            timeout_seconds=DEFAULT_K8S_INFORMER_RESYNC_SECONDS,
            resource_version=self._resource_version,
        ):
            if not self._running:
                break
            if on_event is not None:
                on_event(event)

    def _handle_watch_error(self, exc: Exception) -> None:
        """Handle error from the watch stream and relist on 410 Gone."""
        logger.debug("Informer watch stream encountered exception: %s", exc)
        if getattr(exc, "status", None) == 410:
            self._relist()

    def _run_retry_cycle(self, on_event: Callable[[K8sEvent], None] | None) -> None:
        """Run watch stream attempt cycle with exponential backoff."""
        for attempt in Retrying(
            wait=wait_exponential(
                multiplier=1,
                min=DEFAULT_K8S_INFORMER_BACKOFF_MIN_SECONDS,
                max=DEFAULT_K8S_INFORMER_BACKOFF_MAX_SECONDS,
            ),
            sleep=self._sleep_with_stop,
            reraise=True,
        ):
            with attempt:
                if not self._running:
                    return
                try:
                    self._stream_once(on_event)
                except Exception as exc:
                    self._handle_watch_error(exc)
                    if not self._running:
                        return
                    raise

    def _run_watch_loop(self, on_event: Callable[[K8sEvent], None] | None) -> None:
        """Internal background loop reconnecting watch streams on timeout or failure."""
        while self._running:
            try:
                self._run_retry_cycle(on_event)
            except Exception as exc:
                logger.debug("Informer watch loop retries interrupted: %s", exc)
                if not self._running:
                    break

    def _normalize_event(self, raw: dict[str, Any]) -> K8sEvent:
        """Transform raw Watch event into normalized K8sEvent model."""
        event_type = raw.get("type", CONST_K8S_EVENT_MODIFIED)
        if event_type not in CONST_K8S_INFORMER_EVENTS:
            event_type = CONST_K8S_EVENT_MODIFIED

        obj = raw.get("object")
        name, namespace, status = _extract_event_metadata(obj, self.namespace)

        timestamp = datetime.now(UTC).isoformat()
        self._last_event_time = timestamp

        return K8sEvent(
            event_type=event_type,
            resource_kind=self.resource_kind,
            name=name,
            namespace=namespace,
            status=status,
            timestamp=timestamp,
        )

    def _update_cache(self, event: K8sEvent, obj: Any) -> None:
        """Update the in-memory resource map, evicting oldest entries beyond the cache cap."""
        with self._lock:
            key = f"{event.namespace}/{event.name}"
            if event.event_type == CONST_K8S_EVENT_DELETED:
                self._cache.pop(key, None)
            elif obj is not None:
                # Re-insert so the mapping stays ordered oldest-first for FIFO eviction.
                self._cache.pop(key, None)
                self._cache[key] = obj
                while len(self._cache) > DEFAULT_K8S_INFORMER_CACHE_MAX_ENTRIES:
                    evicted, _ = self._cache.popitem(last=False)
                    logger.debug("Informer cache at capacity; evicted oldest entry %s", evicted)
            self._synced = True
