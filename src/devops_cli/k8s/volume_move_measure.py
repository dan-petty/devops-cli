"""Measure the copy path of a volume move: twenty copies of 100 MiB between two nodes (#3701).

The move copies a claim with one pipe between two `kubectl exec` streams (#3695), so this measure
plans the same `copy_argv` and reads each side with `digest_args`. A person runs it against a
cluster, because a runner Job has no cluster token, and records its report in #3953.

The measure makes one temporary namespace with two claims and two pods, one pod on each named
node. Each copy writes fresh random data to the source claim, empties the destination claim, runs
the pipe of the move and compares the two digests. The run deletes the namespace when it ends,
whether the copies passed or failed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from devops_cli.config.commands import BIN_BASH, build_kubectl_cmd
from devops_cli.config.constants import (
    CONST_K8S_HOSTNAME_LABEL,
    CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
    CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX,
    CONST_K8S_VOLUME_MOVE_LABELS,
    CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
    CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX,
)
from devops_cli.config.defaults import (
    DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS,
    DEFAULT_K8S_VOLUME_MOVE_DETAIL_CHARS,
    DEFAULT_K8S_VOLUME_MOVE_IMAGE,
    DEFAULT_K8S_VOLUME_MOVE_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.exceptions.k8s import VolumeMoveError, VolumeMoveRefusedError
from devops_cli.k8s.volume_move import copy_argv, digest_args, empty_args
from devops_cli.lang import MESSAGES
from devops_cli.output import write_stderr, write_stdout

MEASURE_COPIES: Final[int] = 20
MEASURE_BYTES: Final[int] = 104_857_600
_MEASURE_NAMESPACE: Final[str] = "volume-move-measure"
_MEASURE_CLAIM_SIZE: Final[str] = "1Gi"
_MEASURE_SOURCE_FILE: Final[str] = "data.bin"
_DEFAULT_STORAGE_CLASS: Final[str] = "local-path"
_PLAN_HEADING: Final[str] = "Plan for the volume move copy measure"
_SAME_NODE: Final[str] = (
    "The measure needs two different nodes, and it got {node} for both the source and the target."
)
# The bound of one copy and of one side's digest, which read every byte of the volume.
_COPY_TIMEOUT: Final[float] = DEFAULT_K8S_VOLUME_MOVE_COPY_TIMEOUT_SECONDS
# The bound of a `kubectl wait` or of the delete of the namespace: its own timeout, then a request.
_WAIT_TIMEOUT: Final[float] = (
    DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS + DEFAULT_K8S_VOLUME_MOVE_REQUEST_TIMEOUT_SECONDS
)


@dataclass(frozen=True)
class MeasurePlan:
    """The temporary namespace, the two nodes and the counts of one measure run."""

    namespace: str
    source_node: str
    target_node: str
    storage_class: str
    copies: int = MEASURE_COPIES
    bytes_per_copy: int = MEASURE_BYTES

    @property
    def source_claim(self) -> str:
        """The claim on the source node, which holds the random data of each copy."""
        return f"measure{CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX}"

    @property
    def destination_claim(self) -> str:
        """The claim on the target node, which receives each copy."""
        return f"measure{CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX}"

    @property
    def source_pod(self) -> str:
        """The pod that runs the source side of the pipe."""
        return f"measure{CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX}"

    @property
    def destination_pod(self) -> str:
        """The pod that runs the destination side of the pipe."""
        return f"measure{CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX}"


@dataclass(frozen=True)
class CopyRun:
    """One copy of a run: its number, whether it completed, its two digests and why it did not."""

    number: int
    complete: bool
    source_digest: str
    destination_digest: str
    detail: str = ""

    @property
    def matched(self) -> bool:
        """Whether the copy completed and its destination content digest equals its source."""
        return self.complete and self.source_digest == self.destination_digest


def plan_measure(source_node: str, target_node: str, storage_class: str) -> MeasurePlan:
    """The plan of one measure run, which refuses the same node for both sides."""
    if source_node == target_node:
        raise VolumeMoveRefusedError(_SAME_NODE.format(node=source_node))
    return MeasurePlan(
        namespace=_MEASURE_NAMESPACE,
        source_node=source_node,
        target_node=target_node,
        storage_class=storage_class,
    )


def claim_manifests(plan: MeasurePlan) -> list[dict[str, Any]]:
    """The two claims, made fresh so local-path binds each one on the node of its pod."""
    return [
        _claim_manifest(plan, plan.source_claim),
        _claim_manifest(plan, plan.destination_claim),
    ]


def _claim_manifest(plan: MeasurePlan, name: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": name,
            "namespace": plan.namespace,
            "labels": dict(CONST_K8S_VOLUME_MOVE_LABELS),
        },
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "storageClassName": plan.storage_class,
            "resources": {"requests": {"storage": _MEASURE_CLAIM_SIZE}},
        },
    }


def pod_manifests(plan: MeasurePlan) -> list[dict[str, Any]]:
    """The two pods, each pinned to its node, read-write on its claim and holding no token."""
    return [
        _pod_manifest(
            plan,
            pod=plan.source_pod,
            claim=plan.source_claim,
            node=plan.source_node,
            directory=CONST_K8S_VOLUME_MOVE_SOURCE_DIR,
        ),
        _pod_manifest(
            plan,
            pod=plan.destination_pod,
            claim=plan.destination_claim,
            node=plan.target_node,
            directory=CONST_K8S_VOLUME_MOVE_DESTINATION_DIR,
        ),
    ]


def _pod_manifest(
    plan: MeasurePlan, *, pod: str, claim: str, node: str, directory: str
) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod,
            "namespace": plan.namespace,
            "labels": dict(CONST_K8S_VOLUME_MOVE_LABELS),
        },
        "spec": {
            "restartPolicy": "Never",
            "terminationGracePeriodSeconds": 0,
            "automountServiceAccountToken": False,
            "nodeSelector": {CONST_K8S_HOSTNAME_LABEL: node},
            "containers": [
                {
                    "name": "copy",
                    "image": DEFAULT_K8S_VOLUME_MOVE_IMAGE,
                    "command": ["sleep", "infinity"],
                    "volumeMounts": [{"name": "data", "mountPath": directory, "readOnly": False}],
                }
            ],
            "volumes": [
                {
                    "name": "data",
                    "persistentVolumeClaim": {"claimName": claim, "readOnly": False},
                }
            ],
        },
    }


def random_data_args(plan: MeasurePlan) -> list[str]:
    """The request that replaces the source file with fresh random data of one copy."""
    path = f"{CONST_K8S_VOLUME_MOVE_SOURCE_DIR}/{_MEASURE_SOURCE_FILE}"
    script = f"head -c {plan.bytes_per_copy} /dev/urandom > {path}"
    return ["exec", plan.source_pod, "-n", plan.namespace, "--", "bash", "-c", script]


def measure_requests(plan: MeasurePlan, context: str | None) -> list[PlannedRequest]:
    """Every request of a run, in order, as the dry run of the measure lists them."""
    manifests: list[tuple[dict[str, Any], str]] = [
        (_namespace_manifest(plan), f"namespace {plan.namespace}")
    ]
    manifests.extend(
        (manifest, f"claim {manifest['metadata']['name']}") for manifest in claim_manifests(plan)
    )
    manifests.extend(
        (manifest, f"pod {manifest['metadata']['name']}") for manifest in pod_manifests(plan)
    )
    requests = [_planned_create(context, target, manifest) for manifest, target in manifests]
    requests.extend(
        _wait_request(context, plan, pod) for pod in (plan.source_pod, plan.destination_pod)
    )
    for number in range(1, plan.copies + 1):
        requests.extend(_copy_requests(plan, context, number))
    requests.append(_delete_namespace_request(plan, context))
    return requests


def _namespace_manifest(plan: MeasurePlan) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": plan.namespace,
            "labels": dict(CONST_K8S_VOLUME_MOVE_LABELS),
        },
    }


def _planned_create(context: str | None, target: str, manifest: dict[str, Any]) -> PlannedRequest:
    return _planned(_create_args(), context, target, stdin=manifest)


def _create_args() -> list[str]:
    """The create of a manifest from standard input, which answers with the object's name."""
    return ["create", "-f", "-", "-o", "name"]


def _wait_request(context: str | None, plan: MeasurePlan, pod: str) -> PlannedRequest:
    return _planned(_wait_args(plan, pod), context, f"pod {pod}")


def _wait_args(plan: MeasurePlan, pod: str) -> list[str]:
    """The wait until one copy pod is Ready."""
    return [
        "wait",
        f"pod/{pod}",
        "-n",
        plan.namespace,
        "--for=condition=Ready",
        f"--timeout={DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS}s",
    ]


def _copy_requests(plan: MeasurePlan, context: str | None, number: int) -> list[PlannedRequest]:
    copy = f"copy {number}/{plan.copies}"
    stream = tuple(copy_argv(plan.namespace, plan.source_pod, plan.destination_pod, context))
    return [
        _planned(random_data_args(plan), context, f"the source of {copy}"),
        _planned(
            empty_args(plan.destination_pod, plan.namespace), context, f"the destination of {copy}"
        ),
        PlannedRequest(method=BIN_BASH, target=copy, argv=stream),
        _planned(
            digest_args(plan.source_pod, plan.namespace, CONST_K8S_VOLUME_MOVE_SOURCE_DIR),
            context,
            f"the source of {copy}",
        ),
        _planned(
            digest_args(
                plan.destination_pod, plan.namespace, CONST_K8S_VOLUME_MOVE_DESTINATION_DIR
            ),
            context,
            f"the destination of {copy}",
        ),
    ]


def _delete_namespace_request(plan: MeasurePlan, context: str | None) -> PlannedRequest:
    return _planned(_delete_namespace_args(plan), context, f"namespace {plan.namespace}")


def _delete_namespace_args(plan: MeasurePlan) -> list[str]:
    """The delete of the temporary namespace, with its two claims and its two pods."""
    return [
        "delete",
        "namespace",
        plan.namespace,
        "--wait=true",
        f"--timeout={DEFAULT_K8S_VOLUME_MOVE_WAIT_SECONDS}s",
        "--ignore-not-found",
    ]


def _planned(
    args: Sequence[str],
    context: str | None,
    target: str,
    *,
    stdin: dict[str, Any] | None = None,
) -> PlannedRequest:
    return PlannedRequest(
        method=f"kubectl {args[0]}",
        target=target,
        argv=tuple(build_kubectl_cmd(args, context)),
        stdin=_manifest_json(stdin) if stdin is not None else None,
    )


def _manifest_json(manifest: dict[str, Any]) -> str:
    """A manifest as the body of its create request."""
    return json.dumps(manifest, indent=2)


# ── The run ──────────────────────────────────────────────────────────────────


def run_measure(plan: MeasurePlan, context: str | None) -> list[CopyRun]:
    """Make every copy of the plan, and delete the temporary namespace when the run ends."""
    runs: list[CopyRun] = []
    try:
        _create(_namespace_manifest(plan), context, f"namespace {plan.namespace}")
        for manifest in claim_manifests(plan):
            _create(manifest, context, f"claim {manifest['metadata']['name']}")
        for manifest in pod_manifests(plan):
            _create(manifest, context, f"pod {manifest['metadata']['name']}")
        for pod in (plan.source_pod, plan.destination_pod):
            _kubectl(_wait_args(plan, pod), context, f"pod {pod}", timeout=_WAIT_TIMEOUT)
        for number in range(1, plan.copies + 1):
            runs.append(_copy_once(plan, context, number))
    finally:
        _delete_namespace(plan, context)
    return runs


def _create(manifest: dict[str, Any], context: str | None, request: str) -> None:
    _kubectl(_create_args(), context, request, stdin=_manifest_json(manifest))


def _delete_namespace(plan: MeasurePlan, context: str | None) -> None:
    _kubectl(
        _delete_namespace_args(plan),
        context,
        f"namespace {plan.namespace}",
        timeout=_WAIT_TIMEOUT,
    )


def _copy_once(plan: MeasurePlan, context: str | None, number: int) -> CopyRun:
    """One copy: fresh random data, an empty destination, the pipe of the move and two digests."""
    request = f"copy {number}/{plan.copies}"
    try:
        _kubectl(random_data_args(plan), context, request, timeout=_COPY_TIMEOUT)
        _kubectl(
            empty_args(plan.destination_pod, plan.namespace),
            context,
            request,
            timeout=_COPY_TIMEOUT,
        )
        _run(
            copy_argv(plan.namespace, plan.source_pod, plan.destination_pod, context),
            request,
            timeout=_COPY_TIMEOUT,
        )
        source = _side(plan, context, plan.source_pod, CONST_K8S_VOLUME_MOVE_SOURCE_DIR, request)
        destination = _side(
            plan, context, plan.destination_pod, CONST_K8S_VOLUME_MOVE_DESTINATION_DIR, request
        )
    except VolumeMoveError as exc:
        return CopyRun(
            number=number,
            complete=False,
            source_digest="",
            destination_digest="",
            detail=str(exc),
        )
    return CopyRun(
        number=number,
        complete=True,
        source_digest=source,
        destination_digest=destination,
    )


def _side(plan: MeasurePlan, context: str | None, pod: str, directory: str, request: str) -> str:
    output = _kubectl(
        digest_args(pod, plan.namespace, directory), context, request, timeout=_COPY_TIMEOUT
    )
    return _content_digest(output, pod)


def _content_digest(output: str, pod: str) -> str:
    """The content digest that the digest script prints, or a refusal when it is missing."""
    values = {key: value for key, _, value in (line.partition(" ") for line in output.splitlines())}
    content = values.get("content", "")
    if not content:
        raise VolumeMoveError(
            MESSAGES.k8s.volume_move_digest_unreadable.format(
                pod=pod, output=output[:DEFAULT_K8S_VOLUME_MOVE_DETAIL_CHARS]
            )
        )
    return content


def _kubectl(
    args: Sequence[str],
    context: str | None,
    request: str,
    *,
    stdin: str | None = None,
    timeout: float = DEFAULT_K8S_VOLUME_MOVE_REQUEST_TIMEOUT_SECONDS,
) -> str:
    return _run(build_kubectl_cmd(args, context), request, stdin=stdin, timeout=timeout)


def _run(argv: Sequence[str], request: str, *, stdin: str | None = None, timeout: float) -> str:
    """Run one request through `run_subprocess` and return its stdout, raising when it fails."""
    try:
        result = run_subprocess(list(argv), input=stdin, quiet=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise VolumeMoveError(
            MESSAGES.k8s.volume_move_request_timeout.format(request=request, seconds=timeout)
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise VolumeMoveError(
            MESSAGES.k8s.volume_move_request_failed.format(
                request=request,
                code=result.returncode,
                detail=detail[:DEFAULT_K8S_VOLUME_MOVE_DETAIL_CHARS],
            )
        )
    return result.stdout or ""


# ── The report ───────────────────────────────────────────────────────────────


def render_report(plan: MeasurePlan, runs: Sequence[CopyRun]) -> None:
    """Print the report as a Markdown table: the complete copies and the digest matches."""
    complete = sum(1 for run in runs if run.complete)
    matched = sum(1 for run in runs if run.matched)
    lines = [
        MESSAGES.k8s.volume_move_measure_report_heading.format(
            copies=plan.copies,
            bytes=plan.bytes_per_copy,
            source_node=plan.source_node,
            target_node=plan.target_node,
        ),
        "",
        f"| {MESSAGES.k8s.volume_move_measure_table_measure} "
        f"| {MESSAGES.k8s.volume_move_measure_table_result} |",
        "| :--- | ---: |",
        f"| {MESSAGES.k8s.volume_move_measure_complete_copies} | {complete}/{plan.copies} |",
        f"| {MESSAGES.k8s.volume_move_measure_digest_matches} | {matched}/{plan.copies} |",
    ]
    write_stdout("\n".join(lines) + "\n")


def report_problems(plan: MeasurePlan, runs: Sequence[CopyRun]) -> list[str]:
    """One problem for each copy that did not complete or match, and one for a short run."""
    problems = [_copy_problem(plan, run) for run in runs if not run.matched]
    matched = sum(1 for run in runs if run.matched)
    if matched < plan.copies:
        problems.append(
            MESSAGES.k8s.volume_move_measure_too_few.format(matched=matched, copies=plan.copies)
        )
    return problems


def _copy_problem(plan: MeasurePlan, run: CopyRun) -> str:
    """The problem of one copy: it did not complete, or its two content digests differ."""
    if not run.complete:
        return MESSAGES.k8s.volume_move_measure_copy_failed.format(
            number=run.number, copies=plan.copies, detail=run.detail
        )
    return MESSAGES.k8s.volume_move_measure_digest_differs.format(
        number=run.number,
        copies=plan.copies,
        source=run.source_digest,
        destination=run.destination_digest,
    )


# ── The entry point ──────────────────────────────────────────────────────────


def main(argv: Sequence[str] | None = None) -> int:
    """List the requests of a dry run, or run the measure and print its report.

    Exit status 0 when every copy completed with a matching digest, and 1 when one did not, so a
    short measure never reads as clean.
    """
    parser = argparse.ArgumentParser(
        prog="python -m devops_cli.k8s.volume_move_measure",
        description=__doc__.splitlines()[0],
    )
    parser.add_argument("--source-node", required=True, help="The node of the source claim.")
    parser.add_argument("--target-node", required=True, help="The node of the destination claim.")
    parser.add_argument("--context", help="The kubectl context of the cluster.")
    parser.add_argument(
        "--storage-class",
        default=_DEFAULT_STORAGE_CLASS,
        help="The storage class of the two claims.",
    )
    parser.add_argument("--dry-run", action="store_true", help="List the requests and start none.")
    args = parser.parse_args(argv)
    plan = plan_measure(args.source_node, args.target_node, args.storage_class)
    if args.dry_run:
        render_request_plan(_PLAN_HEADING, measure_requests(plan, args.context), described=True)
        return 0
    runs = run_measure(plan, args.context)
    render_report(plan, runs)
    problems = report_problems(plan, runs)
    for problem in problems:
        write_stderr(problem + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "MEASURE_BYTES",
    "MEASURE_COPIES",
    "CopyRun",
    "MeasurePlan",
    "claim_manifests",
    "main",
    "measure_requests",
    "plan_measure",
    "pod_manifests",
    "random_data_args",
    "render_report",
    "report_problems",
    "run_measure",
]
