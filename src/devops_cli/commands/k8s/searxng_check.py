"""`devops k8s searxng-check`: what a digest bump of SearXNG can change (#3929)."""

from __future__ import annotations

from typing import Annotated

import httpx2
import typer

from devops_cli.config.defaults import (
    DEFAULT_SEARXNG_CHECK_LOCAL_PORT,
    DEFAULT_SEARXNG_TIMEOUT_SECONDS,
)
from devops_cli.dry_run import dry_run_class
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.k8s import ServiceProbeError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from devops_cli.k8s.searxng_check import (
    HEALTH_PATH,
    NAMESPACE,
    SEARXNG_IMAGE,
    SERVICE,
    SERVICE_PORT,
    PodRow,
    SearchResult,
    check_network_policy,
    forward_service,
    plan_check,
    send_searches,
)
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import TableColumn, TablePayload, print, print_success, print_warning

_STATUS_NONE = "no answer"
_PASSED = "ok"
_FAILED = "FAILED"


def _print_searches(rows: list[SearchResult]) -> None:
    print(
        TablePayload(
            title=MESSAGES.k8s.table_title_searxng_search,
            columns=[
                TableColumn(header="Row"),
                TableColumn(header="Status"),
                TableColumn(header="Hits"),
                TableColumn(header="Result"),
            ],
            rows=[
                [
                    r.name,
                    _STATUS_NONE if r.status is None else str(r.status),
                    "-" if r.hits is None else str(r.hits),
                    _FAILED if r.problems else _PASSED,
                ]
                for r in rows
            ],
        )
    )
    for row in rows:
        for problem in row.problems:
            print_warning(f"{row.name}: {problem}")


def _print_pods(rows: list[PodRow]) -> None:
    print(
        TablePayload(
            title=MESSAGES.k8s.table_title_searxng_pod,
            columns=[
                TableColumn(header="Pod"),
                TableColumn(header="Destination"),
                TableColumn(header="Result"),
            ],
            rows=[[r.pod, r.destination, "reached" if r.reached else "blocked"] for r in rows],
        )
    )


def _send_requests(local_port: int, context: str | None) -> list[SearchResult]:
    """Forward the port, send the six rows and stop the forward."""
    with (
        forward_service(
            service=SERVICE,
            namespace=NAMESPACE,
            remote_port=SERVICE_PORT,
            local_port=local_port,
            health_path=HEALTH_PATH,
            context=context,
        ) as base_url,
        http_client(
            EgressLevel.LOOPBACK,
            timeout=httpx2.Timeout(DEFAULT_SEARXNG_TIMEOUT_SECONDS),
            follow_redirects=False,
        ) as client,
    ):
        return list(send_searches(client, base_url))


@dry_run_class("request-plan")
def k8s_searxng_check(
    local_port: Annotated[
        int, typer.Option("--local-port", help=HELP.k8s.searxng_check_local_port)
    ] = DEFAULT_SEARXNG_CHECK_LOCAL_PORT,
    context: Annotated[str | None, typer.Option("--context", help=HELP.options.context)] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Check the points of the SearXNG service that a bump of the image digest can change. It sends
    six search requests with format=json through a local port-forward: one for each category of
    the provider, a query that starts with ! and names an engine that is off, a query that starts
    with !! (the redirect is recorded and never followed), and a category that no kept engine
    serves. It judges the keys of each reply, the hits, and the engines that must stay off. It
    also tries three connects from two throwaway pods, so the NetworkPolicy applies to them: a
    pod that is not a client of the service to port 8080, and a pod with the label of the service
    to the metadata address and to a private ClusterIP. Run it at each bump of the image digest.
    Exits 1 when a row fails or a pod opens a connection."""
    set_dry_run(dry_run)
    if dry_run or is_dry_run():
        render_request_plan(
            "devops k8s searxng-check would make these calls:",
            plan_check(local_port, context),
            [MESSAGES.k8s.searxng_check_dry_run],
        )
        return
    searches = _send_requests(local_port, context)
    _print_searches(searches)
    pods = check_network_policy(context)
    _print_pods(pods)
    failed: list[str] = []
    if bad := [r.name for r in searches if r.problems]:
        failed.append(MESSAGES.k8s.searxng_check_failed_rows.format(rows=", ".join(bad)))
    if opened := [f"{r.pod} -> {r.destination}" for r in pods if r.reached]:
        failed.append(MESSAGES.k8s.searxng_check_failed_pod.format(connects=", ".join(opened)))
    if failed:
        raise ServiceProbeError(
            MESSAGES.k8s.searxng_check_failed.format(count=len(failed), detail="; ".join(failed))
        )
    print_success(
        MESSAGES.k8s.searxng_check_passed.format(
            rows=len(searches), destinations=len(pods), image=SEARXNG_IMAGE
        )
    )


__all__ = ["forward_service", "k8s_searxng_check"]
