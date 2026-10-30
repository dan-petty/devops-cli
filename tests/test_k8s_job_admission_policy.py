"""The admission policy that pins the Jobs of the roadmap Service (#2696).

The policy lives in `k8s/devops/roadmap-service/`. Each test reads what `kubectl kustomize
k8s/devops` renders, so it reads the objects that Argo CD applies. The CEL of the policy runs in
the CEL runtime of the `cel-expr-python` package, against the Job that `build_job` makes from the
rendered CronJob `devops-cli-runner` and against the same Job changed in one way. The policy uses
only standard CEL, so this runtime and the API server give the same answers.
"""

from __future__ import annotations

import copy
import functools
from collections.abc import Callable
from typing import Any

import pytest
from cel_expr_python import cel

from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE, build_job
from tests.k8s_manifests import applied_documents
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"
POLICY_NAME = "roadmap-service-jobs"
RUNNER_IMAGE = "ghcr.io/dan-petty/devops-cli/runner"
DIGEST = "sha256:" + "0" * 64
# The environment value and the label that the Service sets on the Job it makes.
SERVICE_ENV = {"DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY": "example/project"}
SERVICE_LABELS = {"implement-repo": "0123456789ab"}

_CEL = cel.NewEnv(variables={"object": cel.Type.DYN, "request": cel.Type.DYN})
Mutation = Callable[[dict[str, Any]], None]


def _object(kind: str, name: str) -> dict[str, Any]:
    (found,) = (
        document
        for document in applied_documents(DEVOPS_DIR)
        if document["kind"] == kind and document["metadata"]["name"] == name
    )
    return found


def _service_user() -> str:
    """The user the Service acts as: the subject of the RoleBinding that gives it the Role."""
    (subject,) = _object("RoleBinding", POLICY_NAME)["subjects"]
    return f"system:serviceaccount:{subject['namespace']}:{subject['name']}"


def _holds(expression: str, data: dict[str, Any]) -> bool:
    """True only when the expression is a bool and true. An error is not true, as with
    `failurePolicy: Fail`, where an expression that errors refuses the request."""
    result = _CEL.compile(expression).eval(data=data)
    return bool(result.type() == cel.Type.BOOL and result.value() is True)


def _refusals(job: dict[str, Any], user: str | None = None) -> list[str]:
    """The messages of the validations that refuse the Job, or none when the policy does not
    apply to the user."""
    spec = _object("ValidatingAdmissionPolicy", POLICY_NAME)["spec"]
    data = {"object": job, "request": {"userInfo": {"username": user or _service_user()}}}
    if not all(_holds(condition["expression"], data) for condition in spec["matchConditions"]):
        return []
    return [rule["message"] for rule in spec["validations"] if not _holds(rule["expression"], data)]


@functools.cache
def _template_job() -> dict[str, Any]:
    cronjob = _object("CronJob", "devops-cli-runner")
    return build_job(
        cronjob,
        ["roadmap", "implement", "--repo", "example/project", "--item", "7", "--confirm"],
        "devops-cli-runner-20261030-120000-ab12",
        template=RUNNER_TEMPLATE,
        env=SERVICE_ENV,
        labels=SERVICE_LABELS,
    )


def _changed(mutate: Mutation) -> dict[str, Any]:
    job = copy.deepcopy(_template_job())
    mutate(job)
    return job


def _pod(job: dict[str, Any]) -> dict[str, Any]:
    pod: dict[str, Any] = job["spec"]["template"]["spec"]
    return pod


def _container(job: dict[str, Any]) -> dict[str, Any]:
    container: dict[str, Any] = _pod(job)["containers"][0]
    return container


def _deadline() -> int:
    deadline: int = _object("CronJob", "devops-cli-runner")["spec"]["jobTemplate"]["spec"][
        "activeDeadlineSeconds"
    ]
    return deadline


def _set_image(image: str) -> Mutation:
    return lambda job: _container(job).update(image=image)


def _set_pod(**fields: object) -> Mutation:
    return lambda job: _pod(job).update(fields)


def _drop_pod_field(name: str) -> Mutation:
    return lambda job: _pod(job).pop(name)


def _set_spec(**fields: object) -> Mutation:
    return lambda job: job["spec"].update(fields)


def _drop_spec_field(name: str) -> Mutation:
    return lambda job: job["spec"].pop(name)


def _add_container(job: dict[str, Any]) -> None:
    _pod(job)["containers"].append({**copy.deepcopy(_container(job)), "name": "second"})


def _add_init_container(job: dict[str, Any]) -> None:
    _pod(job)["initContainers"] = [{**copy.deepcopy(_container(job)), "name": "init"}]


def _add_env_from(source: dict[str, Any]) -> Mutation:
    return lambda job: _container(job)["envFrom"].append(source)


def _add_env_value_from(job: dict[str, Any]) -> None:
    secret_key = {"secretKeyRef": {"name": "other", "key": "token"}}
    _container(job)["env"].append({"name": "OTHER", "valueFrom": secret_key})


def _add_volume(volume: dict[str, Any]) -> Mutation:
    return lambda job: _pod(job)["volumes"].append(volume)


def _rename_config_map(job: dict[str, Any]) -> None:
    config = next(volume for volume in _pod(job)["volumes"] if volume["name"] == "config")
    config["configMap"]["name"] = "other"


def _host_path_for_tmp(job: dict[str, Any]) -> None:
    tmp = next(volume for volume in _pod(job)["volumes"] if volume["name"] == "tmp")
    del tmp["emptyDir"]
    tmp["hostPath"] = {"path": "/"}


def test_the_job_from_the_runner_template_passes_in_every_image_form() -> None:
    forms = (
        RUNNER_IMAGE,
        f"{RUNNER_IMAGE}:latest",
        f"{RUNNER_IMAGE}@{DIGEST}",
        f"{RUNNER_IMAGE}:latest@{DIGEST}",
    )

    assert [_refusals(_changed(_set_image(image))) for image in forms] == [[]] * len(forms)


@pytest.mark.parametrize(
    ("mutate", "rule"),
    [
        pytest.param(_set_image("ghcr.io/dan-petty/devops-cli/service"), "image", id="service"),
        pytest.param(_set_image(f"{RUNNER_IMAGE}-evil"), "image", id="name-prefix"),
        pytest.param(_set_image(f"{RUNNER_IMAGE}2:latest"), "image", id="name-prefix-and-tag"),
        pytest.param(_set_image(f"docker.io/{RUNNER_IMAGE}"), "image", id="other-registry"),
        pytest.param(_add_container, "one container", id="second-container"),
        pytest.param(_add_init_container, "one container", id="init-container"),
        pytest.param(_set_pod(serviceAccountName="default"), "ServiceAccount", id="other-account"),
        pytest.param(_drop_pod_field("serviceAccountName"), "ServiceAccount", id="no-account"),
        pytest.param(_set_pod(automountServiceAccountToken=True), "token", id="token-mounts"),
        pytest.param(_drop_pod_field("automountServiceAccountToken"), "token", id="token-not-set"),
        pytest.param(_add_env_from({"configMapRef": {"name": "x"}}), "envFrom", id="config-map"),
        pytest.param(_add_env_from({"secretRef": {"name": "x"}}), "envFrom", id="other-secret"),
        pytest.param(_add_env_value_from, "valueFrom", id="env-value-from"),
        pytest.param(_add_volume({"name": "x", "hostPath": {"path": "/"}}), "volumes", id="host"),
        pytest.param(_add_volume({"name": "x", "secret": {"secretName": "x"}}), "volumes", id="s"),
        pytest.param(_add_volume({"name": "x", "emptyDir": {}}), "volumes", id="unnamed-volume"),
        pytest.param(_rename_config_map, "volumes", id="other-config-map"),
        pytest.param(_host_path_for_tmp, "volumes", id="tmp-from-host"),
        pytest.param(_set_pod(hostNetwork=True), "host namespace", id="host-network"),
        pytest.param(_set_pod(hostPID=True), "host namespace", id="host-pid"),
        pytest.param(_set_pod(hostIPC=True), "host namespace", id="host-ipc"),
        pytest.param(_set_spec(backoffLimit=1), "backoffLimit", id="retry"),
        pytest.param(_drop_spec_field("backoffLimit"), "backoffLimit", id="retry-not-set"),
        pytest.param(_drop_spec_field("activeDeadlineSeconds"), "deadline", id="no-deadline"),
    ],
)
def test_a_job_that_breaks_one_rule_is_refused_by_that_rule(mutate: Mutation, rule: str) -> None:
    refused = _refusals(_changed(mutate))

    assert len(refused) == 1
    assert rule in refused[0]


def test_a_job_that_runs_longer_than_the_template_is_refused() -> None:
    longer = _changed(_set_spec(activeDeadlineSeconds=_deadline() + 1))
    as_long = _changed(_set_spec(activeDeadlineSeconds=_deadline()))

    assert (len(_refusals(longer)), _refusals(as_long)) == (1, [])


@pytest.mark.parametrize(
    "user",
    [
        "kubernetes-admin",
        "system:serviceaccount:argocd:argocd-application-controller",
        "system:serviceaccount:kube-system:cronjob-controller",
        "system:serviceaccount:other:roadmap-service",
    ],
)
def test_a_job_of_another_identity_is_not_refused(user: str) -> None:
    broken = _changed(_set_image("example.com/other/image"))

    assert (len(_refusals(broken)), _refusals(broken, user)) == (1, [])


def test_the_policy_covers_the_create_and_update_of_jobs_in_namespace_devops_and_fails_closed() -> (
    None
):
    policy = _object("ValidatingAdmissionPolicy", POLICY_NAME)["spec"]
    binding = _object("ValidatingAdmissionPolicyBinding", POLICY_NAME)["spec"]

    assert (
        policy["matchConstraints"]["resourceRules"],
        policy["failurePolicy"],
        binding["policyName"],
        binding["validationActions"],
        binding["matchResources"],
    ) == (
        [
            {
                "apiGroups": ["batch"],
                "apiVersions": ["v1"],
                "operations": ["CREATE", "UPDATE"],
                "resources": ["jobs"],
            }
        ],
        "Fail",
        POLICY_NAME,
        ["Deny", "Audit"],
        {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "devops"}}},
    )


def test_the_expressions_use_only_standard_cel() -> None:
    """The runtime here compiles standard CEL and nothing of the Kubernetes extensions, so an
    expression that it compiles gives the same answer in the API server."""
    spec = _object("ValidatingAdmissionPolicy", POLICY_NAME)["spec"]
    expressions = [item["expression"] for item in (*spec["matchConditions"], *spec["validations"])]

    assert len(expressions) > 1
    for expression in expressions:
        _CEL.compile(expression)
