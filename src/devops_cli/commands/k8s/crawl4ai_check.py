"""`devops k8s crawl4ai-check`: what the Crawl4AI service must refuse (#3894)."""

from __future__ import annotations

from typing import Annotated

import httpx2
import typer

from devops_cli.config.defaults import (
    DEFAULT_CRAWL4AI_CHECK_LOCAL_PORT,
    DEFAULT_CRAWL4AI_CHECK_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import get_crawl4ai_api_token
from devops_cli.dry_run import dry_run_class
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.k8s import ServiceProbeError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from devops_cli.k8s.crawl4ai_check import (
    CRAWL4AI_IMAGE,
    HEALTH_PATH,
    NAMESPACE,
    SERVICE,
    SERVICE_PORT,
    RequestRow,
    check_network_policy,
    plan_check,
    send_with_token,
    send_without_token,
)
from devops_cli.k8s.service_probe import PodProbeRow, forward_service
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import TableColumn, TablePayload, print, print_success

_STATUS_NONE = "no answer"
_REFUSED = "refused"
_NOT_REFUSED = "NOT refused"


def _status(row: RequestRow) -> str:
    return _STATUS_NONE if row.status is None else str(row.status)


def _verdict(row: RequestRow) -> str:
    return _REFUSED if row.refused else _NOT_REFUSED


def _print_internal(rows: list[RequestRow]) -> None:
    print(
        TablePayload(
            title=MESSAGES.k8s.table_title_crawl4ai_internal,
            columns=[
                TableColumn(header="Route"),
                TableColumn(header="Target"),
                TableColumn(header="Status"),
                TableColumn(header="Body bytes"),
                TableColumn(header="Result"),
            ],
            rows=[[r.route, r.role, _status(r), str(r.body_bytes), _verdict(r)] for r in rows],
        )
    )


def _print_open(rows: list[RequestRow]) -> None:
    print(
        TablePayload(
            title=MESSAGES.k8s.table_title_crawl4ai_open,
            columns=[
                TableColumn(header="Route"),
                TableColumn(header="Status"),
                TableColumn(header="Body bytes"),
                TableColumn(header="Result"),
            ],
            rows=[[r.route, _status(r), str(r.body_bytes), _verdict(r)] for r in rows],
        )
    )


def _print_pod(rows: list[PodProbeRow]) -> None:
    print(
        TablePayload(
            title=MESSAGES.k8s.table_title_crawl4ai_pod,
            columns=[TableColumn(header="Destination"), TableColumn(header="Result")],
            rows=[[r.role, "reached" if r.reached else "blocked"] for r in rows],
        )
    )


def _send_requests(
    local_port: int, token: str, context: str | None
) -> tuple[list[RequestRow], list[RequestRow]]:
    """Forward the port, send the requests of the matrix and stop the forward."""
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
            EgressLevel.LOOPBACK, timeout=httpx2.Timeout(DEFAULT_CRAWL4AI_CHECK_TIMEOUT_SECONDS)
        ) as client,
    ):
        return (
            list(send_with_token(client, base_url, token)),
            list(send_without_token(client, base_url)),
        )


@dry_run_class("request-plan")
def k8s_crawl4ai_check(
    local_port: Annotated[
        int, typer.Option("--local-port", help=HELP.k8s.crawl4ai_check_local_port)
    ] = DEFAULT_CRAWL4AI_CHECK_LOCAL_PORT,
    context: Annotated[str | None, typer.Option("--context", help=HELP.options.context)] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Check that the Crawl4AI service refuses internal targets. It sends each of five routes
    (/md, /html, /screenshot, /pdf and /llm) to each of five internal targets (the metadata
    address, localhost, the Kubernetes API, the service itself and the roadmap Service) with the
    token of the keyring, through a local port-forward, and sends each route once without the
    token. It also tries a connect to the metadata address and to a private ClusterIP from a
    throwaway pod that carries the label of the service, so the NetworkPolicy applies to it.
    Run it at each bump of the image digest. The token never appears in the output. Exits 1 when
    a target is served, a request without the token is not refused, or the pod opens a
    connection."""
    set_dry_run(dry_run)
    if dry_run or is_dry_run():
        render_request_plan(
            "devops k8s crawl4ai-check would make these calls:",
            plan_check(local_port, context),
            [MESSAGES.k8s.crawl4ai_check_dry_run],
        )
        return
    token = get_crawl4ai_api_token()
    if not token:
        raise ConfigurationError(
            MESSAGES.k8s.crawl4ai_check_token_missing, key="crawl4ai.api_token"
        )
    internal, without_token = _send_requests(local_port, token, context)
    _print_internal(internal)
    _print_open(without_token)
    pod = check_network_policy(context)
    _print_pod(pod)
    failed: list[str] = []
    if unrefused := [r for r in internal if not r.refused]:
        failed.append(MESSAGES.k8s.crawl4ai_check_failed_requests.format(count=len(unrefused)))
    if unrefused := [r for r in without_token if not r.refused]:
        failed.append(MESSAGES.k8s.crawl4ai_check_failed_open.format(count=len(unrefused)))
    if opened := [r.role for r in pod if r.reached]:
        failed.append(MESSAGES.k8s.crawl4ai_check_failed_pod.format(roles=", ".join(opened)))
    if failed:
        raise ServiceProbeError(
            MESSAGES.k8s.crawl4ai_check_failed.format(count=len(failed), detail="; ".join(failed))
        )
    print_success(
        MESSAGES.k8s.crawl4ai_check_passed.format(
            internal=len(internal),
            open=len(without_token),
            destinations=len(pod),
            image=CRAWL4AI_IMAGE,
        )
    )
