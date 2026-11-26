"""The admission policy of the Jobs of the runner service (#2164)."""

from __future__ import annotations

import copy
import functools
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from cel_expr_python import cel

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS_AT,
    CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS,
    CONST_ROADMAP_STAGE_JOB_DEADLINE_SECONDS,
    CONST_ROADMAP_STAGE_JOB_SECRET_KEYS,
)
from devops_cli.config.settings import load_settings
from devops_cli.github.repo_ref import RepoRef, ServiceRow
from devops_cli.k8s.cluster_job import (
    RUNNER_TEMPLATE,
    STAGE_TEMPLATE,
    JobTemplate,
    build_job,
    stage_job_env,
    stage_job_labels,
    stage_job_name,
)
from devops_cli.roadmap.fix_checks_row import FixDue, fix_unit
from devops_cli.roadmap.implement.implement_size import RUNNER_SIZES, WORKERS_VARIABLE, RunnerSize
from devops_cli.roadmap.job_launcher import RunnerUnit, runner_job
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
    """The value of the expression as plain Python data, so a later expression can read it as a
    variable, such as the list of the containers (#3700), or None when it errors."""
    result = _CEL.compile(expression).eval(data=data)
    return result.plain_value() if result.type() != cel.Type.ERROR else None


def _policy_refusals(
    name: str,
    *,
    job: dict[str, Any] | None,
    old: dict[str, Any] | None = None,
    user: str | None = None,
    operation: str = "CREATE",
) -> list[str]:
    """The messages of the validations of policy `name` that refuse the request, or none when the
    policy does not apply to the user. Each variable of the policy is computed first, in order,
    as the API server does, so a validation reads it as `variables.<name>`."""
    spec = _object("ValidatingAdmissionPolicy", name)["spec"]
    data: dict[str, Any] = {
        "object": job,
        "oldObject": old,
        "request": {"operation": operation, "userInfo": {"username": user or _service_user()}},
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


def _refusals(job: dict[str, Any], user: str | None = None, *, update: bool = False) -> list[str]:
    """The messages of the validations that refuse the create of the Job, or its update when
    `update` is true, or none when the policy does not apply to the user. A Job keeps its pod
    template for its life, so the old Job of an update has the same template."""
    if update:
        return _policy_refusals(POLICY_NAME, job=job, old=job, user=user, operation="UPDATE")
    return _policy_refusals(POLICY_NAME, job=job, user=user)


def _delete_refusals(job: dict[str, Any], user: str | None = None) -> list[str]:
    """The messages of the validations that refuse the delete of the Job."""
    return _policy_refusals(DELETE_POLICY_NAME, job=None, old=job, user=user, operation="DELETE")


def _job_of_size(size: RunnerSize | None, memory_limit: str = "8Gi") -> dict[str, Any]:
    """The implement Job that the Service makes for a row of the size table, through the
    launcher seam from a `RunnerUnit` of the row implement, as `implement_submit._create` makes
    it, so an env value of that row reaches the policy; or the Job of the bare template."""
    cronjob = _object("CronJob", "devops-cli-runner")
    args = ("roadmap", "implement", "--repo", "example/project", "--item", "7", "--confirm")
    name = "devops-cli-runner-20261030-120000-ab12"
    if size is None:
        return build_job(
            cronjob,
            list(args),
            name,
            template=RUNNER_TEMPLATE,
            env=SERVICE_ENV,
            labels=SERVICE_LABELS,
        )
    unit = RunnerUnit(
        row=ServiceRow.IMPLEMENT,
        repo=RepoRef("example/project"),
        item=7,
        args=args,
        size=size,
        name=name,
        deadline=load_settings().roadmap.implement.deadline_extension_seconds,
        labels=SERVICE_LABELS,
        annotations={CONST_ROADMAP_IMPLEMENT_ANNOTATION_PROGRESS_AT: "1700000000"},
    )
    return runner_job(cronjob, unit, memory_limit)


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


def _containers(job: dict[str, Any]) -> list[dict[str, Any]]:
    """The containers of the pod in the order that they run: the init containers first."""
    pod = _pod(job)
    return [*pod.get("initContainers", []), *pod["containers"]]


def _named(job: dict[str, Any], name: str) -> dict[str, Any]:
    (container,) = (c for c in _containers(job) if c["name"] == name)
    return container


def _container(job: dict[str, Any]) -> dict[str, Any]:
    """The container that the Service sizes: `agent` of a runner Job on the three containers
    (#3700), else the one container of the pod."""
    pod = _pod(job)
    names = [c["name"] for c in _containers(job)]
    container: dict[str, Any] = _named(job, "agent") if "agent" in names else pod["containers"][0]
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
    _pod(job)["containers"].append({**copy.deepcopy(_pod(job)["containers"][0]), "name": "second"})


def _add_init_container(job: dict[str, Any]) -> None:
    """A third init container, a copy of `prepare` under another name."""
    third = {**copy.deepcopy(_named(job, "prepare")), "name": "init"}
    _pod(job)["initContainers"].append(third)


def _add_env_from(source: dict[str, Any]) -> Mutation:
    return lambda job: _container(job).setdefault("envFrom", []).append(source)


def _add_env_value_from(job: dict[str, Any]) -> None:
    secret_key = {"secretKeyRef": {"name": "other", "key": "token"}}
    _container(job)["env"].append({"name": "OTHER", "valueFrom": secret_key})


def _add_volume(volume: dict[str, Any]) -> Mutation:
    return lambda job: _pod(job)["volumes"].append(volume)


def _rename_config_map(job: dict[str, Any]) -> None:
    config = next(volume for volume in _pod(job)["volumes"] if volume["name"] == "config")
    config["configMap"]["name"] = "other"


def _host_path_for_tmp(job: dict[str, Any]) -> None:
    tmp = next(volume for volume in _pod(job)["volumes"] if volume["name"] == "agent-tmp")
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


APP_KEY = "DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY"


MODEL_KEY = "DEVOPS_CLI_AI_API_KEY"


CACHE_KEY = "DEVOPS_CLI_VALKEY_PASSWORD"


def _key_in(name: str, key: str) -> Mutation:
    entry = {"name": key, "valueFrom": {"secretKeyRef": {"name": "devops-cli", "key": key}}}
    return lambda job: _named(job, name)["env"].append(entry)


def _mount_in(name: str, volume: str, path: str) -> Mutation:
    return lambda job: _named(job, name)["volumeMounts"].append({"name": volume, "mountPath": path})


def _writable_in(name: str, volume: str) -> Mutation:
    def mutate(job: dict[str, Any]) -> None:
        (mount,) = (m for m in _named(job, name)["volumeMounts"] if m["name"] == volume)
        mount["readOnly"] = False

    return mutate


def _set_in(name: str, **fields: object) -> Mutation:
    return lambda job: _named(job, name).update(fields)


def _arg_in(name: str, from_end: int, value: str) -> Mutation:
    """Replace the arg `from_end` places from the end of the args of container `name`."""

    def mutate(job: dict[str, Any]) -> None:
        args = _named(job, name)["args"]
        args[len(args) - from_end] = value

    return mutate


def _first_arg_in(name: str, value: str) -> Mutation:
    return lambda job: _named(job, name)["args"].insert(0, value)


def _plain_env_in(name: str, variable: str, value: str) -> Mutation:
    """Set the plain env value `variable` of container `name`, or add it."""

    def mutate(job: dict[str, Any]) -> None:
        env = _named(job, name)["env"]
        env[:] = [entry for entry in env if entry["name"] != variable]
        env.append({"name": variable, "value": value})

    return mutate


@pytest.mark.parametrize(
    ("mutate", "rule"),
    [
        pytest.param(_key_in("agent", APP_KEY), "valueFrom", id="app-key-in-agent"),
        pytest.param(_key_in("prepare", MODEL_KEY), "valueFrom", id="model-key-in-prepare"),
        pytest.param(_key_in("publish", MODEL_KEY), "valueFrom", id="model-key-in-publish"),
        pytest.param(_key_in("agent", CACHE_KEY), "valueFrom", id="cache-key-in-agent"),
        pytest.param(
            _mount_in("agent", "state", "/run/roadmap/state"), "mounts only", id="state-in-agent"
        ),
        pytest.param(
            _mount_in("agent", "publish-home", "/publish"), "mounts only", id="home-of-publish"
        ),
        pytest.param(_writable_in("publish", "run"), "mounts only", id="publish-writes-run"),
        pytest.param(_writable_in("publish", "state"), "mounts only", id="publish-writes-state"),
        pytest.param(_set_pod(shareProcessNamespace=True), "shareProcessNamespace", id="pid"),
        pytest.param(_set_in("prepare", restartPolicy="Always"), "restartPolicy", id="sidecar"),
        pytest.param(_set_in("publish", restartPolicy="Always"), "restartPolicy", id="app"),
        pytest.param(
            _set_in("agent", restartPolicyRules=[{"action": "Restart"}]),
            "restartPolicy",
            id="restart-rules",
        ),
        pytest.param(_add_init_container, "init containers prepare and agent", id="third-init"),
        pytest.param(
            _set_in("prepare", image="ghcr.io/dan-petty/devops-cli/service"),
            "image",
            id="init-image",
        ),
        pytest.param(_set_in("agent", command=["sh", "-c", "id"]), "command", id="init-command"),
        pytest.param(_arg_in("publish", 1, "/run/roadmap/work"), "its name", id="publish-work"),
        pytest.param(_arg_in("prepare", 3, "all"), "its name", id="prepare-phase-all"),
        pytest.param(_first_arg_in("agent", "--phase=publish"), "its name", id="second-phase"),
        pytest.param(_first_arg_in("publish", "--work=/tmp/x"), "its name", id="second-work"),
        pytest.param(_set_pod(restartPolicy="OnFailure"), "restartPolicy Never", id="on-failure"),
        pytest.param(_set_in("publish", lifecycle={"postStart": {}}), "lifecycle", id="lifecycle"),
        pytest.param(_set_in("agent", livenessProbe={}), "lifecycle", id="liveness"),
        pytest.param(_set_in("agent", readinessProbe={}), "lifecycle", id="readiness"),
        pytest.param(_set_in("prepare", startupProbe={}), "lifecycle", id="startup"),
        pytest.param(_set_in("publish", workingDir="/run/roadmap"), "lifecycle", id="working-dir"),
        pytest.param(_plain_env_in("publish", "PYTHONPATH", "/run/roadmap"), "plain env", id="pp"),
        pytest.param(_plain_env_in("agent", "LD_PRELOAD", "/run/roadmap/x"), "plain env", id="ld"),
        pytest.param(
            _plain_env_in("publish", "GIT_CONFIG_GLOBAL", "/run/roadmap/c"), "plain env", id="git"
        ),
        pytest.param(_plain_env_in("publish", "HOME", "/run/roadmap"), "plain env", id="home"),
        pytest.param(
            _plain_env_in("publish", "DEVOPS_CLI_DATA_DIR", "/run/roadmap/work"),
            "plain env",
            id="data-dir",
        ),
        pytest.param(
            _plain_env_in("prepare", "DEVOPS_CLI_CONFIG", "/run/roadmap/c.yaml"),
            "plain env",
            id="config",
        ),
    ],
)
def check_a_job_on_the_three_containers_that_breaks_one_rule_is_refused_by_that_rule(
    mutate: Mutation, rule: str
) -> None:
    """The rules of #3700: the key of each container, the mounts of each, no shared process
    namespace, no container that restarts, and the image and the command of an init container."""
    refused = _refusals(_changed(mutate))

    assert len(refused) == 1, refused
    assert rule in refused[0]


def check_the_patches_of_the_service_on_the_three_containers_are_admitted() -> None:
    """The Service patches a Job that runs: a new deadline on progress, the deadline and the mark
    of a stall (#3063), and the resume of a fix-checks Job that waited (#5027). A Job keeps its
    pod template, so each PATCH is an UPDATE of the same template."""

    def patched(job: dict[str, Any], **spec: object) -> dict[str, Any]:
        changed = copy.deepcopy(job)
        changed["spec"].update(spec)
        changed["metadata"].setdefault("annotations", {})["roadmap.devops-cli/progress-at"] = "1"
        return changed

    jobs = [
        patched(_template_job(), activeDeadlineSeconds=9000),
        patched(_job_of_size(RUNNER_SIZES[-1]), activeDeadlineSeconds=600),
        patched(_fix_job(suspend=True), suspend=False),
    ]

    assert [_refusals(job, update=True) for job in jobs] == [[]] * len(jobs)


def _one_container_job() -> dict[str, Any]:
    """The Job of the runner template before #3700: one container `runner` that holds both keys
    and runs every phase, with the volumes tmp, home and config."""
    cronjob = copy.deepcopy(_object("CronJob", "devops-cli-runner"))
    pod = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    agent = next(c for c in pod["initContainers"] if c["name"] == "agent")
    tmp = next(m["mountPath"] for m in agent["volumeMounts"] if m["name"] == "agent-tmp")
    mounts = [("tmp", tmp), ("home", "/home/devops")]
    runner = {
        **agent,
        "name": "runner",
        "env": [
            *agent["env"],
            {
                "name": APP_KEY,
                "valueFrom": {"secretKeyRef": {"name": "devops-cli", "key": APP_KEY}},
            },
        ],
        "volumeMounts": [
            *({"name": name, "mountPath": path} for name, path in mounts),
            {"name": "config", "mountPath": "/config", "readOnly": True},
        ],
    }
    del pod["initContainers"]
    pod["containers"] = [runner]
    config = next(volume for volume in pod["volumes"] if volume["name"] == "config")
    pod["volumes"] = [{"name": name, "emptyDir": {"sizeLimit": "1Gi"}} for name, _ in mounts]
    pod["volumes"].append(config)
    size = RUNNER_SIZES[0]
    return build_job(
        cronjob,
        ["roadmap", "implement", "--repo", "example/project", "--item", "7", "--confirm"],
        "devops-cli-runner-20261030-120000-ab12",
        template=RUNNER_TEMPLATE,
        env={**SERVICE_ENV, **size.env},
        labels=SERVICE_LABELS,
        resources=size.resources("8Gi"),
    )


def check_the_one_container_of_the_old_template_is_refused_also_on_an_update() -> None:
    """No running runner Job of the template before #3700 is left in the cluster, and the ended
    ones go at their TTL. So the policy refuses the one container `runner` on a CREATE and on an
    UPDATE (#6691)."""
    job = _one_container_job()
    shape = (
        "A runner Job must have the init containers prepare and agent and the container publish."
    )

    assert [
        any(message.endswith(shape) for message in refused)
        for refused in (_refusals(job), _refusals(job, update=True))
    ] == [True, True]


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


def _set_arg(index: int, value: str) -> Mutation:
    return lambda job: _container(job)["args"].__setitem__(index, value)


def _add_arg(value: str) -> Mutation:
    return lambda job: _container(job)["args"].append(value)


def _set_plain_env(name: str, value: str | None) -> Mutation:
    """Set the plain environment value `name` of the container, or remove it when `value` is
    None."""

    def mutate(job: dict[str, Any]) -> None:
        container = _container(job)
        container["env"] = [entry for entry in container["env"] if entry["name"] != name]
        if value is not None:
            container["env"].append({"name": name, "value": value})

    return mutate


TOKEN_REPOSITORY_ENV = "DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY"


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
        RUNNER_IMAGE,
        f"{RUNNER_IMAGE}:latest",
        f"{RUNNER_IMAGE}@{DIGEST}",
        f"{RUNNER_IMAGE}:latest@{DIGEST}",
    )

    assert [_refusals(_stage_changed(_set_image(image))) for image in forms] == [[]] * len(forms)


@pytest.mark.parametrize(
    ("mutate", "rule"),
    [
        pytest.param(_set_image(SERVICE_IMAGE), "image", id="service-image"),
        pytest.param(_set_image(f"{RUNNER_IMAGE}-evil"), "image", id="name-prefix"),
        pytest.param(
            _set_env_from({"secretRef": {"name": "devops-cli"}}), "envFrom", id="env-from"
        ),
        pytest.param(
            _add_secret_key("devops-cli", "DEVOPS_CLI_QDRANT_API_KEY"), "valueFrom", id="4th-key"
        ),
        pytest.param(
            _add_secret_key("devops-cli", "DEVOPS_CLI_MCP_STAGE_TOKEN"),
            "valueFrom",
            id="mcp-token",
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
        pytest.param(
            _set_spec(activeDeadlineSeconds=CONST_ROADMAP_STAGE_JOB_DEADLINE_SECONDS + 1),
            "deadline",
            id="deadline-over-the-stage-deadline",
        ),
        pytest.param(
            _set_spec(activeDeadlineSeconds=CONST_ROADMAP_STAGE_JOB_DEADLINE_SECONDS - 1),
            "deadline",
            id="deadline-under-the-stage-deadline",
        ),
        pytest.param(_set_arg(1, "implement"), "args", id="other-command"),
        pytest.param(_set_arg(5, "0"), "args", id="item-0"),
        pytest.param(_set_arg(5, "7 --plan"), "args", id="item-not-a-number"),
        pytest.param(_add_arg("--plan"), "args", id="extra-arg"),
        pytest.param(
            _set_plain_env("DEVOPS_CLI_AI_BASE_URL", "https://example.com"),
            "plain env",
            id="extra-plain-env",
        ),
        pytest.param(
            _set_plain_env(TOKEN_REPOSITORY_ENV, "example/other"),
            "plain env",
            id="token-for-another-repository",
        ),
        pytest.param(_set_plain_env(TOKEN_REPOSITORY_ENV, None), "plain env", id="no-token-repo"),
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


def check_the_stage_job_may_read_exactly_the_keys_of_the_constant() -> None:
    """The policy admits each key of `CONST_ROADMAP_STAGE_JOB_SECRET_KEYS`, which the template
    reads, and refuses a key of the Secret that a stage Job does not need, such as an MCP token."""
    keys = (
        *CONST_ROADMAP_STAGE_JOB_SECRET_KEYS,
        "DEVOPS_CLI_MCP_STAGE_TOKEN",
        "DEVOPS_CLI_MCP_IMPLEMENT_TOKEN",
    )

    admitted = [
        key
        for key in keys
        if not _refusals(_stage_changed(_drop_secret_keys, _add_secret_key("devops-cli", key)))
    ]

    assert admitted == list(CONST_ROADMAP_STAGE_JOB_SECRET_KEYS)


def check_each_container_of_a_runner_job_may_read_exactly_its_key_of_the_constant() -> None:
    """A runner Job reads the keys of `CONST_ROADMAP_STAGE_JOB_SECRET_KEYS` (#6518): on the three
    containers (#3700) `agent` reads only the model key, and `prepare` and `publish` only the App
    key and the password of the cache (#7293). The policy refuses another key of the Secret, such
    as an MCP token, and it refuses the password of the cache in `agent`."""
    keys = (
        *CONST_ROADMAP_STAGE_JOB_SECRET_KEYS,
        "DEVOPS_CLI_MCP_IMPLEMENT_TOKEN",
    )

    def only(name: str, key: str) -> dict[str, Any]:
        job = _changed()
        container = _named(job, name)
        container["env"] = [entry for entry in container["env"] if "valueFrom" not in entry]
        _key_in(name, key)(job)
        return job

    admitted = {
        name: [key for key in keys if not _refusals(only(name, key))]
        for name in ("prepare", "agent", "publish")
    }

    assert sorted(CONST_ROADMAP_STAGE_JOB_SECRET_KEYS) == sorted((APP_KEY, MODEL_KEY, CACHE_KEY))
    assert admitted == {
        "prepare": [APP_KEY, CACHE_KEY],
        "agent": [MODEL_KEY],
        "publish": [APP_KEY, CACHE_KEY],
    }


ENV_FROM_SECRET = {"secretRef": {"name": "devops-cli"}}


def _env_from_refused(refusals: list[str]) -> bool:
    """True when the envFrom rule alone refuses, with its whole message."""
    return refusals == ["A Job must not use envFrom."]


def check_the_plain_env_names_of_a_stage_job_are_those_of_the_template_and_the_service() -> None:
    """The policy names each plain environment value that a stage Job may set: those of CronJob
    roadmap-stage and those of `stage_job_env`. A new value in either place needs a row here."""
    (rule,) = (
        item["expression"]
        for item in _object("ValidatingAdmissionPolicy", POLICY_NAME)["spec"]["validations"]
        if "plain env" in item["message"] and "stage Job" in item["message"]
    )
    listed = set(re.findall(r'"([A-Z0-9_]+)"', rule.partition("e.name in")[2]))
    template = _object("CronJob", STAGE_TEMPLATE.cronjob)
    (container,) = template["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"]
    plain = {entry["name"] for entry in container["env"] if "valueFrom" not in entry}

    assert listed == plain | set(stage_job_env(STAGE_REPO, "x", STAGE_DEADLINE))


def check_the_plain_env_names_of_a_runner_job_are_those_of_its_template_and_the_service() -> None:
    """The policy names each plain environment value that a container of the three may set: those
    of CronJob devops-cli-runner and those that the Service adds to the implement Job and to the
    fix-checks Job (#3700). A new value in either place needs a row in the policy."""
    (rule,) = (
        item["expression"]
        for item in _object("ValidatingAdmissionPolicy", POLICY_NAME)["spec"]["validations"]
        if "plain env" in item["message"] and "three containers" in item["message"]
    )
    listed = set(re.findall(r'"([A-Z0-9_]+)"', rule.partition("e.name in")[2].partition("]")[0]))
    plain = {
        entry["name"]
        for job in (_template_job(), _fix_job())
        for container in _containers(job)
        for entry in container["env"]
        if "valueFrom" not in entry
    }

    assert listed == plain


def check_the_service_may_delete_a_stage_job_and_a_waiting_fix_job_and_no_other_job() -> None:
    """The Service deletes a stage Job (#5483) and a fix-checks Job that waits suspended past
    `roadmap.fix_checks.max_wait_minutes` (#6018), and no runner Job that runs."""
    runner = _template_job()
    stage = _stage_job()

    assert (
        _delete_refusals(stage),
        _delete_refusals(_fix_job(suspend=True)),
        len(_delete_refusals(_fix_job(suspend=False))),
        len(_delete_refusals(runner)),
        _delete_refusals(runner, "kubernetes-admin"),
    ) == ([], [], 1, 1, [])


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


# ── The fix-checks Job (#5027) ────────────────────────────────────────────────

FIX_DUE = FixDue(pull=7, head="a" * 40, check="Static Analysis", item=5)


def _fix_job(*, confirm: bool = True, suspend: bool = False, attempt: int = 1) -> dict[str, Any]:
    """The Job that the launcher seam makes from CronJob devops-cli-runner for a fix unit."""
    unit = fix_unit(
        STAGE_REPO.display,
        FIX_DUE,
        attempt=attempt,
        confirm=confirm,
        suspend=suspend,
        now=STAGE_DEADLINE,
    )
    return runner_job(_object("CronJob", "devops-cli-runner"), unit, "16Gi")


def check_the_fix_checks_job_of_the_launcher_passes_in_each_mode_and_suspended() -> None:
    jobs = [
        _fix_job(confirm=confirm, suspend=suspend, attempt=attempt)
        for confirm in (True, False)
        for suspend in (True, False)
        for attempt in (1, 2)
    ]

    assert [_refusals(job) for job in jobs] == [[]] * len(jobs)


def check_the_fix_checks_job_carries_its_component_and_no_implement_label() -> None:
    job = _fix_job()
    labels = job["metadata"]["labels"]

    assert (
        labels["app.kubernetes.io/component"],
        job["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/component"],
        "implement-repo" in labels,
        _container(job).get("command"),
    ) == ("roadmap-fix-checks", "roadmap-fix-checks", False, None)


def check_a_fix_checks_job_over_the_deadline_cap_is_refused() -> None:
    job = _fix_job()
    job["spec"]["activeDeadlineSeconds"] = CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS + 1

    refused = _refusals(job)

    assert len(refused) == 1
    assert "deadline" in refused[0]


PLANNER_TEMPLATE = JobTemplate(cronjob="devops-cli-planner-run", container="runner")


def _planner_job() -> dict[str, Any]:
    """The Job that the Service makes from the planner's CronJob template."""
    return build_job(
        _object("CronJob", "devops-cli-planner-run"),
        ["--version"],
        "devops-cli-planner-run-20261114-120000-ab12",
        template=PLANNER_TEMPLATE,
    )


def check_the_planner_job_from_the_template_passes() -> None:
    assert _refusals(_planner_job()) == []


def _selects(selector: dict[str, Any], labels: dict[str, str]) -> bool:
    """True when the label selector `selector` selects a pod with `labels`."""
    expressions = {
        "In": lambda key, values: labels.get(key) in values,
        "NotIn": lambda key, values: labels.get(key) not in values,
        "Exists": lambda key, _values: key in labels,
        "DoesNotExist": lambda key, _values: key not in labels,
    }
    return all(labels.get(k) == v for k, v in selector.get("matchLabels", {}).items()) and all(
        expressions[e["operator"]](e["key"], e.get("values", []))
        for e in selector.get("matchExpressions", [])
    )


def check_the_planner_template_has_the_controls_of_adr_0018() -> None:
    cronjob = _object("CronJob", "devops-cli-planner-run")
    spec = cronjob["spec"]
    pod = spec["jobTemplate"]["spec"]["template"]["spec"]
    (container,) = pod["containers"]
    pod_labels = spec["jobTemplate"]["spec"]["template"]["metadata"]["labels"]
    # NetworkPolicies add their rules, so the pod reaches no network only when the planner policy
    # is the one policy of the namespace that selects it (#6065).
    (policy,) = (
        document
        for document in applied_documents(DEVOPS_DIR)
        if document["kind"] == "NetworkPolicy"
        and _selects(document["spec"]["podSelector"], pod_labels)
    )

    assert (
        policy["metadata"]["name"],
        spec["suspend"],
        spec["jobTemplate"]["spec"]["backoffLimit"],
        spec["jobTemplate"]["spec"]["activeDeadlineSeconds"],
        pod["automountServiceAccountToken"],
        "envFrom" in container,
        container["resources"]["requests"],
        container["resources"]["limits"],
        policy["spec"]["podSelector"]["matchLabels"]["app.kubernetes.io/name"],
        policy["spec"]["policyTypes"],
        policy["spec"].get("egress", []),
    ) == (
        "devops-cli-planner-run",
        True,
        0,
        120,
        False,
        False,
        {"cpu": "1", "memory": "2Gi"},
        {"cpu": "1", "memory": "2Gi"},
        "devops-cli-planner-run",
        ["Egress"],
        [],
    )


def check_a_planner_job_with_an_extra_volume_is_refused() -> None:
    job = _planner_job()
    _pod(job)["volumes"].append({"name": "data", "emptyDir": {}})

    assert any("volumes" in message for message in _refusals(job))


def check_a_planner_job_with_a_writable_repo_is_refused() -> None:
    job = _planner_job()
    (repo,) = (volume for volume in _pod(job)["volumes"] if volume["name"] == "repo")
    repo["persistentVolumeClaim"]["readOnly"] = False

    assert any("repo" in message for message in _refusals(job))


def check_a_planner_job_with_a_secret_env_from_is_refused() -> None:
    job = _planner_job()
    _container(job)["envFrom"] = [{"secretRef": {"name": "devops-cli"}}]

    assert any("envFrom" in message for message in _refusals(job))


@pytest.mark.parametrize("key", [APP_KEY, MODEL_KEY, CACHE_KEY])
def check_a_planner_job_with_a_key_of_the_secret_is_refused(key: str) -> None:
    """A runner Job and a stage Job may read these keys with `valueFrom` (#6518), but a planner
    run Job reads no key of the Secret (ADR 0018)."""
    job = _planner_job()
    _add_secret_key("devops-cli", key)(job)

    assert any("valueFrom" in message for message in _refusals(job))


@pytest.mark.parametrize(
    "job",
    [
        pytest.param(
            lambda: _changed(_drop_secret_keys, _set_env_from(ENV_FROM_SECRET)),
            id="runner-the-secret",
        ),
        pytest.param(
            lambda: _changed(_drop_secret_keys, _set_env_from({"secretRef": {"name": "x"}})),
            id="runner-other-secret",
        ),
        pytest.param(
            lambda: _changed(_drop_secret_keys, _set_env_from({"configMapRef": {"name": "x"}})),
            id="runner-config-map",
        ),
        pytest.param(lambda: _stage_changed(_set_env_from(ENV_FROM_SECRET)), id="stage"),
        pytest.param(lambda: _with_env_from(_planner_job(), ENV_FROM_SECRET), id="planner"),
    ],
)
def check_a_job_with_env_from_is_refused_on_create_and_on_update(
    job: Callable[[], dict[str, Any]],
) -> None:
    """No runner Job made before #6518, which took the whole Secret with `envFrom`, is left in the
    cluster (#6691). So the policy refuses `envFrom` in the CREATE and in the UPDATE of each Job:
    of Secret devops-cli, of another Secret and of a ConfigMap."""
    made = job()

    assert (
        _env_from_refused(_refusals(made)),
        _env_from_refused(_refusals(made, update=True)),
    ) == (
        True,
        True,
    )


def _with_env_from(job: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    _set_env_from(source)(job)
    return job
