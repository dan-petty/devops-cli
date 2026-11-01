"""The scoped checks of the implement job (#3043): the checks a person runs before a push, for the
paths an item changed.

A step runs the `pre-commit` stage of the hooks at its commit (`implement_hooks.py`). The docs and
the archive commits of the job, and the rebase onto the default branch, come after the last step
and run no hook. So after the final rebase and before the push the job runs three checks over the
final tree:

- `pre-push`: the `pre-push` stage of the hooks over the commits past the default branch. It holds
  every check that the devcontainer runs on a push, and `.pre-commit-config.yaml` defines them.
- `static`: the rows of `devops ci` in `CONST_ROADMAP_IMPLEMENT_SCOPED_ROWS`, in check mode: the
  ast-grep scan, the sync of the documents and the OpenSpec gate.
- `tests`: `devops ci test` with the changed sources and test modules. The command selects the
  tests that import or conventionally cover them, and `--no-fallback` keeps a path with no
  covering test from starting the whole suite. The required checks of CI run the suite.

This module only defines the checks and runs them. The job decides what a failure means.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from devops_cli.config.commands import BIN_DEVOPS, BIN_UV
from devops_cli.config.constants import (
    CONST_PRE_COMMIT_PRE_PUSH_STAGE,
    CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_SCOPED_ROWS,
    CONST_SOURCE_ROOT_DIR,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.core.process import run_subprocess
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement_hooks import (
    hook_environment,
    output_text,
    pre_commit_command,
    stage_arguments,
)

_TEST_MODULE_PREFIX = "test_"


@dataclass(frozen=True)
class ScopedCheck:
    """One scoped check: its name, its command line, and the variables its child gets."""

    name: str
    argv: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScopedResult:
    """The end of one run of a scoped check: whether it passed, how many seconds it took, and the
    end of its output when it failed."""

    name: str
    passed: bool
    seconds: float
    log: str = ""
    command: str = ""


def paths_for_tests(names: Iterable[str]) -> list[str]:
    """The paths that `devops ci test` gets from the changed `names`: a Python file under `src/`,
    and a test module under `tests/`. A helper of the tests (`conftest.py`, `tests/support/`) is
    left out: the command refuses to narrow the run for it, and the suite of CI covers it."""
    wanted: list[str] = []
    for name in names:
        path = PurePosixPath(name)
        if path.suffix != ".py" or not path.parts:
            continue
        is_source = path.parts[0] == CONST_SOURCE_ROOT_DIR
        is_test = path.parts[0] == CONST_TESTS_ROOT_DIR and path.name.startswith(
            _TEST_MODULE_PREFIX
        )
        if is_source or is_test:
            wanted.append(name)
    return wanted


def scoped_checks(default_branch: str, changed: Sequence[str]) -> list[ScopedCheck]:
    """The scoped checks of an item that changed `changed`, against `origin/<default_branch>`, in
    the order they run. The `tests` check is left out when no changed file gives a path."""
    names = MESSAGES.roadmap.implement_scoped_names
    pre_push = pre_commit_command(
        *stage_arguments(
            CONST_PRE_COMMIT_PRE_PUSH_STAGE,
            "--from-ref",
            f"origin/{default_branch}",
            "--to-ref",
            "HEAD",
        )
    )
    static = [
        BIN_UV,
        "run",
        BIN_DEVOPS,
        "ci",
        "--check",
        "--only",
        ",".join(CONST_ROADMAP_IMPLEMENT_SCOPED_ROWS),
    ]
    checks = [
        ScopedCheck(names["pre_push"], tuple(pre_push), hook_environment()),
        ScopedCheck(names["static"], tuple(static)),
    ]
    paths = paths_for_tests(changed)
    if paths:
        tests = [BIN_UV, "run", BIN_DEVOPS, "ci", "test", "--no-fallback", *paths]
        checks.append(ScopedCheck(names["tests"], tuple(tests)))
    return checks


def _run_check(source: Path, check: ScopedCheck) -> ScopedResult:
    """Run one check in the checkout, outside any agent shell and with no token: the child is
    `uv`. A check that runs out of time failed."""
    shown = " ".join(check.argv)
    began = time.monotonic()
    try:
        done = run_subprocess(
            list(check.argv),
            cwd=source,
            env=dict(check.env) or None,
            quiet=True,
            timeout=CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        seconds = time.monotonic() - began
        log = MESSAGES.roadmap.implement_stop_command_timeout.format(
            command=shown, seconds=CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS
        )
        return ScopedResult(check.name, False, seconds, log, shown)
    seconds = time.monotonic() - began
    if done.returncode == 0:
        return ScopedResult(check.name, True, seconds, command=shown)
    return ScopedResult(check.name, False, seconds, output_text(done.stdout, done.stderr), shown)


def run_scoped_checks(source: Path, checks: Sequence[ScopedCheck]) -> list[ScopedResult]:
    """Run `checks` in order in the checkout `source`, and stop at the first that fails. The
    results of the checks that ran."""
    results: list[ScopedResult] = []
    for check in checks:
        result = _run_check(source, check)
        results.append(result)
        if not result.passed:
            break
    return results
