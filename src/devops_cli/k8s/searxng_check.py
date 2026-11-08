"""The checks of `devops k8s searxng-check`: what a digest bump of SearXNG can change (#3929).

The Service `searxng` is the search provider of the roadmap Service (#3927). A bump of the pinned
image can change six points, and this module tests each one on a running cluster:

- The reply: `GET /search?format=json` answers HTTP 200 with a JSON object of seven keys. The
  format `json` must be in `search.formats`, or the service answers HTTP 403.
- The categories: each category of the provider (`DEFAULT_SEARXNG_CATEGORIES`) returns a hit.
- The engines: the scraping and keyed engines of `OFF_ENGINES` stay off. A hit of one of them, or
  one of them in `unresponsive_engines`, means that the settings keep an engine that must stay off.
- The bang `!name`: a name of an engine that is off stays text and selects no engine.
- The bang `!!name`: the service answers with a redirect to an external site. The check records the
  answer and never follows it.
- A category that no kept engine serves: the check records the status and the number of hits.
- The NetworkPolicy of the pod (`k8s/devops/searxng/networkpolicy*.yaml`): a pod that is not a
  client of the service gets no connection to port 8080, and a pod with the label of the service
  cannot open a connection to the metadata address or to a private ClusterIP.

The forward and the throwaway pods are the code of `devops_cli.k8s.service_probe`. The report names
each pod and target by a role, never by an address or a host name.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final, Literal

import httpx2

from devops_cli.config.constants import CONST_CLOUD_METADATA_PRIMARY_IPV4
from devops_cli.config.defaults import DEFAULT_SEARXNG_CATEGORIES, DEFAULT_SEARXNG_MAX_REPLY_BYTES
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.http.entry import request_headers
from devops_cli.k8s.service_probe import (
    PodProbeRow,
    PodTarget,
    forward_argv,
    forward_service,
    plan_probe_from_pod,
    probe_from_pod,
    read_capped,
    service_cluster_ip,
)

# The image the check was written for. The gate row `k8s` compares it with the image of
# Deployment `searxng`, so a bump of the digest fails until a person runs `devops k8s
# searxng-check` against the new image and sets this value.
SEARXNG_IMAGE = "docker.io/searxng/searxng:2026.10.23-629368e40@sha256:aecad882e86eeb022b76351c8dce4eb48d0cbb16a5f1691f77ea32c96d317502"

NAMESPACE = "devops"
SERVICE = "searxng"
SERVICE_PORT = 8080
HEALTH_PATH = "/healthz"
POD_LABELS = {"app.kubernetes.io/name": SERVICE}
# A label that is neither the label of the service nor the label of its one client.
UNLABELED_POD_LABELS = {"app.kubernetes.io/name": "searxng-check-unlabeled"}
POD_NAME_PREFIX = "searxng-check"
UNLABELED_POD_NAME_PREFIX = "searxng-check-unlabeled"

# The keys of a reply of `/search?format=json`, read from the pinned image on 2026-11-07.
REPLY_KEYS: Final = (
    "answers",
    "corrections",
    "infoboxes",
    "query",
    "results",
    "suggestions",
    "unresponsive_engines",
)
# The scraping engines that the upstream sites suspended in October 2026 (SearXNG issues 6866 and
# 6819), and the keyed Brave engine, which the owner dropped on 2026-11-07. A name here is a name
# of the default settings.yml, and a prefix: `brave` also covers `brave.news`.
OFF_ENGINES: Final = ("brave", "braveapi", "google", "bing", "startpage", "mojeek", "qwant")

ROLE_UNLABELED_POD = "<unlabeled-pod>"
ROLE_SEARXNG_POD = "<searxng-pod>"
ROLE_SEARXNG_SERVICE = "<searxng-service>"
ROLE_METADATA = "<metadata>"
ROLE_PRIVATE_CLUSTER_IP = "<private-cluster-ip>"

_ROADMAP_SERVICE = "roadmap-service"
_ROADMAP_PORT = 8000
_METADATA_PORT = 80
_QUERY = "python"
_QUERY_OFF_ENGINE = "!google python"
_QUERY_EXTERNAL = "!!g python"
# A category that the provider does not send and no kept engine serves.
_UNUSED_CATEGORY = "images"
_GENERAL_CATEGORY = "general"
_FAULT_STATUS = 500
_FORMAT_REFUSED_STATUS = 403

Judge = Literal["reply", "text", "recorded"]


@dataclass(frozen=True)
class SearchSpec:
    """One search row: the query and the categories of the request, and how to judge the reply.

    `reply`: a full reply with a hit. `text`: a full reply, with no hit needed, for a query that
    must stay text. `recorded`: the status is recorded and only a fault or no answer fails.
    """

    name: str
    query: str
    categories: str
    judge: Judge


@dataclass(frozen=True)
class SearchResult:
    """What the service answered to one row. `status` is None when the request got no answer, and
    `hits` is None when the body holds no list of results."""

    name: str
    status: int | None
    hits: int | None
    problems: tuple[str, ...]


@dataclass(frozen=True)
class PodRow:
    """The result of one connect: the role of the pod, the role of the destination, and whether
    the pod opened a connection."""

    pod: str
    destination: str
    reached: bool


def search_specs() -> tuple[SearchSpec, ...]:
    """The six rows, in order. The categories of the first three are those of the provider."""
    return (
        *(
            SearchSpec(f"json-{category}", _QUERY, category, "reply")
            for category in DEFAULT_SEARXNG_CATEGORIES.split(",")
        ),
        SearchSpec("bang-off-engine", _QUERY_OFF_ENGINE, _GENERAL_CATEGORY, "text"),
        SearchSpec("bang-external", _QUERY_EXTERNAL, _GENERAL_CATEGORY, "recorded"),
        SearchSpec("unused-category", _QUERY, _UNUSED_CATEGORY, "recorded"),
    )


def _off_engines(engines: list[object], names: tuple[str, ...]) -> list[str]:
    """The names in `engines` that start with one of `names`."""
    return [e for e in engines if isinstance(e, str) and e.startswith(names)]


def reply_problems(
    status: int, body: bytes, *, expect_hits: bool = True, also_off: tuple[str, ...] = ()
) -> list[str]:
    """One text for each point of a `/search?format=json` reply that fails. An empty list is a pass.

    The points are the status, the seven keys, the type of `unresponsive_engines`, a hit (only when
    `expect_hits`), and an engine of `OFF_ENGINES` or `also_off` in `results` or in
    `unresponsive_engines`. An engine that is on and suspended shows only in the second list.
    """
    if status == _FORMAT_REFUSED_STATUS:
        return ["HTTP 403: the format json is not in search.formats of the settings"]
    if status != httpx2.codes.OK:
        return [f"HTTP {status}, not 200"]
    try:
        reply = json.loads(body)
    except ValueError:
        reply = None
    if not isinstance(reply, dict):
        return ["the body is not a JSON object"]
    problems = [f"the reply lacks the key {key}" for key in REPLY_KEYS if key not in reply]
    names = (*OFF_ENGINES, *also_off)
    off: list[str] = []
    results = reply.get("results")
    if "results" in reply:
        if not isinstance(results, list):
            problems.append("results is not a list")
        else:
            if expect_hits and not results:
                problems.append("the reply holds no hit")
            off += _off_engines([h.get("engine") for h in results if isinstance(h, dict)], names)
    unresponsive = reply.get("unresponsive_engines")
    if "unresponsive_engines" in reply:
        if not isinstance(unresponsive, list):
            problems.append("unresponsive_engines is not a list")
        else:
            off += _off_engines(
                [i[0] for i in unresponsive if isinstance(i, list | tuple) and i], names
            )
    problems += [f"the engine {engine} must stay off" for engine in dict.fromkeys(off)]
    return problems


def _hit_count(body: bytes) -> int | None:
    try:
        reply = json.loads(body)
    except ValueError:
        return None
    results = reply.get("results") if isinstance(reply, dict) else None
    return len(results) if isinstance(results, list) else None


def judge_search(spec: SearchSpec, status: int | None, body: bytes) -> SearchResult:
    """The verdict for one row. A row with no problem passes."""
    if status is None:
        return SearchResult(spec.name, None, None, ("the request got no answer",))
    hits = _hit_count(body)
    if spec.judge == "recorded":
        problems = [f"HTTP {status}, a fault of the service"] if status >= _FAULT_STATUS else []
    else:
        problems = reply_problems(status, body, expect_hits=spec.judge == "reply")
    return SearchResult(spec.name, status, hits, tuple(problems))


def _search(client: httpx2.Client, base_url: str, spec: SearchSpec) -> SearchResult:
    request = client.build_request(
        "GET",
        f"{base_url}/search",
        params={"q": spec.query, "format": "json", "categories": spec.categories},
        headers=request_headers({"Accept": "application/json"}),
    )
    try:
        response = client.send(request, stream=True, follow_redirects=False)
        try:
            status, body = (
                response.status_code,
                read_capped(response, DEFAULT_SEARXNG_MAX_REPLY_BYTES),
            )
        finally:
            response.close()
    except httpx2.HTTPError:
        return judge_search(spec, None, b"")
    return judge_search(spec, status, body)


def send_searches(client: httpx2.Client, base_url: str) -> Iterator[SearchResult]:
    """Send the six rows through the forward, with no credential. The client must not follow a
    redirect: the answer of `!!g` points to an external site."""
    for spec in search_specs():
        yield _search(client, base_url, spec)


def check_network_policy(context: str | None = None) -> list[PodRow]:
    """Try the three connects of the NetworkPolicy from two throwaway pods. A row with `reached`
    true means that the policy lets the connect through.

    A pod with a neutral label tries port 8080 of the Service. A pod with the label of the service
    tries the metadata address and the ClusterIP of the roadmap Service.
    """
    searxng_ip = service_cluster_ip(NAMESPACE, SERVICE, context)
    roadmap_ip = service_cluster_ip(NAMESPACE, _ROADMAP_SERVICE, context)
    unlabeled = probe_from_pod(
        namespace=NAMESPACE,
        labels=UNLABELED_POD_LABELS,
        targets=[PodTarget(ROLE_SEARXNG_SERVICE, searxng_ip, SERVICE_PORT)],
        name_prefix=UNLABELED_POD_NAME_PREFIX,
        context=context,
    )
    labeled = probe_from_pod(
        namespace=NAMESPACE,
        labels=POD_LABELS,
        targets=[
            PodTarget(ROLE_METADATA, str(CONST_CLOUD_METADATA_PRIMARY_IPV4), _METADATA_PORT),
            PodTarget(ROLE_PRIVATE_CLUSTER_IP, roadmap_ip, _ROADMAP_PORT),
        ],
        name_prefix=POD_NAME_PREFIX,
        context=context,
    )
    return [
        *(PodRow(ROLE_UNLABELED_POD, row.role, row.reached) for row in unlabeled),
        *(PodRow(ROLE_SEARXNG_POD, row.role, row.reached) for row in labeled),
    ]


def plan_check(local_port: int, context: str | None = None) -> list[PlannedRequest]:
    """Every call of the check, in order, with a role in place of each address."""
    plan = [
        PlannedRequest(
            method="kubectl port-forward",
            target=f"svc/{SERVICE}",
            argv=tuple(forward_argv(SERVICE, NAMESPACE, SERVICE_PORT, local_port, context)),
        ),
        PlannedRequest(method="GET", target=HEALTH_PATH),
    ]
    plan.extend(
        PlannedRequest(
            method="GET",
            target=f"/search {spec.name}",
            condition=f"q={spec.query} categories={spec.categories} format=json",
        )
        for spec in search_specs()
    )
    plan.append(PlannedRequest(method="kubectl get service", target=SERVICE))
    plan.append(PlannedRequest(method="kubectl get service", target=_ROADMAP_SERVICE))
    for labels, prefix, targets in (
        (
            UNLABELED_POD_LABELS,
            UNLABELED_POD_NAME_PREFIX,
            [PodTarget(ROLE_SEARXNG_SERVICE, "", SERVICE_PORT)],
        ),
        (
            POD_LABELS,
            POD_NAME_PREFIX,
            [
                PodTarget(ROLE_METADATA, "", _METADATA_PORT),
                PodTarget(ROLE_PRIVATE_CLUSTER_IP, "", _ROADMAP_PORT),
            ],
        ),
    ):
        plan.extend(
            plan_probe_from_pod(
                namespace=NAMESPACE,
                labels=labels,
                targets=targets,
                name_prefix=prefix,
                context=context,
            )
        )
    return plan


__all__ = [
    "HEALTH_PATH",
    "NAMESPACE",
    "OFF_ENGINES",
    "REPLY_KEYS",
    "SEARXNG_IMAGE",
    "SERVICE",
    "SERVICE_PORT",
    "PodProbeRow",
    "PodRow",
    "SearchResult",
    "SearchSpec",
    "check_network_policy",
    "forward_service",
    "judge_search",
    "plan_check",
    "plan_probe_from_pod",
    "probe_from_pod",
    "reply_problems",
    "search_specs",
    "send_searches",
    "service_cluster_ip",
]
