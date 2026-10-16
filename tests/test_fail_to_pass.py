"""Unit tests for `devops ci fail-to-pass` replay and defect PR gating (#844)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.instruction_generator import ProjectMetadata, generate_agents_md
from devops_cli.ci.fail_to_pass import (
    TestCaseOutcome,
    changed_test_files,
    extract_escape_reason,
    materialise_base_with_head_tests,
    parse_junit_xml,
    parse_pr_labels,
    pytest_replay_argv,
)
from devops_cli.commands.ci import app, get_check_specs

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]

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
    grouped = TestCaseOutcome(classname="tests.test_x", name="test_one", status="failed")
    ungrouped = TestCaseOutcome(classname="", name="tests.test_x", status="errored")
    assert (grouped.test_id, ungrouped.test_id) == ("tests.test_x::test_one", "tests.test_x")
