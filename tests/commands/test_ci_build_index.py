"""Unit tests for devops ci coverage --build-index command and lifecycle."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ci.cache import resolve_coverage_index_path
from devops_cli.commands.ci import app as ci_app
from devops_cli.commands.ci import get_check_spec
from devops_cli.core.coverage_index import INDEX_FORMAT_VERSION, load_index

runner = CliRunner()


def _make_git_repo(tmp_path: Path) -> Path:
    """Initialize a miniature git repository with tracked source and test files."""
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "dev@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Dev"], cwd=tmp_path, check=True, capture_output=True
    )

    src_dir = tmp_path / "src" / "devops_cli"
    src_dir.mkdir(parents=True)
    (src_dir / "a.py").write_text("A = 1\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"], cwd=tmp_path, check=True, capture_output=True
    )
    return tmp_path


def _write_minimal_coverage_db(db_path: Path, src_abs: Path, test_rel: str) -> None:
    """Write a minimal SQLite coverage database in the shape produced with --cov-context=test."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(
        "CREATE TABLE file (id INTEGER PRIMARY KEY, path TEXT);"
        "CREATE TABLE context (id INTEGER PRIMARY KEY, context TEXT);"
        "CREATE TABLE line_bits (file_id INTEGER, context_id INTEGER, numbits BLOB);"
    )
    con.execute("INSERT INTO file VALUES (1, ?)", (str(src_abs),))
    con.execute("INSERT INTO context VALUES (1, ?)", (f"{test_rel}::test_case|run",))
    con.execute("INSERT INTO line_bits VALUES (1, 1, ?)", (b"",))
    con.commit()
    con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 1: Exact build command and environment
# ─────────────────────────────────────────────────────────────────────────────


def test_coverage_build_index_runs_exact_argv_and_ctrace_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--build-index appends --cov-context=test and passes COVERAGE_CORE=ctrace to run_subprocess."""
    executed: list[tuple[list[str], dict[str, str] | None]] = []

    def mock_run_subprocess(
        cmd: list[str], *args: Any, env: dict[str, str] | None = None, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        executed.append((cmd, env))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: tmp_path)
    monkeypatch.setattr("devops_cli.commands.ci.run_subprocess", mock_run_subprocess)
    monkeypatch.setattr("devops_cli.ci.cache.compute_worktree_blob_hashes", lambda root: {})

    result = runner.invoke(ci_app, ["coverage", "--build-index"])

    base_spec = get_check_spec("test")
    expected_cmd = list(base_spec.cmd)
    if expected_cmd and expected_cmd[0] == "uv" and "--preview-features" not in expected_cmd:
        expected_cmd[1:1] = ["--preview-features", "malware-check,check-command"]
    expected_cmd.append("--cov-context=test")

    assert (
        result.exit_code,
        len(executed),
        executed[0][0],
        executed[0][1],
    ) == (
        0,
        1,
        expected_cmd,
        {"COVERAGE_CORE": "ctrace"},
    )


def test_coverage_without_build_index_preserves_standard_argv_and_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Plain devops ci coverage does not pass --cov-context or COVERAGE_CORE."""
    executed: list[tuple[list[str], dict[str, str] | None]] = []

    def mock_run_subprocess(
        cmd: list[str], *args: Any, env: dict[str, str] | None = None, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        executed.append((cmd, env))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: tmp_path)
    monkeypatch.setattr("devops_cli.commands.ci.run_subprocess", mock_run_subprocess)

    result = runner.invoke(ci_app, ["coverage"])

    base_spec = get_check_spec("test")
    expected_cmd = list(base_spec.cmd)
    if expected_cmd and expected_cmd[0] == "uv" and "--preview-features" not in expected_cmd:
        expected_cmd[1:1] = ["--preview-features", "malware-check,check-command"]

    assert (
        result.exit_code,
        len(executed),
        executed[0][0],
        executed[0][1],
    ) == (
        0,
        1,
        expected_cmd,
        None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 2: Save index only after clean passing run
# ─────────────────────────────────────────────────────────────────────────────


def test_build_index_saves_index_after_passing_clean_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A passing run on an unmodified tree builds and writes the reverse coverage index."""
    repo = _make_git_repo(tmp_path)
    coverage_db = repo / ".data" / ".coverage"

    def mock_run(cmd: list[str], *a: Any, **kw: Any) -> bool:
        _write_minimal_coverage_db(
            coverage_db, repo / "src" / "devops_cli" / "a.py", "tests/test_a.py"
        )
        return True

    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: repo)
    monkeypatch.setattr("devops_cli.commands.ci._run", mock_run)

    result = runner.invoke(ci_app, ["coverage", "--build-index"])

    target_path = resolve_coverage_index_path(repo)
    index = load_index(target_path)
    assert (
        result.exit_code,
        target_path.is_file(),
        index.version,
        index.covering_tests.get("src/devops_cli/a.py"),
    ) == (
        0,
        True,
        INDEX_FORMAT_VERSION,
        ["tests/test_a.py"],
    )


def test_build_index_saves_nothing_on_failed_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A failing test run saves nothing and exits with a nonzero status code."""
    repo = _make_git_repo(tmp_path)

    def mock_run(cmd: list[str], *a: Any, **kw: Any) -> bool:
        return False

    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: repo)
    monkeypatch.setattr("devops_cli.commands.ci._run", mock_run)

    result = runner.invoke(ci_app, ["coverage", "--build-index"])

    target_path = resolve_coverage_index_path(repo)
    assert (result.exit_code, target_path.is_file()) == (1, False)


def test_build_index_saves_nothing_and_exits_1_when_tree_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When a tracked source file changes during the run, save nothing and exit 1."""
    repo = _make_git_repo(tmp_path)
    coverage_db = repo / ".data" / ".coverage"

    def mock_run_with_mutation(cmd: list[str], *a: Any, **kw: Any) -> bool:
        _write_minimal_coverage_db(
            coverage_db, repo / "src" / "devops_cli" / "a.py", "tests/test_a.py"
        )
        # Mutate tracked source file during execution
        (repo / "src" / "devops_cli" / "a.py").write_text("A = 999\n", encoding="utf-8")
        return True

    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: repo)
    monkeypatch.setattr("devops_cli.commands.ci._run", mock_run_with_mutation)

    result = runner.invoke(ci_app, ["coverage", "--build-index"])

    target_path = resolve_coverage_index_path(repo)
    assert (
        result.exit_code,
        target_path.is_file(),
        "src/devops_cli/a.py" in result.output,
    ) == (
        1,
        False,
        True,
    )
