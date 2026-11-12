"""`devops docs site build`: the command stages the site, runs Zensical and checks the built site (#5152)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devops_cli.core.repo import resolve_store_path
from tests.support.docs_site import SITE_SHA, built_page, write_files, write_site_repository
from tests.support.fakes.process import ProcessAnswer, ProcessCall

if TYPE_CHECKING:
    from tests.support.fakes.process import ProcessFake


def _answer_git(process_fake: ProcessFake) -> None:
    process_fake.answer(["git", "show"], ProcessAnswer(stdout=f"{SITE_SHA}\n0123456\n2026-11-12\n"))


def _zensical_writes(
    pages: dict[str, list[str]], stale: frozenset[str] = frozenset()
) -> Callable[[ProcessCall], Any]:
    """A Zensical build that writes each page of `pages` with its nav links into the site folder
    of the staged config. A page in `stale` holds another commit than the build."""

    def build(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        site = Path(call.argv[3]).parent / "site"
        write_files(
            site,
            {
                f"{path}index.html": built_page(nav, commit="fedcba9")
                if path in stale
                else built_page(nav)
                for path, nav in pages.items()
            },
        )
        return subprocess.CompletedProcess(list(call.argv), 0, "", "")

    return build


def test_site_build_stages_the_site_and_runs_a_strict_zensical_build(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """The command stages the site in `.data/site-src/`, builds it from the staged config and
    reports the pages, the version and the commit of the build."""
    repo = write_site_repository(tmp_path / "repo")
    _answer_git(process_fake)
    nav = ["./", "./docs/TESTING/"]
    process_fake.answer(
        ["zensical", "build"],
        ProcessAnswer(side_effect=_zensical_writes({"": nav, "docs/TESTING/": nav})),
    )

    result = cli("docs", "site", "build", "--strict", "--root", str(repo))

    assert (
        result.exit_code,
        [call.argv for call in process_fake.calls if call.argv[0] == "zensical"],
        "Built 2 pages" in result.output,
        "version 1.2.3, commit 0123456" in result.output,
    ) == (
        0,
        [
            (
                "zensical",
                "build",
                "--config-file",
                str(resolve_store_path("site-src", start_path=repo) / "zensical.yml"),
                "--strict",
            )
        ],
        True,
        True,
    ), result.output


def test_a_strict_site_build_fails_on_a_page_that_no_tab_lists(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """With `--strict`, a built page that has no link in the nav fails the build and is named."""
    repo = write_site_repository(tmp_path / "repo")
    _answer_git(process_fake)
    nav = ["./"]
    process_fake.answer(
        ["zensical", "build"],
        ProcessAnswer(side_effect=_zensical_writes({"": nav, "docs/TESTING/": nav})),
    )

    result = cli("docs", "site", "build", "--strict", "--root", str(repo))

    assert (result.exit_code, "docs/TESTING/" in result.output) == (1, True), result.output


def test_a_site_build_without_strict_warns_on_a_page_that_no_tab_lists(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """Without `--strict`, the build passes and names the page that no tab lists and the page
    without the build commit."""
    repo = write_site_repository(tmp_path / "repo")
    _answer_git(process_fake)
    nav = ["./"]
    process_fake.answer(
        ["zensical", "build"],
        ProcessAnswer(
            side_effect=_zensical_writes(
                {"": nav, "docs/TESTING/": nav}, stale=frozenset({"docs/TESTING/"})
            )
        ),
    )

    result = cli("docs", "site", "build", "--root", str(repo))

    assert (
        result.exit_code,
        "The nav lists no link to the page docs/TESTING/" in result.output,
        "The page docs/TESTING/ does not hold the build commit" in result.output,
    ) == (0, True, True), result.output


def test_a_failed_zensical_build_fails_the_site_build(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """A Zensical build that fails, such as a strict build with a broken link, fails the
    command with its exit code."""
    repo = write_site_repository(tmp_path / "repo")
    _answer_git(process_fake)
    process_fake.answer(["zensical", "build"], ProcessAnswer(returncode=1))

    result = cli("docs", "site", "build", "--strict", "--root", str(repo))

    assert result.exit_code == 1, result.output


def test_site_build_with_serve_serves_the_staged_site(
    cli: Callable[..., Any], process_fake: ProcessFake, tmp_path: Path
) -> None:
    """With `--serve`, Zensical builds and serves the staged site, and the command checks no
    built page."""
    repo = write_site_repository(tmp_path / "repo")
    _answer_git(process_fake)

    result = cli("docs", "site", "build", "--serve", "--root", str(repo))

    assert (
        result.exit_code,
        [call.argv for call in process_fake.calls if call.argv[0] == "zensical"],
    ) == (
        0,
        [
            (
                "zensical",
                "serve",
                "--config-file",
                str(resolve_store_path("site-src", start_path=repo) / "zensical.yml"),
            )
        ],
    ), result.output
