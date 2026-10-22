"""The pinned OpenSpec, run with telemetry off under a configuration of its own (ADR 0010).

OpenSpec reports usage and asks the registry for a newer version unless told not to, and it has no
project-level profile: a developer's own `~/.config/openspec` decides which skills `update` writes.
So every run here sets the opt-outs and points `XDG_CONFIG_HOME` at a scratch directory holding the
configuration the project commits skills for: skills only, the `custom` profile, four workflows.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devops_cli.config.commands import BIN_OPENSPEC, build_openspec_cmd
from devops_cli.config.constants import (
    CONST_OPENSPEC_CONFIG_HOME_ENV,
    CONST_OPENSPEC_ISOLATED_SETTINGS,
    CONST_OPENSPEC_OPT_OUT_ENV,
)
from devops_cli.config.defaults import DEFAULT_OPENSPEC_COMMAND_TIMEOUT_SECONDS
from devops_cli.core.binaries import require_binary
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import ToolExecutionError
from devops_cli.lang import MESSAGES


def output_of(run: subprocess.CompletedProcess[str]) -> str:
    """What a command printed, standard output then standard error, each trimmed."""
    return "\n".join(part for part in (run.stdout.strip(), run.stderr.strip()) if part)


@dataclass(frozen=True)
class OpenSpecTool:
    """`openspec`, started with the opt-outs and the configuration directory `config_home`."""

    config_home: Path

    @property
    def environment(self) -> dict[str, str]:
        """The variables every run sets, over the sanitized environment `run_subprocess` builds,
        which keeps none of them."""
        return {
            **CONST_OPENSPEC_OPT_OUT_ENV,
            CONST_OPENSPEC_CONFIG_HOME_ENV: str(self.config_home),
        }

    def run(self, args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        """Run `openspec <args>` in `cwd`, whatever its exit code."""
        command = build_openspec_cmd(*args)
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


@contextmanager
def isolated_openspec() -> Iterator[OpenSpecTool]:
    """The pinned OpenSpec under a configuration of its own, held in a scratch directory that goes
    when the block ends.

    Raises `DependencyError` naming the install command when `openspec` is not on PATH.
    """
    require_binary(BIN_OPENSPEC, install_hint=MESSAGES.openspec.missing_hint)
    with tempfile.TemporaryDirectory(prefix="openspec-config-") as scratch:
        tool = OpenSpecTool(Path(scratch))
        for setting, value in CONST_OPENSPEC_ISOLATED_SETTINGS:
            tool.run_checked(["config", "set", setting, value], Path(scratch))
        yield tool
