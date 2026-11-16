"""The in-cluster devops-cli runtime under k8s/devops/: namespace, CronJob template and perimeter."""

from __future__ import annotations

import functools
from typing import Any

import yaml

from devops_cli.config import defaults
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


def test_both_cronjob_templates_set_the_runner_instance() -> None:
    """Both cluster job templates name one metric stream for their workload, so the stream of
    `devops-cli-job` continues across the Job pods instead of starting again at zero in the same
    Prometheus series (#4697). The value is plain: it names a stream and holds no secret."""
    documents = {name: _doc(name) for name in ("cronjob.yaml", "cronjob-runner.yaml")}
    envs = {
        name: {
            entry["name"]: entry
            for entry in document["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][
                0
            ]["env"]
        }
        for name, document in documents.items()
    }
    entries = {name: envs[name].get("OTEL_RESOURCE_ATTRIBUTES") for name in envs}
    credential_names = {"GH_TOKEN", "GITHUB_TOKEN"} | {
        variable for credential in CREDENTIALS for variable in credential.env_vars
    }
    assert (
        entries,
        [name for name, entry in entries.items() if "valueFrom" in (entry or {})],
        [
            secret
            for secret in credential_names
            if any(secret in (entry or {}).get("value", "") for entry in entries.values())
        ],
        {name: envs[name].get("OTEL_SERVICE_NAME", {}).get("value") for name in envs},
    ) == (
        {
            name: {
                "name": "OTEL_RESOURCE_ATTRIBUTES",
                "value": "service.instance.id=devops-cli-job",
            }
            for name in documents
        },
        [],
        [],
        {"cronjob.yaml": "devops-cli-job", "cronjob-runner.yaml": "roadmap-implement"},
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


CLUSTER_DOC = REPO_ROOT / "docs" / "CLUSTER.md"


def _cluster_doc_section(heading: str) -> str:
    """The line of docs/CLUSTER.md that the bold heading `heading` starts."""
    return next(
        line
        for line in CLUSTER_DOC.read_text(encoding="utf-8").splitlines()
        if line.startswith(f"- **{heading}.**")
    )


def test_the_size_section_names_the_default_and_the_example_limit() -> None:
    """The example ConfigMap sets the runner memory limit of this cluster (#5484), and the Size
    and the Deadline lines of docs/CLUSTER.md state the setting, the code default `8Gi` and the
    `16Gi` of the template. A line that keeps one of them alone makes a person believe the Jobs
    run under the other limit."""
    raw = yaml.safe_load(_doc("configmap.example.yaml")["data"]["devops-cli.yaml"])
    limit = Settings.model_validate(raw).roadmap.implement.max_memory_limit
    template = (DEVOPS_DIR / "configmap.example.yaml").read_text(encoding="utf-8")
    needles = ("roadmap.implement.max_memory_limit", "8Gi", "16Gi")

    assert (
        limit,
        "#5484" in template,
        {
            heading: [needle for needle in needles if needle not in _cluster_doc_section(heading)]
            for heading in ("Size", "Deadline")
        },
    ) == ("16Gi", True, {"Size": [], "Deadline": []})


def test_the_implement_step_runs_on_a_hosted_gateway_group_that_fits_its_window() -> None:
    """The example ConfigMap names, for the task `implement` and for each step class of the
    ladder, a group that the gateway config serves and that is hosted. The window of the task is
    not above the window of that group, and holds a step and the turn reserve (#3573). A rename of
    the group in `k8s/llm/gateway/config.yaml` fails this test."""
    raw = yaml.safe_load(_doc("configmap.example.yaml")["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(raw)
    gateway = yaml.safe_load((K8S_DIR / "llm" / "gateway" / "config.yaml").read_text("utf-8"))
    served = {entry["model_name"]: entry for entry in gateway["model_list"]}
    aliases = gateway.get("router_settings", {}).get("model_group_alias", {})
    for alias, target in aliases.items():
        if target in served and alias not in served:
            served[alias] = served[target]
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


DEEPSEEK = "openrouter/deepseek/deepseek-v4.1-flash-1017"


# The task of each model role of a roadmap job, with the window it had through its old slot
# (#5903). Intake and retitle had no window.
JOB_WINDOWS = {
    "stage": 256000,
    "stage_review": 256000,
    "fix_plan": 256000,
    "fix_plan_review": 256000,
    "refine": 256000,
    "refine_review": 256000,
    "alternatives": 256000,
    "consolidate": 256000,
    "implement": 256000,
    "implement_split": 256000,
    "intake": None,
    "retitle": None,
}
LOCAL_JOBS = {"intake", "retitle"}


def test_each_job_has_its_own_entry_in_the_template_and_no_job_reads_an_old_slot() -> None:
    """Each roadmap job names its own model, so a trial moves one job (#5903). A job starts on
    DeepSeek (#3874, #4369); intake and retitle run on the local model by the owner decision of
    2026-11-15, and refine and the alternatives check in the owner trial of 2026-11-16. The
    template sets no old shared slot, and the embedding slot stays the embedding model."""
    template = yaml.safe_load(_doc("configmap.example.yaml")["data"]["devops-cli.yaml"])
    ai = Settings.model_validate(template).ai
    slots = {name: ai.for_task(name).model for name in AITasksConfig.model_fields}
    entries = template["ai"]["tasks"]

    assert (
        ai.model,
        {name: model for name, model in slots.items() if model != DEEPSEEK},
        {name: entries[name].get("context_window") for name in JOB_WINDOWS},
        sorted({"analysis", "verification", "triage"} & entries.keys()),
    ) == (
        DEEPSEEK,
        {name: "local/qwen3.8:27b" for name in LOCAL_JOBS}
        | {"embedding": "local/qwen3-embedding:0.6b"},
        JOB_WINDOWS,
        [],
    )


def test_the_template_holds_the_doubled_attempt_limits() -> None:
    """The owner chose twice the default limits of the stage, implement and fix-plan attempts
    (2026-11-13, again 2026-11-16). A deploy renders the template, so a limit that only the live
    ConfigMap holds is lost (#5583). The item time stops at the ceiling of the Job deadline, and
    the two implement token budgets are four times the defaults by the owner rule of 2026-11-16 (#5970)."""
    template = _doc("configmap.example.yaml")["data"]["devops-cli.yaml"]
    roadmap = Settings.model_validate(yaml.safe_load(template)).roadmap
    stage, implement, fix_plan = roadmap.stage, roadmap.implement, roadmap.fix_plan

    assert {
        "stage": (
            stage.verify_repair_rounds,
            stage.verify_repair_rounds_ceiling,
            stage.gate_returns,
            stage.gate_return_extensions,
            stage.plan_defect_limit,
            stage.max_requests,
            stage.max_tool_calls,
        ),
        "implement": (
            implement.repair_rounds,
            implement.command_timeout_seconds,
            implement.request_timeout_seconds,
            implement.monitor_timeout_seconds,
            implement.step_time_limit_seconds,
            implement.deadline_stall_seconds,
            implement.deadline_extension_seconds,
            implement.digest_clears_per_class,
            implement.digest_clears_per_item,
            implement.continuations_per_item,
            implement.max_requests,
            implement.max_tool_calls,
            implement.tool_retries,
            implement.max_refusals,
            implement.max_consecutive_refusals,
            implement.model_resends,
        ),
        "tokens": (implement.step_token_budget, implement.item_token_budget),
        "item": (implement.item_time_limit_seconds, implement.deadline_ceiling_seconds),
        "fix_plan": (fix_plan.time_budget_seconds, fix_plan.head_attempts, fix_plan.revisions),
    } == {
        "stage": tuple(
            2 * value
            for value in (
                defaults.DEFAULT_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS,
                defaults.DEFAULT_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING,
                defaults.DEFAULT_ROADMAP_STAGE_GATE_RETURNS,
                defaults.DEFAULT_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS,
                defaults.DEFAULT_ROADMAP_STAGE_PLAN_DEFECT_LIMIT,
                defaults.DEFAULT_ROADMAP_STAGE_MAX_REQUESTS,
                defaults.DEFAULT_ROADMAP_STAGE_MAX_TOOL_CALLS,
            )
        ),
        "implement": tuple(
            2 * value
            for value in (
                defaults.DEFAULT_ROADMAP_IMPLEMENT_REPAIR_ROUNDS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_STEP_TIME_LIMIT_SECONDS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_EXTENSION_SECONDS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_DIGEST_CLEARS_PER_CLASS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_DIGEST_CLEARS_PER_ITEM,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_CONTINUATIONS_PER_ITEM,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_MAX_REQUESTS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_TOOL_RETRIES,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_MAX_REFUSALS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS,
                defaults.DEFAULT_ROADMAP_IMPLEMENT_MODEL_RESENDS,
            )
        ),
        "tokens": (
            4 * defaults.DEFAULT_ROADMAP_IMPLEMENT_STEP_TOKEN_BUDGET,
            4 * defaults.DEFAULT_ROADMAP_IMPLEMENT_ITEM_TOKEN_BUDGET,
        ),
        "item": (defaults.DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS,) * 2,
        "fix_plan": tuple(
            2 * value
            for value in (
                defaults.DEFAULT_ROADMAP_FIX_PLAN_TIME_BUDGET_SECONDS,
                defaults.DEFAULT_ROADMAP_FIX_PLAN_HEAD_ATTEMPTS,
                defaults.DEFAULT_ROADMAP_FIX_PLAN_REVISIONS,
            )
        ),
    }


def test_the_comment_above_the_job_tasks_names_the_decision_the_cost_and_the_trial() -> None:
    """The planner left Sonnet on 2026-11-10. The comment says who decided, why and what Sonnet
    cost, so a person who reads the template does not put the trial back by mistake."""
    text = (DEVOPS_DIR / "configmap.example.yaml").read_text(encoding="utf-8")
    comment = text.split("        stage:\n")[0].rsplit("      tasks:\n", 1)[1]

    assert [
        needle
        for needle in ("#4369", "2026-11-10", "#4204", "67 USD a week", "#3874", "Sonnet")
        if needle not in comment
    ] == []


def test_every_step_class_of_the_implement_ladder_has_the_one_deepseek_tier() -> None:
    """The cluster ConfigMap has one tier for `edit` and for `repair`, and docs/CLUSTER.md says that a
    step has one tier (#4371). The template says the same, so a render does not add a tier that
    sends the prompts of a step to Anthropic. The support for more tiers stays in the code."""
    template = _doc("configmap.example.yaml")["data"]["devops-cli.yaml"]
    ladder = Settings.model_validate(yaml.safe_load(template)).roadmap.implement.ladder

    assert ladder == {step_class: [DEEPSEEK] for step_class in CONST_ROADMAP_IMPLEMENT_STEP_CLASSES}


def test_the_comment_above_the_implement_ladder_names_the_decision_and_the_later_trial() -> None:
    """A person who reads the template learns who chose one tier, and that a Sonnet tier is a later
    trial, so the second tier of #4274 does not come back by mistake."""
    text = (DEVOPS_DIR / "configmap.example.yaml").read_text(encoding="utf-8")
    comment = text.split("\n      implement:\n")[0].rsplit("first_pass_limit: 20\n", 1)[1]

    assert [
        needle
        for needle in ("#4371", "2026-11-10", "#4274", "one tier", "Sonnet", "later trial")
        if needle not in comment
    ] == []


def _dotted(document: Any, key: str) -> Any:
    for part in key.split("."):
        document = document.get(part) if isinstance(document, dict) else None
    return document


def test_perimeter_admits_no_ingress_and_exactly_five_egress_rules() -> None:
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
        # Every pod but the Crawl4AI, SearXNG and Renovate pods, which have their own policies
        # (#3884, #3924, #4905)
        {
            "matchExpressions": [
                {
                    "key": "app.kubernetes.io/name",
                    "operator": "NotIn",
                    "values": ["crawl4ai", "searxng", "renovate"],
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
                    {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "llm"}}}
                ],
                "ports": [{"protocol": "TCP", "port": 6333}],
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
    manifests = sorted(
        [*on_disk, "crawl4ai", "mcp-server", "renovate", "roadmap-service", "searxng"]
    )
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


def test_mcp_server_reads_its_bearer_token_from_the_secret_that_the_push_writes() -> None:
    """The server refuses to start without `mcp.token`, so the pod takes it from its own Secret."""
    (container,) = _doc("mcp-server/deployment.yaml")["spec"]["template"]["spec"]["containers"]
    (token,) = (e for e in container["env"] if e["name"] == "DEVOPS_CLI_MCP_TOKEN")
    assert token == {
        "name": "DEVOPS_CLI_MCP_TOKEN",
        "valueFrom": {"secretKeyRef": {"name": "mcp-server", "key": "DEVOPS_CLI_MCP_TOKEN"}},
    }


def test_the_config_names_the_qdrant_service_and_holds_no_key() -> None:
    """The pods reach Qdrant in namespace llm at its ClusterIP Service, and the key reaches them
    from Secret devops/devops-cli (#3823)."""
    raw = yaml.safe_load(_doc("configmap.example.yaml")["data"]["devops-cli.yaml"])

    assert (raw["qdrant"], "api_key" in raw["qdrant"]) == (
        {"url": "http://qdrant.llm.svc.cluster.local:6333"},
        False,
    )
