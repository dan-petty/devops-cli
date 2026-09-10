"""Unit tests for GitHub Pages subsystem."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.github.pages import (
    GitHubPagesBuildInfo,
    GitHubPagesInfo,
    get_pages_builds,
    get_pages_status,
    request_pages_build,
    verify_pages_configuration,
)


def test_github_pages_info_model() -> None:
    """GitHubPagesInfo validates properly and handles optional fields."""
    info = GitHubPagesInfo(
        status="built",
        html_url="https://dan-petty.github.io/devops-cli/",
        build_type="legacy",
        branch="main",
        path="/",
        https_enforced=True,
    )
    assert info.status == "built"
    assert info.html_url == "https://dan-petty.github.io/devops-cli/"
    assert info.branch == "main"
    assert info.https_enforced is True


def test_github_pages_build_info_model() -> None:
    """GitHubPagesBuildInfo model parses correctly."""
    build = GitHubPagesBuildInfo(
        status="built",
        commit="b861fc4b957de816aec9b5a650f049efe0251381",
        duration_ms=45802,
        error_message=None,
        created_at="2026-09-09T14:25:58Z",
        updated_at="2026-09-09T14:26:43Z",
    )
    assert build.status == "built"
    assert build.commit.startswith("b861fc4")
    assert build.duration_ms == 45802
    assert build.error_message is None


def test_get_pages_status_success() -> None:
    """get_pages_status parses API output successfully."""
    payload = {
        "status": "built",
        "html_url": "https://dan-petty.github.io/devops-cli/",
        "build_type": "legacy",
        "source": {"branch": "main", "path": "/"},
        "https_enforced": True,
        "cname": None,
        "custom_404": False,
    }
    with patch("devops_cli.github.pages.run_subprocess") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=0, stdout=json.dumps(payload))
        res = get_pages_status("dan-petty/devops-cli")
        assert res is not None
        assert res.status == "built"
        assert res.branch == "main"
        assert res.https_enforced is True


def test_get_pages_status_failure() -> None:
    """get_pages_status returns None when repository does not have Pages enabled."""
    with patch("devops_cli.github.pages.run_subprocess") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=1, stdout="Not Found")
        res = get_pages_status("dan-petty/no-pages")
        assert res is None


def test_get_pages_builds_success() -> None:
    """get_pages_builds parses build history records."""
    builds_payload = [
        {
            "status": "built",
            "commit": "b861fc4b957de816aec9b5a650f049efe0251381",
            "duration": 45802,
            "error": {"message": None},
            "created_at": "2026-09-09T14:25:58Z",
            "updated_at": "2026-09-09T14:26:43Z",
        }
    ]
    with patch("devops_cli.github.pages.run_subprocess") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=0, stdout=json.dumps(builds_payload))
        builds = get_pages_builds("dan-petty/devops-cli")
        assert len(builds) == 1
        assert builds[0].status == "built"
        assert builds[0].duration_ms == 45802


def test_request_pages_build() -> None:
    """request_pages_build calls GitHub API to request a build."""
    with patch("devops_cli.github.pages.run_subprocess") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=0, stdout="{}")
        ok = request_pages_build("dan-petty/devops-cli")
        assert ok is True


def test_verify_pages_configuration_valid(tmp_path: Path) -> None:
    """verify_pages_configuration passes with docs/github-pages.config.yaml."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    config_file = docs_dir / "github-pages.config.yaml"
    config_file.write_text(
        "title: My Project\ndescription: Test\nurl: https://example.github.io\nbaseurl: /test\nmarkdown: kramdown\nplugins:\n  - jekyll-seo-tag\n",
        encoding="utf-8",
    )
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")

    valid, diagnostics = verify_pages_configuration(tmp_path)
    assert valid is True
    assert any("Jekyll configuration valid" in d for d in diagnostics)


def test_verify_pages_configuration_missing_config(tmp_path: Path) -> None:
    """verify_pages_configuration fails when github-pages.config.yaml is missing."""
    valid, diagnostics = verify_pages_configuration(tmp_path)
    assert valid is False
    assert any("Missing github-pages.config.yaml in docs/" in d for d in diagnostics)


def test_verify_pages_configuration_missing_keys(tmp_path: Path) -> None:
    """verify_pages_configuration fails when required keys are missing."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    config_file = docs_dir / "github-pages.config.yaml"
    config_file.write_text("title: Only Title\n", encoding="utf-8")
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")

    valid, diagnostics = verify_pages_configuration(tmp_path)
    assert valid is False
    assert any("Missing required Jekyll config keys" in d for d in diagnostics)
