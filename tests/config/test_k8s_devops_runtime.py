"""The in-cluster devops-cli runtime under k8s/devops/: namespace, CronJob template and perimeter."""

from __future__ import annotations

import functools
from typing import Any

import yaml

from devops_cli.config.env import CREDENTIALS
from devops_cli.config.settings import Settings
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


def test_config_validates_as_settings_and_holds_no_credential() -> None:
    """The example validates as settings and holds no credential. The values are the owner's to
    tune, so the test pins none of them."""
    raw = yaml.safe_load(_doc("configmap.example.yaml")["data"]["devops-cli.yaml"])
    Settings.model_validate(raw)
    leaked = [c.key for c in CREDENTIALS if _dotted(raw, c.key) is not None]
    assert leaked == []


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
        # Every pod but the Crawl4AI, SearXNG, Renovate and planner run pods, which have their own
        # policies (#3884, #3924, #4905, #6065)
        {
            "matchExpressions": [
                {
                    "key": "app.kubernetes.io/name",
                    "operator": "NotIn",
                    "values": ["crawl4ai", "searxng", "renovate", "devops-cli-planner-run"],
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
