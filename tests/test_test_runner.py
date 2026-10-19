"""Tests for test runner and git-diff aware test selector."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.test_cmd import app as app_cli

runner = CliRunner()

# A project on `main`: a source tree with a nested subpackage, a flat test tree beside a nested
# one that mirrors the subpackage, the root and a nested conftest, and a support module.
_PROJECT = {
    "src/devops_cli/__init__.py": "",
    "src/devops_cli/orphan.py": "ORPHAN = 1\n",
    "src/devops_cli/ai/__init__.py": "",
    "src/devops_cli/ai/review/__init__.py": "",
    "src/devops_cli/ai/review/pipeline.py": "STAGES = 1\n",
    "src/devops_cli/commands/__init__.py": "",
    "src/devops_cli/commands/scan.py": "SCAN = 1\n",
    "tests/__init__.py": "",
    "tests/conftest.py": "",
    "tests/support/__init__.py": "",
    "tests/support/paths.py": "ROOT = None\n",
    "tests/test_scan.py": "def test_scan() -> None: ...\n",
    "tests/test_scanner.py": "def test_scanner() -> None: ...\n",
    "tests/test_reports.py": "from devops_cli.commands.scan import SCAN\n",
    "tests/test_old.py": "def test_old() -> None: ...\n",
    "tests/ai/__init__.py": "",
    "tests/ai/conftest.py": "",
    "tests/ai/review/__init__.py": "",
    "tests/ai/review/test_a.py": "def test_a() -> None: ...\n",
    "tests/ai/review/test_b.py": "def test_b() -> None: ...\n",
    "tests/ai/review/stages/__init__.py": "",
    "tests/ai/review/stages/test_c.py": "def test_c() -> None: ...\n",
}


@pytest.fixture
def project(tmp_path: Path, git: Callable[..., None], monkeypatch: pytest.MonkeyPatch) -> Path:
    """The project committed on `main`, checked out on a topic branch, as the working directory."""
    root = tmp_path / "project"
    for relative, text in _PROJECT.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    git(root, "checkout", "-q", "-b", "topic")
    monkeypatch.chdir(root)
    return root


def _commit(root: Path, git: Callable[..., None], *changed: str) -> None:
    """Change each of `changed` on the topic branch and commit it."""
    for relative in changed:
        path = root / relative
        path.write_text(path.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "change")


def _changed_run() -> tuple[list[str], str]:
    """The pytest targets `devops test run --changed --dry-run` names, and what it printed."""
    result = runner.invoke(app_cli, ["run", "--changed", "--dry-run"])
    assert result.exit_code == 0, result.output
    response = json.loads(result.output.split("Command response:\n")[1])
    return response["details"]["targets"], result.output


def test_a_changed_nested_test_module_is_selected(project: Path, git: Callable[..., None]) -> None:
    _commit(project, git, "tests/ai/review/stages/test_c.py")
    assert _changed_run()[0] == ["tests/ai/review/stages/test_c.py"]


def test_a_changed_source_module_selects_the_test_modules_directly_in_its_mirror_directory(
    project: Path, git: Callable[..., None]
) -> None:
    """`devops_cli.ai.review.pipeline` mirrors to `tests/ai/review/`: its test modules run, and
    those of its subdirectories do not."""
    _commit(project, git, "src/devops_cli/ai/review/pipeline.py")
    assert _changed_run()[0] == ["tests/ai/review/test_a.py", "tests/ai/review/test_b.py"]


def test_a_flat_tree_maps_a_source_module_by_its_name_and_its_importers(
    project: Path, git: Callable[..., None]
) -> None:
    _commit(project, git, "src/devops_cli/commands/scan.py")
    assert _changed_run()[0] == ["tests/test_reports.py", "tests/test_scan.py"]


def test_a_changed_conftest_selects_its_directory(project: Path, git: Callable[..., None]) -> None:
    """A fixture reaches every test beside and below its conftest, none of which imports it."""
    _commit(project, git, "tests/ai/conftest.py")
    assert _changed_run()[0] == ["tests/ai"]


def test_a_changed_support_module_selects_the_whole_suite(
    project: Path, git: Callable[..., None]
) -> None:
    """A support module may reach any test, through a fixture it registers."""
    _commit(project, git, "tests/support/paths.py")
    assert _changed_run()[0] == ["tests"]


def test_a_renamed_source_module_selects_by_its_new_path(
    project: Path, git: Callable[..., None]
) -> None:
    """A staged `git mv` is read from `git status --porcelain`, by the path it moves to."""
    git(project, "mv", "src/devops_cli/commands/scan.py", "src/devops_cli/commands/scanner.py")
    assert _changed_run()[0] == ["tests/test_scanner.py"]


def test_a_deleted_test_module_is_not_passed_to_pytest(
    project: Path, git: Callable[..., None]
) -> None:
    git(project, "rm", "-q", "tests/test_old.py")
    _commit(project, git, "tests/test_scan.py")
    assert _changed_run()[0] == ["tests/test_scan.py"]


def test_an_unmapped_source_is_named_and_the_mapped_tests_run(
    project: Path, git: Callable[..., None]
) -> None:
    _commit(project, git, "src/devops_cli/commands/scan.py", "src/devops_cli/orphan.py")
    targets, output = _changed_run()
    assert (targets, "No test module covers src/devops_cli/orphan.py" in output) == (
        ["tests/test_reports.py", "tests/test_scan.py"],
        True,
    )


def test_no_change_runs_the_whole_suite(project: Path) -> None:
    assert _changed_run()[0] == ["tests"]


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


def test_parse_whitelist_and_validate_sandbox_network() -> None:
    """Verify _parse_whitelist and _validate_sandbox_network handle valid and invalid inputs."""
    import pytest
    import typer

    from devops_cli.commands.test_cmd import _parse_whitelist, _validate_sandbox_network

    # Empty raw returns empty list
    assert _parse_whitelist(None, "public") == []
    assert _parse_whitelist("", "public") == []

    # Valid tokens
    tokens = _parse_whitelist("example.com, 127.0.0.1:8080 , api.service", "public")
    assert tokens == ["example.com", "127.0.0.1:8080", "api.service"]

    # Invalid token with forbidden characters
    with pytest.raises(typer.BadParameter, match="Invalid public whitelist entry"):
        _parse_whitelist("invalid token with spaces", "public")

    # Invalid network mode
    with pytest.raises(typer.BadParameter, match="Invalid network mode"):
        _validate_sandbox_network("invalid-mode", "isolated", None, None)

    # Valid bridge mode with warning
    mode, pub, loc = _validate_sandbox_network("bridge", "bridge", "example.com", "localhost:8000")
    assert mode == "bridge"
    assert pub == ["example.com"]
    assert loc == ["localhost:8000"]


def test_test_sandbox_execution_and_failure() -> None:
    """Verify test sandbox execution outputs and error exit codes."""
    mock_runner = MagicMock()
    mock_runner.run.return_value = MagicMock(
        exit_code=0, stdout="Container output", stderr="Warning output", duration_seconds=1.23
    )

    with (
        patch("devops_cli.docker.sandbox.WorkloadSandboxRunner", return_value=mock_runner),
        patch("devops_cli.commands.test_cmd.print_info"),
        patch("devops_cli.commands.test_cmd.print_success"),
    ):
        res = runner.invoke(app_cli, ["sandbox", "echo", "hello"])
        assert res.exit_code == 0

    # Non-zero exit code
    mock_runner_fail = MagicMock()
    mock_runner_fail.run.return_value = MagicMock(
        exit_code=42, stdout="", stderr="Crash", duration_seconds=0.5
    )
    with patch("devops_cli.docker.sandbox.WorkloadSandboxRunner", return_value=mock_runner_fail):
        res_fail = runner.invoke(app_cli, ["sandbox", "false"])
        assert res_fail.exit_code == 42


def test_profile_memory_error_handling() -> None:
    """Verify profile-memory handles MemoryProfilerError with exit code 1."""
    from devops_cli.telemetry.memory_profiler import MemoryProfilerError

    with patch(
        "devops_cli.commands.test_cmd.run_memory_profiler",
        side_effect=MemoryProfilerError("profiling failed"),
    ):
        res = runner.invoke(app_cli, ["profile-memory", "devops_cli.main:app"])
        assert res.exit_code == 1
        assert "profiling failed" in res.output


def test_test_run_runs_pytest_in_a_nested_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops test run` from a worktree under `.claude/worktrees/` runs pytest there,
    not in the checkout around it (#582)."""
    _, nested = nested_worktree
    monkeypatch.chdir(nested)

    with patch(
        "devops_cli.commands.test_cmd.run_subprocess", return_value=MagicMock(returncode=0)
    ) as run:
        result = runner.invoke(app_cli, ["run"])

    assert (result.exit_code, run.call_args.kwargs["cwd"]) == (0, nested.resolve())
