"""The fetch step for the databases that a sandboxed review binds read-only (#2131).

A review runs osv-scanner and Trivy in a sandbox with no network. They read the databases that a
step with a network got before: this one. The tools do the download. This module chooses what to
fetch and where, and starts the tools outside the sandbox.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from devops_cli.config.commands import (
    BIN_OSV_SCANNER,
    BIN_TRIVY,
    build_osv_fetch_cmd,
    build_trivy_checks_fetch_cmd,
    build_trivy_db_fetch_cmd,
)
from devops_cli.config.constants import CONST_OSV_DB_FILE_NAME, CONST_OSV_FETCH_OK_EXIT_CODES
from devops_cli.config.defaults import DEFAULT_TOOL_DATABASE_FETCH_TIMEOUT_SECONDS
from devops_cli.core.binaries import require_binary
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.tools import ToolExecutionError
from devops_cli.lang import MESSAGES
from devops_cli.security.base import ToolDataDir
from devops_cli.security.osv_scanner import lockfiles_of, osv_data_dir, report_ecosystems
from devops_cli.security.trivy import trivy_data_dir

# Stands for the empty directory that the Trivy checks fetch makes, in a plan that starts nothing.
_EMPTY_DIRECTORY = "<empty-directory>"


@dataclass(frozen=True)
class FetchedDatabase:
    """A database that a fetch got: the tool, the directory the tool wrote, and the ecosystems of
    osv-scanner that it fetched (none for Trivy)."""

    tool: str
    directory: Path
    ecosystems: tuple[str, ...] = ()


def plan_database_fetches(tree: Path) -> list[PlannedRequest]:
    """The commands that `fetch_databases` would start for `tree`, each with the directory
    variable of its tool. osv-scanner has none when `tree` holds no lockfile."""
    plan: list[PlannedRequest] = []
    if lockfiles := lockfiles_of(tree):
        plan.append(_planned(osv_data_dir(), build_osv_fetch_cmd(lockfiles)))
    trivy = trivy_data_dir()
    plan.append(_planned(trivy, build_trivy_db_fetch_cmd()))
    plan.append(_planned(trivy, build_trivy_checks_fetch_cmd(_EMPTY_DIRECTORY)))
    return plan


def _planned(data_dir: ToolDataDir, command: list[str]) -> PlannedRequest:
    """The planned start of `command` with the variable of `data_dir`."""
    return PlannedRequest(
        method="EXEC",
        target=command[0],
        argv=tuple(command),
        env=((data_dir.variable, str(data_dir.directory)),),
    )


def _start(command: list[str], data_dir: ToolDataDir) -> subprocess.CompletedProcess[str]:
    """Run `command` outside the sandbox, with the directory variable of its tool."""
    return run_subprocess(
        command,
        env={data_dir.variable: str(data_dir.directory)},
        timeout=DEFAULT_TOOL_DATABASE_FETCH_TIMEOUT_SECONDS,
    )


def _failure(tool: str, proc: subprocess.CompletedProcess[str]) -> str:
    """Why the fetch of `tool` failed: its exit code and the last line it printed on stderr."""
    detail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
    return MESSAGES.review.databases_fetch_failed.format(
        tool=tool, code=proc.returncode, detail=detail[0]
    )


def _fetch_osv(lockfiles: list[Path]) -> FetchedDatabase:
    """Download the offline database of each ecosystem that `lockfiles` use, and set the modified
    time of each database file that the run confirmed. osv-scanner rewrites a file only when
    upstream changed it, and the age of a database counts from its modified time."""
    require_binary(BIN_OSV_SCANNER)
    data_dir = osv_data_dir()
    proc = _start(build_osv_fetch_cmd(lockfiles), data_dir)
    if proc.returncode not in CONST_OSV_FETCH_OK_EXIT_CODES:
        raise ToolExecutionError(
            _failure(BIN_OSV_SCANNER, proc), tool_name=BIN_OSV_SCANNER, exit_code=1
        )
    try:
        ecosystems = report_ecosystems(json.loads(proc.stdout))
    except ValueError as exc:
        raise ToolExecutionError(
            _failure(BIN_OSV_SCANNER, proc), tool_name=BIN_OSV_SCANNER, exit_code=1
        ) from exc
    fetched: list[str] = []
    for ecosystem in ecosystems:
        database = data_dir.read / ecosystem / CONST_OSV_DB_FILE_NAME
        if database.is_file():
            os.utime(database)
            fetched.append(ecosystem)
    return FetchedDatabase(BIN_OSV_SCANNER, data_dir.read, tuple(fetched))


def _fetch_trivy() -> FetchedDatabase:
    """Download the vulnerability database of Trivy and its checks bundle."""
    require_binary(BIN_TRIVY)
    data_dir = trivy_data_dir()
    with tempfile.TemporaryDirectory(prefix="devops-trivy-checks-") as empty:
        for command in (build_trivy_db_fetch_cmd(), build_trivy_checks_fetch_cmd(empty)):
            proc = _start(command, data_dir)
            if proc.returncode != 0:
                raise ToolExecutionError(
                    _failure(BIN_TRIVY, proc), tool_name=BIN_TRIVY, exit_code=1
                )
    return FetchedDatabase(BIN_TRIVY, data_dir.read)


def fetch_databases(tree: Path) -> tuple[list[FetchedDatabase], list[ToolExecutionError]]:
    """Fetch the databases that a review of `tree` binds read-only, and answer what was fetched
    and what failed. A failure of one tool does not skip the other. A tree with no lockfile gets
    no osv-scanner fetch, and the answer for osv-scanner then names no ecosystem."""
    fetched: list[FetchedDatabase] = []
    failed: list[ToolExecutionError] = []
    lockfiles = lockfiles_of(tree)
    steps: list[Callable[[], FetchedDatabase]] = [_fetch_trivy]
    if lockfiles:
        steps.insert(0, lambda: _fetch_osv(lockfiles))
    else:
        fetched.append(FetchedDatabase(BIN_OSV_SCANNER, osv_data_dir().read))
    for step in steps:
        try:
            fetched.append(step())
        except ToolExecutionError as exc:
            failed.append(exc)
    return fetched, failed
