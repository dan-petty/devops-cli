"""Address cluster services through the API server instead of a local port-forward.

Configured endpoints were localhost URLs backed by `kubectl port-forward`, which means a
background process per service, ports that collide between clusters, configuration that
has to be rewritten whenever the cluster changes, and a dashboard that reports "connection
refused" the moment a forward dies. It is also not portable: the same `config.yaml` cannot
describe two clusters.

The API server already proxies to any Service, and it is reachable wherever the kubeconfig
is. A `k8s://` URL therefore names the Service itself:

    k8s://monitoring/prometheus:9090/api/v1/query

which resolves against whichever cluster is configured, with no local port involved and no
process to keep alive. Credentials and TLS come from the kubeconfig, so nothing new has to
be configured to authenticate.
"""

from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from devops_cli.config.constants import (
    CONST_K8S_SERVICE_PROXY_TEMPLATE,
    CONST_K8S_URL_SCHEME,
    CONST_K8S_URL_SCHEME_TLS,
    CONST_K8S_URL_SCHEMES,
)
from devops_cli.exceptions.k8s import KubernetesError
from devops_cli.k8s.context import resolve_context

logger = logging.getLogger(__name__)


class ServiceAddressError(KubernetesError):
    """Raised when a cluster service address cannot be resolved."""


@dataclass(frozen=True)
class ServiceRef:
    """A Service addressed through the API server proxy."""

    namespace: str
    service: str
    port: str
    tls: bool = False
    path: str = ""
    # Carried separately because urlparse splits it off, and a Prometheus or Loki endpoint
    # is almost entirely query string -- dropping it turns every request into a bare /proxy
    # call that the API server rejects with 400.
    query: str = ""

    @property
    def target(self) -> str:
        """The `[scheme:]name:port` segment the proxy endpoint expects.

        The scheme prefix describes how the API server should talk to the *backend*; it is
        unrelated to the TLS between this client and the API server.
        """
        base = f"{self.service}:{self.port}"
        return f"https:{base}" if self.tls else base

    def proxy_path(self, path: str | None = None) -> str:
        """Build the API server path that proxies to this Service.

        An override may carry its own query string, which replaces this reference's.
        """
        prefix = CONST_K8S_SERVICE_PROXY_TEMPLATE.format(
            namespace=self.namespace, target=self.target
        )
        if path is None:
            suffix, query = self.path.lstrip("/"), self.query
        else:
            suffix, _, query = path.lstrip("/").partition("?")

        resolved = f"{prefix}/{suffix}" if suffix else prefix
        return f"{resolved}?{query}" if query else resolved

    def describe(self) -> str:
        """Render this reference the way it is written in configuration."""
        scheme = CONST_K8S_URL_SCHEME_TLS if self.tls else CONST_K8S_URL_SCHEME
        suffix = f"/{self.path.lstrip('/')}" if self.path else ""
        query = f"?{self.query}" if self.query else ""
        return f"{scheme}://{self.namespace}/{self.service}:{self.port}{suffix}{query}"


def is_service_url(url: str) -> bool:
    """Report whether a URL addresses a Service rather than a host."""
    return urlparse(url).scheme in CONST_K8S_URL_SCHEMES if url else False


def parse_service_url(url: str) -> ServiceRef:
    """Parse a `k8s://namespace/service:port[/path]` URL.

    Raises rather than returning None: a caller that wrote a k8s:// URL meant to address a
    Service, and silently treating a malformed one as an ordinary URL would produce a DNS
    failure naming a host they never configured.
    """
    parsed = urlparse(url)
    if parsed.scheme not in CONST_K8S_URL_SCHEMES:
        raise ServiceAddressError(f"'{url}' is not a cluster service URL.")

    namespace = (parsed.hostname or "").strip()
    if not namespace:
        raise ServiceAddressError(f"'{url}' is missing a namespace.")

    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        raise ServiceAddressError(f"'{url}' is missing a service name.")

    service_segment, *rest = segments
    service, separator, port = service_segment.partition(":")
    if not service:
        raise ServiceAddressError(f"'{url}' is missing a service name.")
    if not separator or not port:
        raise ServiceAddressError(
            f"'{url}' is missing a service port. A Service may expose several, so the "
            f"port is required rather than guessed."
        )

    return ServiceRef(
        namespace=namespace,
        service=service,
        port=port,
        tls=parsed.scheme == CONST_K8S_URL_SCHEME_TLS,
        path="/".join(rest),
        query=parsed.query,
    )


def _kube_configuration(context: str | None = None) -> Any:
    """Load the Kubernetes client configuration for the resolved context."""
    from kubernetes import client as k8s_client  # type: ignore[import-untyped]
    from kubernetes import config as k8s_config

    resolved = resolve_context(context)
    try:
        k8s_config.load_incluster_config()
    except Exception:
        try:
            k8s_config.load_kube_config(context=resolved)
        except Exception as exc:
            raise ServiceAddressError(
                f"No usable Kubernetes configuration for context '{resolved or 'current'}': {exc}"
            ) from exc
    return k8s_client.Configuration.get_default_copy()


def _ssl_context(configuration: Any) -> ssl.SSLContext:
    """Build the TLS context for talking to the API server.

    Client certificates and a custom CA cannot both be passed to httpx as plain values, so
    they are combined into one context here.
    """
    ca_cert = getattr(configuration, "ssl_ca_cert", None)
    context = (
        ssl.create_default_context(cafile=ca_cert) if ca_cert else ssl.create_default_context()
    )
    if not getattr(configuration, "verify_ssl", True):
        # Only reachable when the kubeconfig itself sets insecure-skip-tls-verify.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    cert_file = getattr(configuration, "cert_file", None)
    key_file = getattr(configuration, "key_file", None)
    if cert_file and key_file:
        context.load_cert_chain(cert_file, key_file)
    return context


def _auth_headers(configuration: Any) -> dict[str, str]:
    """Extract bearer or token headers from the client configuration."""
    headers: dict[str, str] = {}
    api_keys = getattr(configuration, "api_key", None) or {}
    prefixes = getattr(configuration, "api_key_prefix", None) or {}
    for name, value in api_keys.items():
        if not value:
            continue
        prefix = prefixes.get(name, "")
        header = "authorization" if name.lower() == "authorization" else name
        headers[header] = f"{prefix} {value}".strip()
    return headers


@dataclass(frozen=True)
class ProxyTarget:
    """Everything needed to issue a request through the API server proxy."""

    url: str
    headers: dict[str, str]
    ssl_context: ssl.SSLContext


def resolve_proxy_target(
    ref: ServiceRef, path: str | None = None, context: str | None = None
) -> ProxyTarget:
    """Resolve a Service reference into a concrete API server URL and credentials."""
    configuration = _kube_configuration(context)
    host = str(getattr(configuration, "host", "") or "").rstrip("/")
    if not host:
        raise ServiceAddressError("The Kubernetes configuration has no API server host.")
    return ProxyTarget(
        url=f"{host}{ref.proxy_path(path)}",
        headers=_auth_headers(configuration),
        ssl_context=_ssl_context(configuration),
    )


__all__ = [
    "ProxyTarget",
    "discover_service",
    "ServiceAddressError",
    "ServiceRef",
    "is_service_url",
    "parse_service_url",
    "resolve_proxy_target",
]


def discover_service(
    namespace: str,
    patterns: tuple[str, ...],
    port_hints: tuple[str, ...] = (),
    context: str | None = None,
) -> ServiceRef | None:
    """Find a Service in a namespace by name pattern, returning its proxy address.

    Chart-installed services rarely carry the bare name an operator thinks in: Prometheus
    ships as `kube-prometheus-kube-prome-prometheus`. Matching on substrings lets the same
    lookup work across clusters and chart releases, which is the point of addressing a
    Service by what it is rather than by where a port-forward put it.

    The first pattern that matches anything wins, so callers order patterns from most to
    least specific.
    """
    from devops_cli.k8s.service import KubernetesService

    service_api = KubernetesService.get_instance()
    if not service_api.load_config(context=resolve_context(context)):
        return None

    try:
        listing = service_api._core_v1.list_namespaced_service(namespace=namespace)
    except Exception as exc:
        logger.debug("Could not list services in namespace '%s': %s", namespace, exc)
        return None

    services = [item for item in (listing.items or []) if getattr(item, "metadata", None)]
    for pattern in patterns:
        for item in services:
            name = str(item.metadata.name or "")
            if pattern not in name:
                continue
            port = _select_port(item, port_hints)
            if port is None:
                continue
            return ServiceRef(namespace=namespace, service=name, port=port)
    return None


def _select_port(service: Any, hints: tuple[str, ...]) -> str | None:
    """Choose which of a Service's ports to address.

    A Service commonly exposes several -- Prometheus publishes 9090 alongside a reloader
    port -- so a hinted match is preferred and the first port is only a fallback.
    """
    spec = getattr(service, "spec", None)
    ports = list(getattr(spec, "ports", None) or [])
    if not ports:
        return None

    for hint in hints:
        for port in ports:
            if hint in {str(getattr(port, "name", "") or ""), str(getattr(port, "port", ""))}:
                return str(port.port)
    return str(ports[0].port)
