"""Fail-to-pass replay verifying that a defect fix's tests fail on its merge base (#844).

`devops ci fail-to-pass` resolves the merge base of `--base` and `--head`, lists added or
modified `tests/**/test_*.py` files, checks out the base tree as a detached git worktree in a
temporary directory (#2197) with the head's `tests/` overlaid, and runs those test files with
the current pytest (`-o addopts=`, `-p no:cacheprovider`, `--continue-on-collection-errors`,
`--junitxml`), so a test file that cannot be collected on base is reported as errored and the others still run.
The run exits non-zero unless at least one changed test fails in the call phase on base. The
workflow runs it only for a fix pull request that changes `src/` (#1879), so the command reads no
title, label or body. A replay whose pytest was interrupted, stopped with an internal or usage
error, or wrote no complete JUnit report could not run on base, and fails (#1669). A changed test
file that cannot be collected on base is reported as errored. A replay with a failure that a guard
of the test harness raised, or with a failed test that the fix does not change, proves nothing
about the fix and fails too (#3124).
"""

from __future__ import annotations

import shutil
import sys
import tarfile
import tempfile
from collections.abc import Sequence
from html.parser import HTMLParser
from pathlib import Path, PurePath, PurePosixPath

from pydantic import BaseModel, ConfigDict

from devops_cli.ci.changed_tests import is_test_changed
from devops_cli.config.constants import (
    CONST_FAIL_TO_PASS_COULD_NOT_RUN_EXIT_STATUSES,
    CONST_FAIL_TO_PASS_GUARD_MESSAGE,
    CONST_FAIL_TO_PASS_JUNIT_ROOT_TAG,
    CONST_FAIL_TO_PASS_JUNIT_TAG_STATUS,
    CONST_FAIL_TO_PASS_PYTEST_FLAGS,
    CONST_GIT_NAME_STATUS_CHANGE_TYPES,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_PYTHON_FILE_SUFFIX,
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


class ReplayCouldNotRun(BaseModel):
    """A replay whose pytest stopped before it reported the changed tests on base (#1669)."""

    model_config = ConfigDict(frozen=True)

    exit_status: int
    output_tail: str = ""


class FailToPassReport(BaseModel):
    """Outcome of replaying changed tests against the merge-base tree."""

    model_config = ConfigDict(frozen=True)

    merge_base: str
    head: str
    changed_test_files: tuple[str, ...]
    outcomes: tuple[TestCaseOutcome, ...]
    could_not_run: ReplayCouldNotRun | None = None
    unchanged_failed: tuple[str, ...] = ()

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
    def guard_failures(self) -> tuple[TestCaseOutcome, ...]:
        """The failures and errors that a guard of the test harness raised (#3124)."""
        return tuple(
            outcome
            for outcome in self.outcomes
            if outcome.status in ("failed", "errored")
            and CONST_FAIL_TO_PASS_GUARD_MESSAGE in outcome.message
        )

    @property
    def satisfied(self) -> bool:
        """Whether the fail-to-pass gate is satisfied: a replay that could not run never is, and
        otherwise at least one changed test fails on base, no failure comes from a guard of the
        test harness, and every test that fails on base is one that the fix adds or changes
        (#3124)."""
        return (
            self.could_not_run is None
            and self.failed_count > 0
            and not self.guard_failures
            and not self.unchanged_failed
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


def _is_test_file(path: PurePosixPath) -> bool:
    """Whether `path` is a `tests/**/test_*.py` file."""
    return (
        path.is_relative_to(CONST_TESTS_ROOT_DIR)
        and path.suffix == CONST_PYTHON_FILE_SUFFIX
        and path.name.startswith(CONST_TEST_FILE_PREFIX)
    )


def verify_commit_argv(revision: str) -> list[str]:
    """The command that checks that `revision` names a commit."""
    return ["git", "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"]


def untracked_tests_argv() -> list[str]:
    """The command that lists the untracked files under `tests/`."""
    return ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", CONST_TESTS_ROOT_DIR]


def worktree_add_argv(dest: PurePath | str, merge_base: str) -> list[str]:
    """The command that checks out `merge_base` at `dest` as a detached worktree."""
    return ["git", "worktree", "add", "--quiet", "--detach", str(dest), merge_base]


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


def _untracked_test_files(root: Path) -> list[str]:
    """Untracked `tests/**/test_*.py` files in the working tree."""
    listed = run_subprocess(untracked_tests_argv(), cwd=root, quiet=True).stdout
    return [path for path in filter(None, listed.split("\0")) if _is_test_file(PurePosixPath(path))]


def changed_test_files(root: Path, base: str, head: str = "HEAD") -> tuple[str, tuple[str, ...]]:
    """Resolve the merge base of `base` and `head` and list added or modified `tests/**/test_*.py`."""
    if (merge_base := resolve_merge_base(root, base, head)) is None:
        raise GitOperationError(MESSAGES.ci.mutate_base_refused.format(base=base))
    _verify_commit(root, base)
    _verify_commit(root, head)
    diff_head = None if head == "HEAD" else head
    tracked = [
        change.path
        for change in list_changed_files(root, merge_base, diff_head)
        if change.change_type != _DELETED and _is_test_file(PurePosixPath(change.path))
    ]
    untracked = _untracked_test_files(root) if head == "HEAD" else []
    return merge_base, tuple(sorted(set(tracked) | set(untracked)))


def _archive_to_dir(root: Path, archive_args: list[str], tar_path: Path, dest: Path) -> None:
    """Write a git tar archive for `archive_args` and extract it safely into `dest`."""
    res = run_subprocess(archive_argv(tar_path, archive_args), cwd=root, quiet=True)
    if res.returncode == 0 and tar_path.is_file():
        with tarfile.open(tar_path) as archive:
            archive.extractall(dest, filter="data")


def materialise_base_with_head_tests(root: Path, merge_base: str, head: str, dest: Path) -> None:
    """Check out `merge_base` in `dest` as a detached git worktree of `root`, with `head`'s
    `tests/` overlaid, so a test that runs `git` there works as in the checkout (#2197).

    `remove_materialised_base` removes the worktree.
    """
    add = worktree_add_argv(dest, merge_base)
    if (res := run_subprocess(add, cwd=root, quiet=True)).returncode != 0:
        raise GitOperationError(
            MESSAGES.ci.fail_to_pass_worktree_failed.format(
                base=merge_base, detail=(res.stderr or "").strip()
            )
        )
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


MERGE_BASE_PLACEHOLDER = "<merge-base>"
TEMP_DIR_PLACEHOLDER = "<temp-dir>"
CHANGED_TESTS_PLACEHOLDER = "<changed test files>"
BLOB_PLACEHOLDER = "<blob of the changed test file>"
UNCHANGED_CHECK = "a test that failed on base is in a changed test file"


def plan_fail_to_pass(base: str, head: str = "HEAD") -> list[PlannedRequest]:
    """The processes that `run_fail_to_pass` starts, in order, with no git call made: the
    merge base, the commits and the changed test files are placeholders. The replay steps run
    only when a changed test file exists."""
    diff_head = None if head == "HEAD" else head
    tmp = PurePosixPath(TEMP_DIR_PLACEHOLDER)
    tree = tmp / "tree"
    replay = "a changed test file exists"

    def git(argv: list[str], condition: str = "") -> PlannedRequest:
        return PlannedRequest(method="git", target=argv[1], argv=tuple(argv), condition=condition)

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
            condition=replay,
        ),
        PlannedRequest(
            method="git",
            target="ls-tree",
            argv=tuple(ls_tree_argv(MERGE_BASE_PLACEHOLDER, CHANGED_TESTS_PLACEHOLDER)),
            condition=both(replay, UNCHANGED_CHECK),
        ),
        git(cat_file_argv(BLOB_PLACEHOLDER), both(replay, UNCHANGED_CHECK)),
        git(worktree_remove_argv(tree), replay),
        git(worktree_prune_argv(), replay),
    ]
    return requests


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
) -> tuple[tuple[TestCaseOutcome, ...], ReplayCouldNotRun | None]:
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
        return outcomes, None
    output = _output_tail(f"{result.stdout or ''}\n{result.stderr or ''}")
    return outcomes or (), ReplayCouldNotRun(exit_status=result.returncode, output_tail=output)


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
    sources: dict[str, tuple[str | None, str | None]] = {}
    unchanged: list[str] = []
    for outcome in outcomes:
        if outcome.status != "failed" or (location := _test_location(outcome, files)) is None:
            continue
        path, classes, name = location
        if path not in sources:
            head_file = tree_dir / path
            head_source = head_file.read_text(encoding="utf-8") if head_file.is_file() else None
            base_source = (
                read_file_at_revision(root, merge_base, path) if head_source is not None else None
            )
            sources[path] = (base_source, head_source)
        if not is_test_changed(classes, name, *sources[path]):
            unchanged.append(outcome.test_id)
    return tuple(dict.fromkeys(unchanged))


def run_fail_to_pass(root: Path, *, base: str, head: str = "HEAD") -> FailToPassReport:
    """Replay changed `tests/**/test_*.py` files against the merge-base tree."""
    merge_base, files = changed_test_files(root, base, head)
    if not files:
        return FailToPassReport(
            merge_base=merge_base, head=head, changed_test_files=(), outcomes=()
        )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tree_dir = tmp_path / "tree"
        junit_path = tmp_path / "junit.xml"
        try:
            materialise_base_with_head_tests(root, merge_base, head, tree_dir)
            outcomes, could_not_run = _run_pytest_on_base(tree_dir, junit_path, files)
            unchanged_failed = (
                ()
                if could_not_run
                else _unchanged_failures(root, merge_base, tree_dir, files, outcomes)
            )
        finally:
            remove_materialised_base(root, tree_dir)
    return FailToPassReport(
        merge_base=merge_base,
        head=head,
        changed_test_files=files,
        outcomes=outcomes,
        could_not_run=could_not_run,
        unchanged_failed=unchanged_failed,
    )


def _could_not_run_lines(could_not_run: ReplayCouldNotRun, files: str) -> list[str]:
    """The report's lines for a replay of `files` that could not run on base (#1669)."""
    reason = MESSAGES.ci.fail_to_pass_could_not_run.format(
        status=could_not_run.exit_status, files=files
    )
    if not could_not_run.output_tail:
        return [reason]
    return [reason, MESSAGES.ci.fail_to_pass_replay_output.format(output=could_not_run.output_tail)]


def _unsatisfied_reason(report: FailToPassReport, files_label: str) -> str:
    """The sentence that tells the author why a replay that ran does not satisfy the gate."""
    if not report.changed_test_files:
        return MESSAGES.ci.fail_to_pass_no_tests
    if report.guard_failures:
        guarded = dict.fromkeys(outcome.test_id for outcome in report.guard_failures)
        return MESSAGES.ci.fail_to_pass_guard_failed.format(tests=", ".join(guarded))
    if report.unchanged_failed:
        return MESSAGES.ci.fail_to_pass_unchanged_failed.format(
            tests=", ".join(report.unchanged_failed)
        )
    tests_str = ", ".join(outcome.test_id for outcome in report.outcomes) or files_label
    return MESSAGES.ci.fail_to_pass_none_failed.format(tests=tests_str)


def format_fail_to_pass_report(report: FailToPassReport) -> str:
    """Format a human-readable per-test and summary report for `devops ci fail-to-pass`."""
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
        return "\n".join([*lines, *_could_not_run_lines(report.could_not_run, files_label)])
    lines.append(
        MESSAGES.ci.fail_to_pass_summary.format(
            failed=report.failed_count,
            passed=report.passed_count,
            errored=report.errored_count,
            files=files_label,
        )
    )
    if not report.satisfied:
        lines.append(_unsatisfied_reason(report, files_label))
    return "\n".join(lines)
