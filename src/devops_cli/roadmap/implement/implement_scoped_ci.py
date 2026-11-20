"""The scoped checks of the implement job (#3043): the checks a person runs before a push, for the
paths an item changed.

A step runs the `pre-commit` stage of the hooks at its commit (`implement_hooks.py`). The docs and
the archive commits of the job, and the rebase onto the default branch, come after the last step
and run no hook. So after the final rebase and before the push the job runs four checks over the
final tree:

- `pre-push`: the `pre-push` stage of the hooks over the commits past the default branch. It holds
  every check that the devcontainer runs on a push, and `.pre-commit-config.yaml` defines them.
- `static`: the rows of `devops ci` in `CONST_ROADMAP_IMPLEMENT_SCOPED_ROWS`, in check mode: the
  ast-grep scan, the sync of the documents and the OpenSpec gate.
- `tests`: `devops ci test` with the test modules that cover the changed sources, and the changed
  test modules. `plan_tests` selects them with the selector of `devops ci test`. The check stays
  scoped: a change to a module that most tests import selects hundreds of modules, which no Job of
  2 CPUs runs in the time limit of a command. So above `CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES`
  modules the check runs only the changed test modules. It does not run at all for a change that
  no test covers. The required checks of CI run the whole suite.
- `strength`: the strength check of the new tests (`implement_strength.py`, #3051): the assertion
  scan of the new test files, the bounded mutation run, and the coverage delta of the changed files.

This module only defines the checks and runs them. The job decides what a failure means.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from devops_cli.config.constants import (
    CONST_PRE_COMMIT_PRE_PUSH_STAGE,
    CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES,
    CONST_SOURCE_ROOT_DIR,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.test_selection import is_test_module, select_tests_for_sources
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_hooks import (
    hook_environment,
    output_text,
    pre_commit_command,
    stage_arguments,
)
from devops_cli.roadmap.runner_tools import checkout_environment
from devops_cli.roadmap.toolchains import DEVOPS_CLI_PRESET, ToolchainPreset

_TEST_MODULE_PREFIX = "test_"


@dataclass(frozen=True)
class ScopedCheck:
    """One scoped check: its name, its command line, and the variables its child gets."""

    name: str
    argv: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScopedTests:
    """What the `tests` check runs: the test modules `paths`, none when the check does not run,
    and a `note` that says why the check is narrower than the changed files, or empty."""

    paths: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class ScopedResult:
    """The end of one run of a scoped check: whether it passed, how many seconds it took, and the
    end of its output when it failed. `status` is the exit status of the command, and none when it
    ran out of time (#3032)."""

    name: str
    passed: bool
    seconds: float
    log: str = ""
    command: str = ""
    status: int | None = None


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


def plan_tests(source: Path, changed: Iterable[str]) -> ScopedTests:
    """The test modules that the `tests` check runs for the changed files `changed` of the checkout
    `source`. The selector of `devops ci test` maps the changed sources and test modules onto test
    modules. No path when no test covers the change. Above
    `CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES` modules, or for a change that forces the whole
    suite, only the changed test modules (the note says so)."""
    texts = MESSAGES.roadmap
    wanted = paths_for_tests(changed)
    if not wanted:
        return ScopedTests()
    targets = select_tests_for_sources(wanted, source).pytest_targets()
    if not targets:
        return ScopedTests(note=texts.implement_scoped_tests_uncovered)
    whole_suite = any((source / target).is_dir() for target in targets)
    if not whole_suite and len(targets) <= CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES:
        return ScopedTests(tuple(targets))
    own = tuple(name for name in wanted if is_test_module(name))
    note = texts.implement_scoped_tests_narrowed if own else texts.implement_scoped_tests_skipped
    return ScopedTests(own, note.format(limit=CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES))


def scoped_checks(
    default_branch: str,
    tests: Sequence[str],
    *,
    config: Path | None,
    preset: ToolchainPreset = DEVOPS_CLI_PRESET,
) -> list[ScopedCheck]:
    """The scoped checks of an item, against `origin/<default_branch>`, in the order they run. The
    `pre-push` check runs the hooks of the configuration `config`, and is left out when there is
    none (the repository has no hooks). The `tests` check runs the test modules `tests`, and is
    left out when there are none or the preset has no test command."""
    names = MESSAGES.roadmap.implement_scoped_names
    checks: list[ScopedCheck] = []
    if config is not None:
        pre_push = pre_commit_command(
            config,
            *stage_arguments(
                CONST_PRE_COMMIT_PRE_PUSH_STAGE,
                "--from-ref",
                f"origin/{default_branch}",
                "--to-ref",
                "HEAD",
            ),
        )
        checks.append(ScopedCheck(names["pre_push"], tuple(pre_push), hook_environment()))
    if preset.static_check is not None:
        checks.append(ScopedCheck(names["static"], tuple(preset.static_check)))
    if tests and preset.test_command is not None:
        test_argv: list[str] = []
        for word in preset.test_command:
            if word == "{tests}":
                test_argv.extend(tests)
            else:
                test_argv.append(word)
        checks.append(ScopedCheck(names["tests"], tuple(test_argv)))
    return checks


def _run_check(source: Path, check: ScopedCheck) -> ScopedResult:
    """Run one check in the checkout, outside any agent shell and with no token: the child is
    `uv`. The tools of the checkout come first on PATH (#6517). A check that runs out of time
    failed."""
    shown = " ".join(check.argv)
    limit = load_settings().roadmap.implement.command_timeout_seconds
    began = time.monotonic()
    try:
        done = run_subprocess(
            list(check.argv),
            cwd=source,
            env={**checkout_environment(source), **check.env},
            quiet=True,
            timeout=limit,
        )
    except subprocess.TimeoutExpired:
        seconds = time.monotonic() - began
        log = MESSAGES.roadmap.implement_stop_command_timeout.format(command=shown, seconds=limit)
        return ScopedResult(check.name, False, seconds, log, shown, None)
    seconds = time.monotonic() - began
    if done.returncode == 0:
        return ScopedResult(check.name, True, seconds, command=shown, status=0)
    return ScopedResult(
        check.name,
        False,
        seconds,
        output_text(done.stdout, done.stderr),
        shown,
        done.returncode,
    )


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
