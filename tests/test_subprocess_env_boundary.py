"""Comprehensive unit tests for subprocess environment isolation and credential boundary."""

from __future__ import annotations

import json
import sys

import pytest

from devops_cli.core.process import (
    DEFAULT_ALLOWED_ENV_PREFIXES,
    DEFAULT_ALLOWED_ENV_VARS,
    DEFAULT_DENIED_ENV_PATTERNS,
    build_subprocess_env,
    run_json_subprocess,
    run_subprocess,
    run_subprocess_async,
)


def test_build_subprocess_env_allowlist_and_denylist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify build_subprocess_env preserves allowlisted vars and strips secrets from ambient environment."""
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("HOME", "/home/testuser")
    monkeypatch.setenv("USER", "testuser")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("VIRTUAL_ENV", "/app/.venv")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "/tmp/.data")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "devops-cli")

    # Sensitive credentials that MUST be stripped
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret12345")
    monkeypatch.setenv("GH_TOKEN", "ghp_ambienttoken")
    monkeypatch.setenv("DEVOPS_CLI_GITHUB_TOKEN", "ghp_devopstoken")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-supersecretkey")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    monkeypatch.setenv("VAULT_TOKEN", "hvs.secretvaulttoken")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("DATABASE_PASSWORD", "SuperSecretDbPassword123!")
    monkeypatch.setenv("API_CLIENT_SECRET", "super-secret-client")
    monkeypatch.setenv("UNKNOWN_UNTRUSTED_ENV", "random_leakage")

    env = build_subprocess_env()

    # Allowed safe variables must be retained
    assert env["PATH"] == "/usr/bin:/bin"
    assert env["HOME"] == "/home/testuser"
    assert env["USER"] == "testuser"
    assert env["TERM"] == "xterm-256color"
    assert env["VIRTUAL_ENV"] == "/app/.venv"
    assert env["DEVOPS_CLI_DATA_DIR"] == "/tmp/.data"
    assert env["OTEL_SERVICE_NAME"] == "devops-cli"

    # Ambient credentials must be stripped
    assert "GITHUB_TOKEN" not in env
    assert "GH_TOKEN" not in env
    assert "DEVOPS_CLI_GITHUB_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert "VAULT_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "DATABASE_PASSWORD" not in env
    assert "API_CLIENT_SECRET" not in env
    assert "UNKNOWN_UNTRUSTED_ENV" not in env


def test_build_subprocess_env_explicit_override() -> None:
    """Verify caller-provided explicit env vars are forwarded alongside sanitized base environment."""
    explicit = {
        "CUSTOM_APP_FLAG": "enabled",
        "EXPLICIT_FORWARDED_TOKEN": "token-for-specific-tool",
    }
    env = build_subprocess_env(env=explicit)

    assert env["CUSTOM_APP_FLAG"] == "enabled"
    assert env["EXPLICIT_FORWARDED_TOKEN"] == "token-for-specific-tool"
    assert "PATH" in env
    assert "HOME" in env


def test_build_subprocess_env_disable_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify isolate_env=False preserves raw un-sanitized environment."""
    monkeypatch.setenv("AMBIENT_UNTRUSTED_KEY", "raw_value")
    monkeypatch.setenv("TEST_SECRET_TOKEN", "preserve_raw")

    env = build_subprocess_env(isolate_env=False)
    assert env.get("AMBIENT_UNTRUSTED_KEY") == "raw_value"
    assert env.get("TEST_SECRET_TOKEN") == "preserve_raw"


def test_build_subprocess_env_extra_allowed_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify extra_allowed_keys preserves specific variables from environment."""
    monkeypatch.setenv("SPECIAL_BUILD_TARGET", "linux-amd64")
    monkeypatch.setenv("UNAPPROVED_VAR", "blocked")

    env = build_subprocess_env(extra_allowed_keys={"SPECIAL_BUILD_TARGET"})
    assert env.get("SPECIAL_BUILD_TARGET") == "linux-amd64"
    assert "UNAPPROVED_VAR" not in env


def test_run_subprocess_isolates_real_child_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify real child process executed via run_subprocess does not inherit ambient secrets."""
    monkeypatch.setenv("GITHUB_TOKEN", "leak_test_github_token")
    monkeypatch.setenv("OPENAI_API_KEY", "leak_test_openai_key")
    monkeypatch.setenv("MY_CUSTOM_SECRET", "leak_test_custom_secret")
    monkeypatch.setenv("ALLOWLISTED_TEST_MARKER", "should_be_stripped_if_not_in_allowlist")

    cmd = [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"]
    proc = run_subprocess(cmd)
    assert proc.returncode == 0

    child_env = json.loads(proc.stdout)
    assert "PATH" in child_env
    assert "HOME" in child_env
    assert "GITHUB_TOKEN" not in child_env
    assert "OPENAI_API_KEY" not in child_env
    assert "MY_CUSTOM_SECRET" not in child_env
    assert "ALLOWLISTED_TEST_MARKER" not in child_env


def test_run_subprocess_forwards_explicit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_subprocess explicitly forwards caller-provided env vars."""
    monkeypatch.setenv("AMBIENT_LEAK_CHECK", "ambient_value_to_drop")

    cmd = [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"]
    proc = run_subprocess(cmd, env={"SPECIFIC_TOOL_PARAM": "passed_cleanly"})
    assert proc.returncode == 0

    child_env = json.loads(proc.stdout)
    assert child_env.get("SPECIFIC_TOOL_PARAM") == "passed_cleanly"
    assert "AMBIENT_LEAK_CHECK" not in child_env


@pytest.mark.anyio
async def test_run_subprocess_async_isolates_child_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_subprocess_async also enforces environment isolation."""
    monkeypatch.setenv("VAULT_TOKEN", "hvs.async_leak_test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws_async_leak_test")

    cmd = [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"]
    proc = await run_subprocess_async(cmd)
    assert proc.returncode == 0

    child_env = json.loads(proc.stdout)
    assert "PATH" in child_env
    assert "VAULT_TOKEN" not in child_env
    assert "AWS_SECRET_ACCESS_KEY" not in child_env


def test_run_json_subprocess_inherits_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_json_subprocess benefits from the same environment isolation."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/leak")

    cmd = [sys.executable, "-c", "import os, json; print(json.dumps({'env': dict(os.environ)}))"]
    result = run_json_subprocess(cmd)
    child_env = result["env"]

    assert "PATH" in child_env
    assert "SLACK_WEBHOOK_URL" not in child_env


def test_constants_integrity() -> None:
    """Verify allowed and denied constants are immutable and contain essential markers."""
    assert isinstance(DEFAULT_ALLOWED_ENV_VARS, frozenset)
    assert "PATH" in DEFAULT_ALLOWED_ENV_VARS
    assert "HOME" in DEFAULT_ALLOWED_ENV_VARS
    assert "VIRTUAL_ENV" in DEFAULT_ALLOWED_ENV_VARS
    assert "DEVOPS_CLI_" in DEFAULT_ALLOWED_ENV_PREFIXES
    assert "*TOKEN*" in DEFAULT_DENIED_ENV_PATTERNS
    assert "*SECRET*" in DEFAULT_DENIED_ENV_PATTERNS
    assert "*KEY*" in DEFAULT_DENIED_ENV_PATTERNS
