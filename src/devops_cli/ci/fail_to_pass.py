"""Fail-to-pass replay verifying that a defect fix's tests fail on its merge base (#844).

`devops ci fail-to-pass` resolves the merge base of `--base` and `--head`, lists added or
modified `tests/**/test_*.py` files and check modules of `tests/gate/<row>_checks/`, checks out
the base tree as a detached git worktree in a temporary directory (#2197) with the head's `tests/`
overlaid, and runs those test files with the current pytest (`-n 0`, `-p no:cacheprovider`,
`--continue-on-collection-errors`, `--junitxml`), so a test file that cannot be collected on base
is reported as errored and the others still run. The run keeps the `addopts` of the tree, so a
test that reads them passes as in a normal run, and `-n 0` stops only their xdist workers (#5599).
A test that fails on base proves a change of code, so only a fix that changes source code
(`is_source_code`: a `.py` file under `src/` outside the knowledge base) or a gate check needs
one; a fix that changes neither passes with no replay (#6207). The workflow runs it only for a
fix pull request (#1879), so the command reads no title, label or body. A replay whose pytest
was interrupted, stopped with an internal or usage error, or wrote no complete JUnit report
could not run on base, and fails (#1669). A replay with a failure that the host path
guard of the test harness raised, or with a test that the fix does not change and that fails or
errors on base, proves nothing about the fix and fails too (#3124).

A changed test that errors on base at collection or setup proves the fix as a failure in the call
phase does (#6372): the replay tree holds the head's tests, so only `src/` differs, and a test that
imports or sets up the code that the fix adds errors there. An error at teardown comes after the
call phase ran and proves nothing. pytest reports the collection error of a file as one case with
no class name, named by the module path of the file. That case names the whole file, which counts
as changed when its syntax tree differs from the merge base or the file is new.

A changed check module of `tests/gate/<row>_checks/` is a gate check (#4554), unless it only
loses checks (`only_deleted_checks`). A deleted check module is no gate check either. A deleted
check runs on neither tree, so it can prove no fix, and a fix that changes no source code and only
deletes checks needs no proof (#6456). For each row of the gate checks, the command runs the gate
module `tests.gate.<row>` once on the base tree with the head's `tests/` and once on the head
tree, and reads the failed cases that `tests/gate/runner.py` prints. Each run imports
`devops_cli` from the `src/` of its own tree (#5353). A case of a changed check module that fails
on base and passes on head proves the fix, when both trees run the same cases. A row run that could not run, or a base failure of a check module that the fix does
not change, proves nothing and fails the replay.

The run exits non-zero unless no replay fails and at least one changed test fails on base, or
errors there at collection or setup, or a gate case proves the fix. The report names each changed
test that proves the fix.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path, PurePath, PurePosixPath

from pydantic import BaseModel, ConfigDict

from devops_cli.ci.changed_tests import (
    ParsedTests,
    deleted_module_checks,
    is_file_changed,
    is_test_changed,
    only_deleted_checks,
    parse_tests,
)
from devops_cli.config.constants import (
    CONST_FAIL_TO_PASS_COULD_NOT_RUN_EXIT_STATUSES,
    CONST_FAIL_TO_PASS_GATE_ROW_EXIT_STATUSES,
    CONST_FAIL_TO_PASS_GATE_ROW_SCRIPT,
    CONST_FAIL_TO_PASS_HOST_PATH_GUARD_MESSAGE,
    CONST_FAIL_TO_PASS_JUNIT_ROOT_TAG,
    CONST_FAIL_TO_PASS_JUNIT_TAG_STATUS,
    CONST_FAIL_TO_PASS_PROOF_ERROR_MESSAGES,
    CONST_FAIL_TO_PASS_PYTEST_FLAGS,
    CONST_GATE_CHECKS_PACKAGE_SUFFIX,
    CONST_GATE_DIR,
    CONST_GATE_MODULE_ROWS,
    CONST_GIT_NAME_STATUS_CHANGE_TYPES,
    CONST_KNOWLEDGE_BASE_DIR,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_PYTHON_FILE_SUFFIX,
    CONST_PYTHON_PACKAGE_INIT_FILE,
    CONST_SOURCE_ROOT_DIR,
    CONST_TEST_FILE_PREFIX,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest, both
from devops_cli.exceptions import GitOperationError
from devops_cli.git.operations import (
    cat_file_argv,
    diff_name_status_argv,
    list_changed_files,
    ls_tree_argv,
    merge_base_argv,
    read_file_at_revision,
    resolve_merge_base,
)
from devops_cli.lang import MESSAGES

_DELETED = CONST_GIT_NAME_STATUS_CHANGE_TYPES["D"]
# The statuses of a test that does not pass on base: a failure in the call phase, or an error at
# collection, setup or teardown (#6372).
_NOT_PASSED = frozenset({"failed", "errored"})
# The JUnit message prefix for each pytest error phase (#6372, #6400).
_ERROR_PHASES: dict[str, str] = {
    **dict(zip(CONST_FAIL_TO_PASS_PROOF_ERROR_MESSAGES, ("collection", "setup"), strict=True)),
    "failed on teardown with": "teardown",
}
_PROOF_ERROR_PHASES = frozenset({"collection", "setup"})
# The last line that `tests/gate/runner.py` prints for a row: `<row>: <N> cases, <M> failed`.
_GATE_ROW_SUMMARY = re.compile(
    r"^(?P<row>\S+): (?P<cases>\d+) cases, (?P<failed>\d+) failed$", re.MULTILINE
)


class TestCaseOutcome(BaseModel):
    """Per-test result from replaying a test file against the base tree."""

    model_config = ConfigDict(frozen=True)

    classname: str
    name: str
    status: str
    message: str = ""

    @property
    def test_id(self) -> str:
        """The test's qualified identifier (`classname::name`, or `name` when ungrouped)."""
        return f"{self.classname}::{self.name}" if self.classname else self.name

    @property
    def error_phase(self) -> str | None:
        """The pytest phase of an errored outcome (`collection`, `setup`, or `teardown`), or
        None (#6400)."""
        if self.status != "errored":
            return None
        return next(
            (phase for prefix, phase in _ERROR_PHASES.items() if self.message.startswith(prefix)),
            None,
        )

    @property
    def proves_fix(self) -> bool:
        """Whether this outcome of a changed test on base proves the fix: a failure in the call
        phase, or an error at collection or setup, where the test cannot import or set up the code
        that the fix adds. An error at teardown comes after the call phase ran, so it proves nothing
        (#6372)."""
        return self.status == "failed" or self.error_phase in _PROOF_ERROR_PHASES


class ReplayCouldNotRun(BaseModel):
    """A replay whose pytest stopped before it reported the changed tests on base (#1669).

    `timeout_seconds` names the process-runner limit when pytest ran out of time, so the report
    says so instead of printing a pytest exit status that pytest did not return (#4938)."""

    model_config = ConfigDict(frozen=True)

    exit_status: int
    output_tail: str = ""
    timeout_seconds: float | None = None


class BaseReplayRun(BaseModel):
    """What pytest reported for the test files of one replay on base: the outcome of each test,
    pytest's exit status, and why the run could not run, when it could not (#3042)."""

    model_config = ConfigDict(frozen=True)

    outcomes: tuple[TestCaseOutcome, ...]
    exit_status: int
    could_not_run: ReplayCouldNotRun | None = None


class GateRowRun(BaseModel):
    """What one run of a gate row printed: its case count and the ID of each failed case (#4554)."""

    model_config = ConfigDict(frozen=True)

    cases: int
    failed: tuple[str, ...] = ()


class GateRowReplay(BaseModel):
    """The runs of one gate row on the base and head trees, and the changed check modules of the
    row (#4554). A run that could not run keeps its exit status and the tail of its output."""

    model_config = ConfigDict(frozen=True)

    row: str
    check_modules: tuple[str, ...]
    base: GateRowRun | ReplayCouldNotRun
    head: GateRowRun | ReplayCouldNotRun

    @property
    def runs(self) -> tuple[GateRowRun, GateRowRun] | None:
        """The base and head runs, or None when a run could not run."""
        if isinstance(self.base, GateRowRun) and isinstance(self.head, GateRowRun):
            return self.base, self.head
        return None

    @property
    def same_cases(self) -> bool:
        """Whether both runs ran and counted the same cases."""
        return (runs := self.runs) is not None and runs[0].cases == runs[1].cases

    def _in_changed_module(self, case: str) -> bool:
        """Whether `case`, `<module>.<check>[<label>]`, is a case of a changed check module."""
        changed = {PurePosixPath(path).stem for path in self.check_modules}
        return case.partition(".")[0] in changed

    @property
    def proved(self) -> tuple[str, ...]:
        """The cases of a changed check module that fail on base and not on head, when both runs
        count the same cases."""
        if (runs := self.runs) is None or not self.same_cases:
            return ()
        base, head = runs
        return tuple(
            case
            for case in base.failed
            if self._in_changed_module(case) and case not in head.failed
        )

    @property
    def unchanged_failed(self) -> tuple[str, ...]:
        """The cases that fail on base in a check module that the fix does not change."""
        if not isinstance(self.base, GateRowRun):
            return ()
        return tuple(case for case in self.base.failed if not self._in_changed_module(case))

    @property
    def refused(self) -> bool:
        """Whether the row proves nothing about the fix: a run could not run, the two runs count
        other cases, or a check module that the fix does not change fails on base."""
        return not self.same_cases or bool(self.unchanged_failed)


class GateModuleRun(BaseModel):
    """The problem lines that one run of a changed gate module wrote to stderr (#4596)."""

    model_config = ConfigDict(frozen=True)

    problems: tuple[str, ...] = ()


class GateModuleReplay(BaseModel):
    """The runs of one changed module directly under `tests/gate/` on the base and head trees
    (#4596). `row` is None when no `devops ci` row runs the module."""

    model_config = ConfigDict(frozen=True)

    module: str
    row: str | None = None
    base: GateModuleRun | ReplayCouldNotRun | None = None
    head: GateModuleRun | ReplayCouldNotRun | None = None

    @property
    def runs(self) -> tuple[GateModuleRun, GateModuleRun] | None:
        """The base and head runs, or None when a run could not run."""
        if isinstance(self.base, GateModuleRun) and isinstance(self.head, GateModuleRun):
            return self.base, self.head
        return None

    @property
    def proved(self) -> tuple[str, ...]:
        """The problem lines on base that appear on no line of head."""
        if (runs := self.runs) is None:
            return ()
        base, head = runs
        head_set = set(head.problems)
        return tuple(line for line in base.problems if line not in head_set)

    @property
    def head_only(self) -> tuple[str, ...]:
        """The problem lines on head that appear on no line of base."""
        if (runs := self.runs) is None:
            return ()
        base, head = runs
        base_set = set(base.problems)
        return tuple(line for line in head.problems if line not in base_set)

    @property
    def no_base_problem(self) -> bool:
        """Whether the base run wrote no problem line."""
        return isinstance(self.base, GateModuleRun) and not self.base.problems

    @property
    def refused(self) -> bool:
        """Whether the module proves nothing: no CI row runs it, a run could not run, the base
        run had no problem line, or head wrote a problem line that base did not."""
        return self.row is None or self.runs is None or self.no_base_problem or bool(self.head_only)


class FailToPassReport(BaseModel):
    """Outcome of replaying changed tests against the merge-base tree, and of the gate rows of
    the changed gate checks on the base and head trees (#4554)."""

    model_config = ConfigDict(frozen=True)

    merge_base: str
    head: str
    changed_test_files: tuple[str, ...]
    outcomes: tuple[TestCaseOutcome, ...]
    could_not_run: ReplayCouldNotRun | None = None
    unchanged_failed: tuple[str, ...] = ()
    changed_gate_checks: tuple[str, ...] = ()
    changed_gate_modules: tuple[str, ...] = ()
    gate_rows: tuple[GateRowReplay, ...] = ()
    gate_modules: tuple[GateModuleReplay, ...] = ()
    repaired: tuple[TestCaseOutcome, ...] = ()
    head_could_not_run: ReplayCouldNotRun | None = None
    # False when the fix changes no source code and no gate check, so no test needs to fail on base
    # (#6207).
    needs_proof: bool = True
    # The checks that the gate check modules that only lose checks delete, as `<module>.<check>`.
    # A deleted check runs on neither tree, so it proves nothing and needs no proof (#6456).
    deleted_gate_checks: tuple[str, ...] = ()

    @property
    def failed_count(self) -> int:
        """Number of tests that failed in the call phase on base."""
        return sum(1 for outcome in self.outcomes if outcome.status == "failed")

    @property
    def proof(self) -> tuple[str, ...]:
        """The test IDs of the changed tests that fail on base, or that error there at collection
        or setup, which prove the fix (#6372). A test that the fix does not change, or that the head
        repairs, proves nothing."""
        excluded = set(self.unchanged_failed) | {outcome.test_id for outcome in self.repaired}
        return tuple(
            dict.fromkeys(
                outcome.test_id
                for outcome in self.outcomes
                if outcome.proves_fix and outcome.test_id not in excluded
            )
        )

    @property
    def passed_count(self) -> int:
        """Number of tests that passed on base."""
        return sum(1 for outcome in self.outcomes if outcome.status == "passed")

    @property
    def errored_count(self) -> int:
        """Number of collection or fixture setup/teardown errors on base."""
        return sum(1 for outcome in self.outcomes if outcome.status == "errored")

    @property
    def host_path_guard_failures(self) -> tuple[TestCaseOutcome, ...]:
        """The failures and errors that the host path guard of the test harness raised (#3124)."""
        return tuple(
            outcome
            for outcome in self.outcomes
            if outcome.status in _NOT_PASSED
            and CONST_FAIL_TO_PASS_HOST_PATH_GUARD_MESSAGE in outcome.message
        )

    @property
    def tests_refused(self) -> bool:
        """Whether the test replay proves nothing about the fix: it could not run, a failure comes
        from the host path guard of the test harness, or a test that the fix does not change fails
        or errors on base (#3124)."""
        return (
            self.could_not_run is not None
            or self.head_could_not_run is not None
            or bool(self.host_path_guard_failures)
            or bool(self.unchanged_failed)
        )

    @property
    def satisfied(self) -> bool:
        """Whether the fail-to-pass gate is satisfied: no replay refuses the fix, and at least one
        changed test fails on base, or errors there at collection or setup (#6372), or a gate case
        of a changed check module fails on base and passes on head (#4554). A fix that changes no
        source code and no gate check needs neither (#6207). A check module that only loses
        checks is no changed gate check (#6456)."""
        if not self.needs_proof:
            return True
        if (
            self.tests_refused
            or any(row.refused for row in self.gate_rows)
            or any(module.refused for module in self.gate_modules)
        ):
            return False
        return (
            bool(self.proof)
            or any(row.proved for row in self.gate_rows)
            or any(module.proved for module in self.gate_modules)
        )


class _JUnitHTMLParser(HTMLParser):
    """Lightweight JUnit XML testcase reader built on stdlib HTMLParser."""

    def __init__(self) -> None:
        super().__init__()
        self.outcomes: list[TestCaseOutcome] = []
        self._current_case: tuple[str, str] | None = None
        self._current_status: str = "passed"
        self._current_message: str = ""
        self.root_closed = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: (val or "") for key, val in attrs}
        if tag == "testcase" and self._current_case is None:
            self._current_case = (attr_map.get("classname", ""), attr_map.get("name", ""))
            self._current_status = "passed"
            self._current_message = ""
        elif self._current_case is not None and tag in CONST_FAIL_TO_PASS_JUNIT_TAG_STATUS:
            self._current_status = CONST_FAIL_TO_PASS_JUNIT_TAG_STATUS[tag]
            raw_msg = attr_map.get("message", "").strip()
            self._current_message = raw_msg.splitlines()[0].strip() if raw_msg else ""

    def handle_endtag(self, tag: str) -> None:
        self.root_closed = self.root_closed or tag == CONST_FAIL_TO_PASS_JUNIT_ROOT_TAG
        if tag == "testcase" and self._current_case is not None:
            classname, name = self._current_case
            self.outcomes.append(
                TestCaseOutcome(
                    classname=classname,
                    name=name,
                    status=self._current_status,
                    message=self._current_message,
                )
            )
            self._current_case = None


def parse_junit_xml(xml_text: str) -> tuple[TestCaseOutcome, ...]:
    """Parse pytest `--junitxml` output into per-test outcomes."""
    parser = _JUnitHTMLParser()
    parser.feed(xml_text)
    return tuple(parser.outcomes)


def is_test_file(path: PurePosixPath) -> bool:
    """Whether `path` is a `tests/**/test_*.py` file."""
    return (
        path.is_relative_to(CONST_TESTS_ROOT_DIR)
        and path.suffix == CONST_PYTHON_FILE_SUFFIX
        and path.name.startswith(CONST_TEST_FILE_PREFIX)
    )


def is_source_code(path: PurePosixPath) -> bool:
    """Whether `path` is source code: a `.py` file under `src/` outside the knowledge base, whose
    change a test that fails on base can prove (#6207). A prompt, a tool pin or lockfile, a
    template or other data under `src/` is no code: a validator or a check command proves it,
    never a test of its values."""
    return (
        path.is_relative_to(CONST_SOURCE_ROOT_DIR)
        and path.suffix == CONST_PYTHON_FILE_SUFFIX
        and not path.is_relative_to(CONST_KNOWLEDGE_BASE_DIR)
    )


def is_gate_check(path: PurePosixPath) -> bool:
    """Whether `path` is a check module directly under `tests/gate/<row>_checks/` (#4554)."""
    package = path.parent
    return (
        package.parent == PurePosixPath(CONST_GATE_DIR)
        and package.name.endswith(CONST_GATE_CHECKS_PACKAGE_SUFFIX)
        and package.name != CONST_GATE_CHECKS_PACKAGE_SUFFIX
        and path.suffix == CONST_PYTHON_FILE_SUFFIX
        and path.name != CONST_PYTHON_PACKAGE_INIT_FILE
    )


def is_gate_module(path: PurePosixPath) -> bool:
    """Whether `path` is a module directly under `tests/gate/` (#4596)."""
    return (
        path.parent == PurePosixPath(CONST_GATE_DIR)
        and path.suffix == CONST_PYTHON_FILE_SUFFIX
        and path.name != CONST_PYTHON_PACKAGE_INIT_FILE
    )


def gate_row_of(path: str) -> str:
    """The gate row that runs the check module at `path`: the name of its package without
    `_checks`, so a module of `tests/gate/k8s_checks/` belongs to the row `k8s`."""
    return PurePosixPath(path).parent.name.removesuffix(CONST_GATE_CHECKS_PACKAGE_SUFFIX)


class ChangedTests(BaseModel):
    """The merge base of a replay, and the changed files that can prove the fix on it."""

    model_config = ConfigDict(frozen=True)

    merge_base: str
    test_files: tuple[str, ...]
    gate_checks: tuple[str, ...] = ()
    gate_modules: tuple[str, ...] = ()
    source_files: tuple[str, ...] = ()
    # The checks that the fix deletes, as `<module>.<check>`: from each changed gate check module
    # that only loses checks, and from each deleted gate check module. Neither module is in
    # `gate_checks` (#6456).
    deleted_checks: tuple[str, ...] = ()


def verify_commit_argv(revision: str) -> list[str]:
    """The command that checks that `revision` names a commit."""
    return ["git", "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"]


def untracked_tests_argv() -> list[str]:
    """The command that lists the untracked files under `tests/`."""
    return ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", CONST_TESTS_ROOT_DIR]


def worktree_add_argv(dest: PurePath | str, revision: str) -> list[str]:
    """The command that checks out `revision` at `dest` as a detached worktree."""
    return ["git", "worktree", "add", "--quiet", "--detach", str(dest), revision]


def archive_argv(tar_path: PurePath | str, archive_args: Sequence[str]) -> list[str]:
    """The command that writes the tar archive of `archive_args` to `tar_path`."""
    return ["git", "archive", "--format=tar", f"--output={tar_path}", *archive_args]


def tests_archive_args(head: str) -> list[str]:
    """What `git archive` takes for the `tests/` tree of `head`."""
    return [head, "--", CONST_TESTS_ROOT_DIR]


def worktree_remove_argv(dest: PurePath | str) -> list[str]:
    """The command that removes the worktree at `dest`."""
    return ["git", "worktree", "remove", "--force", str(dest)]


def worktree_prune_argv() -> list[str]:
    """The command that prunes the records of removed worktrees."""
    return ["git", "worktree", "prune"]


def _verify_commit(root: Path, revision: str) -> None:
    """Verify `revision` resolves to a commit in `root`, raising `GitOperationError` otherwise."""
    if run_subprocess(verify_commit_argv(revision), cwd=root, quiet=True).returncode != 0:
        raise GitOperationError(MESSAGES.ci.mutate_base_missing.format(base=revision))


def _untracked_files(root: Path) -> list[str]:
    """The untracked files under `tests/` in the working tree."""
    listed = run_subprocess(untracked_tests_argv(), cwd=root, quiet=True).stdout
    return list(filter(None, listed.split("\0")))


def _head_source(root: Path, head: str, path: str) -> str | None:
    """The text of `path` at `head`: in the working tree for `HEAD`, as the replay overlays the
    tests of the working tree, else at the revision `head`."""
    if head != "HEAD":
        return read_file_at_revision(root, head, path)
    head_file = root / path
    return head_file.read_text(encoding="utf-8") if head_file.is_file() else None


def _deleted_checks_by_module(
    root: Path, merge_base: str, head: str, gate_checks: Sequence[str]
) -> dict[str, tuple[str, ...]]:
    """The checks that each module of `gate_checks` deletes, for the modules that only lose checks
    (#6456)."""
    deleted: dict[str, tuple[str, ...]] = {}
    for path in gate_checks:
        if checks := only_deleted_checks(
            PurePosixPath(path).stem,
            read_file_at_revision(root, merge_base, path),
            _head_source(root, head, path),
        ):
            deleted[path] = checks
    return deleted


def changed_tests(root: Path, base: str, head: str = "HEAD") -> ChangedTests:
    """Resolve the merge base of `base` and `head`, and list the added or modified
    `tests/**/test_*.py` files, check modules of `tests/gate/<row>_checks/` and source files.
    A check module that only loses checks is no changed gate check, and a deleted check module is
    none either: the result names their deleted checks instead (#6456)."""
    if (merge_base := resolve_merge_base(root, base, head)) is None:
        raise GitOperationError(MESSAGES.ci.mutate_base_refused.format(base=base))
    _verify_commit(root, base)
    _verify_commit(root, head)
    diff_head = None if head == "HEAD" else head
    changes = list_changed_files(root, merge_base, diff_head)
    tracked = [change.path for change in changes if change.change_type != _DELETED]
    untracked = _untracked_files(root) if head == "HEAD" else []
    paths = sorted(set(tracked) | set(untracked))
    gate_checks = [path for path in paths if is_gate_check(PurePosixPath(path))]
    deleted = _deleted_checks_by_module(root, merge_base, head, gate_checks)
    for change in changes:
        if change.change_type == _DELETED and is_gate_check(PurePosixPath(change.path)):
            deleted[change.path] = deleted_module_checks(
                PurePosixPath(change.path).stem,
                read_file_at_revision(root, merge_base, change.path),
            )
    return ChangedTests(
        merge_base=merge_base,
        test_files=tuple(path for path in paths if is_test_file(PurePosixPath(path))),
        gate_checks=tuple(path for path in gate_checks if path not in deleted),
        gate_modules=tuple(path for path in paths if is_gate_module(PurePosixPath(path))),
        source_files=tuple(path for path in paths if is_source_code(PurePosixPath(path))),
        deleted_checks=tuple(check for path in sorted(deleted) for check in deleted[path]),
    )


def _archive_to_dir(root: Path, archive_args: list[str], tar_path: Path, dest: Path) -> None:
    """Write a git tar archive for `archive_args` and extract it safely into `dest`."""
    res = run_subprocess(archive_argv(tar_path, archive_args), cwd=root, quiet=True)
    if res.returncode == 0 and tar_path.is_file():
        with tarfile.open(tar_path) as archive:
            archive.extractall(dest, filter="data")


def _add_worktree(root: Path, revision: str, dest: Path) -> None:
    """Check out `revision` in `dest` as a detached git worktree of `root`."""
    add = worktree_add_argv(dest, revision)
    if (res := run_subprocess(add, cwd=root, quiet=True)).returncode != 0:
        raise GitOperationError(
            MESSAGES.ci.fail_to_pass_worktree_failed.format(
                base=revision, detail=(res.stderr or "").strip()
            )
        )


def materialise_base_with_head_tests(root: Path, merge_base: str, head: str, dest: Path) -> None:
    """Check out `merge_base` in `dest` as a detached git worktree of `root`, with `head`'s
    `tests/` overlaid, so a test that runs `git` there works as in the checkout (#2197).

    `remove_materialised_base` removes the worktree.
    """
    _add_worktree(root, merge_base, dest)
    _archive_to_dir(root, tests_archive_args(head), dest.parent / "tests.tar", dest)
    if head == "HEAD" and (root / CONST_TESTS_ROOT_DIR).is_dir():
        shutil.copytree(
            root / CONST_TESTS_ROOT_DIR, dest / CONST_TESTS_ROOT_DIR, dirs_exist_ok=True
        )


def remove_materialised_base(root: Path, dest: Path) -> None:
    """Remove the worktree `materialise_base_with_head_tests` added at `dest`."""
    run_subprocess(worktree_remove_argv(dest), cwd=root, quiet=True)
    run_subprocess(worktree_prune_argv(), cwd=root, quiet=True)


@contextmanager
def _plain_base_tree(root: Path, merge_base: str, dest: Path) -> Iterator[Path]:
    """A detached git worktree of `merge_base` with no head tests overlaid."""
    _add_worktree(root, merge_base, dest)
    try:
        yield dest
    finally:
        remove_materialised_base(root, dest)


@contextmanager
def _head_tree(root: Path, head: str, dest: Path) -> Iterator[Path]:
    """The head tree: the working tree for `HEAD`, else a detached worktree at `dest`."""
    if head == "HEAD":
        yield root
    else:
        _add_worktree(root, head, dest)
        try:
            yield dest
        finally:
            remove_materialised_base(root, dest)


def pytest_replay_argv(
    junit_path: Path, test_files: Sequence[str], *, python: str = sys.executable
) -> list[str]:
    """Construct the pytest argv for replaying `test_files` against the materialised base tree,
    with the interpreter `python`: this command's, or the venv of the checkout of a runner Job,
    whose own venv holds no pytest (#6688)."""
    return [
        python,
        "-m",
        "pytest",
        *CONST_FAIL_TO_PASS_PYTEST_FLAGS,
        f"--junitxml={junit_path}",
        *test_files,
    ]


def gate_row_argv(row: str) -> list[str]:
    """The command that runs the gate row `row` with the interpreter of this command (#4554).

    The editable install of the interpreter finds `devops_cli` in the `src/` of the checkout that
    runs this command. The script puts the `src/` of the folder that it runs in first on the import
    path, so the row of each tree imports the source of that tree (#5353)."""
    return [sys.executable, "-c", CONST_FAIL_TO_PASS_GATE_ROW_SCRIPT.format(module=row)]


def gate_module_argv(module: str) -> list[str]:
    """The command that runs the changed gate module `module` inside a tree (#4596)."""
    return gate_row_argv(PurePosixPath(module).stem)


def gate_row_of_module(path: str) -> str | None:
    """The `devops ci` row whose command runs the gate module at `path`, or None when none does
    (#4596)."""
    return CONST_GATE_MODULE_ROWS.get(PurePosixPath(path).stem)


MERGE_BASE_PLACEHOLDER = "<merge-base>"
TEMP_DIR_PLACEHOLDER = "<temp-dir>"
CHANGED_TESTS_PLACEHOLDER = "<changed test files>"
BLOB_PLACEHOLDER = "<blob of the changed test file>"
GATE_ROW_PLACEHOLDER = "<gate row>"
GATE_MODULE_PLACEHOLDER = "<changed gate check module>"
CHANGED_GATE_MODULE_PLACEHOLDER = "<changed gate module>"
GATE_BLOB_PLACEHOLDER = "<blob of the changed gate check module>"
GATE_MODULE_READ = "a module of tests/gate/*_checks/ changes"
EACH_GATE_MODULE = "for each changed module of tests/gate/*_checks/"
GATE_BASE_READ = "a module of tests/gate/*_checks/ changes or is deleted"
EACH_BASE_GATE_MODULE = "for each changed or deleted module of tests/gate/*_checks/"
UNCHANGED_CHECK = "a test that failed or errored on base is in a changed test file"
TEST_REPLAY = "a changed test file exists and the fix changes source code or a gate check"
GATE_REPLAY = "a changed gate check exists"
EACH_GATE_ROW = "for each row of a changed gate check"
GATE_MODULE_REPLAY = "a module of tests/gate/ changes and a devops ci row runs it"
EACH_GATE_MODULE_ROW = "for each changed module of tests/gate/ that a devops ci row runs"
UNCHANGED_REPLAY = "a test that failed or errored on base is unchanged"
HEAD_RUN = "a changed gate check exists or a test that failed or errored on base is unchanged"
UNCHANGED_TESTS_PLACEHOLDER = "<unchanged test files>"


def plan_fail_to_pass(base: str, head: str = "HEAD") -> list[PlannedRequest]:
    """The processes that `run_fail_to_pass` starts, in order, with no git call made: the
    merge base, the commits, the changed test files and the gate rows are placeholders. The
    base tree exists only when a changed test file or gate check exists, pytest runs only for a
    changed test file, and a gate row runs on each tree only for a changed gate check (#4554).
    The text of each changed check module at the merge base, and at a named head, tells whether
    the module only loses checks. The text of a deleted check module at the merge base names its
    checks (#6456)."""
    diff_head = None if head == "HEAD" else head
    tmp = PurePosixPath(TEMP_DIR_PLACEHOLDER)
    tree = tmp / "tree"
    replay = (
        "the fix changes source code and a changed test file exists, or a changed gate check exists"
    )

    def git(argv: list[str], condition: str = "") -> PlannedRequest:
        return PlannedRequest(method="git", target=argv[1], argv=tuple(argv), condition=condition)

    def gate_row(target: str) -> PlannedRequest:
        return PlannedRequest(
            method="gate row",
            target=target,
            argv=tuple(gate_row_argv(GATE_ROW_PLACEHOLDER)),
            condition=GATE_REPLAY,
            repeat=EACH_GATE_ROW,
        )

    def gate_module_run(target: str) -> PlannedRequest:
        return PlannedRequest(
            method="gate module",
            target=target,
            argv=tuple(gate_module_argv(CHANGED_GATE_MODULE_PLACEHOLDER)),
            condition=GATE_MODULE_REPLAY,
            repeat=EACH_GATE_MODULE_ROW,
        )

    def module_read(
        revision: str, holder: str, condition: str, repeat: str
    ) -> list[PlannedRequest]:
        return [
            PlannedRequest(
                method="git",
                target="ls-tree",
                argv=tuple(ls_tree_argv(revision, GATE_MODULE_PLACEHOLDER)),
                condition=condition,
                repeat=repeat,
            ),
            PlannedRequest(
                method="git",
                target="cat-file",
                argv=tuple(cat_file_argv(GATE_BLOB_PLACEHOLDER)),
                condition=both(condition, f"{holder} holds it"),
                repeat=repeat,
            ),
        ]

    def head_pytest(target: str) -> PlannedRequest:
        return PlannedRequest(
            method="pytest",
            target=target,
            argv=tuple(pytest_replay_argv(Path(tmp / "junit.xml"), [UNCHANGED_TESTS_PLACEHOLDER])),
            condition=UNCHANGED_REPLAY,
        )

    requests = [
        git(merge_base_argv(base, head)),
        git(verify_commit_argv(base)),
        git(verify_commit_argv(head)),
        git(diff_name_status_argv(MERGE_BASE_PLACEHOLDER, diff_head)),
    ]
    if diff_head is not None:
        requests.append(
            git(
                diff_name_status_argv(MERGE_BASE_PLACEHOLDER, diff_head, fallback=True),
                condition="the three-dot diff fails",
            )
        )
    else:
        requests.append(git(untracked_tests_argv()))
    requests += module_read(
        MERGE_BASE_PLACEHOLDER, "the merge base", GATE_BASE_READ, EACH_BASE_GATE_MODULE
    )
    if diff_head is not None:
        requests += module_read(diff_head, "the head", GATE_MODULE_READ, EACH_GATE_MODULE)
    gate_base = tmp / "gate_base"
    requests += [
        git(worktree_add_argv(gate_base, MERGE_BASE_PLACEHOLDER), GATE_MODULE_REPLAY),
        gate_module_run(str(gate_base)),
        git(worktree_remove_argv(gate_base), GATE_MODULE_REPLAY),
        git(worktree_prune_argv(), GATE_MODULE_REPLAY),
    ]
    if diff_head is None:
        requests.append(gate_module_run("the working tree"))
    else:
        gate_head = tmp / "gate_head"
        requests += [
            git(worktree_add_argv(gate_head, diff_head), GATE_MODULE_REPLAY),
            gate_module_run(str(gate_head)),
            git(worktree_remove_argv(gate_head), GATE_MODULE_REPLAY),
            git(worktree_prune_argv(), GATE_MODULE_REPLAY),
        ]
    requests += [
        git(worktree_add_argv(tree, MERGE_BASE_PLACEHOLDER), replay),
        git(archive_argv(tmp / "tests.tar", tests_archive_args(head)), replay),
        PlannedRequest(
            method="pytest",
            target=str(tree),
            argv=tuple(pytest_replay_argv(Path(tmp / "junit.xml"), [CHANGED_TESTS_PLACEHOLDER])),
            condition=TEST_REPLAY,
        ),
        PlannedRequest(
            method="git",
            target="ls-tree",
            argv=tuple(ls_tree_argv(MERGE_BASE_PLACEHOLDER, CHANGED_TESTS_PLACEHOLDER)),
            condition=both(TEST_REPLAY, UNCHANGED_CHECK),
        ),
        git(cat_file_argv(BLOB_PLACEHOLDER), both(TEST_REPLAY, UNCHANGED_CHECK)),
        gate_row(str(tree)),
        git(worktree_remove_argv(tree), replay),
        git(worktree_prune_argv(), replay),
    ]
    if diff_head is None:
        return [
            *requests,
            head_pytest("the working tree"),
            gate_row("the working tree"),
        ]
    head_tree = tmp / "head"
    return [
        *requests,
        git(worktree_add_argv(head_tree, diff_head), HEAD_RUN),
        head_pytest(str(head_tree)),
        gate_row(str(head_tree)),
        git(worktree_remove_argv(head_tree), HEAD_RUN),
        git(worktree_prune_argv(), HEAD_RUN),
    ]


def _output_tail(output: str) -> str:
    """The last whole lines of `output` that fit in `CONST_MAX_ERROR_DETAIL_LENGTH` characters,
    or the end of its last line when that line alone is longer."""
    printed = "\n".join(line.rstrip() for line in output.splitlines() if line.strip())
    if len(printed) <= CONST_MAX_ERROR_DETAIL_LENGTH:
        return printed
    whole_lines = printed[-CONST_MAX_ERROR_DETAIL_LENGTH - 1 :].partition("\n")[2]
    return whole_lines or printed[-CONST_MAX_ERROR_DETAIL_LENGTH:]


def _read_junit_report(junit_path: Path) -> tuple[TestCaseOutcome, ...] | None:
    """The outcomes of the JUnit report at `junit_path`, or None when pytest wrote none, or left
    one empty or cut short, never closing its root element (#1669)."""
    if not junit_path.is_file():
        return None
    parser = _JUnitHTMLParser()
    parser.feed(junit_path.read_text(encoding="utf-8", errors="replace"))
    return tuple(parser.outcomes) if parser.root_closed else None


def _run_pytest_replay(
    tree_dir: Path, junit_path: Path, test_files: Sequence[str], *, python: str = sys.executable
) -> BaseReplayRun:
    """Run pytest on `test_files` inside `tree_dir` and parse its JUnit XML report.

    A run pytest interrupted, stopped with an internal or usage error, or that wrote no complete
    report could not run, and keeps pytest's exit status and the tail of its output (#1669). A run
    that passes the process-runner limit could not run either, and names that limit (#4938).
    """
    argv = pytest_replay_argv(junit_path, test_files, python=python)
    try:
        result = run_subprocess(argv, cwd=tree_dir, capture_output=True)
    except subprocess.TimeoutExpired:
        return BaseReplayRun(
            outcomes=(),
            exit_status=1,
            could_not_run=ReplayCouldNotRun(
                exit_status=1,
                timeout_seconds=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            ),
        )
    outcomes = _read_junit_report(junit_path)
    if (
        outcomes is not None
        and result.returncode not in CONST_FAIL_TO_PASS_COULD_NOT_RUN_EXIT_STATUSES
    ):
        return BaseReplayRun(outcomes=outcomes, exit_status=result.returncode)
    output = _output_tail(f"{result.stdout or ''}\n{result.stderr or ''}")
    return BaseReplayRun(
        outcomes=outcomes or (),
        exit_status=result.returncode,
        could_not_run=ReplayCouldNotRun(exit_status=result.returncode, output_tail=output),
    )


def replay_on_base(
    root: Path,
    merge_base: str,
    head: str,
    test_files: Sequence[str],
    *,
    python: str = sys.executable,
) -> BaseReplayRun:
    """Replay `test_files` on `merge_base`, with the tests of `head` overlaid, and report the
    outcome of each test with the pytest of `python`. The base tree is removed after the run
    (#3042)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tree_dir = tmp_path / "tree"
        try:
            materialise_base_with_head_tests(root, merge_base, head, tree_dir)
            return _run_pytest_replay(tree_dir, tmp_path / "junit.xml", test_files, python=python)
        finally:
            remove_materialised_base(root, tree_dir)


def _test_location(
    outcome: TestCaseOutcome, files: Sequence[str]
) -> tuple[str, tuple[str, ...], str] | None:
    """The changed test file, the class names and the function name that `outcome` names, or
    None when it names no changed test file. The JUnit class name is the file's module path, then
    the classes of the test, and a parametrized test's name ends in its case id. A collection
    error of a file has no class name and the file's module path as its name: it names the whole
    file, with no class and an empty function name (#6372)."""
    name = outcome.name.partition("[")[0]
    for path in files:
        module = PurePosixPath(path).with_suffix("").as_posix().replace("/", ".")
        if not outcome.classname and outcome.name == module:
            return path, (), ""
        if outcome.classname == module:
            return path, (), name
        if outcome.classname.startswith(f"{module}."):
            return path, tuple(outcome.classname.removeprefix(f"{module}.").split(".")), name
    return None


def _unchanged_failures(
    root: Path,
    merge_base: str,
    tree_dir: Path,
    files: Sequence[str],
    outcomes: Sequence[TestCaseOutcome],
) -> tuple[str, ...]:
    """The test ids of the tests that failed or errored on base though the fix leaves them alone
    (#3124).

    A test is unchanged when its function in the replay tree, which holds the head's tests, has the
    syntax tree of the function in the merge base. A collection error names its whole file, which
    is unchanged when the file has the syntax tree of the file in the merge base (#6372). A test
    that is not in a changed file, or that either source does not show, counts as changed.
    """
    parses: dict[str, tuple[ParsedTests | None, ParsedTests | None]] = {}
    unchanged: list[str] = []
    for outcome in outcomes:
        if (
            outcome.status not in _NOT_PASSED
            or (location := _test_location(outcome, files)) is None
        ):
            continue
        path, classes, name = location
        if path not in parses:
            head_file = tree_dir / path
            head_source = head_file.read_text(encoding="utf-8") if head_file.is_file() else None
            base_source = (
                read_file_at_revision(root, merge_base, path) if head_source is not None else None
            )
            parses[path] = (parse_tests(base_source), parse_tests(head_source))
        changed = (
            is_test_changed(classes, name, *parses[path])
            if name
            else is_file_changed(*parses[path])
        )
        if not changed:
            unchanged.append(outcome.test_id)
    return tuple(dict.fromkeys(unchanged))


def _files_holding(
    ids: Sequence[str], outcomes: Sequence[TestCaseOutcome], files: Sequence[str]
) -> tuple[str, ...]:
    """The changed test files that hold the tests named by `ids`."""
    id_set = set(ids)
    holding: list[str] = []
    for outcome in outcomes:
        if outcome.test_id in id_set and (location := _test_location(outcome, files)) is not None:
            path, _, _ = location
            if path not in holding:
                holding.append(path)
    return tuple(holding)


def _file_outcomes(outcomes: Sequence[TestCaseOutcome], module: str) -> list[TestCaseOutcome]:
    """Every outcome in `outcomes` that belongs to the module `module` (#6400)."""
    prefix = f"{module}."
    return [
        outcome
        for outcome in outcomes
        if outcome.classname == module
        or outcome.classname.startswith(prefix)
        or (not outcome.classname and outcome.name == module)
    ]


def _repaired_and_refused(
    unchanged: Sequence[str],
    plain_base_outcomes: Sequence[TestCaseOutcome],
    head_outcomes: Sequence[TestCaseOutcome],
) -> tuple[tuple[TestCaseOutcome, ...], tuple[str, ...]]:
    """Split the `unchanged` test IDs that do not pass on base into repaired outcomes and refused
    test IDs.

    A test is repaired only when it fails or errors on the plain merge base and passes on the head.
    A file-level collection error on the plain merge base is repaired when the head report holds at
    least one case for that module and every head case of that module passes (#6400). An unchanged
    test that passes on the plain merge base or that does not pass on the head is refused.
    """
    plain_map = {o.test_id: o for o in plain_base_outcomes}
    head_map = {o.test_id: o for o in head_outcomes}
    repaired: list[TestCaseOutcome] = []
    refused: list[str] = []
    for test_id in unchanged:
        pb = plain_map.get(test_id)
        if pb is None or pb.status not in _NOT_PASSED:
            refused.append(test_id)
            continue
        if "::" not in test_id and not pb.classname:
            file_head = _file_outcomes(head_outcomes, test_id)
            if file_head and all(outcome.status == "passed" for outcome in file_head):
                repaired.append(pb.model_copy(update={"status": "passed", "message": ""}))
            else:
                refused.append(test_id)
            continue
        h = head_map.get(test_id)
        if h is not None and h.status == "passed":
            repaired.append(h)
        else:
            refused.append(test_id)
    return tuple(repaired), tuple(refused)


def parse_gate_row_output(status: int, stdout: str, stderr: str) -> GateRowRun | None:
    """The case count and the failed cases that a run of a gate row printed, or None when the run
    could not run: it exited with a status other than 0 or 1, or printed no case summary. The
    runner prints `<row>: <case> failed:` for each failed case and `<row>: <N> cases, <M> failed`
    last (#4554)."""
    summaries = list(_GATE_ROW_SUMMARY.finditer(stdout))
    if status not in CONST_FAIL_TO_PASS_GATE_ROW_EXIT_STATUSES or not summaries:
        return None
    summary = summaries[-1]
    prefix, suffix = f"{summary['row']}: ", " failed:"
    failed = (
        line.removeprefix(prefix).removesuffix(suffix)
        for line in stderr.splitlines()
        if line.startswith(prefix) and line.endswith(suffix)
    )
    return GateRowRun(cases=int(summary["cases"]), failed=tuple(dict.fromkeys(failed)))


def _run_gate_row(tree: Path, row: str) -> GateRowRun | ReplayCouldNotRun:
    """Run the gate row `row` in `tree`, and read the cases that it printed (#4554)."""
    try:
        result = run_subprocess(gate_row_argv(row), cwd=tree, capture_output=True)
    except subprocess.TimeoutExpired:
        return ReplayCouldNotRun(exit_status=1, timeout_seconds=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
    stdout, stderr = result.stdout or "", result.stderr or ""
    if (run := parse_gate_row_output(result.returncode, stdout, stderr)) is not None:
        return run
    return ReplayCouldNotRun(
        exit_status=result.returncode, output_tail=_output_tail(f"{stdout}\n{stderr}")
    )


def _run_gate_module(tree: Path, module: str) -> GateModuleRun | ReplayCouldNotRun:
    """Run the changed gate module `module` in `tree` and collect its stderr lines (#4596)."""
    try:
        result = run_subprocess(gate_module_argv(module), cwd=tree, capture_output=True)
    except subprocess.TimeoutExpired:
        return ReplayCouldNotRun(exit_status=1, timeout_seconds=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
    stdout, stderr = result.stdout or "", result.stderr or ""
    if result.returncode in CONST_FAIL_TO_PASS_GATE_ROW_EXIT_STATUSES:
        problems = tuple(dict.fromkeys(line for line in stderr.splitlines() if line))
        return GateModuleRun(problems=problems)
    return ReplayCouldNotRun(
        exit_status=result.returncode, output_tail=_output_tail(f"{stdout}\n{stderr}")
    )


def _replay_gate_modules(
    root: Path,
    merge_base: str,
    head: str,
    tmp_path: Path,
    modules: Sequence[str],
) -> tuple[GateModuleReplay, ...]:
    """Replay each changed module directly under `tests/gate/` on plain base and head trees
    (#4596)."""
    if not modules:
        return ()
    owned = [(path, gate_row_of_module(path)) for path in modules]
    runnable = [(path, row) for path, row in owned if row is not None]
    base_runs: dict[str, GateModuleRun | ReplayCouldNotRun] = {}
    head_runs: dict[str, GateModuleRun | ReplayCouldNotRun] = {}
    if runnable:
        with _plain_base_tree(root, merge_base, tmp_path / "gate_base") as base_dir:
            base_runs = {path: _run_gate_module(base_dir, path) for path, _ in runnable}
        with _head_tree(root, head, tmp_path / "gate_head") as head_dir:
            head_runs = {path: _run_gate_module(head_dir, path) for path, _ in runnable}
    return tuple(
        GateModuleReplay(
            module=path,
            row=row,
            base=base_runs.get(path),
            head=head_runs.get(path),
        )
        for path, row in owned
    )


def _run_gate_rows_on_head(
    root: Path, head: str, rows: Sequence[str], dest: Path
) -> dict[str, GateRowRun | ReplayCouldNotRun]:
    """Run each gate row on the head tree: the working tree for `HEAD`, so a change that is not
    committed counts, else a detached worktree of `head` at `dest`, removed after the runs."""
    if head == "HEAD":
        return {row: _run_gate_row(root, row) for row in rows}
    _add_worktree(root, head, dest)
    try:
        return {row: _run_gate_row(dest, row) for row in rows}
    finally:
        remove_materialised_base(root, dest)


def _check_modules_by_row(gate_checks: Sequence[str]) -> dict[str, tuple[str, ...]]:
    """The changed check modules of each gate row, the rows in name order."""
    rows: dict[str, list[str]] = {}
    for path in gate_checks:
        rows.setdefault(gate_row_of(path), []).append(path)
    return {row: tuple(rows[row]) for row in sorted(rows)}


def _replay_tests(
    root: Path, merge_base: str, tree_dir: Path, test_files: Sequence[str]
) -> tuple[BaseReplayRun | None, tuple[str, ...]]:
    """Run pytest on `test_files` in the base tree, and list the tests that fail on base though
    the fix does not change them. No changed test file starts no pytest."""
    if not test_files:
        return None, ()
    run = _run_pytest_replay(tree_dir, tree_dir.parent / "junit.xml", test_files)
    if run.could_not_run is not None:
        return run, ()
    return run, _unchanged_failures(root, merge_base, tree_dir, test_files, run.outcomes)


def _replay_plain_and_head(
    root: Path,
    merge_base: str,
    head: str,
    tmp_path: Path,
    changed_test_files: Sequence[str],
    unchanged_failed: tuple[str, ...],
    run: BaseReplayRun,
    rows: Sequence[str],
) -> tuple[
    tuple[TestCaseOutcome, ...],
    ReplayCouldNotRun | None,
    ReplayCouldNotRun | None,
    tuple[str, ...],
    dict[str, GateRowRun | ReplayCouldNotRun],
]:
    """Replay the files that hold an unchanged failure on the plain base and the head, and run the
    gate rows. A timeout on the plain base or the head keeps the could-not-run result (#4938)."""
    repaired: tuple[TestCaseOutcome, ...] = ()
    head_could_not_run: ReplayCouldNotRun | None = None
    base_could_not_run = run.could_not_run
    replay_files = _files_holding(unchanged_failed, run.outcomes, changed_test_files)
    with _plain_base_tree(root, merge_base, tmp_path / "plain_base") as plain_dir:
        plain_run = _run_pytest_replay(plain_dir, tmp_path / "plain_junit.xml", replay_files)
    if plain_run.could_not_run is not None:
        with _head_tree(root, head, tmp_path / "head") as head_dir:
            head_runs = {row: _run_gate_row(head_dir, row) for row in rows}
        return repaired, head_could_not_run, plain_run.could_not_run, unchanged_failed, head_runs
    with _head_tree(root, head, tmp_path / "head") as head_dir:
        head_run = _run_pytest_replay(head_dir, tmp_path / "head_junit.xml", replay_files)
        if head_run.could_not_run is not None:
            head_could_not_run = head_run.could_not_run
            refused = unchanged_failed
        else:
            repaired, refused = _repaired_and_refused(
                unchanged_failed, plain_run.outcomes, head_run.outcomes
            )
        head_runs = {row: _run_gate_row(head_dir, row) for row in rows}
    return repaired, head_could_not_run, base_could_not_run, refused, head_runs


def run_fail_to_pass(root: Path, *, base: str, head: str = "HEAD") -> FailToPassReport:
    """Replay the changed `tests/**/test_*.py` files against the merge-base tree, and run the
    gate row of each changed gate check on the base and head trees (#4554)."""
    changed = changed_tests(root, base, head)
    if not changed.source_files and not changed.gate_checks and not changed.gate_modules:
        return FailToPassReport(
            merge_base=changed.merge_base,
            head=head,
            changed_test_files=changed.test_files,
            outcomes=(),
            needs_proof=False,
            deleted_gate_checks=changed.deleted_checks,
        )
    if not changed.test_files and not changed.gate_checks and not changed.gate_modules:
        return FailToPassReport(
            merge_base=changed.merge_base,
            head=head,
            changed_test_files=(),
            outcomes=(),
            deleted_gate_checks=changed.deleted_checks,
        )
    rows = _check_modules_by_row(changed.gate_checks)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        gate_modules = _replay_gate_modules(
            root, changed.merge_base, head, tmp_path, changed.gate_modules
        )
        tree_dir = tmp_path / "tree"
        if changed.test_files or rows:
            try:
                materialise_base_with_head_tests(root, changed.merge_base, head, tree_dir)
                run, unchanged_failed = _replay_tests(
                    root, changed.merge_base, tree_dir, changed.test_files
                )
                base_runs = {row: _run_gate_row(tree_dir, row) for row in rows}
            finally:
                remove_materialised_base(root, tree_dir)
        else:
            run, unchanged_failed, base_runs = None, (), {}

        repaired: tuple[TestCaseOutcome, ...] = ()
        head_could_not_run: ReplayCouldNotRun | None = None
        base_could_not_run = run.could_not_run if run is not None else None
        has_guard_failure = run is not None and any(
            outcome.status in _NOT_PASSED
            and CONST_FAIL_TO_PASS_HOST_PATH_GUARD_MESSAGE in outcome.message
            for outcome in run.outcomes
        )
        if run is not None and unchanged_failed and not has_guard_failure:
            (
                repaired,
                head_could_not_run,
                base_could_not_run,
                unchanged_failed,
                head_runs,
            ) = _replay_plain_and_head(
                root,
                changed.merge_base,
                head,
                tmp_path,
                changed.test_files,
                unchanged_failed,
                run,
                list(rows),
            )
        elif rows:
            with _head_tree(root, head, tmp_path / "head") as head_dir:
                head_runs = {row: _run_gate_row(head_dir, row) for row in rows}
        else:
            head_runs = {}

    return FailToPassReport(
        merge_base=changed.merge_base,
        head=head,
        changed_test_files=changed.test_files,
        outcomes=run.outcomes if run else (),
        could_not_run=base_could_not_run,
        unchanged_failed=unchanged_failed,
        changed_gate_checks=changed.gate_checks,
        changed_gate_modules=changed.gate_modules,
        gate_rows=tuple(
            GateRowReplay(row=row, check_modules=modules, base=base_runs[row], head=head_runs[row])
            for row, modules in rows.items()
        ),
        gate_modules=gate_modules,
        repaired=repaired,
        head_could_not_run=head_could_not_run,
        deleted_gate_checks=changed.deleted_checks,
    )


def _could_not_run_lines(could_not_run: ReplayCouldNotRun, files: str) -> list[str]:
    """The report's lines for a replay of `files` that could not run on base (#1669, #4938)."""
    if could_not_run.timeout_seconds is not None:
        reason = MESSAGES.ci.fail_to_pass_replay_timeout.format(
            seconds=could_not_run.timeout_seconds, files=files
        )
    else:
        reason = MESSAGES.ci.fail_to_pass_could_not_run.format(
            status=could_not_run.exit_status, files=files
        )
    if not could_not_run.output_tail:
        return [reason]
    return [reason, MESSAGES.ci.fail_to_pass_replay_output.format(output=could_not_run.output_tail)]


def _gate_error_lines(
    runs: tuple[tuple[str, object], ...],
    timeout_template: str,
    status_template: str,
    **target: str,
) -> list[str]:
    """Format timeout, exit status and tail output for gate runs that could not run."""
    lines: list[str] = []
    for tree, run in runs:
        if not isinstance(run, ReplayCouldNotRun):
            continue
        if run.timeout_seconds is not None:
            lines.append(timeout_template.format(tree=tree, seconds=run.timeout_seconds, **target))
            continue
        lines.append(status_template.format(tree=tree, status=run.exit_status, **target))
        if run.output_tail:
            lines.append(MESSAGES.ci.fail_to_pass_gate_output.format(output=run.output_tail))
    return lines


def _gate_row_lines(row: GateRowReplay) -> list[str]:
    """The report's lines for the runs of one gate row: the cases that prove the fix and the
    counts of the two runs, or why a run could not run (#4554)."""
    if (runs := row.runs) is None:
        return _gate_error_lines(
            (("base", row.base), ("head", row.head)),
            MESSAGES.ci.fail_to_pass_gate_timeout,
            MESSAGES.ci.fail_to_pass_gate_could_not_run,
            row=row.row,
        )
    base, head = runs
    return [
        *(
            MESSAGES.ci.fail_to_pass_gate_proved.format(row=row.row, case=case)
            for case in row.proved
        ),
        MESSAGES.ci.fail_to_pass_gate_summary.format(
            row=row.row,
            base_failed=len(base.failed),
            base_cases=base.cases,
            head_failed=len(head.failed),
            head_cases=head.cases,
            modules=", ".join(row.check_modules),
        ),
    ]


def _gate_module_lines(module: GateModuleReplay) -> list[str]:
    """The report's lines for one changed gate module directly under `tests/gate/` (#4596)."""
    if module.row is None:
        return [MESSAGES.ci.fail_to_pass_gate_module_no_row.format(module=module.module)]
    if (runs := module.runs) is None:
        return _gate_error_lines(
            (("base", module.base), ("head", module.head)),
            MESSAGES.ci.fail_to_pass_gate_module_timeout,
            MESSAGES.ci.fail_to_pass_gate_module_could_not_run,
            module=module.module,
        )
    base, head = runs
    return [
        *(
            MESSAGES.ci.fail_to_pass_gate_module_proved.format(module=module.module, line=line)
            for line in module.proved
        ),
        MESSAGES.ci.fail_to_pass_gate_module_summary.format(
            module=module.module,
            row=module.row,
            base_problems=len(base.problems),
            head_problems=len(head.problems),
        ),
    ]


def _gate_refusals(report: FailToPassReport) -> list[str]:
    """The sentences that tell the author why the gate rows that ran refuse the fix (#4554)."""
    reasons = [
        MESSAGES.ci.fail_to_pass_gate_case_count.format(
            row=row.row, base_cases=runs[0].cases, head_cases=runs[1].cases
        )
        for row in report.gate_rows
        if (runs := row.runs) is not None and not row.same_cases
    ]
    unchanged = [f"{row.row} {case}" for row in report.gate_rows for case in row.unchanged_failed]
    if unchanged:
        reasons.append(
            MESSAGES.ci.fail_to_pass_gate_unchanged_failed.format(cases=", ".join(unchanged))
        )
    return reasons


def _gate_module_refusals(report: FailToPassReport) -> list[str]:
    """The sentences that tell the author why changed gate modules refuse the fix (#4596)."""
    reasons: list[str] = []
    for module in report.gate_modules:
        if module.no_base_problem:
            reasons.append(
                MESSAGES.ci.fail_to_pass_gate_module_no_base_problem.format(module=module.module)
            )
        if module.head_only:
            reasons.append(
                MESSAGES.ci.fail_to_pass_gate_module_head_only.format(
                    module=module.module, lines=", ".join(module.head_only)
                )
            )
    return reasons


def _unsatisfied_reasons(report: FailToPassReport, files_label: str) -> list[str]:
    """The sentences that tell the author why a replay that ran does not satisfy the gate. A
    replay that could not run has its own lines, and adds no sentence."""
    if (
        not report.changed_test_files
        and not report.changed_gate_checks
        and not report.changed_gate_modules
    ):
        return [MESSAGES.ci.fail_to_pass_no_tests]
    if (
        report.could_not_run is not None
        or any(row.runs is None for row in report.gate_rows)
        or any(module.runs is None for module in report.gate_modules)
    ):
        return []
    if report.host_path_guard_failures:
        guarded = dict.fromkeys(outcome.test_id for outcome in report.host_path_guard_failures)
        return [MESSAGES.ci.fail_to_pass_guard_failed.format(tests=", ".join(guarded))]
    if report.head_could_not_run is not None:
        if report.head_could_not_run.timeout_seconds is not None:
            return [
                MESSAGES.ci.fail_to_pass_head_timeout.format(
                    seconds=report.head_could_not_run.timeout_seconds, files=files_label
                )
            ]
        return [
            MESSAGES.ci.fail_to_pass_head_could_not_run.format(
                status=report.head_could_not_run.exit_status
            )
        ]
    if report.unchanged_failed:
        return [
            MESSAGES.ci.fail_to_pass_unchanged_failed.format(
                tests=", ".join(report.unchanged_failed)
            )
        ]
    if refusals := _gate_refusals(report) + _gate_module_refusals(report):
        return refusals
    return _none_proved_reasons(report, files_label)


def _none_proved_reasons(report: FailToPassReport, files_label: str) -> list[str]:
    """Explain when changed tests, gate checks or gate modules all ran without proving the fix."""
    reasons = []
    if report.changed_test_files:
        tests_str = ", ".join(outcome.test_id for outcome in report.outcomes) or files_label
        reasons.append(MESSAGES.ci.fail_to_pass_none_failed.format(tests=tests_str))
    if report.changed_gate_checks:
        reasons.append(
            MESSAGES.ci.fail_to_pass_gate_none_proved.format(
                modules=", ".join(report.changed_gate_checks)
            )
        )
    if report.changed_gate_modules:
        reasons.append(
            MESSAGES.ci.fail_to_pass_gate_module_none_proved.format(
                modules=", ".join(report.changed_gate_modules)
            )
        )
    return reasons


def format_fail_to_pass_report(report: FailToPassReport) -> str:
    """Format a human-readable per-test, per-gate-row and summary report for
    `devops ci fail-to-pass`."""
    if not report.needs_proof:
        if report.deleted_gate_checks:
            return MESSAGES.ci.fail_to_pass_deleted_checks.format(
                checks=", ".join(report.deleted_gate_checks)
            )
        return MESSAGES.ci.fail_to_pass_no_source
    lines = [
        MESSAGES.ci.fail_to_pass_test_line.format(
            status=outcome.status,
            test_id=outcome.test_id,
            detail=f" ({outcome.message})" if outcome.message else "",
        )
        for outcome in report.outcomes
    ]
    if report.repaired:
        lines.append(
            MESSAGES.ci.fail_to_pass_repaired.format(
                tests=", ".join(outcome.test_id for outcome in report.repaired)
            )
        )
    files_label = (
        ", ".join(report.changed_test_files)
        if report.changed_test_files
        else "no changed test files"
    )
    if report.could_not_run is not None:
        lines += _could_not_run_lines(report.could_not_run, files_label)
    elif report.changed_test_files or (
        not report.changed_gate_checks and not report.changed_gate_modules
    ):
        lines.append(
            MESSAGES.ci.fail_to_pass_summary.format(
                failed=report.failed_count,
                passed=report.passed_count,
                errored=report.errored_count,
                files=files_label,
            )
        )
    for row in report.gate_rows:
        lines += _gate_row_lines(row)
    for module in report.gate_modules:
        lines += _gate_module_lines(module)
    if not report.satisfied:
        lines += _unsatisfied_reasons(report, files_label)
    elif report.proof:
        lines.append(MESSAGES.ci.fail_to_pass_proof.format(tests=", ".join(report.proof)))
    return "\n".join(lines)
