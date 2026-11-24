"""The throwaway pod that probes what a labelled pod can reach (#3894).

A NetworkPolicy selects a pod by its label, so the only way to test it on a running cluster is a
pod that carries the label of the service. `probe_from_pod` starts that pod with `kubectl run`,
probes each target from it with `kubectl exec`, and deletes it. The namespace of the cluster
enforces Pod Security `restricted`, and the Service of the labelled workload selects the pod by its
label, so the pod must pass the admission and must never become ready.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from devops_cli.exceptions.k8s import ServiceProbeError
from devops_cli.k8s.service_probe import PodProbeRow, PodTarget, _answers, probe_from_pod
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.kubectl_calls import (
    after_separator,
    context_of,
    flag,
    kubectl_calls,
    namespace_of,
    verb,
)

_LABELS = {"app.kubernetes.io/name": "crawl4ai"}
_METADATA = PodTarget(role="<metadata>", host="169.254.169.254", port=80)
_CLUSTER_IP = PodTarget(role="<private-cluster-ip>", host="192.0.2.10", port=8080)
_PREFIX = "crawl4ai-check"
_URL = "http://mcp-server.devops.svc.cluster.local:8001/implementation/mcp"
_HTTP_PREFIX = "devops-probe"
_CANNOT_CONNECT = 7
_PROBE_TEMPLATE_IMAGE = (
    "busybox:1.37.0@sha256:a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec"
)
_PROBE_TEMPLATE_JSON = json.dumps(
    {
        "apiVersion": "batch/v1",
        "kind": "CronJob",
        "metadata": {"name": "service-probe", "namespace": "devops"},
        "spec": {
            "jobTemplate": {
                "spec": {
                    "template": {
                        "spec": {
                            "securityContext": {
                                "runAsNonRoot": True,
                                "runAsUser": 65534,
                                "runAsGroup": 65534,
                                "seccompProfile": {"type": "RuntimeDefault"},
                            },
                            "containers": [
                                {
                                    "name": "probe",
                                    "image": _PROBE_TEMPLATE_IMAGE,
                                    "securityContext": {
                                        "allowPrivilegeEscalation": False,
                                        "capabilities": {"drop": ["ALL"]},
                                        "readOnlyRootFilesystem": True,
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        },
    }
)


def _is_cronjob_get(call: ProcessCall) -> bool:
    return "get" in call.argv and "cronjob" in call.argv and "service-probe" in call.argv


@pytest.fixture(autouse=True)
def answer_cronjob_template(process_fake: ProcessFake) -> None:
    process_fake.answer(_is_cronjob_get, ProcessAnswer(stdout=_PROBE_TEMPLATE_JSON))


def _is_exec(call: ProcessCall) -> bool:
    return call.argv[:1] == ("kubectl",) and "exec" in call.argv


def _is_http_exec(call: ProcessCall) -> bool:
    return _is_exec(call) and "curl" in call.argv


def _probe(**overrides: Any) -> list[PodProbeRow]:
    arguments: dict[str, Any] = {
        "namespace": "devops",
        "labels": _LABELS,
        "targets": [_METADATA, _CLUSTER_IP],
        "name_prefix": _PREFIX,
    }
    return probe_from_pod(**{**arguments, **overrides})


def _http(**overrides: Any) -> Any:
    """The HTTP probe, imported in the call phase: on the base commit, before the HTTP probe exists,
    the test fails here and not at collection."""
    from devops_cli.k8s.service_probe import probe_http_from_pod

    arguments: dict[str, Any] = {
        "namespace": "devops",
        "labels": _LABELS,
        "url": _URL,
        "name_prefix": _HTTP_PREFIX,
    }
    return probe_http_from_pod(**{**arguments, **overrides})


def _exec_calls(fake: ProcessFake) -> list[tuple[str, ...]]:
    return [argv for argv in kubectl_calls(fake) if verb(argv) == "exec"]


def _run_call(fake: ProcessFake) -> tuple[str, ...]:
    (run,) = (argv for argv in kubectl_calls(fake) if verb(argv) == "run")
    return run


def _effective_security_context(overrides: dict[str, Any]) -> dict[str, Any]:
    pod = overrides["spec"].get("securityContext", {})
    container = overrides["spec"]["containers"][0].get("securityContext", {})
    return {**pod, **container}


def test_a_target_that_the_pod_cannot_reach_is_blocked(process_fake: ProcessFake) -> None:
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))

    rows = _probe()

    assert rows == [
        PodProbeRow(role="<metadata>", reached=False),
        PodProbeRow(role="<private-cluster-ip>", reached=False),
    ]


def test_a_target_that_the_pod_reaches_is_reported_as_reached(process_fake: ProcessFake) -> None:
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))
    process_fake.answer(
        lambda call: _is_exec(call) and _METADATA.host in " ".join(call.argv),
        ProcessAnswer(returncode=0),
    )

    rows = _probe()

    assert rows == [
        PodProbeRow(role="<metadata>", reached=True),
        PodProbeRow(role="<private-cluster-ip>", reached=False),
    ]


def test_the_pod_carries_the_labels_and_the_namespace_that_the_caller_names(
    process_fake: ProcessFake,
) -> None:
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))

    _probe(labels={"app.kubernetes.io/name": "searxng"}, namespace="search")

    run = _run_call(process_fake)
    assert (flag(run, "--labels"), namespace_of(run), flag(run, "--restart")) == (
        "app.kubernetes.io/name=searxng",
        "search",
        "Never",
    )


def test_the_pod_image_is_pinned_by_digest(process_fake: ProcessFake) -> None:
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))

    _probe()

    image = flag(_run_call(process_fake), "--image")
    name, _, digest = image.partition("@sha256:")
    assert (bool(name), len(digest), set(digest) <= set("0123456789abcdef")) == (True, 64, True)


def test_the_pod_passes_the_restricted_pod_security_level(process_fake: ProcessFake) -> None:
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))

    _probe()

    overrides = json.loads(flag(_run_call(process_fake), "--overrides"))
    container = overrides["spec"]["containers"][0]
    effective = _effective_security_context(overrides)
    assert (
        container["securityContext"]["allowPrivilegeEscalation"],
        container["securityContext"]["capabilities"],
        container["securityContext"]["readOnlyRootFilesystem"],
        overrides["spec"]["automountServiceAccountToken"],
        effective["runAsNonRoot"],
        effective["runAsUser"] > 0,
        effective["seccompProfile"],
    ) == (False, {"drop": ["ALL"]}, True, False, True, True, {"type": "RuntimeDefault"})


def test_the_pod_never_becomes_ready_so_the_service_sends_it_no_traffic(
    process_fake: ProcessFake,
) -> None:
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))

    _probe()

    overrides = json.loads(flag(_run_call(process_fake), "--overrides"))
    probe = overrides["spec"]["containers"][0]["readinessProbe"]
    assert probe["exec"]["command"] == ["false"]


def test_the_pod_starts_first_each_target_is_probed_and_the_pod_is_deleted_last(
    process_fake: ProcessFake,
) -> None:
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))

    _probe()

    calls = kubectl_calls(process_fake)
    verbs = [verb(argv) for argv in calls]
    run = _run_call(process_fake)
    name = run[run.index("run") + 1]
    delete = calls[-1]
    probed = [" ".join(after_separator(argv)) for argv in calls if verb(argv) == "exec"]
    assert (
        verbs[0],
        verbs[1],
        verbs[-1],
        verbs.count("exec"),
        name in delete,
        namespace_of(delete),
    ) == (
        "get",
        "run",
        "delete",
        2,
        True,
        "devops",
    )
    assert [
        [target.host in text and str(target.port) in text for text in probed]
        for target in (_METADATA, _CLUSTER_IP)
    ] == [[True, False], [False, True]]


def test_the_pod_name_starts_with_the_prefix_and_differs_for_each_probe(
    process_fake: ProcessFake,
) -> None:
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))

    _probe()
    _probe()

    names = [
        argv[argv.index("run") + 1] for argv in kubectl_calls(process_fake) if verb(argv) == "run"
    ]
    assert (len(set(names)), all(name.startswith(f"{_PREFIX}-") for name in names)) == (2, True)


def test_every_call_names_the_context_that_the_caller_names(process_fake: ProcessFake) -> None:
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))

    _probe(context="test-ctx")

    assert {context_of(argv) for argv in kubectl_calls(process_fake)} == {"test-ctx"}


def test_a_pod_that_does_not_start_is_deleted_and_the_probe_fails(
    process_fake: ProcessFake,
) -> None:
    process_fake.answer(
        lambda call: call.argv[:1] == ("kubectl",) and "run" in call.argv,
        ProcessAnswer(returncode=1, stderr="admission webhook denied the request"),
    )

    with pytest.raises(ServiceProbeError) as caught:
        _probe()

    verbs = [verb(argv) for argv in kubectl_calls(process_fake)]
    assert (verbs[-1], caught.value.exit_code, caught.value.error_code) == (
        "delete",
        1,
        "K8S_SERVICE_PROBE_ERROR",
    )
    assert "admission webhook denied the request" in caught.value.message


def test_a_probe_that_raises_still_deletes_the_pod(process_fake: ProcessFake) -> None:
    process_fake.answer(
        lambda call: _is_exec(call) and _CLUSTER_IP.host in " ".join(call.argv),
        ProcessAnswer(side_effect=RuntimeError("the connection to the cluster was lost")),
    )

    with pytest.raises(RuntimeError, match="the connection to the cluster was lost"):
        _probe()

    assert verb(kubectl_calls(process_fake)[-1]) == "delete"


def test_the_forward_poll_sends_one_request_for_a_503(web: WebFake, clock: ClockFake) -> None:
    """The wait loop of `forward_service` polls again, so one poll reports down at once (#5532)."""
    web.answer("http://127.0.0.1:8080/healthz", 503)

    assert (_answers("http://127.0.0.1:8080", "/healthz"), len(web.sent), clock.waits) == (
        False,
        1,
        [],
    )


def test_a_blocked_path_prints_the_curl_exit_code_at_the_wait_deadline(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    from devops_cli.config.defaults import DEFAULT_PROBE_RETRY_SECONDS, DEFAULT_PROBE_WAIT_SECONDS
    from devops_cli.k8s.service_probe import PodHttpResult

    process_fake.answer(_is_http_exec, ProcessAnswer(returncode=_CANNOT_CONNECT))

    result = _http()

    verbs = [verb(argv) for argv in kubectl_calls(process_fake)]
    run = _run_call(process_fake)
    pod = run[run.index("run") + 1]
    assert (result, verbs[0], verbs[-1], verbs.count("exec") > 1) == (
        PodHttpResult(status=None, curl_exit=_CANNOT_CONNECT),
        "run",
        "delete",
        True,
    )
    assert all(pod in argv for argv in _exec_calls(process_fake))
    assert set(clock.waits) == {DEFAULT_PROBE_RETRY_SECONDS}
    assert sum(clock.waits) <= DEFAULT_PROBE_WAIT_SECONDS


def test_a_refused_connection_is_retried_until_the_policy_is_programmed(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    from devops_cli.k8s.service_probe import PodHttpResult

    answers = iter(
        [
            ProcessAnswer(returncode=_CANNOT_CONNECT, stderr="command terminated with exit code 7"),
            ProcessAnswer(returncode=_CANNOT_CONNECT, stderr="command terminated with exit code 7"),
            ProcessAnswer(returncode=0, stdout="401"),
        ]
    )
    process_fake.answer(_is_http_exec, lambda call: next(answers))

    result = _http()

    assert (result, len(_exec_calls(process_fake))) == (
        PodHttpResult(status=401, curl_exit=None),
        3,
    )


def test_a_secret_header_travels_on_the_standard_input_of_the_exec_call(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    process_fake.answer(_is_http_exec, ProcessAnswer(returncode=0, stdout="200"))

    _http(headers=["Authorization: Bearer s3cr3t"])

    (exec_call,) = [call for call in process_fake.calls if _is_http_exec(call)]
    assert exec_call.stdin == 'header = "Authorization: Bearer s3cr3t"\n'
    assert not any("s3cr3t" in " ".join(call.argv) for call in process_fake.calls)


def test_the_request_that_the_pod_sends_names_the_url_and_the_method(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    process_fake.answer(_is_http_exec, ProcessAnswer(returncode=0, stdout="204"))

    _http(method="POST")

    (exec_call,) = _exec_calls(process_fake)
    assert (_URL in exec_call, "curl" in exec_call, "POST" in exec_call, "-i" in exec_call) == (
        True,
        True,
        True,
        True,
    )


def test_the_http_probe_pod_runs_the_image_that_the_caller_names(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    process_fake.answer(_is_http_exec, ProcessAnswer(returncode=0, stdout="200"))
    image = f"curlimages/curl:8.23.0@sha256:{'0' * 64}"

    _http(image=image)

    assert flag(_run_call(process_fake), "--image") == image


def test_the_default_http_probe_image_is_pinned_by_digest(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    from devops_cli.k8s.service_probe import CURL_IMAGE

    process_fake.answer(_is_http_exec, ProcessAnswer(returncode=0, stdout="200"))

    _http()

    image = flag(_run_call(process_fake), "--image")
    name, _, digest = image.partition("@sha256:")
    assert (image, name, len(digest), set(digest) <= set("0123456789abcdef")) == (
        CURL_IMAGE,
        "curlimages/curl:8.23.0",
        64,
        True,
    )


def test_a_probe_that_passes_the_timeout_deadline_raises_and_deletes_the_pod(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    process_fake.answer(_is_http_exec, ProcessAnswer(returncode=_CANNOT_CONNECT))

    with pytest.raises(ServiceProbeError, match="made no measurement") as caught:
        _http(wait=20, timeout=5)

    verbs = [verb(argv) for argv in kubectl_calls(process_fake)]
    assert (caught.value.exit_code, verbs[-1], verbs.count("exec")) == (1, "delete", 3)


def test_a_curl_that_fails_stops_the_probe_and_deletes_the_pod(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    process_fake.answer(_is_http_exec, ProcessAnswer(returncode=2))

    with pytest.raises(ServiceProbeError, match="curl exit code 2"):
        _http()

    verbs = [verb(argv) for argv in kubectl_calls(process_fake)]
    assert (verbs[-1], verbs.count("exec")) == ("delete", 1)


def test_a_request_that_prints_no_status_stops_the_probe_and_deletes_the_pod(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    process_fake.answer(_is_http_exec, ProcessAnswer(returncode=0, stdout=""))

    with pytest.raises(ServiceProbeError, match="no HTTP status"):
        _http()

    assert verb(kubectl_calls(process_fake)[-1]) == "delete"


def test_the_plan_of_the_http_probe_names_the_pod_the_curl_line_and_the_url() -> None:
    from devops_cli.k8s.service_probe import plan_probe_http_from_pod

    plan = plan_probe_http_from_pod(
        namespace="devops",
        labels=_LABELS,
        url=_URL,
        name_prefix=_HTTP_PREFIX,
        headers=["Authorization: Bearer s3cr3t"],
    )

    run, request, delete = plan
    assert (run.method, request.method, delete.method) == (
        "kubectl run",
        "kubectl exec",
        "kubectl delete",
    )
    assert (_URL in request.argv, "curl" in request.argv, "-K" in request.argv) == (
        True,
        True,
        True,
    )
    assert request.stdin == 'header = "<value>"\n'
    assert "s3cr3t" not in " ".join(run.argv + request.argv)


def test_the_probe_reads_image_and_security_context_from_the_cluster_cronjob_template(
    process_fake: ProcessFake,
) -> None:
    custom_template = json.dumps(
        {
            "spec": {
                "jobTemplate": {
                    "spec": {
                        "template": {
                            "spec": {
                                "securityContext": {
                                    "runAsNonRoot": True,
                                    "runAsUser": 10001,
                                    "runAsGroup": 10001,
                                    "seccompProfile": {"type": "RuntimeDefault"},
                                },
                                "containers": [
                                    {
                                        "name": "probe",
                                        "image": "busybox:1.37.0@sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
                                        "securityContext": {
                                            "allowPrivilegeEscalation": False,
                                            "capabilities": {"drop": ["ALL"]},
                                            "readOnlyRootFilesystem": True,
                                        },
                                    }
                                ],
                            }
                        }
                    }
                }
            }
        }
    )
    process_fake.answer(_is_cronjob_get, ProcessAnswer(stdout=custom_template))
    process_fake.answer(_is_exec, ProcessAnswer(returncode=1))

    _probe()

    run = _run_call(process_fake)
    assert (
        flag(run, "--image")
        == "busybox:1.37.0@sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"
    )
    overrides = json.loads(flag(run, "--overrides"))
    effective = _effective_security_context(overrides)
    assert effective["runAsUser"] == 10001


def test_a_missing_cronjob_template_raises_service_probe_error(
    process_fake: ProcessFake,
) -> None:
    process_fake.answer(_is_cronjob_get, ProcessAnswer(stdout=""))

    with pytest.raises(ServiceProbeError, match="devops/service-probe"):
        _probe()
