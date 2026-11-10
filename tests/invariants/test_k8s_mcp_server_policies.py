"""The NetworkPolicies of the MCP server admit the pods that call it (#4355).

The pods that call the server are the roadmap Service and the Job pods that `build_job` makes. The
policies select pods by the label `app.kubernetes.io/name`. A Job pod carries the value that
`build_job` sets, not the value of the CronJob template, so the policies must name that value.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.k8s.cluster_job import (
    JOB_NAME_LABEL,
    JOB_NAME_LABEL_VALUE,
    RUNNER_TEMPLATE,
    build_job,
)
from tests.support.k8s_tree import manifests

NAME_LABEL = "app.kubernetes.io/name"
SERVICE_NAME = "roadmap-service"
SERVER_NAME = "mcp-server"
SERVER_PORT = 8001


def _manifest(kind: str, name: str) -> dict[str, Any]:
    found = [
        document
        for _, document in manifests()
        if document["kind"] == kind and document["metadata"]["name"] == name
    ]
    assert len(found) == 1, f"expected one {kind} {name}, found {len(found)}"
    return found[0]


def _ingress_client_names() -> set[str]:
    rules = _manifest("NetworkPolicy", "mcp-server-ingress")["spec"]["ingress"]
    assert len(rules) == 1
    return {peer["podSelector"]["matchLabels"][NAME_LABEL] for peer in rules[0]["from"]}


def _egress_client_names() -> set[str]:
    selector = _manifest("NetworkPolicy", "mcp-server-clients")["spec"]["podSelector"]
    assert "matchLabels" not in selector
    (expression,) = selector["matchExpressions"]
    assert (expression["key"], expression["operator"]) == (NAME_LABEL, "In")
    return set(expression["values"])


def _job_pod_name_label() -> str:
    cronjob = _manifest("CronJob", "devops-cli-runner")
    job = build_job(cronjob, ["--version"], "probe", template=RUNNER_TEMPLATE)
    return job["spec"]["template"]["metadata"]["labels"][JOB_NAME_LABEL]


def test_the_policies_admit_the_label_of_a_job_pod() -> None:
    assert (
        JOB_NAME_LABEL_VALUE in _ingress_client_names(),
        JOB_NAME_LABEL_VALUE in _egress_client_names(),
    ) == (True, True)


def test_the_policies_admit_the_service_and_the_label_that_build_job_sets_and_no_other() -> None:
    expected = {SERVICE_NAME, _job_pod_name_label()}
    assert (_ingress_client_names(), _egress_client_names()) == (expected, expected)


def test_the_label_of_a_job_pod_is_the_label_that_the_admission_policy_requires() -> None:
    policy = _manifest("ValidatingAdmissionPolicy", "roadmap-service-jobs")
    required = [
        validation["expression"]
        for validation in policy["spec"]["validations"]
        if "object.spec.template.metadata.labels" in validation["expression"]
    ]
    assert [f'["{NAME_LABEL}"] == "{_job_pod_name_label()}"' in e for e in required] == [True]


def test_ingress_admits_only_tcp_8001_to_the_server_pods() -> None:
    policy = _manifest("NetworkPolicy", "mcp-server-ingress")["spec"]
    (rule,) = policy["ingress"]
    assert (
        policy["podSelector"],
        policy["policyTypes"],
        rule["ports"],
    ) == (
        {"matchLabels": {NAME_LABEL: SERVER_NAME}},
        ["Ingress"],
        [{"protocol": "TCP", "port": SERVER_PORT}],
    )


def test_egress_admits_only_tcp_8001_to_the_server_pods() -> None:
    policy = _manifest("NetworkPolicy", "mcp-server-clients")["spec"]
    (rule,) = policy["egress"]
    assert (
        policy["policyTypes"],
        rule["to"],
        rule["ports"],
    ) == (
        ["Egress"],
        [{"podSelector": {"matchLabels": {NAME_LABEL: SERVER_NAME}}}],
        [{"protocol": "TCP", "port": SERVER_PORT}],
    )


@pytest.mark.parametrize("name", ["mcp-server-ingress", "mcp-server-clients"])
def test_a_policy_of_the_server_names_no_namespace_and_no_address(name: str) -> None:
    text = repr(_manifest("NetworkPolicy", name)["spec"])
    assert ("namespaceSelector" in text, "ipBlock" in text) == (False, False)
