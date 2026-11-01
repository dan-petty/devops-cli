"""Unit tests for uv CLI subcommands (devops_cli.commands.uv)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.uv import _get_project_root
from devops_cli.commands.uv import app as uv_app
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessFake

runner = CliRunner()


def _mock_proc(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["uv"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_uv_commands(tmp_path: Path) -> None:
    """Verify uv sync, lock, and python-install subcommands."""
    with patch("devops_cli.commands.uv.run_subprocess", return_value=_mock_proc(0)):
        res_sync = runner.invoke(uv_app, ["sync", "--frozen"])
        assert res_sync.exit_code == 0

        res_lock = runner.invoke(uv_app, ["lock", "--upgrade"])
        assert res_lock.exit_code == 0

        res_py = runner.invoke(uv_app, ["python-install", "--version", "3.14.0"])
        assert res_py.exit_code == 0

        # uv run with args
        res_run = runner.invoke(uv_app, ["run", "pytest", "-q"])
        assert res_run.exit_code == 0


def test_uv_python_install_and_run_edge_cases(tmp_path: Path) -> None:
    """Verify uv python-install from .python-version, invalid version, and uv run errors."""

    # 1. uv run missing args
    res_no_args = runner.invoke(uv_app, ["run"])
    assert res_no_args.exit_code == 1

    # 2. python-install from .python-version file
    (tmp_path / ".python-version").write_text("3.14.10\n", encoding="utf-8")
    with (
        patch("devops_cli.commands.uv._get_project_root", return_value=tmp_path),
        patch("devops_cli.commands.uv.run_subprocess", return_value=_mock_proc(0)),
    ):
        res_pv = runner.invoke(uv_app, ["python-install"])
        assert res_pv.exit_code == 0

    # 3. python-install without version or .python-version
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with patch("devops_cli.commands.uv._get_project_root", return_value=empty_dir):
        res_err = runner.invoke(uv_app, ["python-install"])
        assert res_err.exit_code == 1

    # 4. python-install invalid version format
    res_bad = runner.invoke(uv_app, ["python-install", "--version", "bad$$version"])
    assert res_bad.exit_code == 1

    # 5. Non-zero exit from subprocess
    with patch("devops_cli.commands.uv.run_subprocess", return_value=_mock_proc(2)):
        res_fail = runner.invoke(uv_app, ["sync"])
        assert res_fail.exit_code == 2


@pytest.fixture
def nested_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Provide a nested worktree without starting git processes."""
    main = tmp_path / "main"
    main.mkdir(parents=True, exist_ok=True)
    (main / ".git").mkdir(parents=True, exist_ok=True)
    (main / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (main / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (main / "pyproject.toml").write_text(
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n',
        encoding="utf-8",
    )
    nested = main / ".claude" / "worktrees" / "wt"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.mkdir(parents=True, exist_ok=True)
    (nested / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (nested / "pyproject.toml").write_text(
        '[project]\nname = "main"\n\n[tool.ruff.lint]\nselect = ["F401"]\n',
        encoding="utf-8",
    )
    wt_git = main / ".git" / "worktrees" / "wt"
    wt_git.mkdir(parents=True, exist_ok=True)
    (nested / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
    (wt_git / "gitdir").write_text(f"{nested / '.git'}\n", encoding="utf-8")
    (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
    (wt_git / "HEAD").write_text("ref: refs/heads/nested\n", encoding="utf-8")
    return main, nested


def test_uv_operates_on_a_nested_worktree(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    git_fake: GitFake,
) -> None:
    """Verify `devops uv` from a worktree under `.claude/worktrees/` syncs and locks that
    worktree's own project, not the checkout around it (#582)."""
    _, nested = nested_worktree
    monkeypatch.chdir(nested)

    assert _get_project_root() == nested.resolve()


# =============================================================================
# Dry runs (#2260)
# =============================================================================


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    import re

    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


_UV = "uv --preview-features malware-check,check-command"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["sync", "--frozen"], f"{_UV} sync --frozen"),
        (["lock", "--upgrade"], f"{_UV} lock --upgrade"),
        (["python-install", "--version", "3.14.10"], f"{_UV} python install 3.14.10"),
        (["run", "--", "pytest", "-q", "--dry-run"], f"{_UV} run pytest -q --dry-run"),
    ],
)
@pytest.mark.parametrize("flag_first", [True, False])
def test_uv_dry_run_lists_the_one_uv_command(
    cli: Any,
    process_fake: ProcessFake,
    argv: list[str],
    expected: str,
    flag_first: bool,
) -> None:
    """A dry run starts no process and lists the uv command as the runner would start it."""
    if flag_first:
        full = ["--dry-run", "uv", *argv]
    elif "--" in argv:
        cut = argv.index("--")
        full = ["uv", *argv[:cut], "--dry-run", *argv[cut:]]
    else:
        full = ["uv", *argv, "--dry-run"]

    result = cli(full)

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    assert _plan_lines(result.output) == [expected]


def test_uv_python_install_dry_run_reads_the_python_version_file(
    tmp_path: Path, cli: Any, process_fake: ProcessFake
) -> None:
    """Without `--version`, the plan holds the version of `.python-version`."""
    (tmp_path / ".python-version").write_text("3.14.10\n", encoding="utf-8")
    with patch("devops_cli.commands.uv._get_project_root", return_value=tmp_path):
        result = cli(["uv", "python-install", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert _plan_lines(result.output) == [f"{_UV} python install 3.14.10"]
    assert process_fake.calls == []


def test_uv_dry_run_refuses_what_a_run_refuses(cli: Any, process_fake: ProcessFake) -> None:
    """A bad version and a missing command end the dry run as they end the run."""
    assert cli(["uv", "python-install", "--version", "3;rm", "--dry-run"]).exit_code == 1
    assert cli(["uv", "run", "--dry-run"]).exit_code == 1
    assert process_fake.calls == []


@pytest.mark.parametrize(
    "argv",
    [
        ["sync", "--frozen"],
        ["lock", "--upgrade"],
        ["python-install", "--version", "3.14.10"],
        ["run", "--", "pytest", "-q"],
    ],
)
def test_uv_runs_the_request_of_its_plan(
    cli: Any, process_fake: ProcessFake, argv: list[str]
) -> None:
    """The real run starts the command of the plan."""
    planned = _plan_lines(cli(["--dry-run", "uv", *argv]).output)

    result = cli(["uv", *argv])

    assert result.exit_code == 0, result.output
    assert [" ".join(call.argv) for call in process_fake.calls] == planned
