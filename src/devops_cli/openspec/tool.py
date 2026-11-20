"""The pinned OpenSpec, run with telemetry off under a configuration of its own (ADR 0010).

The `package-lock.json` at the root of a checkout pins OpenSpec as a devDependency, and
`npm ci --ignore-scripts` links it into `node_modules/.bin` (#6409). A run in a checkout starts
that binary when it is there, so an `openspec` on PATH, such as the one of the devtools image, has
no effect on it; else it starts the `openspec` on PATH.

OpenSpec reports usage and asks the registry for a newer version unless told not to, and it has no
project-level profile: a developer's own `~/.config/openspec` decides which skills `update` writes.
So every run here sets the opt-outs and points `XDG_CONFIG_HOME` at a scratch directory holding the
configuration the project commits skills for: the `custom` profile, four workflows. The directory is
also the home of the run, because OpenSpec 2.1 refreshes the skills it finds under the home with the
profile of the run.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devops_cli.config.commands import BIN_OPENSPEC, build_openspec_cmd
from devops_cli.config.constants import (
    CONST_NPM_BIN_DIR,
    CONST_NPM_LOCKFILE,
    CONST_OPENSPEC_CONFIG_HOME_ENV,
    CONST_OPENSPEC_HOME_ENV,
    CONST_OPENSPEC_ISOLATED_SETTINGS,
    CONST_OPENSPEC_LOCK_KEY,
    CONST_OPENSPEC_OPT_OUT_ENV,
)
from devops_cli.config.defaults import DEFAULT_OPENSPEC_COMMAND_TIMEOUT_SECONDS
from devops_cli.core.binaries import require_binary
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import ToolExecutionError
from devops_cli.lang import MESSAGES

# The arguments of the run that lists the active changes.
LIST_ARGS: tuple[str, ...] = ("list", "--json")


def isolated_environment(config_home: str) -> dict[str, str]:
    """The variables of a run under the configuration directory `config_home`: the opt-outs, and
    the directory as the configuration directory and as the home."""
    return {
        **CONST_OPENSPEC_OPT_OUT_ENV,
        CONST_OPENSPEC_CONFIG_HOME_ENV: config_home,
        CONST_OPENSPEC_HOME_ENV: config_home,
    }


def settings_args() -> list[tuple[str, ...]]:
    """The arguments of the `config set` runs that make the isolated configuration, in order."""
    return [
        ("config", "set", setting, value) for setting, value in CONST_OPENSPEC_ISOLATED_SETTINGS
    ]


def output_of(run: subprocess.CompletedProcess[str]) -> str:
    """What a command printed, standard output then standard error, each trimmed."""
    return "\n".join(part for part in (run.stdout.strip(), run.stderr.strip()) if part)


def locked_version(root: Path) -> str | None:
    """The version of OpenSpec that the `package-lock.json` of the checkout at `root` pins, or None
    when the checkout has no such lockfile or the lockfile holds no OpenSpec."""
    lockfile = root / CONST_NPM_LOCKFILE
    if not lockfile.is_file():
        return None
    package = json.loads(lockfile.read_text(encoding="utf-8")).get("packages", {})
    version = package.get(CONST_OPENSPEC_LOCK_KEY, {}).get("version")
    return str(version) if version else None


def installed_program(root: Path) -> Path:
    """Where `npm ci --ignore-scripts` links `openspec` in the checkout at `root`."""
    return root / CONST_NPM_BIN_DIR / BIN_OPENSPEC


@dataclass(frozen=True)
class OpenSpecTool:
    """`openspec`, started with the opt-outs and the configuration directory `config_home`.
    `program` is the bare name that PATH resolves, or the path of the binary of a checkout."""

    config_home: Path
    program: str = BIN_OPENSPEC

    @property
    def path(self) -> str:
        """The binary that a run starts: the path of the binary of a checkout, else the `openspec`
        that PATH resolves, or the bare name when PATH resolves none."""
        if self.program != BIN_OPENSPEC:
            return self.program
        return shutil.which(BIN_OPENSPEC) or BIN_OPENSPEC

    @property
    def environment(self) -> dict[str, str]:
        """The variables every run sets, over the sanitized environment `run_subprocess` builds,
        which keeps none of them."""
        return isolated_environment(str(self.config_home))

    def run(self, args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        """Run `openspec <args>` in `cwd`, whatever its exit code."""
        command = [self.program, *args]
        try:
            return run_subprocess(
                command,
                cwd=cwd,
                env=self.environment,
                quiet=True,
                timeout=DEFAULT_OPENSPEC_COMMAND_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolExecutionError(
                MESSAGES.openspec.command_timed_out.format(
                    command=" ".join(command),
                    timeout=f"{DEFAULT_OPENSPEC_COMMAND_TIMEOUT_SECONDS:g}s",
                ),
                tool_name=BIN_OPENSPEC,
            ) from exc

    def run_checked(self, args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        """Run `openspec <args>` in `cwd` and raise when it exits non-zero."""
        run = self.run(args, cwd)
        if run.returncode != 0:
            raise ToolExecutionError(
                MESSAGES.openspec.command_failed.format(
                    command=" ".join(build_openspec_cmd(*args)),
                    code=run.returncode,
                    reason=output_of(run)[:256],
                ),
                tool_name=BIN_OPENSPEC,
            )
        return run

    def read_json(self, args: Sequence[str], cwd: Path) -> Any:
        """The JSON `openspec <args>` printed, raising when it fails or prints something else."""
        run = self.run_checked(args, cwd)
        try:
            return json.loads(run.stdout)
        except ValueError as exc:
            raise ToolExecutionError(
                MESSAGES.openspec.command_failed.format(
                    command=" ".join(build_openspec_cmd(*args)),
                    code=run.returncode,
                    reason=f"not JSON: {run.stdout[:128]}",
                ),
                tool_name=BIN_OPENSPEC,
            ) from exc


def active_changes(tool: OpenSpecTool, directory: Path) -> list[str]:
    """The name of each active change under `directory`, in the order OpenSpec lists them."""
    listing = tool.read_json(LIST_ARGS, directory)
    return [change["name"] for change in listing["changes"]]


@contextmanager
def isolated_openspec(root: Path | None = None) -> Iterator[OpenSpecTool]:
    """The pinned OpenSpec under a configuration of its own, held in a scratch directory that goes
    when the block ends: the binary that `npm ci` installed in the checkout at `root` when it is
    there, else the `openspec` on PATH.

    Raises `DependencyError` naming the install command when neither is there.
    """
    if root is not None and installed_program(root).is_file():
        program = str(installed_program(root))
    else:
        require_binary(BIN_OPENSPEC, install_hint=MESSAGES.openspec.missing_hint)
        program = BIN_OPENSPEC
    with tempfile.TemporaryDirectory(prefix="openspec-config-") as scratch:
        tool = OpenSpecTool(Path(scratch), program)
        for args in settings_args():
            tool.run_checked(args, Path(scratch))
        yield tool
