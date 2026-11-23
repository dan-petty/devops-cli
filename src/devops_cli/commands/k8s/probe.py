"""`devops k8s probe`: one HTTP request from a labelled pod through a network policy (#4407)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

import typer

from devops_cli.config.defaults import (
    DEFAULT_PROBE_TIMEOUT_SECONDS,
    DEFAULT_PROBE_WAIT_SECONDS,
)
from devops_cli.dry_run import dry_run_class
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.k8s import ServiceProbeError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.k8s.service_probe import (
    CURL_IMAGE,
    PodHttpResult,
    plan_probe_http_from_pod,
    probe_http_from_pod,
)
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import write_stdout

_DEFAULT_NAMESPACE = "devops"
# The pod name is this prefix and a random suffix, so two runs never meet.
_POD_PREFIX = "devops-probe"
_DIGEST_MARKER = "@sha256:"
_LABEL_SEPARATOR = "="


def _labels(values: Sequence[str]) -> dict[str, str]:
    """The labels of the probe pod, from the `key=value` options."""
    labels: dict[str, str] = {}
    for value in values:
        key, separator, text = value.partition(_LABEL_SEPARATOR)
        if not separator or not key or not text:
            raise ValidationError(
                MESSAGES.k8s.probe_label_invalid.format(label=value), field="label"
            )
        labels[key] = text
    return labels


def _pinned_image(value: str) -> str:
    """The image of the probe pod. A value without a digest is refused, because a tag can name
    another image at the next run."""
    if _DIGEST_MARKER not in value:
        raise ValidationError(
            MESSAGES.k8s.probe_image_not_pinned.format(image=value), field="image"
        )
    return value


def _print_result(result: PodHttpResult, url: str, namespace: str) -> None:
    """Print the measured HTTP status, or the exit code of curl for a path that stays refused."""
    if result.status is not None:
        write_stdout(MESSAGES.k8s.probe_status.format(status=result.status) + "\n")
        return
    if result.curl_exit is not None:
        write_stdout(MESSAGES.k8s.probe_curl_exit.format(code=result.curl_exit) + "\n")
        return
    raise ServiceProbeError(MESSAGES.k8s.probe_no_measurement.format(url=url, namespace=namespace))


@dry_run_class("request-plan")
def k8s_probe(
    label: Annotated[list[str], typer.Option("--label", help=HELP.k8s.probe_label)],
    url: Annotated[str, typer.Option("--url", help=HELP.k8s.probe_url)],
    method: Annotated[str, typer.Option("--method", help=HELP.k8s.probe_method)] = "GET",
    header: Annotated[
        list[str] | None, typer.Option("--header", help=HELP.k8s.probe_header)
    ] = None,
    namespace: Annotated[str, typer.Option("--namespace", help=HELP.options.namespace)] = (
        _DEFAULT_NAMESPACE
    ),
    image: Annotated[str, typer.Option("--image", help=HELP.k8s.probe_image)] = CURL_IMAGE,
    wait: Annotated[float, typer.Option("--wait", help=HELP.k8s.probe_wait)] = (
        DEFAULT_PROBE_WAIT_SECONDS
    ),
    timeout: Annotated[float, typer.Option("--timeout", help=HELP.k8s.probe_timeout)] = (
        DEFAULT_PROBE_TIMEOUT_SECONDS
    ),
    context: Annotated[str | None, typer.Option("--context", help=HELP.options.context)] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Probe one URL from one throwaway pod that carries a label, so the network policy of that
    label applies to it. It starts one pod, sends the request from it with kubectl exec and curl,
    and prints the HTTP status, or the exit code of curl for a path that no response reaches. It
    sends the request again while curl exits 7, the code of a refused connection, until kube-router
    programs the policy of the new pod and the --wait deadline passes. It deletes the pod, also
    after an error or the --timeout deadline. Each header value travels to curl on the standard
    input of the exec call, so no command line and no output holds it. A blocked path prints
    curl_exit=7 and exits 0: it is a measurement of the policy, not a fault. Exits non-zero when
    the probe measured nothing."""
    set_dry_run(dry_run)
    labels = _labels(label)
    pod_image = _pinned_image(image)
    if dry_run or is_dry_run():
        render_request_plan(
            "devops k8s probe would make these calls:",
            plan_probe_http_from_pod(
                namespace=namespace,
                labels=labels,
                url=url,
                name_prefix=_POD_PREFIX,
                method=method,
                headers=header,
                image=pod_image,
                wait=wait,
                context=context,
            ),
            [MESSAGES.k8s.probe_dry_run],
        )
        return
    result = probe_http_from_pod(
        namespace=namespace,
        labels=labels,
        url=url,
        name_prefix=_POD_PREFIX,
        method=method,
        headers=header,
        image=pod_image,
        wait=wait,
        timeout=timeout,
        context=context,
    )
    _print_result(result, url, namespace)


__all__ = ["k8s_probe"]
