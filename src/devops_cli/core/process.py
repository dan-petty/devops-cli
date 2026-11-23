"""Subprocess execution utility with consolidated timeouts, error handling, and dry-run support."""

from __future__ import annotations

import asyncio
import contextlib
import fnmatch
import json
import logging
import os
import signal
import subprocess
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from devops_cli.config.constants import (
    CONST_CODE_LOADING_ENV_PATTERNS,
    CONST_DATA_EGRESS_ENV_VARS,
    CONST_EXIT_COMMAND_NOT_FOUND,
    CONST_GH_AUTH_ENV_VAR,
    CONST_GH_AUTH_SUBCOMMAND,
    CONST_GH_CLI,
    CONST_GH_LOGIN_ENV_VARS,
    CONST_GH_NON_API_COMMANDS,
    CONST_GH_TOKEN_ENV_VARS,
    CONST_GIT_ACCEPTED_ENV,
    CONST_GIT_CLI,
    CONST_GIT_CONFIG_ENV_PATTERNS,
    CONST_GIT_ISOLATED_CONFIG_ENV,
    CONST_GIT_LOCAL_ONLY_ENV,
    CONST_GITHUB_APP_PRIVATE_KEY_ENV,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_AUTH_TOKEN_ATTEMPTS,
    DEFAULT_GH_AUTH_TOKEN_TIMEOUT_SECONDS,
    DEFAULT_GITHUB_APP_TOKEN_RENEW_SECONDS,
    DEFAULT_SHELL_STOP_GRACE_SECONDS,
    DEFAULT_SHELL_STOP_POLL_SECONDS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.git import (
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.exceptions.tools import SubprocessError
from devops_cli.telemetry.instruments import SUBPROCESS_DURATION, emit
from devops_cli.telemetry.tracer import get_tracer, trace_span

logger = logging.getLogger(__name__)

# How long a child of its own session has to end after the SIGINT of a Ctrl+C, before its group
# gets SIGKILL: the wait of `subprocess.run` for a child after a Ctrl+C (#6691).
_SIGINT_WAIT_SECONDS = 0.25

_QUIET_SUBPROCESS_ARGS = frozenset(
    {
        "rev-parse",
        "symbolic-ref",
        "for-each-ref",
        "diff",
        "cat-file",
        "tag",
        "remote",
        "status",
    }
)

DEFAULT_ALLOWED_ENV_VARS: frozenset[str] = frozenset(
    {
        "PATH",
        "PATHEXT",
        "COMSPEC",
        "SYSTEMROOT",
        "WINDIR",
        "SYSTEMDRIVE",
        "HOME",
        "USER",
        "LOGNAME",
        "HOMEDRIVE",
        "HOMEPATH",
        "USERPROFILE",
        "TMPDIR",
        "TMP",
        "TEMP",
        "TERM",
        "COLORTERM",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LC_MESSAGES",
        "LC_COLLATE",
        "TZ",
        "PYTHONUNBUFFERED",
        "PYTHONDONTWRITEBYTECODE",
        "TRACEPARENT",
        "TRACESTATE",
        "KUBECONFIG",
        "DOCKER_HOST",
        "DOCKER_CONFIG",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "CI",
        # A number only. `pytest-xdist` counts the CPUs of the node, not of the pod, so a child that
        # runs `pytest` (the gate of `devops ci`) must keep the bound that the runner pod sets
        # (#2806).
        "PYTEST_XDIST_AUTO_NUM_WORKERS",
        "XDG_RUNTIME_DIR",
        "DBUS_SESSION_BUS_ADDRESS",
    }
)

# uv's own settings reach a child `uv run`, so it keeps the interpreter, cache and Python install
# directory the environment was built with instead of rebuilding it (#1735); a uv credential such
# as UV_PUBLISH_TOKEN still matches a denied pattern. The prefix lets UV_PYTHON and
# UV_PYTHON_INSTALL_DIR through from the environment of the person, although a caller may not set
# them: the gate on a CI runner needs both (#2673).
DEFAULT_ALLOWED_ENV_PREFIXES: tuple[str, ...] = (
    "DEVOPS_CLI_",
    "OTEL_",
    "W3C_",
    "LC_",
    "UV_",
)

DEFAULT_DENIED_ENV_PATTERNS: tuple[str, ...] = (
    "*TOKEN*",
    "*SECRET*",
    "*KEY*",
    "*PASSWORD*",
    "*CREDENTIAL*",
    "*AUTH*",
    "*PRIVATE*",
    # Names the environment whose bin/python uv starts. No file of the repository sets it, so the
    # prefix of DEFAULT_ALLOWED_ENV_PREFIXES does not pass it (#2673).
    "UV_PROJECT_ENVIRONMENT",
    # Name a directory of tools that uv starts, and a file of keys that uv puts into the program of
    # `uv run`. No file of the repository sets either key (#2750).
    "UV_TOOL_DIR",
    "UV_ENV_FILE",
)


def _is_env_var_denied(
    key: str, denied_patterns: tuple[str, ...] = DEFAULT_DENIED_ENV_PATTERNS
) -> bool:
    """Whether the upper-case key matches one of `denied_patterns`, by default the credentials."""
    upper_key = key.upper()
    return any(fnmatch.fnmatchcase(upper_key, pat) for pat in denied_patterns)


def _is_env_override_refused(key: str, value: str) -> bool:
    """Whether a caller may not set `key` to `value`: a pattern of `CONST_CODE_LOADING_ENV_PATTERNS`
    matches it, and it is not a git key that `CONST_GIT_ACCEPTED_ENV` names, nor a key of
    `CONST_GIT_ISOLATED_CONFIG_ENV` or `CONST_GIT_LOCAL_ONLY_ENV` with its one value."""
    if value in (CONST_GIT_ISOLATED_CONFIG_ENV.get(key), CONST_GIT_LOCAL_ONLY_ENV.get(key)):
        return False
    return (
        key.upper() not in CONST_GIT_ACCEPTED_ENV
        and _is_env_var_denied(key, CONST_CODE_LOADING_ENV_PATTERNS)
    ) or key.upper() in CONST_DATA_EGRESS_ENV_VARS


def _is_env_var_allowed(
    key: str,
    *,
    allowed_vars: frozenset[str] = DEFAULT_ALLOWED_ENV_VARS,
    allowed_prefixes: tuple[str, ...] = DEFAULT_ALLOWED_ENV_PREFIXES,
    extra_allowed: frozenset[str] | set[str] | None = None,
) -> bool:
    """Predicate determining if an environment variable key is safe to pass to child processes."""
    upper_key = key.upper()
    if upper_key in allowed_vars:
        return True
    if extra_allowed and (key in extra_allowed or upper_key in extra_allowed):
        return True
    return any(upper_key.startswith(p.upper()) for p in allowed_prefixes)


def build_subprocess_env(
    env: dict[str, str] | None = None,
    *,
    isolate_env: bool = True,
    extra_allowed_keys: set[str] | list[str] | frozenset[str] | None = None,
) -> dict[str, str]:
    """Build a sanitized subprocess environment isolating ambient credentials and secrets.

    When isolate_env is True (default), ambient environment variables are filtered
    against DEFAULT_ALLOWED_ENV_VARS and DEFAULT_ALLOWED_ENV_PREFIXES, while stripping
    any variables matching DEFAULT_DENIED_ENV_PATTERNS. Caller-provided env overrides
    are merged on top of the sanitized base, preserving explicit caller intent.

    The git configuration keys of the environment (`CONST_GIT_CONFIG_ENV_PATTERNS`) reach each
    child of a person, as a shell gives them, so git reads the credential helper that the
    devcontainer sets. A process that acts as the GitHub App gives them to no child, also with
    isolation off: its image sets the helper in `/etc/gitconfig`, and the shell of the agent
    runs in its own container, which holds no App key (#3700, #6653). A caller cannot set them.
    """
    if not isolate_env:
        base_env = dict(os.environ)
    else:
        extra_set = (
            frozenset(extra_allowed_keys) | frozenset(k.upper() for k in extra_allowed_keys)
            if extra_allowed_keys
            else frozenset()
        )
        base_env = {
            k: v
            for k, v in os.environ.items()
            if not _is_env_var_denied(k) and _is_env_var_allowed(k, extra_allowed=extra_set)
        }
    if env:
        from devops_cli.exceptions.security import SecurityError

        for k, v in env.items():
            if _is_env_override_refused(k, str(v)):
                raise SecurityError(f"Prohibited dangerous environment variable override: '{k}'")
            if "\x00" in k or "\x00" in str(v):
                raise SecurityError(f"Null byte in environment variable prohibited: '{k}'")
            base_env[k] = str(v)
    git_config = {
        key: value
        for key, value in os.environ.items()
        if any(fnmatch.fnmatchcase(key, pattern) for pattern in CONST_GIT_CONFIG_ENV_PATTERNS)
    }
    if acts_as_github_app():
        for key in git_config:
            base_env.pop(key, None)
    elif isolate_env:
        base_env.update(git_config)
    return base_env


def _subprocess_span_attributes(
    cmd: list[str], bin_name: str, cwd: Path | None, timeout: float
) -> dict[str, Any]:
    """The attributes a subprocess span starts with: the program and the number of its arguments.

    The arguments go in `process.command_args` only when `telemetry.capture_command_args` turns
    them on, each one through the secret mask. The OpenTelemetry semantic conventions make
    `process.command_args` and `process.command_line` Opt-In: a command such as `devops uv run`
    or `devops gh api` passes the arguments of a person on, and an argument can be a credential
    that the mask does not find (#2025). No attribute holds `process.command_line`, which the
    conventions say not to assemble from the arguments.
    """
    attrs: dict[str, Any] = {
        "subprocess.bin": bin_name,
        "subprocess.args_count": len(cmd),
        "subprocess.cwd": str(cwd or ""),
        "subprocess.timeout_seconds": timeout,
        "process.executable.name": bin_name,
        "process.args_count": len(cmd),
        "process.working_directory": str(cwd or ""),
    }
    if get_tracer().capture_command_args:
        from devops_cli.security.sanitizer import mask_secrets

        attrs["process.command_args"] = [mask_secrets(arg) for arg in cmd]
    return attrs


def _validate_subprocess_cwd(cwd: Path | str | None) -> None:
    """Validate that subprocess working directory does not violate traversal or system path security."""
    if cwd is None:
        return
    from devops_cli.core.paths import (
        is_forbidden_system_path,
        validate_no_path_traversal,
    )
    from devops_cli.exceptions.security import SecurityError

    validate_no_path_traversal(str(cwd), label="subprocess cwd")
    resolved_cwd = Path(cwd).resolve()
    if is_forbidden_system_path(resolved_cwd):
        raise SecurityError(f"Subprocess cwd cannot reside in forbidden system directory: '{cwd}'.")


# The process's one GitHub identity (#767): None until a lookup finds a token, then that token.
# gh's token is kept for the life of the process. A GitHub App's installation token keeps when it
# expires, and the next call after it comes within DEFAULT_GITHUB_APP_TOKEN_RENEW_SECONDS of that
# time mints a new one (ADR 0015). A lookup that finds none is not kept, so the next gh call looks
# again (#6671). A git child of a person keeps that failed lookup (`_git_lookup_failed`), so a
# process with no login starts no `gh auth token` before each git call (#6691).
_github_token: str | None = None
_github_token_expires_at: datetime | None = None
_git_lookup_failed = False
_GITHUB_TOKEN_LOCK = threading.Lock()


@dataclass(frozen=True)
class GitHubIdentity:
    """Who the process's GitHub calls act as.

    `key` names the identity's quota ledger and session: gh's token itself, or the App's
    installation, so every token of one installation shares them. It is never shown. `login` is
    the identity's login when the identity names it without a request: the App's bot login.
    `renews` is True for the App, whose token the process mints again before it expires.
    """

    key: str = field(repr=False)
    login: str | None = None
    renews: bool = False

    def token(self) -> str:
        """The token to send as this identity: the App's current installation token, minted again
        before it expires, or gh's token, which is the identity's own key."""
        return github_token() if self.renews else self.key


def acts_as_github_app() -> bool:
    """Whether the process acts as the GitHub App: its environment holds the App's private key.

    Secret `devops/devops-cli` gives the key to the cluster's pods. A workstation keeps the key
    in the OS keyring only, for `devops k8s push-secrets`, so it keeps the gh login of its person,
    as gh lets GH_TOKEN take precedence over a stored login.
    """
    return bool(os.environ.get(CONST_GITHUB_APP_PRIVATE_KEY_ENV, "").strip())


def github_identity() -> GitHubIdentity:
    """The process's GitHub identity: the App's installation and bot login when the process acts
    as the App, which mints no token; otherwise gh's token, looked up as `github_token` does."""
    if acts_as_github_app():
        from devops_cli.github.app_installation import configured_app

        app = configured_app()
        return GitHubIdentity(key=app.ledger_key, login=app.bot_login, renews=True)
    return GitHubIdentity(key=github_token())


def _lookup_github_token() -> tuple[str, str]:
    """Run `gh auth token`; it applies GH_TOKEN, then GITHUB_TOKEN, then gh's stored login.

    The child is a `gh auth` call, so it gets the ambient tokens and never a pinned one. A timeout
    tries again, because a loaded host can start gh slower than the limit (#4940). Returns the
    token, or "" and the unauthenticated error's message when there is none.
    """
    from devops_cli.lang import ERRORS

    timeout = DEFAULT_GH_AUTH_TOKEN_TIMEOUT_SECONDS
    attempts = max(1, DEFAULT_GH_AUTH_TOKEN_ATTEMPTS)
    for attempt in range(attempts):
        try:
            proc = run_subprocess(
                [CONST_GH_CLI, CONST_GH_AUTH_SUBCOMMAND, "token"],
                check=False,
                quiet=True,
                timeout=timeout,
                extra_allowed_env=CONST_GH_LOGIN_ENV_VARS,
            )
        except subprocess.TimeoutExpired:
            if attempt + 1 < attempts:
                continue
            reason = ERRORS.git.github_token_lookup_timed_out.format(seconds=timeout)
            return "", ERRORS.git.github_token_lookup_failed.format(reason=reason)
        except OSError as err:
            return "", ERRORS.git.github_token_lookup_failed.format(reason=type(err).__name__)
        token = proc.stdout.strip() if proc.returncode == 0 else ""
        if token:
            return token, ""
        if proc.returncode == CONST_EXIT_COMMAND_NOT_FOUND:
            reason = ERRORS.git.github_token_lookup_not_found
            return "", ERRORS.git.github_token_lookup_failed.format(reason=reason)
        return "", ERRORS.git.github_unauthenticated.format(status=proc.returncode)
    reason = ERRORS.git.github_token_lookup_timed_out.format(seconds=timeout)
    return "", ERRORS.git.github_token_lookup_failed.format(reason=reason)


def _lookup_session_token() -> tuple[str, str, datetime | None]:
    """A new token for the session, the reason when there is none, and when the token expires.

    The App mints an installation token; otherwise `gh auth token` prints gh's token, which does
    not expire within the process.
    """
    if acts_as_github_app():
        from devops_cli.github.app_installation import mint_installation_token

        return mint_installation_token()
    token, why = _lookup_github_token()
    return token, why, None


def _renewal_due(expires_at: datetime | None) -> bool:
    """Whether a token that expires at `expires_at` is close enough to it to mint a new one."""
    if expires_at is None:
        return False
    left = expires_at - datetime.now(UTC)
    return left <= timedelta(seconds=DEFAULT_GITHUB_APP_TOKEN_RENEW_SECONDS)


def _kept_token() -> str:
    """The kept installation token while it has not expired, else "". The caller holds
    `_GITHUB_TOKEN_LOCK`."""
    expires_at = _github_token_expires_at
    if _github_token and expires_at is not None and expires_at > datetime.now(UTC):
        return _github_token
    return ""


def _session_github_token() -> tuple[str, str]:
    """The session's token, looked up on first use; or "" and why there is none.

    gh's token is kept for the life of the process, and an App's installation token until its
    renewal is due. A lookup that finds none is not kept, so the next call looks again. When the
    renewal fails, the kept token serves until it expires, and the next call mints again (#6671).
    """
    global _github_token, _github_token_expires_at
    with _GITHUB_TOKEN_LOCK:
        if _github_token and not _renewal_due(_github_token_expires_at):
            return _github_token, ""
        try:
            token, why, expires_at = _lookup_session_token()
        except GitHubUnreadError, GitHubRateLimitError:
            if not _kept_token():
                raise
            token, why, expires_at = "", "", None
        if token:
            _github_token, _github_token_expires_at = token, expires_at
            return token, ""
        if kept := _kept_token():
            logger.warning(
                "The renewal of the GitHub token failed; the kept token serves until it expires"
            )
            return kept, ""
        return "", why


def github_token() -> str:
    """The session's current GitHub token, raising the unauthenticated error when there is none:
    gh's token, or the App's installation token, minted again before it expires."""
    token, why = _session_github_token()
    if not token:
        raise GitHubUnauthenticatedError(why)
    return token


def finds_github_login() -> bool:
    """Whether the lookup of `github_token` finds a GitHub token for the session: a token variable
    or a stored gh login. The agent phase of the stage Job refuses to start with one (#6705)."""
    try:
        github_token()
    except GitHubOperationError:
        return False
    return True


def _git_github_token() -> str:
    """The session's token for a git child of a person, or "" when there is none. A lookup that
    finds no token is kept for git for the life of the process, so the next git child starts no
    lookup; a token that a later gh call finds reaches the next git child (#6671, #6691)."""
    global _git_lookup_failed
    with _GITHUB_TOKEN_LOCK:
        if _git_lookup_failed and not _github_token:
            return ""
    token = _session_github_token()[0]
    if not token:
        with _GITHUB_TOKEN_LOCK:
            _git_lookup_failed = True
    return token


def reset_github_token() -> None:
    """Forget the token and a failed lookup, so the next GitHub call looks it up or mints it
    again."""
    global _github_token, _github_token_expires_at, _git_lookup_failed
    with _GITHUB_TOKEN_LOCK:
        _github_token, _github_token_expires_at, _git_lookup_failed = None, None, False


def is_local_gh_command(gh_args: list[str]) -> bool:
    """Whether gh's arguments make no call of the session's: `gh auth`, version or help.

    These need no identity, so they run before one is resolved and outside the pin.
    """
    return not gh_args or gh_args[0].lower() in CONST_GH_NON_API_COMMANDS


def _github_client_name(cmd: list[str]) -> str | None:
    """The GitHub client a command runs, gh or git, or None for any other program."""
    name = Path(cmd[0]).name if cmd else ""
    return name if name in (CONST_GH_CLI, CONST_GIT_CLI) else None


@dataclass(frozen=True)
class _GitHubPin:
    """The GitHub token that one child gets: `env` holds the token variables of its environment,
    and `session` says that the child gets the session's token."""

    env: dict[str, str] = field(default_factory=dict)
    session: bool = False


def _github_pin(cmd: list[str], caller_env: dict[str, str] | None = None) -> _GitHubPin | None:
    """The GitHub token that the child `cmd` gets, or None for a program that is no GitHub client.
    It looks the token up and changes no environment, so an async call can run it in a thread.

    A gh or git child gets the session's token as GH_TOKEN, and no other GitHub token. git reads it
    through the credential helper that it is configured with, `gh auth git-credential`.

    gh's local commands (`gh auth` subcommands, version and help) are exempt: they get the
    GH_TOKEN and GITHUB_TOKEN of the environment, or of `caller_env` where the caller set them,
    unchanged. Other gh calls without a token raise the unauthenticated error before they run.
    So does a git child when the process acts as the GitHub App: the failed mint is the cause of
    its failure. A person's git child runs without a token, and the remote gives its own answer
    (#6671). git keeps a failed lookup of a person for the life of the process (#6691).
    """
    client = _github_client_name(cmd)
    if client is None or is_dry_run():
        return None
    if client == CONST_GH_CLI and is_local_gh_command(cmd[1:]):
        given = {**os.environ, **(caller_env or {})}
        return _GitHubPin(
            {name: str(given[name]) for name in CONST_GH_TOKEN_ENV_VARS if name in given}
        )
    if client == CONST_GIT_CLI and not acts_as_github_app():
        token = _git_github_token()
    else:
        token = github_token()
    return _GitHubPin({CONST_GH_AUTH_ENV_VAR: token}, session=True) if token else _GitHubPin()


def _pin(pin: _GitHubPin | None, sub_env: dict[str, str]) -> None:
    """Give the child of `sub_env` the token of `pin`, and no other GitHub token."""
    if pin is None:
        return
    for name in CONST_GH_TOKEN_ENV_VARS:
        sub_env.pop(name, None)
    sub_env.update(pin.env)


def _run_in_own_session(
    cmd: list[str],
    *,
    input: str | None = None,
    capture_output: bool = False,
    timeout: float | None = None,
    check: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """`subprocess.run` for a child that gets the session's token: the child starts in a session
    of its own, and a timeout or another error while it runs kills its whole process group, as
    `run_async` stops a group. `subprocess.run` kills only the child, and a helper that the child
    started, such as `git-remote-https`, holds the token in its environment. After a Ctrl+C the
    group first gets the SIGINT of the terminal (`_interrupt_group`)."""
    if input is not None:
        kwargs["stdin"] = subprocess.PIPE
    if capture_output:
        kwargs["stdout"] = kwargs["stderr"] = subprocess.PIPE
    with subprocess.Popen(cmd, start_new_session=True, **kwargs) as child:
        try:
            stdout, stderr = child.communicate(input, timeout=timeout)
        except BaseException as error:
            try:
                if isinstance(error, KeyboardInterrupt):
                    _interrupt_group(child)
            finally:
                if not _signal_process_group(child.pid, signal.SIGKILL):
                    child.kill()
                child.wait()
            raise
        returncode = child.wait()
    if check and returncode:
        raise subprocess.CalledProcessError(returncode, cmd, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)


def _interrupt_group(child: subprocess.Popen[Any]) -> None:
    """Give the process group of `child` the SIGINT of a Ctrl+C, and wait up to
    `_SIGINT_WAIT_SECONDS` for the child to end, as `subprocess.run` waits for a child after a
    Ctrl+C. The child runs in a session of its own, so the SIGINT of the terminal does not reach
    it. git removes its lock files on SIGINT, so `.git/index.lock` and a half-made worktree do not
    stay. The caller kills what is left of the group: a SIGKILL reaches no group that ended."""
    if _signal_process_group(child.pid, signal.SIGINT):
        with contextlib.suppress(subprocess.TimeoutExpired):
            child.wait(timeout=_SIGINT_WAIT_SECONDS)


class PlannedProcessResult(subprocess.CompletedProcess[str], PlannedRequest):
    """A dry-run process result that is both a PlannedRequest and a CompletedProcess."""

    def __init__(
        self,
        method: str = "run",
        target: str = "",
        argv: tuple[str, ...] = (),
        stdin: str | None = None,
        env: tuple[tuple[str, str], ...] = (),
        condition: str = "",
        repeat: str = "",
        **kwargs: Any,
    ) -> None:
        args = kwargs.get("args", list(argv))
        returncode = kwargs.get("returncode", 0)
        stdout = kwargs.get("stdout", "")
        stderr = kwargs.get("stderr", "")
        super().__init__(args=list(args), returncode=returncode, stdout=stdout, stderr=stderr)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "argv", tuple(argv) if argv else tuple(args))
        object.__setattr__(self, "stdin", stdin)
        object.__setattr__(self, "env", env)
        object.__setattr__(self, "condition", condition)
        object.__setattr__(self, "repeat", repeat)


def prepare_tool_cmd(cmd: Sequence[str] | list[str]) -> list[str]:
    """Prepare command arguments list, injecting uv preview features when starting uv."""
    full_cmd = list(cmd)
    if full_cmd and full_cmd[0] == "uv" and "--preview-features" not in full_cmd:
        full_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
    return full_cmd


class ProcessRunner(Protocol):
    """Protocol for process runners executing system subprocesses."""

    def prepare_cmd(self, cmd: Sequence[str] | list[str]) -> list[str]: ...

    def run(
        self,
        cmd: Sequence[str] | list[str],
        *,
        input: str | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        quiet: bool = False,
        timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        isolate_env: bool = True,
        extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
        local_read: bool = False,
        intent: str | None = None,
    ) -> subprocess.CompletedProcess[str]: ...

    async def run_async(
        self,
        cmd: Sequence[str] | list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        quiet: bool = False,
        timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        isolate_env: bool = True,
        extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
        local_read: bool = False,
        intent: str | None = None,
    ) -> subprocess.CompletedProcess[str]: ...

    def spawn_detached(
        self,
        cmd: Sequence[str] | list[str],
        *,
        isolate_env: bool = True,
        extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
    ) -> DetachedProcess: ...

    def spawn_sandbox(
        self,
        cmd: Sequence[str] | list[str],
    ) -> Any: ...

    def terminate_process_group(
        self,
        pid: int,
        sig: int = signal.SIGTERM,
    ) -> bool: ...


class DetachedProcess(Protocol):
    """A child in a session of its own, which runs on after the command that started it ends."""

    pid: int

    def poll(self) -> int | None: ...


class DefaultProcessRunner:
    """The default production process runner executing real system processes."""

    def prepare_cmd(self, cmd: Sequence[str] | list[str]) -> list[str]:
        """Prepare command arguments list, injecting standardized uv preview features when starting uv."""
        return prepare_tool_cmd(cmd)

    def spawn_detached(
        self,
        cmd: Sequence[str] | list[str],
        *,
        isolate_env: bool = True,
        extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
    ) -> DetachedProcess:
        """Start `cmd` in a session of its own, with no terminal and no pipes.

        The child runs on after this process ends, and a SIGINT from the terminal does not reach
        it. `terminate_process_group` with its pid stops it and its children.
        """
        sub_env = build_subprocess_env(
            isolate_env=isolate_env, extra_allowed_keys=extra_allowed_env
        )
        return subprocess.Popen(
            list(cmd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=sub_env,
            start_new_session=True,
        )

    def spawn_sandbox(
        self,
        cmd: Sequence[str] | list[str],
    ) -> subprocess.Popen[bytes]:
        """Spawn a sandbox process in a new session with piped stdout/stderr (#2149)."""
        return subprocess.Popen(
            list(cmd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

    def terminate_process_group(
        self,
        pid: int,
        sig: int = signal.SIGTERM,
    ) -> bool:
        """Terminate process group using default OS process group signaling (#2149)."""
        return _terminate_process_group_os(pid, sig)

    def run(
        self,
        cmd: Sequence[str] | list[str],
        *,
        input: str | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        quiet: bool = False,
        timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        isolate_env: bool = True,
        extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
        local_read: bool = False,
        intent: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        full_cmd = list(cmd)
        _validate_subprocess_cwd(cwd)
        if is_dry_run() and not (local_read or intent in ("read", "local_read")):
            if not quiet and not _QUIET_SUBPROCESS_ARGS.intersection(full_cmd):
                from devops_cli.output import print_dry_run_command

                print_dry_run_command(full_cmd, cwd=str(cwd) if cwd else None)
            method = full_cmd[0] if full_cmd else "process"
            target = " ".join(full_cmd[1:]) if len(full_cmd) > 1 else "workspace"
            return PlannedProcessResult(
                method=method,
                target=target,
                argv=tuple(full_cmd),
                stdin=input,
            )

        bin_name = Path(full_cmd[0]).name if full_cmd else "unknown"
        start_time = time.perf_counter()

        sub_env = build_subprocess_env(
            env=env,
            isolate_env=isolate_env,
            extra_allowed_keys=extra_allowed_env,
        )
        pin = _github_pin(full_cmd, env)
        _pin(pin, sub_env)

        with (
            trace_span(
                f"subprocess.{bin_name}",
                attributes=_subprocess_span_attributes(full_cmd, bin_name, cwd, timeout),
            ) as span_h,
        ):
            get_tracer().inject_trace_env(sub_env)
            run = _run_in_own_session if pin is not None and pin.session else subprocess.run
            try:
                proc = run(
                    full_cmd,
                    input=input,
                    cwd=cwd,
                    env=sub_env,
                    capture_output=capture_output,
                    text=text,
                    errors="replace" if text else None,
                    check=check,
                    timeout=timeout,
                )
            except FileNotFoundError:
                dur = time.perf_counter() - start_time
                span_h.set_attribute("subprocess.executable_found", False)
                span_h.set_attribute("subprocess.exit_code", CONST_EXIT_COMMAND_NOT_FOUND)
                span_h.set_attribute("process.exit.code", CONST_EXIT_COMMAND_NOT_FOUND)
                span_h.set_attribute("subprocess.duration_seconds", dur)
                span_h.set_attribute("subprocess.status", "not_found")
                span_h.add_event("subprocess_not_found", {"bin": bin_name})
                if check:
                    raise
                return subprocess.CompletedProcess(
                    full_cmd,
                    returncode=CONST_EXIT_COMMAND_NOT_FOUND,
                    stdout="",
                    stderr=f"Executable '{bin_name}' not found in PATH",
                )

            ret_code = getattr(proc, "returncode", 0)
            stdout_val = getattr(proc, "stdout", None)
            stderr_val = getattr(proc, "stderr", None)

            dur = time.perf_counter() - start_time
            span_h.set_attribute("subprocess.exit_code", ret_code)
            span_h.set_attribute("process.exit.code", ret_code)
            span_h.set_attribute("subprocess.duration_seconds", dur)
            span_h.set_attribute("subprocess.status", "ok" if ret_code == 0 else "non_zero")

            if stdout_val is not None:
                stdout_len = (
                    len(stdout_val.encode("utf-8"))
                    if isinstance(stdout_val, str)
                    else len(stdout_val)
                )
                span_h.set_attribute("subprocess.stdout_bytes", stdout_len)
            if stderr_val is not None:
                stderr_len = (
                    len(stderr_val.encode("utf-8"))
                    if isinstance(stderr_val, str)
                    else len(stderr_val)
                )
                span_h.set_attribute("subprocess.stderr_bytes", stderr_len)

            if ret_code != 0 and check:
                span_h.set_attribute("error", True)
                raw_sample = (
                    (stderr_val or stdout_val or "")[:400]
                    if isinstance(stderr_val or stdout_val, str)
                    else ""
                )
                from devops_cli.security.sanitizer import mask_secrets

                err_sample = mask_secrets(raw_sample) if raw_sample else ""
                if err_sample:
                    span_h.set_attribute("subprocess.error_sample", err_sample)
                span_h.add_event(
                    "subprocess_failed",
                    {"exit_code": ret_code, "error_sample": err_sample},
                )
            else:
                span_h.add_event(
                    "subprocess_completed",
                    {"exit_code": ret_code, "duration_seconds": dur},
                )

            emit(
                SUBPROCESS_DURATION,
                dur,
                {"bin": bin_name, "status": "ok" if ret_code == 0 else "error"},
            )
            return proc

    async def run_async(
        self,
        cmd: Sequence[str] | list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        quiet: bool = False,
        timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        isolate_env: bool = True,
        extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
        local_read: bool = False,
        intent: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        full_cmd = list(cmd)
        _validate_subprocess_cwd(cwd)
        if is_dry_run() and not (local_read or intent in ("read", "local_read")):
            if not quiet and not _QUIET_SUBPROCESS_ARGS.intersection(full_cmd):
                from devops_cli.output import print_dry_run_command

                print_dry_run_command(full_cmd, cwd=str(cwd) if cwd else None)
            method = full_cmd[0] if full_cmd else "process"
            target = " ".join(full_cmd[1:]) if len(full_cmd) > 1 else "workspace"
            return PlannedProcessResult(
                method=method,
                target=target,
                argv=tuple(full_cmd),
                stdin=None,
            )

        bin_name = Path(full_cmd[0]).name if full_cmd else "unknown"
        start_time = time.perf_counter()

        sub_env = build_subprocess_env(
            env=env,
            isolate_env=isolate_env,
            extra_allowed_keys=extra_allowed_env,
        )
        pin = await asyncio.to_thread(_github_pin, full_cmd, env)
        _pin(pin, sub_env)

        with (
            trace_span(
                f"subprocess.{bin_name}",
                attributes=_subprocess_span_attributes(full_cmd, bin_name, cwd, timeout),
            ) as span_h,
        ):
            get_tracer().inject_trace_env(sub_env)
            stdout_pipe = asyncio.subprocess.PIPE if capture_output else None
            stderr_pipe = asyncio.subprocess.PIPE if capture_output else None

            try:
                proc = await _spawn_under_stop(
                    full_cmd,
                    cwd=cwd,
                    env=sub_env,
                    stdout=stdout_pipe,
                    stderr=stderr_pipe,
                    start_new_session=(os.name == "posix"),
                )
                stdout_bytes, stderr_bytes = await _communicate_or_stop_group(
                    proc, full_cmd, timeout
                )
            except FileNotFoundError:
                dur = time.perf_counter() - start_time
                span_h.set_attribute("subprocess.executable_found", False)
                span_h.set_attribute("subprocess.exit_code", CONST_EXIT_COMMAND_NOT_FOUND)
                span_h.set_attribute("process.exit.code", CONST_EXIT_COMMAND_NOT_FOUND)
                span_h.set_attribute("subprocess.duration_seconds", dur)
                span_h.set_attribute("subprocess.status", "not_found")
                span_h.add_event("subprocess_not_found", {"bin": bin_name})
                if check:
                    raise
                return subprocess.CompletedProcess(
                    full_cmd,
                    returncode=CONST_EXIT_COMMAND_NOT_FOUND,
                    stdout="",
                    stderr=f"Executable '{bin_name}' not found in PATH",
                )

            ret_code = proc.returncode if proc.returncode is not None else 0
            stdout_str = (
                stdout_bytes.decode("utf-8", errors="replace")
                if (text and stdout_bytes is not None)
                else (stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else "")
            )
            stderr_str = (
                stderr_bytes.decode("utf-8", errors="replace")
                if (text and stderr_bytes is not None)
                else (stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else "")
            )

            dur = time.perf_counter() - start_time
            span_h.set_attribute("subprocess.exit_code", ret_code)
            span_h.set_attribute("process.exit.code", ret_code)
            span_h.set_attribute("subprocess.duration_seconds", dur)
            span_h.set_attribute("subprocess.status", "ok" if ret_code == 0 else "non_zero")

            if stdout_bytes:
                span_h.set_attribute("subprocess.stdout_bytes", len(stdout_bytes))
            if stderr_bytes:
                span_h.set_attribute("subprocess.stderr_bytes", len(stderr_bytes))

            if ret_code != 0 and check:
                span_h.set_attribute("error", True)
                raw_sample = (stderr_str or stdout_str or "")[:400]
                from devops_cli.security.sanitizer import mask_secrets

                err_sample = mask_secrets(raw_sample) if raw_sample else ""
                if err_sample:
                    span_h.set_attribute("subprocess.error_sample", err_sample)
                span_h.add_event(
                    "subprocess_failed",
                    {"exit_code": ret_code, "error_sample": err_sample},
                )
                raise subprocess.CalledProcessError(
                    ret_code, full_cmd, output=stdout_str, stderr=stderr_str
                )

            span_h.add_event(
                "subprocess_completed",
                {"exit_code": ret_code, "duration_seconds": dur},
            )

            emit(
                SUBPROCESS_DURATION,
                dur,
                {"bin": bin_name, "status": "ok" if ret_code == 0 else "error"},
            )
            return subprocess.CompletedProcess(
                full_cmd,
                returncode=ret_code,
                stdout=stdout_str,
                stderr=stderr_str,
            )


_PROCESS_RUNNER: ProcessRunner | None = None
_PROCESS_RUNNER_LOCK = threading.Lock()


def get_process_runner() -> ProcessRunner:
    """The active process runner seam: custom runner if set, otherwise DefaultProcessRunner."""
    global _PROCESS_RUNNER
    with _PROCESS_RUNNER_LOCK:
        if _PROCESS_RUNNER is None:
            return DefaultProcessRunner()
        return _PROCESS_RUNNER


def set_process_runner(runner: ProcessRunner | None) -> None:
    """Set custom process runner for testing."""
    global _PROCESS_RUNNER
    with _PROCESS_RUNNER_LOCK:
        _PROCESS_RUNNER = runner


def reset_process_runner() -> None:
    """Reset active process runner back to default."""
    global _PROCESS_RUNNER
    with _PROCESS_RUNNER_LOCK:
        _PROCESS_RUNNER = None


def run_subprocess(
    cmd: Sequence[str] | list[str],
    *,
    input: str | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
    quiet: bool = False,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    isolate_env: bool = True,
    extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
    local_read: bool = False,
    intent: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command with unified timeout bounds, dry-run reporting,
    W3C trace context propagation, OpenTelemetry tracing, and ambient environment isolation."""
    return get_process_runner().run(
        cmd,
        input=input,
        cwd=cwd,
        env=env,
        capture_output=capture_output,
        text=text,
        check=check,
        quiet=quiet,
        timeout=timeout,
        isolate_env=isolate_env,
        extra_allowed_env=extra_allowed_env,
        local_read=local_read,
        intent=intent,
    )


def spawn_detached(
    cmd: Sequence[str] | list[str],
    *,
    isolate_env: bool = True,
    extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
) -> DetachedProcess:
    """Start `cmd` detached, in a session of its own, through the active process runner."""
    return get_process_runner().spawn_detached(
        cmd, isolate_env=isolate_env, extra_allowed_env=extra_allowed_env
    )


def _signal_process_group(pgid: int, sig: int) -> bool:
    """Send a signal to the process group, returning False if unreachable."""
    if not hasattr(os, "killpg"):
        return False
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError, PermissionError:
        return False
    return True


def _is_invalid_pgid(pgid: int | None) -> bool:
    """Check whether a pgid is invalid or belongs to the current process group."""
    if not isinstance(pgid, int) or pgid <= 1:
        return True
    return bool(hasattr(os, "getpgrp") and pgid == os.getpgrp())


def _terminate_process_group_os(
    pid: int,
    sig: int = signal.SIGTERM,
    os_module: Any = os,
) -> bool:
    """Safely terminate an isolated process group hierarchy via OS calls."""
    if not isinstance(pid, int) or pid <= 1:
        return False
    try:
        if pid == os_module.getpid():
            return False
        group = os_module.getpgid(pid)
    except OSError, ProcessLookupError, TypeError:
        return False

    if group <= 1:
        return False

    self_pgrp = os_module.getpgrp() if hasattr(os_module, "getpgrp") else -1
    own_pgrp_0 = os_module.getpgid(0) if hasattr(os_module, "getpgid") else -1
    if group == self_pgrp or group == own_pgrp_0:
        try:
            os_module.kill(pid, sig)
            return True
        except OSError, ProcessLookupError, PermissionError:
            return False

    if not hasattr(os_module, "killpg"):
        try:
            os_module.kill(pid, sig)
            return True
        except OSError, ProcessLookupError, PermissionError:
            return False

    try:
        os_module.killpg(group, sig)
        return True
    except OSError, ProcessLookupError, PermissionError:
        return False


def terminate_process_group(
    pid: int,
    sig: int = signal.SIGTERM,
    os_module: Any = os,
) -> bool:
    """Safely terminate an isolated process group hierarchy, falling back to direct process kill.

    Guards against PID 0, PID 1, non-integers, self PID, and the caller's own PGID to prevent
    accidental termination of container init or ambient caller processes. If the process shares
    the caller's process group, signals only the direct process to avoid killing the caller.
    """
    if os_module is not os:
        return _terminate_process_group_os(pid, sig, os_module)
    return get_process_runner().terminate_process_group(pid, sig)


async def _wait_for_group_exit_async(
    proc: asyncio.subprocess.Process, pgid: int, deadline: float
) -> bool:
    """Poll for group exit until deadline. Returns True if group exited. The leader is reaped as
    it exits; once it has, the poll sleeps between probes of the members left (#1669)."""
    while time.monotonic() < deadline:
        if proc.returncode is not None and not _signal_process_group(pgid, 0):
            return True
        if proc.returncode is not None:
            await asyncio.sleep(DEFAULT_SHELL_STOP_POLL_SECONDS)
            continue
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(proc.wait(), timeout=DEFAULT_SHELL_STOP_POLL_SECONDS)
    return not _signal_process_group(pgid, 0)


async def _kill_leader_async(proc: asyncio.subprocess.Process) -> None:
    """Kill only the leader, when its group cannot be signalled; one already reaped is left be."""
    if proc.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
    await proc.wait()


async def _escalate_async(
    proc: asyncio.subprocess.Process,
    pgid: int,
    later_signals: tuple[int, ...],
    grace: float,
) -> bool:
    """Give the group `grace` seconds after the signal already sent, then send each later signal
    with the same grace; whether the group exited."""
    if await _wait_for_group_exit_async(proc, pgid, time.monotonic() + grace):
        return True
    for sig in later_signals:
        if not _signal_process_group(pgid, sig):
            return True
        if await _wait_for_group_exit_async(proc, pgid, time.monotonic() + grace):
            return True
    return False


async def _reap_after_kill_async(
    proc: asyncio.subprocess.Process, grace: float
) -> asyncio.CancelledError | None:
    """Wait up to `grace` seconds for the killed leader to be reaped, through any cancellation;
    the last cancellation absorbed, if any."""
    deadline = time.monotonic() + grace
    absorbed: asyncio.CancelledError | None = None
    while proc.returncode is None and (remaining := deadline - time.monotonic()) > 0:
        try:
            await asyncio.wait_for(proc.wait(), timeout=remaining)
        except TimeoutError:
            break
        except asyncio.CancelledError as cancellation:
            absorbed = cancellation
    return absorbed


async def _terminate_process_group_async(
    proc: asyncio.subprocess.Process,
    *,
    first_signal: int = signal.SIGTERM,
    stop_grace_seconds: float = DEFAULT_SHELL_STOP_GRACE_SECONDS,
) -> None:
    """Stop the process group of proc: `first_signal`, then SIGTERM if that was not it, each with
    `stop_grace_seconds` to end the group, then SIGKILL. The group is stopped even when its
    leader has exited, since killpg still reaches the members left (#1669).

    Once begun, the stop is not given up. A further cancellation cuts the grace short and is
    raised again only once the group is killed, and the SIGKILL is sent from a `finally`. A
    signal handler that raises, as `asyncio.run`'s handler raises KeyboardInterrupt at a second
    Ctrl-C, can raise before the `try` or in the `finally` and skip the SIGKILL, so a caller that
    must not lose it turns each stop signal into a cancellation, as `devops ci test` does
    (#2069)."""
    pgid = proc.pid
    if _is_invalid_pgid(pgid) or not _signal_process_group(pgid, first_signal):
        await _kill_leader_async(proc)
        return
    later = () if first_signal == signal.SIGTERM else (signal.SIGTERM,)
    exited = False
    absorbed: asyncio.CancelledError | None = None
    try:
        exited = await _escalate_async(proc, pgid, later, stop_grace_seconds)
    except asyncio.CancelledError as cancellation:
        absorbed = cancellation
    finally:
        if not exited:
            _signal_process_group(pgid, signal.SIGKILL)
    if not exited:
        absorbed = await _reap_after_kill_async(proc, stop_grace_seconds) or absorbed
    if absorbed is not None:
        raise absorbed


async def _spawn_under_stop(cmd: list[str], **kwargs: Any) -> asyncio.subprocess.Process:
    """Start `cmd`, shielded: a cancellation while the start is still pending lets it finish and
    then stops the child's whole process group, where asyncio's own clean-up kills only the
    child (#1669). The start absorbs every further cancellation until it completes. Under
    `asyncio.run`'s own Ctrl-C handler, a second Ctrl-C while the child is still starting raises
    KeyboardInterrupt instead, `asyncio.Runner.close` cancels the start itself, and asyncio's
    clean-up then kills the direct child alone."""
    spawn = asyncio.ensure_future(asyncio.create_subprocess_exec(*cmd, **kwargs))
    try:
        return await asyncio.shield(spawn)
    except asyncio.CancelledError:
        while not spawn.done():
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait({spawn})
        if not spawn.cancelled() and spawn.exception() is None:
            await _terminate_process_group_async(spawn.result(), first_signal=signal.SIGINT)
        raise


async def _communicate_or_stop_group(
    proc: asyncio.subprocess.Process, cmd: list[str], timeout: float
) -> tuple[bytes | None, bytes | None]:
    """The child's output once it exits. A run past `timeout` stops the child's whole process
    group and raises `subprocess.TimeoutExpired`. A cancelled run stops the group too and stays
    cancelled: the child's session is its own, so no Ctrl-C reaches it, and the stop first sends
    the SIGINT a terminal would have sent, so a pytest runs its KeyboardInterrupt teardown and
    its `finally` blocks before SIGTERM and SIGKILL follow (#1669)."""
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        await _terminate_process_group_async(proc)
        raise subprocess.TimeoutExpired(cmd, timeout) from None
    except asyncio.CancelledError:
        await _terminate_process_group_async(proc, first_signal=signal.SIGINT)
        raise


async def run_subprocess_async(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
    quiet: bool = False,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    isolate_env: bool = True,
    extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command asynchronously with non-blocking I/O, unified timeout bounds,
    dry-run reporting, W3C trace context propagation, OpenTelemetry tracing, and ambient environment isolation,
    through the active process runner."""
    return await get_process_runner().run_async(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=capture_output,
        text=text,
        check=check,
        quiet=quiet,
        timeout=timeout,
        isolate_env=isolate_env,
        extra_allowed_env=extra_allowed_env,
    )


_JSON_UNSET = object()


def _raise_subprocess_error(
    err_type: type[DevOpsCLIError],
    cmd: list[str],
    ret_code: int,
    stderr: str | None,
    msg: str,
) -> None:
    """Helper to raise SubprocessError or custom DevOpsCLIError with command context."""
    bin_name = cmd[0] if cmd else "unknown"
    if issubclass(err_type, SubprocessError):
        raise err_type(
            f"Subprocess failed for command '{bin_name}': {msg}",
            command=cmd,
            exit_code=ret_code,
            stderr=stderr,
        )
    raise err_type(
        f"Subprocess failed for command '{bin_name}': {msg}",
        exit_code=ret_code,
        details={"command": cmd, "stderr": stderr},
    )


def run_json_subprocess(
    cmd: list[str],
    *,
    input: str | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    quiet: bool = True,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    default: Any = _JSON_UNSET,
    error_cls: type[DevOpsCLIError] | None = None,
    check: bool = True,
    isolate_env: bool = True,
    extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
) -> Any:
    """Execute subprocess and safely deserialize its stdout as JSON.

    Args:
        cmd: Command arguments list.
        input: Optional stdin string.
        cwd: Working directory.
        env: Environment variables override.
        quiet: Suppress output.
        timeout: Subprocess timeout in seconds.
        default: Fallback value if JSON parsing fails.
        error_cls: Exception class to raise upon command or parsing failure (defaults to SubprocessError).
        check: Whether to raise on non-zero exit code immediately. If False, attempts to parse valid stdout JSON first.
        isolate_env: Whether to isolate ambient environment secrets.
        extra_allowed_env: Additional environment variable keys to preserve.

    Returns:
        Parsed JSON data structure (dict or list), or default if fallback provided.

    Raises:
        SubprocessError or error_cls: If subprocess exits with non-zero code and check is True, or JSON is invalid and default is unset.
    """
    err_type = error_cls or SubprocessError
    res = run_subprocess(
        cmd,
        input=input,
        cwd=cwd,
        env=env,
        quiet=quiet,
        timeout=timeout,
        check=False,
        isolate_env=isolate_env,
        extra_allowed_env=extra_allowed_env,
    )

    ret_code = res.returncode if isinstance(res.returncode, int) else 0
    raw_stdout = (res.stdout or "").strip()

    if ret_code != 0 and check:
        err_msg = (res.stderr or "").strip() or raw_stdout or f"Process exited with code {ret_code}"
        _raise_subprocess_error(err_type, cmd, ret_code, res.stderr, err_msg)

    if not raw_stdout:
        if default is not _JSON_UNSET:
            return default
        err_msg = (
            res.stderr or ""
        ).strip() or f"Process exited with code {ret_code} and produced no output"
        _raise_subprocess_error(err_type, cmd, ret_code, res.stderr, err_msg)

    try:
        return json.loads(raw_stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        if default is not _JSON_UNSET:
            return default
        exit_val = ret_code if ret_code != 0 else 1
        _raise_subprocess_error(err_type, cmd, exit_val, res.stderr, f"Invalid JSON output: {exc}")
