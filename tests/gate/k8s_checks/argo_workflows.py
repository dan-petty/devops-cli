"""The Argo objects of the product base use the plural fields that the controller reads (#5289).

The Argo Workflows controller v4 refuses a CronWorkflow with the singular `spec.schedule`
(`SpecError`, "cron workflow must have at least one schedule"), and it does not read the singular
`synchronization.mutex` or `synchronization.semaphore`. The installed CRDs keep unknown fields, so
the API server and Argo CD accept such an object, and only the log of the controller shows it.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

import pytest

from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


# The kinds whose `spec` is a Workflow spec. A CronWorkflow holds one in `spec.workflowSpec`.
_WORKFLOW_SPEC_KINDS = frozenset({"Workflow", "WorkflowTemplate", "ClusterWorkflowTemplate"})


# Each singular field of controller v3 and the list that controller v4 reads in its place.
_PLURAL = {"schedule": "schedules", "mutex": "mutexes", "semaphore": "semaphores"}


def _singular_locks(spec: dict[str, Any], path: str) -> Iterator[str]:
    """The path of each singular lock of the Workflow spec at `path`: in its `synchronization`
    and in the `synchronization` of each of its templates."""
    owners = [(path, spec.get("synchronization") or {})]
    owners += [
        (f"{path}.templates[{template.get('name', index)}]", template.get("synchronization") or {})
        for index, template in enumerate(spec.get("templates") or [])
    ]
    for owner, synchronization in owners:
        yield from (
            f"{owner}.synchronization.{lock}"
            for lock in ("mutex", "semaphore")
            if lock in synchronization
        )


def _singular_fields(document: dict[str, Any]) -> Iterator[str]:
    """The path of each singular field of one Argo object."""
    spec = document.get("spec") or {}
    if document["kind"] == "CronWorkflow":
        if "schedule" in spec:
            yield "spec.schedule"
        yield from _singular_locks(spec.get("workflowSpec") or {}, "spec.workflowSpec")
    elif document["kind"] in _WORKFLOW_SPEC_KINDS:
        yield from _singular_locks(spec, "spec")


def singular_field_problems(documents: Iterable[dict[str, Any]]) -> list[str]:
    """One line for each singular field of each object of the group `argoproj.io` (#5289)."""
    return [
        f"{document['kind']} {document['metadata'].get('namespace')}/"
        f"{document['metadata']['name']}: sets {field}. The Argo Workflows controller v4 refuses "
        "or does not read the singular field, so write the list "
        f"{field.rpartition('.')[0]}.{_PLURAL[field.rpartition('.')[2]]} in its place"
        for document in documents
        if str(document.get("apiVersion", "")).startswith("argoproj.io/")
        for field in _singular_fields(document)
    ]


def _argo(kind: str, **spec: Any) -> dict[str, Any]:
    """An Argo object of `kind` named `fixture` in namespace `fixture` with the fields `spec`."""
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": kind,
        "metadata": {"name": "fixture", "namespace": "fixture"},
        "spec": spec,
    }


_MUTEX = {"name": "fixture"}
_SEMAPHORE = {"configMapKeyRef": {"name": "fixture", "key": "workflow"}}
_PLURAL_LOCKS = {"mutexes": [_MUTEX], "semaphores": [_SEMAPHORE]}


@pytest.mark.parametrize(
    ("document", "field"),
    [
        pytest.param(
            _argo("CronWorkflow", schedule="*/3 * * * *", workflowSpec={}),
            "spec.schedule",
            id="cron-schedule",
        ),
        pytest.param(
            _argo("WorkflowTemplate", synchronization={"mutex": _MUTEX}),
            "spec.synchronization.mutex",
            id="template-mutex",
        ),
        pytest.param(
            _argo(
                "WorkflowTemplate",
                templates=[{"name": "main", "synchronization": {"mutex": _MUTEX}}],
            ),
            "spec.templates[main].synchronization.mutex",
            id="template-step-mutex",
        ),
        pytest.param(
            _argo("Workflow", synchronization={"semaphore": _SEMAPHORE}),
            "spec.synchronization.semaphore",
            id="workflow-semaphore",
        ),
        pytest.param(
            _argo(
                "CronWorkflow",
                schedules=["*/3 * * * *"],
                workflowSpec={"synchronization": {"semaphore": _SEMAPHORE}},
            ),
            "spec.workflowSpec.synchronization.semaphore",
            id="cron-workflow-spec-semaphore",
        ),
    ],
)
def check_the_rule_names_each_singular_field(document: dict[str, Any], field: str) -> None:
    (problem,) = singular_field_problems([document])
    assert (f"{document['kind']} fixture/fixture" in problem, f" sets {field}." in problem) == (
        True,
        True,
    )


def check_the_rule_accepts_the_plural_fields_and_a_cronjob() -> None:
    documents = [
        _argo(
            "CronWorkflow",
            schedules=["*/3 * * * *"],
            workflowSpec={"synchronization": _PLURAL_LOCKS},
        ),
        _argo(
            "WorkflowTemplate",
            synchronization=_PLURAL_LOCKS,
            templates=[{"name": "main", "synchronization": _PLURAL_LOCKS}],
        ),
        _argo("Workflow", synchronization=_PLURAL_LOCKS),
        # A CronJob holds `spec.schedule` too, and it is no Argo object.
        {
            "apiVersion": "batch/v1",
            "kind": "CronJob",
            "metadata": {"name": "fixture", "namespace": "fixture"},
            "spec": {"schedule": "*/3 * * * *"},
        },
    ]

    assert singular_field_problems(documents) == []


def check_no_argo_object_of_the_product_base_sets_a_singular_field() -> None:
    """Each Argo object that `kubectl apply -k k8s/devops` applies uses `schedules`, `mutexes`
    and `semaphores`, the fields that the controller v4 reads (#5289)."""
    problems = singular_field_problems(applied_documents(DEVOPS_DIR))
    assert not problems, "\n".join(problems)
