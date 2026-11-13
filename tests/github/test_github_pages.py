"""Unit tests for GitHub Pages subsystem."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from devops_cli.github.pages import (
    GitHubPagesInfo,
    get_pages_status,
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
    """GitHubPagesInfo gives no source branch and no path for a workflow build that names none
    (#5212)."""
    info = GitHubPagesInfo(
        status="built",
        html_url="https://dan-petty.github.io/devops-cli/",
        build_type="workflow",
        https_enforced=True,
    )
    assert info.status == "built"
    assert info.html_url == "https://dan-petty.github.io/devops-cli/"
    assert (info.build_type, info.branch, info.path) == ("workflow", None, None)
    assert info.https_enforced is True


def test_get_pages_status_parses_status_payload(process_fake: ProcessFake) -> None:
    """get_pages_status parses API output successfully."""
    payload = {
        "status": "built",
        "html_url": "https://dan-petty.github.io/devops-cli/",
        "build_type": "workflow",
        "source": {"branch": "main", "path": "/docs"},
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
    assert (res.build_type, res.branch, res.path) == ("workflow", "main", "/docs")
    assert res.https_enforced is True


def test_get_pages_status_gives_no_value_for_an_omitted_field(process_fake: ProcessFake) -> None:
    """get_pages_status invents no legacy build type, source branch or path when the API omits
    them (#5212)."""
    payload = {"status": "built", "html_url": "https://dan-petty.github.io/devops-cli/"}
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/pages"],
        ProcessAnswer(returncode=0, stdout=json.dumps(payload)),
    )
    res = get_pages_status("dan-petty/devops-cli")
    assert res is not None
    assert (res.build_type, res.branch, res.path) == (None, None, None)


def test_get_pages_status_returns_none_when_disabled(process_fake: ProcessFake) -> None:
    """get_pages_status returns None when repository does not have Pages enabled."""
    process_fake.answer(
        ["gh", "api", "repos/dan-petty/no-pages/pages"],
        ProcessAnswer(returncode=1, stdout="Not Found"),
    )
    res = get_pages_status("dan-petty/no-pages")
    assert res is None


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
    """Verify that the first nav tab of the site is README.md (#5152)."""
    nav = yaml.safe_load((REPO_ROOT / ".nav.yml").read_text(encoding="utf-8"))["nav"]

    assert nav[0] == {"Home": "README.md"}


def test_the_cli_reference_tab_opens_on_the_index() -> None:
    """Verify that the CLI reference tab of the site opens on the index of the command groups,
    and then lists the page of each group (#5163)."""
    nav = yaml.safe_load((REPO_ROOT / ".nav.yml").read_text(encoding="utf-8"))["nav"]

    tabs = [entry["CLI reference"] for entry in nav if "CLI reference" in entry]

    assert tabs == [[{"Index": "docs/CLI_REFERENCE.md"}, "docs/commands/*.md"]]


def test_the_repository_documentation_has_an_index_home_page() -> None:
    """Verify that docs/index.md exists and is a non-empty page that routes to the main docs
    (#2070). The site shows it as the Overview page of the Guides tab (#5152)."""
    index_file = REPO_ROOT / "docs" / "index.md"
    assert index_file.is_file(), "docs/index.md must exist as the overview page of the guides"
    content = index_file.read_text(encoding="utf-8").strip()
    assert len(content) > 0, "docs/index.md must not be empty"
