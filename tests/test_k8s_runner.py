"""The runner of the implement job in namespace devops: the CronJob template, the Role of the
Service and the network rules of the Service and of the Job (#2667).

Each test reads what `kubectl kustomize k8s/devops` renders, so it reads the objects that Argo
CD applies.
"""

from __future__ import annotations

import functools
from typing import Any

import pytest
import yaml

from tests.k8s_manifests import kustomize
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


def _runner_container() -> dict[str, Any]:
    (container,) = _cronjob_pod("devops-cli-runner")["containers"]
    return container


def test_the_runner_cronjob_is_a_suspended_template_that_never_retries() -> None:
    cronjob = _object("CronJob", "devops-cli-runner")
    job = cronjob["spec"]["jobTemplate"]["spec"]
    pod = _cronjob_pod("devops-cli-runner")
    container = _runner_container()

    assert (
        cronjob["metadata"]["namespace"],
        cronjob["spec"]["suspend"],
        job["backoffLimit"],
        job["activeDeadlineSeconds"],
        pod["restartPolicy"],
        pod["serviceAccountName"],
        container["name"],
        container["image"],
        container["imagePullPolicy"],
        container["resources"],
    ) == (
        "devops",
        True,
        0,
        7200,
        "Never",
        "devops-cli",
        "runner",
        RUNNER_IMAGE,
        "IfNotPresent",
        {
            "requests": {"cpu": "2", "memory": "4Gi", "ephemeral-storage": "2Gi"},
            "limits": {"cpu": "2", "memory": "12Gi", "ephemeral-storage": "6Gi"},
        },
    )


def test_the_runner_bounds_the_workers_of_the_test_runner_to_its_cpu_limit() -> None:
    """`pytest-xdist` counts the CPUs of the node, not the CPU limit of the pod. On a node with 48
    CPUs a test run started 48 workers of about 280 MB each in a pod with 2 CPUs (#2806)."""
    container = _runner_container()
    env = {entry["name"]: entry.get("value") for entry in container["env"]}

    assert env["PYTEST_XDIST_AUTO_NUM_WORKERS"] == container["resources"]["limits"]["cpu"]


def test_the_runner_pod_is_restricted_and_mounts_no_token() -> None:
    pod = _cronjob_pod("devops-cli-runner")
    container = _runner_container()
    reference = _cronjob_pod("devops-cli")

    assert (
        pod["securityContext"],
        container["securityContext"],
        pod["automountServiceAccountToken"],
        [volume["name"] for volume in pod["volumes"] if "projected" in volume],
    ) == (
        reference["securityContext"],
        reference["containers"][0]["securityContext"],
        False,
        [],
    )


def test_the_runner_container_knows_it_is_a_runner_and_takes_its_credentials_from_the_secret() -> (
    None
):
    container = _runner_container()
    env = {entry["name"]: entry.get("value") for entry in container["env"]}
    service = _object("Deployment", "roadmap-service")["spec"]["template"]["spec"]["containers"][0]
    default = _cronjob_pod("devops-cli")["containers"][0]

    assert (
        env["DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER"],
        container["envFrom"],
        env["DEVOPS_CLI_CONFIG"],
        [e["name"] for e in service["env"] if "IN_RUNNER" in e["name"]],
        [e["name"] for e in default["env"] if "IN_RUNNER" in e["name"]],
    ) == ("true", [{"secretRef": {"name": "devops-cli"}}], "/config/devops-cli.yaml", [], [])


def test_the_runner_home_is_an_empty_dir_of_4_gi_and_the_data_dir_lives_in_it() -> None:
    pod = _cronjob_pod("devops-cli-runner")
    container = _runner_container()
    home = next(v for v in pod["volumes"] if v["name"] == "home")
    env = {entry["name"]: entry.get("value") for entry in container["env"]}

    assert (
        home["emptyDir"],
        {m["name"]: m["mountPath"] for m in container["volumeMounts"] if m["name"] == "home"},
        env["DEVOPS_CLI_DATA_DIR"].startswith("/home/devops/"),
        {"home", "tmp"} <= {m["name"] for m in container["volumeMounts"]},
    ) == ({"sizeLimit": "4Gi"}, {"home": "/home/devops"}, True, True)


def test_every_volume_of_the_runner_has_a_size_limit_inside_the_ephemeral_storage_limit() -> None:
    """A step can write as much as it wants into `/tmp`. Without a limit one Job fills the disk
    of its node (#2667), so each volume has a limit and the container has a storage limit that
    covers them both."""
    pod = _cronjob_pod("devops-cli-runner")
    limits = {v["name"]: v["emptyDir"].get("sizeLimit") for v in pod["volumes"] if "emptyDir" in v}
    storage = _runner_container()["resources"]["limits"]["ephemeral-storage"]

    assert (limits, storage) == ({"tmp": "1Gi", "home": "4Gi"}, "6Gi")


def test_the_service_has_its_own_account_and_mounts_a_token_that_expires_in_an_hour() -> None:
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


def test_the_jobs_run_as_an_account_with_no_token_and_no_role() -> None:
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


def test_the_role_of_the_service_holds_four_rules_and_one_binding() -> None:
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
            {"apiGroups": ["batch"], "resources": ["jobs"], "verbs": ["create", "get", "list"]},
            {
                "apiGroups": ["batch"],
                "resources": ["cronjobs"],
                "resourceNames": ["devops-cli-runner"],
                "verbs": ["get"],
            },
            {"apiGroups": [""], "resources": ["pods"], "verbs": ["list"]},
            {"apiGroups": [""], "resources": ["pods/log"], "verbs": ["get"]},
        ],
        {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "roadmap-service-jobs"},
        [{"kind": "ServiceAccount", "name": "roadmap-service", "namespace": "devops"}],
    )


def test_no_role_in_the_namespace_reads_a_secret_or_creates_anything_but_jobs() -> None:
    rules = [
        rule
        for document in _rendered()
        if document["kind"] in {"Role", "ClusterRole"}
        for rule in document["rules"]
    ]
    creating = [rule["resources"] for rule in rules if "create" in rule["verbs"]]
    reading_secrets = [rule for rule in rules if "secrets" in rule["resources"]]

    assert (creating, reading_secrets) == ([["jobs"]], [])


def _egress_to_port(policy: dict[str, Any], port: int) -> list[dict[str, Any]]:
    return [
        rule
        for rule in policy["spec"].get("egress", [])
        if any(entry["port"] == port for entry in rule.get("ports", []))
    ]


def test_only_the_service_pod_may_reach_the_api_server() -> None:
    policy = _object("NetworkPolicy", "roadmap-service-egress")
    perimeter = _object("NetworkPolicy", "devops-default-perimeter")
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


@pytest.mark.parametrize("name", ["devops-cli", "devops-cli-runner"])
def test_the_pods_of_jobs_carry_no_label_that_the_service_policy_selects(name: str) -> None:
    template = _object("CronJob", name)["spec"]["jobTemplate"]["spec"]["template"]

    assert template["metadata"]["labels"].get("app.kubernetes.io/name") != "roadmap-service"


def test_image_updater_keeps_the_runner_image_on_its_latest_digest() -> None:
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
    }
