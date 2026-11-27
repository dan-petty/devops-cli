"""The measure of the volume move copy path: its plan, its copies and its report (#3701).

The cluster is the shared process fake: no test starts kubectl or bash, and no test reaches a
cluster. The live run is the step of a person, who records the numbers in #3953.

The measure module is imported inside each test, so this file collects on the base commit and
each test fails there on its own.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import (
    CONST_K8S_HOSTNAME_LABEL,
    CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
    CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT,
    CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
)
from devops_cli.exceptions.k8s import VolumeMoveRefusedError
from devops_cli.k8s.volume_move import copy_argv
from devops_cli.lang import MESSAGES
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

if TYPE_CHECKING:
    from devops_cli.k8s.volume_move_measure import CopyRun

VOLUME_MOVE_IMAGE = (
    "debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2"
)
SOURCE_NODE = "node-a"
TARGET_NODE = "node-b"
STORAGE_CLASS = "local-path"
CONTEXT = "test-ctx"
CONTENT = "b" * 64
OTHER_CONTENT = "c" * 64
DIGEST = f"entries 1\nfiles 1\nbytes 104857600\nmetadata {'a' * 64}\ncontent {CONTENT}\n"
OTHER_DIGEST = DIGEST.replace(CONTENT, OTHER_CONTENT)


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
    assert all("/dev/tcp/" in argv[-1] and argv[-1].count("kubectl") == 4 for argv in copies)
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

    plan = plan_measure(SOURCE_NODE, TARGET_NODE, STORAGE_CLASS, image=VOLUME_MOVE_IMAGE)

    pods = pod_manifests(plan)

    assert [pod["spec"]["automountServiceAccountToken"] for pod in pods] == [False, False]
    assert [pod["spec"]["containers"][0]["image"] for pod in pods] == [
        VOLUME_MOVE_IMAGE,
        VOLUME_MOVE_IMAGE,
    ]
    assert [pod["spec"]["containers"][0].get("securityContext") for pod in pods] == [None, None]
    assert [pod["spec"]["containers"][0]["command"] for pod in pods] == [
        ["sleep", "infinity"],
        ["sleep", "infinity"],
    ]
    assert [pod["spec"]["containers"][0]["volumeMounts"][0]["mountPath"] for pod in pods] == [
        CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
        CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
    ]
    assert process_fake.calls == []


def _completed(
    argv: list[str], code: int, *, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=argv, returncode=code, stdout=stdout, stderr=stderr)


@dataclass
class MeasureCluster:
    """The requests of one measure run, answered from the argv of each command.

    Every `kubectl` request succeeds, and one copy of `failing_copy` fails with the exit code and
    the error line that a short pipe writes. Each digest request answers with the content digest
    of its side, so a test can make one destination differ from its source.
    """

    failing_copy: int | None = None
    destination_digest: str = DIGEST
    started: int = 0
    changes: list[str] = field(default_factory=list)

    def __call__(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        argv = list(call.argv)
        if argv[0] == "bash":
            self.started += 1
            failed = self.started == self.failing_copy
            return _completed(argv, 1 if failed else 0, stderr="tar: short write" if failed else "")
        assert argv[:3] == ["kubectl", "--context", CONTEXT], argv
        args = argv[3:]
        self.changes.append(" ".join(args[:2]))
        return _completed(argv, 0, stdout=self._read(args))

    def _read(self, args: list[str]) -> str:
        if args[:3] == ["get", "cronjob", "volume-move"]:
            return json.dumps(
                {
                    "apiVersion": "batch/v1",
                    "kind": "CronJob",
                    "metadata": {"name": "volume-move", "namespace": "devops"},
                    "spec": {
                        "jobTemplate": {
                            "spec": {
                                "template": {
                                    "spec": {
                                        "containers": [{"name": "copy", "image": VOLUME_MOVE_IMAGE}]
                                    }
                                }
                            }
                        }
                    },
                }
            )
        if args[0] != "exec":
            return ""
        if args[-1] == CONST_K8S_VOLUME_MOVE_SOURCE_DIR:
            return DIGEST
        if args[-1] == CONST_K8S_VOLUME_MOVE_DESTINATION_DIR:
            return self.destination_digest
        return ""


def _copies(count: int, *, mismatch: int | None = None, short: int | None = None) -> list[CopyRun]:
    """A report fixture of `count` copies, with one mismatched or one short by its number."""
    from devops_cli.k8s.volume_move_measure import CopyRun

    return [
        CopyRun(
            number=number,
            complete=number != short,
            source_digest=CONTENT,
            destination_digest=OTHER_CONTENT if number == mismatch else CONTENT,
            detail="the copy exited 1" if number == short else "",
        )
        for number in range(1, count + 1)
    ]


def test_a_failed_copy_still_removes_the_namespace(process_fake: ProcessFake) -> None:
    """A copy that fails is recorded, the run goes on, and its temporary namespace is deleted."""
    from devops_cli.k8s.volume_move_measure import plan_measure, report_problems, run_measure

    plan = plan_measure(SOURCE_NODE, TARGET_NODE, STORAGE_CLASS)
    cluster = MeasureCluster(failing_copy=3)
    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=cluster))

    runs = run_measure(plan, CONTEXT)

    assert len(runs) == plan.copies
    assert [run.number for run in runs if not run.complete] == [3]
    assert "exited 1" in runs[2].detail
    assert sum(1 for run in runs if run.matched) == plan.copies - 1
    assert {run.source_digest for run in runs if run.complete} == {CONTENT}
    assert report_problems(plan, runs)
    deletes = [call.argv for call in process_fake.calls if "delete" in call.argv]
    assert len(deletes) == 1
    assert deletes[0][:6] == (
        "kubectl",
        "--context",
        CONTEXT,
        "delete",
        "namespace",
        plan.namespace,
    )
    assert process_fake.calls[-1].argv == deletes[0]
    assert cluster.started == plan.copies


def test_a_mismatch_fails_the_report() -> None:
    """One destination digest that differs from its source fails the report by its copy number."""
    from devops_cli.k8s.volume_move_measure import plan_measure, report_problems

    plan = plan_measure(SOURCE_NODE, TARGET_NODE, STORAGE_CLASS)

    problems = report_problems(plan, _copies(plan.copies, mismatch=7))

    assert "7/20" in problems[0]
    assert problems == [
        MESSAGES.k8s.volume_move_measure_digest_differs.format(
            number=7, copies=plan.copies, source=CONTENT, destination=OTHER_CONTENT
        ),
        MESSAGES.k8s.volume_move_measure_too_few.format(matched=19, copies=plan.copies),
    ]


def test_all_copies_match(capsys: pytest.CaptureFixture[str]) -> None:
    """Twenty complete copies with matching digests pass, and the table holds both counts."""
    from devops_cli.k8s.volume_move_measure import plan_measure, render_report, report_problems

    plan = plan_measure(SOURCE_NODE, TARGET_NODE, STORAGE_CLASS)
    runs = _copies(plan.copies)

    render_report(plan, runs)

    output = capsys.readouterr().out
    assert "| Measure | Result |" in output
    assert "| Complete copies | 20/20 |" in output
    assert "| Digest matches | 20/20 |" in output
    assert report_problems(plan, runs) == []


def test_the_dry_run_lists_the_requests(
    process_fake: ProcessFake, capsys: pytest.CaptureFixture[str]
) -> None:
    """The dry run prints the namespace, the two claims, the two pods and the 20 copies."""
    from devops_cli.k8s.volume_move_measure import MEASURE_COPIES, main, plan_measure

    code = main(
        [
            "--source-node",
            SOURCE_NODE,
            "--target-node",
            TARGET_NODE,
            "--context",
            CONTEXT,
            "--dry-run",
        ]
    )

    output = capsys.readouterr().out
    plan = plan_measure(SOURCE_NODE, TARGET_NODE, STORAGE_CLASS)
    assert code == 0
    assert f"namespace {plan.namespace}" in output
    assert f"claim {plan.source_claim}" in output
    assert f"claim {plan.destination_claim}" in output
    assert f"pod {plan.source_pod}" in output
    assert f"pod {plan.destination_pod}" in output
    assert f"copy 1/{MEASURE_COPIES}" in output
    assert f"copy {MEASURE_COPIES}/{MEASURE_COPIES}" in output
    assert output.count("volume-move-send") == MEASURE_COPIES
    assert process_fake.calls == []


def test_main_returns_one_for_a_failed_report(
    process_fake: ProcessFake, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run whose copy fails prints the report, names the copy and returns 1."""
    from devops_cli.k8s.volume_move_measure import main

    cluster = MeasureCluster(failing_copy=3)
    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=cluster))

    code = main(["--source-node", SOURCE_NODE, "--target-node", TARGET_NODE, "--context", CONTEXT])

    captured = capsys.readouterr()
    assert code == 1
    assert "| Complete copies | 19/20 |" in captured.out
    assert "| Digest matches | 19/20 |" in captured.out
    assert "3/20" in captured.err
    assert cluster.started == 20


def test_one_short_copy_fails_the_report() -> None:
    """A copy that did not complete fails the report, which names it by its copy number."""
    from devops_cli.k8s.volume_move_measure import plan_measure, report_problems

    plan = plan_measure(SOURCE_NODE, TARGET_NODE, STORAGE_CLASS)

    problems = report_problems(plan, _copies(plan.copies, short=plan.copies))

    assert "20/20" in problems[0]
    assert problems == [
        MESSAGES.k8s.volume_move_measure_copy_failed.format(
            number=20, copies=plan.copies, detail="the copy exited 1"
        ),
        MESSAGES.k8s.volume_move_measure_too_few.format(matched=19, copies=plan.copies),
    ]
