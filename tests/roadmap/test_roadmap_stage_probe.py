"""The premise probe of the stage job: bounded read-only git commands at the staging commit (#3011)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS
from devops_cli.roadmap import stage_probe
from devops_cli.roadmap.refine import git_result
from devops_cli.roadmap.stage_probe import probe_premise

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.roadmap_stage import StageRepo

LIVE = "src/devops_cli/live.py"
GONE = "src/devops_cli/gone.py"
LIVE_SOURCE = "def keep_comment(comments):\n    return comments[:-1]\n\nLIMIT = 3\n"
GONE_SOURCE = "def validate_url(url):\n    return url\n"


@pytest.fixture
def repo(stage_repo: StageRepo) -> StageRepo:
    """A repository where `gone.py` (with `validate_url`) was added and then deleted."""
    stage_repo.track({LIVE: LIVE_SOURCE, GONE: GONE_SOURCE})
    stage_repo.git("rm", "-q", GONE)
    stage_repo.git("commit", "-q", "-m", "remove the url check")
    stage_repo.git("push", "-q", "origin", "main")
    return stage_repo


def _probe(repo: StageRepo, body: str) -> stage_probe.Probe:
    return probe_premise(repo.clone, repo.git("rev-parse", "HEAD"), body)


def test_a_present_path_and_a_defined_identifier_are_confirmed(repo: StageRepo) -> None:
    probe = _probe(repo, f"Change `{LIVE}` and `keep_comment`.")

    assert f"The path `{LIVE}` is a file of the staging commit." in probe.text
    assert f"`keep_comment` is defined at {LIVE}:1" in probe.text
    assert probe.missing == ()
    assert probe.skipped == ()


def test_a_constant_counts_as_a_definition(repo: StageRepo) -> None:
    probe = _probe(repo, "Raise `LIMIT` to 5.")

    assert f"`LIMIT` is defined at {LIVE}:4" in probe.text


def test_a_deleted_path_names_the_commit_that_deleted_it(repo: StageRepo) -> None:
    probe = _probe(repo, f"Fix `{GONE}`.")

    assert f"The path `{GONE}` is no file of the staging commit." in probe.text
    assert "remove the url check" in probe.text
    assert probe.missing == (GONE,)


def test_a_path_that_no_commit_held_says_so(repo: StageRepo) -> None:
    probe = _probe(repo, "Add `src/devops_cli/never.py`.")

    assert "No commit in the history deleted or renamed it." in probe.text
    assert probe.missing == ("src/devops_cli/never.py",)


def test_the_replay_of_2971_names_the_commit_that_removed_validate_url(repo: StageRepo) -> None:
    probe = _probe(repo, "The check `validate_url` rejects a private address.")

    assert "`validate_url` has no definition at the staging commit." in probe.text
    assert "remove the url check" in probe.text
    assert probe.missing == ("validate_url",)


def test_an_identifier_that_no_commit_held_says_so(repo: StageRepo) -> None:
    probe = _probe(repo, "Call `brand_new_function`.")

    assert "No commit in the history added or removed its text." in probe.text


def test_a_command_a_name_with_a_slash_and_a_version_are_no_cited_items(repo: StageRepo) -> None:
    body = "Run `git log -S x -- a/b`, see `owner/repo` and release 0.41."

    probe = _probe(repo, body)

    assert (probe.text, probe.missing, probe.skipped) == ("", (), ())


def test_the_probe_stops_at_the_bound_and_lists_the_items_it_skipped(repo: StageRepo) -> None:
    names = {f"src/devops_cli/f{i}.py": "x = 1\n" for i in range(12)}
    repo.track(names)
    body = " ".join(f"`{name}`" for name in names)

    probe = _probe(repo, body)

    assert CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS == 10
    assert probe.commands == 10
    assert probe.skipped == tuple(list(names)[10:])
    assert "Not probed, the bound of 10 commands is reached:" in probe.text


def test_a_missing_item_that_the_bound_cuts_off_from_its_removal_probe_is_listed(
    repo: StageRepo,
) -> None:
    names = [f"src/devops_cli/m{i}.py" for i in range(6)]
    body = " ".join(f"`{name}`" for name in names)

    probe = _probe(repo, body)

    assert probe.commands == 10
    assert probe.missing == tuple(names[:5])
    assert probe.skipped == (names[5],)


def test_every_command_reads_and_the_checkout_does_not_change(
    repo: StageRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[tuple[str, ...]] = []

    def spy(checkout: Path, *args: str) -> tuple[int, str]:
        ran.append(args)
        return git_result(checkout, *args)

    monkeypatch.setattr(stage_probe, "git_result", spy)
    body = f"`{LIVE}` `{GONE}` `keep_comment` `validate_url`"

    _probe(repo, body)

    assert {args[0] for args in ran} == {"cat-file", "grep", "log"}
    assert repo.git("status", "--porcelain") == ""
