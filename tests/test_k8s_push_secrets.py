"""The cluster Secret table and `devops k8s push-secrets` (workstation keyring → cluster).

Offline: a stub keyring backend, and a fake cluster standing in for `subprocess.run` beneath
`run_subprocess`, so every argv, stdin and environment a child would see is recorded.
"""

from __future__ import annotations

import base64
import functools
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import keyring
import pytest
import typer
import yaml
from click.testing import CliRunner
from keyring.backends.fail import Keyring as FailKeyring

from devops_cli.commands.k8s.cluster_secret_push import push_secrets
from devops_cli.commands.k8s.stack_lifecycle import _HELM_RELEASES_BY_STACK
from devops_cli.config import options as opt
from devops_cli.config.env import ENV_VAR_TO_OPTION, OPTION_TO_ENV_VAR, get_all_env_var_specs
from devops_cli.k8s.cluster_secrets import (
    CLUSTER_SECRETS,
    LLM_GATEWAY_MASTER_KEY,
    KeyringSource,
    SecretGenerator,
)
from devops_cli.security.secrets import build_secret_registry
from devops_cli.telemetry import tracer
from tests.cluster_secret_fakes import (
    MACHINE_LOGIN,
    MACHINE_TOKEN,
    FakeCluster,
    FakeKeyring,
    forbid_requests,
)
from tests.conftest import PINNED_GITHUB_TOKEN

REPO_ROOT = Path(__file__).resolve().parent.parent
K8S_DIR = REPO_ROOT / "k8s"
runner = CliRunner()
# Built once: building the whole `devops k8s` group costs a quarter second per invoke.
_push_app = typer.Typer()
_push_app.command()(push_secrets)
PUSH_COMMAND = typer.main.get_command(_push_app)

GATEWAY_KEY = "sk-keyring-gateway-value-0001"
QDRANT_KEY = "qdrant-keyring-value-0001"
RUNS_PASSWORD = "runs-keyring-value-0001"
TUNNEL_TOKEN = "tunnel-keyring-value-0001"
FULL_KEYRING = {
    LLM_GATEWAY_MASTER_KEY: GATEWAY_KEY,
    "qdrant_api_key": QDRANT_KEY,
    "runs_index_password": RUNS_PASSWORD,
    "cloudflare_tunnel_token": TUNNEL_TOKEN,
}
TABLE_REFS = {secret.ref for secret in CLUSTER_SECRETS}


@pytest.fixture
def cluster(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeCluster]:
    # No exporter to start for each child's span, nor to flush at teardown.
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    # Each child's span would otherwise load the settings twice per test to learn the above.
    monkeypatch.setattr(tracer, "_resolve_telemetry_settings", lambda: (None, False))
    monkeypatch.setenv("K8S_CONTEXT", "test-ctx")
    monkeypatch.setenv("K8S_NAMESPACE", "test")
    fake = FakeCluster()
    with patch("devops_cli.core.process.subprocess.run", side_effect=fake):
        yield fake


def _install(monkeypatch: pytest.MonkeyPatch, cluster: FakeCluster, **values: Any) -> FakeKeyring:
    backend = FakeKeyring(values.get("values", FULL_KEYRING), locked=values.get("locked", False))
    backend.events = cluster.events
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    monkeypatch.delenv("DEVOPS_CLI_HEADLESS_AUTH", raising=False)
    return backend


@pytest.fixture
def stub_keyring(monkeypatch: pytest.MonkeyPatch, cluster: FakeCluster) -> FakeKeyring:
    return _install(monkeypatch, cluster)


def _push(*args: str) -> Any:
    return runner.invoke(PUSH_COMMAND, ["--context", "test-ctx", *args])


# ── The table ────────────────────────────────────────────────────────────────


def test_table_holds_this_items_six_entries_in_five_secrets() -> None:
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
            "llm/qdrant-api-key",
            "api-key",
            "llm",
            True,
            SecretGenerator("urlsafe", 32),
            None,
            ("statefulset/qdrant",),
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
            "cloudflared/cloudflared-token",
            "token",
            "base",
            False,
            None,
            None,
            ("deployment/cloudflared",),
        ),
        ("devops/devops-cli", "GH_TOKEN", "devops", True, None, None, ()),
        (
            "devops/devops-cli",
            "DEVOPS_CLI_AI_API_KEY",
            "devops",
            True,
            None,
            "llm/llm-gateway-secrets master-key",
            (),
        ),
    ]


def test_generators_make_the_documented_shapes() -> None:
    gateway, qdrant, runs = (CLUSTER_SECRETS[i].entries[0].generator for i in range(3))
    assert gateway is not None and qdrant is not None and runs is not None
    master, api_key, password = gateway.generate(), qdrant.generate(), runs.generate()
    assert (master[:3], len(master), len(api_key) >= 43, len(password), int(password, 16) >= 0) == (
        "sk-",
        51,
        True,
        64,
        True,
    )


def _secret_references(node: Any) -> Iterator[str]:
    """Secret names a manifest or values document references, at any depth."""
    if isinstance(node, list):
        for item in node:
            yield from _secret_references(item)
        return
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        if key in ("secretKeyRef", "secretRef") and isinstance(value, dict) and value.get("name"):
            yield str(value["name"])
        elif str(key).lower().endswith("existingsecret") and isinstance(value, str) and value:
            yield value
        else:
            yield from _secret_references(value)


def _values_namespaces() -> dict[str, str]:
    return {
        str(Path(release["values"]).resolve()): release["namespace"]
        for releases in _HELM_RELEASES_BY_STACK.values()
        for release in releases
    }


@functools.cache
def yaml_documents(root: Path) -> tuple[tuple[Path, Any], ...]:
    """Every YAML document under root, parsed once with libyaml's safe loader."""
    return tuple(
        (path, document)
        for path in sorted(root.rglob("*.yaml"))
        for document in yaml.load_all(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
    )


def referenced_secrets(root: Path) -> set[str]:
    """`namespace/name` of every Secret a YAML file under root references."""
    values_namespaces = _values_namespaces()
    found: set[str] = set()
    for path, document in yaml_documents(root):
        names = set(_secret_references(document))
        metadata = document.get("metadata") if isinstance(document, dict) else None
        namespace = (metadata or {}).get("namespace") or values_namespaces.get(
            str(path.resolve()), "?"
        )
        found.update(f"{namespace}/{name}" for name in names)
    return found


def test_every_secret_referenced_under_k8s_has_a_table_row() -> None:
    references = referenced_secrets(K8S_DIR)
    assert (references - TABLE_REFS, len(references) >= 5) == (set(), True)


def test_a_reference_without_a_row_fails_the_guard(tmp_path: Path) -> None:
    (tmp_path / "values.yaml").write_text(
        "metadata: {namespace: tools}\nfooExistingSecret: unlisted\n"
        "env: [{valueFrom: {secretKeyRef: {name: also-unlisted, key: k}}}]\n",
        encoding="utf-8",
    )
    assert referenced_secrets(tmp_path) - TABLE_REFS == {"tools/unlisted", "tools/also-unlisted"}


def test_keyring_sources_are_managed_keys_or_declared_keyring_only() -> None:
    from devops_cli.k8s.cluster_secrets import keyring_only_keys

    sources = [
        entry.source
        for secret in CLUSTER_SECRETS
        for entry in secret.entries
        if isinstance(entry.source, KeyringSource)
    ]
    managed = set(opt.KEYRING_KEYS.values())
    assert (
        all(opt.KEYRING_KEYS[s.option] == s.key for s in sources if s.option),
        {s.key for s in sources if not s.option} == keyring_only_keys(),
        keyring_only_keys() & managed,
        keyring_only_keys(),
    ) == (True, True, frozenset(), frozenset({LLM_GATEWAY_MASTER_KEY}))


def test_env_name_keys_of_devops_cli_feed_their_options() -> None:
    devops_cli = next(s for s in CLUSTER_SECRETS if s.ref == "devops/devops-cli")
    option_keys = [e.key for e in devops_cli.entries if e.key.startswith("DEVOPS_CLI_")]
    assert (
        {key: ENV_VAR_TO_OPTION.get(key) for key in option_keys},
        OPTION_TO_ENV_VAR[opt.AI_API_KEY],
    ) == ({"DEVOPS_CLI_AI_API_KEY": opt.AI_API_KEY}, "DEVOPS_CLI_AI_API_KEY")


def _manifest_workloads() -> set[str]:
    return {
        f"{str(document.get('kind', '')).lower()}/{document['metadata'].get('name')}"
        for _, document in yaml_documents(K8S_DIR)
        if isinstance(document, dict) and isinstance(document.get("metadata"), dict)
    }


def test_every_restart_target_is_a_manifest_workload_or_helm_release() -> None:
    releases = {r["name"] for rs in _HELM_RELEASES_BY_STACK.values() for r in rs}
    targets = [w for secret in CLUSTER_SECRETS for w in secret.restarts]
    workloads = _manifest_workloads()
    assert [str(t) for t in targets if str(t) not in workloads and t.name not in releases] == []


def test_tunnel_token_is_a_managed_credential() -> None:
    specs = {spec.option_key for spec in get_all_env_var_specs() if spec.is_secret}
    registry = build_secret_registry(opt.KEYRING_KEYS)
    assert (
        opt.CLOUDFLARE_TUNNEL_TOKEN in opt.SECRET_CONFIG_OPTIONS,
        opt.KEYRING_KEYS[opt.CLOUDFLARE_TUNNEL_TOKEN],
        opt.CLOUDFLARE_TUNNEL_TOKEN in specs,
        registry[opt.CLOUDFLARE_TUNNEL_TOKEN].env_vars,
    ) == (True, "cloudflare_tunnel_token", True, ("DEVOPS_CLI_CLOUDFLARE_TUNNEL_TOKEN",))


def test_no_table_secret_is_copied_back_by_sync() -> None:
    from devops_cli.k8s.credentials import sync_k8s_credentials

    read: list[str] = []

    def record(secret_name: str, namespace: str, context: str | None = None) -> dict[str, str]:
        read.append(f"{namespace}/{secret_name}")
        return {}

    with patch("devops_cli.k8s.credentials.fetch_secret_data", side_effect=record):
        sync_k8s_credentials(stack="all", save_to_keyring=False)
    assert (set(read) & TABLE_REFS, bool(read)) == (set(), True)


def _readme_row(secret: Any, entry: Any) -> str:
    source = entry.source
    label = f"keyring `{source.key}`" if isinstance(source, KeyringSource) else source.label
    absent = "fail" if entry.required else "skip with a warning"
    if isinstance(source, KeyringSource):
        generator = entry.generator
        if generator is not None:
            body = (
                f"{generator.nbytes * 2} hex"
                if generator.encoding == "hex"
                else f"`token_urlsafe({generator.nbytes})`"
            )
            absent = (
                f"generate `{generator.prefix}` + {body}"
                if generator.prefix
                else f"generate {body}"
            )
        adopt = f"adopt from `{entry.adopt_from}`" if entry.adopt_from else "adopt the live value"
        absent = f"{adopt}; else {absent}"
    restarts = ", ".join(f"`{w}`" for w in secret.restarts) or "none"
    required = "yes" if entry.required else "no"
    cells = [f"`{secret.ref}`", f"`{entry.key}`", label, required, absent, secret.stack, restarts]
    return "| " + " | ".join(cells) + " |"


def test_readme_lists_the_table() -> None:
    readme = (K8S_DIR / "README.md").read_text(encoding="utf-8")
    rows = [_readme_row(s, e) for s in CLUSTER_SECRETS for e in s.entries]
    assert [row for row in rows if row not in readme] == []


# ── push-secrets: apply and resolution ──────────────────────────────────────


def test_apply_is_one_server_side_apply_of_a_list_on_stdin(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    result = _push("--github-account", MACHINE_LOGIN)
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
            "cloudflared/cloudflared-token": ["token"],
            "devops/devops-cli": ["DEVOPS_CLI_AI_API_KEY", "GH_TOKEN"],
        },
        [],
        {"devops-cli"},
    )


def test_keyring_values_without_live_secrets_are_created_and_restart_nothing(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.workloads = {("llm", "deployment/llm-gateway"), ("llm", "statefulset/qdrant")}
    result = _push("--github-account", MACHINE_LOGIN)
    assert (
        result.exit_code,
        "llm/qdrant-api-key: api-key (keyring qdrant_api_key) created" in result.output,
        cluster.live_data("devops", "devops-cli"),
        cluster.commands("kubectl", "rollout"),
    ) == (
        0,
        True,
        {"GH_TOKEN": MACHINE_TOKEN, "DEVOPS_CLI_AI_API_KEY": GATEWAY_KEY},
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
    cluster.workloads = {("llm", "statefulset/qdrant")}
    result = _push("--only", "llm/qdrant-api-key")
    assert (result.exit_code, cluster.commands("kubectl", "rollout")) == (
        0,
        [["kubectl", "rollout", "restart", "statefulset/qdrant", "-n", "llm"]],
    )


def test_a_missing_keyring_value_is_adopted_from_the_live_secret(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _install(monkeypatch, cluster, values={})
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
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _install(monkeypatch, cluster, values={})
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
        [LLM_GATEWAY_MASTER_KEY, "qdrant_api_key", "runs_index_password"],
    )


def test_the_devops_api_key_is_adopted_from_the_gateway_secret_never_generated(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _install(monkeypatch, cluster, values={})
    cluster.add_secret("llm", "llm-gateway-secrets", {"master-key": "sk-live-gateway-0001"})
    result = _push("--stack", "devops", "--github-account", MACHINE_LOGIN)
    assert (result.exit_code, backend.writes, cluster.live_data("devops", "devops-cli")) == (
        0,
        {LLM_GATEWAY_MASTER_KEY: "sk-live-gateway-0001"},
        {"GH_TOKEN": MACHINE_TOKEN, "DEVOPS_CLI_AI_API_KEY": "sk-live-gateway-0001"},
    )


def test_a_gateway_key_without_the_litellm_prefix_fails(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, cluster, values={LLM_GATEWAY_MASTER_KEY: "no-prefix-value-0001"})
    result = _push("--only", "llm/llm-gateway-secrets")
    assert (
        result.exit_code,
        "llm_gateway_master_key does not start with `sk-`" in result.output,
    ) == (
        1,
        True,
    )
    assert cluster.applies() == []


# ── Rotation ─────────────────────────────────────────────────────────────────


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


# ── Missing sources ──────────────────────────────────────────────────────────


def test_missing_required_sources_are_named_together_and_nothing_is_written(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _install(monkeypatch, cluster, values={})
    result = _push("--stack", "devops")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "GH_TOKEN" in output,
        "keyring llm_gateway_master_key is empty" in output,
        "--github-account" in output and "k8s.github_account" in output,
        backend.writes,
        cluster.applies(),
    ) == (1, True, True, True, {}, [])


def test_a_missing_optional_source_is_skipped_with_a_warning_and_left_out(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    values = {k: v for k, v in FULL_KEYRING.items() if k != "cloudflare_tunnel_token"}
    _install(monkeypatch, cluster, values=values)
    result = _push("--stack", "base")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "devops config set cloudflare.tunnel_token" in output,
        cluster.applies(),
    ) == (0, True, [])


# ── Keyring ──────────────────────────────────────────────────────────────────


def test_a_locked_keyring_stops_before_any_kubectl(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _install(monkeypatch, cluster, locked=True)
    result = _push()
    assert (result.exit_code, "devops devcontainer unlock-keyring" in result.output) == (1, True)
    assert (cluster.calls, backend.writes) == ([], {})


def test_no_keyring_backend_stops_before_any_kubectl(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(keyring, "get_keyring", FailKeyring)
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


# ── Selection ────────────────────────────────────────────────────────────────


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


def test_stack_devops_reads_gh_and_the_gateway_key_only(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    result = _push("--stack", "devops", "--github-account", MACHINE_LOGIN)
    assert (
        result.exit_code,
        stub_keyring.secret_reads(),
        bool(cluster.commands("gh", "auth", "token")),
    ) == (
        0,
        {LLM_GATEWAY_MASTER_KEY},
        True,
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


def test_without_devops_a_bare_push_needs_no_github_account(
    cluster: FakeCluster, stub_keyring: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEVOPS_CLI_K8S_GITHUB_ACCOUNT", raising=False)
    cluster.namespaces = {"llm", "cloudflared"}
    result = _push()
    assert (result.exit_code, cluster.commands("gh")) == (0, [])


# ── gh ───────────────────────────────────────────────────────────────────────


def test_gh_runs_only_its_auth_commands_and_never_gets_the_session_token(
    cluster: FakeCluster, stub_keyring: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`gh auth` is exempt from the session pin (#767): its children get the ambient tokens
    unchanged and never the session's, and `gh auth token --user` still reads the account's
    stored token. No gh call of the push reaches GitHub with the machine token."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.setenv(name, f"ambient-{name.lower()}-0001")
    result = _push("--stack", "devops", "--github-account", MACHINE_LOGIN)
    gh_calls = [c for c in cluster.calls if c.argv[0] == "gh"]
    assert (
        result.exit_code,
        [c.argv for c in gh_calls],
        [(c.env.get("GH_TOKEN"), c.env.get("GITHUB_TOKEN")) for c in gh_calls],
        cluster.live_data("devops", "devops-cli")["GH_TOKEN"],
    ) == (
        0,
        [
            ["gh", "auth", "status", "--hostname", "github.com", "--json", "hosts"],
            ["gh", "auth", "token", "--user", MACHINE_LOGIN, "--hostname", "github.com"],
        ],
        [("ambient-gh_token-0001", "ambient-github_token-0001")] * 2,
        MACHINE_TOKEN,
    )
    assert PINNED_GITHUB_TOKEN not in {v for c in gh_calls for v in c.env.values()}


def test_an_ambient_token_of_the_same_login_does_not_hide_the_keyring_account(
    cluster: FakeCluster, stub_keyring: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gh lists an ambient GH_TOKEN as an account of its own; the keyring entry still wins."""
    monkeypatch.setenv("GH_TOKEN", MACHINE_TOKEN)
    result = _push("--stack", "devops", "--github-account", MACHINE_LOGIN)
    assert (result.exit_code, cluster.live_data("devops", "devops-cli")["GH_TOKEN"]) == (
        0,
        MACHINE_TOKEN,
    )


def test_the_account_comes_from_the_setting_when_no_flag_is_given(
    cluster: FakeCluster, stub_keyring: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_K8S_GITHUB_ACCOUNT", MACHINE_LOGIN)
    result = _push("--stack", "devops")
    assert (result.exit_code, cluster.live_data("devops", "devops-cli")["GH_TOKEN"]) == (
        0,
        MACHINE_TOKEN,
    )


def test_a_token_gh_could_not_confirm_fails_and_applies_nothing(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    cluster.gh_state = "error"
    result = _push("--stack", "devops", "--github-account", MACHINE_LOGIN)
    assert (
        result.exit_code,
        f"gh reports {MACHINE_LOGIN}'s token as error" in " ".join(result.output.split()),
        cluster.commands("gh", "auth", "token"),
        cluster.applies(),
    ) == (1, True, [], [])


def test_a_token_in_ghs_config_file_fails(cluster: FakeCluster, stub_keyring: FakeKeyring) -> None:
    cluster.gh_accounts = {MACHINE_LOGIN: (MACHINE_TOKEN, "oauth_token")}
    result = _push("--stack", "devops", "--github-account", MACHINE_LOGIN)
    assert (
        result.exit_code,
        "config file" in result.output,
        cluster.commands("gh", "auth", "token"),
    ) == (
        1,
        True,
        [],
    )


# ── Leaked annotation, values and --plan ───────────────────────────────────


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
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    backend = _install(monkeypatch, cluster, values={"cloudflare_tunnel_token": TUNNEL_TOKEN})
    cluster.add_secret("llm", "qdrant-api-key", {"api-key": "live-qdrant-value-0002"})
    result = _push("--github-account", MACHINE_LOGIN)
    values = [TUNNEL_TOKEN, "live-qdrant-value-0002", MACHINE_TOKEN, *backend.writes.values()]
    encoded = [base64.b64encode(v.encode()).decode() for v in values]
    argv = " ".join(" ".join(call.argv) for call in cluster.calls)
    texts = [argv, caplog.text, result.output, result.stderr if result.stderr_bytes else ""]
    assert (result.exit_code, [v for v in values + encoded if any(v in t for t in texts)]) == (
        0,
        [],
    )


def test_plan_reads_only_and_prints_states_without_values(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _install(monkeypatch, cluster, values={"qdrant_api_key": QDRANT_KEY})
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


# ── --dry-run: no request at all ─────────────────────────────────────────────


def _context_free(argv: tuple[str, ...] | list[str]) -> list[str]:
    """The argv without `--context NAME`, as the fake cluster records it."""
    args = list(argv)
    if "--context" in args:
        index = args.index("--context")
        del args[index : index + 2]
    return args


def test_dry_run_makes_no_request_and_prints_the_requests_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted = forbid_requests(monkeypatch)
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
        attempted,
        -1 in positions,
        positions == sorted(positions),
        "no request was made" in output,
    ) == (0, None, [], False, True, True), output


def test_plan_says_it_read_ghs_record_of_the_machine_account(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    result = _push("--only", "devops/devops-cli", "--github-account", MACHINE_LOGIN, "--plan")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "read the keyring, gh's record of its machine account (gh checks the token on "
        "github.com) and the cluster (context test-ctx); wrote nothing" in output,
        [call.argv[:3] for call in cluster.calls if call.argv[0] == "gh"],
    ) == (
        0,
        True,
        [["gh", "auth", "status"], ["gh", "auth", "token"]],
    )


def test_dry_run_wins_over_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    attempted = forbid_requests(monkeypatch)
    result = _push("--only", "llm/qdrant-api-key", "--plan", "--dry-run")
    assert (result.exit_code, attempted, "no request was made" in result.output) == (0, [], True)


def test_dry_run_returns_the_push_result_type_marked_as_a_dry_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devops_cli.commands.k8s.cluster_secret_push import run_push
    from devops_cli.k8s.secret_push import PushMode, PushOptions, PushResult

    attempted = forbid_requests(monkeypatch)
    result = run_push(CLUSTER_SECRETS, PushOptions(context="test-ctx"), mode=PushMode.DRY_RUN)
    assert (
        type(result),
        result.dry_run,
        result.plan,
        bool(result.requests),
        attempted,
    ) == (PushResult, True, None, True, [])


def test_a_real_push_returns_the_same_type_with_its_plan(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    from devops_cli.commands.k8s.cluster_secret_push import run_push
    from devops_cli.k8s.secret_push import PushMode, PushOptions, PushResult

    result = run_push(CLUSTER_SECRETS[1:2], PushOptions(context="test-ctx"), mode=PushMode.PUSH)
    assert (type(result), result.dry_run, result.plan is not None) == (PushResult, False, True)


def test_the_dry_run_lists_exactly_the_requests_a_push_then_makes(
    cluster: FakeCluster, stub_keyring: FakeKeyring
) -> None:
    """With both namespaces, every key in the keyring, gh holding the account's token and no
    live Secret, the push makes exactly the dry run's requests whose conditions that answers,
    in order, and applies the Secrets it showed with placeholders."""
    from devops_cli.k8s.cluster_secrets import secrets_by_ref
    from devops_cli.k8s.secret_push import PushOptions, dry_run_push

    selected, _ = secrets_by_ref(["llm/qdrant-api-key", "devops/devops-cli"])
    options = PushOptions(context="test-ctx", github_account=MACHINE_LOGIN, strict_namespaces=True)
    present = "every selected namespace exists"
    holds = {
        present,
        f"{present} and gh auth status lists {MACHINE_LOGIN} with a working token in the keyring",
    }
    requests = dry_run_push(selected, options).requests
    planned = [r for r in requests if not r.condition or r.condition in holds]
    result = _push(
        "--only",
        "llm/qdrant-api-key",
        "--only",
        "devops/devops-cli",
        "--github-account",
        MACHINE_LOGIN,
    )
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
        ["<>", "<>", "<>"],
    )


def test_under_only_every_request_after_the_namespace_reads_needs_them_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--only` stops on a missing namespace, so nothing after the namespace reads runs
    unless every selected namespace exists."""
    from devops_cli.k8s.cluster_secrets import secrets_by_ref
    from devops_cli.k8s.secret_push import PushOptions, dry_run_push

    forbid_requests(monkeypatch)
    selected, _ = secrets_by_ref(["llm/qdrant-api-key", "devops/devops-cli"])
    requests = dry_run_push(selected, PushOptions(strict_namespaces=True)).requests
    assert [r.method for r in requests if not r.condition] == [
        "keyring read",
        "kubectl get",
        "kubectl get",
    ]


def test_the_dry_run_names_the_conditional_requests_and_holds_no_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devops_cli.k8s.cluster_secrets import secrets_by_ref
    from devops_cli.k8s.secret_push import PushOptions, dry_run_push

    forbid_requests(monkeypatch)
    selected, _ = secrets_by_ref(["devops/devops-cli"])
    requests = dry_run_push(selected, PushOptions(rotate=True)).requests
    text = "\n".join(f"{r.line()}\n{r.stdin or ''}" for r in requests)
    assert (
        [
            r.condition
            for r in requests
            if r.argv[1:3] == ("get", "secret/devops-cli")
            or r.argv[1:3] == ("get", "secret/llm-gateway-secrets")
        ],
        [r.argv[:3] for r in requests if r.argv[:1] == ("gh",)],
        "gh auth token --user '<k8s.github_account>' --hostname github.com  [only if namespace "
        "devops exists and k8s.github_account is set and gh auth status lists "
        "<k8s.github_account> with a working token in the keyring]" in text,
        any(v in text for v in (*FULL_KEYRING.values(), MACHINE_TOKEN)),
    ) == (
        [
            "namespace devops exists",
            "namespace devops exists and keyring llm_gateway_master_key is empty",
        ],
        [("gh", "auth", "status"), ("gh", "auth", "token")],
        True,
        False,
    )


def test_setting_and_literal_sources_feed_rows_later_items_add(
    cluster: FakeCluster, stub_keyring: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.k8s.cluster_secrets import (
        ClusterSecret,
        LiteralSource,
        SecretEntry,
        SettingSource,
    )
    from devops_cli.k8s.secret_push import PushOptions, plan_push

    monkeypatch.setenv("DEVOPS_CLI_K8S_DOMAIN", "example.com")
    row = ClusterSecret(
        "devops",
        "example-creds",
        "devops",
        (
            SecretEntry("url", LiteralSource("https://example.com/repo.git")),
            SecretEntry("domain", SettingSource(opt.K8S_DOMAIN)),
            SecretEntry("username", SettingSource(opt.K8S_GITHUB_ACCOUNT), required=False),
        ),
    )
    plan = plan_push([row], PushOptions(context="test-ctx"))
    assert [(e.entry.key, e.state.value, e.value) for e in plan.secrets[0].entries] == [
        ("url", "created", "https://example.com/repo.git"),
        ("domain", "created", "example.com"),
        ("username", "skipped", None),
    ]


def test_a_failed_apply_echoes_no_kubectl_output_and_names_what_was_written(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    """kubectl may quote part of stdin; no slice of it reaches the output, and the message
    says which keyring entries were already stored rather than that nothing was written."""
    backend = _install(monkeypatch, cluster, values={})
    cluster.namespaces = {"llm"}
    quoted: list[str] = []

    def failing_apply(cmd: list[str], **kwargs: Any) -> Any:
        import subprocess

        if cmd[:3] == ["kubectl", "apply", "--server-side"]:
            encoded = json.loads(kwargs["input"])["items"][0]["data"]["api-key"]
            quoted.append(encoded[3:38])
            return subprocess.CompletedProcess(cmd, 1, "", f"error: invalid {quoted[0]}")
        return cluster(cmd, **kwargs)

    with patch("devops_cli.core.process.subprocess.run", side_effect=failing_apply):
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


def test_plan_reprs_hold_no_value(cluster: FakeCluster, stub_keyring: FakeKeyring) -> None:
    """A `logger.debug(plan)` or an assertion diff must not print live or keyring values."""
    from devops_cli.k8s.secret_push import PushOptions, plan_push

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


def _set_raw(cluster: FakeCluster, namespace: str, name: str, key: str, raw: bytes) -> None:
    cluster.secrets[(namespace, name)]["data"][key] = base64.b64encode(raw).decode()


def test_a_live_value_that_is_not_utf8_is_never_adopted(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _install(monkeypatch, cluster, values={})
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
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, cluster, values={})
    cluster.add_secret("llm", "llm-gateway-secrets", {"master-key": "no-prefix-live-0001"})
    result = _push("--only", "llm/llm-gateway-secrets")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "live llm/llm-gateway-secrets master-key does not start with `sk-`" in output,
        "keyring llm_gateway_master_key does not start" in output,
    ) == (1, True, False)


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
