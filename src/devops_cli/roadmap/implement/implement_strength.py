"""The strength check of the implement job (#3051): how strong the tests of an item are.

The scoped checks of `implement_scoped_ci.py` run the tests of an item, and a test that asserts
nothing passes. This check measures the strength of the new tests in three parts:

- the assertion scan of the new test files, with the rule `test-function-has-assertion`: a test
  function that holds no `assert`, no `pytest.raises` or `pytest.warns` call and no `self.assert*`
  call proves nothing.

The parts after it, the bounded mutation run and the coverage delta of the changed files, come with
the later groups of #3051.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import tomlkit

from devops_cli.ci.mutate import MutationTarget, select_targets, tally
from devops_cli.config.commands import BIN_UV
from devops_cli.config.constants import (
    CONST_PYTHON_FILE_SUFFIX,
    CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.process import run_subprocess
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_scoped_ci import ScopedResult
from devops_cli.roadmap.step_files import KIND_LINE, parse_task_groups

_ASSERTION_RULE = ".ast-grep/rules/test-function-has-assertion.yml"
_TEST_MODULE_PREFIX = "test_"
# The file and the key from which mutmut 3.8.1 reads the test selection of its stats run.
_MUTMUT_CONFIG = "pyproject.toml"
_MUTMUT_SELECTION = "pytest_add_cli_args_test_selection"


@dataclass(frozen=True)
class AssertionFinding:
    """A test function that asserts nothing: its file, the line of the function, and the message
    of the rule that found it."""

    path: str
    line: int
    message: str


def new_test_files(names: Iterable[str]) -> list[str]:
    """The new test modules of the changed paths `names`: a Python file under `tests/` whose name
    starts with `test_`. The assertion rule scans only those, and a helper such as `conftest.py` or
    `tests/support/` holds no test function of its own."""
    files: list[str] = []
    for name in names:
        path = PurePosixPath(name)
        if (
            path.suffix == CONST_PYTHON_FILE_SUFFIX
            and path.parts
            and path.parts[0] == CONST_TESTS_ROOT_DIR
            and path.name.startswith(_TEST_MODULE_PREFIX)
        ):
            files.append(name)
    return files


def _assertion_command(files: Sequence[str]) -> list[str]:
    """The command line of the assertion scan over `files`: each path is one argument, so no shell
    reads it."""
    return [
        BIN_UV,
        "run",
        "ast-grep",
        "scan",
        "--rule",
        _ASSERTION_RULE,
        "--json",
        *files,
    ]


def assertion_failures(source: Path, files: Sequence[str]) -> tuple[AssertionFinding, ...]:
    """The test functions of `files` that assert nothing, in the checkout `source`.

    The rule `test-function-has-assertion` holds the definition of an assertion, so a second parser
    would define it twice. The scan exits 1 when it finds one, and prints the file, the start line
    and the message of each match as JSON.
    """
    if not files:
        return ()
    done = run_subprocess(_assertion_command(files), cwd=source, quiet=True)
    matches: list[dict[str, Any]] = json.loads(done.stdout or "[]")
    return tuple(
        AssertionFinding(
            path=str(match["file"]),
            line=int(match["range"]["start"]["line"]) + 1,
            message=str(match["message"]),
        )
        for match in matches
    )


@dataclass(frozen=True)
class MutationOutcome:
    """The outcome of a mutation run: surviving mutants with their targets, whether the run
    reached the time bound, and changed source files that were skipped when they exceeded the
    file bound."""

    survivors: tuple[tuple[str, MutationTarget], ...] = ()
    timeout: bool = False
    skipped_files: tuple[str, ...] = ()


def mutation_targets(
    source: Path, changed_files: Sequence[str], default_branch: str
) -> tuple[tuple[MutationTarget, ...], tuple[str, ...]]:
    """The mutation targets of `changed_files` in `source` against `origin/<default_branch>`.

    The targets come from `select_targets` of `devops_cli.ci.mutate`. The targets of the first
    `CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES` source files are kept, and any remaining source
    files are returned as skipped.
    """
    if not changed_files:
        return (), ()
    paths = [source / file for file in changed_files]
    all_targets = select_targets(source, paths, changed=True, base=f"origin/{default_branch}")
    if not all_targets:
        return (), ()

    seen_files: list[str] = []
    for file in changed_files:
        if file not in seen_files and any(t.path == file for t in all_targets):
            seen_files.append(file)
    for t in all_targets:
        if t.path not in seen_files:
            seen_files.append(t.path)

    kept_files = set(seen_files[:CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES])
    skipped_files = tuple(seen_files[CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES:])
    kept_targets = tuple(t for t in all_targets if t.path in kept_files)
    return kept_targets, skipped_files


@contextmanager
def _mutmut_test_selection(source: Path, tests: Sequence[str]) -> Iterator[None]:
    """Add `tests` to the test selection of mutmut in the checkout `source` while the block runs,
    then give the file its bytes again.

    `mutmut run` 3.8.1 takes no pytest argument. It reads `pytest_add_cli_args_test_selection` of
    `[tool.mutmut]` in `pyproject.toml`, and its stats run gives that list to pytest. The process
    runner refuses the key `PYTEST_ADDOPTS` (#2747), so the selection goes in the file. The entries
    of the table stay first. A checkout with no `pyproject.toml` gets one for the block, and has
    none after it. The job commits no change of the file: the block ends before any commit, and
    the bytes come back when the run raises or runs out of time too. With no `tests`, the file
    stays as it is, and mutmut runs the selection of the table.
    """
    if not tests:
        yield
        return
    path = source / _MUTMUT_CONFIG
    original = path.read_bytes() if path.is_file() else None
    document = (
        tomlkit.parse(original.decode("utf-8")) if original is not None else tomlkit.document()
    )
    tool = document.setdefault("tool", tomlkit.table(is_super_table=True))
    table = tool.setdefault("mutmut", tomlkit.table())
    table[_MUTMUT_SELECTION] = [*(str(entry) for entry in table.get(_MUTMUT_SELECTION, [])), *tests]
    path.write_text(tomlkit.dumps(document), encoding="utf-8")
    try:
        yield
    finally:
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(original)


def run_mutation(
    source: Path,
    targets: Sequence[MutationTarget],
    tests: Sequence[str],
    *,
    skipped_files: Sequence[str] = (),
    timeout: int | None = None,
) -> MutationOutcome:
    """Run mutmut over `targets` in `source`, with stats collection scoped to `tests`.

    `uv run mutmut run` reads `tests` from the test selection of its table
    (`_mutmut_test_selection`), so stats collection runs only the scoped test modules, bounded by
    `timeout` (defaulting to `roadmap.implement.command_timeout_seconds`). The run sets no
    environment key. When the run times out or finishes, `uv run mutmut results --all true` is read
    through `tally`. A run that reaches the timeout retains the survivors collected so far and marks
    `timeout=True`.
    """
    if not targets:
        return MutationOutcome(skipped_files=tuple(skipped_files))

    limit = (
        timeout
        if timeout is not None
        else load_settings().roadmap.implement.command_timeout_seconds
    )
    globs = [glob for target in targets for glob in target.run_globs]
    cmd = [BIN_UV, "run", "mutmut", "run", *globs]
    timed_out = False
    with _mutmut_test_selection(source, tests):
        try:
            run_subprocess(cmd, cwd=source, timeout=float(limit), quiet=True)
        except subprocess.TimeoutExpired:
            timed_out = True

    results_cmd = [BIN_UV, "run", "mutmut", "results", "--all", "true"]
    done = run_subprocess(results_cmd, cwd=source, quiet=True)
    report = tally(done.stdout or "", targets)
    return MutationOutcome(
        survivors=report.survivors,
        timeout=timed_out,
        skipped_files=tuple(skipped_files),
    )


@dataclass(frozen=True)
class CoverageDelta:
    """The outcome of measuring changed-line test coverage: whether the coverage run and diff-cover
    passed, the text of the markdown coverage report, and the command log when a command failed."""

    passed: bool
    report: str = ""
    log: str = ""


def coverage_delta(source: Path, default_branch: str, tests: Sequence[str]) -> CoverageDelta:
    """Measure the changed-line coverage of `tests` in `source` against `origin/<default_branch>`.

    Runs `pytest` with coverage over `tests`, generates the XML report, and runs `diff-cover`
    with `--fail-under 90`. Each test path is an individual argv argument.
    """
    if not tests:
        return CoverageDelta(passed=True)

    pytest_cmd = [
        BIN_UV,
        "run",
        "pytest",
        "--cov=src",
        "--cov-report=",
        "--cov-fail-under=0",
        *tests,
    ]
    proc_pytest = run_subprocess(pytest_cmd, cwd=source, quiet=True)
    if proc_pytest.returncode != 0:
        log = proc_pytest.stdout or proc_pytest.stderr or ""
        return CoverageDelta(passed=False, log=log)

    xml_cmd = [BIN_UV, "run", "coverage", "xml", "-q"]
    proc_xml = run_subprocess(xml_cmd, cwd=source, quiet=True)
    if proc_xml.returncode != 0:
        log = proc_xml.stdout or proc_xml.stderr or ""
        return CoverageDelta(passed=False, log=log)

    data_dir = source / Path() / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    report_file = data_dir / "coverage.md"

    diff_cmd = [
        BIN_UV,
        "run",
        "diff-cover",
        ".data/coverage.xml",
        f"--compare-branch=origin/{default_branch}",
        "--fail-under",
        "90",
        "--format",
        f"markdown:{report_file.relative_to(source).as_posix()}",
    ]
    proc_diff = run_subprocess(diff_cmd, cwd=source, quiet=True)

    report = ""
    if report_file.is_file():
        report = report_file.read_text(encoding="utf-8")
    if not report and proc_diff.stdout:
        report = proc_diff.stdout

    if proc_diff.returncode != 0:
        log = proc_diff.stdout or proc_diff.stderr or report
        return CoverageDelta(passed=False, report=report, log=log)

    return CoverageDelta(passed=True, report=report)


def strength_scope(
    tasks_md: str, changed_files: Sequence[str]
) -> tuple[tuple[str, ...], tuple[tuple[int, str], ...]]:
    """Determine the files subject to the strength check and any files/groups left out.

    Reads the `Kind:` line of each group with `KIND_LINE`. Leaves the changed files of any group
    of kind `other` out of the check, with the group number as the reason.
    """
    groups = parse_task_groups(tasks_md)
    other_files: set[str] = set()
    skipped_groups: list[tuple[int, str]] = []

    for group in groups:
        match = KIND_LINE.search(group.text)
        if match and match.group("kind") == "other":
            named = [f for f in changed_files if f in group.text or f in group.named_paths]
            if named:
                other_files.update(named)
                skipped_groups.append((group.number, f"group {group.number}: kind other"))

    active_files = tuple(f for f in changed_files if f not in other_files)
    return active_files, tuple(skipped_groups)


@dataclass(frozen=True)
class StrengthReport:
    """The result of the strength check across assertion scanning, mutation testing, and coverage."""

    passed: bool
    assertion_findings: tuple[AssertionFinding, ...] = ()
    surviving_mutants: tuple[tuple[str, MutationTarget], ...] = ()
    mutation_outcome: MutationOutcome | None = None
    coverage_delta: CoverageDelta | None = None
    uncovered_lines: tuple[str, ...] = ()
    skipped_groups: tuple[tuple[int, str], ...] = ()
    note: str = ""


def _extract_uncovered_lines(report_text: str) -> tuple[str, ...]:
    uncovered: list[str] = []
    current_file = ""
    for raw_line in report_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## ") and "(" in line:
            current_file = line[3:].split("(")[0].strip()
        elif line.startswith("- ") and "Missing lines" in line:
            part = line[2:].split(":")[0].split("(")[0].strip()
            if part.endswith(".py") or "/" in part:
                current_file = part
        if "Missing lines" in line and current_file:
            _, _, missing = line.partition("Missing lines")
            missing = missing.lstrip(": ").strip()
            for item in missing.split(","):
                item = item.strip()
                if item:
                    uncovered.append(f"{current_file}:{item}")
    return tuple(uncovered)


def strength_report(
    source: Path,
    tasks_md: str,
    changed_files: Sequence[str],
    default_branch: str,
    tests: Sequence[str],
) -> StrengthReport:
    """Run the assertion scan, the mutation run, and the coverage run in order."""
    active_files, skipped_groups = strength_scope(tasks_md, changed_files)
    test_files = new_test_files(active_files)
    findings = assertion_failures(source, test_files)

    targets, skipped_sources = mutation_targets(source, active_files, default_branch)
    mutation = run_mutation(source, targets, tests, skipped_files=skipped_sources)

    note = ""
    coverage: CoverageDelta | None = None
    if not tests:
        note = MESSAGES.roadmap.implement_scoped_tests_uncovered
    else:
        coverage = coverage_delta(source, default_branch, tests)

    uncovered_lines: tuple[str, ...] = ()
    if coverage and not coverage.passed:
        uncovered_lines = _extract_uncovered_lines(coverage.report)

    has_assertions = bool(findings)
    has_survivors = bool(mutation.survivors)
    has_uncovered = bool(coverage and not coverage.passed)
    passed = not (has_assertions or has_survivors or has_uncovered)

    return StrengthReport(
        passed=passed,
        assertion_findings=findings,
        surviving_mutants=mutation.survivors,
        mutation_outcome=mutation,
        coverage_delta=coverage,
        uncovered_lines=uncovered_lines,
        skipped_groups=skipped_groups,
        note=note,
    )


def _finding_lines(report: StrengthReport) -> list[str]:
    lines: list[str] = []
    for finding in report.assertion_findings:
        lines.append(f"- missing assertion in {finding.path}:{finding.line}: {finding.message}")
    for name, target in report.surviving_mutants:
        lines.append(f"- surviving mutant in {target.path}:{target.line}: {name}")
    for item in report.uncovered_lines:
        lines.append(f"- uncovered changed line in {item}")
    if report.coverage_delta and not report.coverage_delta.passed and not report.uncovered_lines:
        if report.coverage_delta.report:
            lines.append(f"- coverage failure:\n{report.coverage_delta.report.strip()}")
        elif report.coverage_delta.log:
            lines.append(f"- coverage failure: {report.coverage_delta.log.strip()}")
    return lines


def _outcome_lines(report: StrengthReport) -> list[str]:
    lines: list[str] = []
    if report.mutation_outcome:
        if report.mutation_outcome.timeout:
            lines.append("- mutation run reached command timeout bound")
        for skipped in report.mutation_outcome.skipped_files:
            lines.append(f"- mutation run skipped file over bound: {skipped}")
    for group_num, reason in report.skipped_groups:
        lines.append(f"- group {group_num}: skipped, {reason}")
    if report.note:
        lines.append(f"- {report.note}")
    return lines


def report_lines(report: StrengthReport) -> list[str]:
    """The lines of the strength report for the pull request comment."""
    lines = _finding_lines(report) + _outcome_lines(report)
    if not lines and report.passed:
        lines.append("- strength: passed")
    return lines


def scoped_result(report: StrengthReport) -> ScopedResult:
    """Convert a strength report into a ScopedResult."""
    lines = report_lines(report)
    log = "\n".join(lines) if not report.passed else ""
    return ScopedResult(
        name="strength",
        passed=report.passed,
        seconds=0.0,
        log=log,
        command="devops roadmap implement strength",
        status=0 if report.passed else 1,
    )
