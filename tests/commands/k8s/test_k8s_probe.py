"""`devops k8s probe`: one HTTP request from a labelled pod through the network policy (#4407).

The command starts one throwaway pod that carries the label of a workload, so the NetworkPolicy of
the workload applies to it, sends one request from it with `kubectl exec` and curl, and deletes the
pod. It sends the request again while curl cannot connect, because kube-router programs the policy
of a new pod a few seconds after the pod starts. The tests fake the process edge and the clock, and
none skips on the state of the host.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

import pytest

from tests.support.fakes.clock import ClockFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.kubectl_calls import (
    context_of,
    flag,
    kubectl_calls,
    namespace_of,
    verb,
    without_context,
)

_URL = "http://mcp-server.devops.svc.cluster.local:8001/implementation/mcp"
_LABEL = "app.kubernetes.io/name=devops-cli-job"
_SECRET = "s3cr3t"
_HEADER = f"Authorization: Bearer {_SECRET}"
_PINNED = f"curlimages/curl:8.23.0@sha256:{'0' * 64}"
_CANNOT_CONNECT = 7


def _is_http_exec(call: ProcessCall) -> bool:
    return call.argv[:1] == ("kubectl",) and "exec" in call.argv and "curl" in call.argv


def _probe(cli: Callable[..., Any], *args: str) -> Any:
    return cli("k8s", "probe", "--label", _LABEL, "--url", _URL, *args)


@pytest.fixture
def cluster(process_fake: ProcessFake, clock: ClockFake) -> ProcessFake:
    """A cluster whose probe pod answers 200, so a test changes only the answer it measures."""
    process_fake.answer(_is_http_exec, ProcessAnswer(returncode=0, stdout="200"))
    return process_fake


def _exec_calls(cluster: ProcessFake) -> list[tuple[str, ...]]:
    return [argv for argv in kubectl_calls(cluster) if verb(argv) == "exec"]


def _run_call(cluster: ProcessFake) -> tuple[str, ...]:
    (run,) = (argv for argv in kubectl_calls(cluster) if verb(argv) == "run")
    return run


def _delete_calls(cluster: ProcessFake) -> list[tuple[str, ...]]:
    return [argv for argv in kubectl_calls(cluster) if verb(argv) == "delete"]


def _pod_of(argv: Sequence[str]) -> str:
    return without_context(argv)[2]


def test_a_blocked_path_prints_the_curl_exit_code(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    """A path that the policy drops is a measurement, not a fault: the command prints the exit
    code of curl and exits 0."""
    cluster.answer(_is_http_exec, ProcessAnswer(returncode=_CANNOT_CONNECT))

    result = _probe(cli)

    assert (result.exit_code, "curl_exit=7" in result.output) == (0, True)
    assert len(_exec_calls(cluster)) > 1
    assert verb(kubectl_calls(cluster)[-1]) == "delete"


def test_one_pod_carries_the_label_and_the_namespace_of_the_probe(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _probe(cli)

    run = _run_call(cluster)
    assert (result.exit_code, namespace_of(run), flag(run, "--labels")) == (
        0,
        "devops",
        _LABEL,
    )
    assert all(_pod_of(run) in argv for argv in _exec_calls(cluster))


def test_the_namespace_option_names_the_namespace_of_every_call(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _probe(cli, "--namespace", "search")

    assert (result.exit_code, {namespace_of(argv) for argv in kubectl_calls(cluster)}) == (
        0,
        {"search"},
    )


def test_a_refused_connection_is_retried_until_the_pod_answers(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    answers = iter(
        [
            ProcessAnswer(returncode=_CANNOT_CONNECT),
            ProcessAnswer(returncode=_CANNOT_CONNECT),
            ProcessAnswer(returncode=0, stdout="401"),
        ]
    )
    cluster.answer(_is_http_exec, lambda call: next(answers))

    result = _probe(cli)

    assert (result.exit_code, len(_exec_calls(cluster)), "status=401" in result.output) == (
        0,
        3,
        True,
    )


def test_the_restricted_pod_spec_passes_the_pod_security_standard(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    _probe(cli)

    overrides = json.loads(flag(_run_call(cluster), "--overrides"))
    pod = overrides["spec"]
    container = pod["containers"][0]
    security = {**pod["securityContext"], **container["securityContext"]}
    assert (
        pod["automountServiceAccountToken"],
        security["runAsNonRoot"],
        security["runAsUser"] > 0,
        security["allowPrivilegeEscalation"],
        security["capabilities"]["drop"],
        security["seccompProfile"]["type"],
        security["readOnlyRootFilesystem"],
    ) == (False, True, True, False, ["ALL"], "RuntimeDefault", True)


def test_a_secret_header_stays_off_every_argv_and_out_of_the_output(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    cluster.answer(_is_http_exec, ProcessAnswer(returncode=0, stdout="200"))

    result = _probe(cli, "--header", _HEADER)

    (exec_call,) = [call for call in cluster.calls if _is_http_exec(call)]
    argvs = [" ".join(call.argv) for call in cluster.calls]
    assert (result.exit_code, exec_call.stdin) == (0, f'header = "{_HEADER}"\n')
    assert [argv for argv in argvs if _SECRET in argv] == []
    assert (_SECRET not in result.output, _SECRET not in result.stderr) == (True, True)


def test_the_pod_is_deleted_after_a_failed_probe(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    cluster.answer(_is_http_exec, ProcessAnswer(returncode=2))

    result = _probe(cli)

    (delete,) = _delete_calls(cluster)
    assert (
        result.exit_code != 0,
        without_context(delete)[1:3],
        _pod_of(_run_call(cluster)) in delete,
        "--ignore-not-found" in delete,
    ) == (True, ["delete", "pod"], True, True)


def test_the_deadline_stops_a_slow_probe(cli: Callable[..., Any], cluster: ProcessFake) -> None:
    cluster.answer(_is_http_exec, ProcessAnswer(returncode=_CANNOT_CONNECT))

    result = _probe(cli, "--timeout", "5")

    assert (result.exit_code != 0, "made no measurement" in result.output) == (True, True)
    (delete,) = _delete_calls(cluster)
    assert (_pod_of(_run_call(cluster)) in delete, verb(kubectl_calls(cluster)[-1])) == (
        True,
        "delete",
    )


def test_a_dry_run_prints_the_plan_only(cli: Callable[..., Any], process_fake: ProcessFake) -> None:
    result = _probe(cli, "--dry-run")

    assert (result.exit_code, process_fake.calls) == (0, [])
    assert ("kubectl run" in result.output, "curl" in result.output, _URL in result.output) == (
        True,
        True,
        True,
    )


def test_the_default_image_is_pinned_by_digest(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    from devops_cli.k8s.service_probe import CURL_IMAGE

    _probe(cli)

    image = flag(_run_call(cluster), "--image")
    name, _, digest = image.partition("@sha256:")
    assert (image, name, len(digest), set(digest) <= set("0123456789abcdef")) == (
        CURL_IMAGE,
        "curlimages/curl:8.23.0",
        64,
        True,
    )


def test_the_pod_runs_the_image_that_the_operator_names(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _probe(cli, "--image", _PINNED)

    assert (result.exit_code, flag(_run_call(cluster), "--image")) == (0, _PINNED)


def test_an_image_without_a_digest_is_refused_before_any_kubectl_call(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    result = _probe(cli, "--image", "curlimages/curl:8.23.0")

    assert (result.exit_code != 0, process_fake.calls) == (True, [])
    assert ("@sha256:" in result.output, "curlimages/curl:8.23.0" in result.output) == (
        True,
        True,
    )


def test_a_label_without_a_value_is_refused_before_any_kubectl_call(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    result = cli("k8s", "probe", "--label", "devops-cli-job", "--url", _URL)

    assert (result.exit_code != 0, process_fake.calls) == (True, [])
    assert "key=value" in result.output


def test_the_request_names_the_url_and_the_method(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _probe(cli, "--method", "POST")

    (exec_call,) = _exec_calls(cluster)
    assert (result.exit_code, _URL in exec_call, "POST" in exec_call, "-i" in exec_call) == (
        0,
        True,
        True,
        True,
    )


def test_the_context_option_reaches_every_kubectl_call(
    cli: Callable[..., Any], cluster: ProcessFake
) -> None:
    result = _probe(cli, "--context", "test-ctx")

    assert (result.exit_code, {context_of(argv) for argv in kubectl_calls(cluster)}) == (
        0,
        {"test-ctx"},
    )
