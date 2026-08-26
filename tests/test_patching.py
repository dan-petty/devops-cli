"""Unit tests for automated review finding patch staging."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from devops_cli.ai.review.patching import stage_finding_patch


def test_stage_finding_patch_invalid_session() -> None:
    """Invalid session IDs must return False."""
    assert stage_finding_patch("../escaping/path") is False


def test_stage_finding_patch_session_not_found(tmp_path: Path) -> None:
    """Nonexistent session directory returns False."""
    with patch("devops_cli.ai.review.patching._get_reviews_base_dir", return_value=tmp_path):
        assert stage_finding_patch("session-123") is False


def test_stage_finding_patch_corrupted_json(tmp_path: Path) -> None:
    """Corrupted findings.json returns False."""
    sess_dir = tmp_path / "session-123"
    sess_dir.mkdir()
    (sess_dir / "findings.json").write_text("invalid json", encoding="utf-8")

    with patch("devops_cli.ai.review.patching._get_reviews_base_dir", return_value=tmp_path):
        assert stage_finding_patch("session-123") is False


def test_stage_finding_patch_out_of_bounds_index(tmp_path: Path) -> None:
    """Index outside finding count returns False."""
    sess_dir = tmp_path / "session-123"
    sess_dir.mkdir()
    findings_data = {"findings": [{"title": "F1", "fix": "pass"}]}
    (sess_dir / "findings.json").write_text(json.dumps(findings_data), encoding="utf-8")

    with patch("devops_cli.ai.review.patching._get_reviews_base_dir", return_value=tmp_path):
        assert stage_finding_patch("session-123", index=0) is False
        assert stage_finding_patch("session-123", index=5) is False


def test_stage_finding_patch_no_fix_available(tmp_path: Path) -> None:
    """Finding without a fix returns False."""
    sess_dir = tmp_path / "session-123"
    sess_dir.mkdir()
    findings_data = {"findings": [{"title": "F1", "fix": None}]}
    (sess_dir / "findings.json").write_text(json.dumps(findings_data), encoding="utf-8")

    with patch("devops_cli.ai.review.patching._get_reviews_base_dir", return_value=tmp_path):
        assert stage_finding_patch("session-123", index=1) is False


def test_stage_finding_patch_success(tmp_path: Path) -> None:
    """Valid finding with fix stages successfully and returns True."""
    sess_dir = tmp_path / "session-123"
    sess_dir.mkdir()
    findings_data = {"findings": [{"title": "F1", "fix": "runAsNonRoot: true"}]}
    (sess_dir / "findings.json").write_text(json.dumps(findings_data), encoding="utf-8")

    with patch("devops_cli.ai.review.patching._get_reviews_base_dir", return_value=tmp_path):
        assert stage_finding_patch("session-123", index=1) is True
