"""Unit tests for uv CLI subcommands (devops_cli.commands.uv)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessFake

_UV = "uv --preview-features malware-check,check-command"


def _project(directory: Path, python_version: str | None = None) -> Path:
    """Make `directory` a project root, with a `.python-version` file when given a version."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    if python_version is not None:
        (directory / ".python-version").write_text(f"{python_version}\n", encoding="utf-8")
    return directory


def test_uv_commands(cli: Any, process_fake: ProcessFake) -> None:
    """Verify uv sync, lock, and python-install subcommands."""
    res_sync = cli(["uv", "sync", "--frozen"])
    assert res_sync.exit_code == 0

    res_lock = cli(["uv", "lock", "--upgrade"])
    assert res_lock.exit_code == 0

    res_py = cli(["uv", "python-install", "--version", "3.14.0"])
    assert res_py.exit_code == 0

    # uv run with args
    res_run = cli(["uv", "run", "pytest", "-q"])
    assert res_run.exit_code == 0

    assert [" ".join(call.argv) for call in process_fake.calls] == [
        f"{_UV} sync --frozen",
        f"{_UV} lock --upgrade",
        f"{_UV} python install 3.14.0",
        f"{_UV} run pytest -q",
    ]


def test_uv_python_install_and_run_edge_cases(
    tmp_path: Path,
    cli: Any,
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify uv python-install from .python-version, invalid version, and uv run errors."""
    with_version = _project(tmp_path / "with-version", "3.14.10")
    empty_dir = _project(tmp_path / "empty")

    # 1. uv run missing args
    res_no_args = cli(["uv", "run"])
    assert res_no_args.exit_code == 1

    # 2. python-install from .python-version file
    monkeypatch.chdir(with_version)
    res_pv = cli(["uv", "python-install"])
    assert res_pv.exit_code == 0
    assert [" ".join(call.argv) for call in process_fake.calls] == [f"{_UV} python install 3.14.10"]

    # 3. python-install without version or .python-version
    monkeypatch.chdir(empty_dir)
    res_err = cli(["uv", "python-install"])
    assert res_err.exit_code == 1

    # 4. python-install invalid version format
    res_bad = cli(["uv", "python-install", "--version", "bad$$version"])
    assert res_bad.exit_code == 1

    # 5. Non-zero exit from subprocess
    process_fake.answer("uv", ProcessAnswer(returncode=2))
    res_fail = cli(["uv", "sync"])
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
    cli: Any,
    process_fake: ProcessFake,
) -> None:
    """Verify `devops uv` from a worktree under `.claude/worktrees/` syncs and locks that
    worktree's own project, not the checkout around it (#582)."""
    _, nested = nested_worktree
    monkeypatch.chdir(nested)

    results = [cli(["uv", "sync"]), cli(["uv", "lock"])]

    assert [result.exit_code for result in results] == [0, 0]
    assert [call.cwd for call in process_fake.calls] == [nested.resolve()] * 2


# =============================================================================
# Dry runs (#2260)
# =============================================================================


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    import re

    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


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
    tmp_path: Path,
    cli: Any,
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without `--version`, the plan holds the version of `.python-version`."""
    monkeypatch.chdir(_project(tmp_path / "project", "3.14.10"))
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
