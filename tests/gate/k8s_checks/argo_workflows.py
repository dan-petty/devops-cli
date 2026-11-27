"""The Argo objects of the product base pass `argo lint --offline` (#5289).

The Argo Workflows controller v4 refuses a CronWorkflow with the singular `spec.schedule`
(`SpecError`, "cron workflow must have at least one schedule"), and it does not read the singular
`synchronization.mutex` or `synchronization.semaphore`. The installed CRDs keep unknown fields, so
the API server and Argo CD accept such an object, and only the log of the controller shows it.
`argo lint --offline` decodes each Argo object strictly, as the controller does, and names each
field that the controller does not know, at the spec level, in a template and in the
`workflowSpec` of a CronWorkflow. The `argo` command comes from the devtools image, as the
controller comes from the same Argo release.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


# An offline lint of a few objects takes less than a second. The bound stops a hung binary.
ARGO_LINT_TIMEOUT_SECONDS = 60


def argo_lint_problems(documents: Iterable[dict[str, Any]]) -> list[str]:
    """Each problem that `argo lint --offline` finds in the Argo objects of `documents`, one line
    for each, such as `in "rag-ingest" (CronWorkflow): strict decoding error: unknown field
    "spec.schedule"`. The command skips each object that is not of the group `argoproj.io`."""
    with tempfile.TemporaryDirectory(prefix="argo-lint-") as folder:
        manifest = Path(folder) / "objects.yaml"
        manifest.write_text(yaml.safe_dump_all(list(documents)), encoding="utf-8")
        result = subprocess.run(
            ["argo", "lint", "--offline", "--output", "simple", str(manifest)],
            check=False,
            capture_output=True,
            text=True,
            timeout=ARGO_LINT_TIMEOUT_SECONDS,
        )
    prefix = f"{manifest}: "
    problems = [line.removeprefix(prefix) for line in result.stdout.splitlines() if prefix in line]
    # A lint that fails with no line of an object did not read the objects, such as on a YAML
    # error: its output is the problem.
    if result.returncode != 0 and not problems:
        problems = [f"argo lint exited {result.returncode}: {result.stderr or result.stdout}"]
    return problems


def _argo(kind: str, name: str, **spec: Any) -> dict[str, Any]:
    """An Argo object of `kind` named `name` in namespace `fixture` with the fields `spec`."""
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": kind,
        "metadata": {"name": name, "namespace": "fixture"},
        "spec": spec,
    }


_CRON = "*/3 * * * *"
_MUTEX = {"name": "fixture"}
_SEMAPHORE = {"configMapKeyRef": {"name": "fixture", "key": "workflow"}}
_PLURAL_LOCKS = {"mutexes": [_MUTEX], "semaphores": [_SEMAPHORE]}
_REF = {"workflowTemplateRef": {"name": "fixture-template"}}


def _template(**synchronization: Any) -> dict[str, Any]:
    """The WorkflowTemplate `fixture-template` with one container template `main`. The keys of
    `synchronization` go to the spec, and the key `main` goes to the template `main`."""
    main = {"name": "main", "container": {"image": "example.com/fixture", "command": ["true"]}}
    if "main" in synchronization:
        main["synchronization"] = synchronization.pop("main")
    spec: dict[str, Any] = {"entrypoint": "main", "templates": [main]}
    if synchronization:
        spec["synchronization"] = synchronization
    return _argo("WorkflowTemplate", "fixture-template", **spec)


@pytest.mark.parametrize(
    ("document", "named", "field"),
    [
        pytest.param(
            _argo("CronWorkflow", "fixture-cron", schedule=_CRON, workflowSpec=_REF),
            '"fixture-cron" (CronWorkflow)',
            "spec.schedule",
            id="cron-schedule",
        ),
        pytest.param(
            _template(mutex=_MUTEX),
            '"fixture-template" (WorkflowTemplate)',
            "spec.synchronization.mutex",
            id="template-mutex",
        ),
        pytest.param(
            _template(main={"mutex": _MUTEX}),
            '"fixture-template" (WorkflowTemplate)',
            "spec.templates[0].synchronization.mutex",
            id="template-step-mutex",
        ),
        pytest.param(
            _argo("Workflow", "fixture-run", synchronization={"semaphore": _SEMAPHORE}, **_REF),
            '"fixture-run" (Workflow)',
            "spec.synchronization.semaphore",
            id="workflow-semaphore",
        ),
        pytest.param(
            _argo(
                "CronWorkflow",
                "fixture-cron",
                schedules=[_CRON],
                workflowSpec={"synchronization": {"semaphore": _SEMAPHORE}, **_REF},
            ),
            '"fixture-cron" (CronWorkflow)',
            "spec.workflowSpec.synchronization.semaphore",
            id="cron-workflow-spec-semaphore",
        ),
    ],
)
def check_the_lint_names_each_singular_field(
    document: dict[str, Any], named: str, field: str
) -> None:
    # The template that the reference names comes with each object, so the offline lint finds it.
    documents = [document] if document["kind"] == "WorkflowTemplate" else [document, _template()]

    (problem,) = argo_lint_problems(documents)
    assert (named in problem, f'unknown field "{field}"' in problem) == (True, True), problem


def check_the_lint_accepts_the_plural_fields_and_a_cronjob() -> None:
    documents = [
        _argo(
            "CronWorkflow",
            "fixture-cron",
            schedules=[_CRON],
            workflowSpec={"synchronization": _PLURAL_LOCKS, **_REF},
        ),
        _template(main=_PLURAL_LOCKS, **_PLURAL_LOCKS),
        _argo("Workflow", "fixture-run", synchronization=_PLURAL_LOCKS, **_REF),
        # A CronJob holds `spec.schedule` too, and it is no Argo object.
        {
            "apiVersion": "batch/v1",
            "kind": "CronJob",
            "metadata": {"name": "fixture-job", "namespace": "fixture"},
            "spec": {"schedule": _CRON},
        },
    ]

    assert argo_lint_problems(documents) == []


def check_each_argo_object_of_the_product_base_passes_the_offline_lint() -> None:
    """Each Argo object that `kubectl apply -k k8s/devops` applies uses `schedules`, `mutexes`
    and `semaphores`, the fields that the controller v4 reads, and no other field that it does
    not know (#5289)."""
    problems = argo_lint_problems(applied_documents(DEVOPS_DIR))
    assert not problems, "\n".join(problems)
