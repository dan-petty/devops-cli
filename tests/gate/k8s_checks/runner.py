"""The runner CronJob, its service account and its role, as Argo CD renders them (#2164)."""

from __future__ import annotations

import functools
from typing import Any

import pytest
import yaml
from kubernetes.utils.quantity import parse_quantity

from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_JOB_SECRET_KEYS,
    CONST_RUNNER_PHASE_AGENT,
    CONST_RUNNER_PHASE_PREPARE,
    CONST_RUNNER_PHASE_PUBLISH,
)
from devops_cli.k8s.cluster_job import phase_containers
from tests.gate.k8s_render import kustomize
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


RUNNER_IMAGE = "ghcr.io/dan-petty/devops-cli/runner"


METADATA_ADDRESS = "169.254.169.254/32"


@functools.cache
def _rendered() -> tuple[dict[str, Any], ...]:
    documents = yaml.load_all(kustomize(DEVOPS_DIR).stdout, Loader=yaml.CSafeLoader)
    return tuple(document for document in documents if isinstance(document, dict))


def _object(kind: str, name: str) -> dict[str, Any]:
    (found,) = (
        document
        for document in _rendered()
        if document["kind"] == kind and document["metadata"]["name"] == name
    )
    return found


def _cronjob_pod(name: str) -> dict[str, Any]:
    pod: dict[str, Any] = _object("CronJob", name)["spec"]["jobTemplate"]["spec"]["template"][
        "spec"
    ]
    return pod


def _runner_containers() -> dict[str, dict[str, Any]]:
    """The containers of the runner pod by name, in the order that they run (#3700)."""
    pod = _cronjob_pod("devops-cli-runner")
    return {c["name"]: c for c in [*pod.get("initContainers", []), *pod["containers"]]}


def _env(container: dict[str, Any]) -> dict[str, Any]:
    return {entry["name"]: entry.get("value") for entry in container["env"]}


def check_the_runner_cronjob_is_a_suspended_template_that_never_retries() -> None:
    cronjob = _object("CronJob", "devops-cli-runner")
    job = cronjob["spec"]["jobTemplate"]["spec"]
    pod = _cronjob_pod("devops-cli-runner")

    assert (
        cronjob["metadata"]["namespace"],
        cronjob["spec"]["suspend"],
        job["backoffLimit"],
        pod["restartPolicy"],
        pod["serviceAccountName"],
        phase_containers(pod),
        {(c["image"], c["imagePullPolicy"]) for c in _runner_containers().values()},
    ) == (
        "devops",
        True,
        0,
        "Never",
        "devops-cli",
        (CONST_RUNNER_PHASE_PREPARE, CONST_RUNNER_PHASE_AGENT, CONST_RUNNER_PHASE_PUBLISH),
        {(RUNNER_IMAGE, "IfNotPresent")},
    )


def check_the_runner_bounds_the_workers_of_the_test_runner_to_its_cpu_limit() -> None:
    """`pytest-xdist` counts the CPUs of the node, not the CPU limit of the pod. On a node with 48
    CPUs a test run started 48 workers of about 280 MB each in a pod with 2 CPUs (#2806). Only
    `agent` runs the tests."""
    agent = _runner_containers()["agent"]

    assert _env(agent)["PYTEST_XDIST_AUTO_NUM_WORKERS"] == agent["resources"]["limits"]["cpu"]


def check_the_runner_pod_is_restricted_and_mounts_no_token() -> None:
    pod = _cronjob_pod("devops-cli-runner")
    reference = _cronjob_pod("devops-cli")

    assert (
        pod["securityContext"],
        {name: c["securityContext"] for name, c in _runner_containers().items()},
        pod["automountServiceAccountToken"],
        "shareProcessNamespace" in pod,
        [volume["name"] for volume in pod["volumes"] if "projected" in volume],
    ) == (
        reference["securityContext"],
        dict.fromkeys(_runner_containers(), reference["containers"][0]["securityContext"]),
        False,
        False,
        [],
    )


def check_the_runner_container_knows_it_is_a_runner_and_takes_its_credentials_from_the_secret() -> (
    None
):
    """Only `prepare` and `publish` read the App key and the password of the cache (#7293), and
    only `agent` the model key (#3700)."""
    containers = _runner_containers()
    service = _object("Deployment", "roadmap-service")["spec"]["template"]["spec"]["containers"][0]
    default = _cronjob_pod("devops-cli")["containers"][0]
    cache_key, app_key, model_key = sorted(CONST_ROADMAP_STAGE_JOB_SECRET_KEYS, reverse=True)

    def keys(container: dict[str, Any]) -> list[str]:
        return [
            e["valueFrom"]["secretKeyRef"]["key"]
            for e in container["env"]
            if "valueFrom" in e and e["valueFrom"]["secretKeyRef"]["name"] == "devops-cli"
        ]

    assert (
        {name: _env(c)["DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER"] for name, c in containers.items()},
        [name for name, c in containers.items() if "envFrom" in c],
        {name: keys(c) for name, c in containers.items()},
        {_env(c)["DEVOPS_CLI_CONFIG"] for c in containers.values()},
        [e["name"] for e in service["env"] if "IN_RUNNER" in e["name"]],
        [e["name"] for e in default["env"] if "IN_RUNNER" in e["name"]],
    ) == (
        dict.fromkeys(containers, "true"),
        [],
        {"prepare": [app_key, cache_key], "agent": [model_key], "publish": [app_key, cache_key]},
        {"/config/devops-cli.yaml"},
        [],
        [],
    )


def check_each_runner_container_has_its_own_home_and_tmp_and_the_data_dir_lives_in_it() -> None:
    """A run that reached the strength check went over 4 Gi and the kubelet evicted it (#5960).
    Each container has its own home and tmp, so no writable volume of `agent` reaches `publish`
    (#3700). The sizes are values of the template, so the check holds the form only (#6060)."""
    pod = _cronjob_pod("devops-cli-runner")
    volumes = {v["name"]: v for v in pod["volumes"]}
    containers = _runner_containers()
    # The tmp of each container is at the path of the tmp of CronJob devops-cli.
    (tmp,) = (
        m["mountPath"]
        for m in _cronjob_pod("devops-cli")["containers"][0]["volumeMounts"]
        if m["name"] == "tmp"
    )

    assert (
        {
            name: {
                m["mountPath"]: m["name"]
                for m in c["volumeMounts"]
                if m["mountPath"] in (tmp, "/home/devops")
            }
            for name, c in containers.items()
        },
        {
            sorted(volumes[f"{name}-{part}"]["emptyDir"]) == ["sizeLimit"]
            for name in containers
            for part in ("tmp", "home")
        },
        {_env(c)["DEVOPS_CLI_DATA_DIR"].startswith("/home/devops/") for c in containers.values()},
    ) == (
        {name: {tmp: f"{name}-tmp", "/home/devops": f"{name}-home"} for name in containers},
        {True},
        {True},
    )


def check_every_volume_of_the_runner_has_a_size_limit_inside_the_ephemeral_storage_limit() -> None:
    """A step can write as much as it wants into `/tmp`. Without a limit one Job fills the disk
    of its node (#2667), so each volume has a limit. The kubelet sizes the storage of the pod by
    its largest init container, `agent`, whose storage limit covers every volume and the log
    (#5960, #3700)."""
    pod = _cronjob_pod("devops-cli-runner")
    limits = {v["name"]: v["emptyDir"].get("sizeLimit") for v in pod["volumes"] if "emptyDir" in v}
    storage = _runner_containers()["agent"]["resources"]["limits"]["ephemeral-storage"]

    assert (
        None in limits.values(),
        sum(parse_quantity(limit) for limit in limits.values() if limit) < parse_quantity(storage),
    ) == (False, True)


def check_the_service_has_its_own_account_and_mounts_a_token_that_expires_in_an_hour() -> None:
    account = _object("ServiceAccount", "roadmap-service")
    pod = _object("Deployment", "roadmap-service")["spec"]["template"]["spec"]
    (container,) = pod["containers"]
    token_volume = next(v for v in pod["volumes"] if "projected" in v)
    (token,) = (
        s["serviceAccountToken"]
        for s in token_volume["projected"]["sources"]
        if "serviceAccountToken" in s
    )
    mount = next(m for m in container["volumeMounts"] if m["name"] == token_volume["name"])

    assert (
        account["automountServiceAccountToken"],
        pod["serviceAccountName"],
        pod["automountServiceAccountToken"],
        token["expirationSeconds"],
        token["path"],
        mount["mountPath"],
        mount["readOnly"],
    ) == (
        False,
        "roadmap-service",
        False,
        3600,
        "token",
        "/var/run/secrets/kubernetes.io/serviceaccount",
        True,
    )


def check_the_jobs_run_as_an_account_with_no_token_and_no_role() -> None:
    account = _object("ServiceAccount", "devops-cli")
    subjects = [
        (subject["kind"], subject["name"])
        for document in _rendered()
        if document["kind"] in {"RoleBinding", "ClusterRoleBinding"}
        for subject in document.get("subjects", [])
    ]

    assert (
        account["automountServiceAccountToken"],
        ("ServiceAccount", "devops-cli") in subjects,
    ) == (
        False,
        False,
    )


def check_the_role_of_the_service_holds_seven_rules_and_one_binding() -> None:
    role = _object("Role", "roadmap-service-jobs")
    binding = _object("RoleBinding", "roadmap-service-jobs")

    assert (
        role["metadata"]["namespace"],
        role["rules"],
        binding["roleRef"],
        binding["subjects"],
    ) == (
        "devops",
        [
            {
                "apiGroups": ["batch"],
                "resources": ["jobs"],
                "verbs": ["create", "delete", "get", "list", "patch"],
            },
            {
                "apiGroups": ["batch"],
                "resources": ["cronjobs"],
                "resourceNames": ["devops-cli-runner", "roadmap-stage", "devops-cli-planner-run"],
                "verbs": ["get"],
            },
            {
                "apiGroups": ["apps"],
                "resources": ["deployments"],
                "resourceNames": ["roadmap-service"],
                "verbs": ["get"],
            },
            {"apiGroups": [""], "resources": ["pods"], "verbs": ["list"]},
            {"apiGroups": [""], "resources": ["pods/log"], "verbs": ["get"]},
            # The Lease of the rows (#6058): RBAC cannot limit `create` to a name.
            {
                "apiGroups": ["coordination.k8s.io"],
                "resources": ["leases"],
                "resourceNames": ["roadmap-service-rows"],
                "verbs": ["get", "update"],
            },
            {"apiGroups": ["coordination.k8s.io"], "resources": ["leases"], "verbs": ["create"]},
        ],
        {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "roadmap-service-jobs"},
        [{"kind": "ServiceAccount", "name": "roadmap-service", "namespace": "devops"}],
    )


def check_no_role_in_the_namespace_reads_a_secret_or_creates_anything_but_jobs_and_leases() -> None:
    """A Role creates only Jobs, and the Lease of the rows of the Service (#6058)."""
    rules = [
        rule
        for document in _rendered()
        if document["kind"] in {"Role", "ClusterRole"}
        for rule in document["rules"]
    ]
    creating = [
        (rule.get("apiGroups"), rule["resources"]) for rule in rules if "create" in rule["verbs"]
    ]
    reading_secrets = [rule for rule in rules if "secrets" in rule["resources"]]

    assert (creating, reading_secrets) == (
        [(["batch"], ["jobs"]), (["coordination.k8s.io"], ["leases"])],
        [],
    )


def _egress_to_port(policy: dict[str, Any], port: int) -> list[dict[str, Any]]:
    return [
        rule
        for rule in policy["spec"].get("egress", [])
        if any(entry["port"] == port for entry in rule.get("ports", []))
    ]


def check_only_the_service_pod_may_reach_the_api_server() -> None:
    policy = _object("NetworkPolicy", "roadmap-service-egress")
    perimeter = _object("NetworkPolicy", "devops-default-perimeter-egress")
    others = [
        document["metadata"]["name"]
        for document in _rendered()
        if document["kind"] == "NetworkPolicy" and _egress_to_port(document, 6443)
    ]

    assert (
        policy["spec"]["podSelector"],
        policy["spec"]["policyTypes"],
        policy["spec"]["egress"],
        _egress_to_port(perimeter, 6443),
        others,
    ) == (
        {"matchLabels": {"app.kubernetes.io/name": "roadmap-service"}},
        ["Egress"],
        [
            {
                "to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": [METADATA_ADDRESS]}}],
                "ports": [{"protocol": "TCP", "port": 6443}],
            }
        ],
        [],
        ["roadmap-service-egress"],
    )


@pytest.mark.parametrize("name", ["devops-cli", "devops-cli-runner", "roadmap-stage"])
def check_the_pods_of_jobs_carry_no_label_that_the_service_policy_selects(name: str) -> None:
    template = _object("CronJob", name)["spec"]["jobTemplate"]["spec"]["template"]

    assert template["metadata"]["labels"].get("app.kubernetes.io/name") != "roadmap-service"


def check_image_updater_keeps_the_runner_image_on_its_latest_digest() -> None:
    values = yaml.safe_load(
        (REPO_ROOT / "k8s" / "argocd" / "image-updater-values.yaml").read_text(encoding="utf-8")
    )
    (updater,) = values["extraObjects"]
    (ref,) = updater["spec"]["applicationRefs"]

    assert {
        image["alias"]: (
            image["imageName"],
            image["commonUpdateSettings"]["updateStrategy"],
            image["commonUpdateSettings"]["forceUpdate"],
        )
        for image in ref["images"]
    } == {
        "service": ("ghcr.io/dan-petty/devops-cli/service:latest", "digest", True),
        "runner": (f"{RUNNER_IMAGE}:latest", "digest", True),
        "mcp-server": ("ghcr.io/dan-petty/devops-cli/mcp-server:latest", "digest", True),
    }
