"""Fail-to-pass replay verifying that a defect fix's tests fail on its merge base (#844).

`devops ci fail-to-pass` resolves the merge base of `--base` and `--head`, lists added or
modified `tests/**/test_*.py` files, materialises the base tree in a temporary directory
with the head's `tests/` overlaid, and runs those test files with the current pytest
(`-o addopts=`, `-p no:cacheprovider`, `--junitxml`). A defect PR exits non-zero unless at
least one changed test fails in the call phase on base, or the PR body declares
`Fail-to-pass: not applicable: <reason>`.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Sequence
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_FAIL_TO_PASS_ESCAPE_PATTERN,
    CONST_FAIL_TO_PASS_JUNIT_TAG_STATUS,
    CONST_FAIL_TO_PASS_PYTEST_FLAGS,
    CONST_GIT_NAME_STATUS_CHANGE_TYPES,
    CONST_PYTHON_FILE_SUFFIX,
    CONST_TEST_FILE_PREFIX,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError
from devops_cli.git.operations import list_changed_files, resolve_merge_base
from devops_cli.github.defect_classifier import is_defect_pr
from devops_cli.lang import MESSAGES

_ESCAPE_RE = re.compile(CONST_FAIL_TO_PASS_ESCAPE_PATTERN)
_DELETED = CONST_GIT_NAME_STATUS_CHANGE_TYPES["D"]


def extract_escape_reason(body: str | None) -> str | None:
    """Return the reason from a `Fail-to-pass: not applicable: <reason>` line, or None."""
    match = _ESCAPE_RE.search(body or "")
    return match.group(1).strip() if match else None


def _parse_json_labels(raw: str) -> list[str] | None:
    """Parse a JSON array of label names or label objects when `raw` starts with `[`."""
    if not raw.startswith("["):
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(parsed, list):
        return None
    names = [
        str(item.get("name", "") if isinstance(item, dict) else item).strip() for item in parsed
    ]
    return [name for name in names if name]


def parse_pr_labels(raw: str | Sequence[str] | None) -> list[str]:
    """Normalize PR labels from a JSON array string, comma-separated string, or sequence."""
    if not raw:
        return []
    if not isinstance(raw, str):
        return [item.strip() for item in raw if item.strip()]
    stripped = raw.strip()
    if (json_labels := _parse_json_labels(stripped)) is not None:
        return json_labels
    return [part.strip() for part in re.split(r"[,\n]", stripped) if part.strip()]


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


class FailToPassReport(BaseModel):
    """Outcome of replaying changed tests against the merge-base tree."""

    model_config = ConfigDict(frozen=True)

    merge_base: str
    head: str
    changed_test_files: tuple[str, ...]
    outcomes: tuple[TestCaseOutcome, ...]
    is_defect: bool
    escape_reason: str | None = None

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
    def satisfied(self) -> bool:
        """Whether the fail-to-pass gate is satisfied for this run."""
        return not self.is_defect or self.escape_reason is not None or self.failed_count > 0


class _JUnitHTMLParser(HTMLParser):
    """Lightweight JUnit XML testcase reader built on stdlib HTMLParser."""

    def __init__(self) -> None:
        super().__init__()
        self.outcomes: list[TestCaseOutcome] = []
        self._current_case: tuple[str, str] | None = None
        self._current_status: str = "passed"
        self._current_message: str = ""

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


def _verify_commit(root: Path, revision: str) -> None:
    """Verify `revision` resolves to a commit in `root`, raising `GitOperationError` otherwise."""
    verify = ["git", "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"]
    if run_subprocess(verify, cwd=root, quiet=True).returncode != 0:
        raise GitOperationError(MESSAGES.ci.mutate_base_missing.format(base=revision))


def _untracked_test_files(root: Path) -> list[str]:
    """Untracked `tests/**/test_*.py` files in the working tree."""
    cmd = ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", CONST_TESTS_ROOT_DIR]
    listed = run_subprocess(cmd, cwd=root, quiet=True).stdout
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
    cmd = ["git", "archive", "--format=tar", f"--output={tar_path}", *archive_args]
    res = run_subprocess(cmd, cwd=root, quiet=True)
    if res.returncode == 0 and tar_path.is_file():
        with tarfile.open(tar_path) as archive:
            archive.extractall(dest, filter="data")


def materialise_base_with_head_tests(root: Path, merge_base: str, head: str, dest: Path) -> None:
    """Materialise `merge_base` in `dest` with `head`'s `tests/` overlaid."""
    dest.mkdir(parents=True, exist_ok=True)
    _archive_to_dir(root, [merge_base], dest.parent / "base.tar", dest)
    _archive_to_dir(root, [head, "--", CONST_TESTS_ROOT_DIR], dest.parent / "tests.tar", dest)
    if head == "HEAD" and (root / CONST_TESTS_ROOT_DIR).is_dir():
        shutil.copytree(
            root / CONST_TESTS_ROOT_DIR, dest / CONST_TESTS_ROOT_DIR, dirs_exist_ok=True
        )


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


def _run_pytest_on_base(
    tree_dir: Path, junit_path: Path, test_files: Sequence[str]
) -> tuple[TestCaseOutcome, ...]:
    """Run pytest on `test_files` inside `tree_dir` and parse the JUnit XML report."""
    run_subprocess(pytest_replay_argv(junit_path, test_files), cwd=tree_dir, capture_output=True)
    if not junit_path.is_file():
        return ()
    return parse_junit_xml(junit_path.read_text(encoding="utf-8"))


def _is_enforced_defect(title: str | None, labels: Sequence[str] | None) -> bool:
    """Classify whether the run enforces the defect fail-to-pass gate."""
    clean_title = (title or "").strip()
    clean_labels = list(labels or ())
    if not clean_title and not clean_labels:
        return True
    return is_defect_pr(clean_title, clean_labels)


def run_fail_to_pass(
    root: Path,
    *,
    base: str,
    head: str = "HEAD",
    title: str | None = None,
    labels: Sequence[str] | None = None,
    body: str | None = None,
) -> FailToPassReport:
    """Replay changed `tests/**/test_*.py` files against the merge-base tree."""
    is_defect = _is_enforced_defect(title, labels)
    if (escape_reason := extract_escape_reason(body)) is not None:
        return FailToPassReport(
            merge_base=base,
            head=head,
            changed_test_files=(),
            outcomes=(),
            is_defect=is_defect,
            escape_reason=escape_reason,
        )
    merge_base, files = changed_test_files(root, base, head)
    if not files:
        return FailToPassReport(
            merge_base=merge_base,
            head=head,
            changed_test_files=(),
            outcomes=(),
            is_defect=is_defect,
        )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tree_dir = tmp_path / "tree"
        junit_path = tmp_path / "junit.xml"
        materialise_base_with_head_tests(root, merge_base, head, tree_dir)
        outcomes = _run_pytest_on_base(tree_dir, junit_path, files)
    return FailToPassReport(
        merge_base=merge_base,
        head=head,
        changed_test_files=files,
        outcomes=outcomes,
        is_defect=is_defect,
    )


def format_fail_to_pass_report(report: FailToPassReport) -> str:
    """Format a human-readable per-test and summary report for `devops ci fail-to-pass`."""
    if report.escape_reason is not None:
        return MESSAGES.ci.fail_to_pass_not_applicable.format(reason=report.escape_reason)
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
    lines.append(
        MESSAGES.ci.fail_to_pass_summary.format(
            failed=report.failed_count,
            passed=report.passed_count,
            errored=report.errored_count,
            files=files_label,
        )
    )
    if not report.satisfied:
        if not report.changed_test_files:
            lines.append(MESSAGES.ci.fail_to_pass_no_tests)
        else:
            tests_str = ", ".join(outcome.test_id for outcome in report.outcomes) or files_label
            lines.append(MESSAGES.ci.fail_to_pass_none_failed.format(tests=tests_str))
    return "\n".join(lines)
