"""The checks of `devops k8s crawl4ai-check`: what the Crawl4AI service must refuse (#3894).

The service fetches the page of any URL that a client names, so it is a server-side request forgery
risk. Three controls keep it off internal addresses, and this module tests each one on a running
cluster:

- The bearer token: every route but `/health` answers 401 or 403 without it.
- The destination filter inside the service: each route refuses a URL on an internal target. The
  pinned image answers with HTTP 400 and the body `{"detail": "URL blocked (SSRF protection): URL
  blocked"}`. A second source reports 403. A refusal holds no page content, so its body is a JSON
  object with the one key `detail`.
- The NetworkPolicy of the pod (`k8s/devops/crawl4ai/networkpolicy.yaml`): a pod with the label of
  the service cannot open a connection to the metadata address or to a private ClusterIP.

The report names each target by a role, never by an address or a host name.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

import httpx2

from devops_cli.config.constants import CONST_CLOUD_METADATA_PRIMARY_IPV4
from devops_cli.config.defaults import DEFAULT_CRAWL4AI_MAX_REPLY_BYTES
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.http.entry import request_headers
from devops_cli.k8s.service_probe import (
    PodProbeRow,
    PodTarget,
    forward_argv,
    plan_probe_from_pod,
    probe_from_pod,
    read_capped,
    service_cluster_ip,
)

# The image the check was written for. The gate row `k8s` compares it with the image of
# Deployment `crawl4ai`, so a bump of the digest fails until a person runs `devops k8s
# crawl4ai-check` against the new image and sets this value.
CRAWL4AI_IMAGE = "unclecode/crawl4ai:0.9.5@sha256:0b05666882bfb67f45d559a5b827839c54127b74aedd723f8ab338a3571b5fc9"

NAMESPACE = "devops"
SERVICE = "crawl4ai"
SERVICE_PORT = 11235
HEALTH_PATH = "/health"
POD_LABELS = {"app.kubernetes.io/name": SERVICE}
POD_NAME_PREFIX = "crawl4ai-check"

_ROADMAP_SERVICE = "roadmap-service"
_ROADMAP_PORT = 8000
_METADATA_PORT = 80
# A public page for the requests without the token. The service must refuse them before it reads
# the URL, so the page is never fetched.
_PUBLIC_PAGE = "https://example.com/"
_LLM_QUESTION = "Summarize the page."
_REFUSALS_WITHOUT_TOKEN = (401, 403)
_REFUSAL_STATUSES = (400, 403)

ROLE_METADATA = "<metadata>"
ROLE_PRIVATE_CLUSTER_IP = "<private-cluster-ip>"
CREDENTIAL_LABEL_NONE = "(no token)"


@dataclass(frozen=True)
class Route:
    """A route of the service that fetches the page of a URL."""

    method: Literal["GET", "POST"]
    name: str
    # Fields of the JSON body besides `url`, for a POST.
    fields: tuple[tuple[str, str], ...] = ()


ROUTES = (
    Route("POST", "/md", (("f", "fit"),)),
    Route("POST", "/html"),
    Route("POST", "/screenshot"),
    Route("POST", "/pdf"),
    Route("GET", "/llm/{url}"),
)


def internal_targets() -> dict[str, str]:
    """The URL of each internal target, by role. The Service names are composed from the namespace,
    the Service and the `svc` domain, so no host name is written in full."""

    def url(scheme: str, host: str, port: int | None = None, path: str = "/") -> str:
        return str(httpx2.URL(scheme=scheme, host=host, port=port, path=path))

    def service(name: str, port: int) -> str:
        return url("http", f"{name}.{NAMESPACE}.svc.cluster.local", port)

    return {
        ROLE_METADATA: url(
            "http", str(CONST_CLOUD_METADATA_PRIMARY_IPV4), path="/latest/meta-data/"
        ),
        "<loopback>": url("http", "localhost", SERVICE_PORT),
        "<kubernetes-api>": url("https", "kubernetes.default.svc"),
        "<crawl4ai-service>": service(SERVICE, SERVICE_PORT),
        "<roadmap-service>": service(_ROADMAP_SERVICE, _ROADMAP_PORT),
    }


def is_refusal(status: int, body: bytes) -> bool:
    """Whether a reply is a refusal of the URL: a status of 400 or 403, and a body that is a JSON
    object with the one key `detail`, a text. A page, a fault or a redirect is no refusal."""
    if status not in _REFUSAL_STATUSES:
        return False
    try:
        reply = json.loads(body)
    except ValueError:
        return False
    return isinstance(reply, dict) and set(reply) == {"detail"} and isinstance(reply["detail"], str)


@dataclass(frozen=True)
class RequestRow:
    """One request of the check and what the service answered. `status` is None when the request
    got no answer. `refused` is the verdict of the check for the request."""

    route: str
    role: str
    status: int | None
    body_bytes: int
    refused: bool


def _send(
    client: httpx2.Client, base_url: str, route: Route, url: str, headers: dict[str, str]
) -> tuple[int, bytes]:
    """One request of `route` that asks the service to fetch `url`. Returns the status and the
    body, cut at the byte cap."""
    if route.method == "POST":
        request = client.build_request(
            "POST",
            f"{base_url}{route.name}",
            json={"url": url, **dict(route.fields)},
            headers=headers,
        )
    else:
        request = client.build_request(
            "GET",
            f"{base_url}/llm/{quote(url, safe='')}",
            params={"q": _LLM_QUESTION},
            headers=headers,
        )
    response = client.send(request, stream=True)
    try:
        return response.status_code, read_capped(response, DEFAULT_CRAWL4AI_MAX_REPLY_BYTES)
    finally:
        response.close()


def _row(
    client: httpx2.Client,
    base_url: str,
    route: Route,
    role: str,
    url: str,
    headers: dict[str, str],
    accepts: Callable[[int, bytes], bool],
) -> RequestRow:
    try:
        status, body = _send(client, base_url, route, url, headers)
    except httpx2.HTTPError:
        return RequestRow(route.name, role, None, 0, False)
    return RequestRow(route.name, role, status, len(body), accepts(status, body))


def send_with_token(client: httpx2.Client, base_url: str, token: str) -> Iterator[RequestRow]:
    """Send each route to each internal target with the token. A row is `refused` when the reply
    is a refusal of the URL."""
    headers = request_headers({"Authorization": f"Bearer {token}"})
    for route in ROUTES:
        for role, url in internal_targets().items():
            yield _row(client, base_url, route, role, url, headers, is_refusal)


def send_without_token(client: httpx2.Client, base_url: str) -> Iterator[RequestRow]:
    """Send each route once with no token. A row is `refused` when the status is 401 or 403."""
    headers = request_headers()
    for route in ROUTES:
        yield _row(
            client,
            base_url,
            route,
            CREDENTIAL_LABEL_NONE,
            _PUBLIC_PAGE,
            headers,
            lambda status, _body: status in _REFUSALS_WITHOUT_TOKEN,
        )


def check_network_policy(context: str | None = None) -> list[PodProbeRow]:
    """Try a connect to the metadata address and to the ClusterIP of the roadmap Service from a pod
    that carries the label of the service. A row with `reached` false means that the policy blocks
    the destination."""
    cluster_ip = service_cluster_ip(NAMESPACE, _ROADMAP_SERVICE, context)
    return probe_from_pod(
        namespace=NAMESPACE,
        labels=POD_LABELS,
        targets=[
            PodTarget(ROLE_METADATA, str(CONST_CLOUD_METADATA_PRIMARY_IPV4), _METADATA_PORT),
            PodTarget(ROLE_PRIVATE_CLUSTER_IP, cluster_ip, _ROADMAP_PORT),
        ],
        name_prefix=POD_NAME_PREFIX,
        context=context,
    )


def plan_check(local_port: int, context: str | None = None) -> list[PlannedRequest]:
    """Every call of the check, in order, with a role in place of each address. The plan holds no
    token."""
    plan = [
        PlannedRequest(
            method="keyring",
            target="read crawl4ai_api_token",
        ),
        PlannedRequest(
            method="kubectl port-forward",
            target=f"svc/{SERVICE}",
            argv=tuple(forward_argv(SERVICE, NAMESPACE, SERVICE_PORT, local_port, context)),
        ),
        PlannedRequest(method="GET", target=f"{HEALTH_PATH} {CREDENTIAL_LABEL_NONE}"),
    ]
    plan.extend(
        PlannedRequest(method=route.method, target=f"{route.name} {role}")
        for route in ROUTES
        for role in internal_targets()
    )
    plan.extend(
        PlannedRequest(method=route.method, target=f"{route.name} {CREDENTIAL_LABEL_NONE}")
        for route in ROUTES
    )
    plan.append(PlannedRequest(method="kubectl get service", target=_ROADMAP_SERVICE))
    plan.extend(
        plan_probe_from_pod(
            namespace=NAMESPACE,
            labels=POD_LABELS,
            targets=[
                PodTarget(ROLE_METADATA, "", _METADATA_PORT),
                PodTarget(ROLE_PRIVATE_CLUSTER_IP, "", _ROADMAP_PORT),
            ],
            name_prefix=POD_NAME_PREFIX,
            context=context,
        )
    )
    return plan
