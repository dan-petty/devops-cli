"""`devops roadmap review run` (#4686): its dry run, its refusals, and the data.json that a run
writes, through the command layer with git answered from the recorded scenario `review_window`."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.settings import load_settings
from devops_cli.core.repo import resolve_data_path
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessFake

VERSION = "v1.0.0..v1.1.1"


@pytest.fixture
def checkout(git_fake: GitFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The working directory in the repository of the scenario `review_window`."""
    git_fake.replay("review_window")
    repo = tmp_path / "project"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(repo)
    return repo


def test_a_dry_run_starts_no_program_and_lists_the_git_commands(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    result = cli("roadmap", "review", "run", "--version", VERSION, "--dry-run")

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    assert "log -1 --format=%H%x09%ct --end-of-options 'v1.0.0^{commit}'" in result.stdout
    assert (
        "log --first-parent -M --numstat -z --format=%x1e%H%x1f%ct%x1f%s "
        "'<base commit>..<head commit>'"
    ) in result.stdout


def test_a_dry_run_of_a_week_lists_the_commits_before_each_time(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    result = cli("roadmap", "review", "run", "--week", "2026-W40", "--dry-run")

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    assert "--before=@1790553600" in result.stdout
    assert "--before=@1791158400" in result.stdout


def test_two_windows_are_refused_before_any_read(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    result = cli("roadmap", "review", "run", "--version", VERSION, "--last", "7d")

    assert result.exit_code == 1
    assert "Give one window" in result.output
    assert process_fake.calls == []


def test_a_run_writes_data_json_under_the_data_directory_and_prints_it(
    cli: Callable[..., Any], checkout: Path
) -> None:
    result = cli("roadmap", "review", "run", "--version", VERSION, "--json")

    assert result.exit_code == 0, result.output
    folder = resolve_data_path(load_settings().data.dir) / "project-review/example/project"
    written = json.loads((folder / VERSION / "data.json").read_text(encoding="utf-8"))
    schema = json.loads((folder / VERSION / "data.schema.json").read_text(encoding="utf-8"))
    assert json.loads(result.stdout) == written
    assert (written["repo"], written["window"]["id"], schema["title"]) == (
        "example/project",
        VERSION,
        "ReviewData",
    )
    assert [fact["id"] for fact in written["facts"]] == [
        "git.commits",
        "git.commit_types",
        "git.net_change",
        "git.churn",
        "git.releases",
        "git.release_tags",
        "git.hotspots",
        "lizard.complexity",
    ]


def test_a_run_prints_the_window_and_one_line_for_each_fact(
    cli: Callable[..., Any], checkout: Path, tmp_path: Path
) -> None:
    result = cli("roadmap", "review", "run", "--version", VERSION, "--out", str(tmp_path / "out"))

    assert result.exit_code == 0, result.output
    assert "Window v1.0.0..v1.1.1 (version)" in result.stdout
    assert "from 2026-09-25T10:00:00+00:00 (out) to 2026-10-05T06:30:00+00:00 (in)" in result.stdout
    assert "Previous window: none." in result.stdout
    assert "  git.commits: 4 commits" in result.stdout
    assert (tmp_path / "out" / "data.json").is_file()


def test_a_repository_that_is_not_the_origin_is_refused(
    cli: Callable[..., Any], checkout: Path, tmp_path: Path
) -> None:
    result = cli(
        "roadmap",
        "review",
        "run",
        "--version",
        VERSION,
        "--repo",
        "example/other",
        "--out",
        str(tmp_path / "out"),
    )

    assert result.exit_code == 1
    assert "The origin of the checkout is example/project" in result.output
    assert not (tmp_path / "out").exists()
