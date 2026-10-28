"""The Argo Workflows controller under k8s/argo-workflows/ (#1535): chart values, template, perimeter.

The chart cannot be rendered in a test, since helm is not an offline renderer, so the controller
and executor are checked through the values that configure them. What the chart then renders was
read once from `helm template` of the pinned chart and is recorded in the docstrings below.
"""

from __future__ import annotations

import functools
from collections.abc import Iterator
from typing import Any

import yaml

from devops_cli.config.env import env_var_for_option
from devops_cli.tools_lock import load_tools_lock
from tests.k8s_manifests import kustomize
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
ARGO_DIR = K8S_DIR / "argo-workflows"
NAMESPACE = "argo-workflows"
EXECUTOR_ACCOUNT = "argo-workflows-executor"
SYNC_OPTIONS = "argocd.argoproj.io/sync-options"


@functools.cache
def _load(path: str) -> Any:
    """A YAML document of the repository, by path below the repository root."""
    return yaml.load((REPO_ROOT / path).read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)


def _values() -> Any:
    return _load("k8s/argo-workflows/values.yaml")


def _template() -> Any:
    return _load("k8s/argo-workflows/workflowtemplate-version.yaml")


def _container() -> Any:
    (template,) = _template()["spec"]["templates"]
    return template["container"]


def _cronjob_pod() -> Any:
    return _load("k8s/devops/cronjob.yaml")["spec"]["jobTemplate"]["spec"]["template"]["spec"]


def _secret_fields(node: object, path: str = "") -> Iterator[str]:
    """Path of every mapping key that names a Secret, at any depth.

    A Kubernetes field that refers to a Secret has `secret` in its name (`secretKeyRef`,
    `secretRef`, `secretName`, `imagePullSecrets`, `existingSecret`), so the match is not a subset.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)
            if "secret" in str(key).lower():
                yield here
            yield from _secret_fields(value, here)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _secret_fields(item, f"{path}[{index}]")


def test_the_workflow_namespace_is_restricted_and_never_pruned() -> None:
    documents = yaml.safe_load_all((K8S_DIR / "namespaces.yaml").read_text(encoding="utf-8"))
    (namespace,) = [
        d
        for d in documents
        if d and d["kind"] == "Namespace" and d["metadata"]["name"] == NAMESPACE
    ]
    assert namespace["metadata"] == {
        "name": NAMESPACE,
        "labels": {
            "app.kubernetes.io/part-of": "devops-cli-stack",
            "pod-security.kubernetes.io/enforce": "restricted",
            "pod-security.kubernetes.io/warn": "restricted",
            "pod-security.kubernetes.io/audit": "restricted",
        },
        "annotations": {SYNC_OPTIONS: "Prune=false,Delete=false"},
    }


def test_the_controller_runs_one_namespaced_replica_with_no_server_database_or_archive() -> None:
    """The chart then rolls out with `Recreate` and sets LEADER_ELECTION_DISABLE itself, so any
    `extraEnv` would repeat the variable, and `singleNamespace` makes the controller watch only
    its own namespace and renders a Role in place of a ClusterRole. `createAggregateRoles` would
    add cluster-wide aggregate ClusterRoles."""
    values = _values()
    controller = values["controller"]
    assert (
        controller["replicas"],
        controller.get("extraEnv"),
        values["singleNamespace"],
        values["createAggregateRoles"],
        controller.get("workflowNamespaces"),
        controller["clusterWorkflowTemplates"],
        values["server"],
        controller.get("persistence"),
    ) == (1, None, True, False, None, {"enabled": False}, {"enabled": False}, None)


def test_the_crds_are_minimal_kept_and_carry_argo_cds_sync_options() -> None:
    """The full CRDs come from a pre-install hook Job whose ClusterRole may change every CRD in
    the cluster, and `crds.annotations` reaches only the minimal ones."""
    argocd_annotations = _load("k8s/argocd/values.yaml")["crds"]["annotations"]
    assert _values()["crds"] == {
        "install": True,
        "keep": True,
        "full": False,
        "annotations": argocd_annotations,
    }
    assert argocd_annotations == {SYNC_OPTIONS: "ServerSideApply=true,Prune=false,Delete=false"}


def test_every_pod_the_namespace_admits_meets_restricted_pod_security() -> None:
    """Chart 2.0.13 leaves the controller pod's and the executor's `securityContext` empty, and
    its controller container sets no seccomp profile, so the values supply what `restricted`
    requires of each; the template pod carries the cluster job template's own."""
    values = _values()
    pod = _template()["spec"]["securityContext"]
    assert (
        values["controller"]["podSecurityContext"],
        values["executor"]["securityContext"],
        (pod["runAsNonRoot"], pod["seccompProfile"]),
        _container()["securityContext"],
    ) == (
        {"runAsNonRoot": True, "seccompProfile": {"type": "RuntimeDefault"}},
        {
            "allowPrivilegeEscalation": False,
            "runAsNonRoot": True,
            "capabilities": {"drop": ["ALL"]},
            "seccompProfile": {"type": "RuntimeDefault"},
        },
        (True, {"type": "RuntimeDefault"}),
        {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
    )


def test_the_executor_identity_may_only_create_and_patch_workflow_task_results() -> None:
    """With `workflow.rbac.create` and none of `rules`, `agentPermissions` or `artifactGC`, the
    chart's Role for this ServiceAccount grants `create` and `patch` on `workflowtaskresults`
    and nothing else, so any key added to `workflow` here widens it."""
    assert (_values()["workflow"], _template()["spec"]["serviceAccountName"]) == (
        {"serviceAccount": {"create": True, "name": EXECUTOR_ACCOUNT}, "rbac": {"create": True}},
        EXECUTOR_ACCOUNT,
    )


def test_the_controller_metrics_are_scraped_through_a_service_monitor() -> None:
    controller = _values()["controller"]
    assert (controller["metricsConfig"], controller["serviceMonitor"]) == (
        {"enabled": True, "port": 9090},
        {"enabled": True},
    )


def test_the_version_template_runs_the_service_image_with_only_version_and_no_secret() -> None:
    """The template is the cluster job template's pod without its Secret, ConfigMap and token: it
    keeps the writable emptyDir mounts and names the command, because the controller would look an
    image's entrypoint up in the registry over HTTPS, which the perimeter blocks."""
    container, cronjob_pod = _container(), _cronjob_pod()
    (cronjob_container,) = cronjob_pod["containers"]
    assert (
        container["image"],
        container["imagePullPolicy"],
        container["command"],
        container["args"],
        container["env"],
        container["volumeMounts"],
        _template()["spec"]["templates"][0]["volumes"],
        container["resources"],
        "envFrom" in container,
    ) == (
        cronjob_container["image"],
        cronjob_container["imagePullPolicy"],
        ["devops"],
        ["--version"],
        [
            {"name": env_var_for_option("telemetry.enabled"), "value": "false"},
            {"name": env_var_for_option("data.dir"), "value": "/home/devops/.data"},
        ],
        [m for m in cronjob_container["volumeMounts"] if not m.get("readOnly")],
        [v for v in cronjob_pod["volumes"] if "emptyDir" in v],
        cronjob_container["resources"],
        False,
    )


def test_the_version_template_has_the_cluster_job_templates_security_context() -> None:
    """Pod and container, read from the cron job so they cannot drift apart."""
    (cronjob_container,) = _cronjob_pod()["containers"]
    assert (_template()["spec"]["securityContext"], _container()["securityContext"]) == (
        _cronjob_pod()["securityContext"],
        cronjob_container["securityContext"],
    )


def test_a_version_run_has_a_deadline_and_its_workflow_and_pods_are_garbage_collected() -> None:
    spec = _template()["spec"]
    assert (
        spec["activeDeadlineSeconds"],
        spec["ttlStrategy"],
        spec["podGC"],
    ) == (300, {"secondsAfterCompletion": 3600}, {"strategy": "OnWorkflowSuccess"})


def test_the_workflow_directory_and_its_values_reference_no_secret() -> None:
    """No object `kubectl kustomize` renders from the directory, and nothing in the chart's
    values, names a Secret field, so Secret `devops-cli` is never mounted or read here."""
    rendered = [d for d in yaml.safe_load_all(kustomize(ARGO_DIR).stdout) if d]
    assert (
        [path for document in rendered for path in _secret_fields(document)],
        [document["kind"] for document in rendered if document["kind"] == "Secret"],
        list(_secret_fields(_values())),
    ) == ([], [], [])


def test_a_field_that_names_a_secret_is_found_at_any_depth() -> None:
    """Pin the walker on documents that do reference Secrets, so an empty result means none."""
    pod = {
        "spec": {
            "containers": [
                {
                    "envFrom": [{"secretRef": {"name": "example"}}],
                    "env": [{"valueFrom": {"secretKeyRef": {"name": "example", "key": "k"}}}],
                }
            ],
            "volumes": [{"secret": {"secretName": "example"}}],
            "imagePullSecrets": [{"name": "example"}],
        },
        "existingSecret": "example",
    }
    assert list(_secret_fields(pod)) == [
        "spec.containers[0].envFrom[0].secretRef",
        "spec.containers[0].env[0].valueFrom.secretKeyRef",
        "spec.volumes[0].secret",
        "spec.volumes[0].secret.secretName",
        "spec.imagePullSecrets",
        "existingSecret",
    ]


def test_the_perimeter_admits_the_metrics_scrape_and_reaches_dns_and_the_api_server() -> None:
    """Ingress is Alloy's scrape of the controller's metrics port, from `monitoring` by namespace
    selector alone, since kube-router matches an ingress CIDR against pod addresses. Egress is
    CoreDNS and the API server on 6443 through an ipBlock that excludes the cloud metadata
    address. There is no public HTTPS and no OTLP: `--version` needs neither."""
    policy = _load("k8s/argo-workflows/networkpolicy.yaml")
    metrics_port = _values()["controller"]["metricsConfig"]["port"]
    assert (policy["metadata"], policy["spec"]) == (
        {
            "name": "argo-workflows-default-perimeter",
            "namespace": NAMESPACE,
            "labels": {"app.kubernetes.io/part-of": "devops-cli-stack"},
        },
        {
            "podSelector": {},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [
                {
                    "from": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {"kubernetes.io/metadata.name": "monitoring"}
                            }
                        }
                    ],
                    "ports": [{"protocol": "TCP", "port": metrics_port}],
                }
            ],
            "egress": [
                {
                    "to": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                            }
                        }
                    ],
                    "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
                },
                {
                    "to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": ["169.254.169.254/32"]}}],
                    "ports": [{"protocol": "TCP", "port": 6443}],
                },
            ],
        },
    )


def test_the_kustomization_renders_the_template_and_the_perimeter_and_nothing_else() -> None:
    rendered = [d for d in yaml.safe_load_all(kustomize(ARGO_DIR).stdout) if d]
    assert sorted(
        (d["kind"], d["metadata"]["namespace"], d["metadata"]["name"]) for d in rendered
    ) == [
        ("NetworkPolicy", NAMESPACE, "argo-workflows-default-perimeter"),
        ("WorkflowTemplate", NAMESPACE, "devops-cli-version"),
    ]


def test_the_kustomization_lists_every_manifest_and_stays_out_of_the_root() -> None:
    """The chart's values are no manifest, so the kustomization leaves them out, and the root
    kustomization leaves the directory to its Application and to deploy-stack."""
    kustomization = _load("k8s/argo-workflows/kustomization.yaml")
    root = _load("k8s/kustomization.yaml")
    assert (
        sorted(path.name for path in ARGO_DIR.iterdir()),
        kustomization["resources"],
        [resource for resource in root["resources"] if resource.startswith("argo-workflows")],
    ) == (
        [
            "kustomization.yaml",
            "networkpolicy.yaml",
            "values.yaml",
            "workflowtemplate-version.yaml",
        ],
        ["networkpolicy.yaml", "workflowtemplate-version.yaml"],
        [],
    )


def test_the_argo_cli_pin_is_the_version_of_the_controller_and_executor_images() -> None:
    """One tag sets both images, and the measurement submits its Workflows with the CLI at that
    tag, whose build the lock fetches for every platform from that release."""
    values = _values()
    tag = values["images"]["tag"]
    argo = load_tools_lock().binary["argo"]
    release = "https://github.com/argoproj/argo-workflows/releases/download"
    assert (
        argo.version,
        {name: build.url for name, build in argo.platforms.items()},
        values["controller"].get("image"),
        values["executor"]["image"],
    ) == (
        tag.removeprefix("v"),
        {name: f"{release}/{tag}/argo-{name}.gz" for name in argo.platforms},
        None,
        {"nonroot": True},
    )
