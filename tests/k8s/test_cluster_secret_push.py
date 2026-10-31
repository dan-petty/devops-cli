"""The cluster Secret push: workstation keyring to cluster.

Offline: a stub keyring backend and a fake cluster standing in for process execution,
so every argv, stdin, and environment a child sees is recorded and verified.
"""

from __future__ import annotations

import base64
import json
import logging
import subprocess
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import pytest
import typer
from click.testing import CliRunner
from keyring.backends.fail import Keyring as FailKeyring

from devops_cli.commands.k8s.cluster_secret_push import push_secrets, run_push
from devops_cli.config.settings import reset_settings_cache
from devops_cli.k8s.cluster_secrets import (
    CLUSTER_SECRETS,
    DEVOPS_CACHE_VALKEY_AUTH_KEY,
    LLM_GATEWAY_MASTER_KEY,
    ClusterSecret,
    DerivedSource,
    KeyringSource,
    LiteralSource,
    SecretEntry,
    SecretGenerator,
)
from devops_cli.k8s.secret_push import (
    PushMode,
    PushOptions,
    PushResult,
    dry_run_push,
    execute_push,
    plan_push,
)
from tests.cluster_secret_fakes import (
    APP_KEY,
    APP_KEY_ENTRY,
    FakeCluster,
)
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_push_app = typer.Typer()
_push_app.command()(push_secrets)
PUSH_COMMAND = typer.main.get_command(_push_app)

GATEWAY_KEY = "sk-keyring-gateway-value-0001"
QDRANT_KEY = "qdrant-keyring-value-0001"
RUNS_PASSWORD = "runs-keyring-value-0001"
CACHE_PASSWORD = "cache-keyring-value-0001"
DEVOPS_CACHE_PASSWORD = "devops-cache-keyring-value-0001"
TUNNEL_TOKEN = "tunnel-keyring-value-0001"
FULL_KEYRING = {
    LLM_GATEWAY_MASTER_KEY: GATEWAY_KEY,
    "qdrant_api_key": QDRANT_KEY,
    "runs_index_password": RUNS_PASSWORD,
    "valkey_password": CACHE_PASSWORD,
    DEVOPS_CACHE_VALKEY_AUTH_KEY: DEVOPS_CACHE_PASSWORD,
    "cloudflare_tunnel_token": TUNNEL_TOKEN,
    "service_github_app_private_key": APP_KEY,
}
TABLE_REFS = {secret.ref for secret in CLUSTER_SECRETS}

NOTIFIER = "argocd/argocd-notifications-secret"
NOTIFIER_KEYRING = "argocd_github_app_private_key"
NOTIFIER_PEM = "-----BEGIN TEST KEY-----\nnotifier-key-body-0001\n-----END TEST KEY-----\n"
NOTIFIER_APP_ID = "123456"
NOTIFIER_INSTALLATION_ID = "7890123"

DB_KEY = "example_db_password"
DB_USER = "app/user"
DSN_TEMPLATE = "postgres://{user}:{password}@db.example.com:5432/app?sslmode=require"


@pytest.fixture
def cluster(process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch) -> FakeCluster:
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    monkeypatch.setenv("K8S_CONTEXT", "test-ctx")
    monkeypatch.setenv("K8S_NAMESPACE", "test")
    fake = FakeCluster()
    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=fake))
    return fake


def _install(
    monkeypatch: pytest.MonkeyPatch,
    cluster: FakeCluster,
    keyring_store: FakeKeyring,
    **values: Any,
) -> FakeKeyring:
    keyring_store.values.clear()
    keyring_store.values.update(values.get("values", FULL_KEYRING))
    keyring_store.locked = values.get("locked", False)
    keyring_store.events = cluster.events
    monkeypatch.delenv("DEVOPS_CLI_HEADLESS_AUTH", raising=False)
    return keyring_store


@pytest.fixture
def stub_keyring(
    monkeypatch: pytest.MonkeyPatch, cluster: FakeCluster, keyring_store: FakeKeyring
) -> FakeKeyring:
    return _install(monkeypatch, cluster, keyring_store)


def _push(*args: str) -> Any:
    runner = CliRunner()
    return runner.invoke(PUSH_COMMAND, ["--context", "test-ctx", *args])


def _notifier_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ARGOCD_GITHUB_APP_ID", NOTIFIER_APP_ID)
    monkeypatch.setenv("DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID", NOTIFIER_INSTALLATION_ID)
    reset_settings_cache()


def _set_raw(cluster: FakeCluster, namespace: str, name: str, key: str, raw: bytes) -> None:
    cluster.secrets[(namespace, name)]["data"][key] = base64.b64encode(raw).decode()


def _db_row(*, dsn_first: bool = False) -> Any:
    password_source = KeyringSource(DB_KEY)
    dsn = SecretEntry(
        "DSN",
        DerivedSource(DSN_TEMPLATE, {"user": LiteralSource(DB_USER), "password": password_source}),
    )
    username = SecretEntry("username", LiteralSource(DB_USER))
    password = SecretEntry("password", password_source, generator=SecretGenerator("urlsafe", 32))
    entries = (dsn, username, password) if dsn_first else (username, password, dsn)
    return ClusterSecret(
        "devops", "example-db", "devops", entries, secret_type="kubernetes.io/basic-auth"
    )


def _hook_row(hook: KeyringSource, *, required: bool = True) -> Any:
    from devops_cli.config.constants import CONST_K8S_MATTERMOST_URL

    url = DerivedSource(f"{CONST_K8S_MATTERMOST_URL}/hooks/{{hook}}", {"hook": hook})
    return ClusterSecret(
        "devops", "example-hook", "devops", (SecretEntry("url", url, required=required),)
    )


def _token_row() -> Any:
    return ClusterSecret(
        "devops", "example-token", "devops", (SecretEntry("token", KeyringSource("example_token")),)
    )


def _entry_states(plan: Any) -> list[tuple[str, str]]:
    return [(entry.entry.key, entry.state.value) for entry in plan.secrets[0].entries]


def test_the_notifier_secret_gets_the_ids_and_the_pem_key_byte_for_byte(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    cluster.namespaces.add("argocd")
    _install(
        monkeypatch,
        cluster,
        keyring_store,
        values={**FULL_KEYRING, NOTIFIER_KEYRING: NOTIFIER_PEM},
    )
    _notifier_settings(monkeypatch)
    result = _push("--only", NOTIFIER)
    assert (
        result.exit_code,
        cluster.live_data("argocd", "argocd-notifications-secret"),
        cluster.commands("kubectl", "rollout"),
        [v for v in (NOTIFIER_PEM.splitlines()[1], NOTIFIER_APP_ID) if v in result.output],
    ) == (
        0,
        {
            "github-appID": NOTIFIER_APP_ID,
            "github-installationID": NOTIFIER_INSTALLATION_ID,
            "github-privateKey": NOTIFIER_PEM,
        },
        [],
        [],
    ), result.output


def test_with_no_notifier_value_the_push_writes_nothing_and_names_the_commands(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    cluster.namespaces.add("argocd")
    _install(monkeypatch, cluster, keyring_store)
    reset_settings_cache()
    result = _push("--only", NOTIFIER)
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "devops config set argocd.github_app_id" in output,
        "devops config set argocd.github_app_installation_id" in output,
        "devops config set argocd.github_app_private_key" in output,
        cluster.applies(),
    ) == (0, True, True, True, []), result.output


def test_apply_is_one_server_side_apply_of_a_list_on_stdin(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    result = _push()
    applies = cluster.applies()
    items = cluster.applied_items()
    assert result.exit_code == 0, result.output
    assert (
        len(applies),
        applies[0].argv[:7],
        json.loads(applies[0].stdin or "{}")["kind"],
        {f"{i['metadata']['namespace']}/{i['metadata']['name']}": sorted(i["data"]) for i in items},
        [i for i in items if "stringData" in i or "annotations" in i["metadata"]],
        {i["metadata"]["labels"]["app.kubernetes.io/managed-by"] for i in items},
    ) == (
        1,
        [
            "kubectl",
            "apply",
            "--server-side",
            "--field-manager=devops-cli",
            "--force-conflicts",
            "-f",
            "-",
        ],
        "List",
        {
            "llm/llm-gateway-secrets": ["master-key"],
            "llm/qdrant-api-key": ["api-key"],
            "llm/valkey-runs-auth": ["password"],
            "llm/valkey-auth": ["VALKEY_PASSWORD"],
            "llm/valkey-devops-auth": ["password"],
            "cloudflared/cloudflared-token": ["token"],
            "devops/devops-cli": [
                "DEVOPS_CLI_AI_API_KEY",
                APP_KEY_ENTRY,
                "DEVOPS_CLI_VALKEY_PASSWORD",
            ],
        },
        [],
        {"devops-cli"},
    )


def test_keyring_values_without_live_secrets_are_created_and_restart_nothing(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.workloads = {("llm", "deployment/llm-gateway"), ("llm", "statefulset/qdrant")}
    result = _push()
    assert (
        result.exit_code,
        "llm/qdrant-api-key: api-key (keyring qdrant_api_key) created" in result.output,
        cluster.live_data("devops", "devops-cli"),
        cluster.commands("kubectl", "rollout"),
    ) == (
        0,
        True,
        {
            APP_KEY_ENTRY: APP_KEY,
            "DEVOPS_CLI_AI_API_KEY": GATEWAY_KEY,
            "DEVOPS_CLI_VALKEY_PASSWORD": DEVOPS_CACHE_PASSWORD,
        },
        [],
    )


def test_an_equal_live_value_is_unchanged_and_restarts_nothing(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.add_secret("llm", "qdrant-api-key", {"api-key": QDRANT_KEY})
    cluster.workloads = {("llm", "statefulset/qdrant")}
    result = _push("--only", "llm/qdrant-api-key")
    assert (result.exit_code, "api-key (keyring qdrant_api_key) unchanged" in result.output) == (
        0,
        True,
    )
    assert cluster.commands("kubectl", "rollout") == []


def test_a_key_added_to_an_existing_secret_restarts_its_workloads_once(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.add_secret("llm", "qdrant-api-key", {"legacy": "kept-by-another-manager"})
    cluster.workloads = {("llm", "statefulset/qdrant"), ("llm", "statefulset/open-webui")}
    result = _push("--only", "llm/qdrant-api-key")
    assert (result.exit_code, cluster.commands("kubectl", "rollout")) == (
        0,
        [
            ["kubectl", "rollout", "restart", "statefulset/qdrant", "-n", "llm"],
            ["kubectl", "rollout", "restart", "statefulset/open-webui", "-n", "llm"],
        ],
    )


def test_a_missing_keyring_value_is_adopted_from_the_live_secret(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    backend = _install(monkeypatch, cluster, keyring_store, values={})
    cluster.add_secret("llm", "qdrant-api-key", {"api-key": "live-qdrant-value-0001"})
    result = _push("--only", "llm/qdrant-api-key")
    assert (
        result.exit_code,
        backend.writes,
        cluster.live_data("llm", "qdrant-api-key"),
        "api-key (keyring qdrant_api_key) adopted" in result.output,
        cluster.commands("kubectl", "rollout"),
    ) == (
        0,
        {"qdrant_api_key": "live-qdrant-value-0001"},
        {"api-key": "live-qdrant-value-0001"},
        True,
        [],
    )


def test_a_generated_value_is_stored_in_the_keyring_before_the_apply(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    backend = _install(monkeypatch, cluster, keyring_store, values={})
    cluster.namespaces = {"llm", "cloudflared"}
    result = _push("--stack", "llm")
    write_at = cluster.events.index(f"keyring-write {LLM_GATEWAY_MASTER_KEY}")
    apply_at = cluster.events.index("kubectl apply --server-side")
    assert (
        result.exit_code,
        write_at < apply_at,
        backend.writes[LLM_GATEWAY_MASTER_KEY].startswith("sk-"),
        cluster.live_data("llm", "llm-gateway-secrets")["master-key"],
        sorted(backend.writes),
    ) == (
        0,
        True,
        True,
        backend.writes[LLM_GATEWAY_MASTER_KEY],
        [
            LLM_GATEWAY_MASTER_KEY,
            "qdrant_api_key",
            "runs_index_password",
            DEVOPS_CACHE_VALKEY_AUTH_KEY,
            "valkey_password",
        ],
    )


def test_the_devops_api_key_is_adopted_from_the_gateway_secret_never_generated(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    backend = _install(
        monkeypatch, cluster, keyring_store, values={"service_github_app_private_key": APP_KEY}
    )
    cluster.add_secret("llm", "llm-gateway-secrets", {"master-key": "sk-live-gateway-0001"})
    cluster.add_secret("llm", "valkey-devops-auth", {"password": "live-devops-cache-0001"})
    result = _push("--stack", "devops")
    assert (result.exit_code, backend.writes, cluster.live_data("devops", "devops-cli")) == (
        0,
        {
            LLM_GATEWAY_MASTER_KEY: "sk-live-gateway-0001",
            DEVOPS_CACHE_VALKEY_AUTH_KEY: "live-devops-cache-0001",
        },
        {
            APP_KEY_ENTRY: APP_KEY,
            "DEVOPS_CLI_AI_API_KEY": "sk-live-gateway-0001",
            "DEVOPS_CLI_VALKEY_PASSWORD": "live-devops-cache-0001",
        },
    )


def test_a_gateway_key_without_the_litellm_prefix_fails(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    _install(
        monkeypatch,
        cluster,
        keyring_store,
        values={LLM_GATEWAY_MASTER_KEY: "no-prefix-value-0001"},
    )
    result = _push("--only", "llm/llm-gateway-secrets")
    assert (
        result.exit_code,
        "llm_gateway_master_key does not start with `sk-`" in result.output,
    ) == (
        1,
        True,
    )
    assert cluster.applies() == []


def test_a_differing_live_value_stops_the_push_without_rotate(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.add_secret("llm", "qdrant-api-key", {"api-key": "live-other-value-0001"})
    result = _push("--only", "llm/qdrant-api-key")
    assert (
        result.exit_code,
        "llm/qdrant-api-key api-key" in result.output,
        "--rotate" in result.output,
        stub_keyring.writes,
        cluster.applies(),
    ) == (1, True, True, {}, [])


def test_rotate_applies_the_keyring_value_and_restarts_each_workload_once(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.add_secret("llm", "llm-gateway-secrets", {"master-key": "sk-live-other-0001"})
    cluster.workloads = {("llm", "deployment/llm-gateway")}
    result = _push("--only", "llm/llm-gateway-secrets", "--rotate")
    assert (
        result.exit_code,
        cluster.live_data("llm", "llm-gateway-secrets"),
        cluster.commands("kubectl", "rollout"),
        "Open WebUI keeps the gateway connection" in result.output,
    ) == (
        0,
        {"master-key": GATEWAY_KEY},
        [["kubectl", "rollout", "restart", "deployment/llm-gateway", "-n", "llm"]],
        True,
    )


def test_no_restart_prints_the_commands_and_runs_none(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.add_secret("llm", "llm-gateway-secrets", {"master-key": "sk-live-other-0001"})
    cluster.workloads = {("llm", "deployment/llm-gateway")}
    result = _push("--only", "llm/llm-gateway-secrets", "--rotate", "--no-restart")
    assert (
        result.exit_code,
        cluster.commands("kubectl", "rollout"),
        "kubectl rollout restart deployment/llm-gateway -n llm --context test-ctx" in result.output,
    ) == (0, [], True)


def test_missing_required_sources_are_named_together_and_nothing_is_written(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    backend = _install(monkeypatch, cluster, keyring_store, values={})
    result = _push("--stack", "devops")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "keyring service_github_app_private_key is empty" in output,
        "keyring llm_gateway_master_key is empty" in output,
        "devops config set service.github_app.private_key" in output,
        backend.writes,
        cluster.applies(),
    ) == (1, True, True, True, {}, [])


def test_a_missing_optional_source_is_skipped_with_a_warning_and_left_out(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    values = {k: v for k, v in FULL_KEYRING.items() if k != "cloudflare_tunnel_token"}
    _install(monkeypatch, cluster, keyring_store, values=values)
    result = _push("--stack", "base")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "devops config set cloudflare.tunnel_token" in output,
        cluster.applies(),
    ) == (0, True, [])


def test_a_locked_keyring_stops_before_any_kubectl(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    backend = _install(monkeypatch, cluster, keyring_store, locked=True)
    result = _push()
    assert (result.exit_code, "devops devcontainer unlock-keyring" in result.output) == (1, True)
    assert (cluster.calls, backend.writes) == ([], {})


def test_no_keyring_backend_stops_before_any_kubectl(
    cluster: FakeCluster, keyring_store: FakeKeyring
) -> None:
    keyring_store.selected = FailKeyring()
    result = _push()
    assert (
        result.exit_code,
        "no encrypted OS keyring backend" in result.output,
        "keyring.backends.fail.Keyring" in " ".join(result.output.split()),
        cluster.calls,
    ) == (1, True, True, [])


def test_headless_auth_stops_before_any_kubectl(
    cluster: FakeCluster, stub_keyring: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_HEADLESS_AUTH", "true")
    result = _push()
    assert (result.exit_code, "DEVOPS_CLI_HEADLESS_AUTH" in result.output, cluster.calls) == (
        1,
        True,
        [],
    )
    assert (stub_keyring.reads, stub_keyring.writes) == ([], {})


def test_only_applies_one_secret_and_reads_only_its_source(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    result = _push("--only", "llm/qdrant-api-key")
    assert (
        result.exit_code,
        [f"{i['metadata']['namespace']}/{i['metadata']['name']}" for i in cluster.applied_items()],
        stub_keyring.secret_reads(),
    ) == (0, ["llm/qdrant-api-key"], {"qdrant_api_key"})


def test_an_unknown_only_name_exits_2_listing_the_table(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    result = _push("--only", "llm/nope")
    assert (result.exit_code, "llm/qdrant-api-key" in result.output, cluster.calls) == (2, True, [])


def test_an_unknown_stack_exits_2(cluster: FakeCluster, stub_keyring: FakeKeyring) -> None:
    assert _push("--stack", "nope").exit_code == 2


def test_stack_devops_reads_the_app_key_gateway_key_and_webhook_secrets_and_runs_no_gh(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    result = _push("--stack", "devops")
    assert (
        result.exit_code,
        stub_keyring.secret_reads(),
        cluster.commands("gh"),
        cluster.live_data("devops", "devops-cli")[APP_KEY_ENTRY],
    ) == (
        0,
        {
            "service_github_app_private_key",
            LLM_GATEWAY_MASTER_KEY,
            "service_webhook_secrets",
            "firecrawl_api_key",
            DEVOPS_CACHE_VALKEY_AUTH_KEY,
        },
        [],
        APP_KEY,
    )


def test_a_missing_namespace_skips_under_stack_and_fails_under_only(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.namespaces = {"llm", "devops"}
    skipped = _push("--stack", "base")
    failed = _push("--only", "cloudflared/cloudflared-token")
    assert (
        skipped.exit_code,
        "Namespace cloudflared not found" in skipped.output,
        failed.exit_code,
        cluster.applies(),
    ) == (0, True, 1, [])


def test_the_leaked_last_applied_annotation_is_removed_once(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    leaked = {"kubectl.kubernetes.io/last-applied-configuration": "{}"}
    cluster.add_secret("llm", "qdrant-api-key", {"api-key": QDRANT_KEY}, annotations=leaked)
    cluster.add_secret("llm", "valkey-runs-auth", {"password": RUNS_PASSWORD})
    result = _push("--only", "llm/qdrant-api-key", "--only", "llm/valkey-runs-auth")
    assert (result.exit_code, cluster.commands("kubectl", "annotate")) == (
        0,
        [
            [
                "kubectl",
                "annotate",
                "secret/qdrant-api-key",
                "-n",
                "llm",
                "kubectl.kubernetes.io/last-applied-configuration-",
            ]
        ],
    )


def test_no_value_reaches_argv_logs_or_output(
    cluster: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    keyring_store: FakeKeyring,
) -> None:
    caplog.set_level(logging.DEBUG)
    backend = _install(
        monkeypatch,
        cluster,
        keyring_store,
        values={"cloudflare_tunnel_token": TUNNEL_TOKEN, "service_github_app_private_key": APP_KEY},
    )
    cluster.add_secret("llm", "qdrant-api-key", {"api-key": "live-qdrant-value-0002"})
    result = _push()
    values = [TUNNEL_TOKEN, "live-qdrant-value-0002", *backend.writes.values()]
    encoded = [base64.b64encode(v.encode()).decode() for v in values]
    argv = " ".join(" ".join(call.argv) for call in cluster.calls)
    texts = [argv, caplog.text, result.output, result.stderr if result.stderr_bytes else ""]
    assert (result.exit_code, [v for v in values + encoded if any(v in t for t in texts)]) == (
        0,
        [],
    )


def test_a_real_push_returns_the_same_type_with_its_plan(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    result = run_push(CLUSTER_SECRETS[1:2], PushOptions(context="test-ctx"), mode=PushMode.PUSH)
    assert (type(result), result.dry_run, result.plan is not None) == (PushResult, False, True)


def test_under_only_every_request_after_the_namespace_reads_needs_them_all() -> None:
    from devops_cli.k8s.cluster_secrets import secrets_by_ref

    selected, _ = secrets_by_ref(["llm/qdrant-api-key", "devops/devops-cli"])
    requests = dry_run_push(selected, PushOptions(strict_namespaces=True)).requests
    assert [r.method for r in requests if not r.condition] == [
        "keyring read",
        "kubectl get",
        "kubectl get",
    ]


def test_a_failed_apply_echoes_no_kubectl_output_and_names_what_was_written(
    cluster: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
    keyring_store: FakeKeyring,
) -> None:
    backend = _install(monkeypatch, cluster, keyring_store, values={})
    cluster.namespaces = {"llm"}
    quoted: list[str] = []

    def failing_apply(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        if call.argv[:3] == ("kubectl", "apply", "--server-side"):
            encoded = json.loads(call.stdin or "{}")["items"][0]["data"]["api-key"]
            quoted.append(encoded[3:38])
            return subprocess.CompletedProcess(
                list(call.argv), 1, "", f"error: invalid {quoted[0]}"
            )
        return cluster(call)

    process_fake.answer(lambda _call: True, ProcessAnswer(side_effect=failing_apply))
    result = _push("--only", "llm/qdrant-api-key")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        quoted[0] in result.output,
        "nothing was written" in output,
        "keyring entries stored: qdrant_api_key" in output,
        "llm/qdrant-api-key" in output,
        sorted(backend.writes),
    ) == (1, False, False, True, True, ["qdrant_api_key"])


def test_a_live_value_that_is_not_utf8_is_never_adopted(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    backend = _install(monkeypatch, cluster, keyring_store, values={})
    cluster.add_secret("llm", "qdrant-api-key", {"api-key": "placeholder"})
    _set_raw(cluster, "llm", "qdrant-api-key", "api-key", b"\xffqdrant\xfe")
    result = _push("--only", "llm/qdrant-api-key")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "live llm/qdrant-api-key api-key is not UTF-8" in output,
        backend.writes,
        cluster.applies(),
    ) == (1, True, {}, [])


def test_a_keyring_value_against_a_non_utf8_live_value_differs(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.add_secret("llm", "qdrant-api-key", {"api-key": "placeholder"})
    _set_raw(cluster, "llm", "qdrant-api-key", "api-key", QDRANT_KEY.encode() + b"\xff")
    held = _push("--only", "llm/qdrant-api-key")
    rotated = _push("--only", "llm/qdrant-api-key", "--rotate")
    assert (held.exit_code, "--rotate" in held.output, rotated.exit_code) == (1, True, 0)
    assert cluster.live_data("llm", "qdrant-api-key") == {"api-key": QDRANT_KEY}


def test_an_adopted_value_without_the_prefix_names_the_live_secret(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    _install(monkeypatch, cluster, keyring_store, values={})
    cluster.add_secret("llm", "llm-gateway-secrets", {"master-key": "no-prefix-live-0001"})
    result = _push("--only", "llm/llm-gateway-secrets")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "live llm/llm-gateway-secrets master-key does not start with `sk-`" in output,
        "keyring llm_gateway_master_key does not start" in output,
    ) == (1, True, False)


def test_a_derived_connection_string_quotes_a_literal_user_and_a_generated_password(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    backend = _install(monkeypatch, cluster, keyring_store, values={})
    options = PushOptions(context="test-ctx")
    plan = plan_push([_db_row()], options)
    execute_push(plan, options)
    live = cluster.live_data("devops", "example-db")
    dsn = urlsplit(live["DSN"])
    assert (
        [(e.entry.key, e.state.value, e.store_key) for e in plan.secrets[0].entries],
        (unquote(dsn.username or ""), unquote(dsn.password or ""), dsn.hostname, dsn.port),
        (dsn.path, dsn.query),
        backend.writes,
    ) == (
        [
            ("username", "created", None),
            ("password", "generated", DB_KEY),
            ("DSN", "created", None),
        ],
        (DB_USER, live["password"], "db.example.com", 5432),
        ("/app", "sslmode=require"),
        {DB_KEY: live["password"]},
    )


def test_a_derived_entry_before_its_input_is_built_from_the_adopted_value(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    password = "p@ss:w/rd?#%"
    live_dsn = DSN_TEMPLATE.format(user=quote(DB_USER, safe=""), password=quote(password, safe=""))
    _install(monkeypatch, cluster, keyring_store, values={})
    cluster.add_secret(
        "devops",
        "example-db",
        {"username": DB_USER, "password": password, "DSN": live_dsn},
        manager="devops-cli",
    )
    plan = plan_push([_db_row(dsn_first=True)], PushOptions(context="test-ctx"))
    assert _entry_states(plan) == [
        ("DSN", "unchanged"),
        ("username", "unchanged"),
        ("password", "adopted"),
    ]


def test_a_derived_hook_url_is_skipped_until_its_managed_input_has_a_value(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    hook = KeyringSource.for_credential("firecrawl.api_key")
    row = _hook_row(hook, required=False)
    backend = _install(monkeypatch, cluster, keyring_store, values={})
    options = PushOptions(context="test-ctx")
    before = plan_push([row], options).secrets[0].entries[0]
    backend.values[hook.key] = "hook id 0001"
    after = plan_push([row], options).secrets[0].entries[0]
    assert ((before.state.value, before.problem), (after.state.value, after.value)) == (
        (
            "skipped",
            "devops/example-hook url: derived from keyring firecrawl_api_key, which has no "
            "value; store it with `devops config set firecrawl.api_key`",
        ),
        ("created", "http://mattermost.mattermost.svc.cluster.local:8065/hooks/hook%20id%200001"),
    )


def test_a_differing_derived_value_needs_rotate(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    _install(monkeypatch, cluster, keyring_store, values={DB_KEY: "db-value-0001"})
    cluster.add_secret(
        "devops",
        "example-db",
        {"username": DB_USER, "password": "db-value-0001", "DSN": "postgres://old.example.com"},
        manager="devops-cli",
    )
    states = [
        _entry_states(plan_push([_db_row()], PushOptions(context="test-ctx", rotate=rotate)))
        for rotate in (False, True)
    ]
    assert states == [
        [("username", "unchanged"), ("password", "unchanged"), ("DSN", "differs")],
        [("username", "unchanged"), ("password", "unchanged"), ("DSN", "rotated")],
    ]


def test_a_pushed_manifest_carries_the_secret_type_of_its_row(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    _install(
        monkeypatch,
        cluster,
        keyring_store,
        values={DB_KEY: "db-value-0001", "example_token": "t-0001"},
    )
    rows = [_db_row(), _token_row()]
    options = PushOptions(context="test-ctx")
    dry_run = dry_run_push(rows, options).requests
    shown = json.loads(next(r.stdin for r in dry_run if r.stdin) or "{}")["items"]
    execute_push(plan_push(rows, options), options)
    assert (
        {item["metadata"]["name"]: item["type"] for item in cluster.applied_items()},
        {item["metadata"]["name"]: item["type"] for item in shown},
    ) == (
        {"example-db": "kubernetes.io/basic-auth", "example-token": "Opaque"},
        {"example-db": "kubernetes.io/basic-auth", "example-token": "Opaque"},
    )
