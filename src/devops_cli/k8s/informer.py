"""Kubernetes Informer and event streaming watcher architecture."""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

from devops_cli.config.constants import (
    CONST_K8S_EVENT_DELETED,
    CONST_K8S_EVENT_MODIFIED,
    CONST_K8S_INFORMER_EVENTS,
)
from devops_cli.config.defaults import (
    DEFAULT_K8S_INFORMER_CACHE_MAX_ENTRIES,
    DEFAULT_K8S_INFORMER_RESYNC_SECONDS,
    DEFAULT_K8S_INFORMER_STOP_TIMEOUT_SECONDS,
    DEFAULT_K8S_STREAM_TIMEOUT_SECONDS,
)
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.service import KubernetesService
from devops_cli.models.k8s import K8sEvent, K8sInformerState

logger = logging.getLogger(__name__)


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
    ) -> Iterator[K8sEvent]:
        """Yield real-time cluster events over a Watch stream without polling."""
        from kubernetes import watch  # type: ignore[import-untyped]

        if not self._service.load_config():
            raise KubernetesContextError("Kubernetes client is not configured.")

        core_v1 = self._service._core_v1
        w = watch.Watch()
        # Publish the watcher so stop() can interrupt the blocking stream immediately
        # instead of waiting out the server-side resync timeout.
        self._watcher = w
        kwargs: dict[str, Any] = {"timeout_seconds": int(timeout_seconds)}
        if self.label_selector:
            kwargs["label_selector"] = self.label_selector

        target_fn = (
            core_v1.list_pod_for_all_namespaces
            if self.namespace == "" or self.namespace == "*"
            else lambda **kw: core_v1.list_namespaced_pod(namespace=self.namespace, **kw)
        )

        try:
            for raw_event in w.stream(target_fn, **kwargs):
                event = self._normalize_event(raw_event)
                self._update_cache(event, raw_event.get("object"))
                yield event
        finally:
            self._watcher = None

    def start(self, on_event: Callable[[K8sEvent], None] | None = None) -> None:
        """Start informer background watcher thread."""
        if self._running:
            return
        self._running = True
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

    def _run_watch_loop(self, on_event: Callable[[K8sEvent], None] | None) -> None:
        """Internal background loop reconnecting watch streams on timeout."""
        while self._running:
            try:
                for event in self.stream_events(
                    timeout_seconds=DEFAULT_K8S_INFORMER_RESYNC_SECONDS
                ):
                    if not self._running:
                        break
                    if on_event:
                        on_event(event)
            except Exception as exc:
                logger.debug("Informer watch stream encountered exception: %s", exc)
                if not self._running:
                    break

    def _normalize_event(self, raw: dict[str, Any]) -> K8sEvent:
        """Transform raw Watch event into normalized K8sEvent model."""
        event_type = raw.get("type", CONST_K8S_EVENT_MODIFIED)
        if event_type not in CONST_K8S_INFORMER_EVENTS:
            event_type = CONST_K8S_EVENT_MODIFIED

        obj = raw.get("object")
        name = getattr(getattr(obj, "metadata", None), "name", "unknown")
        namespace = getattr(getattr(obj, "metadata", None), "namespace", self.namespace)
        status = getattr(getattr(obj, "status", None), "phase", "Active")

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
