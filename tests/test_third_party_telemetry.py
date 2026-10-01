"""Tests verifying third-party telemetry, phone-home, and update checks are disabled."""

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"
DEVCONTAINER_JSON = REPO_ROOT / ".devcontainer" / "devcontainer.json"


def test_grafana_values_disables_telemetry_and_news() -> None:
    """Verify Grafana Helm values disables telemetry reporting, update checks, and news."""
    values_path = K8S_DIR / "monitoring" / "grafana-values.yaml"
    assert values_path.is_file(), f"Missing {values_path}"

    with open(values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    ini = data.get("grafana.ini", {})
    analytics = ini.get("analytics", {})
    news = ini.get("news", {})

    actual = (
        analytics.get("reporting_enabled"),
        analytics.get("check_for_updates"),
        analytics.get("check_for_plugin_updates"),
        analytics.get("feedback_links_enabled"),
        news.get("news_feed_enabled"),
    )
    expected = (False, False, False, False, False)
    assert actual == expected


def test_k8s_monitoring_values_disables_alloy_telemetry() -> None:
    """Verify k8s-monitoring Helm values disables self-reporting and Alloy telemetry."""
    values_path = K8S_DIR / "monitoring" / "k8s-monitoring-values.yaml"
    assert values_path.is_file(), f"Missing {values_path}"

    with open(values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    self_reporting = data.get("selfReporting", {}).get("enabled")
    collectors = data.get("collectors", {})
    metrics_rep = collectors.get("alloy-metrics", {}).get("alloy", {}).get("enableReporting")
    singleton_rep = collectors.get("alloy-singleton", {}).get("alloy", {}).get("enableReporting")
    logs_rep = collectors.get("alloy-logs", {}).get("alloy", {}).get("enableReporting")

    assert (self_reporting, metrics_rep, singleton_rep, logs_rep) == (False, False, False, False)


def test_loki_values_disables_analytics() -> None:
    """Verify Loki Helm values disables anonymous usage reporting."""
    values_path = K8S_DIR / "logging" / "loki-values.yaml"
    assert values_path.is_file(), f"Missing {values_path}"

    with open(values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    analytics = data.get("loki", {}).get("analytics", {})
    assert analytics.get("reporting_enabled") is False


def test_traefik_values_disables_telemetry_and_version_check() -> None:
    """Verify Traefik Helm values passes flags to disable anonymous usage and version check."""
    values_path = K8S_DIR / "ingress" / "traefik-values.yaml"
    assert values_path.is_file(), f"Missing {values_path}"

    with open(values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    args = data.get("additionalArguments", [])
    assert "--global.sendanonymoususage=false" in args
    assert "--global.checknewversion=false" in args


def test_open_webui_values_disables_telemetry_and_version_check() -> None:
    """Verify Open-WebUI Helm values disables version update check and analytics."""
    values_path = K8S_DIR / "llm" / "values-open-webui.yaml"
    assert values_path.is_file(), f"Missing {values_path}"

    with open(values_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    env_map = {item["name"]: item["value"] for item in data.get("extraEnvVars", [])}
    actual = (
        env_map.get("ENABLE_VERSION_UPDATE_CHECK"),
        env_map.get("ANONYMIZED_TELEMETRY"),
        env_map.get("DO_NOT_TRACK"),
        env_map.get("SCARF_NO_ANALYTICS"),
    )
    expected = ("false", "false", "true", "true")
    assert actual == expected


def test_litellm_gateway_disables_telemetry() -> None:
    """Verify LiteLLM Gateway configmap and deployment disable telemetry."""
    configmap_path = K8S_DIR / "llm" / "gateway" / "configmap.yaml"
    deployment_path = K8S_DIR / "llm" / "gateway" / "deployment.yaml"
    assert configmap_path.is_file() and deployment_path.is_file()

    cm_data = yaml.safe_load(configmap_path.read_text(encoding="utf-8"))
    config_yaml = yaml.safe_load(cm_data.get("data", {}).get("config.yaml", ""))
    litellm_settings = config_yaml.get("litellm_settings", {})
    assert litellm_settings.get("telemetry") is False

    dep_data = yaml.safe_load(deployment_path.read_text(encoding="utf-8"))
    container = dep_data["spec"]["template"]["spec"]["containers"][0]
    dep_env = {
        item["name"]: item.get("value") for item in container.get("env", []) if "value" in item
    }
    assert dep_env.get("LITELLM_TELEMETRY") == "False"


def test_devcontainer_disables_telemetry() -> None:
    """Verify devcontainer.json specifies telemetry opt-out variables and editor settings."""
    assert DEVCONTAINER_JSON.is_file(), f"Missing {DEVCONTAINER_JSON}"

    data = json.loads(DEVCONTAINER_JSON.read_text(encoding="utf-8"))
    env = data.get("containerEnv", {})

    actual_env = (
        env.get("DO_NOT_TRACK"),
        env.get("HF_HUB_DISABLE_TELEMETRY"),
        env.get("SCARF_NO_ANALYTICS"),
        env.get("NEXT_TELEMETRY_DISABLED"),
        env.get("CHECKPOINT_DISABLE"),
        env.get("DOTNET_CLI_TELEMETRY_OPTOUT"),
        env.get("ANONYMIZED_TELEMETRY"),
        env.get("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"),
        env.get("DISABLE_TELEMETRY"),
        env.get("GOTELEMETRY"),
        env.get("PIP_DISABLE_PIP_VERSION_CHECK"),
        env.get("npm_config_update_notifier"),
        env.get("DOCKER_CLI_HINTS"),
        env.get("MINIKUBE_WANTUPDATENOTIFICATION"),
        env.get("MINIKUBE_WANTREPORTERRORPROMPT"),
    )
    expected_env = (
        "1",
        "1",
        "true",
        "1",
        "1",
        "1",
        "false",
        "1",
        "1",
        "off",
        "1",
        "false",
        "false",
        "false",
        "false",
    )
    assert actual_env == expected_env

    vscode_settings = data.get("customizations", {}).get("vscode", {}).get("settings", {})
    actual_settings = (
        vscode_settings.get("telemetry.telemetryLevel"),
        vscode_settings.get("redhat.telemetry.enabled"),
        vscode_settings.get("workbench.enableExperiments"),
    )
    expected_settings = ("off", False, False)
    assert actual_settings == expected_settings
