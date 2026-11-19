"""The tools of each infra repo (#6336).

An infra repo pins the tools of its checks and plays, and its project profile names the command
that installs them into its checkout (`tools.install`; `make install` for the type `ansible-k8s`).
`devops devcontainer post-start` runs that command in the checkout of each entry of `infra.repos`,
so the devcontainer has the tools of each infra repo at the versions that the repository pins,
and devops-cli holds no second copy of those versions. The install reads the working tree of the
checkout, not the default branch at origin: it installs what the checkout uses.

A missing checkout, an invalid profile, a failed install or an install past its bound gives a
warning line, and the next repo goes on: a container start does not fail for an infra repo.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from devops_cli.config.defaults import DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS
from devops_cli.config.settings import InfraRepoConfig, Settings
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import ConfigurationError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.infra.onboard import default_checkout
from devops_cli.lang import MESSAGES
from devops_cli.project.profile import resolve_profile


def install_repo_tools(settings: Settings, *, dry_run: bool = False) -> list[str]:
    """Run the install command of each infra repo in its checkout, and give one line for each
    repo. A dry run reads the profiles and runs no command."""
    return [_install(entry, settings, dry_run=dry_run) for entry in settings.infra.repos]


def plan_repo_tools(settings: Settings) -> list[PlannedRequest]:
    """The install command of each infra repo whose checkout is a folder with a valid profile
    that names a command: the requests of `install_repo_tools`."""
    requests: list[PlannedRequest] = []
    for entry in settings.infra.repos:
        checkout = _checkout(entry, settings)
        command = _command(checkout)
        if command:
            requests.append(
                PlannedRequest(
                    method=command[0],
                    target=entry.repo,
                    argv=tuple(command),
                    condition=f"run in the checkout {checkout}",
                )
            )
    return requests


def _checkout(entry: InfraRepoConfig, settings: Settings) -> Path:
    """The `path` of the entry, else `<repos.base_dir>/<owner>/<name>`."""
    return entry.path or default_checkout(RepoRef(entry.repo), settings)


def _command(checkout: Path) -> list[str]:
    """The install command of the checkout, or none when the checkout or its profile is not
    usable."""
    if not checkout.is_dir():
        return []
    try:
        return resolve_profile(checkout).profile.tools.install
    except ConfigurationError:
        return []


def _install(entry: InfraRepoConfig, settings: Settings, *, dry_run: bool) -> str:
    texts = MESSAGES.infra
    checkout = _checkout(entry, settings)
    names = {"repo": entry.repo, "path": checkout}
    if not checkout.is_dir():
        return texts.tools_no_checkout.format(**names)
    try:
        command = resolve_profile(checkout).profile.tools.install
    except ConfigurationError as exc:
        return texts.tools_invalid_profile.format(repo=entry.repo, reason=exc.message)
    if not command:
        return texts.tools_no_command.format(**names)
    shown = shlex.join(command)
    if dry_run:
        return texts.tools_planned.format(**names, command=shown)
    return _run(command, checkout, names, shown)


def _run(command: list[str], checkout: Path, names: dict[str, object], shown: str) -> str:
    texts = MESSAGES.infra
    timeout = DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS
    try:
        result = run_subprocess(command, cwd=checkout, check=False, quiet=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return texts.tools_timed_out.format(**names, seconds=timeout)
    if result.returncode != 0:
        output = (result.stderr or result.stdout or "").strip().splitlines()
        reason = output[-1] if output else ""
        return texts.tools_failed.format(**names, code=result.returncode, reason=reason)
    return texts.tools_installed.format(**names, command=shown)


__all__ = ["install_repo_tools", "plan_repo_tools"]
