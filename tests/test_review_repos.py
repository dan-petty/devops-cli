"""Unit tests for running devops ai review commands in subdirectories and repos/ paths."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.ai.review.runner import _detect_base_branch, _is_allowed_review_boundary
from devops_cli.config.settings import Settings

pytestmark = pytest.mark.usefixtures("mock_keyring")


class TestReviewReposSubdirectories:
    """Tests for review path and branch functionality in subdirectories and repos/."""

    def test_is_allowed_review_boundary_workspace_and_repos(self, tmp_path: Path) -> None:
        """_is_allowed_review_boundary must allow paths under the working directory that the command
        gives, the repos base, or a git root."""
        settings = Settings()
        settings.repos.base_dir = tmp_path / "repos"

        sub_dir = tmp_path / "repos" / "my-org" / "sub-repo"
        sub_dir.mkdir(parents=True)

        assert _is_allowed_review_boundary(sub_dir, settings, tmp_path / "elsewhere") is True

    def test_detect_base_branch_falls_back_to_master(self, tmp_path: Path) -> None:
        """_detect_base_branch must detect master if main does not exist in repo."""
        with patch("devops_cli.ai.review.runner._run_subprocess") as mock_proc:
            mock_proc.side_effect = [
                subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr=""),
                subprocess.CompletedProcess(
                    args=["git"], returncode=0, stdout="master\n", stderr=""
                ),
            ]
            detected = _detect_base_branch(tmp_path, preferred_base="main")
            assert detected == "master"

    def test_review_path_summary_in_repos_directory(
        self,
        cli: Callable[..., Any],
        tmp_path: Path,
        tmp_path_factory: pytest.TempPathFactory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`devops review path --summary` of a clone under repos/ lists the cached analysis of the
        clone, even when the command runs in another directory: the review takes its workspace
        from the command, which reads the working directory one time (#2098)."""
        from devops_cli.ai.analyze.cache import save_analysis_metadata
        from devops_cli.models.ai import FileAnalysisMeta

        target_dir = tmp_path / "repos" / "sample-app"
        target_dir.mkdir(parents=True)
        (target_dir / "main.py").write_text("print('hello')", encoding="utf-8")
        greeting = FileAnalysisMeta(path="main.py", language="python", primary_purpose="Greets")
        save_analysis_metadata("path", str(target_dir), "sample-app", [greeting], target_dir)
        monkeypatch.setenv("DEVOPS_CLI_REPOS_BASE_DIR", str(tmp_path / "repos"))
        monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))

        result = cli("review", "path", str(target_dir), "--summary", "--dry-run")

        assert (result.exit_code, "main.py" in result.output, "Greets" in result.output) == (
            0,
            True,
            True,
        )
