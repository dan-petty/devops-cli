"""Fail-to-pass replay verifying that a defect fix's tests fail on its merge base (#844).

`devops ci fail-to-pass` resolves the merge base of `--base` and `--head`, lists added or
modified `tests/**/test_*.py` files and check modules of `tests/gate/<row>_checks/`, checks out
the base tree as a detached git worktree in a temporary directory (#2197) with the head's `tests/`
overlaid, and runs those test files with the current pytest (`-o addopts=`, `-p no:cacheprovider`,
`--continue-on-collection-errors`, `--junitxml`), so a test file that cannot be collected on base
is reported as errored and the others still run. The workflow runs it only for a fix pull request
that changes `src/` or a gate check (#1879), so the command reads no title, label or body. A
replay whose pytest was interrupted, stopped with an internal or usage error, or wrote no complete
JUnit report could not run on base, and fails (#1669). A replay with a failure that the host path
guard of the test harness raised, or with a failed test that the fix does not change, proves
nothing about the fix and fails too (#3124).

A changed check module of `tests/gate/<row>_checks/` is a gate check (#4554). For each row of
these modules, the command runs the gate module `tests.gate.<row>` once on the base tree with the
head's `tests/` and once on the head tree, and reads the failed cases that `tests/gate/runner.py`
prints. Each run imports `devops_cli` from the `src/` of its own tree (#5353). A case of a
changed check module that fails on base and passes on head proves the fix, when both trees run the
same cases. A row run that could not run, or a base failure of a check module that the fix does
not change, proves nothing and fails the replay.

The run exits non-zero unless no replay fails and at least one changed test fails in the call
phase on base, or a gate case proves the fix.
"""

from __future__ import annotations

import re
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Sequence
from html.parser import HTMLParser
from pathlib import Path, PurePath, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ci.changed_tests import ParsedTests, is_test_changed, parse_tests
from devops_cli.config.constants import (
    CONST_FAIL_TO_PASS_COULD_NOT_RUN_EXIT_STATUSES,
    CONST_FAIL_TO_PASS_GATE_ROW_EXIT_STATUSES,
    CONST_FAIL_TO_PASS_GATE_ROW_SCRIPT,
    CONST_FAIL_TO_PASS_HOST_PATH_GUARD_MESSAGE,
    CONST_FAIL_TO_PASS_JUNIT_ROOT_TAG,
    CONST_FAIL_TO_PASS_JUNIT_TAG_STATUS,
    CONST_FAIL_TO_PASS_PYTEST_FLAGS,
    CONST_GATE_CHECKS_PACKAGE_SUFFIX,
    CONST_GATE_DIR,
    CONST_GIT_NAME_STATUS_CHANGE_TYPES,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_PYTHON_FILE_SUFFIX,
    CONST_PYTHON_PACKAGE_INIT_FILE,
    CONST_TEST_FILE_PREFIX,
    CONST_TESTS_ROOT_DIR,
)
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
    # The `time` of the testcase: the seconds of its setup, call and teardown, which only
    # `devops ci durations` reads, so the report of a replay leaves it out (#5247).
    seconds: float = Field(default=0.0, exclude=True)

    @property
    def test_id(self) -> str:
        """The test's qualified identifier (`classname::name`, or `name` when ungrouped)."""
        return f"{self.classname}::{self.name}" if self.classname else self.name


class ReplayCouldNotRun(BaseModel):
    """A replay whose pytest stopped before it reported the changed tests on base (#1669)."""

    model_config = ConfigDict(frozen=True)

    exit_status: int
    output_tail: str = ""


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
    gate_rows: tuple[GateRowReplay, ...] = ()

    @property
    def failed_count(self) -> int:
        """Number of tests that failed in the call phase on base."""
        return sum(1 for outcome in self.outcomes if outcome.status == "failed")

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
            if outcome.status in ("failed", "errored")
            and CONST_FAIL_TO_PASS_HOST_PATH_GUARD_MESSAGE in outcome.message
        )

    @property
    def tests_refused(self) -> bool:
        """Whether the test replay proves nothing about the fix: it could not run, a failure comes
        from the host path guard of the test harness, or a test that the fix does not change fails
        on base (#3124)."""
        return (
            self.could_not_run is not None
            or bool(self.host_path_guard_failures)
            or bool(self.unchanged_failed)
        )

    @property
    def satisfied(self) -> bool:
        """Whether the fail-to-pass gate is satisfied: no replay refuses the fix, and at least one
        changed test fails on base or a gate case of a changed check module fails on base and
        passes on head (#4554)."""
        if self.tests_refused or any(row.refused for row in self.gate_rows):
            return False
        return self.failed_count > 0 or any(row.proved for row in self.gate_rows)


class _JUnitHTMLParser(HTMLParser):
    """Lightweight JUnit XML testcase reader built on stdlib HTMLParser."""

    def __init__(self) -> None:
        super().__init__()
        self.outcomes: list[TestCaseOutcome] = []
        self._current_case: tuple[str, str] | None = None
        self._current_seconds: str = ""
        self._current_status: str = "passed"
        self._current_message: str = ""
        self.root_closed = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: (val or "") for key, val in attrs}
        if tag == "testcase" and self._current_case is None:
            self._current_case = (attr_map.get("classname", ""), attr_map.get("name", ""))
            self._current_seconds = attr_map.get("time", "")
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
                    seconds=float(self._current_seconds or 0),
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


def changed_tests(root: Path, base: str, head: str = "HEAD") -> ChangedTests:
    """Resolve the merge base of `base` and `head`, and list the added or modified
    `tests/**/test_*.py` files and check modules of `tests/gate/<row>_checks/`."""
    if (merge_base := resolve_merge_base(root, base, head)) is None:
        raise GitOperationError(MESSAGES.ci.mutate_base_refused.format(base=base))
    _verify_commit(root, base)
    _verify_commit(root, head)
    diff_head = None if head == "HEAD" else head
    tracked = [
        change.path
        for change in list_changed_files(root, merge_base, diff_head)
        if change.change_type != _DELETED
    ]
    untracked = _untracked_files(root) if head == "HEAD" else []
    paths = sorted(set(tracked) | set(untracked))
    return ChangedTests(
        merge_base=merge_base,
        test_files=tuple(path for path in paths if is_test_file(PurePosixPath(path))),
        gate_checks=tuple(path for path in paths if is_gate_check(PurePosixPath(path))),
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


def pytest_replay_argv(junit_path: Path, test_files: Sequence[str]) -> list[str]:
    """Construct the pytest argv for replaying `test_files` against the materialised base tree."""
    return [
        sys.executable,
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


MERGE_BASE_PLACEHOLDER = "<merge-base>"
TEMP_DIR_PLACEHOLDER = "<temp-dir>"
CHANGED_TESTS_PLACEHOLDER = "<changed test files>"
BLOB_PLACEHOLDER = "<blob of the changed test file>"
GATE_ROW_PLACEHOLDER = "<gate row>"
UNCHANGED_CHECK = "a test that failed on base is in a changed test file"
TEST_REPLAY = "a changed test file exists"
GATE_REPLAY = "a changed gate check exists"
EACH_GATE_ROW = "for each row of a changed gate check"


def plan_fail_to_pass(base: str, head: str = "HEAD") -> list[PlannedRequest]:
    """The processes that `run_fail_to_pass` starts, in order, with no git call made: the
    merge base, the commits, the changed test files and the gate rows are placeholders. The
    base tree exists only when a changed test file or gate check exists, pytest runs only for a
    changed test file, and a gate row runs on each tree only for a changed gate check (#4554)."""
    diff_head = None if head == "HEAD" else head
    tmp = PurePosixPath(TEMP_DIR_PLACEHOLDER)
    tree = tmp / "tree"
    replay = "a changed test file or gate check exists"

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
        return [*requests, gate_row("the working tree")]
    head_tree = tmp / "head"
    return [
        *requests,
        git(worktree_add_argv(head_tree, diff_head), GATE_REPLAY),
        gate_row(str(head_tree)),
        git(worktree_remove_argv(head_tree), GATE_REPLAY),
        git(worktree_prune_argv(), GATE_REPLAY),
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


def _run_pytest_on_base(
    tree_dir: Path, junit_path: Path, test_files: Sequence[str]
) -> BaseReplayRun:
    """Run pytest on `test_files` inside `tree_dir` and parse its JUnit XML report.

    A run pytest interrupted, stopped with an internal or usage error, or that wrote no complete
    report could not run, and keeps pytest's exit status and the tail of its output (#1669).
    """
    argv = pytest_replay_argv(junit_path, test_files)
    result = run_subprocess(argv, cwd=tree_dir, capture_output=True)
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
    root: Path, merge_base: str, head: str, test_files: Sequence[str]
) -> BaseReplayRun:
    """Replay `test_files` on `merge_base`, with the tests of `head` overlaid, and report the
    outcome of each test. The base tree is removed after the run (#3042)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tree_dir = tmp_path / "tree"
        try:
            materialise_base_with_head_tests(root, merge_base, head, tree_dir)
            return _run_pytest_on_base(tree_dir, tmp_path / "junit.xml", test_files)
        finally:
            remove_materialised_base(root, tree_dir)


def _test_location(
    outcome: TestCaseOutcome, files: Sequence[str]
) -> tuple[str, tuple[str, ...], str] | None:
    """The changed test file, the class names and the function name that `outcome` names, or
    None when it names no changed test file. The JUnit class name is the file's module path, then
    the classes of the test, and a parametrized test's name ends in its case id."""
    name = outcome.name.partition("[")[0]
    for path in files:
        module = PurePosixPath(path).with_suffix("").as_posix().replace("/", ".")
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
    """The test ids of the tests that failed on base though the fix leaves them alone (#3124).

    A test is unchanged when its function in the replay tree, which holds the head's tests, has the
    syntax tree of the function in the merge base. A failed test that is not in a changed file, or
    that either source does not show, counts as changed.
    """
    parses: dict[str, tuple[ParsedTests | None, ParsedTests | None]] = {}
    unchanged: list[str] = []
    for outcome in outcomes:
        if outcome.status != "failed" or (location := _test_location(outcome, files)) is None:
            continue
        path, classes, name = location
        if path not in parses:
            head_file = tree_dir / path
            head_source = head_file.read_text(encoding="utf-8") if head_file.is_file() else None
            base_source = (
                read_file_at_revision(root, merge_base, path) if head_source is not None else None
            )
            parses[path] = (parse_tests(base_source), parse_tests(head_source))
        if not is_test_changed(classes, name, *parses[path]):
            unchanged.append(outcome.test_id)
    return tuple(dict.fromkeys(unchanged))


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
    result = run_subprocess(gate_row_argv(row), cwd=tree, capture_output=True)
    stdout, stderr = result.stdout or "", result.stderr or ""
    if (run := parse_gate_row_output(result.returncode, stdout, stderr)) is not None:
        return run
    return ReplayCouldNotRun(
        exit_status=result.returncode, output_tail=_output_tail(f"{stdout}\n{stderr}")
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
    run = _run_pytest_on_base(tree_dir, tree_dir.parent / "junit.xml", test_files)
    if run.could_not_run is not None:
        return run, ()
    return run, _unchanged_failures(root, merge_base, tree_dir, test_files, run.outcomes)


def run_fail_to_pass(root: Path, *, base: str, head: str = "HEAD") -> FailToPassReport:
    """Replay the changed `tests/**/test_*.py` files against the merge-base tree, and run the
    gate row of each changed gate check on the base and head trees (#4554)."""
    changed = changed_tests(root, base, head)
    if not changed.test_files and not changed.gate_checks:
        return FailToPassReport(
            merge_base=changed.merge_base, head=head, changed_test_files=(), outcomes=()
        )
    rows = _check_modules_by_row(changed.gate_checks)
    with tempfile.TemporaryDirectory() as tmp:
        tree_dir = Path(tmp) / "tree"
        try:
            materialise_base_with_head_tests(root, changed.merge_base, head, tree_dir)
            run, unchanged_failed = _replay_tests(
                root, changed.merge_base, tree_dir, changed.test_files
            )
            base_runs = {row: _run_gate_row(tree_dir, row) for row in rows}
        finally:
            remove_materialised_base(root, tree_dir)
        head_runs = (
            _run_gate_rows_on_head(root, head, list(rows), Path(tmp) / "head") if rows else {}
        )
    return FailToPassReport(
        merge_base=changed.merge_base,
        head=head,
        changed_test_files=changed.test_files,
        outcomes=run.outcomes if run else (),
        could_not_run=run.could_not_run if run else None,
        unchanged_failed=unchanged_failed,
        changed_gate_checks=changed.gate_checks,
        gate_rows=tuple(
            GateRowReplay(row=row, check_modules=modules, base=base_runs[row], head=head_runs[row])
            for row, modules in rows.items()
        ),
    )


def _could_not_run_lines(could_not_run: ReplayCouldNotRun, files: str) -> list[str]:
    """The report's lines for a replay of `files` that could not run on base (#1669)."""
    reason = MESSAGES.ci.fail_to_pass_could_not_run.format(
        status=could_not_run.exit_status, files=files
    )
    if not could_not_run.output_tail:
        return [reason]
    return [reason, MESSAGES.ci.fail_to_pass_replay_output.format(output=could_not_run.output_tail)]


def _gate_row_lines(row: GateRowReplay) -> list[str]:
    """The report's lines for the runs of one gate row: the cases that prove the fix and the
    counts of the two runs, or why a run could not run (#4554)."""
    if (runs := row.runs) is None:
        lines: list[str] = []
        for tree, run in (("base", row.base), ("head", row.head)):
            if not isinstance(run, ReplayCouldNotRun):
                continue
            lines.append(
                MESSAGES.ci.fail_to_pass_gate_could_not_run.format(
                    row=row.row, tree=tree, status=run.exit_status
                )
            )
            if run.output_tail:
                lines.append(MESSAGES.ci.fail_to_pass_gate_output.format(output=run.output_tail))
        return lines
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


def _unsatisfied_reasons(report: FailToPassReport, files_label: str) -> list[str]:
    """The sentences that tell the author why a replay that ran does not satisfy the gate. A
    replay that could not run has its own lines, and adds no sentence."""
    if not report.changed_test_files and not report.changed_gate_checks:
        return [MESSAGES.ci.fail_to_pass_no_tests]
    if report.could_not_run is not None or any(row.runs is None for row in report.gate_rows):
        return []
    if report.host_path_guard_failures:
        guarded = dict.fromkeys(outcome.test_id for outcome in report.host_path_guard_failures)
        return [MESSAGES.ci.fail_to_pass_guard_failed.format(tests=", ".join(guarded))]
    if report.unchanged_failed:
        return [
            MESSAGES.ci.fail_to_pass_unchanged_failed.format(
                tests=", ".join(report.unchanged_failed)
            )
        ]
    if refusals := _gate_refusals(report):
        return refusals
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
    return reasons


def format_fail_to_pass_report(report: FailToPassReport) -> str:
    """Format a human-readable per-test, per-gate-row and summary report for
    `devops ci fail-to-pass`."""
    lines = [
        MESSAGES.ci.fail_to_pass_test_line.format(
            status=outcome.status,
            test_id=outcome.test_id,
            detail=f" ({outcome.message})" if outcome.message else "",
        )
        for outcome in report.outcomes
    ]
    files_label = (
        ", ".join(report.changed_test_files)
        if report.changed_test_files
        else "no changed test files"
    )
    if report.could_not_run is not None:
        lines += _could_not_run_lines(report.could_not_run, files_label)
    elif report.changed_test_files or not report.changed_gate_checks:
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
    if not report.satisfied:
        lines += _unsatisfied_reasons(report, files_label)
    return "\n".join(lines)
