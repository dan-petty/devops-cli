"""The in-cluster devops-cli runtime under k8s/devops/: namespace, CronJob template and perimeter."""

from __future__ import annotations

import functools
from typing import Any

import yaml

from devops_cli.config.constants import (
    CONST_AI_GATEWAY_HOSTED_MODELS,
    CONST_OTEL_SERVICE_NAME,
    CONST_ROADMAP_IMPLEMENT_STEP_CLASSES,
    CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS,
)
from devops_cli.config.env import CREDENTIALS
from devops_cli.config.settings import AITasksConfig, Settings
from tests.support.paths import REPO_ROOT

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


def test_cluster_jobs_report_under_a_service_name_of_their_own() -> None:
    """A Job made from the template sends its telemetry under its own `job` in Prometheus, apart
    from workstation runs, which use the default service name, and from roadmap-service (#1629)."""
    job_env = {e["name"]: e.get("value") for e in _container()["env"]}
    service = _doc("roadmap-service/deployment.yaml")["spec"]["template"]["spec"]
    (service_container,) = service["containers"]
    service_env = {e["name"]: e.get("value") for e in service_container["env"]}
    assert (
        job_env.get("OTEL_SERVICE_NAME"),
        CONST_OTEL_SERVICE_NAME,
        service_env["OTEL_SERVICE_NAME"],
    ) == ("devops-cli-job", "devops-cli", "roadmap-service")


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
        variable for credential in CREDENTIALS for variable in credential.env_vars
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
    ) == (
        {"/tmp", "/home/devops"},  # nosec B108  # the pod's emptyDir mount paths, under test
        True,
        "/config/devops-cli.yaml",
        True,
    )


def test_config_targets_the_in_cluster_gateway_and_holds_no_credential() -> None:
    """The example validates as settings, calls the model through the gateway in the cluster, and
    holds no credential. The models, windows and limits are the owner's to tune, so the test pins
    none of them."""
    raw = yaml.safe_load(_doc("configmap.example.yaml")["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(raw)
    leaked = [c.key for c in CREDENTIALS if _dotted(raw, c.key) is not None]
    assert (
        settings.ai.provider,
        str(settings.ai.gateway_url).split("/")[2].endswith(".svc.cluster.local:4000"),
        leaked,
    ) == ("gateway", True, [])


def test_the_implement_step_runs_on_a_hosted_gateway_group_that_fits_its_window() -> None:
    """The example ConfigMap names, for the task `implement` and for each step class of the
    ladder, a group that the gateway config serves and that is hosted. The window of the task is
    not above the window of that group, and holds a step and the turn reserve (#3573). A rename of
    the group in `k8s/llm/gateway/config.yaml` fails this test."""
    raw = yaml.safe_load(_doc("configmap.example.yaml")["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(raw)
    gateway = yaml.safe_load((K8S_DIR / "llm" / "gateway" / "config.yaml").read_text("utf-8"))
    served = {entry["model_name"]: entry for entry in gateway["model_list"]}
    task = settings.ai.for_task("implement")
    ladder = settings.roadmap.implement.ladder
    tiers = {task.model, *(tier for step in ladder.values() for tier in step)}
    group_window = served[task.model]["model_info"]["max_input_tokens"]

    assert (
        sorted(tiers - served.keys()),
        sorted(tiers - set(CONST_AI_GATEWAY_HOSTED_MODELS)),
        sorted(ladder) == sorted(CONST_ROADMAP_IMPLEMENT_STEP_CLASSES),
        task.context_window <= group_window,
        settings.roadmap.stage.step_tokens + CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS
        <= task.context_window,
    ) == ([], [], True, True, True)


DEEPSEEK = "deepseek-v4.1-flash-1017"
SONNET = "claude-sonnet-5-5"


def test_the_analysis_slot_is_the_sonnet_trial_and_every_other_chat_slot_is_deepseek() -> None:
    """The owner tries Sonnet in the `analysis` slot, because the stage job stages nothing with
    DeepSeek (#4204). The task `stage` takes its model and window from `analysis`. Every other
    chat slot stays on DeepSeek (#3874), and the embedding slot stays the embedding model."""
    template = _doc("configmap.example.yaml")["data"]["devops-cli.yaml"]
    ai = Settings.model_validate(yaml.safe_load(template)).ai
    slots = {name: ai.for_task(name).model for name in AITasksConfig.model_fields}

    assert (
        ai.model,
        {name: model for name, model in slots.items() if model != DEEPSEEK},
        ai.for_task("analysis").context_window,
        ai.for_task("stage").context_window,
    ) == (
        DEEPSEEK,
        {"analysis": SONNET, "stage": SONNET, "embedding": "qwen3-embedding:0.6b"},
        200000,
        200000,
    )


def test_the_comment_above_the_analysis_slot_names_the_reason_the_cost_and_the_way_back() -> None:
    """The trial leaves the one-model rule (#3874). The comment says why, who decided, what it
    costs and when to undo it, so a person who reads the template does not take it for drift."""
    text = (DEVOPS_DIR / "configmap.example.yaml").read_text(encoding="utf-8")
    comment = text.split("        analysis:\n")[0].rsplit("      tasks:\n", 1)[1]

    assert [
        needle
        for needle in ("#4204", "2026-11-09", "0.27 USD", "3 items", "37 minutes", "#3874")
        if needle not in comment
    ] == []


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
        # Every pod but the Crawl4AI and SearXNG pods, which have their own policies (#3884, #3924)
        {
            "matchExpressions": [
                {
                    "key": "app.kubernetes.io/name",
                    "operator": "NotIn",
                    "values": ["crawl4ai", "searxng"],
                }
            ]
        },
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
                "ports": [{"protocol": "TCP", "port": 4000}, {"protocol": "TCP", "port": 6379}],
            },
            {
                "to": [
                    {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "otel"}}}
                ],
                "ports": [{"protocol": "TCP", "port": 4318}],
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
                                "100.64.0.0/10",
                                "169.254.0.0/16",
                                "169.254.169.254/32",
                                "192.0.0.0/24",
                                "198.18.0.0/15",
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
        if p.name != "kustomization.yaml"
        and not p.name.endswith(".example.yaml")
        and p.name != "configmap.yaml"
    ]
    manifests = sorted([*on_disk, "crawl4ai", "mcp-server", "roadmap-service", "searxng"])
    root = yaml.safe_load((K8S_DIR / "kustomization.yaml").read_text(encoding="utf-8"))
    assert (
        sorted(kustomization["resources"]),
        "images" in kustomization,
        [r for r in root["resources"] if r.startswith("devops")],
    ) == (manifests, False, [])


def test_mcp_server_and_workloads_disable_telemetry_and_banners() -> None:
    """The MCP server, runner CronJob and roadmap Service disable CLI banners and external telemetry."""
    mcp_deploy = _doc("mcp-server/deployment.yaml")
    mcp_pod = mcp_deploy["spec"]["template"]["spec"]
    (mcp_container,) = mcp_pod["containers"]
    mcp_env = {e["name"]: e.get("value") for e in mcp_container["env"]}

    runner_pod = _doc("cronjob-runner.yaml")["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    (runner_container,) = runner_pod["containers"]
    runner_env = {e["name"]: e.get("value") for e in runner_container["env"]}

    service_pod = _doc("roadmap-service/deployment.yaml")["spec"]["template"]["spec"]
    (service_container,) = service_pod["containers"]
    service_env = {e["name"]: e.get("value") for e in service_container["env"]}

    expected_flags = {
        "DO_NOT_TRACK": "1",
        "OPENSPEC_TELEMETRY": "0",
        "OPENSPEC_NO_UPDATE_CHECK": "1",
        "PYDANTIC_AI_NO_BANNER": "1",
    }
    assert (
        mcp_deploy["metadata"]["name"],
        mcp_pod["automountServiceAccountToken"],
        mcp_container["image"],
        {k: mcp_env.get(k) for k in expected_flags},
        {k: runner_env.get(k) for k in expected_flags},
        {k: service_env.get(k) for k in expected_flags},
    ) == (
        "mcp-server",
        False,
        "ghcr.io/dan-petty/devops-cli/mcp-server",
        expected_flags,
        expected_flags,
        expected_flags,
    )
