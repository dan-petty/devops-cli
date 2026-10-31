"""Tests for dry-run request plans and classifications across 17 Valkey and Vault commands.

Issue #2253: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.valkey import (
    valkey_backup,
    valkey_cli,
    valkey_flush,
    valkey_get,
    valkey_info,
    valkey_keys,
    valkey_ping,
    valkey_set,
    valkey_stats,
)
from devops_cli.commands.vault import (
    vault_audit,
    vault_get,
    vault_leases,
    vault_login,
    vault_logout,
    vault_set,
    vault_status,
    vault_sync,
)
from devops_cli.config.constants import (
    CONST_VAULT_PATH_APPROLE_LOGIN,
    CONST_VAULT_PATH_HEALTH,
    CONST_VAULT_PATH_KUBERNETES_LOGIN,
    CONST_VAULT_PATH_LEASE_REVOKE,
    CONST_VAULT_PATH_TOKEN_REVOKE_SELF,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app
from devops_cli.security.vault_http import vault_url
from devops_cli.security.vault_plans import (
    plan_vault_get,
    plan_vault_leases,
    plan_vault_login,
    plan_vault_logout,
    plan_vault_set,
    plan_vault_status,
    plan_vault_sync,
)
from devops_cli.valkey.valkey_plans import (
    plan_valkey_backup,
    plan_valkey_cli,
    plan_valkey_flush,
    plan_valkey_get,
    plan_valkey_info,
    plan_valkey_keys,
    plan_valkey_ping,
    plan_valkey_set,
    plan_valkey_stats,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    ("valkey backup", valkey_backup, ["valkey", "backup", "--dry-run"]),
    ("valkey cli", valkey_cli, ["valkey", "cli", "ping", "--dry-run"]),
    ("valkey flush", valkey_flush, ["valkey", "flush", "--dry-run"]),
    ("valkey get", valkey_get, ["valkey", "get", "mykey", "--dry-run"]),
    ("valkey info", valkey_info, ["valkey", "info", "--dry-run"]),
    ("valkey keys", valkey_keys, ["valkey", "keys", "--dry-run"]),
    ("valkey ping", valkey_ping, ["valkey", "ping", "--dry-run"]),
    ("valkey set", valkey_set, ["valkey", "set", "mykey", "myval", "--dry-run"]),
    ("valkey stats", valkey_stats, ["valkey", "stats", "--dry-run"]),
    ("vault get", vault_get, ["vault", "get", "secret/data/app", "--dry-run"]),
    ("vault leases", vault_leases, ["vault", "leases", "--revoke", "lease-1", "--dry-run"]),
    (
        "vault login",
        vault_login,
        [
            "vault",
            "login",
            "--method",
            "approle",
            "--role-id",
            "r",
            "--secret-id",
            "s",
            "--dry-run",
        ],
    ),
    ("vault logout", vault_logout, ["vault", "logout", "--dry-run"]),
    ("vault set", vault_set, ["vault", "set", "secret/data/app", "KEY=VAL", "--dry-run"]),
    ("vault status", vault_status, ["vault", "status", "--dry-run"]),
    ("vault sync", vault_sync, ["vault", "sync", "secret/data/app", "--dry-run"]),
]

MARK_ONLY_COMMANDS = [
    ("vault audit", vault_audit, ["--dry-run", "vault", "audit"]),
]


@pytest.fixture
def block_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real subprocess, socket, HTTP client, or Valkey execution occurs during dry run."""

    def _fail_process(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected process invocation: {args}, {kwargs}")

    def _fail_socket(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected socket call: {args}, {kwargs}")

    def _fail_http(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Unexpected HTTP request: {args}, {kwargs}")

    monkeypatch.setattr(subprocess, "run", _fail_process)
    monkeypatch.setattr(subprocess, "Popen", _fail_process)
    monkeypatch.setattr(socket.socket, "connect", _fail_socket)
    monkeypatch.setattr(socket, "getaddrinfo", _fail_socket)
    monkeypatch.setattr(httpx2.Client, "send", _fail_http)
    monkeypatch.setattr(httpx2.Client, "request", _fail_http)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", _fail_http)


@pytest.fixture(autouse=True)
def mock_vault_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide dummy Vault environment so dry-run commands do not fail on missing address."""
    monkeypatch.setenv("VAULT_ADDR", "https://vault.example.com:8200")


def test_command_dry_run_class_declarations() -> None:
    """Criterion 1: 16 commands declare request-plan and 1 declares no-external-request."""
    for name, callback, _ in REQUEST_PLAN_COMMANDS:
        cls = get_dry_run_class(callback)
        assert cls == "request-plan", (
            f"Expected '{name}' callback to declare dry_run_class('request-plan'), got '{cls}'"
        )

    for name, callback, _ in MARK_ONLY_COMMANDS:
        cls = get_dry_run_class(callback)
        assert cls == "no-external-request", (
            f"Expected '{name}' callback to declare dry_run_class('no-external-request'), got '{cls}'"
        )


def test_gaps_file_does_not_contain_valkey_or_vault_commands() -> None:
    """Criterion 1: all 17 commands are removed from dry_run_gaps.json."""
    gaps_path = Path("tests/fixtures/dry_run_gaps.json")
    assert gaps_path.exists()
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))

    expected_removed = [
        "valkey backup",
        "valkey cli",
        "valkey flush",
        "valkey get",
        "valkey info",
        "valkey keys",
        "valkey ping",
        "valkey set",
        "valkey stats",
        "vault audit",
        "vault get",
        "vault leases",
        "vault login",
        "vault logout",
        "vault set",
        "vault status",
        "vault sync",
    ]
    remaining = [cmd for cmd in expected_removed if cmd in gaps]
    assert not remaining, f"Commands still present in dry_run_gaps.json: {remaining}"


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_valkey_vault_commands_make_no_external_requests(
    block_external_calls: None,
    name: str,
    callback: Any,
    argv: list[str],
) -> None:
    """Criterion 2 & 3: devops <cmd> --dry-run and devops --dry-run <cmd> make no external calls and print plan."""
    # Test 1: devops <command> --dry-run
    res1 = runner.invoke(app, argv)
    assert res1.exit_code == 0, (
        f"{name} with --dry-run failed with code {res1.exit_code}: {res1.output}"
    )
    assert "1." in res1.output or "Planned" in res1.output or "Plan for" in res1.output, (
        f"{name} output missing request plan: {res1.output}"
    )

    # Test 2: devops --dry-run <command>
    root_argv = ["--dry-run", *[arg for arg in argv if arg != "--dry-run"]]
    res2 = runner.invoke(app, root_argv)
    assert res2.exit_code == 0, (
        f"{name} with root --dry-run failed with code {res2.exit_code}: {res2.output}"
    )
    assert "1." in res2.output or "Planned" in res2.output or "Plan for" in res2.output, (
        f"{name} root dry-run output missing request plan: {res2.output}"
    )


@pytest.mark.parametrize("name,callback,argv", MARK_ONLY_COMMANDS)
def test_mark_only_commands_run_normally_under_dry_run(
    block_external_calls: None,
    name: str,
    callback: Any,
    argv: list[str],
) -> None:
    """Criterion 6: devops --dry-run <cmd> runs normally for mark-only commands without external calls."""
    res = runner.invoke(app, argv)
    assert res.exit_code == 0, f"{name} failed with code {res.exit_code}: {res.output}"


def test_valkey_plans_match_client_operations() -> None:
    """Criterion 5: verify all Valkey plans structure and methods."""
    # 1. ping
    p_ping = plan_valkey_ping()
    assert len(p_ping) == 1
    assert p_ping[0].method == "valkey"
    assert p_ping[0].target == "PING"

    # 2. info
    p_info = plan_valkey_info()
    assert len(p_info) == 1
    assert p_info[0].method == "valkey"
    assert p_info[0].target == "INFO"

    p_info_sec = plan_valkey_info("memory")
    assert p_info_sec[0].target == "INFO memory"

    # 3. stats
    p_stats = plan_valkey_stats()
    assert len(p_stats) == 2
    assert p_stats[0].target == "INFO"
    assert p_stats[1].target == "DBSIZE"

    # 4. keys
    p_keys = plan_valkey_keys("user:*")
    assert len(p_keys) == 1
    assert p_keys[0].target == "KEYS user:*"

    # 5. get
    p_get = plan_valkey_get("session:1")
    assert len(p_get) == 1
    assert p_get[0].target == "GET session:1"

    # 6. set
    p_set = plan_valkey_set("key1", "secretval", ex=60)
    assert len(p_set) == 1
    assert p_set[0].target == "SET key1 <value> EX 60"
    assert "secretval" not in p_set[0].target

    # 7. flush
    p_flush = plan_valkey_flush(all_databases=False)
    assert p_flush[0].target == "FLUSHDB"
    p_flush_all = plan_valkey_flush(all_databases=True)
    assert p_flush_all[0].target == "FLUSHALL"

    # 8. backup
    p_backup = plan_valkey_backup()
    assert p_backup[0].target == "BGSAVE"

    # 9. cli
    p_cli = plan_valkey_cli(["set", "mykey", "val"])
    assert p_cli[0].target == "SET mykey val"
    p_cli_empty = plan_valkey_cli(None)
    assert p_cli_empty[0].target == "<command>"


def test_vault_plans_match_http_requests() -> None:
    """Criterion 5: verify all Vault plans structure and HTTP targets."""
    vaddr = "https://vault.example.com:8200"

    # 1. status
    p_status = plan_vault_status(vaddr)
    assert len(p_status) == 1
    assert p_status[0].method == "GET"
    assert p_status[0].target == vault_url(vaddr, CONST_VAULT_PATH_HEALTH)

    # 2. get
    p_get = plan_vault_get("secret/data/app", vaddr)
    assert len(p_get) == 1
    assert p_get[0].method == "GET"
    assert p_get[0].target == vault_url(vaddr, "secret/data/app")

    # 3. set
    p_set = plan_vault_set("secret/data/app", ["token", "password"], vaddr)
    assert len(p_set) == 1
    assert p_set[0].method == "POST"
    assert p_set[0].target == vault_url(vaddr, "secret/data/app")
    assert p_set[0].stdin is not None
    assert json.loads(p_set[0].stdin) == {"data": {"token": "<value>", "password": "<value>"}}

    # 4. sync
    p_sync = plan_vault_sync("secret/data/app", vaddr)
    assert len(p_sync) == 1
    assert p_sync[0].method == "GET"
    assert p_sync[0].target == vault_url(vaddr, "secret/data/app")

    # 5. login (approle and kubernetes)
    p_login_app = plan_vault_login("approle", role_id="r1", vault_addr=vaddr)
    assert p_login_app[0].method == "POST"
    assert p_login_app[0].target == vault_url(vaddr, CONST_VAULT_PATH_APPROLE_LOGIN)
    assert p_login_app[0].stdin is not None
    assert json.loads(p_login_app[0].stdin) == {"role_id": "r1", "secret_id": "<secret-id>"}

    p_login_k8s = plan_vault_login("kubernetes", role="role1", vault_addr=vaddr)
    assert p_login_k8s[0].method == "POST"
    assert p_login_k8s[0].target == vault_url(vaddr, CONST_VAULT_PATH_KUBERNETES_LOGIN)
    assert p_login_k8s[0].stdin is not None
    assert json.loads(p_login_k8s[0].stdin) == {"role": "role1", "jwt": "<jwt>"}

    # 6. logout
    p_logout = plan_vault_logout(vaddr)
    assert len(p_logout) == 1
    assert p_logout[0].method == "POST"
    assert p_logout[0].target == vault_url(vaddr, CONST_VAULT_PATH_TOKEN_REVOKE_SELF)

    # 7. leases
    p_leases = plan_vault_leases("lease-abc", vaddr)
    assert len(p_leases) == 1
    assert p_leases[0].method == "POST"
    assert p_leases[0].target == vault_url(vaddr, CONST_VAULT_PATH_LEASE_REVOKE)
    assert p_leases[0].stdin is not None
    assert json.loads(p_leases[0].stdin) == {"lease_id": "lease-abc"}
