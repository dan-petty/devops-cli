"""Unit tests for running devops review commands in subdirectories and repos/ paths."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from devops_cli.commands.review import _detect_base_branch, _is_allowed_review_boundary, app
from devops_cli.config.settings import Settings

if TYPE_CHECKING:
    pass


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestReviewReposSubdirectories:
    """Tests for review path and branch functionality in subdirectories and repos/."""

    def test_is_allowed_review_boundary_workspace_and_repos(self, tmp_path: Path) -> None:
        """_is_allowed_review_boundary must allow paths under CWD, repos base, or git root."""
        settings = Settings()
        settings.repos.base_dir = tmp_path / "repos"

        sub_dir = tmp_path / "repos" / "my-org" / "sub-repo"
        sub_dir.mkdir(parents=True)

        assert _is_allowed_review_boundary(sub_dir, settings) is True

    def test_detect_base_branch_falls_back_to_master(self, tmp_path: Path) -> None:
        """_detect_base_branch must detect master if main does not exist in repo."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=test",
                "-c",
                "user.email=test@test.com",
                "commit",
                "--allow-empty",
                "-m",
                "init",
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-M", "master"], cwd=tmp_path, check=True, capture_output=True
        )

        detected = _detect_base_branch(tmp_path, preferred_base="main")
        assert detected == "master"

    def test_review_path_summary_in_repos_directory(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """devops review path must collect files under repos/ even if git-ignored at parent."""
        target_dir = tmp_path / "repos" / "sample-app"
        target_dir.mkdir(parents=True)
        (target_dir / "main.py").write_text("print('hello')", encoding="utf-8")

        monkeypatch.setenv("DEVOPS_CLI_REPOS_BASE_DIR", str(tmp_path / "repos"))

        result = runner.invoke(app, ["path", str(target_dir), "--summary"])
        assert result.exit_code == 0
        assert "Segment 1" in result.output or "main.py" in result.output
