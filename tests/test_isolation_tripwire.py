"""Unit tests for the test session workspace isolation tripwire (Issue #749)."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.conftest import (
    _check_config_diff,
    _check_forbidden_test_paths,
    _check_test_paths_isolated,
    _check_tracked_diff,
    _evaluate_workspace_tripwire,
    _get_git_tracked_files,
    _is_xdist_worker,
    _snapshot_tracked_files,
    pytest_sessionfinish,
    pytest_sessionstart,
    pytest_terminal_summary,
)


def test_is_xdist_worker_detection() -> None:
    """Verify _is_xdist_worker accurately distinguishes controller from xdist workers."""
    controller_cfg = pytest.Config.fromdictargs({}, [])
    worker_cfg = SimpleNamespace(workerinput={"workerid": "gw0"})

    assert (
        _is_xdist_worker(controller_cfg),
        _is_xdist_worker(worker_cfg),  # type: ignore[arg-type]
    ) == (False, True)


def test_get_git_tracked_files_resolves_repo(tmp_path: Path) -> None:
    """Verify _get_git_tracked_files executes git ls-files and handles non-git folders gracefully."""
    tracked = _get_git_tracked_files(tmp_path)
    assert tracked == []


def test_snapshot_tracked_files_captures_mtime_and_size(tmp_path: Path) -> None:
    """Verify _snapshot_tracked_files records stat stamps for existing files only."""
    f1 = tmp_path / "file1.txt"
    f1.write_text("hello", encoding="utf-8")
    st = f1.stat()

    stamps = _snapshot_tracked_files(tmp_path, ["file1.txt", "nonexistent.txt"])
    assert stamps == {"file1.txt": (st.st_mtime_ns, st.st_size)}


def test_check_config_diff_permutations(tmp_path: Path) -> None:
    """Verify _check_config_diff identifies creation, deletion, and modification states."""
    repo_dir = tmp_path / "custom_repo"
    repo_dir.mkdir()
    cfg = repo_dir / "config.yaml"

    # Case 1: Unchanged (absent)
    res_absent = _check_config_diff(repo_dir, None)

    # Case 2: Created
    cfg.write_text("foo: 1", encoding="utf-8")
    res_created = _check_config_diff(repo_dir, None)

    # Case 3: Unchanged (present)
    res_unchanged = _check_config_diff(repo_dir, b"foo: 1")

    # Case 4: Modified
    cfg.write_text("foo: 2", encoding="utf-8")
    res_modified = _check_config_diff(repo_dir, b"foo: 1")

    # Case 5: Deleted
    cfg.unlink()
    res_deleted = _check_config_diff(repo_dir, b"foo: 1")

    assert (
        res_absent,
        res_created,
        res_unchanged,
        res_modified,
        res_deleted,
    ) == (
        None,
        "config.yaml (created by tests)",
        None,
        "config.yaml (content modified by tests)",
        "config.yaml (deleted by tests)",
    )


def test_check_tracked_diff_detects_mutations(tmp_path: Path) -> None:
    """Verify _check_tracked_diff detects deleted and modified tracked files."""
    f1 = tmp_path / "tracked1.py"
    f1.write_text("print('v1')", encoding="utf-8")
    init_st1 = f1.stat()

    f2 = tmp_path / "tracked2.py"
    f2.write_text("print('orig')", encoding="utf-8")
    init_st2 = f2.stat()

    snapshot = {
        "tracked1.py": (init_st1.st_mtime_ns, init_st1.st_size),
        "tracked2.py": (init_st2.st_mtime_ns, init_st2.st_size),
    }

    # Simulate f1 modified and f2 deleted
    f1.write_text("print('v2-modified')", encoding="utf-8")
    f2.unlink()

    diffs = _check_tracked_diff(tmp_path, snapshot)
    assert diffs == [
        "tracked1.py (modified by tests)",
        "tracked2.py (deleted by tests)",
    ]


def test_check_tracked_diff_compares_content_in_a_linked_worktree(
    nested_worktree: tuple[Path, Path],
) -> None:
    """In a linked worktree, where `.git` is a file, a tracked file rewritten unchanged is not
    a mutation and an edited one is. `devops ci` regenerates the docs while the tests run, so
    requiring `.git/index` failed the gate from every worktree."""
    _, worktree = nested_worktree
    touched, edited = worktree / ".gitignore", worktree / "pyproject.toml"
    snapshot = _snapshot_tracked_files(worktree, [".gitignore", "pyproject.toml"])

    stamp = touched.stat()
    os.utime(touched, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
    edited.write_text(edited.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")

    assert ((worktree / ".git").is_file(), _check_tracked_diff(worktree, snapshot)) == (
        True,
        ["pyproject.toml (modified by tests)"],
    )


def test_check_forbidden_test_paths_detects_test_artifacts(tmp_path: Path) -> None:
    """Verify _check_forbidden_test_paths identifies test artifacts created in project root."""
    repo_dir = tmp_path / "custom_repo"
    repo_dir.mkdir()

    # Initially empty
    assert _check_forbidden_test_paths(repo_dir) == []

    # Create forbidden test paths
    (repo_dir / "test_config.yaml").write_text("dummy", encoding="utf-8")
    (repo_dir / ".data").mkdir(parents=True, exist_ok=True)
    (repo_dir / ".data" / "test_llm_cache").mkdir(parents=True, exist_ok=True)

    violations = _check_forbidden_test_paths(repo_dir)
    assert (
        "test_config.yaml (test path found in project directory)" in violations,
        ".data/test_llm_cache (test path found in project directory)" in violations,
    ) == (True, True)


def test_check_test_paths_isolated_rejects_project_dir(tmp_path: Path) -> None:
    """Verify _check_test_paths_isolated flags test paths located within repo root."""
    repo_dir = tmp_path / "project"
    repo_dir.mkdir()
    outside_dir = tmp_path / "isolated_tmp"
    outside_dir.mkdir()

    # Clean outside paths
    valid_paths = [outside_dir / "config.yaml", outside_dir / ".data"]
    assert _check_test_paths_isolated(valid_paths, repo_dir) == []

    # Leaked inside path
    leaked_paths = [outside_dir / "config.yaml", repo_dir / "config.yaml"]
    violations = _check_test_paths_isolated(leaked_paths, repo_dir)
    assert (
        len(violations),
        "inside project directory" in violations[0],
    ) == (1, True)


def test_evaluate_workspace_tripwire_aggregates_failures(tmp_path: Path) -> None:
    """Verify _evaluate_workspace_tripwire aggregates config, tracked, and forbidden failures."""
    repo_dir = tmp_path / "eval_repo"
    repo_dir.mkdir()
    (repo_dir / "config.yaml").write_text("bad: true", encoding="utf-8")
    (repo_dir / "test_config.yaml").write_text("leak: true", encoding="utf-8")

    snapshot: dict[str, Any] = {
        "repo_root": repo_dir,
        "config_state": None,
        "tracked_snapshot": {},
    }
    failures = _evaluate_workspace_tripwire(snapshot)

    assert (
        "config.yaml (created by tests)" in failures,
        "test_config.yaml (test path found in project directory)" in failures,
    ) == (True, True)


def test_session_hooks_lifecycle(tmp_path: Path) -> None:
    """Verify pytest_sessionstart and pytest_sessionfinish hooks record and trigger failure."""
    session = MagicMock()
    session.config = SimpleNamespace()

    # Session start snapshots
    pytest_sessionstart(session)
    assert hasattr(session.config, "_tripwire_snapshot")

    # Worker skips finish
    worker_session = MagicMock()
    worker_session.config = SimpleNamespace(workerinput={"workerid": "gw0"})
    pytest_sessionfinish(worker_session, 0)
    assert not hasattr(worker_session.config, "_tripwire_failures")

    # Controller with simulated failure
    repo_dir = tmp_path / "sim_repo"
    repo_dir.mkdir()
    cfg_leak = SimpleNamespace(
        _tripwire_snapshot={
            "repo_root": repo_dir,
            "config_state": b"initial",
            "tracked_snapshot": {},
        }
    )
    fail_session = MagicMock()
    fail_session.config = cfg_leak
    pytest_sessionfinish(fail_session, 0)
    assert (
        fail_session.exitstatus,
        getattr(cfg_leak, "_tripwire_failures", []),
    ) == (
        pytest.ExitCode.TESTS_FAILED,
        ["config.yaml (deleted by tests)"],
    )


def test_terminal_summary_reporting() -> None:
    """Verify pytest_terminal_summary prints section on failure and skips on workers."""
    reporter = MagicMock()

    # Worker skips
    worker_cfg = SimpleNamespace(workerinput={"workerid": "gw0"})
    pytest_terminal_summary(reporter, 0, worker_cfg)  # type: ignore[arg-type]
    assert not reporter.section.called

    # Controller with failures writes section
    ctrl_cfg = SimpleNamespace(_tripwire_failures=["config.yaml (created by tests)"])
    pytest_terminal_summary(reporter, 0, ctrl_cfg)  # type: ignore[arg-type]
    assert (
        reporter.section.called,
        reporter.write_line.called,
    ) == (True, True)
