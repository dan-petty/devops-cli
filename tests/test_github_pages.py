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
from tests.support.paths import REPO_ROOT


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
    with patch("devops_cli.github.pages.run_gh") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=0, stdout=json.dumps(payload))
        res = get_pages_status("dan-petty/devops-cli")
        assert res is not None
        assert res.status == "built"
        assert res.branch == "main"
        assert res.https_enforced is True


def test_get_pages_status_failure() -> None:
    """get_pages_status returns None when repository does not have Pages enabled."""
    with patch("devops_cli.github.pages.run_gh") as mock_proc:
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
    with patch("devops_cli.github.pages.run_gh") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=0, stdout=json.dumps(builds_payload))
        builds = get_pages_builds("dan-petty/devops-cli")
        assert len(builds) == 1
        assert builds[0].status == "built"
        assert builds[0].duration_ms == 45802


def test_request_pages_build() -> None:
    """request_pages_build calls GitHub API to request a build."""
    with patch("devops_cli.github.pages.run_gh") as mock_proc:
        mock_proc.return_value = MagicMock(returncode=0, stdout="{}")
        ok = request_pages_build("dan-petty/devops-cli")
        assert ok is True


def test_verify_pages_configuration_valid(tmp_path: Path) -> None:
    """Verify that a docs/_config.yml with the required site settings passes."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    config_file = docs_dir / "_config.yml"
    config_file.write_text(
        "title: My Project\ndescription: Test\nurl: https://example.github.io\nbaseurl: /test\nmarkdown: kramdown\nplugins:\n  - jekyll-seo-tag\n",
        encoding="utf-8",
    )
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")

    valid, diagnostics = verify_pages_configuration(tmp_path)
    assert valid is True
    assert any("Jekyll configuration valid" in d for d in diagnostics)


def test_verify_pages_configuration_missing_config(tmp_path: Path) -> None:
    """Verify that the check fails and names _config.yml when docs/ has no _config.yml."""
    valid, diagnostics = verify_pages_configuration(tmp_path)
    assert valid is False
    assert any("Missing _config.yml in docs/" in d for d in diagnostics)


def test_verify_pages_configuration_reads_only_the_file_jekyll_reads(tmp_path: Path) -> None:
    """Verify that site settings in a file other than docs/_config.yml do not pass the check.

    The Pages builder runs Jekyll with no `--config` option, so Jekyll reads `_config.yml` in the
    source directory only. A second file with valid settings has no effect on the site.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "github-pages.config.yaml").write_text(
        "title: My Project\nurl: https://example.github.io\nbaseurl: /test\nmarkdown: kramdown\n",
        encoding="utf-8",
    )
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")

    valid, diagnostics = verify_pages_configuration(tmp_path)
    assert valid is False
    assert any("Missing _config.yml in docs/" in d for d in diagnostics)


def test_verify_pages_configuration_missing_keys(tmp_path: Path) -> None:
    """Verify that the check fails when docs/_config.yml has no url, baseurl or markdown."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    config_file = docs_dir / "_config.yml"
    config_file.write_text("title: Only Title\n", encoding="utf-8")
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")

    valid, diagnostics = verify_pages_configuration(tmp_path)
    assert valid is False
    assert any("Missing required Jekyll config keys" in d for d in diagnostics)


def test_the_repository_site_settings_are_in_the_one_file_jekyll_reads() -> None:
    """Verify that docs/_config.yml of this repository passes the check and is the only YAML
    file at the top of docs/.

    GitHub Pages builds `main:/docs`, and Jekyll reads `docs/_config.yml` only. A second YAML file
    there is published as a static file, and its settings have no effect (#2001).
    """
    docs_dir = REPO_ROOT / "docs"
    assert sorted(path.name for path in docs_dir.glob("*.y*ml")) == ["_config.yml"]

    valid, diagnostics = verify_pages_configuration(REPO_ROOT)
    assert valid is True, diagnostics
