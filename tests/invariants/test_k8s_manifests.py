"""The table of cluster Secrets (`CLUSTER_SECRETS`): its keyring sources, the options that its
keys feed, the sync that reads none of its Secrets back, and the README that lists it (#1322).

The tests read the table of the source code. The form of the manifests under `k8s/` is the work of
the `k8s` row of `devops ci` and of kube-linter, and no test asserts a value of them (#6060).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from devops_cli.config.env import keyring_names, option_env_vars
from devops_cli.k8s.cluster_secrets import (
    CLUSTER_SECRETS,
    DEVOPS_CACHE_VALKEY_AUTH_KEY,
    GRAFANA_RENDERER_AUTH_KEY,
    GRAFANA_SECURITY_KEY,
    LLM_GATEWAY_MASTER_KEY,
    MATTERMOST_DB_AUTH_KEY,
    SEARXNG_SERVER_KEY,
    KeyringSource,
    keyring_only_keys,
    keyring_sources,
)
from tests.support.paths import REPO_ROOT

TABLE_REFS = {secret.ref for secret in CLUSTER_SECRETS}


def test_keyring_sources_are_managed_keys_or_declared_keyring_only() -> None:
    sources = [
        source
        for secret in CLUSTER_SECRETS
        for entry in secret.entries
        for source in keyring_sources(entry)
    ]
    managed = set(keyring_names().values())
    assert (
        all(keyring_names()[s.option] == s.key for s in sources if s.option),
        {s.key for s in sources if not s.option} == keyring_only_keys(),
        keyring_only_keys() & managed,
        keyring_only_keys(),
    ) == (
        True,
        True,
        frozenset(),
        frozenset(
            {
                LLM_GATEWAY_MASTER_KEY,
                DEVOPS_CACHE_VALKEY_AUTH_KEY,
                MATTERMOST_DB_AUTH_KEY,
                SEARXNG_SERVER_KEY,
                GRAFANA_RENDERER_AUTH_KEY,
                GRAFANA_SECURITY_KEY,
                # The admin password of the object store (#4750), by its name: the key is new.
                "seaweedfs_admin_password",
            }
        ),
    )


def test_env_name_keys_of_devops_cli_feed_their_options() -> None:
    devops_cli = next(s for s in CLUSTER_SECRETS if s.ref == "devops/devops-cli")
    option_keys = [e.key for e in devops_cli.entries if e.key.startswith("DEVOPS_CLI_")]
    option_of = {variable: key for key, variable in option_env_vars().items()}
    assert {key: option_of.get(key) for key in option_keys} == {
        "DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY": "service.github_app.private_key",
        "DEVOPS_CLI_AI_API_KEY": "ai.api_key",
        "DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS": "service.webhook_secrets",
        "DEVOPS_CLI_FIRECRAWL_API_KEY": "firecrawl.api_key",
        "DEVOPS_CLI_VALKEY_PASSWORD": "valkey.password",
        "DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN": "mattermost.command_token",
        "DEVOPS_CLI_CRAWL4AI_API_TOKEN": "crawl4ai.api_token",
        "DEVOPS_CLI_MCP_STAGE_TOKEN": "mcp.stage_token",
        "DEVOPS_CLI_MCP_IMPLEMENT_TOKEN": "mcp.implement_token",
        "DEVOPS_CLI_QDRANT_API_KEY": "qdrant.api_key",
    }


@pytest.mark.usefixtures("keyring_store")
def test_no_table_secret_is_copied_back_by_sync(process_fake: Any) -> None:
    from devops_cli.k8s.credentials import sync_k8s_credentials
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer(
        ["kubectl", "get", "secret"],
        ProcessAnswer(stdout=json.dumps({"data": {}})),
    )
    sync_k8s_credentials(stack="all", save_to_keyring=False)
    read = [
        f"{call.argv[5]}/{call.argv[3]}"
        for call in process_fake.calls
        if len(call.argv) >= 6 and call.argv[:3] == ("kubectl", "get", "secret")
    ]
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
    readme = (REPO_ROOT / "k8s" / "README.md").read_text(encoding="utf-8")
    rows = [_readme_row(s, e) for s in CLUSTER_SECRETS for e in s.entries]
    assert [row for row in rows if row not in readme] == []
