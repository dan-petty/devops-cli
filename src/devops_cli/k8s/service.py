"""Consolidated native Kubernetes service layer eliminating subprocess overhead."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from devops_cli.config.defaults import (
    DEFAULT_K8S_CACHE_TTL_SECONDS,
    DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_LOG_TAIL_LINES,
)
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.security.sanitizer import mask_secrets

logger = logging.getLogger(__name__)


class KubernetesService:
    """Consolidated, high-performance in-process Kubernetes API service.

    Eliminates kubectl subprocess invocations by interfacing directly with the
    official Python kubernetes SDK and caching API client instances and responses.
    """

    _instance: KubernetesService | None = None

    def __init__(self) -> None:
        self._config_loaded: bool = False
        self._active_context: str | None = None
        self._api_client: Any = None
        self._core_v1: Any = None
        self._apps_v1: Any = None
        self._version_api: Any = None
        self._custom_objects: Any = None
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl: float = DEFAULT_K8S_CACHE_TTL_SECONDS

    @classmethod
    def get_instance(cls) -> KubernetesService:
        """Retrieve the singleton KubernetesService instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance for clean test fixture isolation."""
        cls._instance = None

    def _get_kubeconfig_path(self) -> Path:
        """Resolve the effective kubeconfig path."""
        env_path = os.environ.get("KUBECONFIG")
        if env_path:
            first_path = env_path.split(os.pathsep)[0].strip()
            if first_path:
                return Path(first_path).expanduser().resolve()
        return (Path.home() / ".kube" / "config").resolve()

    def load_config(self, context: str | None = None) -> bool:
        """Load Kubernetes configuration into memory, handling in-cluster and local config."""
        from kubernetes import client as k8s_client  # type: ignore[import-untyped]
        from kubernetes import config as k8s_config

        if self._config_loaded and self._active_context == context and self._core_v1 is not None:
            return True

        try:
            try:
                k8s_config.load_incluster_config()
                logger.debug("Loaded in-cluster Kubernetes configuration")
            except Exception:
                k8s_config.load_kube_config(context=context)
                logger.debug("Loaded kubeconfig with context: %s", context)

            self._active_context = context
            self._api_client = k8s_client.ApiClient()
            self._core_v1 = k8s_client.CoreV1Api(self._api_client)
            self._apps_v1 = k8s_client.AppsV1Api(self._api_client)
            self._version_api = k8s_client.VersionApi(self._api_client)
            self._custom_objects = k8s_client.CustomObjectsApi(self._api_client)
            self._config_loaded = True
            return True
        except Exception as exc:
            logger.debug("Failed to initialize Kubernetes API client: %s", exc)
            self._config_loaded = False
            return False

    def custom_objects_api(self, context: str | None = None) -> Any:
        """Return the CustomObjectsApi client used to manipulate CRDs in-process."""
        if not self.load_config(context=context) or self._custom_objects is None:
            raise KubernetesContextError(
                "Cannot reach the Kubernetes API server to manipulate custom resources",
                context=context,
            )
        return self._custom_objects

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

        if not self.load_config(context=context):
            self._set_cached(cache_key, False, ttl=2.0)
            return False

        try:
            if self._version_api:
                self._version_api.get_code(_request_timeout=timeout)
                self._set_cached(cache_key, True, ttl=self._cache_ttl)
                return True
        except Exception as exc:
            logger.debug("Cluster reachability probe failed: %s", exc)

        self._set_cached(cache_key, False, ttl=2.0)
        return False

    def list_contexts(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """List available contexts and identify the active one without spawning kubectl."""
        from kubernetes import config as k8s_config

        try:
            contexts_raw, active_raw = k8s_config.list_kube_config_contexts()
            return list(contexts_raw or []), active_raw
        except Exception as exc:
            raise KubernetesContextError(
                f"Failed to inspect kubeconfig contexts: {mask_secrets(str(exc))}"
            ) from exc

    def switch_context(self, name: str) -> None:
        """Switch current kubeconfig context natively without spawning kubectl."""
        import yaml

        kubeconfig_path = self._get_kubeconfig_path()
        if not kubeconfig_path.exists():
            raise KubernetesContextError(f"Kubeconfig file not found at '{kubeconfig_path}'.")

        try:
            raw_text = kubeconfig_path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw_text) or {}
            contexts = [c.get("name") for c in data.get("contexts", []) if isinstance(c, dict)]
            if name not in contexts:
                raise KubernetesContextError(
                    f"Context '{name}' does not exist in '{kubeconfig_path}'."
                )

            data["current-context"] = name
            temp_path = kubeconfig_path.with_suffix(".tmp")
            temp_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            temp_path.replace(kubeconfig_path)

            self.reset_instance()
            self.load_config(context=name)
        except KubernetesContextError:
            raise
        except Exception as exc:
            raise KubernetesContextError(
                f"Failed to switch context to '{name}': {mask_secrets(str(exc))}"
            ) from exc

    def list_nodes(self, context: str | None = None) -> list[Any]:
        """Fetch cluster node objects using native API client with caching."""
        cache_key = f"nodes:{context or 'default'}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return list(cached)

        if not self.load_config(context=context):
            raise KubernetesContextError("Kubernetes client configuration is not available.")

        try:
            node_list = self._core_v1.list_node()
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
        if not self.load_config(context=context):
            raise KubernetesContextError("Kubernetes client configuration is not available.")

        kwargs: dict[str, Any] = {}
        if label_selector:
            kwargs["label_selector"] = label_selector

        try:
            if all_namespaces:
                pod_list = self._core_v1.list_pod_for_all_namespaces(**kwargs)
            else:
                ns = namespace or "default"
                pod_list = self._core_v1.list_namespaced_pod(namespace=ns, **kwargs)
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
    ) -> str | Iterator[str]:
        """Read pod logs natively via CoreV1Api without spawning kubectl logs."""
        if not self.load_config(context=context):
            raise KubernetesContextError("Kubernetes client configuration is not available.")

        bounded_tail = max(1, min(tail_lines, 10000))
        kwargs: dict[str, Any] = {
            "name": pod,
            "namespace": namespace,
            "tail_lines": bounded_tail,
            "follow": follow,
            "_preload_content": not follow,
        }
        if container:
            kwargs["container"] = container

        try:
            resp = self._core_v1.read_namespaced_pod_log(**kwargs)
            if follow:
                return (
                    line.decode("utf-8") if isinstance(line, bytes) else str(line)
                    for line in resp.stream()
                )
            return str(resp)
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
        if not self.load_config(context=context):
            return None

        try:
            svc = self._core_v1.read_namespaced_service(name=service, namespace=namespace)
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
                    return f"http://{lb_host}:{port}"

            if node_port:
                nodes = self.list_nodes(context=context)
                for node in nodes:
                    for addr in node.status.addresses or []:
                        if addr.type in ("InternalIP", "ExternalIP") and addr.address:
                            return f"http://{addr.address}:{node_port}"
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
