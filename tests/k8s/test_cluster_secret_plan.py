"""The cluster Secret table, source resolution, and push planning.

Offline: a stub keyring backend and a fake cluster standing in for process execution,
so the tests verify planning, dry-run requests, derived entries, and table invariants
without touching a real cluster.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import typer
from click.testing import CliRunner

from devops_cli.commands.k8s.cluster_secret_push import push_secrets, run_push
from devops_cli.config.constants import CONST_K8S_MATTERMOST_URL
from devops_cli.config.env import (
    keyring_names,
    option_env_vars,
    secret_keys,
)
from devops_cli.config.settings import ArgoCDConfig, reset_settings_cache
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
    SettingSource,
    keyring_only_keys,
    secrets_by_ref,
)
from devops_cli.k8s.secret_push import (
    PushMode,
    PushOptions,
    PushResult,
    dry_run_push,
    plan_push,
    secret_line,
)
from tests.cluster_secret_fakes import (
    APP_KEY,
    APP_KEY_ENTRY,
    FakeCluster,
)
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessFake

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


def _context_free(argv: tuple[str, ...] | list[str]) -> list[str]:
    """The argv without `--context NAME`, as the fake cluster records it."""
    args = list(argv)
    if "--context" in args:
        index = args.index("--context")
        del args[index : index + 2]
    return args


def _db_row(*, dsn_first: bool = False) -> Any:
    """A basic-auth database Secret whose `DSN` is derived from its user and its password."""
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
    """A Secret whose `url` is derived from a hook ID in the keyring."""
    from devops_cli.config.constants import CONST_K8S_MATTERMOST_URL

    url = DerivedSource(f"{CONST_K8S_MATTERMOST_URL}/hooks/{{hook}}", {"hook": hook})
    return ClusterSecret(
        "devops", "example-hook", "devops", (SecretEntry("url", url, required=required),)
    )


def test_table_holds_each_secret_entry_with_its_source_and_restarts() -> None:
    rows = [
        (
            secret.ref,
            entry.key,
            secret.stack,
            entry.required,
            entry.generator,
            str(entry.adopt_from) if entry.adopt_from else None,
            tuple(str(w) for w in secret.restarts),
        )
        for secret in CLUSTER_SECRETS
        for entry in secret.entries
    ]
    assert rows == [
        (
            "llm/llm-gateway-secrets",
            "master-key",
            "llm",
            True,
            SecretGenerator("hex", 24, prefix="sk-"),
            None,
            ("deployment/llm-gateway",),
        ),
        (
            "llm/llm-gateway-secrets",
            "gemini-api-key",
            "llm",
            False,
            None,
            None,
            ("deployment/llm-gateway",),
        ),
        (
            "llm/llm-gateway-secrets",
            "anthropic-api-key",
            "llm",
            False,
            None,
            None,
            ("deployment/llm-gateway",),
        ),
        (
            "llm/qdrant-api-key",
            "api-key",
            "llm",
            True,
            SecretGenerator("urlsafe", 32),
            None,
            ("statefulset/qdrant", "statefulset/open-webui"),
        ),
        (
            "llm/valkey-runs-auth",
            "password",
            "llm",
            True,
            SecretGenerator("hex", 32),
            None,
            ("deployment/valkey-runs",),
        ),
        (
            "llm/valkey-auth",
            "VALKEY_PASSWORD",
            "llm",
            True,
            SecretGenerator("hex", 32),
            None,
            ("deployment/valkey", "statefulset/open-webui"),
        ),
        (
            "llm/valkey-devops-auth",
            "password",
            "llm",
            True,
            SecretGenerator("hex", 32),
            None,
            ("deployment/valkey-devops",),
        ),
        (
            "cloudflared/cloudflared-token",
            "token",
            "base",
            False,
            None,
            None,
            ("deployment/cloudflared",),
        ),
        (
            "devops/devops-cli",
            APP_KEY_ENTRY,
            "devops",
            True,
            None,
            None,
            ("deployment/roadmap-service",),
        ),
        (
            "devops/devops-cli",
            "DEVOPS_CLI_AI_API_KEY",
            "devops",
            True,
            None,
            "llm/llm-gateway-secrets master-key",
            ("deployment/roadmap-service",),
        ),
        (
            "devops/devops-cli",
            "DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS",
            "devops",
            False,
            None,
            None,
            ("deployment/roadmap-service",),
        ),
        (
            "devops/devops-cli",
            "DEVOPS_CLI_FIRECRAWL_API_KEY",
            "devops",
            False,
            None,
            None,
            ("deployment/roadmap-service",),
        ),
        (
            "devops/devops-cli",
            "DEVOPS_CLI_VALKEY_PASSWORD",
            "devops",
            True,
            SecretGenerator("hex", 32),
            "llm/valkey-devops-auth password",
            ("deployment/roadmap-service",),
        ),
        (
            "devops/devops-cli",
            "DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN",
            "devops",
            False,
            None,
            None,
            ("deployment/roadmap-service",),
        ),
        (
            "monitoring/grafana-admin",
            "admin-user",
            "infra",
            True,
            None,
            None,
            ("deployment/grafana",),
        ),
        (
            "monitoring/grafana-admin",
            "admin-password",
            "infra",
            True,
            SecretGenerator("urlsafe", 32),
            "monitoring/grafana admin-password",
            ("deployment/grafana",),
        ),
        ("monitoring/alertmanager-mattermost", "url", "infra", False, None, None, ()),
        ("argocd/argocd-notifications-secret", "github-appID", "infra", False, None, None, ()),
        (
            "argocd/argocd-notifications-secret",
            "github-installationID",
            "infra",
            False,
            None,
            None,
            (),
        ),
        ("argocd/argocd-notifications-secret", "github-privateKey", "infra", False, None, None, ()),
        (
            "argocd/argocd-notifications-secret",
            "mattermost-deploys-url",
            "infra",
            False,
            None,
            None,
            (),
        ),
        ("gitea/gitea-admin", "username", "gitea", True, None, None, ("deployment/gitea",)),
        ("gitea/gitea-admin", "password", "gitea", True, None, None, ("deployment/gitea",)),
        ("mattermost/mattermost-db", "username", "chat", True, None, None, ()),
        (
            "mattermost/mattermost-db",
            "password",
            "chat",
            True,
            SecretGenerator("urlsafe", 32),
            "mattermost/mattermost-db password",
            (),
        ),
        ("mattermost/mattermost-db", "DB_CONNECTION_STRING", "chat", True, None, None, ()),
    ]


def test_generators_make_the_documented_shapes() -> None:
    gateway, qdrant, runs = (CLUSTER_SECRETS[i].entries[0].generator for i in range(3))
    assert gateway is not None
    assert qdrant is not None
    assert runs is not None
    master, api_key, password = gateway.generate(), qdrant.generate(), runs.generate()
    assert (master[:3], len(master), len(api_key) >= 43, len(password), int(password, 16) >= 0) == (
        "sk-",
        51,
        True,
        64,
        True,
    )


def test_tunnel_token_is_a_managed_credential() -> None:
    from devops_cli.config.env import get_all_env_var_specs
    from devops_cli.security.secrets import build_secret_registry

    specs = {spec.option_key for spec in get_all_env_var_specs() if spec.is_secret}
    registry = build_secret_registry()
    assert (
        "cloudflare.tunnel_token" in secret_keys(),
        keyring_names()["cloudflare.tunnel_token"],
        "cloudflare.tunnel_token" in specs,
        registry["cloudflare.tunnel_token"].env_vars,
    ) == (True, "cloudflare_tunnel_token", True, ("DEVOPS_CLI_CLOUDFLARE_TUNNEL_TOKEN",))


def test_the_gitea_admin_password_is_a_typed_managed_credential_and_its_user_a_literal() -> None:
    from devops_cli.config.env import get_all_env_var_specs
    from devops_cli.security.secrets import build_secret_registry

    gitea = next(s for s in CLUSTER_SECRETS if s.ref == "gitea/gitea-admin")
    username, password = gitea.entries
    specs = {spec.option_key for spec in get_all_env_var_specs() if spec.is_secret}
    registry = build_secret_registry()
    assert (
        (username.key, username.source),
        (password.key, password.source, password.required, password.generator),
        "gitea.admin_password" in secret_keys(),
        option_env_vars()["gitea.admin_password"],
        "gitea.admin_password" in specs,
        registry["gitea.admin_password"].env_vars,
    ) == (
        ("username", LiteralSource("gitea_admin")),
        ("password", KeyringSource("gitea_admin_password", "gitea.admin_password"), True, None),
        True,
        "DEVOPS_CLI_GITEA_ADMIN_PASSWORD",
        True,
        ("DEVOPS_CLI_GITEA_ADMIN_PASSWORD",),
    )


def test_the_gitea_dry_run_lists_its_secret_and_restart_with_no_value() -> None:
    result = _push("--stack", "gitea", "--dry-run")
    output = result.output
    order = [
        "kubectl get namespace gitea --ignore-not-found -o name --context test-ctx",
        "kubectl get secret/gitea-admin -n gitea --ignore-not-found -o json",
        "keyring read devops-cli/gitea_admin_password",
        "kubectl apply --server-side --field-manager=devops-cli --force-conflicts -f -",
        "kubectl get deployment/gitea -n gitea --ignore-not-found -o name",
        "kubectl rollout restart deployment/gitea -n gitea",
    ]
    positions = [output.find(text) for text in order]
    assert (
        result.exit_code,
        -1 in positions,
        positions == sorted(positions),
        '"password": "<base64 of keyring gitea_admin_password>"' in output,
        "no request was made" in output,
    ) == (0, False, True, True, True), output


def test_the_notifier_values_are_two_settings_and_a_managed_credential() -> None:
    notifier = next(s for s in CLUSTER_SECRETS if s.ref == NOTIFIER)
    assert (
        [(e.key, e.source, e.required, e.generator) for e in notifier.entries],
        notifier.restarts,
        sorted(set(ArgoCDConfig.model_fields) - {"url"}),
        option_env_vars()["argocd.github_app_id"],
        option_env_vars()["argocd.github_app_installation_id"],
        option_env_vars()["argocd.github_app_private_key"],
        keyring_names()["argocd.github_app_private_key"],
        "argocd.github_app_private_key" in secret_keys(),
        "argocd.github_app_id" in secret_keys(),
    ) == (
        [
            ("github-appID", SettingSource("argocd.github_app_id"), False, None),
            (
                "github-installationID",
                SettingSource("argocd.github_app_installation_id"),
                False,
                None,
            ),
            (
                "github-privateKey",
                KeyringSource(NOTIFIER_KEYRING, "argocd.github_app_private_key"),
                False,
                None,
            ),
            (
                "mattermost-deploys-url",
                DerivedSource(
                    f"{CONST_K8S_MATTERMOST_URL}/hooks/{{hook}}",
                    {"hook": KeyringSource("mattermost_deploys_hook", "mattermost.deploys_hook")},
                ),
                False,
                None,
            ),
        ],
        (),
        ["github_app_id", "github_app_installation_id"],
        "DEVOPS_CLI_ARGOCD_GITHUB_APP_ID",
        "DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID",
        "DEVOPS_CLI_ARGOCD_GITHUB_APP_PRIVATE_KEY",
        NOTIFIER_KEYRING,
        True,
        False,
    )


def test_the_notifier_plan_names_each_key_and_its_source_with_no_value(
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
    result = _push("--only", NOTIFIER, "--plan")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "github-appID (setting argocd.github_app_id) would create" in output,
        "github-installationID (setting argocd.github_app_installation_id) would create" in output,
        f"github-privateKey (keyring {NOTIFIER_KEYRING}) would create" in output,
        [v for v in (NOTIFIER_PEM.splitlines()[1], NOTIFIER_APP_ID) if v in result.output],
        cluster.applies(),
    ) == (0, True, True, True, [], []), result.output


def test_the_notifier_dry_run_names_the_keys_with_placeholders_and_runs_nothing(
    cluster: FakeCluster,
) -> None:
    result = _push("--only", NOTIFIER, "--dry-run")
    output = result.output
    assert (
        result.exit_code,
        '"github-appID": "<base64 of setting argocd.github_app_id, left out when it has none>"'
        in output,
        f'"github-privateKey": "<base64 of keyring {NOTIFIER_KEYRING}, left out when it has none>"'
        in output,
        "no request was made" in output,
        cluster.calls,
    ) == (0, True, True, True, []), output


def test_plan_reads_only_and_prints_states_without_values(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    backend = _install(monkeypatch, cluster, keyring_store, values={"qdrant_api_key": QDRANT_KEY})
    cluster.add_secret("llm", "llm-gateway-secrets", {"master-key": "sk-live-gateway-0003"})
    result = _push("--stack", "llm", "--plan")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        {tuple(c[:2]) for c in (call.argv for call in cluster.calls)},
        backend.writes,
        "master-key (keyring llm_gateway_master_key) would adopt" in output,
        "password (keyring runs_index_password) would generate" in output,
        "api-key (keyring qdrant_api_key) would create" in output,
        "read the keyring and the cluster (context test-ctx); wrote nothing" in output,
        "sk-live-gateway-0003" in output or QDRANT_KEY in output,
    ) == (0, {("kubectl", "get")}, {}, True, True, True, True, False)


def test_dry_run_makes_no_request_and_prints_the_requests_in_order() -> None:
    result = _push("--stack", "llm", "--dry-run")
    output = result.output
    order = [
        "keyring read devops-cli/keyring-unlock-probe",
        "kubectl get namespace llm --ignore-not-found -o name --context test-ctx",
        "kubectl get secret/llm-gateway-secrets -n llm --ignore-not-found -o json",
        "keyring read devops-cli/llm_gateway_master_key",
        "keyring write devops-cli/llm_gateway_master_key",
        "kubectl apply --server-side --field-manager=devops-cli --force-conflicts -f -",
        "kubectl annotate secret/llm-gateway-secrets -n llm "
        "kubectl.kubernetes.io/last-applied-configuration-",
        "kubectl get deployment/llm-gateway -n llm --ignore-not-found -o name",
        "kubectl rollout restart deployment/llm-gateway -n llm",
    ]
    positions = [output.find(text) for text in order]
    assert (
        result.exit_code,
        result.exception,
        -1 in positions,
        positions == sorted(positions),
        "no request was made" in output,
    ) == (0, None, False, True, True), output


def test_dry_run_wins_over_plan() -> None:
    result = _push("--only", "llm/qdrant-api-key", "--plan", "--dry-run")
    assert (result.exit_code, "no request was made" in result.output) == (0, True)


def test_dry_run_returns_the_push_result_type_marked_as_a_dry_run() -> None:
    result = run_push(CLUSTER_SECRETS, PushOptions(context="test-ctx"), mode=PushMode.DRY_RUN)
    assert (
        type(result),
        result.dry_run,
        result.plan,
        bool(result.requests),
    ) == (PushResult, True, None, True)


def test_the_dry_run_lists_exactly_the_requests_a_push_then_makes(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    selected, _ = secrets_by_ref(["llm/qdrant-api-key", "devops/devops-cli"])
    options = PushOptions(context="test-ctx", strict_namespaces=True)
    holds = {"every selected namespace exists"}
    requests = dry_run_push(selected, options).requests
    planned = [r for r in requests if not r.condition or r.condition in holds]
    stub_keyring.values["service_webhook_secrets"] = "service-secrets-value-0001"
    stub_keyring.values["firecrawl_api_key"] = "firecrawl-secrets-value-0001"
    stub_keyring.values["mattermost_command_token"] = "mattermost-secrets-value-0001"
    result = _push("--only", "llm/qdrant-api-key", "--only", "devops/devops-cli")
    planned_apply = json.loads(next(r.stdin for r in planned if r.stdin) or "{}")
    applied = cluster.applied_items()
    assert result.exit_code == 0, result.output
    assert (
        [_context_free(r.argv) for r in planned if r.argv],
        [r.target for r in planned if r.method == "keyring read"],
        [{**i, "data": sorted(i["data"])} for i in planned_apply["items"]],
        sorted(v[:1] + v[-1:] for i in planned_apply["items"] for v in i["data"].values()),
    ) == (
        [call.argv for call in cluster.calls],
        [f"devops-cli/{key}" for key in stub_keyring.reads],
        [{**i, "data": sorted(i["data"])} for i in applied],
        ["<>", "<>", "<>", "<>", "<>", "<>", "<>"],
    )


def test_the_dry_run_names_the_conditional_requests_and_holds_no_value() -> None:
    selected, _ = secrets_by_ref(["devops/devops-cli"])
    requests = dry_run_push(selected, PushOptions(rotate=True)).requests
    text = "\n".join(f"{r.line()}\n{r.stdin or ''}" for r in requests)
    applied = json.loads(next(r.stdin for r in requests if r.stdin) or "{}")["items"][0]
    assert (
        [
            r.condition
            for r in requests
            if r.argv[1:3] == ("get", "secret/devops-cli")
            or r.argv[1:3] == ("get", "secret/llm-gateway-secrets")
        ],
        [r.target for r in requests if r.method == "keyring read"][1:2],
        applied["data"][APP_KEY_ENTRY],
        [r.argv[:1] for r in requests if r.argv[:1] == ("gh",)],
        "GH_TOKEN" in text,
        any(v in text for v in FULL_KEYRING.values()),
    ) == (
        [
            "namespace devops exists",
            "namespace devops exists and keyring llm_gateway_master_key is empty",
        ],
        ["devops-cli/service_github_app_private_key"],
        "<base64 of keyring service_github_app_private_key>",
        [],
        False,
        False,
    )


def test_setting_and_literal_sources_feed_rows_later_items_add(
    cluster: FakeCluster, stub_keyring: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_K8S_DOMAIN", "example.com")
    row = ClusterSecret(
        "devops",
        "example-creds",
        "devops",
        (
            SecretEntry("url", LiteralSource("https://example.com/repo.git")),
            SecretEntry("domain", SettingSource("k8s.domain")),
            SecretEntry("slug", SettingSource("service.github_app.slug"), required=False),
        ),
    )
    plan = plan_push([row], PushOptions(context="test-ctx"))
    assert [(e.entry.key, e.state.value, e.value) for e in plan.secrets[0].entries] == [
        ("url", "created", "https://example.com/repo.git"),
        ("domain", "created", "example.com"),
        ("slug", "skipped", None),
    ]


def test_plan_reprs_hold_no_value(cluster: FakeCluster, stub_keyring: FakeKeyring) -> None:
    leaked = {
        "kubectl.kubernetes.io/last-applied-configuration": json.dumps(
            {"stringData": {"api-key": "live-annotation-value-0001"}}
        )
    }
    cluster.add_secret(
        "llm", "qdrant-api-key", {"api-key": "live-qdrant-value-0004"}, annotations=leaked
    )
    plan = plan_push(CLUSTER_SECRETS[1:2], PushOptions(context="test-ctx", rotate=True))
    text = repr(plan)
    assert (
        plan.secrets[0].leaked_annotation(),
        [
            v
            for v in ("live-annotation-value-0001", "live-qdrant-value-0004", QDRANT_KEY)
            if v in text
        ],
    ) == (True, [])


def test_plan_lists_the_workloads_a_changed_secret_would_restart(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.add_secret("llm", "qdrant-api-key", {"legacy": "kept-by-another-manager"})
    cluster.add_secret("llm", "valkey-runs-auth", {"password": RUNS_PASSWORD})
    cluster.workloads = {("llm", "statefulset/qdrant"), ("llm", "deployment/valkey-runs")}
    result = _push("--only", "llm/qdrant-api-key", "--only", "llm/valkey-runs-auth", "--plan")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "api-key (keyring qdrant_api_key) would create; would restart: statefulset/qdrant"
        in output,
        "password (keyring runs_index_password) unchanged; would restart: none" in output,
        {tuple(c[:2]) for c in (call.argv for call in cluster.calls)},
    ) == (0, True, True, {("kubectl", "get")})


def test_the_plan_and_the_dry_run_name_a_derived_entry_with_no_value(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    db_value = "keyring-db-value-0001"
    _install(monkeypatch, cluster, keyring_store, values={DB_KEY: db_value})
    requests = dry_run_push([_db_row()], PushOptions()).requests
    calls_of_the_dry_run = list(cluster.calls)
    line = secret_line(plan_push([_db_row()], PushOptions()).secrets[0], preview=True)
    applied = json.loads(next(r.stdin for r in requests if r.stdin) or "{}")["items"][0]
    text = "\n".join(f"{r.line()}\n{r.stdin or ''}" for r in requests)
    assert (
        calls_of_the_dry_run,
        line,
        (applied["type"], applied["data"]["DSN"]),
        [r.target for r in requests if r.method == "keyring write"],
        db_value in line + text,
    ) == (
        [],
        "devops/example-db: username (literal) would create, password (keyring "
        "example_db_password) would create, DSN (derived from literal, keyring "
        "example_db_password) would create; would restart: none",
        (
            "kubernetes.io/basic-auth",
            "<base64 of derived from literal, keyring example_db_password>",
        ),
        ["devops-cli/example_db_password"],
        False,
    )


def test_the_dry_run_lists_the_derived_reads_where_the_push_makes_them(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, keyring_store: FakeKeyring
) -> None:
    from devops_cli.k8s.secret_push import execute_push

    rows = [
        _hook_row(KeyringSource("example_hook")),
        ClusterSecret(
            "devops",
            "example-token",
            "devops",
            (SecretEntry("token", KeyringSource("example_token")),),
        ),
    ]
    backend = _install(
        monkeypatch,
        cluster,
        keyring_store,
        values={"example_hook": "hook-value-0001", "example_token": "token-value-0001"},
    )
    options = PushOptions(context="test-ctx", strict_namespaces=True)
    requests = dry_run_push(rows, options).requests
    planned = [r for r in requests if r.condition in ("", "every selected namespace exists")]
    execute_push(plan_push(rows, options), options)
    assert (
        [_context_free(r.argv) for r in planned if r.argv],
        [r.target for r in planned if r.method == "keyring read"],
    ) == (
        [call.argv for call in cluster.calls],
        [f"devops-cli/{key}" for key in backend.reads],
    )
    assert backend.reads[-2:] == ["example_token", "example_hook"]


def test_keyring_only_keys_count_the_keyring_inputs_of_a_derived_entry() -> None:
    rows = [_db_row(), _hook_row(KeyringSource("example_hook"))]
    assert keyring_only_keys(rows) == frozenset({DB_KEY, "example_hook"})


def test_mattermost_db_secret_plan_and_dsn_shape() -> None:
    """The database Secret row has basic-auth type and DSN parses to valid connection URL (#1391)."""
    import urllib.parse

    from devops_cli.k8s.cluster_secrets import (
        MATTERMOST_DB_AUTH_KEY,
        DerivedSource,
        keyring_only_keys,
    )

    (secret,) = [s for s in CLUSTER_SECRETS if s.ref == "mattermost/mattermost-db"]
    assert (secret.secret_type, secret.stack, secret.restarts) == (
        "kubernetes.io/basic-auth",
        "chat",
        (),
    )
    assert MATTERMOST_DB_AUTH_KEY in keyring_only_keys(CLUSTER_SECRETS)

    entries = {e.key: e for e in secret.entries}
    dsn_source = entries["DB_CONNECTION_STRING"].source
    assert isinstance(dsn_source, DerivedSource)

    test_user = "mattermost"
    test_pw = "pass/word@123"
    resolved_inputs = {
        "username": urllib.parse.quote(test_user, safe=""),
        "password": urllib.parse.quote(test_pw, safe=""),
    }
    dsn = dsn_source.template.format(**resolved_inputs)
    split = urllib.parse.urlsplit(dsn)
    assert (
        split.scheme,
        urllib.parse.unquote(split.username or ""),
        urllib.parse.unquote(split.password or ""),
        split.hostname,
        split.port,
        split.path,
    ) == (
        "postgres",
        test_user,
        test_pw,
        "mattermost-db-rw.mattermost.svc.cluster.local",
        5432,
        "/mattermost",
    )


def test_alertmanager_mattermost_secret_plan_and_derived_url() -> None:
    """The Alertmanager Mattermost Secret row has infra stack and derived webhook URL (#1392)."""
    from devops_cli.config.constants import CONST_K8S_MATTERMOST_URL
    from devops_cli.k8s.cluster_secrets import DerivedSource

    (secret,) = [s for s in CLUSTER_SECRETS if s.ref == "monitoring/alertmanager-mattermost"]
    assert (secret.secret_type, secret.stack, secret.restarts) == (
        "Opaque",
        "infra",
        (),
    )
    entries = {e.key: e for e in secret.entries}
    assert not entries["url"].required
    url_source = entries["url"].source
    assert isinstance(url_source, DerivedSource)
    assert url_source.template == f"{CONST_K8S_MATTERMOST_URL}/hooks/{{hook}}"
    assert url_source.inputs["hook"].option == "mattermost.alerts_hook"
