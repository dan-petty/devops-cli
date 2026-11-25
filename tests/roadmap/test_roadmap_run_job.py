"""The isolation controls of the planner's sandboxed run Job (ADR 0018, #4007).

The offline tests read the committed CronJob `k8s/devops/roadmap-service/cronjob-planner-run.yaml`,
its NetworkPolicy and the Job that `build_job` makes from them: the read-only clone, the
credential-free pod and the deny-all egress. The live test, marked `k8s`, runs the three attempts in
a real cluster Job pod. A default run deselects it; `pytest -m k8s` selects it.
"""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
import yaml

from devops_cli.core.process import run_subprocess
from devops_cli.k8s.cluster_job import (
    JOB_NAMESPACE,
    PLANNER_TEMPLATE,
    build_job,
)
from tests.support.paths import REPO_ROOT

CRONJOB = REPO_ROOT / "k8s/devops/roadmap-service/cronjob-planner-run.yaml"
JOB_NAME = "devops-cli-planner-run-20261115-120000-ab12"

_PROBE = """status=0
if echo probe > /repo/.proof-write 2>/dev/null; then echo write-allowed; status=1; else echo write-denied; fi
if cat /var/run/secrets/kubernetes.io/serviceaccount/token >/dev/null 2>&1; then echo credential-allowed; status=1; else echo credential-denied; fi
if python3 -c 'import socket; socket.create_connection(("1.1.1.1", 443), timeout=3)' >/dev/null 2>&1; then echo network-allowed; status=1; else echo network-denied; fi
exit $status
"""


def _cronjob() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(CRONJOB.read_text(encoding="utf-8")))


def _planner_job() -> dict[str, Any]:
    return build_job(_cronjob(), ["--version"], JOB_NAME, template=PLANNER_TEMPLATE)


def _pod_spec(job: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], job["spec"]["template"]["spec"])


def _container(pod: dict[str, Any]) -> dict[str, Any]:
    (container,) = [
        entry for entry in pod["containers"] if entry["name"] == PLANNER_TEMPLATE.container
    ]
    return cast(dict[str, Any], container)


@pytest.mark.k8s
@pytest.mark.live("kubectl")
@pytest.mark.timeout(300)
def test_the_run_job_holds_the_three_controls() -> None:
    """Run a write, a credential read and a public connection in the planner Job pod of a real
    cluster, and assert that each fails. A person runs this test with `pytest -m k8s`."""
    reachable = run_subprocess(
        ("kubectl", "version", "--request-timeout=5s"), isolate_env=False, quiet=True
    )
    if reachable.returncode != 0:
        pytest.skip("no reachable cluster")

    job = _planner_job()
    container = _container(_pod_spec(job))
    container["command"] = ["sh", "-c", _PROBE]
    container["args"] = []
    applied = run_subprocess(
        ("kubectl", "apply", "-f", "-"), input=json.dumps(job), isolate_env=False, quiet=True
    )
    try:
        waited = run_subprocess(
            (
                "kubectl",
                "wait",
                "--for=condition=complete",
                f"job/{JOB_NAME}",
                "-n",
                JOB_NAMESPACE,
                "--timeout=180s",
            ),
            isolate_env=False,
            quiet=True,
        )
        logs = run_subprocess(
            ("kubectl", "logs", f"job/{JOB_NAME}", "-n", JOB_NAMESPACE),
            isolate_env=False,
            quiet=True,
        ).stdout
    finally:
        run_subprocess(
            ("kubectl", "delete", f"job/{JOB_NAME}", "-n", JOB_NAMESPACE, "--ignore-not-found"),
            isolate_env=False,
            quiet=True,
        )

    assert (applied.returncode, waited.returncode) == (0, 0)
    for attempt in ("write-denied", "credential-denied", "network-denied"):
        assert attempt in logs, logs
