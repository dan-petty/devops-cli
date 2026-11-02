"""Unit tests for `devops ci fail-to-pass` replay and defect PR gating (#844)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai.instruction_generator import ProjectMetadata, generate_agents_md
from devops_cli.ci.fail_to_pass import TestCaseOutcome as CaseOutcome
from devops_cli.ci.fail_to_pass import (
    changed_test_files,
    format_fail_to_pass_report,
    materialise_base_with_head_tests,
    parse_junit_xml,
    pytest_replay_argv,
    run_fail_to_pass,
)
from devops_cli.commands.ci import app, get_check_specs
from devops_cli.core.process import run_subprocess
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
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

JUNIT_ONE_FAILURE_ONE_ERROR = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="1" failures="1" skipped="0" tests="2">
    <testcase classname="tests.test_mod" name="test_value" time="0.001">
      <failure message="AssertionError: assert 1 == 2">AssertionError</failure>
    </testcase>
    <testcase classname="" name="tests.test_newmod" time="0.000">
      <error message="collection failure">ModuleNotFoundError: No module named 'newmod'</error>
    </testcase>
  </testsuite>
</testsuites>
"""

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


@dataclass
class _FailToPassState:
    exit_status: int = 0
    junit_xml: str | None = None
    stdout: str = ""
    stderr: str = ""
    changed_test_files: tuple[str, ...] = ("tests/test_mod.py",)
    base_files: dict[str, str] = field(default_factory=dict)
    active_worktrees: set[Path] = field(default_factory=set)


@pytest.fixture
def replay_state() -> _FailToPassState:
    return _FailToPassState()


def _handle_worktree_add(replay_state: _FailToPassState, argv: list[str]) -> ProcessAnswer:
    dest = Path(argv[argv.index("add") + 3])
    dest.mkdir(parents=True, exist_ok=True)
    replay_state.active_worktrees.add(dest.resolve())
    for rel, text in replay_state.base_files.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return ProcessAnswer(returncode=0, stdout="")


def _handle_worktree_remove(replay_state: _FailToPassState, argv: list[str]) -> ProcessAnswer:
    dest = Path(argv[-1])
    replay_state.active_worktrees.discard(dest.resolve())
    shutil.rmtree(dest, ignore_errors=True)
    return ProcessAnswer(returncode=0, stdout="")


def _worktree_answer(replay_state: _FailToPassState, call: ProcessCall) -> ProcessAnswer:
    argv = call.argv
    if "add" in argv:
        return _handle_worktree_add(replay_state, argv)
    if "remove" in argv:
        return _handle_worktree_remove(replay_state, argv)
    if "list" in argv:
        cwd_str = str(call.cwd or "")
        lines = [f"worktree {cwd_str}"] + [
            f"worktree {d}" for d in sorted(replay_state.active_worktrees)
        ]
        return ProcessAnswer(returncode=0, stdout="\n\n".join(lines) + "\n\n")
    return ProcessAnswer(returncode=0, stdout="")


def _pytest_answer(replay_state: _FailToPassState, call: ProcessCall) -> ProcessAnswer:
    for arg in call.argv:
        if arg.startswith("--junitxml="):
            report_path = Path(arg.removeprefix("--junitxml="))
            report_path.parent.mkdir(parents=True, exist_ok=True)
            if replay_state.junit_xml is not None:
                report_path.write_text(replay_state.junit_xml, encoding="utf-8")
    return ProcessAnswer(
        returncode=replay_state.exit_status,
        stdout=replay_state.stdout,
        stderr=replay_state.stderr,
    )


@pytest.fixture(autouse=True)
def _setup_fail_to_pass_fake(git_fake: GitFake, replay_state: _FailToPassState) -> None:
    git_fake.answer(
        lambda call: "merge-base" in call.argv, ProcessAnswer(returncode=0, stdout="deadbeef\n")
    )
    git_fake.answer(
        lambda call: "rev-parse" in call.argv, ProcessAnswer(returncode=0, stdout="deadbeef\n")
    )
    git_fake.answer(
        lambda call: "diff" in call.argv,
        lambda _call: ProcessAnswer(
            returncode=0, stdout="".join(f"M\0{f}\0" for f in replay_state.changed_test_files)
        ),
    )
    git_fake.answer(lambda call: "ls-files" in call.argv, ProcessAnswer(returncode=0, stdout=""))
    git_fake.answer(lambda call: "archive" in call.argv, ProcessAnswer(returncode=0, stdout=""))
    git_fake.answer(
        lambda call: "worktree" in call.argv,
        lambda call: _worktree_answer(replay_state, call),
    )
    git_fake.answer(
        lambda call: "-m" in call.argv and "pytest" in call.argv,
        lambda call: _pytest_answer(replay_state, call),
    )


def _mock_replay_repo(replay_state: _FailToPassState, junit_xml: str, exit_status: int = 0) -> None:
    """Configure the git fake to report `tests/test_sample.py` and write `junit_xml`."""
    replay_state.changed_test_files = ("tests/test_sample.py",)
    replay_state.junit_xml = junit_xml
    replay_state.exit_status = exit_status


def _branch_changing_a_test(repo: Path) -> Path:
    """A repository whose checked-out `fix/bug` branch changes `tests/test_mod.py` from `main`."""
    test_file = repo / "tests" / "test_mod.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_v():\n    assert 1 == 1\n", encoding="utf-8")
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/fix/bug\n", encoding="utf-8")
    return repo


def _replay_report(
    repo: Path,
    *,
    outcomes: tuple[dict[str, str], ...] = (),
    could_not_run: dict[str, object] | None = None,
) -> dict[str, object]:
    """The whole dump of a feature's report replaying `tests/test_mod.py` in `repo`, whose
    merge base is the commit `main` names."""
    return {
        "merge_base": "deadbeef",
        "head": "HEAD",
        "changed_test_files": ("tests/test_mod.py",),
        "outcomes": outcomes,
        "could_not_run": could_not_run,
    }


def _replayed_pytest(
    replay_state: _FailToPassState,
    *,
    exit_status: int,
    junit_xml: str | None = None,
    stdout: str = "",
    stderr: str = "",
) -> None:
    """Answer the replay's pytest child with `exit_status`, its output and `junit_xml`."""
    replay_state.exit_status = exit_status
    replay_state.junit_xml = junit_xml
    replay_state.stdout = stdout
    replay_state.stderr = stderr


def test_fail_to_pass_failing_test_on_base_exits_0(
    replay_state: _FailToPassState, git_fake: GitFake
) -> None:
    """A test that fails on base exits 0 and reports '1 failed on base'."""
    _mock_replay_repo(replay_state, JUNIT_ONE_FAILURE, exit_status=1)
    result = runner.invoke(
        app,
        ["fail-to-pass", "--base", "main"],
    )
    pytest_calls = [c for c in git_fake.calls if "-m" in c.argv and "pytest" in c.argv]
    assert (
        result.exit_code,
        len(pytest_calls),
        "1 failed on base" in result.output,
        "tests.test_sample::test_regression_fails" in result.output,
    ) == (0, 1, True, True)


def test_fail_to_pass_passing_test_on_base_exits_1_and_names_test(
    replay_state: _FailToPassState,
) -> None:
    """A test that passes on base exits 1 and names the test."""
    _mock_replay_repo(replay_state, JUNIT_ALL_PASS)
    result = runner.invoke(
        app,
        ["fail-to-pass", "--base", "main"],
    )
    assert (
        result.exit_code,
        "0 failed on base" in result.output,
        "tests.test_sample::test_unchanged_passes" in result.output,
    ) == (1, True, True)


def test_fail_to_pass_collection_error_does_not_satisfy_check(
    replay_state: _FailToPassState,
) -> None:
    """A collection error is reported as errored and does not satisfy the fail-to-pass check."""
    _mock_replay_repo(replay_state, JUNIT_COLLECTION_ERROR, exit_status=1)
    result = runner.invoke(
        app,
        ["fail-to-pass", "--base", "main"],
    )
    assert (
        result.exit_code,
        "errored on base: tests.test_sample (collection failure)" in result.output,
        "1 errored" in result.output,
    ) == (1, True, True)


def test_no_title_label_or_body_changes_the_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replay_state: _FailToPassState
) -> None:
    """The replay reads no pull request title, label or body (#1879): the workflow runs it only
    for a fix, so a run whose changed tests all pass on base fails, whatever the environment says,
    and the options that took a title, labels or a body are gone."""
    summary_file = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    monkeypatch.setenv("PR_TITLE", "feat(ci): add a check")
    monkeypatch.setenv("PR_LABELS", '["type/feature"]')
    monkeypatch.setenv("PR_BODY", "Fail-to-pass: not applicable: the tests pass on base\n")
    _mock_replay_repo(replay_state, JUNIT_ALL_PASS)

    result = runner.invoke(app, ["fail-to-pass", "--base", "main"])
    old_options = [
        runner.invoke(app, ["fail-to-pass", "--base", "main", option, "x"]).exit_code
        for option in ("--title", "--labels", "--body")
    ]

    assert (
        result.exit_code,
        "0 failed on base" in result.output,
        "not applicable" in result.output,
        old_options,
    ) == (1, True, False, [2, 2, 2])


def test_fail_to_pass_materialises_base_and_overlays_head_tests(
    tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """Materialising overlays the head's tests/ onto the merge-base source tree."""
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "tests" / "test_mod.py").write_text(
        "def test_v():\n    assert 2 == 2\n", encoding="utf-8"
    )
    replay_state.base_files["src/mod.py"] = "VALUE = 1\n"
    replay_state.changed_test_files = ("tests/test_mod.py",)

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
    tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """A fix that adds a module and its test file cannot import that file on base; pytest then
    stops at collection unless told to continue, and the fix's other failing test goes unseen."""
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    replay_state.changed_test_files = ("tests/test_mod.py", "tests/test_newmod.py")
    replay_state.junit_xml = JUNIT_ONE_FAILURE_ONE_ERROR
    replay_state.exit_status = 1

    report = run_fail_to_pass(tmp_path, base="main")

    assert (report.failed_count, report.errored_count, report.satisfied) == (1, 1, True)


def test_a_test_that_runs_git_ls_files_passes_on_base_in_the_replay(
    tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """The replay tree is a git work tree (#2197): a test that lists tracked files passes on
    base there, as it does in the checkout, and the replay does not fail for its own setup."""
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    replay_state.changed_test_files = ("tests/test_git.py",)
    replay_state.junit_xml = JUNIT_ALL_PASS
    replay_state.exit_status = 0

    report = run_fail_to_pass(tmp_path, base="main")

    assert (report.passed_count, report.failed_count, report.could_not_run) == (1, 0, None)


def test_the_replay_leaves_no_worktree_behind(
    tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """The replay removes the worktree it adds, so the checkout lists no extra worktree."""
    repo = _branch_changing_a_test(tmp_path)
    _replayed_pytest(replay_state, exit_status=0, junit_xml=JUNIT_ALL_PASS)

    run_fail_to_pass(repo, base="main")

    listed = run_subprocess(["git", "-C", str(repo), "worktree", "list", "--porcelain"]).stdout
    assert listed.count("worktree ") == 1


def test_fail_to_pass_helpers_and_no_ci_stage(tmp_path: Path) -> None:
    """`uv run devops ci` gains no stage, and the helpers parse XML and instructions."""
    outcomes = parse_junit_xml(JUNIT_ONE_FAILURE)
    argv = pytest_replay_argv(tmp_path / "j.xml", ["tests/test_a.py"])
    agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    generated_md = generate_agents_md(
        ProjectMetadata(
            name="devops-cli",
            description="CLI",
            version="0.2.36",
            requires_python=">=3.14",
        )
    )
    assert (
        "fail-to-pass" in {spec.name for spec in get_check_specs()},
        [(o.test_id, o.status) for o in outcomes],
        ("-o" in argv and "addopts=" in argv and "-p" in argv and "no:cacheprovider" in argv),
        "devops ci fail-to-pass" in agents_md,
        "devops ci fail-to-pass" in generated_md,
    ) == (
        False,
        [
            ("tests.test_sample::test_regression_fails", "failed"),
            ("tests.test_sample::test_existing_passes", "passed"),
        ],
        True,
        True,
        True,
    )


def test_fail_to_pass_dry_run_and_no_changed_tests(replay_state: _FailToPassState) -> None:
    """Dry-run exits 0 without git calls, and a fix with no changed tests exits 1."""
    dry_res = runner.invoke(app, ["fail-to-pass", "--base", "main", "--dry-run"])
    replay_state.changed_test_files = ()
    empty_defect = runner.invoke(
        app,
        ["fail-to-pass", "--base", "main"],
    )
    assert (
        dry_res.exit_code,
        empty_defect.exit_code,
        "The fix changes no tests/**/test_*.py file." in empty_defect.output,
    ) == (0, 1, True)


def test_fail_to_pass_outcome_model_properties() -> None:
    """TestCaseOutcome formats test_id with and without classname."""
    grouped = CaseOutcome(classname="tests.test_x", name="test_one", status="failed")
    ungrouped = CaseOutcome(classname="", name="tests.test_x", status="errored")
    assert (grouped.test_id, ungrouped.test_id) == ("tests.test_x::test_one", "tests.test_x")


def test_a_replay_pytest_could_not_start_fails_the_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replay_state: _FailToPassState,
    snapshot: SnapshotAssertion,
) -> None:
    """A replay whose pytest stops with an internal error and writes no JUnit report fails the
    check, names the exit status and the replay, and tells the author to merge the harness change
    first in a pull request that is not a fix (#1669, #1879)."""
    monkeypatch.chdir(_branch_changing_a_test(tmp_path))
    _replayed_pytest(replay_state, exit_status=3, stderr=INTERNAL_ERROR_OUTPUT)

    result = runner.invoke(app, ["fail-to-pass", "--base", "main"])

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
    monkeypatch: pytest.MonkeyPatch,
    replay_state: _FailToPassState,
    snapshot: SnapshotAssertion,
) -> None:
    """pytest's last output reaches the terminal as pytest wrote it: its brackets are not read
    as markup, nor its colon-wrapped words as emoji codes."""
    monkeypatch.chdir(_branch_changing_a_test(tmp_path))
    _replayed_pytest(replay_state, exit_status=exit_status, junit_xml=junit_xml, stderr=stderr)

    result = runner.invoke(app, ["fail-to-pass", "--base", "main"])

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
    replay_state: _FailToPassState,
    snapshot: SnapshotAssertion,
) -> None:
    """An interrupted (2), internally failed (3) or refused (4) pytest, or one that wrote no
    complete JUnit report, means the replay could not run, whatever outcomes the report holds;
    a report that is empty or never closes its root is no report."""
    repo = _branch_changing_a_test(tmp_path)
    could_not_run = {"exit_status": exit_status, "output_tail": output_tail}
    expected = _replay_report(repo, outcomes=outcomes, could_not_run=could_not_run)
    _replayed_pytest(
        replay_state,
        exit_status=exit_status,
        junit_xml=junit_xml,
        stdout=stdout,
        stderr=stderr,
    )

    report = run_fail_to_pass(repo, base="main")

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
    replay_state: _FailToPassState,
) -> None:
    """The report keeps the last whole lines of pytest's output that fit in 256 characters, all
    of them when they fill it exactly, or the end of the last line when that line alone is
    longer."""
    repo = _branch_changing_a_test(tmp_path)
    expected = _replay_report(repo, could_not_run={"exit_status": 3, "output_tail": output_tail})
    _replayed_pytest(replay_state, exit_status=3, stderr=stderr)

    report = run_fail_to_pass(repo, base="main")

    assert report.model_dump() == expected


@pytest.mark.parametrize(
    ("exit_status", "junit_xml", "satisfied", "text"),
    [
        (
            1,
            JUNIT_ONE_FAILURE,
            True,
            "  failed on base: tests.test_sample::test_regression_fails"
            " (AssertionError: expected 2)\n"
            "  passed on base: tests.test_sample::test_existing_passes\n"
            "1 failed on base (1 failed and 1 passed in tests/test_mod.py; 0 errored).",
        ),
        (
            0,
            JUNIT_ALL_PASS,
            False,
            "  passed on base: tests.test_sample::test_unchanged_passes\n"
            "0 failed on base (0 failed and 1 passed in tests/test_mod.py; 0 errored).\n"
            "A fix needs at least one changed test that fails in the call phase on base "
            "(tests.test_sample::test_unchanged_passes).",
        ),
        (
            1,
            JUNIT_COLLECTION_ERROR,
            False,
            "  errored on base: tests.test_sample (collection failure)\n"
            "0 failed on base (0 failed and 0 passed in tests/test_mod.py; 1 errored).\n"
            "A fix needs at least one changed test that fails in the call phase on base "
            "(tests.test_sample).",
        ),
    ],
    ids=["failing", "passing", "collection-error"],
)
def test_a_replay_that_collects_and_runs_reports_its_outcomes(
    exit_status: int,
    junit_xml: str,
    satisfied: bool,
    text: str,
    tmp_path: Path,
    replay_state: _FailToPassState,
) -> None:
    """A replay whose tests collect and run, failing, passing or erroring, reports its outcomes."""
    repo = _branch_changing_a_test(tmp_path)
    _replayed_pytest(replay_state, exit_status=exit_status, junit_xml=junit_xml)

    report = run_fail_to_pass(repo, base="main")

    assert (report.satisfied, format_fail_to_pass_report(report)) == (satisfied, text)


def test_a_replay_that_collects_no_tests_is_an_empty_replay(
    tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """pytest's exit 5, no tests collected, is an empty replay, not one that could not run, and
    an empty replay does not satisfy the check."""
    repo = _branch_changing_a_test(tmp_path)
    _replayed_pytest(replay_state, exit_status=5, junit_xml=JUNIT_NO_TESTS, stdout="no tests ran")

    report = run_fail_to_pass(repo, base="main")

    assert (report.satisfied, format_fail_to_pass_report(report)) == (
        False,
        "0 failed on base (0 failed and 0 passed in tests/test_mod.py; 0 errored).\n"
        "A fix needs at least one changed test that fails in the call phase on base "
        "(tests/test_mod.py).",
    )


# =============================================================================
# Dry runs (#2260)
# =============================================================================


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    import re

    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


@pytest.mark.parametrize("flag_first", [True, False])
def test_fail_to_pass_dry_run_lists_the_replay_and_starts_nothing(
    cli: Any, process_fake: ProcessFake, flag_first: bool
) -> None:
    """A dry run starts no git and no pytest, and lists each process of the run in order."""
    argv = ["ci", "fail-to-pass", "--base", "main"]
    result = cli(["--dry-run", *argv] if flag_first else [*argv, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    lines = [line.split("  [")[0] for line in _plan_lines(result.output)]
    assert lines[:5] == [
        "git merge-base -- main HEAD",
        "git rev-parse --verify --quiet 'main^{commit}'",
        "git rev-parse --verify --quiet 'HEAD^{commit}'",
        "git diff --name-status -z --find-renames '<merge-base>' --",
        "git ls-files --others --exclude-standard -z -- tests",
    ]
    assert lines[5] == "git worktree add --quiet --detach '<temp-dir>/tree' '<merge-base>'"
    assert lines[6] == "git archive --format=tar '--output=<temp-dir>/tests.tar' HEAD -- tests"
    assert " -m pytest " in lines[7]
    assert lines[7].endswith("'<changed test files>'")
    assert lines[8:] == [
        "git worktree remove --force '<temp-dir>/tree'",
        "git worktree prune",
    ]
    assert all(
        "[only if a changed test file exists]" in line for line in _plan_lines(result.output)[5:]
    )


def test_fail_to_pass_dry_run_of_a_head_lists_the_fallback_diff(
    cli: Any, process_fake: ProcessFake
) -> None:
    """With `--head`, the plan lists the two-dot diff that follows a failed three-dot diff."""
    result = cli(["ci", "fail-to-pass", "--base", "main", "--head", "feature", "--dry-run"])

    lines = _plan_lines(result.output)
    assert result.exit_code == 0, result.output
    assert lines[3] == "git diff --name-status -z --find-renames '<merge-base>...feature' --"
    assert lines[4] == (
        "git diff --name-status -z --find-renames '<merge-base>' feature --"
        "  [only if the three-dot diff fails]"
    )
    assert not [line for line in lines if "ls-files" in line]


def test_fail_to_pass_runs_the_processes_of_its_plan(
    tmp_path: Path, cli: Any, process_fake: ProcessFake
) -> None:
    """The real replay starts the commands of the plan, in the same order, once the
    placeholders hold the values that the run reads."""
    import shlex

    from devops_cli.ci.fail_to_pass import plan_fail_to_pass

    process_fake.answer(["git", "merge-base"], ProcessAnswer(stdout="abc123\n"))
    process_fake.answer(
        ["git", "diff", "--name-status"], ProcessAnswer(stdout="M\0tests/test_x.py\0")
    )

    run_fail_to_pass(tmp_path, base="main")

    recorded = [call.argv for call in process_fake.calls]
    tree = Path(recorded[5][5])
    values = {
        "<merge-base>": "abc123",
        "<temp-dir>": str(tree.parent),
        "<changed test files>": "tests/test_x.py",
    }
    planned = []
    for request in plan_fail_to_pass("main"):
        line = shlex.join(request.argv)
        for placeholder, value in values.items():
            line = line.replace(shlex.quote(placeholder), value).replace(placeholder, value)
        planned.append(shlex.split(line))
    assert [list(argv) for argv in recorded] == planned
