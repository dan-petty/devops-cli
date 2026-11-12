"""The docs site build: the stage, the link change, the build data and the checks of the built site (#5152)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from devops_cli.docs.site import (
    BuildData,
    SiteDefects,
    check_built_site,
    read_build_data,
    stage_site,
)
from devops_cli.exceptions.tools import SubprocessError
from devops_cli.exceptions.validation import DocsSiteError
from tests.support.docs_site import SITE_SHA, built_page, write_files, write_site_repository
from tests.support.fakes.process import ProcessAnswer

if TYPE_CHECKING:
    from tests.support.fakes.process import ProcessFake

SHA = SITE_SHA
BLOB = f"https://github.com/example/site/blob/{SHA}"
TREE = f"https://github.com/example/site/tree/{SHA}"
RAW = f"https://github.com/example/site/raw/{SHA}"

BUILD = BuildData(
    version="1.2.3",
    commit=SHA,
    short_commit="0123456",
    commit_url=f"https://github.com/example/site/commit/{SHA}",
    commit_date="2026-11-12",
    built_at="2026-11-12T18:00:00Z",
)


def test_a_link_to_a_repository_file_outside_the_site_becomes_a_github_url_at_the_build_commit(
    tmp_path: Path,
) -> None:
    """A relative link that works on github.com works on the site: a link to a page of the site
    stays relative, a link to another file of the repository goes to that file on GitHub at the
    commit of the build, and code keeps its text."""
    readme = (
        "# Site\n"
        "\n"
        "See [x](src/x.py#L1), [tests](docs/TESTING.md#run-time), [the manifests](k8s/) and "
        "[the agent records](docs/agent/README.md).\n"
        "\n"
        "| Page | Link |\n"
        "| :--- | :--- |\n"
        "| Code | [x](./src/x.py) |\n"
        "\n"
        "Write `[x](src/x.py)` for a link. ![logo](src/x.py) [gone](src/missing.py) "
        "[web](https://example.com/src/x.py) [top](#site)\n"
        "\n"
        "```markdown\n"
        "[x](src/x.py)\n"
        "```\n"
    )
    repo = write_site_repository(tmp_path / "repo", readme, guide="Back to [x](../../src/x.py).\n")

    staged = stage_site(repo, tmp_path / "stage", BUILD)

    assert (
        (staged.pages_dir / "README.md").read_text(encoding="utf-8"),
        (staged.pages_dir / "docs/guide/page.md").read_text(encoding="utf-8"),
        staged.rewritten_links,
    ) == (
        "# Site\n"
        "\n"
        f"See [x]({BLOB}/src/x.py#L1), [tests](docs/TESTING.md#run-time), "
        f"[the manifests]({TREE}/k8s) and [the agent records]({BLOB}/docs/agent/README.md).\n"
        "\n"
        "| Page | Link |\n"
        "| :--- | :--- |\n"
        f"| Code | [x]({BLOB}/src/x.py) |\n"
        "\n"
        f"Write `[x](src/x.py)` for a link. ![logo]({RAW}/src/x.py) "
        "[gone](src/missing.py) [web](https://example.com/src/x.py) [top](#site)\n"
        "\n"
        "```markdown\n"
        "[x](src/x.py)\n"
        "```\n",
        f"Back to [x]({BLOB}/src/x.py).\n",
        6,
    )


def test_the_stage_holds_the_site_pages_at_their_repository_paths(tmp_path: Path) -> None:
    """The stage holds `docs/` without the agent records, the root documents that the site
    publishes and the navigation file, each at its path in the repository."""
    repo = write_site_repository(tmp_path / "repo")

    staged = stage_site(repo, tmp_path / "stage", BUILD)

    assert (
        sorted(
            path.relative_to(staged.pages_dir).as_posix()
            for path in staged.pages_dir.rglob("*")
            if path.is_file()
        ),
        staged.pages,
    ) == (
        [
            ".nav.yml",
            "AGENTS.md",
            "ARCHITECTURE.md",
            "CHANGELOG.md",
            "CONTEXT.md",
            "CONTRIBUTING.md",
            "README.md",
            "RELEASE_CYCLE.md",
            "SECURITY.md",
            "docs/TESTING.md",
            "docs/assets/css/tokens-light.css",
            "docs/guide/page.md",
        ],
        10,
    )


def test_the_stage_needs_each_root_document_that_the_site_publishes(tmp_path: Path) -> None:
    """The nav lists each root document, so a missing one fails the stage and is named."""
    repo = write_site_repository(tmp_path / "repo")
    (repo / "CONTEXT.md").unlink()

    with pytest.raises(DocsSiteError) as raised:
        stage_site(repo, tmp_path / "stage", BUILD)

    assert (raised.value.error_code, raised.value.details) == (
        "DOCS_SITE_INVALID",
        {"missing": ["CONTEXT.md"]},
    )


def test_a_new_stage_holds_no_page_of_an_earlier_stage(tmp_path: Path) -> None:
    """A page that the repository no longer holds leaves the site at the next build."""
    repo = write_site_repository(tmp_path / "repo")
    stage_site(repo, tmp_path / "stage", BUILD)
    (repo / "docs/guide/page.md").unlink()

    staged = stage_site(repo, tmp_path / "stage", BUILD)

    assert (staged.pages_dir / "docs/guide/page.md").exists() is False


def test_the_staged_config_adds_the_stage_paths_and_the_build_data(tmp_path: Path) -> None:
    """The staged config keeps each setting of `zensical.toml`, and adds the stage folders, the
    theme overrides of the repository and the build data that the footer shows."""
    repo = write_site_repository(tmp_path / "repo")

    staged = stage_site(repo, tmp_path / "stage", BUILD)

    assert yaml.safe_load(staged.config_file.read_text(encoding="utf-8")) == {
        "site_name": "site",
        "site_url": "https://example.com/site/",
        "repo_url": "https://github.com/example/site",
        "edit_uri": "edit/main/",
        "docs_dir": "pages",
        "site_dir": "site",
        "theme": {"features": ["navigation.tabs"], "custom_dir": str(repo / "overrides")},
        "plugins": {"awesome-nav": {}},
        "extra": {
            "build": {
                "version": "1.2.3",
                "commit": SHA,
                "short_commit": "0123456",
                "commit_url": f"https://github.com/example/site/commit/{SHA}",
                "commit_date": "2026-11-12",
                "built_at": "2026-11-12T18:00:00Z",
            }
        },
    }


def test_the_build_data_holds_the_version_and_the_commit_of_the_checkout(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """The version comes from `pyproject.toml`, the commit and its date from git, and the link
    of the commit from the repository URL of the site."""
    repo = write_site_repository(tmp_path / "repo")
    process_fake.answer(["git", "show"], ProcessAnswer(stdout=f"{SHA}\n0123456\n2026-11-12\n"))

    build = read_build_data(repo, built_at=datetime(2026, 11, 12, 18, 0, 5, tzinfo=UTC))

    assert (build, [call.argv for call in process_fake.calls]) == (
        BuildData(
            version="1.2.3",
            commit=SHA,
            short_commit="0123456",
            commit_url=f"https://github.com/example/site/commit/{SHA}",
            commit_date="2026-11-12",
            built_at="2026-11-12T18:00:05Z",
        ),
        [("git", "show", "--no-patch", "--format=%H%n%h%n%cs", "HEAD")],
    )


def test_the_build_data_needs_a_commit(tmp_path: Path, process_fake: ProcessFake) -> None:
    """A checkout with no commit has no build data, and the error names git."""
    repo = write_site_repository(tmp_path / "repo")
    process_fake.answer(
        ["git", "show"], ProcessAnswer(returncode=128, stderr="fatal: bad revision 'HEAD'\n")
    )

    with pytest.raises(SubprocessError) as raised:
        read_build_data(repo, built_at=datetime(2026, 11, 12, 18, 0, tzinfo=UTC))

    assert (raised.value.error_code, raised.value.exit_code) == ("SUBPROCESS_FAILED", 128)


def test_a_page_with_no_nav_link_is_a_defect_of_the_built_site(tmp_path: Path) -> None:
    """Every page of the site has a link in the navigation of the home page, so a reader can
    reach it. A page that no tab lists is a defect."""
    site = tmp_path / "site"
    nav = ["./", "./docs/TESTING/", "./docs/adr/0001-first/"]
    write_files(
        site,
        {
            "index.html": built_page(nav),
            "docs/TESTING/index.html": built_page(nav),
            "docs/adr/0001-first/index.html": built_page(nav),
            "docs/commands/ai/index.html": built_page(nav),
            "404.html": "<html></html>",
        },
    )

    assert check_built_site(site, BUILD) == SiteDefects(
        outside_nav=["docs/commands/ai/"], without_build_commit=[]
    )


def test_a_page_without_the_build_commit_is_a_defect_of_the_built_site(tmp_path: Path) -> None:
    """Each page holds the commit of its build in the `devops-build-commit` meta tag, so the
    Pages job can compare the live site with `main`."""
    site = tmp_path / "site"
    nav = ["./", "./docs/TESTING/"]
    write_files(
        site,
        {
            "index.html": built_page(nav),
            "docs/TESTING/index.html": built_page(nav, commit="fedcba9"),
        },
    )

    assert check_built_site(site, BUILD) == SiteDefects(
        outside_nav=[], without_build_commit=["docs/TESTING/"]
    )


def test_a_link_out_of_the_repository_stays_as_it_is(tmp_path: Path) -> None:
    """A link above the repository root is no repository file, so the stage keeps it and the
    strict build reports it. A destination in angle brackets is a link like any other."""
    repo = write_site_repository(tmp_path / "repo", "[out](../outside.md) [angle](<src/x.py>)\n")

    staged = stage_site(repo, tmp_path / "stage", BUILD)

    assert (
        (staged.pages_dir / "README.md").read_text(encoding="utf-8"),
        staged.rewritten_links,
    ) == (f"[out](../outside.md) [angle]({BLOB}/src/x.py)\n", 1)


def test_the_build_data_needs_the_repository_url_of_the_site(tmp_path: Path) -> None:
    """The link of the commit and the GitHub links need `repo_url` in `zensical.toml`."""
    repo = write_site_repository(tmp_path / "repo")
    (repo / "zensical.toml").write_text('[project]\nsite_name = "site"\n', encoding="utf-8")

    with pytest.raises(DocsSiteError) as raised:
        read_build_data(repo, built_at=datetime(2026, 11, 12, 18, 0, tzinfo=UTC))

    assert (raised.value.error_code, raised.value.details) == (
        "DOCS_SITE_INVALID",
        {"field": "repo_url"},
    )


def test_the_build_data_needs_the_site_settings_file(tmp_path: Path) -> None:
    """A repository with no `zensical.toml` has no site to build, and the error names the file."""
    repo = write_site_repository(tmp_path / "repo")
    (repo / "zensical.toml").unlink()

    with pytest.raises(DocsSiteError) as raised:
        read_build_data(repo, built_at=datetime(2026, 11, 12, 18, 0, tzinfo=UTC))

    assert (raised.value.error_code, raised.value.details) == (
        "DOCS_SITE_INVALID",
        {"path": str(repo / "zensical.toml")},
    )
