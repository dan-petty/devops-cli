"""Unit tests for GitHub Pages subsystem."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from devops_cli.github.pages import (
    GitHubPagesBuildInfo,
    GitHubPagesInfo,
    get_pages_builds,
    get_pages_status,
    request_pages_build,
    verify_pages_configuration,
)
from tests.support.fakes.process import ProcessAnswer
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from tests.support.fakes.process import ProcessFake


@pytest.fixture(autouse=True)
def _answer_rate_limit(process_fake: ProcessFake) -> None:
    payload = json.dumps(
        {
            "resources": {
                name: {
                    "limit": 5000,
                    "used": 10,
                    "remaining": 4990,
                    "reset": int(time.time()) + 600,
                }
                for name in ("core", "graphql", "search")
            }
        }
    )
    process_fake.answer(["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=payload))


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


def test_get_pages_status_parses_status_payload(process_fake: ProcessFake) -> None:
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
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/pages"],
        ProcessAnswer(returncode=0, stdout=json.dumps(payload)),
    )
    res = get_pages_status("dan-petty/devops-cli")
    assert res is not None
    assert res.status == "built"
    assert res.branch == "main"
    assert res.https_enforced is True


def test_get_pages_status_returns_none_when_disabled(process_fake: ProcessFake) -> None:
    """get_pages_status returns None when repository does not have Pages enabled."""
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/no-pages/pages"],
        ProcessAnswer(returncode=1, stdout="Not Found"),
    )
    res = get_pages_status("dan-petty/no-pages")
    assert res is None


def test_get_pages_builds_returns_history_records(process_fake: ProcessFake) -> None:
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
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/pages/builds?per_page=5"],
        ProcessAnswer(returncode=0, stdout=json.dumps(builds_payload)),
    )
    builds = get_pages_builds("dan-petty/devops-cli")
    assert len(builds) == 1
    assert builds[0].status == "built"
    assert builds[0].duration_ms == 45802


def test_request_pages_build_triggers_deployment(process_fake: ProcessFake) -> None:
    """request_pages_build calls GitHub API to request a build."""
    process_fake.answer(
        ["gh", "api", "-X", "POST", "repos/dan-petty/devops-cli/pages/builds"],
        ProcessAnswer(returncode=0, stdout="{}"),
    )
    ok = request_pages_build("dan-petty/devops-cli")
    assert ok is True


SITE_SETTINGS = (
    "[project]\n"
    'site_name = "My Project"\n'
    'site_url = "https://example.github.io/test/"\n'
    'repo_url = "https://github.com/example/test"\n'
)


def test_verify_pages_configuration_valid(tmp_path: Path) -> None:
    """Verify that a zensical.toml with the required site settings passes."""
    (tmp_path / "zensical.toml").write_text(SITE_SETTINGS, encoding="utf-8")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")

    valid, diagnostics = verify_pages_configuration(tmp_path)

    assert (valid, diagnostics[0]) == (
        True,
        "✓ Zensical configuration valid (site_name='My Project', "
        "site_url='https://example.github.io/test/')",
    )


def test_verify_pages_configuration_missing_config(tmp_path: Path) -> None:
    """Verify that the check fails and names zensical.toml when the root has no zensical.toml."""
    valid, diagnostics = verify_pages_configuration(tmp_path)

    assert (valid, diagnostics[0]) == (False, "Missing zensical.toml at the repository root.")


def test_verify_pages_configuration_reads_only_the_file_the_site_build_reads(
    tmp_path: Path,
) -> None:
    """Verify that site settings in a file other than zensical.toml do not pass the check.

    `devops docs site build` reads `zensical.toml` only, so the settings of a `mkdocs.yml` have no
    effect on the site (#5152).
    """
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: My Project\nsite_url: https://example.github.io/test/\n", encoding="utf-8"
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")

    valid, diagnostics = verify_pages_configuration(tmp_path)

    assert (valid, diagnostics[0]) == (False, "Missing zensical.toml at the repository root.")


def test_verify_pages_configuration_missing_keys(tmp_path: Path) -> None:
    """Verify that the check fails when zensical.toml has no site_url or repo_url."""
    (tmp_path / "zensical.toml").write_text('[project]\nsite_name = "Only"\n', encoding="utf-8")

    valid, diagnostics = verify_pages_configuration(tmp_path)

    assert (valid, diagnostics[0]) == (
        False,
        "Missing required Zensical settings in zensical.toml: site_url, repo_url",
    )


def test_verify_pages_configuration_invalid_toml(tmp_path: Path) -> None:
    """Verify that the check fails and names the file when zensical.toml is not valid TOML."""
    (tmp_path / "zensical.toml").write_text("[project\n", encoding="utf-8")

    valid, diagnostics = verify_pages_configuration(tmp_path)

    assert (valid, diagnostics[0].startswith("Invalid TOML syntax in zensical.toml:")) == (
        False,
        True,
    )


def test_the_repository_site_settings_pass_the_check() -> None:
    """Verify that zensical.toml of this repository passes the check, and that docs/ holds no
    settings file of the Jekyll build that the site no longer uses (#5152)."""
    valid, diagnostics = verify_pages_configuration(REPO_ROOT)

    assert (valid, sorted(path.name for path in (REPO_ROOT / "docs").glob("*.y*ml"))) == (
        True,
        [],
    ), diagnostics


def test_the_repository_site_has_readme_as_its_home_page() -> None:
    """Verify that the first nav tab of the site is README.md, which holds the command matrix
    (#5152)."""
    nav = yaml.safe_load((REPO_ROOT / ".nav.yml").read_text(encoding="utf-8"))["nav"]

    assert nav[0] == {"Home": "README.md"}


def test_the_repository_documentation_has_an_index_home_page() -> None:
    """Verify that docs/index.md exists and is a non-empty page that routes to the main docs
    (#2070). The site shows it as the Overview page of the Guides tab (#5152)."""
    index_file = REPO_ROOT / "docs" / "index.md"
    assert index_file.is_file(), "docs/index.md must exist as the overview page of the guides"
    content = index_file.read_text(encoding="utf-8").strip()
    assert len(content) > 0, "docs/index.md must not be empty"
