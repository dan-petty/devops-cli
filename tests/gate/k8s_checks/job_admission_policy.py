"""The admission policy of the Jobs of the runner service (#2164)."""

from __future__ import annotations

import copy
import functools
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from cel_expr_python import cel

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS,
    CONST_ROADMAP_STAGE_JOB_SECRET_KEYS,
)
from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.cluster_job import (
    RUNNER_TEMPLATE,
    STAGE_TEMPLATE,
    build_job,
    stage_job_env,
    stage_job_labels,
    stage_job_name,
)
from devops_cli.roadmap.implement.implement_size import RUNNER_SIZES, WORKERS_VARIABLE, RunnerSize
from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


POLICY_NAME = "roadmap-service-jobs"


DELETE_POLICY_NAME = "roadmap-service-job-deletes"


RUNNER_IMAGE = "ghcr.io/dan-petty/devops-cli/runner"


DIGEST = "sha256:" + "0" * 64


# The environment value and the label that the Service sets on the Job it makes.
SERVICE_ENV = {"DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY": "example/project"}


SERVICE_LABELS = {"implement-repo": "0123456789ab"}


_CEL = cel.NewEnv(
    variables={
        "object": cel.Type.DYN,
        "oldObject": cel.Type.DYN,
        "request": cel.Type.DYN,
        "variables": cel.Type.DYN,
    }
)


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


def _value(expression: str, data: dict[str, Any]) -> Any:
    """The value of the expression, or None when it errors."""
    result = _CEL.compile(expression).eval(data=data)
    return result.value() if result.type() != cel.Type.ERROR else None


def _policy_refusals(
    name: str,
    *,
    job: dict[str, Any] | None,
    old: dict[str, Any] | None = None,
    user: str | None = None,
) -> list[str]:
    """The messages of the validations of policy `name` that refuse the request, or none when the
    policy does not apply to the user. Each variable of the policy is computed first, in order,
    as the API server does, so a validation reads it as `variables.<name>`."""
    spec = _object("ValidatingAdmissionPolicy", name)["spec"]
    data: dict[str, Any] = {
        "object": job,
        "oldObject": old,
        "request": {"userInfo": {"username": user or _service_user()}},
    }
    if not all(_holds(condition["expression"], data) for condition in spec["matchConditions"]):
        return []
    variables: dict[str, Any] = {}
    for variable in spec.get("variables", []):
        variables[variable["name"]] = _value(
            variable["expression"], {**data, "variables": variables}
        )
    data["variables"] = variables
    return [rule["message"] for rule in spec["validations"] if not _holds(rule["expression"], data)]


def _refusals(job: dict[str, Any], user: str | None = None) -> list[str]:
    """The messages of the validations that refuse the create of the Job, or none when the policy
    does not apply to the user."""
    return _policy_refusals(POLICY_NAME, job=job, user=user)


def _delete_refusals(job: dict[str, Any], user: str | None = None) -> list[str]:
    """The messages of the validations that refuse the delete of the Job."""
    return _policy_refusals(DELETE_POLICY_NAME, job=None, old=job, user=user)


def _job_of_size(size: RunnerSize | None, memory_limit: str = "8Gi") -> dict[str, Any]:
    """The Job the Service makes for a row of the size table, or the Job of the bare template."""
    cronjob = _object("CronJob", "devops-cli-runner")
    return build_job(
        cronjob,
        ["roadmap", "implement", "--repo", "example/project", "--item", "7", "--confirm"],
        "devops-cli-runner-20261030-120000-ab12",
        template=RUNNER_TEMPLATE,
        env={**SERVICE_ENV, **(size.env if size else {})},
        labels=SERVICE_LABELS,
        resources=size.resources(memory_limit) if size else None,
    )


@functools.cache
def _template_job() -> dict[str, Any]:
    """The Job of the Service for the small row."""
    return _job_of_size(RUNNER_SIZES[0])


def _changed(*mutations: Mutation) -> dict[str, Any]:
    job = copy.deepcopy(_template_job())
    for mutate in mutations:
        mutate(job)
    return job


def _pod(job: dict[str, Any]) -> dict[str, Any]:
    pod: dict[str, Any] = job["spec"]["template"]["spec"]
    return pod


def _container(job: dict[str, Any]) -> dict[str, Any]:
    container: dict[str, Any] = _pod(job)["containers"][0]
    return container


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


def _set_pod_label(value: str) -> Mutation:
    return lambda job: job["spec"]["template"]["metadata"]["labels"].update(
        {"app.kubernetes.io/name": value}
    )


def _drop_pod_labels(job: dict[str, Any]) -> None:
    del job["spec"]["template"]["metadata"]["labels"]


def _set_resources(
    *, cpu: str | None = None, memory: str | None = None, limit: str | None = None
) -> Mutation:
    """Replace the CPU of the request and the limit, the memory request or the memory limit."""

    def mutate(job: dict[str, Any]) -> None:
        resources = _container(job)["resources"]
        if cpu is not None:
            resources["requests"]["cpu"] = cpu
            resources["limits"]["cpu"] = cpu
        if memory is not None:
            resources["requests"]["memory"] = memory
        if limit is not None:
            resources["limits"]["memory"] = limit

    return mutate


def _set_workers(value: str) -> Mutation:
    def mutate(job: dict[str, Any]) -> None:
        for entry in _container(job)["env"]:
            if entry["name"] == WORKERS_VARIABLE:
                entry["value"] = value

    return mutate


def _drop_workers(job: dict[str, Any]) -> None:
    container = _container(job)
    container["env"] = [e for e in container["env"] if e["name"] != WORKERS_VARIABLE]


def _drop_memory_limit(job: dict[str, Any]) -> None:
    del _container(job)["resources"]["limits"]["memory"]


def _drop_resources(job: dict[str, Any]) -> None:
    del _container(job)["resources"]


def _set_container(**fields: object) -> Mutation:
    return lambda job: _container(job).update(fields)


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


def check_the_job_from_the_runner_template_passes_in_every_image_form() -> None:
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
        pytest.param(_set_pod_label("roadmap-service"), "label", id="label-of-the-service"),
        pytest.param(_set_pod_label("traefik"), "label", id="label-of-another-pod"),
        pytest.param(_drop_pod_labels, "label", id="no-labels"),
        pytest.param(_set_pod(priorityClassName="system-node-critical"), "priority", id="priority"),
        pytest.param(_set_pod(nodeName="node-1"), "node", id="node-name"),
        pytest.param(
            _set_pod(imagePullSecrets=[{"name": "x"}]), "imagePullSecrets", id="pull-secret"
        ),
        pytest.param(_set_container(command=["sh", "-c", "id"]), "command", id="command"),
        pytest.param(_set_spec(manualSelector=True), "manualSelector", id="manual-selector"),
        pytest.param(_set_spec(completions=2), "once", id="completions"),
        pytest.param(_set_spec(parallelism=2), "once", id="parallelism"),
        pytest.param(_set_spec(backoffLimit=1), "backoffLimit", id="retry"),
        pytest.param(_drop_spec_field("backoffLimit"), "backoffLimit", id="retry-not-set"),
        pytest.param(_drop_spec_field("activeDeadlineSeconds"), "deadline", id="no-deadline"),
        pytest.param(_set_resources(cpu="3"), "size table", id="cpu-off-the-table"),
        pytest.param(_set_resources(memory="7Gi"), "size table", id="memory-off-the-table"),
        pytest.param(_set_resources(memory="6Gi"), "size table", id="large-memory-small-cpu"),
        pytest.param(_set_resources(cpu="4"), "size table", id="large-cpu-small-memory"),
        pytest.param(_set_workers("2"), "size table", id="workers-differ-from-cpu"),
        pytest.param(_drop_workers, "size table", id="no-worker-count"),
        pytest.param(_drop_memory_limit, "size table", id="no-memory-limit"),
        pytest.param(_drop_resources, "size table", id="no-resources"),
    ],
)
def check_a_job_that_breaks_one_rule_is_refused_by_that_rule(mutate: Mutation, rule: str) -> None:
    refused = _refusals(_changed(mutate))

    assert len(refused) == 1
    assert rule in refused[0]


def check_the_job_of_every_row_of_the_size_table_passes_also_with_a_raised_memory_limit() -> None:
    jobs = [_job_of_size(row, limit) for row in RUNNER_SIZES for limit in ("8Gi", "12Gi")]

    assert [_refusals(job) for job in jobs] == [[]] * len(jobs)


def check_the_policy_admits_exactly_the_cpu_and_memory_pairs_of_the_size_table() -> None:
    """Each pair from a grid that holds the rows and the values near them: only the table passes."""
    cpus = sorted({row.cpu for row in RUNNER_SIZES} | {"0.5", "2", "3", "5", "8"})
    memories = sorted({row.memory for row in RUNNER_SIZES} | {"1Gi", "4Gi", "5Gi", "7Gi", "8Gi"})

    admitted = {
        (cpu, memory)
        for cpu in cpus
        for memory in memories
        if not _refusals(_changed(_set_resources(cpu=cpu, memory=memory), _set_workers(cpu)))
    }

    assert admitted == {(row.cpu, row.memory) for row in RUNNER_SIZES}


def check_a_job_with_the_size_of_the_template_is_refused() -> None:
    refused = _refusals(_job_of_size(None))

    assert len(refused) == 1
    assert "size table" in refused[0]


def check_a_job_that_names_the_default_values_passes() -> None:
    explicit = _changed(_set_spec(completions=1, parallelism=1, manualSelector=False))

    assert _refusals(explicit) == []


def check_a_job_that_runs_longer_than_the_cap_is_refused() -> None:
    longer = _changed(
        _set_spec(activeDeadlineSeconds=CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS + 1)
    )
    as_long = _changed(
        _set_spec(activeDeadlineSeconds=CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS)
    )

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
def check_a_job_of_another_identity_is_not_refused(user: str) -> None:
    broken = _changed(_set_image("example.com/other/image"))

    assert (len(_refusals(broken)), _refusals(broken, user)) == (1, [])


def check_the_policy_covers_the_create_and_update_of_jobs_in_namespace_devops_and_fails_closed() -> (
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


def check_the_match_condition_names_the_user_of_the_role_binding() -> None:
    spec = _object("ValidatingAdmissionPolicy", POLICY_NAME)["spec"]

    assert [condition["expression"] for condition in spec["matchConditions"]] == [
        f'request.userInfo.username == "{_service_user()}"'
    ]


@pytest.mark.parametrize("name", [POLICY_NAME, DELETE_POLICY_NAME])
def check_the_expressions_use_only_standard_cel(name: str) -> None:
    """The runtime here compiles standard CEL and nothing of the Kubernetes extensions, so an
    expression that it compiles gives the same answer in the API server."""
    spec = _object("ValidatingAdmissionPolicy", name)["spec"]
    expressions = [
        item["expression"]
        for item in (*spec["matchConditions"], *spec.get("variables", []), *spec["validations"])
    ]

    assert len(expressions) > 1
    for expression in expressions:
        _CEL.compile(expression)


# ── The stage Job (#5483) ─────────────────────────────────────────────────────

SERVICE_IMAGE = "ghcr.io/dan-petty/devops-cli/service"


STAGE_REPO = RepoRef("example/project")


STAGE_DEADLINE = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)


def _stage_job(item: int = 7) -> dict[str, Any]:
    """The Job that the Service makes from CronJob roadmap-stage for one item."""
    name = stage_job_name(STAGE_REPO, item, "0123456789abcdef")
    return build_job(
        _object("CronJob", STAGE_TEMPLATE.cronjob),
        ["roadmap", "stage", "--repo", STAGE_REPO.display, "--job-item", str(item), "--confirm"],
        name,
        template=STAGE_TEMPLATE,
        env=stage_job_env(STAGE_REPO, name, STAGE_DEADLINE),
        labels=stage_job_labels(STAGE_REPO, item),
    )


def _stage_changed(*mutations: Mutation) -> dict[str, Any]:
    job = _stage_job()
    for mutate in mutations:
        mutate(job)
    return job


def _add_secret_key(secret: str, key: str, name: str | None = None) -> Mutation:
    entry = {"name": name or key, "valueFrom": {"secretKeyRef": {"name": secret, "key": key}}}
    return lambda job: _container(job)["env"].append(entry)


def _add_env_source(source: dict[str, Any]) -> Mutation:
    return lambda job: _container(job)["env"].append({"name": "OTHER", "valueFrom": source})


def _set_env_from(source: dict[str, Any]) -> Mutation:
    return lambda job: _container(job).update(envFrom=[source])


def _set_component(value: str | None) -> Mutation:
    def mutate(job: dict[str, Any]) -> None:
        labels = job["spec"]["template"]["metadata"]["labels"]
        labels.pop("app.kubernetes.io/component", None)
        if value is not None:
            labels["app.kubernetes.io/component"] = value

    return mutate


def _stage_retries(job: dict[str, Any]) -> None:
    """The backoff limit and the pod failure policy of a stage Job, on any Job."""
    stage = _stage_job()["spec"]
    job["spec"].update(
        backoffLimit=stage["backoffLimit"], podFailurePolicy=stage["podFailurePolicy"]
    )


def _ignore_every_exit(job: dict[str, Any]) -> None:
    job["spec"]["podFailurePolicy"]["rules"].append(
        {"action": "Ignore", "onExitCodes": {"operator": "NotIn", "values": [0]}}
    )


def check_the_stage_job_from_the_template_passes_in_every_image_form() -> None:
    forms = (
        SERVICE_IMAGE,
        f"{SERVICE_IMAGE}:latest",
        f"{SERVICE_IMAGE}@{DIGEST}",
        f"{SERVICE_IMAGE}:latest@{DIGEST}",
    )

    assert [_refusals(_stage_changed(_set_image(image))) for image in forms] == [[]] * len(forms)


@pytest.mark.parametrize(
    ("mutate", "rule"),
    [
        pytest.param(_set_image(RUNNER_IMAGE), "image", id="runner-image"),
        pytest.param(_set_image(f"{SERVICE_IMAGE}-evil"), "image", id="name-prefix"),
        pytest.param(
            _set_env_from({"secretRef": {"name": "devops-cli"}}), "envFrom", id="env-from"
        ),
        pytest.param(
            _add_secret_key("devops-cli", "DEVOPS_CLI_VALKEY_PASSWORD"), "valueFrom", id="4th-key"
        ),
        pytest.param(
            _add_secret_key("other", "DEVOPS_CLI_AI_API_KEY"), "valueFrom", id="other-secret"
        ),
        pytest.param(
            _add_secret_key("devops-cli", "DEVOPS_CLI_AI_API_KEY", "OTHER"),
            "valueFrom",
            id="key-in-another-variable",
        ),
        pytest.param(
            _add_env_source({"fieldRef": {"fieldPath": "metadata.namespace"}}),
            "valueFrom",
            id="field-ref",
        ),
        pytest.param(
            _add_env_source({"configMapKeyRef": {"name": "devops-cli-config", "key": "x"}}),
            "valueFrom",
            id="config-map-key",
        ),
        pytest.param(_set_pod(automountServiceAccountToken=True), "token", id="token-mounts"),
        pytest.param(_set_pod(serviceAccountName="default"), "ServiceAccount", id="other-account"),
        pytest.param(_drop_spec_field("podFailurePolicy"), "backoffLimit", id="no-failure-policy"),
        pytest.param(_set_spec(backoffLimit=3), "backoffLimit", id="three-retries"),
        pytest.param(_ignore_every_exit, "backoffLimit", id="ignore-every-exit"),
        pytest.param(
            _set_spec(activeDeadlineSeconds=CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS + 1),
            "deadline",
            id="deadline-over-the-cap",
        ),
        pytest.param(_set_resources(cpu="2"), "size", id="other-cpu"),
        pytest.param(_set_resources(limit="4Gi"), "size", id="other-memory-limit"),
        pytest.param(_set_component(None), "label", id="no-component"),
        pytest.param(_set_component("roadmap-implement"), "label", id="other-component"),
    ],
)
def check_a_stage_job_that_breaks_one_rule_is_refused_by_that_rule(
    mutate: Mutation, rule: str
) -> None:
    refused = _refusals(_stage_changed(mutate))

    assert len(refused) == 1, refused
    assert rule in refused[0]


@pytest.mark.parametrize(
    ("mutate", "rule"),
    [
        pytest.param(_stage_retries, "backoffLimit", id="stage-retries"),
        pytest.param(_set_spec(backoffLimit=2), "backoffLimit", id="two-retries"),
        pytest.param(_set_component("roadmap-stage"), "label", id="stage-component"),
    ],
)
def check_a_runner_job_with_a_rule_of_the_stage_job_is_refused(mutate: Mutation, rule: str) -> None:
    refused = _refusals(_changed(mutate))

    assert len(refused) == 1, refused
    assert rule in refused[0]


def _drop_secret_keys(job: dict[str, Any]) -> None:
    container = _container(job)
    container["env"] = [entry for entry in container["env"] if "valueFrom" not in entry]


def check_the_stage_job_may_read_exactly_the_three_keys_of_the_secret() -> None:
    """The policy admits each key of `CONST_ROADMAP_STAGE_JOB_SECRET_KEYS`, which the template
    reads, and refuses a key of the Secret that a stage Job does not need."""
    keys = (*CONST_ROADMAP_STAGE_JOB_SECRET_KEYS, "DEVOPS_CLI_MCP_IMPLEMENT_TOKEN")

    admitted = [
        key
        for key in keys
        if not _refusals(_stage_changed(_drop_secret_keys, _add_secret_key("devops-cli", key)))
    ]

    assert admitted == list(CONST_ROADMAP_STAGE_JOB_SECRET_KEYS)


def check_the_service_may_delete_a_stage_job_and_no_other_job() -> None:
    runner = _template_job()
    stage = _stage_job()

    assert (
        _delete_refusals(stage),
        len(_delete_refusals(runner)),
        _delete_refusals(runner, "kubernetes-admin"),
    ) == ([], 1, [])


def check_the_delete_policy_covers_the_delete_of_jobs_in_namespace_devops_and_fails_closed() -> (
    None
):
    policy = _object("ValidatingAdmissionPolicy", DELETE_POLICY_NAME)["spec"]
    binding = _object("ValidatingAdmissionPolicyBinding", DELETE_POLICY_NAME)["spec"]

    assert (
        policy["matchConstraints"]["resourceRules"],
        policy["failurePolicy"],
        [condition["expression"] for condition in policy["matchConditions"]],
        binding["policyName"],
        binding["validationActions"],
        binding["matchResources"],
    ) == (
        [
            {
                "apiGroups": ["batch"],
                "apiVersions": ["v1"],
                "operations": ["DELETE"],
                "resources": ["jobs"],
            }
        ],
        "Fail",
        [f'request.userInfo.username == "{_service_user()}"'],
        DELETE_POLICY_NAME,
        ["Deny", "Audit"],
        {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "devops"}}},
    )
