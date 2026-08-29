"""Unit tests for Difftastic structural AST diff provider."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.diff.difftastic import get_structural_diff
from devops_cli.exceptions import SecurityError


def test_get_structural_diff_unified_fallback(tmp_path: Path) -> None:
    file_a = tmp_path / "a.py"
    file_b = tmp_path / "b.py"
    file_a.write_text("def foo():\n    return 1\n")
    file_b.write_text("def foo():\n    return 2\n")

    diff = get_structural_diff(file_a, file_b, repo_root=tmp_path)
    assert "-    return 1" in diff
    assert "+    return 2" in diff


@patch("shutil.which", return_value="/usr/local/bin/difft")
@patch("devops_cli.ai.diff.difftastic.run_subprocess")
def test_get_structural_diff_with_difft(
    mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path
) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="structural diff output\n", stderr="")
    file_a = tmp_path / "a.py"
    file_b = tmp_path / "b.py"
    diff = get_structural_diff(file_a, file_b, repo_root=tmp_path)
    assert diff == "structural diff output\n"
    assert mock_run.called


@patch("devops_cli.ai.diff.difftastic.run_subprocess")
def test_get_structural_diff_git_branch(mock_run: MagicMock, tmp_path: Path) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="git diff branch output\n", stderr="")
    diff = get_structural_diff("feat/x", branch="feat/x", base="main", repo_root=tmp_path)
    assert diff == "git diff branch output\n"


def test_get_structural_diff_path_containment_violation(tmp_path: Path) -> None:
    safe_file = tmp_path / "safe.py"
    safe_file.write_text("print('hello')\n")
    outside_file = tmp_path.parent / "outside.py"

    with pytest.raises(SecurityError, match="Path traversal detected"):
        get_structural_diff(outside_file, safe_file, repo_root=tmp_path)

    with pytest.raises(SecurityError, match="Path traversal detected"):
        get_structural_diff(safe_file, outside_file, repo_root=tmp_path)


def test_get_structural_diff_empty(tmp_path: Path) -> None:
    diff = get_structural_diff(tmp_path / "a.py", repo_root=tmp_path)
    assert diff == ""
