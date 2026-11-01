"""Each setting is declared once, on its settings field or as a credential, and every list of
settings, variables and keyring entries is a view of that declaration (#2444)."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.config import env
from devops_cli.config.settings import Settings, dotted_get
from devops_cli.security.secrets import build_secret_registry

pytestmark = pytest.mark.usefixtures("keyring_store")

# Every variable that set a setting or a credential before the declaration moved onto the fields
# (origin/main 22654249): the option map, the variables of each credential and the spec list.
_VARIABLES_BEFORE = frozenset(
    {
        "CLOUDFLARE_API_TOKEN",
        "DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK",
        "DEVOPS_CLI_AI_API_BASE_URL",
        "DEVOPS_CLI_AI_API_KEY",
        "DEVOPS_CLI_AI_GATEWAY_URL",
        "DEVOPS_CLI_AI_MAX_RETRIES",
        "DEVOPS_CLI_AI_MODEL",
        "DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL",
        "DEVOPS_CLI_AI_OLLAMA_URLS",
        "DEVOPS_CLI_AI_PROVIDER",
        "DEVOPS_CLI_AI_RAG_ENABLED",
        "DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD",
        "DEVOPS_CLI_AI_RAG_TOP_K",
        "DEVOPS_CLI_AI_REASONING_EFFORT",
        "DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL",
        "DEVOPS_CLI_AI_TASK_ANALYSIS_OLLAMA_URLS",
        "DEVOPS_CLI_AI_TASK_ANALYSIS_PROVIDER",
        "DEVOPS_CLI_AI_TASK_ANALYSIS_REASONING_EFFORT",
        "DEVOPS_CLI_AI_TASK_CHAT_MODEL",
        "DEVOPS_CLI_AI_TASK_CHAT_OLLAMA_URLS",
        "DEVOPS_CLI_AI_TASK_CHAT_PROVIDER",
        "DEVOPS_CLI_AI_TASK_CHAT_REASONING_EFFORT",
        "DEVOPS_CLI_AI_TASK_EMBEDDING_MODEL",
        "DEVOPS_CLI_AI_TASK_EMBEDDING_OLLAMA_URLS",
        "DEVOPS_CLI_AI_TASK_EMBEDDING_PROVIDER",
        "DEVOPS_CLI_AI_TASK_EMBEDDING_REASONING_EFFORT",
        "DEVOPS_CLI_AI_TASK_EMBEDDING_TIMEOUT",
        "DEVOPS_CLI_AI_TASK_METADATA_MODEL",
        "DEVOPS_CLI_AI_TASK_METADATA_OLLAMA_URLS",
        "DEVOPS_CLI_AI_TASK_METADATA_PROVIDER",
        "DEVOPS_CLI_AI_TASK_METADATA_REASONING_EFFORT",
        "DEVOPS_CLI_ARGOCD_PASSWORD",
        "DEVOPS_CLI_ARGOCD_TOKEN",
        "DEVOPS_CLI_ARGOCD_URL",
        "DEVOPS_CLI_CI_GATE_SLOTS",
        "DEVOPS_CLI_CLOUDFLARE_ACCOUNT_ID",
        "DEVOPS_CLI_CLOUDFLARE_API_TOKEN",
        "DEVOPS_CLI_CLOUDFLARE_DOMAIN",
        "DEVOPS_CLI_CLOUDFLARE_TUNNEL",
        "DEVOPS_CLI_CLOUDFLARE_TUNNEL_TOKEN",
        "DEVOPS_CLI_CLOUDFLARE_ZONE_ID",
        "DEVOPS_CLI_CONFIG",
        "DEVOPS_CLI_DATA_ANALYSIS_DIR",
        "DEVOPS_CLI_DATA_AUDIT_LOG_PATH",
        "DEVOPS_CLI_DATA_BENCHMARKS_DIR",
        "DEVOPS_CLI_DATA_CACHE_DIR",
        "DEVOPS_CLI_DATA_DIR",
        "DEVOPS_CLI_DATA_FEEDBACK_DATASET_PATH",
        "DEVOPS_CLI_DATA_LOGS_DIR",
        "DEVOPS_CLI_DATA_MODELS_DIR",
        "DEVOPS_CLI_DATA_RAG_DIR",
        "DEVOPS_CLI_DATA_REVIEWS_DIR",
        "DEVOPS_CLI_DATA_RUNS_DIR",
        "DEVOPS_CLI_DATA_SAMPLES_DIR",
        "DEVOPS_CLI_DATA_TLS_DIR",
        "DEVOPS_CLI_FIRECRAWL_API_KEY",
        "DEVOPS_CLI_GITEA_ADMIN_PASSWORD",
        "DEVOPS_CLI_GITHUB_DEFAULT_ORG",
        "DEVOPS_CLI_GRAFANA_PASSWORD",
        "DEVOPS_CLI_GRAFANA_TOKEN",
        "DEVOPS_CLI_GRAFANA_URL",
        "DEVOPS_CLI_K8S_CONTEXT",
        "DEVOPS_CLI_K8S_DOMAIN",
        "DEVOPS_CLI_PROMETHEUS_URL",
        "DEVOPS_CLI_QDRANT_API_KEY",
        "DEVOPS_CLI_QDRANT_COLLECTION_PREFIX",
        "DEVOPS_CLI_QDRANT_TIMEOUT",
        "DEVOPS_CLI_QDRANT_URL",
        "DEVOPS_CLI_REPOS_BASE_DIR",
        "DEVOPS_CLI_RUNS_INDEX_PASSWORD",
        "DEVOPS_CLI_RUNS_INDEX_URL",
        "DEVOPS_CLI_SERVICE_DRAIN_TIMEOUT_SECONDS",
        "DEVOPS_CLI_SERVICE_GITHUB_APP_APP_ID",
        "DEVOPS_CLI_SERVICE_GITHUB_APP_INSTALLATION_ID",
        "DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY",
        "DEVOPS_CLI_SERVICE_GITHUB_APP_SLUG",
        "DEVOPS_CLI_SERVICE_POLL_INTERVAL_SECONDS",
        "DEVOPS_CLI_SERVICE_REPOS",
        "DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS",
        "DEVOPS_CLI_SSH_KEY_DIR",
        "DEVOPS_CLI_SSH_KEY_PREFIX",
        "DEVOPS_CLI_SSH_ROTATION_DAYS",
        "DEVOPS_CLI_TELEMETRY_ENABLED",
        "DEVOPS_CLI_TELEMETRY_ENDPOINT",
        "DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN",
        "DEVOPS_CLI_VALKEY_PASSWORD",
        "DEVOPS_CLI_VALKEY_TIMEOUT",
        "DEVOPS_CLI_VALKEY_URL",
        "DEVOPS_CLI_WORKSPACE_FILE",
        "FIRECRAWL_API_KEY",
        "LOGFIRE_TOKEN",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
    }
)

# The options that had no variable before, and that code reads: each now has one by the rule.
_VARIABLES_ADDED = frozenset(
    {
        "DEVOPS_CLI_AI_HARDWARE_COST_USD",
        "DEVOPS_CLI_AI_REFERENCE_EMBEDDING_MODEL",
        "DEVOPS_CLI_AI_REFERENCE_MODEL",
        "DEVOPS_CLI_AI_REFERENCE_PROVIDER",
        "DEVOPS_CLI_CLOUDFLARE_ACCESS_ALLOWED_EMAILS",
        "DEVOPS_CLI_CLOUDFLARE_ACCESS_BYPASS_IPS",
        "DEVOPS_CLI_CLOUDFLARE_ACCESS_PUBLIC_IP_BYPASS",
        "DEVOPS_CLI_CLOUDFLARE_PUBLIC_IP_BYPASS",
        "DEVOPS_CLI_SANDBOX_EXCLUDE_HOME_DIR",
        "DEVOPS_CLI_TELEMETRY_CAPTURE_LLM_CONTENT",
    }
)

# Settings added after the declaration moved onto the fields: each has its variable by the rule.
_VARIABLES_OF_LATER_SETTINGS = frozenset(
    {
        "DEVOPS_CLI_K8S_TUNNEL_HOST",  # #1641
        "DEVOPS_CLI_ARGOCD_GITHUB_APP_ID",  # #2000
        "DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID",  # #2000
        "DEVOPS_CLI_ARGOCD_GITHUB_APP_PRIVATE_KEY",  # #2000
        "DEVOPS_CLI_SERVICE_MODEL_CALL_CONCURRENCY",  # #2564
        "DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS",  # #2654
        "DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER",  # #2665
        "DEVOPS_CLI_ROADMAP_IMPLEMENT_REPAIR_ROUNDS",  # #3043
        "DEVOPS_CLI_ROADMAP_STAGE_FILTER",  # #2659
        "DEVOPS_CLI_ROADMAP_STAGE_LIMIT",  # #2659
        "DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY",  # #2667
        "DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR",  # #2755
        "DEVOPS_CLI_MATTERMOST_ALERTS_HOOK",  # #1392
        "DEVOPS_CLI_MATTERMOST_DEPLOYS_HOOK",  # #1393
        "DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN",  # #1395
    }
)

_KEYRING_BEFORE = {
    "ai.api_key": "ai_api_key",
    "argocd.password": "argocd_password",
    "argocd.token": "argocd_token",
    "cloudflare.api_token": "cloudflare_api_token",
    "cloudflare.tunnel_token": "cloudflare_tunnel_token",
    "firecrawl.api_key": "firecrawl_api_key",
    "gitea.admin_password": "gitea_admin_password",
    "grafana.password": "grafana_password",
    "grafana.token": "grafana_token",
    "qdrant.api_key": "qdrant_api_key",
    "runs.index_password": "runs_index_password",
    "service.github_app.private_key": "service_github_app_private_key",
    "service.webhook_secrets": "service_webhook_secrets",
    "telemetry.logfire_token": "logfire_token",
    "valkey.password": "valkey_password",
}


# Credentials added after the declaration moved onto the fields.
_KEYRING_OF_LATER_CREDENTIALS = {
    "argocd.github_app_private_key": "argocd_github_app_private_key",  # #2000
    "mattermost.alerts_hook": "mattermost_alerts_hook",  # #1392
    "mattermost.deploys_hook": "mattermost_deploys_hook",  # #1393
    "mattermost.command_token": "mattermost_command_token",  # #1395
}


def _variables_read() -> set[str]:
    credential_variables = {var for ref in build_secret_registry().values() for var in ref.env_vars}
    specs = {spec.env_var for spec in env.get_all_env_var_specs()}
    return set(env.setting_variables().values()) | credential_variables | specs


def test_the_variables_are_those_before_one_for_each_read_option_that_had_none_and_later_ones() -> (
    None
):
    assert sorted(_variables_read()) == sorted(
        _VARIABLES_BEFORE | _VARIABLES_ADDED | _VARIABLES_OF_LATER_SETTINGS
    )


def test_the_keyring_entries_and_the_secret_keys_are_those_before_and_later_ones() -> None:
    keyring = {**_KEYRING_BEFORE, **_KEYRING_OF_LATER_CREDENTIALS}
    assert (env.keyring_names(), sorted(env.secret_keys())) == (keyring, sorted(keyring))


def test_config_env_lists_every_variable_that_sets_a_setting_or_a_credential() -> None:
    """The four task reasoning efforts and the three `ai.rag` variables had no spec (#2444)."""
    listed = {spec.env_var for spec in env.get_all_env_var_specs()}
    expected = set(env.setting_variables().values()) | {
        credential.env_vars[0] for credential in env.CREDENTIALS
    }
    assert (
        sorted(expected - listed),
        {
            "DEVOPS_CLI_AI_TASK_CHAT_REASONING_EFFORT",
            "DEVOPS_CLI_AI_RAG_TOP_K",
            "DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD",
        }
        <= listed,
    ) == ([], True)


def test_every_listed_variable_has_a_description() -> None:
    assert [spec.env_var for spec in env.get_all_env_var_specs() if not spec.description] == []


def test_a_credential_that_a_file_may_hold_is_a_field_and_no_credential_has_a_variable_marker() -> (
    None
):
    settings = Settings()
    in_file = [c.key for c in env.CREDENTIALS if c.in_file]
    assert (
        [key for key in in_file if not _is_field(settings, key)],
        sorted(env.secret_keys() & env.setting_variables().keys()),
    ) == ([], [])


def _is_field(settings: Settings, key: str) -> bool:
    try:
        dotted_get(settings, key)
    except AttributeError:
        return False
    return True


def test_every_setting_variable_names_a_field() -> None:
    settings = Settings()
    assert [key for key in env.setting_variables() if not _is_field(settings, key)] == []


def test_the_options_module_is_gone() -> None:
    assert importlib.util.find_spec("devops_cli.config.options") is None


def test_config_show_prints_every_setting_and_credential_once(cli: Callable[..., Any]) -> None:
    result = cli("config", "show", "--json")
    keys = [row["key"] for row in json.loads(result.stdout)]
    assert (result.exit_code, keys) == (
        0,
        sorted(set(env.setting_variables()) | env.secret_keys()),
    )


def test_config_show_masks_a_credential_and_prints_a_setting(cli: Callable[..., Any]) -> None:
    result = cli(
        "config",
        "show",
        "--json",
        env={"DEVOPS_CLI_GRAFANA_TOKEN": "t0k3n-value", "DEVOPS_CLI_AI_MODEL": "gpt-4o"},
    )
    rows = {row["key"]: row["value"] for row in json.loads(result.stdout)}
    assert (
        result.exit_code,
        rows["grafana.token"],
        rows["ai.model"],
        "t0k3n-value" in result.stdout,
    ) == (0, "****", "gpt-4o", False)


def test_a_variable_added_for_a_read_option_sets_it(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.config.settings import load_settings

    monkeypatch.setenv("DEVOPS_CLI_AI_REFERENCE_MODEL", "gpt-5")
    monkeypatch.setenv("DEVOPS_CLI_CLOUDFLARE_ACCESS_BYPASS_IPS", "192.0.2.1, 198.51.100.0/24")
    settings = load_settings()
    assert (settings.ai.reference_model, settings.cloudflare.access.bypass_ips) == (
        "gpt-5",
        ["192.0.2.1", "198.51.100.0/24"],
    )


def test_env_var_for_option_names_the_variable_of_a_setting_and_of_a_credential() -> None:
    assert (
        env.env_var_for_option("ai.tasks.chat.provider"),
        env.env_var_for_option("telemetry.logfire_token"),
        env.env_var_for_option("data.dir"),
        env.env_var_for_option("ai.temperature"),
    ) == (
        "DEVOPS_CLI_AI_TASK_CHAT_PROVIDER",
        "DEVOPS_CLI_TELEMETRY_LOGFIRE_TOKEN",
        "DEVOPS_CLI_DATA_DIR",
        None,
    )


def test_the_app_private_key_constant_is_the_variable_of_its_credential() -> None:
    """Modules below the settings read the App's private key by this constant (#2444)."""
    from devops_cli.config.constants import CONST_GITHUB_APP_PRIVATE_KEY_ENV

    assert (
        env.credential("service.github_app.private_key").env_vars[0]
        == CONST_GITHUB_APP_PRIVATE_KEY_ENV
    )
