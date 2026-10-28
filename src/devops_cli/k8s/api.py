"""The Kubernetes API seam: the calls devops-cli makes on the SDK's API objects, and their source.

`KubernetesService` (`k8s/service.py`) takes its API objects from a `KubernetesApiSource`. In
production that is `KubernetesClientSource`, which builds them with the official client; a test
gives the service the shared fake cluster instead. The Protocols name only the calls devops-cli
makes, so the fake and its contract suite cover exactly those (#1315).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.security.sanitizer import mask_secrets


class CoreApi(Protocol):
    """The calls devops-cli makes on the SDK's `CoreV1Api`."""

    def list_node(self, **kwargs: Any) -> Any: ...

    def list_namespaced_pod(self, namespace: str, **kwargs: Any) -> Any: ...

    def list_pod_for_all_namespaces(self, **kwargs: Any) -> Any: ...

    def read_namespaced_pod_log(self, name: str, namespace: str, **kwargs: Any) -> Any: ...

    def list_namespaced_service(self, namespace: str, **kwargs: Any) -> Any: ...

    def read_namespaced_service(self, name: str, namespace: str, **kwargs: Any) -> Any: ...

    def list_namespaced_event(self, namespace: str, **kwargs: Any) -> Any: ...

    def list_event_for_all_namespaces(self, **kwargs: Any) -> Any: ...

    def read_persistent_volume(self, name: str, **kwargs: Any) -> Any: ...

    def patch_persistent_volume(self, name: str, body: Any, **kwargs: Any) -> Any: ...

    def delete_persistent_volume(self, name: str, **kwargs: Any) -> Any: ...

    def read_namespaced_persistent_volume_claim(
        self, name: str, namespace: str, **kwargs: Any
    ) -> Any: ...


class CustomObjectsApi(Protocol):
    """The calls devops-cli makes on the SDK's `CustomObjectsApi`."""

    def list_namespaced_custom_object(
        self, group: str, version: str, namespace: str, plural: str, **kwargs: Any
    ) -> Any: ...

    def get_namespaced_custom_object(
        self, group: str, version: str, namespace: str, plural: str, name: str, **kwargs: Any
    ) -> Any: ...

    def create_namespaced_custom_object(
        self, group: str, version: str, namespace: str, plural: str, body: Any, **kwargs: Any
    ) -> Any: ...

    def patch_namespaced_custom_object(
        self,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        name: str,
        body: Any,
        **kwargs: Any,
    ) -> Any: ...

    def patch_namespaced_custom_object_status(
        self,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        name: str,
        body: Any,
        **kwargs: Any,
    ) -> Any: ...


class VersionApi(Protocol):
    """The call devops-cli makes on the SDK's `VersionApi`."""

    def get_code(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class KubernetesApis:
    """The API objects of one connection, which share one client configuration."""

    core: CoreApi
    custom_objects: CustomObjectsApi
    version: VersionApi


class KubernetesApiSource(Protocol):
    """Where `KubernetesService` gets its API objects."""

    def contexts(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """The kubeconfig contexts and the current one, as `list_kube_config_contexts` gives."""
        ...

    def connect(self, context: str | None) -> KubernetesApis:
        """The API objects of `context`, else of the kubeconfig's current context.

        Raises `KubernetesContextError` when no configuration gives a connection.
        """
        ...


def _kubeconfig_paths() -> str:
    """Every `KUBECONFIG` entry, read now, else `~/.kube/config`.

    The client reads `KUBECONFIG` once, when its module is imported, so the source passes the
    paths itself. The client's `KubeConfigMerger` splits the entries and expands each one.
    """
    return os.environ.get("KUBECONFIG") or str(Path.home() / ".kube" / "config")


class KubernetesClientSource:
    """The official client, with one configuration rule and one `Configuration` per client.

    A connection uses the kubeconfig when the kubeconfig names the context: the one asked for,
    else the kubeconfig's current context. Otherwise it uses the pod's service account. The
    client's global default `Configuration` is never written, so loaders that still use it
    cannot change where this connection goes, and it cannot change where they go.
    """

    def __init__(self, service_account_dir: Path | None = None) -> None:
        self._service_account_dir = service_account_dir

    def contexts(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        from kubernetes import config as k8s_config  # type: ignore[import-untyped]

        try:
            contexts, active = k8s_config.list_kube_config_contexts(config_file=_kubeconfig_paths())
        except Exception as exc:
            raise KubernetesContextError(
                f"Failed to inspect kubeconfig contexts: {mask_secrets(str(exc))}"
            ) from exc
        return list(contexts or []), active

    def connect(self, context: str | None) -> KubernetesApis:
        from kubernetes import client as k8s_client

        name = context or self._current_context()
        if name and name in self._context_names():
            from kubernetes import config as k8s_config

            api_client = k8s_config.new_client_from_config(
                config_file=_kubeconfig_paths(), context=name, persist_config=False
            )
        else:
            api_client = k8s_client.ApiClient(self._service_account_configuration(name))
        return KubernetesApis(
            core=k8s_client.CoreV1Api(api_client),
            custom_objects=k8s_client.CustomObjectsApi(api_client),
            version=k8s_client.VersionApi(api_client),
        )

    def _context_names(self) -> set[str]:
        try:
            contexts, _ = self.contexts()
        except KubernetesContextError:
            return set()
        return {str(ctx.get("name")) for ctx in contexts if ctx.get("name")}

    def _current_context(self) -> str | None:
        try:
            _, active = self.contexts()
        except KubernetesContextError:
            return None
        return str(active.get("name")) if active and active.get("name") else None

    def _service_account_configuration(self, name: str | None) -> Any:
        """A new `Configuration` from the pod's service account, or the reason there is none."""
        from kubernetes import client as k8s_client
        from kubernetes.config import incluster_config  # type: ignore[import-untyped]

        token, cert = (
            incluster_config.SERVICE_TOKEN_FILENAME,
            incluster_config.SERVICE_CERT_FILENAME,
        )
        if self._service_account_dir is not None:
            token = str(self._service_account_dir / "token")
            cert = str(self._service_account_dir / "ca.crt")
        configuration = k8s_client.Configuration()
        try:
            incluster_config.InClusterConfigLoader(
                token_filename=token, cert_filename=cert
            ).load_and_set(configuration)
        except Exception as exc:
            named = f"No kubeconfig context named '{name}'" if name else "No kubeconfig context"
            raise KubernetesContextError(
                f"{named}, and no service account: {mask_secrets(str(exc))}", context=name
            ) from exc
        return configuration


__all__ = [
    "CoreApi",
    "CustomObjectsApi",
    "KubernetesApiSource",
    "KubernetesApis",
    "KubernetesClientSource",
    "VersionApi",
]


def api_error_type() -> type[Exception]:
    """The client's error for an HTTP reply of the API server, `kubernetes.client.ApiException`.

    The client raises it for every status it does not take as success; a connection that fails
    raises urllib3's errors instead.
    """
    from kubernetes import client as k8s_client

    error: type[Exception] = k8s_client.ApiException
    return error
