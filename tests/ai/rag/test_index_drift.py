"""Index drift: what the working tree, the index cache, git and Qdrant say about a stale index."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.drift import RAGDriftDetector, RAGDriftReport
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.config.defaults import DEFAULT_MAX_AST_FILE_SIZE_BYTES
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.qdrant import seed_knowledge_base

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture
def indexer(tmp_path: Path, qdrant: Any, embedder: Any) -> WorkspaceIndexer:
    seed_knowledge_base(qdrant, embedding_model=embedder.model)
    return WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")


def _detector(root: Path, indexer: WorkspaceIndexer) -> RAGDriftDetector:
    return RAGDriftDetector(root_dir=root, indexer=indexer, cache_dir=root / ".cache")


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


def test_a_workspace_that_was_indexed_has_no_drift(
    tmp_path: Path, indexer: WorkspaceIndexer
) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "main.py").write_text("def hello(): pass\n", encoding="utf-8")
    indexer.index_workspace(workspace, include_kb=False)

    report = _detector(workspace, indexer).detect_drift(
        last_indexed_commit="commit_123", current_commit="commit_123"
    )

    assert isinstance(report, RAGDriftReport)
    assert (
        report.drift_score,
        report.stale_files,
        report.new_files,
        report.deleted_files,
        report.git_commit_drift,
    ) == (0.0, [], [], [], False)


def test_a_file_that_was_never_indexed_is_new(tmp_path: Path, indexer: WorkspaceIndexer) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "new_module.py").write_text("x = 1\n", encoding="utf-8")

    report = _detector(workspace, indexer).detect_drift(current_cache={})

    assert ("new_module.py" in report.new_files, report.drift_score > 0.0) == (True, True)


def test_a_file_changed_after_it_was_indexed_is_stale(
    tmp_path: Path, indexer: WorkspaceIndexer
) -> None:
    workspace = _workspace(tmp_path)
    service = workspace / "service.py"
    service.write_text("class Service: pass\n", encoding="utf-8")
    indexer.index_workspace(workspace, include_kb=False)
    service.write_text("class Service:\n    changed = True\n", encoding="utf-8")

    report = _detector(workspace, indexer).detect_drift()

    assert (report.stale_files, report.drift_score > 0.0) == (["service.py"], True)


def test_a_file_deleted_after_it_was_indexed_is_reported_deleted(
    tmp_path: Path, indexer: WorkspaceIndexer
) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "keep.py").write_text("x = 1\n", encoding="utf-8")
    missing = workspace / "missing_file.py"
    missing.write_text("y = 2\n", encoding="utf-8")
    indexer.index_workspace(workspace, include_kb=False)
    missing.unlink()

    report = _detector(workspace, indexer).detect_drift()

    assert ("missing_file.py" in report.deleted_files, report.drift_score > 0.0) == (True, True)


def test_a_new_commit_since_the_index_run_is_commit_drift(
    tmp_path: Path, indexer: WorkspaceIndexer
) -> None:
    report = _detector(_workspace(tmp_path), indexer).detect_drift(
        current_cache={}, last_indexed_commit="abc1234", current_commit="def5678"
    )

    assert (report.git_commit_drift, report.last_indexed_commit, report.current_head_commit) == (
        True,
        "abc1234",
        "def5678",
    )


def test_a_store_that_holds_no_point_of_the_project_makes_every_file_stale(
    tmp_path: Path, indexer: WorkspaceIndexer, qdrant: Any
) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "main.py").write_text("def hello(): pass\n", encoding="utf-8")
    indexer.index_workspace(workspace, include_kb=False)
    qdrant.collections["devops_code"] = []

    report = _detector(workspace, indexer).detect_drift()

    assert report.stale_files == ["main.py"]


def test_auto_sync_indexes_the_drifted_workspace(tmp_path: Path, indexer: WorkspaceIndexer) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "app.py").write_text("print('hello')\n", encoding="utf-8")

    report = _detector(workspace, indexer).detect_and_sync(auto_sync=True)
    after = _detector(workspace, indexer).detect_drift()

    assert (report.reindexed_files, after.drift_score) == (1, 0.0)


def test_without_auto_sync_a_drifted_workspace_is_only_reported(
    tmp_path: Path, indexer: WorkspaceIndexer, qdrant: Any
) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "app.py").write_text("print('hello')\n", encoding="utf-8")

    report = _detector(workspace, indexer).detect_and_sync()

    assert (report.reindexed_files, report.new_files, qdrant.collections.get("devops_code")) == (
        0,
        ["app.py"],
        None,
    )


def test_symlinks_oversized_files_and_paths_outside_the_root_are_not_scanned(
    tmp_path: Path, indexer: WorkspaceIndexer
) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "valid.py").write_text("x = 42\n", encoding="utf-8")
    (workspace / "target.py").write_text("y = 100\n", encoding="utf-8")
    (workspace / "symlink.py").symlink_to(workspace / "target.py")
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    (outside / "external.py").write_text("z = 1\n", encoding="utf-8")
    (workspace / "linked_dir").symlink_to(outside, target_is_directory=True)
    with (workspace / "huge.py").open("wb") as huge:
        huge.truncate(DEFAULT_MAX_AST_FILE_SIZE_BYTES + 1)

    report = _detector(workspace, indexer).detect_drift(current_cache={})

    assert report.new_files == ["target.py", "valid.py"]


def test_drift_reads_the_head_commit_with_git_through_the_process_seam(
    tmp_path: Path, indexer: WorkspaceIndexer, process_fake: ProcessFake
) -> None:
    """The head commit is a local read of `git rev-parse HEAD` in the root, through the process
    seam (#1538)."""
    process_fake.answer(["git", "rev-parse", "HEAD"], ProcessAnswer(stdout="abc123\n"))
    workspace = _workspace(tmp_path)

    report = _detector(workspace, indexer).detect_drift(
        current_cache={}, last_indexed_commit="abc123"
    )

    call = process_fake.calls[0]
    assert (report.current_head_commit, call.argv, call.cwd, call.local_read) == (
        "abc123",
        ("git", "rev-parse", "HEAD"),
        workspace,
        True,
    )


def test_drift_without_git_has_no_head_commit_and_logs_the_missing_program(
    tmp_path: Path,
    indexer: WorkspaceIndexer,
    process_fake: ProcessFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A missing `git` gives no head commit, and the log line names the program (#1538)."""
    process_fake.answer(
        "git", ProcessAnswer(returncode=127, stderr="Executable 'git' not found in PATH")
    )

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.drift"):
        report = _detector(_workspace(tmp_path), indexer).detect_drift(
            current_cache={}, last_indexed_commit="abc123"
        )

    assert (report.current_head_commit, "Executable 'git' not found" in caplog.text) == (
        None,
        True,
    )


def test_drift_has_no_head_commit_when_git_runs_out_of_time(
    tmp_path: Path, indexer: WorkspaceIndexer, process_fake: ProcessFake
) -> None:
    """A `git` read that runs out of time gives no head commit (#1538)."""
    process_fake.answer(
        "git",
        ProcessAnswer(side_effect=subprocess.TimeoutExpired(cmd=["git", "rev-parse"], timeout=5)),
    )

    report = _detector(_workspace(tmp_path), indexer).detect_drift(
        current_cache={}, last_indexed_commit="abc123"
    )

    assert report.current_head_commit is None
