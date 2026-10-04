"""Unit and integration tests for Qdrant API key secret protection and ClusterIP defaults.

Validates:
1. k8s/llm/values-qdrant.yaml manifests (ClusterIP service, apiKey disabled auto-generation,
   extraEnv secretKeyRef injection).
2. Configuration & OS Keyring secret mappings for Qdrant API key.
3. deploy-stack pushing the cluster Secrets from the keyring before anything reads them, in
   place of the client-side Qdrant Secret apply that leaked the key into an annotation.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import keyring
import pytest
import typer
import yaml
from click.testing import CliRunner

from devops_cli.commands.k8s.stack_lifecycle import deploy_stack
from devops_cli.config import env as env_mod
from devops_cli.config import options as opt
from devops_cli.config.settings import (
    QdrantConfig,
    Settings,
    dotted_set,
    get_qdrant_api_key,
)
from devops_cli.telemetry import tracer
from tests.cluster_secret_fakes import MACHINE_LOGIN, MACHINE_TOKEN, FakeCluster, FakeKeyring

REPO_ROOT = Path(__file__).resolve().parent.parent
_deploy_app = typer.Typer()
_deploy_app.command()(deploy_stack)
DEPLOY_COMMAND = typer.main.get_command(_deploy_app)


def test_qdrant_helm_values_security() -> None:
    """Validate k8s/llm/values-qdrant.yaml zero-trust perimeter and secret protection."""
    values_path = REPO_ROOT / "k8s" / "llm" / "values-qdrant.yaml"
    assert values_path.is_file(), f"Missing {values_path}"

    content = values_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert isinstance(data, dict), "values-qdrant.yaml must parse as dictionary"

    # 1. Zero-trust internal perimeter: service.type must be ClusterIP
    service = data.get("service", {})
    assert service.get("type") == "ClusterIP", (
        f"Expected service.type 'ClusterIP', got {service.get('type')}"
    )

    # 2. Disabled auto-generated secret to prevent unmanaged secret sprawl
    assert data.get("apiKey") is False, "apiKey must be false to disable chart auto-generation"

    # 3. Secret reference injection via extraEnv
    extra_env = data.get("extraEnv", [])
    assert isinstance(extra_env, list), "extraEnv must be a list"
    api_key_env = next(
        (
            e
            for e in extra_env
            if isinstance(e, dict) and e.get("name") == "QDRANT__SERVICE__API_KEY"
        ),
        None,
    )
    assert api_key_env is not None, "Missing QDRANT__SERVICE__API_KEY in extraEnv"

    value_from = api_key_env.get("valueFrom", {})
    secret_ref = value_from.get("secretKeyRef", {})
    assert secret_ref.get("name") == "qdrant-api-key", "Expected secretKeyRef.name 'qdrant-api-key'"
    assert secret_ref.get("key") == "api-key", "Expected secretKeyRef.key 'api-key'"

    # 4. Pod and container security contexts. The qdrant chart renders the container's from
    # `containerSecurityContext` and never reads `securityContext`, so a hardening block there
    # never reached the pod (#953).
    container_sec_ctx = data["containerSecurityContext"]
    pod_sec_ctx = data["podSecurityContext"]
    assert (
        "securityContext" in data,
        container_sec_ctx.get("runAsNonRoot"),
        container_sec_ctx.get("runAsUser"),
        container_sec_ctx.get("privileged"),
        container_sec_ctx.get("readOnlyRootFilesystem"),
        container_sec_ctx.get("allowPrivilegeEscalation"),
        container_sec_ctx.get("capabilities", {}).get("drop"),
        container_sec_ctx.get("seccompProfile", {}).get("type"),
        container_sec_ctx.get("runAsGroup"),
        pod_sec_ctx.get("runAsNonRoot"),
    ) == (
        False,
        True,
        pod_sec_ctx["runAsUser"],
        False,
        True,
        False,
        ["ALL"],
        "RuntimeDefault",
        pod_sec_ctx["runAsGroup"],
        True,
    )


def test_qdrant_config_options_and_secret_registry() -> None:
    """Verify Qdrant config options and secret registry mappings."""
    assert opt.QDRANT_API_KEY in opt.CONFIG_OPTIONS
    assert opt.QDRANT_URL in opt.CONFIG_OPTIONS
    assert opt.QDRANT_COLLECTION_PREFIX in opt.CONFIG_OPTIONS

    assert opt.QDRANT_API_KEY in opt.SECRET_CONFIG_OPTIONS
    assert opt.KEYRING_KEYS[opt.QDRANT_API_KEY] == "qdrant_api_key"


def test_qdrant_env_variable_mappings() -> None:
    """Verify Qdrant environment variable mappings and secret specs."""
    assert env_mod.ENV_QDRANT_API_KEY == "DEVOPS_CLI_QDRANT_API_KEY"
    assert env_mod.OPTION_TO_ENV_VAR[opt.QDRANT_API_KEY] == env_mod.ENV_QDRANT_API_KEY
    assert env_mod.ENV_VAR_TO_OPTION[env_mod.ENV_QDRANT_API_KEY] == opt.QDRANT_API_KEY

    specs = {s.env_var: s for s in env_mod.get_all_env_var_specs()}
    spec = specs.get(env_mod.ENV_QDRANT_API_KEY)
    assert spec is not None
    assert spec.is_secret is True
    assert spec.option_key == opt.QDRANT_API_KEY


def test_get_qdrant_api_key_precedence() -> None:
    """Verify get_qdrant_api_key prioritizes OS Keyring over settings fallback."""
    settings = Settings(qdrant=QdrantConfig(api_key="fallback-key"))

    with patch("devops_cli.config.settings._keyring_get", return_value="keyring-vault-key"):
        assert get_qdrant_api_key(settings) == "keyring-vault-key"

    with patch("devops_cli.config.settings._keyring_get", return_value=None):
        assert get_qdrant_api_key(settings) == "fallback-key"


def test_dotted_set_routes_qdrant_api_key_to_keyring() -> None:
    """Verify dotted_set routes qdrant.api_key exclusively to the OS Keyring."""
    settings = Settings()
    with patch("devops_cli.config.settings._keyring_set") as mock_set:
        dotted_set(settings, "qdrant.api_key", "super-secret-vector-token")
        mock_set.assert_called_once_with("qdrant_api_key", "super-secret-vector-token")


@pytest.fixture
def cluster(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeCluster]:
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    # Each child's span would otherwise load the settings twice per test to learn the above.
    monkeypatch.setattr(tracer, "_resolve_telemetry_settings", lambda: (None, False))
    monkeypatch.setenv("K8S_CONTEXT", "test-ctx")
    monkeypatch.setenv("K8S_NAMESPACE", "test")
    fake = FakeCluster(namespaces={"llm", "cloudflared"})
    with (
        patch("devops_cli.core.process.subprocess.run", side_effect=fake),
        patch("devops_cli.commands.k8s.cluster_runtime._cluster_reachable", return_value=True),
        patch("devops_cli.k8s.credentials.sync_k8s_credentials", return_value={}),
    ):
        yield fake


@pytest.fixture
def stub_keyring(monkeypatch: pytest.MonkeyPatch, cluster: FakeCluster) -> FakeKeyring:
    backend = FakeKeyring(
        {
            "llm_gateway_master_key": "sk-deploy-gateway-0001",
            "qdrant_api_key": "deploy-qdrant-0001",
            "runs_index_password": "deploy-runs-0001",
            "cloudflare_tunnel_token": "deploy-tunnel-0001",
        }
    )
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    monkeypatch.delenv("DEVOPS_CLI_HEADLESS_AUTH", raising=False)
    return backend


def _deploy(*args: str) -> Any:
    return CliRunner().invoke(DEPLOY_COMMAND, ["--context", "test-ctx", "--no-wait", *args])


def _pushed(cluster: FakeCluster) -> list[str]:
    return [
        f"{i['metadata']['namespace']}/{i['metadata']['name']}" for i in cluster.applied_items()
    ]


def _step(argv: list[str]) -> str:
    if argv[:3] == ["kubectl", "apply", "-k"]:
        return "namespaces"
    if argv[:3] == ["kubectl", "apply", "--server-side"]:
        return "secrets"
    if argv[:3] == ["kubectl", "apply", "-f"]:
        return "manifests"
    return "helm" if argv[:3] == ["helm", "upgrade", "--install"] else ""


def test_deploy_stack_pushes_secrets_after_namespaces_and_before_manifests_and_helm(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    result = _deploy("--stack", "llm")
    steps = [step for step in (_step(call.argv) for call in cluster.calls) if step]
    assert (
        result.exit_code,
        list(dict.fromkeys(steps)),
        steps.count("secrets"),
        _pushed(cluster),
    ) == (
        0,
        ["namespaces", "secrets", "manifests", "helm"],
        1,
        [
            "llm/llm-gateway-secrets",
            "llm/qdrant-api-key",
            "llm/valkey-runs-auth",
            "cloudflared/cloudflared-token",
        ],
    )


def test_deploy_stack_pushes_devops_only_where_its_namespace_exists(
    cluster: FakeCluster, stub_keyring: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_K8S_GITHUB_ACCOUNT", MACHINE_LOGIN)
    without = (_deploy("--stack", "infra").exit_code, _pushed(cluster), cluster.commands("gh"))
    cluster.calls.clear()
    cluster.namespaces.add("devops")
    with_devops = (_deploy("--stack", "infra").exit_code, _pushed(cluster))
    assert (without, with_devops, cluster.live_data("devops", "devops-cli")["GH_TOKEN"]) == (
        (0, ["cloudflared/cloudflared-token"], []),
        (0, ["cloudflared/cloudflared-token", "devops/devops-cli"]),
        MACHINE_TOKEN,
    )


def test_a_locked_keyring_stops_deploy_stack_before_it_touches_the_cluster(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    """Not even the root kustomization is applied while the keyring is locked."""
    stub_keyring.locked = True
    result = _deploy("--stack", "llm")
    assert (
        result.exit_code,
        [call.argv for call in cluster.calls],
        "devops devcontainer unlock-keyring" in result.output,
    ) == (1, [], True)


def test_a_failed_push_exits_1_before_any_manifest_or_helm_release(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.add_secret("llm", "qdrant-api-key", {"api-key": "live-differs-0001"})
    stub_keyring.values["qdrant_api_key"] = "keyring-differs-0001"
    result = _deploy("--stack", "llm")
    steps = {_step(call.argv) for call in cluster.calls} - {""}
    assert (result.exit_code, steps, "--rotate" in result.output) == (1, {"namespaces"}, True)


def test_no_push_secrets_pushes_nothing(cluster: FakeCluster, stub_keyring: FakeKeyring) -> None:
    result = _deploy("--stack", "llm", "--no-push-secrets")
    assert (result.exit_code, cluster.applies(), stub_keyring.reads) == (0, [], [])


def test_the_qdrant_secret_helpers_are_gone() -> None:
    import devops_cli.commands.k8s as k8s_commands
    import devops_cli.commands.k8s.stack_lifecycle as stack_lifecycle
    import devops_cli.k8s.credentials as credentials

    assert (
        hasattr(stack_lifecycle, "_ensure_qdrant_api_key_secret"),
        hasattr(k8s_commands, "_ensure_qdrant_api_key_secret"),
        hasattr(credentials, "fetch_qdrant_api_key"),
    ) == (False, False, False)


def test_sync_k8s_credentials_reads_no_llm_secret() -> None:
    from devops_cli.k8s.credentials import sync_k8s_credentials

    with patch("devops_cli.k8s.credentials.fetch_secret_data") as fetch:
        results = sync_k8s_credentials(stack="llm", save_to_keyring=False)
    assert (results, fetch.call_count) == ({}, 0)
