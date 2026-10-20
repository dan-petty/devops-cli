"""Unit tests for `devops ci fail-to-pass` replay and defect PR gating (#844)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from devops_cli.ai.instruction_generator import ProjectMetadata, generate_agents_md
from devops_cli.ci.fail_to_pass import TestCaseOutcome as CaseOutcome
from devops_cli.ci.fail_to_pass import (
    changed_test_files,
    extract_escape_reason,
    format_fail_to_pass_report,
    materialise_base_with_head_tests,
    parse_junit_xml,
    parse_pr_labels,
    pytest_replay_argv,
    run_fail_to_pass,
)
from devops_cli.commands.ci import app, get_check_specs
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

runner = CliRunner()

JUNIT_ONE_FAILURE = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="0" tests="2">
    <testcase classname="tests.test_sample" name="test_regression_fails" time="0.001">
      <failure message="AssertionError: expected 2">AssertionError</failure>
    </testcase>
    <testcase classname="tests.test_sample" name="test_existing_passes" time="0.001" />
  </testsuite>
</testsuites>
"""

JUNIT_ALL_PASS = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="0" skipped="0" tests="1">
    <testcase classname="tests.test_sample" name="test_unchanged_passes" time="0.001" />
  </testsuite>
</testsuites>
"""

JUNIT_COLLECTION_ERROR = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="1" failures="0" skipped="0" tests="1">
    <testcase classname="" name="tests.test_sample" time="0.000">
      <error message="collection failure">ModuleNotFoundError: No module named 'missing'</error>
    </testcase>
  </testsuite>
</testsuites>
"""


def _mock_replay_repo(monkeypatch: pytest.MonkeyPatch, junit_xml: str) -> list[list[str]]:
    """Stub git merge-base/materialisation and have the pytest subprocess write `junit_xml`."""
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "devops_cli.ci.fail_to_pass.changed_test_files",
        lambda _root, _base, _head="HEAD": ("deadbeef", ("tests/test_sample.py",)),
    )
    monkeypatch.setattr(
        "devops_cli.ci.fail_to_pass.materialise_base_with_head_tests",
        lambda _root, _base, _head, dest: dest.mkdir(parents=True, exist_ok=True),
    )

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        for arg in cmd:
            if arg.startswith("--junitxml="):
                Path(arg.removeprefix("--junitxml=")).write_text(junit_xml, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("devops_cli.ci.fail_to_pass.run_subprocess", fake_run)
    return calls


JUNIT_NO_TESTS = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
  <testsuite name="pytest" errors="0" failures="0" skipped="0" tests="0" time="0.015" />
</testsuites>
"""

INTERNAL_ERROR_OUTPUT = """\
INTERNALERROR> Traceback (most recent call last):
INTERNALERROR>   File "tests/support/bootstrap.py", line 9, in pytest_configure
INTERNALERROR> ImportError: cannot import name 'defines_fixture_or_hook'
"""

USAGE_ERROR_OUTPUT = """\
ERROR: usage: __main__.py [options] [file_or_dir] [file_or_dir] [...]
__main__.py: error: unrecognized arguments: --bogus
"""

# Rich reads `:x:` and `:b:` as emoji codes unless told not to.
EMOJI_CODE_OUTPUT = "INTERNALERROR> PATH=src:x:tests and a:b:c\n"

# The report pytest writes when an internal error ends a session it had begun to report.
JUNIT_INTERNAL_ERROR = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
  <testsuite name="pytest" errors="1" failures="0" skipped="0" tests="1" time="0.020">
    <testcase classname="pytest" name="internal" time="0.000">
      <error message="internal error">RuntimeError: boom</error>
    </testcase>
  </testsuite>
</testsuites>
"""

# A report cut short after its first test case, as a write that ran out of space leaves it.
JUNIT_TRUNCATED = JUNIT_ALL_PASS[: JUNIT_ALL_PASS.index("</testsuite>")]

PASSED_OUTCOME = {
    "classname": "tests.test_sample",
    "name": "test_unchanged_passes",
    "status": "passed",
    "message": "",
}
INTERNAL_ERROR_OUTCOME = {
    "classname": "pytest",
    "name": "internal",
    "status": "errored",
    "message": "internal error",
}


def _branch_changing_a_test(repo: Path, git: Callable[..., None]) -> Path:
    """A repository whose checked-out `fix/bug` branch changes `tests/test_mod.py` from `main`."""
    test_file = repo / "tests" / "test_mod.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_v():\n    assert True\n", encoding="utf-8")
    git(repo, "init", "--quiet", "-b", "main")
    git(repo, "add", ".")
    git(repo, "commit", "--quiet", "-m", "base")
    git(repo, "switch", "--quiet", "-c", "fix/bug")
    test_file.write_text("def test_v():\n    assert 1 == 1\n", encoding="utf-8")
    git(repo, "commit", "--quiet", "-am", "change the test")
    return repo


def _replay_report(
    repo: Path,
    *,
    outcomes: tuple[dict[str, str], ...] = (),
    could_not_run: dict[str, object] | None = None,
) -> dict[str, object]:
    """The whole dump of a feature's report replaying `tests/test_mod.py` in `repo`, whose
    merge base is the commit `main` names."""
    merge_base = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "main"], capture_output=True, text=True, check=True
    ).stdout.strip()
    return {
        "merge_base": merge_base,
        "head": "HEAD",
        "changed_test_files": ("tests/test_mod.py",),
        "outcomes": outcomes,
        "is_defect": False,
        "escape_reason": None,
        "could_not_run": could_not_run,
    }


def _replayed_pytest(
    monkeypatch: pytest.MonkeyPatch,
    *,
    exit_status: int,
    junit_xml: str | None = None,
    stdout: str = "",
    stderr: str = "",
) -> list[list[str]]:
    """Answer the replay's pytest child with `exit_status`, its output and, when given,
    `junit_xml` as its report, at the stdlib; git still runs for real."""
    real_run = subprocess.run
    started: list[list[str]] = []

    def run(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        if list(cmd[1:3]) != ["-m", "pytest"]:
            return real_run(cmd, *args, **kwargs)  # type: ignore[call-overload,no-any-return]
        started.append(list(cmd))
        report = next(arg.removeprefix("--junitxml=") for arg in cmd if "--junitxml=" in arg)
        if junit_xml is not None:
            Path(report).write_text(junit_xml, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, exit_status, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(subprocess, "run", run)
    return started


def test_fail_to_pass_failing_test_on_base_exits_0(monkeypatch: pytest.MonkeyPatch) -> None:
    """A test that fails on base exits 0 and reports '1 failed on base'."""
    calls = _mock_replay_repo(monkeypatch, JUNIT_ONE_FAILURE)
    result = runner.invoke(
        app,
        ["fail-to-pass", "--base", "main", "--title", "fix(ci): handle regression"],
    )
    assert (
        result.exit_code,
        len(calls),
        "1 failed on base" in result.output,
        "tests.test_sample::test_regression_fails" in result.output,
    ) == (0, 1, True, True)


def test_fail_to_pass_passing_test_on_base_exits_1_and_names_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A test that passes on base exits 1 and names the test."""
    _mock_replay_repo(monkeypatch, JUNIT_ALL_PASS)
    result = runner.invoke(
        app,
        ["fail-to-pass", "--base", "main", "--title", "fix(ci): missing regression test"],
    )
    assert (
        result.exit_code,
        "0 failed on base" in result.output,
        "tests.test_sample::test_unchanged_passes" in result.output,
    ) == (1, True, True)


def test_fail_to_pass_collection_error_does_not_satisfy_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A collection error is reported as errored and does not satisfy the fail-to-pass check."""
    _mock_replay_repo(monkeypatch, JUNIT_COLLECTION_ERROR)
    result = runner.invoke(
        app,
        ["fail-to-pass", "--base", "main", "--labels", "type/bug"],
    )
    assert (
        result.exit_code,
        "errored on base: tests.test_sample (collection failure)" in result.output,
        "1 errored" in result.output,
    ) == (1, True, True)


def test_fail_to_pass_not_applicable_line_exits_0_and_prints_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PR body with 'Fail-to-pass: not applicable: <reason>' exits 0 and echoes the reason."""
    summary_file = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    calls = _mock_replay_repo(monkeypatch, JUNIT_ALL_PASS)
    result = runner.invoke(
        app,
        [
            "fail-to-pass",
            "--base",
            "main",
            "--title",
            "fix(deps): bump runtime dependency",
            "--body",
            "Closes #844\n\nFail-to-pass: not applicable: dependency bump errors on base\n",
        ],
    )
    assert (
        result.exit_code,
        calls,
        "Fail-to-pass: not applicable: dependency bump errors on base" in result.output,
        "Fail-to-pass: not applicable: dependency bump errors on base"
        in summary_file.read_text(encoding="utf-8"),
    ) == (0, [], True, True)


def test_fail_to_pass_non_defect_pr_exits_0(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-defect PR gets the report and exits 0 even when all changed tests pass on base."""
    _mock_replay_repo(monkeypatch, JUNIT_ALL_PASS)
    result = runner.invoke(
        app,
        [
            "fail-to-pass",
            "--base",
            "main",
            "--title",
            "feat(ci): add new subcommand",
            "--labels",
            '["type/feature", "scope/cli"]',
        ],
    )
    assert (
        result.exit_code,
        "0 failed on base" in result.output,
        "tests.test_sample::test_unchanged_passes" in result.output,
    ) == (0, True, True)


def test_fail_to_pass_materialises_base_and_overlays_head_tests(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """Materialising overlays the head's tests/ onto the merge-base source tree."""
    git(tmp_path, "init", "--quiet", "-b", "main")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_mod.py").write_text(
        "def test_v():\n    assert 1 == 1\n", encoding="utf-8"
    )
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    git(tmp_path, "switch", "--quiet", "-c", "fix/bug")
    (tmp_path / "src" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_mod.py").write_text(
        "def test_v():\n    assert 2 == 2\n", encoding="utf-8"
    )
    git(tmp_path, "commit", "--quiet", "-am", "fix")

    merge_base, files = changed_test_files(tmp_path, "main", "HEAD")
    dest = tmp_path / "materialised"
    materialise_base_with_head_tests(tmp_path, merge_base, "HEAD", dest)

    assert (
        files,
        (dest / "src" / "mod.py").read_text(encoding="utf-8"),
        (dest / "tests" / "test_mod.py").read_text(encoding="utf-8"),
    ) == (
        ("tests/test_mod.py",),
        "VALUE = 1\n",
        "def test_v():\n    assert 2 == 2\n",
    )


def test_a_new_module_s_test_that_cannot_import_on_base_leaves_the_other_tests_counted(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """A fix that adds a module and its test file cannot import that file on base; pytest then
    stops at collection unless told to continue, and the fix's other failing test goes unseen."""
    files = {
        "conftest.py": "",
        "mod.py": "VALUE = 1\n",
        "tests/test_mod.py": "from mod import VALUE\n\n\ndef test_value():\n    assert VALUE == 1\n",
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    git(tmp_path, "init", "--quiet", "-b", "main")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    git(tmp_path, "switch", "--quiet", "-c", "fix/bug")
    fixed = {
        "mod.py": "VALUE = 2\n",
        "newmod.py": "NEW = True\n",
        "tests/test_mod.py": "from mod import VALUE\n\n\ndef test_value():\n    assert VALUE == 2\n",
        "tests/test_newmod.py": "from newmod import NEW\n\n\ndef test_new():\n    assert NEW\n",
    }
    for name, text in fixed.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "fix")

    report = run_fail_to_pass(tmp_path, base="main", title="fix(mod): value is 2")

    assert (report.failed_count, report.errored_count, report.satisfied) == (1, 1, True)


def test_fail_to_pass_helpers_and_no_ci_stage(tmp_path: Path) -> None:
    """`uv run devops ci` gains no stage, and helpers parse labels, XML, and instructions."""
    outcomes = parse_junit_xml(JUNIT_ONE_FAILURE)
    argv = pytest_replay_argv(tmp_path / "j.xml", ["tests/test_a.py"])
    agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    generated_md = generate_agents_md(
        ProjectMetadata(
            name="devops-cli",
            description="CLI",
            version="0.2.36",
            requires_python=">=3.14",
            is_devops_cli=True,
        )
    )
    assert (
        "fail-to-pass" in {spec.name for spec in get_check_specs()},
        parse_pr_labels('[{"name": "type/bug"}, "scope/cli"]'),
        parse_pr_labels("type/security, scope/ci"),
        extract_escape_reason("Body\nFail-to-pass: not applicable: harness change"),
        [(o.test_id, o.status) for o in outcomes],
        ("-o" in argv and "addopts=" in argv and "-p" in argv and "no:cacheprovider" in argv),
        "devops ci fail-to-pass" in agents_md,
        "devops ci fail-to-pass" in generated_md,
    ) == (
        False,
        ["type/bug", "scope/cli"],
        ["type/security", "scope/ci"],
        "harness change",
        [
            ("tests.test_sample::test_regression_fails", "failed"),
            ("tests.test_sample::test_existing_passes", "passed"),
        ],
        True,
        True,
        True,
    )


def test_fail_to_pass_dry_run_and_no_changed_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dry-run exits 0 without git calls, and a defect PR with no changed tests exits 1."""
    dry_res = runner.invoke(app, ["fail-to-pass", "--base", "main", "--dry-run"])
    monkeypatch.setattr(
        "devops_cli.ci.fail_to_pass.changed_test_files",
        lambda _root, _base, _head="HEAD": ("deadbeef", ()),
    )
    empty_defect = runner.invoke(
        app,
        ["fail-to-pass", "--base", "main", "--title", "fix(ci): no tests changed"],
    )
    assert (
        dry_res.exit_code,
        empty_defect.exit_code,
        "modifies no tests/**/test_*.py files" in empty_defect.output,
    ) == (0, 1, True)


def test_fail_to_pass_outcome_model_properties() -> None:
    """TestCaseOutcome formats test_id with and without classname."""
    grouped = CaseOutcome(classname="tests.test_x", name="test_one", status="failed")
    ungrouped = CaseOutcome(classname="", name="tests.test_x", status="errored")
    assert (grouped.test_id, ungrouped.test_id) == ("tests.test_x::test_one", "tests.test_x")


@pytest.mark.parametrize(
    "title",
    ["feat(test): add support plugins", "fix(test): replay the support plugins"],
    ids=["feature", "defect"],
)
def test_a_replay_pytest_could_not_start_fails_the_check_for_any_pull_request(
    title: str,
    tmp_path: Path,
    git: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """A replay whose pytest stops with an internal error and writes no JUnit report fails the
    check for a feature as for a defect, naming the exit status and the replay (#1669)."""
    monkeypatch.chdir(_branch_changing_a_test(tmp_path, git))
    _replayed_pytest(monkeypatch, exit_status=3, stderr=INTERNAL_ERROR_OUTPUT)

    result = runner.invoke(app, ["fail-to-pass", "--base", "main", "--title", title])

    assert result.exit_code == 1
    assert result.output.replace(str(tmp_path.resolve()), "<tmp_path>") == snapshot


@pytest.mark.parametrize(
    ("exit_status", "junit_xml", "stderr"),
    [(4, JUNIT_NO_TESTS, USAGE_ERROR_OUTPUT), (3, None, EMOJI_CODE_OUTPUT)],
    ids=["markup-brackets", "emoji-codes"],
)
def test_a_replay_that_could_not_run_prints_pytest_s_output_as_it_is(
    exit_status: int,
    junit_xml: str | None,
    stderr: str,
    tmp_path: Path,
    git: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """pytest's last output reaches the terminal as pytest wrote it: its brackets are not read
    as markup, nor its colon-wrapped words as emoji codes."""
    monkeypatch.chdir(_branch_changing_a_test(tmp_path, git))
    _replayed_pytest(monkeypatch, exit_status=exit_status, junit_xml=junit_xml, stderr=stderr)

    result = runner.invoke(app, ["fail-to-pass", "--base", "main", "--title", "feat(ci): a check"])

    assert (result.exit_code, result.output.endswith(f"pytest's last output: {stderr}")) == (
        1,
        True,
    )
    assert result.output.replace(str(tmp_path.resolve()), "<tmp_path>") == snapshot


@pytest.mark.parametrize(
    ("exit_status", "junit_xml", "stdout", "stderr", "outcomes", "output_tail"),
    [
        (
            2,
            JUNIT_ALL_PASS,
            "!!! KeyboardInterrupt !!!\n",
            "",
            (PASSED_OUTCOME,),
            "!!! KeyboardInterrupt !!!",
        ),
        (
            3,
            JUNIT_INTERNAL_ERROR,
            "INTERNALERROR> RuntimeError: boom\n",
            "",
            (INTERNAL_ERROR_OUTCOME,),
            "INTERNALERROR> RuntimeError: boom",
        ),
        (
            4,
            JUNIT_NO_TESTS,
            "no tests ran\n",
            USAGE_ERROR_OUTPUT,
            (),
            f"no tests ran\n{USAGE_ERROR_OUTPUT}".rstrip(),
        ),
        (-9, None, "", "", (), ""),
        (
            1,
            "",
            "",
            "OSError: [Errno 27] File too large\n",
            (),
            "OSError: [Errno 27] File too large",
        ),
        (
            1,
            JUNIT_TRUNCATED,
            "",
            "OSError: [Errno 28] No space left on device\n",
            (),
            "OSError: [Errno 28] No space left on device",
        ),
    ],
    ids=[
        "interrupted",
        "internal-error-with-report",
        "usage-error",
        "killed-without-report",
        "empty-report",
        "truncated-report",
    ],
)
def test_a_replay_that_stopped_or_wrote_no_report_could_not_run(
    exit_status: int,
    junit_xml: str | None,
    stdout: str,
    stderr: str,
    outcomes: tuple[dict[str, str], ...],
    output_tail: str,
    tmp_path: Path,
    git: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """An interrupted (2), internally failed (3) or refused (4) pytest, or one that wrote no
    complete JUnit report, means the replay could not run, whatever outcomes the report holds;
    a report that is empty or never closes its root is no report."""
    repo = _branch_changing_a_test(tmp_path, git)
    could_not_run = {"exit_status": exit_status, "output_tail": output_tail}
    expected = _replay_report(repo, outcomes=outcomes, could_not_run=could_not_run)
    _replayed_pytest(
        monkeypatch, exit_status=exit_status, junit_xml=junit_xml, stdout=stdout, stderr=stderr
    )

    report = run_fail_to_pass(repo, base="main", title="feat(ci): add a check")

    assert (report.satisfied, report.model_dump()) == (False, expected)
    assert format_fail_to_pass_report(report) == snapshot


_FRAMES = [f"INTERNALERROR> frame {number:02d} of the import" for number in range(40)]
_LONG_LINE = "INTERNALERROR> " + "x" * 300
# The last three lines fill the bound exactly: 84 + 1 + 84 + 1 + 86 = 256 characters.
_FILLING_LINES = ["z" * 10, "a" * 84, "b" * 84, "c" * 86]


@pytest.mark.parametrize(
    ("stderr", "output_tail"),
    [
        ("\n".join(_FRAMES), "\n".join(_FRAMES[-6:])),
        (_LONG_LINE, _LONG_LINE[-256:]),
        ("\n".join(_FILLING_LINES), "\n".join(_FILLING_LINES[1:])),
    ],
    ids=["whole-lines", "one-long-line", "lines-filling-the-bound"],
)
def test_a_replay_that_could_not_run_keeps_the_last_whole_lines_within_the_bound(
    stderr: str,
    output_tail: str,
    tmp_path: Path,
    git: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The report keeps the last whole lines of pytest's output that fit in 256 characters, all
    of them when they fill it exactly, or the end of the last line when that line alone is
    longer."""
    repo = _branch_changing_a_test(tmp_path, git)
    expected = _replay_report(repo, could_not_run={"exit_status": 3, "output_tail": output_tail})
    _replayed_pytest(monkeypatch, exit_status=3, stderr=stderr)

    report = run_fail_to_pass(repo, base="main", title="feat(ci): add a check")

    assert report.model_dump() == expected


@pytest.mark.parametrize(
    ("exit_status", "junit_xml", "title", "satisfied", "text"),
    [
        (
            1,
            JUNIT_ONE_FAILURE,
            "fix(mod): value is 2",
            True,
            "  failed on base: tests.test_sample::test_regression_fails"
            " (AssertionError: expected 2)\n"
            "  passed on base: tests.test_sample::test_existing_passes\n"
            "1 failed on base (1 failed and 1 passed in tests/test_mod.py; 0 errored).",
        ),
        (
            0,
            JUNIT_ALL_PASS,
            "feat(mod): add a value",
            True,
            "  passed on base: tests.test_sample::test_unchanged_passes\n"
            "0 failed on base (0 failed and 1 passed in tests/test_mod.py; 0 errored).",
        ),
        (
            1,
            JUNIT_COLLECTION_ERROR,
            "fix(mod): value is 2",
            False,
            "  errored on base: tests.test_sample (collection failure)\n"
            "0 failed on base (0 failed and 0 passed in tests/test_mod.py; 1 errored).\n"
            "Defect PR requires at least one changed test to fail in the call phase on base "
            "(tests.test_sample).",
        ),
    ],
    ids=["failing", "passing", "collection-error"],
)
def test_a_replay_that_collects_and_runs_reports_its_outcomes(
    exit_status: int,
    junit_xml: str,
    title: str,
    satisfied: bool,
    text: str,
    tmp_path: Path,
    git: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A replay whose tests collect and run, failing, passing or erroring, reports its outcomes."""
    repo = _branch_changing_a_test(tmp_path, git)
    _replayed_pytest(monkeypatch, exit_status=exit_status, junit_xml=junit_xml)

    report = run_fail_to_pass(repo, base="main", title=title)

    assert (report.satisfied, format_fail_to_pass_report(report)) == (satisfied, text)


@pytest.mark.parametrize(
    ("title", "satisfied", "text"),
    [
        (
            "feat(mod): add a value",
            True,
            "0 failed on base (0 failed and 0 passed in tests/test_mod.py; 0 errored).",
        ),
        (
            "fix(mod): value is 2",
            False,
            "0 failed on base (0 failed and 0 passed in tests/test_mod.py; 0 errored).\n"
            "Defect PR requires at least one changed test to fail in the call phase on base "
            "(tests/test_mod.py).",
        ),
    ],
    ids=["feature", "defect"],
)
def test_a_replay_that_collects_no_tests_is_an_empty_replay(
    title: str,
    satisfied: bool,
    text: str,
    tmp_path: Path,
    git: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pytest's exit 5, no tests collected, is an empty replay, not one that could not run."""
    repo = _branch_changing_a_test(tmp_path, git)
    _replayed_pytest(monkeypatch, exit_status=5, junit_xml=JUNIT_NO_TESTS, stdout="no tests ran")

    report = run_fail_to_pass(repo, base="main", title=title)

    assert (report.satisfied, format_fail_to_pass_report(report)) == (satisfied, text)


def test_the_not_applicable_line_wins_over_a_replay_that_could_not_run(
    tmp_path: Path, git: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pull request declaring 'Fail-to-pass: not applicable: <reason>' passes the check
    without replaying, even when its tests could not run against its base."""
    monkeypatch.chdir(_branch_changing_a_test(tmp_path, git))
    started = _replayed_pytest(monkeypatch, exit_status=3, stderr=INTERNAL_ERROR_OUTPUT)

    result = runner.invoke(
        app,
        [
            "fail-to-pass",
            "--base",
            "main",
            "--title",
            "feat(test): add support plugins",
            "--body",
            "Fail-to-pass: not applicable: the tests import support the base lacks",
        ],
    )

    assert (result.exit_code, started, result.output) == (
        0,
        [],
        f"ℹ Quality gate root: {tmp_path.resolve()}\n"
        "Fail-to-pass: not applicable: the tests import support the base lacks\n",
    )
