"""Unit tests for Autonomous RAG Index Drift Detection & Auto-Reindexing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.ai.rag.drift import RAGDriftDetector, RAGDriftReport
from devops_cli.main import app

runner = CliRunner()


def test_drift_detector_clean_state(tmp_path: Path) -> None:
    """Verify that an identical working tree and cache yields drift_score == 0.0."""
    code_file = tmp_path / "main.py"
    code_file.write_text("def hello(): pass\n", encoding="utf-8")

    detector = RAGDriftDetector(root_dir=tmp_path)
    # Pre-populate cache with matching hash
    from devops_cli.ai.rag.chunker import SemanticChunker

    chash = SemanticChunker._hash_content("def hello(): pass\n")
    proj = tmp_path.name
    cache_key = f"{proj}:main.py"

    report = detector.detect_drift(
        current_cache={cache_key: chash},
        last_indexed_commit="commit_123",
        current_commit="commit_123",
    )

    assert isinstance(report, RAGDriftReport)
    assert report.drift_score == 0.0
    assert len(report.stale_files) == 0
    assert len(report.new_files) == 0
    assert len(report.deleted_files) == 0
    assert not report.git_commit_drift


def test_drift_detector_detects_new_files(tmp_path: Path) -> None:
    """Verify that unindexed files are identified in new_files."""
    code_file = tmp_path / "new_module.py"
    code_file.write_text("x = 1\n", encoding="utf-8")

    detector = RAGDriftDetector(root_dir=tmp_path)
    report = detector.detect_drift(current_cache={})

    assert "new_module.py" in report.new_files
    assert report.drift_score > 0.0


def test_drift_detector_detects_stale_modified_files(tmp_path: Path) -> None:
    """Verify that modified files with outdated hash are flagged as stale."""
    code_file = tmp_path / "service.py"
    code_file.write_text("class Service: pass\n", encoding="utf-8")

    proj = tmp_path.name
    cache_key = f"{proj}:service.py"

    detector = RAGDriftDetector(root_dir=tmp_path)
    report = detector.detect_drift(current_cache={cache_key: "old_outdated_hash_123"})

    assert "service.py" in report.stale_files
    assert report.drift_score > 0.0


def test_drift_detector_detects_deleted_files(tmp_path: Path) -> None:
    """Verify that files present in cache but absent on disk are flagged as deleted."""
    proj = tmp_path.name
    cache_key = f"{proj}:missing_file.py"

    detector = RAGDriftDetector(root_dir=tmp_path)
    report = detector.detect_drift(current_cache={cache_key: "some_hash"})

    assert "missing_file.py" in report.deleted_files
    assert report.drift_score > 0.0


def test_drift_detector_git_commit_drift(tmp_path: Path) -> None:
    """Verify that a mismatch between current and indexed commit triggers git_commit_drift."""
    detector = RAGDriftDetector(root_dir=tmp_path)
    report = detector.detect_drift(
        current_cache={},
        last_indexed_commit="abc1234",
        current_commit="def5678",
    )

    assert report.git_commit_drift
    assert report.last_indexed_commit == "abc1234"
    assert report.current_head_commit == "def5678"


def test_drift_detector_auto_sync_triggers_indexer(tmp_path: Path) -> None:
    """Verify that auto_sync invokes WorkspaceIndexer and records reindexed files."""
    code_file = tmp_path / "app.py"
    code_file.write_text("print('hello')\n", encoding="utf-8")

    mock_indexer = MagicMock()
    mock_indexer.index_workspace.return_value = {
        "indexed_files": 1,
        "total_chunks": 1,
    }

    detector = RAGDriftDetector(root_dir=tmp_path, indexer=mock_indexer)
    report = detector.detect_and_sync(auto_sync=True)

    assert report.reindexed_files == 1
    mock_indexer.index_workspace.assert_called_once()


def test_cli_rag_drift_clean(tmp_path: Path) -> None:
    """Verify devops ai rag drift succeeds on clean directory."""
    with patch("devops_cli.ai.rag.drift.RAGDriftDetector.detect_and_sync") as mock_detect:
        mock_detect.return_value = RAGDriftReport(
            root_dir=str(tmp_path),
            project="test-proj",
            total_files=5,
            synced_files=5,
            stale_files=[],
            new_files=[],
            deleted_files=[],
            git_commit_drift=False,
            drift_score=0.0,
        )

        res = runner.invoke(app, ["ai", "rag", "drift", str(tmp_path)])
        assert res.exit_code == 0
        assert "RAG Index Drift" in res.stdout
        assert "Clean" in res.stdout or "0%" in res.stdout


def test_cli_rag_drift_fail_on_drift(tmp_path: Path) -> None:
    """Verify devops ai rag drift fails with code 1 when --fail-on-drift is passed and drift exists."""
    with patch("devops_cli.ai.rag.drift.RAGDriftDetector.detect_and_sync") as mock_detect:
        mock_detect.return_value = RAGDriftReport(
            root_dir=str(tmp_path),
            project="test-proj",
            total_files=5,
            synced_files=3,
            stale_files=["service.py"],
            new_files=["new_file.py"],
            deleted_files=[],
            git_commit_drift=True,
            drift_score=0.4,
        )

        res = runner.invoke(app, ["ai", "rag", "drift", str(tmp_path), "--fail-on-drift", "--json"])
        assert res.exit_code == 1
        data = json.loads(res.stdout)
        assert data["drift_score"] == 0.4
        assert "service.py" in data["stale_files"]
        assert "new_file.py" in data["new_files"]


def test_cli_rag_drift_auto_sync(tmp_path: Path) -> None:
    """Verify devops ai rag drift --auto-sync invokes synchronization."""
    with patch("devops_cli.ai.rag.drift.RAGDriftDetector.detect_and_sync") as mock_detect:
        mock_detect.return_value = RAGDriftReport(
            root_dir=str(tmp_path),
            project="test-proj",
            total_files=2,
            synced_files=2,
            stale_files=[],
            new_files=[],
            deleted_files=[],
            git_commit_drift=False,
            drift_score=0.0,
            reindexed_files=2,
        )

        res = runner.invoke(app, ["ai", "rag", "drift", str(tmp_path), "--auto-sync"])
        assert res.exit_code == 0
        mock_detect.assert_called_with(auto_sync=True)


def test_drift_detector_defensive_boundaries(tmp_path: Path) -> None:
    """Verify that symlinks, traversal paths, and oversized files are skipped during drift scanning."""
    from devops_cli.ai.rag.drift import _scan_file_drift

    # 1. Normal file
    valid_file = tmp_path / "valid.py"
    valid_file.write_text("x = 42\n", encoding="utf-8")
    stale: list[str] = []
    new: list[str] = []
    _scan_file_drift(valid_file, tmp_path, "proj", {}, stale, new)
    assert new == ["valid.py"]

    # 2. Symlink file
    target_file = tmp_path / "target.py"
    target_file.write_text("y = 100\n", encoding="utf-8")
    symlink_file = tmp_path / "symlink.py"
    symlink_file.symlink_to(target_file)
    stale_sym, new_sym = [], []
    _scan_file_drift(symlink_file, tmp_path, "proj", {}, stale_sym, new_sym)
    assert (stale_sym, new_sym) == ([], [])

    # 3. Path outside root_dir (traversal)
    outside_dir = tmp_path.parent / "outside_dir"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "external.py"
    outside_file.write_text("z = 1\n", encoding="utf-8")
    stale_out, new_out = [], []
    _scan_file_drift(outside_file, tmp_path, "proj", {}, stale_out, new_out)
    assert (stale_out, new_out) == ([], [])

    # 4. Oversized file (> 5MB)
    mock_large = MagicMock(spec=Path)
    mock_large.resolve.return_value = mock_large
    mock_large.is_symlink.return_value = False
    mock_large.is_file.return_value = True
    mock_large.is_relative_to.return_value = True
    mock_large.stat.return_value.st_size = 6 * 1024 * 1024
    stale_large, new_large = [], []
    _scan_file_drift(mock_large, tmp_path, "proj", {}, stale_large, new_large)
    assert (stale_large, new_large) == ([], [])
