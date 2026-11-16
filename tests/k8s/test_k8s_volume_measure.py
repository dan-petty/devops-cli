"""The measure of the volume move copy path: its plan, its copies and its report (#3701).

The cluster is the shared process fake: no test starts kubectl or bash, and no test reaches a
cluster. The live run is the step of a person, who records the numbers in #3953.

The measure module is imported inside each test, so this file collects on the base commit and
each test fails there on its own.
"""

from __future__ import annotations

import pytest

from devops_cli.config.constants import (
    CONST_K8S_HOSTNAME_LABEL,
    CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
    CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT,
    CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
)
from devops_cli.config.defaults import DEFAULT_K8S_VOLUME_MOVE_IMAGE
from devops_cli.exceptions.k8s import VolumeMoveRefusedError
from devops_cli.k8s.volume_move import copy_argv
from tests.support.fakes.process import ProcessFake

SOURCE_NODE = "node-a"
TARGET_NODE = "node-b"
STORAGE_CLASS = "local-path"
CONTEXT = "test-ctx"


def test_the_measure_plans_the_copy_command_of_the_move(process_fake: ProcessFake) -> None:
    """Each copy is the move's own pipe, and each side is read with the move's digest script."""
    # Imported here, so the file collects on the base commit and this test fails there.
    from devops_cli.k8s.volume_move_measure import MEASURE_COPIES, measure_requests, plan_measure

    plan = plan_measure(SOURCE_NODE, TARGET_NODE, STORAGE_CLASS)

    requests = measure_requests(plan, CONTEXT)
    copies = [request.argv for request in requests if request.argv[0] == "bash"]
    digests = [
        request.argv for request in requests if CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT in request.argv
    ]

    assert (
        copies
        == [tuple(copy_argv(plan.namespace, plan.source_pod, plan.destination_pod, CONTEXT))]
        * MEASURE_COPIES
    )
    assert all("mkfifo" in argv[-1] and argv[-1].count("kubectl") == 2 for argv in copies)
    assert len(digests) == 2 * MEASURE_COPIES
    assert any(
        plan.source_pod in argv and CONST_K8S_VOLUME_MOVE_SOURCE_DIR in argv for argv in digests
    )
    assert any(
        plan.destination_pod in argv and CONST_K8S_VOLUME_MOVE_DESTINATION_DIR in argv
        for argv in digests
    )
    assert process_fake.calls == []


def test_the_measure_plans_twenty_copies_of_100_mib(process_fake: ProcessFake) -> None:
    """The plan holds 20 copies, and each one writes 104,857,600 fresh random bytes to the source."""
    # Imported here, so the file collects on the base commit and this test fails there.
    from devops_cli.k8s.volume_move_measure import (
        MEASURE_BYTES,
        MEASURE_COPIES,
        measure_requests,
        plan_measure,
    )

    plan = plan_measure(SOURCE_NODE, TARGET_NODE, STORAGE_CLASS)

    requests = measure_requests(plan, CONTEXT)
    writes = [request.argv for request in requests if request.argv[-1].startswith("head -c ")]

    assert (
        (plan.copies, plan.bytes_per_copy) == (MEASURE_COPIES, MEASURE_BYTES) == (20, 104_857_600)
    )
    assert len(writes) == MEASURE_COPIES
    assert all(f"head -c {MEASURE_BYTES} /dev/urandom" in argv[-1] for argv in writes)
    assert all(plan.source_pod in argv for argv in writes)
    assert process_fake.calls == []


def test_each_copy_pod_selects_its_node(process_fake: ProcessFake) -> None:
    """Both claims are fresh, so each pod pins the node where its claim must be made."""
    # Imported here, so the file collects on the base commit and this test fails there.
    from devops_cli.k8s.volume_move_measure import plan_measure, pod_manifests

    plan = plan_measure(SOURCE_NODE, TARGET_NODE, STORAGE_CLASS)

    pods = {manifest["metadata"]["name"]: manifest["spec"] for manifest in pod_manifests(plan)}

    assert pods[plan.source_pod]["nodeSelector"] == {CONST_K8S_HOSTNAME_LABEL: SOURCE_NODE}
    assert pods[plan.destination_pod]["nodeSelector"] == {CONST_K8S_HOSTNAME_LABEL: TARGET_NODE}
    assert plan.source_node != plan.target_node
    with pytest.raises(VolumeMoveRefusedError) as refused:
        plan_measure(SOURCE_NODE, SOURCE_NODE, STORAGE_CLASS)
    assert refused.value.error_code == "K8S_VOLUME_MOVE_REFUSED"
    assert process_fake.calls == []


def test_the_measure_pods_carry_no_service_account_token(process_fake: ProcessFake) -> None:
    """A temporary pod mounts no token, runs the move image and sleeps with its claim mounted."""
    # Imported here, so the file collects on the base commit and this test fails there.
    from devops_cli.k8s.volume_move_measure import plan_measure, pod_manifests

    plan = plan_measure(SOURCE_NODE, TARGET_NODE, STORAGE_CLASS)

    pods = pod_manifests(plan)

    assert [pod["spec"]["automountServiceAccountToken"] for pod in pods] == [False, False]
    assert [pod["spec"]["containers"][0]["image"] for pod in pods] == [
        DEFAULT_K8S_VOLUME_MOVE_IMAGE,
        DEFAULT_K8S_VOLUME_MOVE_IMAGE,
    ]
    assert [pod["spec"]["containers"][0]["command"] for pod in pods] == [
        ["sleep", "infinity"],
        ["sleep", "infinity"],
    ]
    assert [pod["spec"]["containers"][0]["volumeMounts"][0]["mountPath"] for pod in pods] == [
        CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
        CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
    ]
    assert process_fake.calls == []
