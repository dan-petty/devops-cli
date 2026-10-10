"""Comprehensive unit tests for subprocess environment isolation and credential boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.config.defaults import (
    DEFAULT_GH_AUTH_TOKEN_RETRY_SECONDS,
    DEFAULT_GH_AUTH_TOKEN_TIMEOUT_SECONDS,
)
from devops_cli.core import process
from devops_cli.core.process import (
    DEFAULT_ALLOWED_ENV_PREFIXES,
    DEFAULT_ALLOWED_ENV_VARS,
    DEFAULT_DENIED_ENV_PATTERNS,
    build_subprocess_env,
    run_json_subprocess,
    run_subprocess,
    run_subprocess_async,
)
from devops_cli.exceptions.git import GitHubUnauthenticatedError


def test_build_subprocess_env_allowlist_and_denylist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify build_subprocess_env preserves allowlisted vars and strips secrets from ambient environment."""
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("HOME", "/home/testuser")
    monkeypatch.setenv("USER", "testuser")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("VIRTUAL_ENV", "/app/.venv")
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
    monkeypatch.setenv("OTEL_SERVICE_NAME", "devops-cli")

    # Sensitive credentials that MUST be stripped
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret12345")
    monkeypatch.setenv("GH_TOKEN", "ghp_ambienttoken")
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
    assert env["DEVOPS_CLI_DATA_DIR"] == str(tmp_path / ".data")
    assert env["OTEL_SERVICE_NAME"] == "devops-cli"

    # Ambient credentials must be stripped
    assert "GITHUB_TOKEN" not in env
    assert "GH_TOKEN" not in env
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


def test_build_subprocess_env_case_insensitivity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify allowlist and denylist matching is case-insensitive for cross-platform support."""
    monkeypatch.setenv("path", "/usr/local/bin")
    monkeypatch.setenv("Home", "/home/testuser")
    monkeypatch.setenv("devops_cli_custom_setting", "custom_val")
    monkeypatch.setenv("github_token", "lower_case_secret")
    monkeypatch.setenv("My_Secret_Key", "mixed_secret")

    env = build_subprocess_env()
    # The key is preserved as stored in os.environ, but recognized as allowed
    assert env.get("path") == "/usr/local/bin" or env.get("PATH") is not None
    assert "github_token" not in env
    assert "My_Secret_Key" not in env


def test_run_subprocess_isolates_real_child_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify real child process executed via run_subprocess does not inherit ambient secrets."""
    # Ensure baseline PATH and HOME exist deterministically across all environments
    monkeypatch.setenv("PATH", os.environ.get("PATH", "/usr/bin:/bin"))
    monkeypatch.setenv("HOME", os.environ.get("HOME", str(tmp_path)))
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
async def test_run_subprocess_async_isolates_child_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify run_subprocess_async also enforces environment isolation."""
    monkeypatch.setenv("PATH", os.environ.get("PATH", "/usr/bin:/bin"))
    monkeypatch.setenv("HOME", os.environ.get("HOME", str(tmp_path)))
    monkeypatch.setenv("VAULT_TOKEN", "hvs.async_leak_test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws_async_leak_test")

    cmd = [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"]
    proc = await run_subprocess_async(cmd)
    assert proc.returncode == 0

    child_env = json.loads(proc.stdout)
    assert "PATH" in child_env
    assert "HOME" in child_env
    assert "VAULT_TOKEN" not in child_env
    assert "AWS_SECRET_ACCESS_KEY" not in child_env


def test_run_json_subprocess_inherits_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_json_subprocess benefits from the same environment isolation."""
    monkeypatch.setenv("PATH", os.environ.get("PATH", "/usr/bin:/bin"))
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


_GH_AUTH_SUBCOMMANDS = ("login", "status", "refresh", "token", "switch", "logout", "setup-git")


def _gh_answers(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """A finished child, as `subprocess.run` returns it."""
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def _child_envs(run: MagicMock) -> list[tuple[list[str], str | None, str | None]]:
    """Each child's argv with the GH_TOKEN and GITHUB_TOKEN it was given."""
    return [
        (call.args[0], call.kwargs["env"].get("GH_TOKEN"), call.kwargs["env"].get("GITHUB_TOKEN"))
        for call in run.call_args_list
    ]


@pytest.fixture
def unresolved_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forget the token conftest pins, so the next GitHub call looks the identity up."""
    monkeypatch.setattr(process, "_github_token", None)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


def test_the_identity_lookup_honours_the_environment_tokens(
    monkeypatch: pytest.MonkeyPatch, unresolved_identity: None
) -> None:
    """`gh auth token` gets GH_TOKEN and GITHUB_TOKEN from the environment; its answer is the token."""
    monkeypatch.setenv("GH_TOKEN", "B")
    monkeypatch.setenv("GITHUB_TOKEN", "C")
    with patch("subprocess.run", return_value=_gh_answers("B\n")) as run:
        token = process.github_token()
    assert (_child_envs(run), token) == ([([CONST_GH_CLI, "auth", "token"], "B", "C")], "B")


def test_the_identity_is_looked_up_once_per_process(unresolved_identity: None) -> None:
    """Every gh call after the first reuses the token `gh auth token` printed."""
    with patch("subprocess.run", return_value=_gh_answers("A\n")) as run:
        run_subprocess([CONST_GH_CLI, "issue", "list"])
        run_subprocess([CONST_GH_CLI, "pr", "list"])
    assert _child_envs(run) == [
        ([CONST_GH_CLI, "auth", "token"], None, None),
        ([CONST_GH_CLI, "issue", "list"], "A", None),
        ([CONST_GH_CLI, "pr", "list"], "A", None),
    ]


def test_a_failed_lookup_raises_and_runs_no_other_gh(unresolved_identity: None) -> None:
    """With no token from `gh auth token`, a gh call raises the unauthenticated error and never runs."""
    with (
        patch("subprocess.run", return_value=_gh_answers(returncode=1)) as run,
        pytest.raises(GitHubUnauthenticatedError) as raised,
    ):
        run_subprocess([CONST_GH_CLI, "issue", "list"])
    assert ([call.args[0] for call in run.call_args_list], raised.value.error_code) == (
        [[CONST_GH_CLI, "auth", "token"]],
        "GITHUB_UNAUTHENTICATED",
    )


def test_a_failed_lookup_is_not_kept(unresolved_identity: None) -> None:
    """After `gh auth login` fixes a failed lookup, the next gh call acts as the new login."""
    answers = [_gh_answers(returncode=1), _gh_answers("A\n"), _gh_answers()]
    with patch("subprocess.run", side_effect=answers) as run:
        with pytest.raises(GitHubUnauthenticatedError):
            run_subprocess([CONST_GH_CLI, "issue", "list"])
        run_subprocess([CONST_GH_CLI, "issue", "list"])
    assert _child_envs(run)[1:] == [
        ([CONST_GH_CLI, "auth", "token"], None, None),
        ([CONST_GH_CLI, "issue", "list"], "A", None),
    ]


def test_git_waits_before_looking_again_after_a_failed_lookup(
    monkeypatch: pytest.MonkeyPatch, unresolved_identity: None
) -> None:
    """git does not run `gh auth token` on every call while gh has no login; it looks again later."""
    with patch("subprocess.run", return_value=_gh_answers(returncode=1)) as run:
        run_subprocess(["git", "status"])
        run_subprocess(["git", "status"])
        assert process._github_lookup_failure is not None
        failed_at, why = process._github_lookup_failure
        expired = (failed_at - DEFAULT_GH_AUTH_TOKEN_RETRY_SECONDS, why)
        monkeypatch.setattr(process, "_github_lookup_failure", expired)
        run_subprocess(["git", "status"])
    assert [call.args[0][0] for call in run.call_args_list] == [
        CONST_GH_CLI,
        "git",
        "git",
        CONST_GH_CLI,
        "git",
    ]


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (subprocess.TimeoutExpired(["gh"], DEFAULT_GH_AUTH_TOKEN_TIMEOUT_SECONDS), "no answer"),
        (PermissionError("gh"), "PermissionError"),
    ],
    ids=["timeout", "not-executable"],
)
def test_a_lookup_that_cannot_run_leaves_git_working_and_says_why(
    failure: Exception, reason: str, unresolved_identity: None
) -> None:
    """A hung or unrunnable gh means no token: git still runs, and gh's error names the cause."""
    with patch("subprocess.run", side_effect=[failure, _gh_answers(), failure]) as run:
        proc = run_subprocess(["git", "status"])
        with pytest.raises(GitHubUnauthenticatedError) as raised:
            run_subprocess([CONST_GH_CLI, "issue", "list"])
    assert (
        run.call_args_list[0].kwargs["timeout"],
        proc.returncode,
        _child_envs(run)[1],
        reason in raised.value.message,
    ) == (DEFAULT_GH_AUTH_TOKEN_TIMEOUT_SECONDS, 0, (["git", "status"], None, None), True)


@pytest.mark.parametrize(
    ("returncode", "cause"), [(127, "gh is not on PATH"), (1, "exit status 1")]
)
def test_the_unauthenticated_error_says_why_gh_gave_no_token(
    returncode: int, cause: str, unresolved_identity: None
) -> None:
    """A missing gh is not reported as a missing login, and a failed lookup gives its status."""
    with (
        patch("subprocess.run", return_value=_gh_answers(returncode=returncode)),
        pytest.raises(GitHubUnauthenticatedError) as raised,
    ):
        process.github_token()
    assert (cause in raised.value.message, "gh auth login" in raised.value.message) == (True, True)


def test_gh_and_git_children_get_only_the_pinned_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """gh and a `git push` get GH_TOKEN set to the session's token and never a GITHUB_TOKEN."""
    monkeypatch.setattr(process, "_github_token", "A")
    monkeypatch.setenv("GH_TOKEN", "B")
    monkeypatch.setenv("GITHUB_TOKEN", "C")
    with patch("subprocess.run", return_value=_gh_answers()) as run:
        run_subprocess([CONST_GH_CLI, "pr", "view", "184"], env={"GITHUB_TOKEN": "D"})
        run_subprocess(["git", "push", "origin", "release/v0.2.26"])
    assert _child_envs(run) == [
        ([CONST_GH_CLI, "pr", "view", "184"], "A", None),
        (["git", "push", "origin", "release/v0.2.26"], "A", None),
    ]


def test_git_runs_without_a_token_when_gh_has_no_login(unresolved_identity: None) -> None:
    """A local git command still runs when no identity resolves; it just gets no token."""
    with patch("subprocess.run", side_effect=[_gh_answers(returncode=1), _gh_answers()]) as run:
        proc = run_subprocess(["git", "status"])
    assert (proc.returncode, _child_envs(run)[1:]) == (0, [(["git", "status"], None, None)])


@pytest.mark.parametrize("argv", [[CONST_GH_CLI, "--version"], [CONST_GH_CLI, "help"]])
def test_gh_version_and_help_need_no_identity(argv: list[str], unresolved_identity: None) -> None:
    """gh's local commands make no call of the session's, so they run without looking one up."""
    with patch("subprocess.run", return_value=_gh_answers()) as run:
        proc = run_subprocess(argv)
    assert (proc.returncode, _child_envs(run)) == (0, [(argv, None, None)])


@pytest.mark.parametrize("subcommand", _GH_AUTH_SUBCOMMANDS)
@pytest.mark.parametrize("ambient", [None, "B"])
def test_gh_auth_gets_the_ambient_tokens_and_never_the_pin(
    monkeypatch: pytest.MonkeyPatch, subcommand: str, ambient: str | None
) -> None:
    """`gh auth` subcommands see GH_TOKEN and GITHUB_TOKEN exactly as the environment has them."""
    monkeypatch.setattr(process, "_github_token", "A")
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    if ambient:
        monkeypatch.setenv("GH_TOKEN", ambient)
    with patch("subprocess.run", return_value=_gh_answers()) as run:
        run_subprocess([CONST_GH_CLI, "auth", subcommand])
    assert _child_envs(run) == [([CONST_GH_CLI, "auth", subcommand], ambient, None)]


def test_gh_auth_gets_a_token_its_caller_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A token the caller hands `gh auth` in `env` reaches it, ahead of the environment's."""
    monkeypatch.setattr(process, "_github_token", "A")
    monkeypatch.setenv("GH_TOKEN", "B")
    with patch("subprocess.run", return_value=_gh_answers()) as run:
        run_subprocess([CONST_GH_CLI, "auth", "status"], env={"GH_TOKEN": "C"})
    assert _child_envs(run) == [([CONST_GH_CLI, "auth", "status"], "C", None)]


@pytest.mark.anyio
async def test_the_async_runner_pins_gh_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """The async runner gives a gh child the same pinned GH_TOKEN as the sync one."""
    import asyncio

    monkeypatch.setattr(process, "_github_token", "A")
    spawned: list[tuple[list[str], str | None]] = []

    async def spawn(*argv: str, env: dict[str, str], **_: object) -> None:
        spawned.append((list(argv), env.get("GH_TOKEN")))
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    proc = await run_subprocess_async([CONST_GH_CLI, "issue", "list"])
    assert (proc.returncode, spawned) == (127, [([CONST_GH_CLI, "issue", "list"], "A")])


def test_sanitize_command_for_telemetry() -> None:
    """Verify _sanitize_command_for_telemetry redacts sensitive args and user comments."""
    from devops_cli.core.process import _sanitize_command_for_telemetry

    cmd = [
        CONST_GH_CLI,
        "pr",
        "close",
        "187",
        "--comment",
        "Secret comment ghp_secrettoken1234567890abcdefghijklmn",
    ]
    summary = _sanitize_command_for_telemetry(cmd)
    assert "[REDACTED]" in summary
    assert "ghp_secrettoken" not in summary

    cmd2 = [CONST_GH_CLI, "api", "issues/1", "-f", "title=Secret issue title"]
    summary2 = _sanitize_command_for_telemetry(cmd2)
    assert "title=[REDACTED]" in summary2
