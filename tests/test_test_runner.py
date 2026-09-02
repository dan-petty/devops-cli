"""Tests for test runner and git-diff aware test selector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.test_cmd import (
    app as app_cli,
)
from devops_cli.commands.test_cmd import (
    find_changed_test_files,
)

runner = CliRunner()


def test_find_changed_test_files(tmp_path: Path) -> None:
    """Map changed files to matching test files."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_scan.py").write_text("# test scan", encoding="utf-8")
    (tests_dir / "test_release.py").write_text("# test release", encoding="utf-8")

    mock_proc_diff = MagicMock(returncode=0, stdout="src/devops_cli/commands/scan.py\n")
    mock_proc_wt = MagicMock(returncode=0, stdout="")

    with patch(
        "devops_cli.commands.test_cmd.run_subprocess", side_effect=[mock_proc_diff, mock_proc_wt]
    ):
        found = find_changed_test_files(tmp_path)
        assert len(found) == 1
        assert found[0].name == "test_scan.py"

    # Test porcelain rename output (old -> new)
    mock_proc_diff_empty = MagicMock(returncode=0, stdout="")
    mock_proc_wt_rename = MagicMock(
        returncode=0,
        stdout="R  src/devops_cli/old_scan.py -> src/devops_cli/commands/scan.py\n",
    )
    with patch(
        "devops_cli.commands.test_cmd.run_subprocess",
        side_effect=[mock_proc_diff_empty, mock_proc_wt_rename],
    ):
        found_rename = find_changed_test_files(tmp_path)
        assert len(found_rename) == 1
        assert found_rename[0].name == "test_scan.py"


def test_test_run_dry_run() -> None:
    """devops test run --dry-run prints simulated test execution."""
    res = runner.invoke(app_cli, ["run", "--dry-run"])
    assert res.exit_code == 0
    assert "DRY-RUN" in res.output or "pytest" in res.output


def test_test_run_execution() -> None:
    """devops test run with mocks."""
    mock_res = MagicMock(returncode=0)
    with patch("devops_cli.commands.test_cmd.run_subprocess", return_value=mock_res):
        res = runner.invoke(
            app_cli, ["run", "tests/test_scan.py", "--cov", "-v", "-x", "-k", "sample"]
        )
        assert res.exit_code == 0
        assert "Test suite passed cleanly" in res.output

    # Test run failure
    mock_fail = MagicMock(returncode=1)
    with patch("devops_cli.commands.test_cmd.run_subprocess", return_value=mock_fail):
        res_fail = runner.invoke(app_cli, ["run", "tests/test_scan.py"])
        assert res_fail.exit_code == 1


def test_test_run_changed_flag(tmp_path: Path) -> None:
    """Verify devops test run --changed with both detected and empty modifications."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    test_f = tests_dir / "test_foo.py"
    test_f.write_text("# foo test", encoding="utf-8")

    # 1. Direct test file changed
    mock_proc_diff = MagicMock(returncode=0, stdout="tests/test_foo.py\nREADME.md\n")
    mock_proc_wt = MagicMock(returncode=0, stdout="")
    with (
        patch("devops_cli.commands.test_cmd.find_top_level_repo_root", return_value=tmp_path),
        patch(
            "devops_cli.commands.test_cmd.run_subprocess",
            side_effect=[mock_proc_diff, mock_proc_wt, MagicMock(returncode=0)],
        ),
    ):
        res = runner.invoke(app_cli, ["run", "--changed"])
        assert res.exit_code == 0

    # 2. No changes detected
    mock_empty = MagicMock(returncode=0, stdout="")
    with (
        patch("devops_cli.commands.test_cmd.find_top_level_repo_root", return_value=tmp_path),
        patch(
            "devops_cli.commands.test_cmd.run_subprocess",
            side_effect=[mock_empty, mock_empty, MagicMock(returncode=0)],
        ),
    ):
        res_no_chg = runner.invoke(app_cli, ["run", "--changed"])
        assert res_no_chg.exit_code == 0


def test_test_load_missing_k6_and_failure(tmp_path: Path) -> None:
    """Verify devops test load when k6 is not installed or when test run fails."""
    # 1. Missing k6
    with patch("devops_cli.commands.test_cmd.shutil.which", return_value=None):
        res_no_k6 = runner.invoke(app_cli, ["load"])
        assert res_no_k6.exit_code == 1

    # 2. k6 failure
    export_file = tmp_path / "summary.json"
    with (
        patch("devops_cli.commands.test_cmd.shutil.which", return_value="/usr/local/bin/k6"),
        patch("devops_cli.commands.test_cmd.run_subprocess", return_value=MagicMock(returncode=2)),
    ):
        res_fail = runner.invoke(app_cli, ["load", "--summary-export", str(export_file)])
        assert res_fail.exit_code == 2
