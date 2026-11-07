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
from devops_cli.k8s.service_probe import PodProbeRow, PodTarget, probe_from_pod

from devops_cli.exceptions.k8s import ServiceProbeError
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


def _is_exec(call: ProcessCall) -> bool:
    return call.argv[:1] == ("kubectl",) and "exec" in call.argv


def _probe(**overrides: Any) -> list[PodProbeRow]:
    arguments: dict[str, Any] = {
        "namespace": "devops",
        "labels": _LABELS,
        "targets": [_METADATA, _CLUSTER_IP],
        "name_prefix": _PREFIX,
    }
    return probe_from_pod(**{**arguments, **overrides})


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
        effective["runAsNonRoot"],
        effective["runAsUser"] > 0,
        effective["seccompProfile"],
    ) == (False, {"drop": ["ALL"]}, True, True, {"type": "RuntimeDefault"})


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
    assert (verbs[0], verbs[-1], verbs.count("exec"), name in delete, namespace_of(delete)) == (
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
