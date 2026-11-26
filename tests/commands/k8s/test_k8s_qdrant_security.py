"""Unit and integration tests for the Qdrant API key.

Validates:
1. Configuration & OS Keyring secret mappings for Qdrant API key.
2. deploy-stack pushing the cluster Secrets from the keyring before anything reads them, in
   place of the client-side Qdrant Secret apply that leaked the key into an annotation.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import typer
from click.testing import CliRunner

from devops_cli.commands.k8s.stack_lifecycle import deploy_stack
from devops_cli.config import env as env_mod
from devops_cli.config.os_keyring import set_keyring_edge
from devops_cli.config.settings import (
    QdrantConfig,
    Settings,
    dotted_set,
    get_qdrant_api_key,
)
from devops_cli.k8s.cluster_secrets import (
    CLUSTER_SECRETS,
    KeyringSource,
    SecretKeyRef,
    load_cluster_secrets_table,
)
from tests.support.cluster_secret_fakes import APP_KEY, APP_KEY_ENTRY, FakeCluster
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessFake

_deploy_app = typer.Typer()
_deploy_app.command()(deploy_stack)
DEPLOY_COMMAND = typer.main.get_command(_deploy_app)


def test_qdrant_settings_variables_and_its_api_key_credential() -> None:
    """The Qdrant URL and prefix are settings that a variable sets; its API key is a credential."""
    specs = {s.env_var: s for s in env_mod.get_all_env_var_specs()}
    key_spec = specs["DEVOPS_CLI_QDRANT_API_KEY"]
    assert (
        env_mod.env_var_for_option("qdrant.url"),
        env_mod.env_var_for_option("qdrant.collection_prefix"),
        env_mod.credential("qdrant.api_key").keyring_name,
        (key_spec.is_secret, key_spec.option_key),
    ) == (
        "DEVOPS_CLI_QDRANT_URL",
        "DEVOPS_CLI_QDRANT_COLLECTION_PREFIX",
        "qdrant_api_key",
        (True, "qdrant.api_key"),
    )


def test_get_qdrant_api_key_precedence(keyring_store: FakeKeyring) -> None:
    """Verify get_qdrant_api_key prioritizes OS Keyring over settings fallback."""
    settings = Settings(qdrant=QdrantConfig(api_key="fallback-key"))

    keyring_store.values["qdrant_api_key"] = "keyring-vault-key"
    from_keyring = get_qdrant_api_key(settings)
    del keyring_store.values["qdrant_api_key"]

    assert (from_keyring, get_qdrant_api_key(settings)) == ("keyring-vault-key", "fallback-key")


def test_dotted_set_routes_qdrant_api_key_to_keyring(keyring_store: FakeKeyring) -> None:
    """Verify dotted_set routes qdrant.api_key exclusively to the OS Keyring."""
    settings = Settings()

    dotted_set(settings, "qdrant.api_key", "super-secret-vector-token")

    assert (keyring_store.writes, settings.qdrant.api_key) == (
        {"qdrant_api_key": "super-secret-vector-token"},
        None,
    )


@pytest.fixture
def cluster(process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeCluster]:
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    monkeypatch.setenv("K8S_CONTEXT", "test-ctx")
    monkeypatch.setenv("K8S_NAMESPACE", "test")
    fake = FakeCluster(namespaces={"llm", "cloudflared"})
    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=fake))
    # A git read of the checkout, such as its `origin`, goes to no cluster.
    process_fake.answer(
        lambda call: call.local_read and call.argv[:1] == ("git",), ProcessAnswer(returncode=1)
    )
    yield fake


@pytest.fixture
def stub_keyring(monkeypatch: pytest.MonkeyPatch, cluster: FakeCluster) -> FakeKeyring:
    backend = FakeKeyring(
        {
            "llm_gateway_master_key": "sk-deploy-gateway-0001",
            "qdrant_api_key": "deploy-qdrant-0001",
            "runs_index_password": "deploy-runs-0001",
            "valkey_password": "deploy-cache-0001",
            "cloudflare_tunnel_token": "deploy-tunnel-0001",
            "searxng_metrics_password": "deploy-searxng-metrics-0001",
        }
    )
    set_keyring_edge(backend)
    monkeypatch.delenv("DEVOPS_CLI_HEADLESS_AUTH", raising=False)
    return backend


def _deploy(tree: Path, *args: str) -> Any:
    options = ["--context", "test-ctx", "--no-wait", "--k8s-dir", str(tree)]
    return CliRunner().invoke(DEPLOY_COMMAND, [*options, *args])


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
    cluster: FakeCluster, stub_keyring: FakeKeyring, env_tree: Path
) -> None:
    result = _deploy(env_tree, "--stack", "llm")
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
            "llm/valkey-auth",
            "cloudflared/cloudflared-token",
            "llm/valkey-runs-auth",
            "llm/valkey-devops-auth",
        ],
    )


def test_deploy_stack_pushes_devops_only_where_its_namespace_exists(
    cluster: FakeCluster, stub_keyring: FakeKeyring, env_tree: Path
) -> None:
    stub_keyring.values["service_github_app_private_key"] = APP_KEY
    first = _deploy(env_tree, "--stack", "infra")
    without = (first.exit_code, _pushed(cluster), cluster.commands("gh"))
    cluster.calls.clear()
    cluster.namespaces.add("devops")
    with_devops = (_deploy(env_tree, "--stack", "infra").exit_code, _pushed(cluster))
    assert (without, with_devops, cluster.live_data("devops", "devops-cli")[APP_KEY_ENTRY]) == (
        (0, ["cloudflared/cloudflared-token"], []),
        (
            0,
            [
                "cloudflared/cloudflared-token",
                "devops/valkey-roadmap-auth",
                "devops/crawl4ai",
                "devops/searxng",
                "devops/searxng-metrics-auth",
                "devops/mcp-server",
                "devops/devops-cli",
                "devops/qdrant-api-key",
            ],
        ),
        APP_KEY,
    )


def test_a_locked_keyring_stops_deploy_stack_before_it_touches_the_cluster(
    cluster: FakeCluster, stub_keyring: FakeKeyring, env_tree: Path
) -> None:
    """Not even the root kustomization is applied while the keyring is locked."""
    stub_keyring.locked = True
    result = _deploy(env_tree, "--stack", "llm")
    assert (
        result.exit_code,
        [call.argv for call in cluster.calls],
        "devops devcontainer unlock-keyring" in result.output,
    ) == (1, [], True)


def test_a_failed_push_exits_1_before_any_manifest_or_helm_release(
    cluster: FakeCluster, stub_keyring: FakeKeyring, env_tree: Path
) -> None:
    cluster.add_secret("llm", "qdrant-api-key", {"api-key": "live-differs-0001"})
    stub_keyring.values["qdrant_api_key"] = "keyring-differs-0001"
    result = _deploy(env_tree, "--stack", "llm")
    steps = {_step(call.argv) for call in cluster.calls} - {""}
    assert (result.exit_code, steps, "--rotate" in result.output) == (1, {"namespaces"}, True)


def test_no_push_secrets_pushes_nothing(
    cluster: FakeCluster, stub_keyring: FakeKeyring, env_tree: Path
) -> None:
    result = _deploy(env_tree, "--stack", "llm", "--no-push-secrets")
    assert (result.exit_code, cluster.applies(), stub_keyring.reads) == (0, [], [])


def test_the_qdrant_secret_helpers_are_gone() -> None:
    import devops_cli.commands.k8s as k8s_commands
    import devops_cli.commands.k8s.stack_lifecycle as stack_lifecycle
    import devops_cli.k8s.credentials as credentials

    assert "_ensure_qdrant_api_key_secret" not in dir(stack_lifecycle)
    assert "_ensure_qdrant_api_key_secret" not in dir(k8s_commands)
    assert "fetch_qdrant_api_key" not in dir(credentials)


def test_sync_k8s_credentials_reads_no_llm_secret(process_fake: ProcessFake) -> None:
    from devops_cli.k8s.credentials import sync_k8s_credentials

    results = sync_k8s_credentials(stack="llm", save_to_keyring=False)
    assert (results, process_fake.calls) == ({}, [])


def test_one_keyring_value_feeds_the_read_only_key_of_both_secrets(env_tree: Path) -> None:
    """Secret llm/qdrant-api-key holds the read-only key, and Secret devops/devops-cli takes the
    same keyring value for the pods that load that Secret with envFrom (#3823)."""
    rows = {
        (secret.ref, entry.key): entry
        for secret in load_cluster_secrets_table(k8s_dir=env_tree)
        for entry in secret.entries
    }
    read_only = rows[("llm/qdrant-api-key", "read-only-api-key")]
    runner = rows[("devops/devops-cli", "DEVOPS_CLI_QDRANT_API_KEY")]

    assert (
        read_only.source.key,
        runner.source.key,
        runner.adopt_from,
        runner.required,
    ) == (
        "qdrant_read_only_api_key",
        "qdrant_read_only_api_key",
        SecretKeyRef("llm", "qdrant-api-key", "read-only-api-key"),
        True,
    )


def test_no_devops_cli_row_holds_the_qdrant_admin_key() -> None:
    """The runner and the roadmap Service hold no write or delete path: no row of
    devops/devops-cli names keyring qdrant_api_key (#3823)."""
    devops_cli = next(secret for secret in CLUSTER_SECRETS if secret.ref == "devops/devops-cli")

    assert [
        entry.key
        for entry in devops_cli.entries
        if isinstance(entry.source, KeyringSource) and entry.source.key == "qdrant_api_key"
    ] == []
