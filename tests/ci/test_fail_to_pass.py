"""Unit tests for `devops ci fail-to-pass` replay and defect PR gating (#844)."""

from __future__ import annotations

import importlib
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai.instruction_generator import ProjectMetadata, generate_agents_md
from devops_cli.ci import fail_to_pass
from devops_cli.ci.fail_to_pass import TestCaseOutcome as CaseOutcome
from devops_cli.ci.fail_to_pass import (
    format_fail_to_pass_report,
    materialise_base_with_head_tests,
    parse_junit_xml,
    plan_fail_to_pass,
    pytest_replay_argv,
    run_fail_to_pass,
)
from devops_cli.commands.ci import app, get_check_specs
from devops_cli.core.process import build_subprocess_env, run_subprocess
from tests.gate import runner as gate_runner
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
    base_tests: dict[str, str] = field(default_factory=dict)
    active_worktrees: set[Path] = field(default_factory=set)
    satisfied: bool | None = None
    gate_base: ProcessAnswer = field(default_factory=ProcessAnswer)
    gate_head: ProcessAnswer = field(default_factory=ProcessAnswer)


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


def _ls_tree_answer(replay_state: _FailToPassState, call: ProcessCall) -> ProcessAnswer:
    """The tree entry of a test file that the merge base holds, or none (exit 128)."""
    path = call.argv[-1]
    if path not in replay_state.base_tests:
        return ProcessAnswer(returncode=128, stdout="")
    return ProcessAnswer(returncode=0, stdout=f"100644 blob blob:{path}\t{path}\0")


def _cat_file_answer(replay_state: _FailToPassState, call: ProcessCall) -> ProcessAnswer:
    """The text of the test file that `_ls_tree_answer` named."""
    return ProcessAnswer(
        returncode=0, stdout=replay_state.base_tests[call.argv[-1].removeprefix("blob:")]
    )


def _is_gate_row_run(call: ProcessCall) -> bool:
    """Whether `call` runs the `main` of a gate module with `python -c`."""
    return call.argv[1:2] == ("-c",) and "from tests.gate." in call.argv[2]


def _gate_row_answer(replay_state: _FailToPassState, call: ProcessCall) -> ProcessAnswer:
    """The output of a gate row run: the base answer in the replay tree, else the head answer."""
    return replay_state.gate_base if _ran_on_base(call) else replay_state.gate_head


def _ran_on_base(call: ProcessCall) -> bool:
    """Whether `call` ran in the replay tree of the merge base."""
    return call.cwd is not None and Path(call.cwd).name == "tree"


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
    git_fake.answer(
        lambda call: "ls-tree" in call.argv, lambda call: _ls_tree_answer(replay_state, call)
    )
    git_fake.answer(
        lambda call: "cat-file" in call.argv, lambda call: _cat_file_answer(replay_state, call)
    )
    git_fake.answer(lambda call: "archive" in call.argv, ProcessAnswer(returncode=0, stdout=""))
    git_fake.answer(
        lambda call: "worktree" in call.argv,
        lambda call: _worktree_answer(replay_state, call),
    )
    git_fake.answer(
        lambda call: "-m" in call.argv and "pytest" in call.argv,
        lambda call: _pytest_answer(replay_state, call),
    )
    git_fake.answer(_is_gate_row_run, lambda call: _gate_row_answer(replay_state, call))


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
        "unchanged_failed": (),
        "changed_gate_checks": (),
        "gate_rows": (),
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

    changed = fail_to_pass.changed_tests(tmp_path, "main", "HEAD")
    dest = tmp_path / "materialised"
    materialise_base_with_head_tests(tmp_path, changed.merge_base, "HEAD", dest)

    assert (
        changed.test_files,
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
            manifests=["pyproject.toml"],
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
        "The fix changes no tests/**/test_*.py file and no module of tests/gate/*_checks/."
        in empty_defect.output,
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
# A replay that proves nothing (#3124)
# =============================================================================

BASE_TESTS = """\
def test_kept():
    assert 1 == 1


def test_fixed():
    assert 1 == 1
"""

HEAD_TESTS = """\
def test_kept():
    assert 1 == 1


def test_fixed():
    assert 1 == 2
"""


def _junit(*cases: tuple[str, str, str]) -> str:
    """A JUnit report of `tests/test_mod.py` with one case per (name, tag, message): a tag of
    `failure` or `error` gives the case that child, and an empty tag a passing case."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<testsuites>", '<testsuite name="pytest">']
    for name, tag, message in cases:
        case = f'<testcase classname="tests.test_mod" name="{name}" time="0.001"'
        lines.append(
            f'{case}><{tag} message="{message}">x</{tag}></testcase>' if tag else f"{case} />"
        )
    return "\n".join([*lines, "</testsuite>", "</testsuites>"])


def _replay_of_test_mod(
    tmp_path: Path, replay_state: _FailToPassState, *, base: str | None, head: str, junit: str
) -> str:
    """Replay `tests/test_mod.py`, which holds `head` and which `base` held at the merge base
    (None when the merge base had no such file), and return the report text."""
    repo = _branch_changing_a_test(tmp_path)
    (repo / "tests" / "test_mod.py").write_text(head, encoding="utf-8")
    if base is not None:
        replay_state.base_tests["tests/test_mod.py"] = base
    _replayed_pytest(replay_state, exit_status=1, junit_xml=junit)
    report = run_fail_to_pass(repo, base="main")
    replay_state.satisfied = report.satisfied
    return format_fail_to_pass_report(report)


@pytest.mark.parametrize("tag", ["failure", "error"], ids=["call", "teardown"])
def test_a_host_path_guard_message_in_a_replay_failure_refuses_the_replay(
    tag: str, tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """A failure of the host path guard is no fail-to-pass result (#3124): the guard can fail
    every test of the replay tree, so a replay that holds one proves nothing, though a changed
    test failed in it."""
    text = _replay_of_test_mod(
        tmp_path,
        replay_state,
        base=BASE_TESTS,
        head=HEAD_TESTS,
        junit=_junit(
            ("test_fixed", "failure", "assert 1 == 2"),
            (
                "test_kept",
                tag,
                "Failed: host path reached without a fake: "
                "/home/runner/work/devops-cli/.git/worktrees/tree/HEAD",
            ),
        ),
    )

    assert (replay_state.satisfied, text.splitlines()[-1]) == (
        False,
        "The host path guard of the test harness stopped the replay on base "
        "(tests.test_mod::test_kept). The replay proves nothing about the fix. The cause is one "
        "of two. The harness does not allow a path that every checkout reads: merge the change to "
        "the harness first, in a pull request that is not a fix, and replay this fix against the "
        "new base. Or a test reads a host path with no fake: fake that path in the test.",
    )


@pytest.mark.parametrize(
    "edge_message",
    [
        "Failed: network edge reached without a fake: 127.0.0.1:6379",
        "Failed: process edge reached without a fake: gh api user",
        "Failed: keyring edge reached without a fake: devops-cli/token",
    ],
    ids=["network-edge", "process-edge", "keyring-edge"],
)
def test_an_edge_guard_message_in_a_changed_test_keeps_the_replay_satisfied(
    edge_message: str, tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """A fix that stops code from reaching an edge proves itself by a changed test that fails on
    base at that edge, as docs/TESTING.md teaches, so the gate counts that failure (#3124)."""
    _replay_of_test_mod(
        tmp_path,
        replay_state,
        base=BASE_TESTS,
        head=HEAD_TESTS,
        junit=_junit(("test_fixed", "failure", edge_message)),
    )

    assert replay_state.satisfied is True


def test_a_test_that_the_fix_leaves_alone_and_that_fails_on_base_refuses_the_replay(
    tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """A changed test file can hold a test that the fix does not change (#3124). That test must
    pass on base: its failure there is not the fix's."""
    text = _replay_of_test_mod(
        tmp_path,
        replay_state,
        base=BASE_TESTS,
        head=HEAD_TESTS,
        junit=_junit(
            ("test_fixed", "failure", "assert 1 == 2"), ("test_kept", "failure", "assert 0")
        ),
    )

    assert (replay_state.satisfied, text.splitlines()[-1]) == (
        False,
        "A test that the fix does not change fails on base (tests.test_mod::test_kept). "
        "A test that fails on base must be one that the fix adds or changes.",
    )


def test_a_test_that_fails_on_base_after_a_changed_helper_does_not_refuse_the_replay(
    tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """A fix can change a helper that a test of the file runs. That test fails on base for a
    reason that the fix adds, so the replay stays valid (#3124)."""
    _replay_of_test_mod(
        tmp_path,
        replay_state,
        base="def helper():\n    return 1\n\n\n" + BASE_TESTS,
        head="def helper():\n    return 2\n\n\n" + HEAD_TESTS,
        junit=_junit(
            ("test_fixed", "failure", "assert 1 == 2"), ("test_kept", "failure", "assert 0")
        ),
    )

    assert replay_state.satisfied is True


def test_a_parametrized_test_that_the_fix_changes_stays_changed_in_each_case(
    tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """The case ids of a parametrized test are no part of its function name."""
    _replay_of_test_mod(
        tmp_path,
        replay_state,
        base=BASE_TESTS,
        head=HEAD_TESTS,
        junit=_junit(("test_fixed[a]", "failure", "x"), ("test_fixed[b]", "failure", "x")),
    )

    assert replay_state.satisfied is True


@pytest.mark.parametrize(
    "base", [None, "def test_other():\n    pass\n"], ids=["new-file", "new-test"]
)
def test_a_fix_with_one_new_test_that_fails_in_full_on_base_stays_satisfied(
    base: str | None, tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """A fix that adds one test, alone in its file or beside another test it does not touch, fails
    every test of that file on base, and the replay is valid: a new test is a changed test."""
    _replay_of_test_mod(
        tmp_path,
        replay_state,
        base=base,
        head="def test_fixed():\n    assert 1 == 2\n",
        junit=_junit(("test_fixed", "failure", "assert 1 == 2")),
    )

    assert replay_state.satisfied is True


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
    gate_row = shlex.join(fail_to_pass.gate_row_argv("<gate row>"))
    assert lines[8:] == [
        "git --literal-pathspecs ls-tree -z --full-tree '<merge-base>' -- '<changed test files>'",
        "git cat-file blob '<blob of the changed test file>'",
        gate_row,
        "git worktree remove --force '<temp-dir>/tree'",
        "git worktree prune",
        gate_row,
    ]
    conditions = [line.split("  [", 1)[1] for line in _plan_lines(result.output)[5:]]
    replay = "only if a changed test file or gate check exists]"
    gate = "only if a changed gate check exists]  [repeated for each row of a changed gate check]"
    assert [conditions[index] for index in (0, 1, 6, 7)] == [replay] * 4
    assert all(
        condition.startswith("only if a changed test file exists") for condition in conditions[2:5]
    )
    assert [conditions[5], conditions[8]] == [gate, gate]


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
    gate = "  [only if a changed gate check exists]"
    assert lines[-4:] == [
        f"git worktree add --quiet --detach '<temp-dir>/head' feature{gate}",
        f"{shlex.join(fail_to_pass.gate_row_argv('<gate row>'))}{gate}  [repeated for each row of a changed gate check]",
        f"git worktree remove --force '<temp-dir>/head'{gate}",
        f"git worktree prune{gate}",
    ]


@pytest.mark.parametrize(
    ("changed", "skipped"),
    [
        ("tests/test_x.py", "a changed gate check exists"),
        ("tests/gate/k8s_checks/x.py", "a changed test file exists"),
    ],
    ids=["test-file", "gate-check"],
)
def test_fail_to_pass_runs_the_processes_of_its_plan(
    changed: str, skipped: str, tmp_path: Path, cli: Any, process_fake: ProcessFake
) -> None:
    """The real replay starts the commands of the plan, in the same order, once the
    placeholders hold the values that the run reads. A fix that changes only a test file starts
    no gate row, and one that changes only a gate check starts no pytest."""
    process_fake.answer(["git", "merge-base"], ProcessAnswer(stdout="abc123\n"))
    process_fake.answer(["git", "diff", "--name-status"], ProcessAnswer(stdout=f"M\0{changed}\0"))

    run_fail_to_pass(tmp_path, base="main")

    recorded = [call.argv for call in process_fake.calls]
    tree = Path(recorded[5][5])
    values = {
        "<merge-base>": "abc123",
        "<temp-dir>": str(tree.parent),
        "<changed test files>": "tests/test_x.py",
        "<gate row>": "k8s",
    }
    planned = []
    for request in plan_fail_to_pass("main"):
        if "failed on base" in request.condition or request.condition.startswith(skipped):
            continue  # Read only when a test failed on base: this replay ran no test.
        line = shlex.join(request.argv)
        for placeholder, value in values.items():
            line = line.replace(shlex.quote(placeholder), value).replace(placeholder, value)
        planned.append(shlex.split(line))
    assert [list(argv) for argv in recorded] == planned


# =============================================================================
# Gate check replay (#4554)
# =============================================================================

OTEL_CHECK = "tests/gate/k8s_checks/otel_collector.py"
FIXED_CASE = "otel_collector.check_spans_hold_no_management_body"
_GATE_PACKAGE = "replay_gate_checks"


def _row_answer(cases: int, *failed: str, row: str = "k8s") -> ProcessAnswer:
    """What `tests/gate/runner.py` prints for a row of `cases` cases, of which `failed` fail."""
    stderr = "".join(
        f"{row}: {case} failed:\nTraceback (most recent call last):\nAssertionError\n"
        for case in failed
    )
    return ProcessAnswer(
        returncode=1 if failed else 0,
        stdout=f"{row}: {cases} cases, {len(failed)} failed\n",
        stderr=stderr,
    )


def _gate_replay(
    repo: Path,
    replay_state: _FailToPassState,
    *,
    base: ProcessAnswer,
    head: ProcessAnswer,
    changed: tuple[str, ...] = (OTEL_CHECK,),
    head_revision: str = "HEAD",
) -> tuple[bool, str]:
    """Replay a fix that changes `changed`, whose gate rows print `base` on the base tree and
    `head` on the head tree, and return whether it is satisfied and the report text."""
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    replay_state.changed_test_files = changed
    replay_state.gate_base = base
    replay_state.gate_head = head
    report = run_fail_to_pass(repo, base="main", head=head_revision)
    return report.satisfied, format_fail_to_pass_report(report)


def _gate_row_runs(git_fake: GitFake) -> list[tuple[str, str]]:
    """The tree and the gate module of each gate row run, in order."""
    return [
        (
            "base" if _ran_on_base(call) else "head",
            call.argv[2].split("from tests.gate.")[1].split(" ")[0],
        )
        for call in git_fake.calls
        if _is_gate_row_run(call)
    ]


def test_a_gate_check_that_fails_on_base_and_passes_on_head_proves_the_fix(
    tmp_path: Path, replay_state: _FailToPassState, git_fake: GitFake
) -> None:
    """A manifest fix proves itself with a changed `k8s` check: the case fails on the base tree
    and passes on the head tree, so the replay is satisfied and names the case and the module."""
    satisfied, text = _gate_replay(
        tmp_path, replay_state, base=_row_answer(107, FIXED_CASE), head=_row_answer(107)
    )

    assert (satisfied, text, _gate_row_runs(git_fake)) == (
        True,
        f"  failed on base, passed on head: k8s {FIXED_CASE}\n"
        f"k8s gate row: 1 of 107 cases failed on base, 0 of 107 on head ({OTEL_CHECK}).",
        [("base", "k8s"), ("head", "k8s")],
    )


def test_the_command_exits_0_for_a_gate_check_that_proves_the_fix(
    replay_state: _FailToPassState,
) -> None:
    """`devops ci fail-to-pass` exits 0 for a fix that only a gate check proves, and its report
    holds no line about changed test files."""
    replay_state.changed_test_files = (OTEL_CHECK,)
    replay_state.gate_base = _row_answer(107, FIXED_CASE)
    replay_state.gate_head = _row_answer(107)

    result = runner.invoke(app, ["fail-to-pass", "--base", "main"])

    assert (result.exit_code, OTEL_CHECK in result.output, "test files" in result.output) == (
        0,
        True,
        False,
    )


@pytest.mark.parametrize(
    ("base", "head", "last_line"),
    [
        (
            _row_answer(107),
            _row_answer(107),
            f"No case of a changed gate check fails on base and passes on head ({OTEL_CHECK}).",
        ),
        (
            _row_answer(107, FIXED_CASE),
            _row_answer(107, FIXED_CASE),
            f"No case of a changed gate check fails on base and passes on head ({OTEL_CHECK}).",
        ),
        (
            _row_answer(107, FIXED_CASE),
            _row_answer(106),
            "The k8s gate row ran 107 cases on base and 106 cases on head. A gate case proves "
            "a fix only when both trees run the same cases.",
        ),
        (
            _row_answer(107, FIXED_CASE, "other_module.check_other"),
            _row_answer(107, "other_module.check_other"),
            "A gate case of a check module that the fix does not change fails on base "
            "(k8s other_module.check_other). A gate case that fails on base must be in a check "
            "module that the fix adds or changes.",
        ),
    ],
    ids=["passes-on-both", "fails-on-both", "case-count-changes", "unchanged-module-fails"],
)
def test_a_gate_replay_that_proves_nothing_refuses_the_fix(
    base: ProcessAnswer,
    head: ProcessAnswer,
    last_line: str,
    tmp_path: Path,
    replay_state: _FailToPassState,
) -> None:
    """A changed gate check that passes on base, that still fails on head, whose row runs other
    cases on the two trees, or whose row fails on base in a module that the fix leaves alone,
    proves nothing about the fix."""
    satisfied, text = _gate_replay(tmp_path, replay_state, base=base, head=head)

    assert (satisfied, text.splitlines()[-1]) == (False, last_line)


@pytest.mark.parametrize(
    ("answer", "tail"),
    [
        (
            ProcessAnswer(
                returncode=1,
                stderr="Traceback (most recent call last):\n"
                "ImportError: cannot import name 'SPAN_KEYS'\n",
            ),
            "Traceback (most recent call last):\nImportError: cannot import name 'SPAN_KEYS'",
        ),
        (
            ProcessAnswer(returncode=-9, stdout="k8s: 107 cases, 0 failed\n"),
            "k8s: 107 cases, 0 failed",
        ),
    ],
    ids=["no-summary", "killed"],
)
def test_a_gate_row_that_could_not_run_on_base_refuses_the_fix(
    answer: ProcessAnswer, tail: str, tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """A row run that prints no case summary, or that exits with a status other than 0 or 1,
    could not run: the replay proves nothing and the report names the row, the tree, the status
    and the last output."""
    satisfied, text = _gate_replay(tmp_path, replay_state, base=answer, head=_row_answer(107))

    assert (satisfied, text) == (
        False,
        f"The k8s gate row could not run on the base tree: it exited with status "
        f"{answer.returncode}. A gate row run must exit with status 0 or 1 and print its case "
        "summary. Each changed check module must import and run on both trees. Merge the change "
        "that a check needs first, in a pull request that is not a fix. Then replay this fix "
        "against the new base.\n"
        f"Its last output: {tail}",
    )


def test_the_check_directory_names_the_row_of_a_changed_module(
    tmp_path: Path, replay_state: _FailToPassState, git_fake: GitFake
) -> None:
    """A module directly under `tests/gate/<row>_checks/` runs the gate module `<row>` on both
    trees. A package file, another gate module and a test file start no gate row."""
    _gate_replay(
        tmp_path,
        replay_state,
        base=_row_answer(107, FIXED_CASE),
        head=_row_answer(107),
        changed=(
            "tests/gate/tree_checks/assertions.py",
            OTEL_CHECK,
            "tests/gate/k8s_checks/__init__.py",
            "tests/gate/runner.py",
            "tests/gate/k8s_checks/data/values.py",
            "tests/gate/ruff_config.py",
        ),
    )

    assert _gate_row_runs(git_fake) == [
        ("base", "k8s"),
        ("base", "tree"),
        ("head", "k8s"),
        ("head", "tree"),
    ]


def test_a_test_only_fix_starts_no_gate_row(
    tmp_path: Path, replay_state: _FailToPassState, git_fake: GitFake
) -> None:
    """A fix that changes only `tests/**/test_*.py` files keeps the pytest replay and its report,
    and starts no gate row."""
    repo = _branch_changing_a_test(tmp_path)
    _replayed_pytest(replay_state, exit_status=1, junit_xml=JUNIT_ONE_FAILURE)

    report = run_fail_to_pass(repo, base="main")

    assert (report.satisfied, report.gate_rows, _gate_row_runs(git_fake)) == (True, (), [])


@pytest.mark.parametrize(
    ("junit_xml", "satisfied"),
    [(JUNIT_ALL_PASS, True), (_junit(("test_kept", "failure", "assert 0")), False)],
    ids=["test-passes-on-base", "unchanged-test-fails-on-base"],
)
def test_a_gate_proof_satisfies_a_fix_whose_test_replay_refuses_nothing(
    junit_xml: str, satisfied: bool, tmp_path: Path, replay_state: _FailToPassState
) -> None:
    """A fix that changes a test file and a gate check is proved by either replay, and each
    replay can refuse it: a test that the fix does not change and that fails on base refuses the
    fix that a gate check proves."""
    replay_state.base_tests["tests/test_mod.py"] = BASE_TESTS
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_mod.py").write_text(BASE_TESTS, encoding="utf-8")
    _replayed_pytest(replay_state, exit_status=1, junit_xml=junit_xml)

    result, _ = _gate_replay(
        tmp_path,
        replay_state,
        base=_row_answer(107, FIXED_CASE),
        head=_row_answer(107),
        changed=("tests/test_mod.py", OTEL_CHECK),
    )

    assert result is satisfied


def test_a_named_head_runs_the_gate_row_in_a_worktree_of_that_head(
    tmp_path: Path, replay_state: _FailToPassState, git_fake: GitFake
) -> None:
    """With `--head feature`, the head row runs in a detached worktree of `feature`, which the
    replay removes after the run."""
    satisfied, _ = _gate_replay(
        tmp_path,
        replay_state,
        base=_row_answer(107, FIXED_CASE),
        head=_row_answer(107),
        head_revision="feature",
    )

    head_tree = next(
        call.cwd for call in git_fake.calls if _is_gate_row_run(call) and not _ran_on_base(call)
    )
    added = [call.argv[-2:] for call in git_fake.calls if call.argv[1:3] == ("worktree", "add")]
    assert (satisfied, added[-1], replay_state.active_worktrees) == (
        True,
        (str(head_tree), "feature"),
        set(),
    )


# =============================================================================
# The source that a gate row imports (#5353)
# =============================================================================

ADDED_CHECK = "tests/gate/probe_checks/added.py"
# The gate row `probe`: the check module `listed` reads the list of manifests in `src/`, and the
# fix leaves it alone. The fix changes the check module `added`.
_PROBE_GATE = {
    "tests/__init__.py": "",
    "tests/gate/__init__.py": "",
    "tests/gate/probe.py": (
        "import tests.gate.probe_checks as probe_checks\n"
        "from tests.gate.runner import main as run_checks\n\n\n"
        "def main():\n"
        '    return run_checks("probe", probe_checks)\n'
    ),
    "tests/gate/probe_checks/__init__.py": "",
    "tests/gate/probe_checks/listed.py": (
        "from pathlib import Path\n\n"
        "from devops_cli import MANIFESTS\n\n\n"
        "def check_each_listed_manifest_exists():\n"
        '    assert all(Path("k8s", name).is_file() for name in MANIFESTS)\n'
    ),
    ADDED_CHECK: (
        "from pathlib import Path\n\n\n"
        "def check_the_added_manifest_exists():\n"
        '    assert Path("k8s", "b.yaml").is_file()\n'
    ),
}


def _write_files(root: Path, files: dict[str, str]) -> None:
    """Write each file of `files`, by its path under `root`."""
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


@pytest.fixture
def head_source_interpreter(
    tmp_path: Path, replay_state: _FailToPassState, git_fake: GitFake
) -> Path:
    """The checkout of a fix that adds `k8s/b.yaml` and names it in a list of `src/`, as the fix
    of #5306 does, and changes a check module of the gate row `probe`. The gate row runs for real,
    with an interpreter that finds `devops_cli` in the `src/` of the head, as the editable install
    of the checkout does: PYTHONPATH holds that `src/`, after the folder that the row runs in and
    before `site-packages`. Returns the checkout."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    runner_source = (REPO_ROOT / "tests" / "gate" / "runner.py").read_text(encoding="utf-8")
    _write_files(
        repo,
        {
            "src/devops_cli/__init__.py": 'MANIFESTS = ("a.yaml", "b.yaml")\n',
            "k8s/a.yaml": "",
            "k8s/b.yaml": "",
            "tests/gate/runner.py": runner_source,
            **_PROBE_GATE,
        },
    )
    replay_state.base_files = {"src/devops_cli/__init__.py": 'MANIFESTS = ("a.yaml",)\n'}
    replay_state.base_files["k8s/a.yaml"] = ""
    replay_state.changed_test_files = ("src/devops_cli/__init__.py", "k8s/b.yaml", ADDED_CHECK)
    head_source = {"PYTHONPATH": str(repo / "src")}

    def run_for_real(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        env = build_subprocess_env(
            call.env, isolate_env=call.isolate_env, extra_allowed_keys=call.extra_allowed_env
        )
        return subprocess.run(
            call.argv,
            cwd=call.cwd,
            env=env | head_source,
            capture_output=True,
            text=True,
            check=False,
        )

    git_fake.answer(_is_gate_row_run, ProcessAnswer(side_effect=run_for_real))
    return repo


@pytest.mark.live("python")
def test_a_gate_row_on_the_base_tree_imports_the_source_of_the_base_tree(
    head_source_interpreter: Path,
) -> None:
    """The base run of a gate row imports `devops_cli` from the `src/` of the base tree, not from
    the head that the interpreter finds (#5353). So the check module that the fix leaves alone
    passes on base, and the changed case that fails on base and passes on head proves the fix."""
    report = run_fail_to_pass(head_source_interpreter, base="main")

    assert (report.satisfied, format_fail_to_pass_report(report)) == (
        True,
        "  failed on base, passed on head: probe added.check_the_added_manifest_exists\n"
        f"probe gate row: 1 of 2 cases failed on base, 0 of 2 on head ({ADDED_CHECK}).",
    )


@pytest.fixture
def gate_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Where to write a check package that `tmp_path` makes importable, forgotten by the import
    system after the test."""
    monkeypatch.syspath_prepend(tmp_path)
    yield tmp_path / _GATE_PACKAGE
    for name in [name for name in sys.modules if name.split(".")[0] == _GATE_PACKAGE]:
        del sys.modules[name]


def test_the_replay_reads_the_output_of_the_gate_runner(
    gate_package: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The replay reads what `tests/gate/runner.py` prints: the case count and the ID of each
    failed case, a parametrized case with its label."""
    gate_package.mkdir()
    (gate_package / "__init__.py").write_text("", encoding="utf-8")
    (gate_package / "otel_collector.py").write_text(
        "import pytest\n\n\n"
        "def check_kept():\n    pass\n\n\n"
        '@pytest.mark.parametrize("name", ["a", "b"], ids=["argo-cd", "deploy-stack"])\n'
        "def check_fixed(name):\n"
        '    assert name == "a", "failed: the body is kept"\n',
        encoding="utf-8",
    )

    status = gate_runner.main("k8s", importlib.import_module(_GATE_PACKAGE))
    printed = capsys.readouterr()

    assert fail_to_pass.parse_gate_row_output(
        status, printed.out, printed.err
    ) == fail_to_pass.GateRowRun(cases=3, failed=("otel_collector.check_fixed[deploy-stack]",))
