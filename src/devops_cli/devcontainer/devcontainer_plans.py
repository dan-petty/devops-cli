"""Planned requests for devcontainer and install-tools commands (#412, #886, #2256).

A dry run makes zero external requests and returns ordered PlannedRequest items.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Final

from devops_cli.config.commands import build_npm_ci_cmd
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.k8s.context import configured_context
from devops_cli.tools_lock import (
    LOCK_DIR,
    BinaryTool,
    NpmTool,
    PythonTool,
    load_tools_lock,
)


def _sys_info() -> tuple[str, str]:
    system = platform.system().lower()
    arch = platform.machine().lower()
    os_name = {"darwin": "darwin", "linux": "linux", "windows": "windows"}.get(system, system)
    arch_name = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(
        arch, arch
    )
    return os_name, arch_name


_PLATFORM: Final[str] = "-".join(_sys_info())


def plan_bootstrap_k8s(
    workspace: Path | str = ".",
    stack: str = "infra",
) -> list[PlannedRequest]:
    """Plan Minikube cluster startup and context update."""
    return [
        PlannedRequest(
            method="minikube",
            target="status",
            argv=("minikube", "status", "--format", "{{.Host}}"),
        ),
        PlannedRequest(
            method="minikube",
            target="start",
            argv=("minikube", "start"),
            condition="minikube is not running",
        ),
        PlannedRequest(
            method="minikube",
            target="update-context",
            argv=("minikube", "update-context"),
        ),
    ]


def plan_install_tools(
    tool: str | None = None,
    target_dir: Path | None = None,
    only_missing: bool = False,
) -> list[PlannedRequest]:
    """Plan tool downloads and installations from tools lock."""
    tools = load_tools_lock().tools()
    if tool is not None and tool in tools:
        selected_tools = {tool: tools[tool]}
    else:
        selected_tools = tools

    requests: list[PlannedRequest] = []
    for name, entry in selected_tools.items():
        if isinstance(entry, BinaryTool):
            artifact = entry.platforms.get(_PLATFORM)
            if artifact:
                requests.append(
                    PlannedRequest(
                        method="GET",
                        target=artifact.url,
                    )
                )
        elif isinstance(entry, PythonTool):
            requests.append(
                PlannedRequest(
                    method="uv",
                    target=f"pip sync {entry.requirements}",
                    argv=(
                        "uv",
                        "pip",
                        "sync",
                        "--require-hashes",
                        "-p",
                        "<python>",
                        str(LOCK_DIR / entry.requirements),
                    ),
                )
            )
        elif isinstance(entry, NpmTool):
            requests.append(
                PlannedRequest(
                    method="npm",
                    target=f"ci {name}",
                    argv=tuple(build_npm_ci_cmd()),
                )
            )
    return requests


def plan_post_create(
    workspace: Path | str = ".",
    skip_tools: bool = False,
    target_dir: Path | None = None,
) -> list[PlannedRequest]:
    """Plan developer tool bootstrapping and managed tools installation."""
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="curl",
            target="https://astral.sh/uv/install.sh",
            argv=(
                "bash",
                "-o",
                "pipefail",
                "-c",
                "curl -LsSf https://astral.sh/uv/install.sh | sh",
            ),
            condition="uv is not installed",
        ),
        PlannedRequest(
            method="uv",
            target="tool install pre-commit",
            argv=("uv", "tool", "install", "pre-commit"),
            condition="pre-commit is not installed",
        ),
        PlannedRequest(
            method="curl",
            target="https://claude.ai/install.sh",
            argv=("bash", "-o", "pipefail", "-c", "curl -fsSL https://claude.ai/install.sh | bash"),
            condition="claude is not installed",
        ),
    ]
    if not skip_tools:
        requests.extend(plan_install_tools(target_dir=target_dir, only_missing=True))
    return requests


def plan_post_start(workspace: Path | str = ".") -> list[PlannedRequest]:
    """Plan git configuration and kubectl context alignment."""
    desired = configured_context()
    target_ctx = desired or "<context>"
    return [
        PlannedRequest(
            method="git",
            target="config --global push.autoSetupRemote true",
            argv=("git", "config", "--global", "push.autoSetupRemote", "true"),
        ),
        PlannedRequest(
            method="git",
            target="config --global init.defaultBranch main",
            argv=("git", "config", "--global", "init.defaultBranch", "main"),
        ),
        PlannedRequest(
            method="kubectl",
            target="config get-contexts -o name",
            argv=("kubectl", "config", "get-contexts", "-o", "name"),
        ),
        PlannedRequest(
            method="kubectl",
            target=f"config use-context {target_ctx}",
            argv=("kubectl", "config", "use-context", target_ctx),
            condition="context in kubeconfig",
        ),
    ]


def plan_run_lifecycle(
    workspace: Path | str = ".",
    post_create: bool = True,
    post_start: bool = True,
) -> list[PlannedRequest]:
    """Plan lifecycle actions for post-create and/or post-start."""
    requests: list[PlannedRequest] = []
    if post_create:
        requests.extend(plan_post_create(workspace))
    if post_start:
        requests.extend(plan_post_start(workspace))
    return requests


def _gh_hosts_file() -> Path:
    """Return the file gh keeps per-host login state in."""
    config_home = os.getenv("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(os.getenv("GH_CONFIG_DIR") or Path(config_home) / "gh") / "hosts.yml"


def _gh_plaintext_token_hosts() -> list[str]:
    """Return the hosts gh keeps a plaintext token for instead of using the keyring.

    gh falls back to hosts.yml whenever the keyring is locked or unreachable at login, and
    a token there wins over the keyring, so a fallback stays in effect until moved.
    """
    import yaml

    try:
        hosts = yaml.safe_load(_gh_hosts_file().read_text(encoding="utf-8"))
    except OSError, yaml.YAMLError:
        return []
    if not isinstance(hosts, dict):
        return []

    found: list[str] = []
    for host, entry in hosts.items():
        if not isinstance(entry, dict):
            continue
        users = entry.get("users")
        user_entries = users.values() if isinstance(users, dict) else []
        if entry.get("oauth_token") or any(
            isinstance(user, dict) and user.get("oauth_token") for user in user_entries
        ):
            found.append(str(host))
    return found


def plan_unlock_keyring() -> list[PlannedRequest]:
    """Plan gnome-keyring unlock and gh credential migration."""
    hosts = _gh_plaintext_token_hosts() or ["<host>"]
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="gnome-keyring-daemon",
            target="--replace --unlock",
            argv=("gnome-keyring-daemon", "--replace", "--unlock", "--components=secrets"),
            stdin="<password>",
        )
    ]
    for host in hosts:
        requests.extend(
            [
                PlannedRequest(
                    method="gh",
                    target=f"auth token -h {host}",
                    argv=("gh", "auth", "token", "-h", host),
                ),
                PlannedRequest(
                    method="gh",
                    target=f"auth login -h {host} --with-token",
                    argv=("gh", "auth", "login", "-h", host, "--with-token"),
                    stdin="<token>",
                ),
            ]
        )
    return requests
