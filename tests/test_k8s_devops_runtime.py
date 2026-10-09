"""The in-cluster devops-cli runtime under k8s/devops/: namespace, CronJob template and perimeter."""

from __future__ import annotations

import functools
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config import options as opt
from devops_cli.config.env import OPTION_TO_ENV_VAR
from devops_cli.config.settings import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"
DEVOPS_DIR = K8S_DIR / "devops"


@functools.cache
def _doc(name: str) -> Any:
    target = DEVOPS_DIR / name
    return yaml.load(target.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)


def _pod_spec() -> dict[str, Any]:
    return _doc("cronjob.yaml")["spec"]["jobTemplate"]["spec"]["template"]["spec"]


def _container() -> dict[str, Any]:
    (container,) = _pod_spec()["containers"]
    return container


def test_namespace_is_restricted_and_never_pruned() -> None:
    docs = list(
        yaml.load_all(
            (K8S_DIR / "namespaces.yaml").read_text(encoding="utf-8"), Loader=yaml.CSafeLoader
        )
    )
    devops_doc = next(
        d
        for d in docs
        if d and d.get("kind") == "Namespace" and d.get("metadata", {}).get("name") == "devops"
    )
    namespace = devops_doc["metadata"]
    labels = namespace["labels"]
    assert (
        namespace["name"],
        {labels[f"pod-security.kubernetes.io/{mode}"] for mode in ("enforce", "warn", "audit")},
        namespace["annotations"]["argocd.argoproj.io/sync-options"],
    ) == ("devops", {"restricted"}, "Prune=false,Delete=false")


def test_service_account_mounts_no_token() -> None:
    account = _doc("serviceaccount.yaml")
    assert (account["metadata"]["name"], account["automountServiceAccountToken"]) == (
        "devops-cli",
        False,
    )


def test_cronjob_is_a_suspended_template_that_never_retries() -> None:
    cronjob = _doc("cronjob.yaml")
    job = cronjob["spec"]["jobTemplate"]["spec"]
    pod = _pod_spec()
    assert (
        cronjob["metadata"]["name"],
        cronjob["spec"]["suspend"],
        job["backoffLimit"],
        job["ttlSecondsAfterFinished"],
        job["activeDeadlineSeconds"],
        pod["restartPolicy"],
        pod["serviceAccountName"],
        _container()["name"],
        _container()["image"],
        _container()["args"],
        _container()["resources"],
    ) == (
        "devops-cli",
        True,
        0,
        86400,
        7200,
        "Never",
        "devops-cli",
        "devops-cli",
        "ghcr.io/dan-petty/devops-cli/service",
        ["--version"],
        {"requests": {"cpu": "100m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "1Gi"}},
    )


def test_security_context_is_restricted() -> None:
    pod_context = _pod_spec()["securityContext"]
    container_context = _container()["securityContext"]
    assert (
        pod_context["runAsNonRoot"],
        pod_context["seccompProfile"]["type"],
        container_context["readOnlyRootFilesystem"],
        container_context["allowPrivilegeEscalation"],
        container_context["capabilities"]["drop"],
    ) == (True, "RuntimeDefault", True, False, ["ALL"])


def test_credentials_arrive_only_through_the_devops_cli_secret() -> None:
    container = _container()
    secret_env = {"GH_TOKEN", "GITHUB_TOKEN"} | {
        OPTION_TO_ENV_VAR[o] for o in opt.SECRET_CONFIG_OPTIONS if o in OPTION_TO_ENV_VAR
    }
    literal = [
        e["name"] for e in container.get("env", []) if e["name"] in secret_env and "value" in e
    ]
    assert (container["envFrom"], literal) == ([{"secretRef": {"name": "devops-cli"}}], [])


def test_writable_paths_are_empty_dirs_and_the_data_dir_is_under_home() -> None:
    pod = _pod_spec()
    container = _container()
    empty_dirs = {v["name"] for v in pod["volumes"] if "emptyDir" in v}
    mounts = {m["mountPath"] for m in container["volumeMounts"] if m["name"] in empty_dirs}
    env = {e["name"]: e.get("value") for e in container["env"]}
    config_mount = next(m for m in container["volumeMounts"] if m["mountPath"] == "/config")
    assert (
        mounts,
        env["DEVOPS_CLI_DATA_DIR"].startswith("/home/devops"),
        env["DEVOPS_CLI_CONFIG"],
        config_mount["readOnly"],
    ) == ({"/tmp", "/home/devops"}, True, "/config/devops-cli.yaml", True)


def test_config_targets_the_in_cluster_gateway_and_holds_no_credential() -> None:
    raw = yaml.safe_load(_doc("configmap.example.yaml")["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(raw)
    leaked = [key for key in sorted(opt.SECRET_CONFIG_OPTIONS) if _dotted(raw, key) is not None]
    assert (
        settings.ai.provider,
        settings.ai.gateway_url,
        settings.ai.allow_private_network,
        settings.ai.model,
        settings.ai.tasks.analysis.model,
        settings.ai.tasks.analysis.context_window,
        settings.ai.tasks.chat.model,
        settings.telemetry.enabled,
        settings.telemetry.endpoint,
        leaked,
    ) == (
        "gateway",
        "http://llm-gateway.llm.svc.cluster.local:4000/v1",
        True,
        "devops-background",
        "devops-background",
        65536,
        "devops-background",
        True,
        "http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318",
        [],
    )


def _dotted(document: Any, key: str) -> Any:
    for part in key.split("."):
        document = document.get(part) if isinstance(document, dict) else None
    return document


def test_perimeter_admits_no_ingress_and_exactly_four_egress_rules() -> None:
    policy = _doc("networkpolicy.yaml")
    spec = policy["spec"]
    assert (
        policy["metadata"]["name"],
        spec["podSelector"],
        spec["policyTypes"],
        spec.get("ingress"),
        spec["egress"],
    ) == (
        "devops-default-perimeter",
        {},
        ["Ingress", "Egress"],
        None,
        [
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
                "to": [
                    {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "llm"}}}
                ],
                "ports": [{"protocol": "TCP", "port": 4000}],
            },
            {
                "to": [
                    {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "otel"}}}
                ],
                "ports": [{"protocol": "TCP", "port": 4318}, {"protocol": "TCP", "port": 4317}],
            },
            {
                "to": [
                    {
                        "ipBlock": {
                            "cidr": "0.0.0.0/0",
                            "except": [
                                "10.0.0.0/8",
                                "172.16.0.0/12",
                                "192.168.0.0/16",
                                "169.254.169.254/32",
                            ],
                        }
                    }
                ],
                "ports": [{"protocol": "TCP", "port": 443}],
            },
        ],
    )


def test_kustomization_lists_every_manifest_and_pins_no_image_and_stays_out_of_the_root() -> None:
    """Git names the service image untagged; Image Updater sets its digest on Application devops.

    A release writes nothing here (#1486), so the kustomization carries no `images:` entry.
    """
    kustomization = _doc("kustomization.yaml")
    on_disk = [
        p.name
        for p in DEVOPS_DIR.glob("*.yaml")
        if p.name != "kustomization.yaml" and not p.name.endswith(".example.yaml")
    ]
    # A gitignored local copy, such as a configmap.yaml an older deploy-stack wrote, is no manifest
    tracked = subprocess.run(
        ["git", "ls-files", "--", *on_disk],
        cwd=DEVOPS_DIR,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    manifests = sorted([*tracked, "roadmap-service"])
    root = yaml.safe_load((K8S_DIR / "kustomization.yaml").read_text(encoding="utf-8"))
    assert (
        sorted(kustomization["resources"]),
        "images" in kustomization,
        [r for r in root["resources"] if r.startswith("devops")],
    ) == (manifests, False, [])


def test_both_workloads_run_the_digest_image_updater_sets_and_pull_it_only_when_missing(
    tmp_path: Path,
) -> None:
    """Application devops renders the CronJob and roadmap-service on Image Updater's digest (#1485).

    Git names the image untagged, and Argo CD adds the Application's `spec.source.kustomize.images`
    entry, which sets the digest, to the kustomization it builds, as this overlay does. A tag of
    `latest` would default the pull policy to Always, so both containers set IfNotPresent.
    """
    service = "ghcr.io/dan-petty/devops-cli/service"
    digest = f"sha256:{'0' * 64}"
    overlay = K8S_DIR / "overlays" / "homelab" / "devops"
    (tmp_path / "kustomization.yaml").write_text(
        yaml.safe_dump(
            {
                "resources": [os.path.relpath(overlay, tmp_path)],
                "images": [{"name": service, "newTag": "latest", "digest": digest}],
            }
        ),
        encoding="utf-8",
    )
    rendered = subprocess.run(
        ["kubectl", "kustomize", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout
    workloads = [
        d for d in yaml.safe_load_all(rendered) if d and d["kind"] in ("CronJob", "Deployment")
    ]
    containers = {
        (workload["kind"], container["name"], container["image"], container["imagePullPolicy"])
        for workload in workloads
        for container in (
            workload["spec"]["jobTemplate"]["spec"]
            if workload["kind"] == "CronJob"
            else workload["spec"]
        )["template"]["spec"]["containers"]
    }
    assert containers == {
        ("CronJob", "devops-cli", f"{service}:latest@{digest}", "IfNotPresent"),
        ("Deployment", "service", f"{service}:latest@{digest}", "IfNotPresent"),
    }
