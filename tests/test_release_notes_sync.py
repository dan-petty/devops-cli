"""Test suite for keeping published release descriptions equal to the changelog."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.release import app
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.release_notes import (
    ReleaseBody,
    get_release_body,
    list_published_releases,
    set_release_body,
    strip_generated_notes,
)

runner = CliRunner()
REPO = "dan-petty/devops-cli"

CHANGELOG_BODY = "### Added\n- A thing.\n"
APPENDED = (
    "\n\n## What's Changed\n"
    "* feat(release): v0.2.21 by @dan-petty in https://example.com/pull/329\n\n\n"
    "**Full Changelog**: https://example.com/compare/v0.2.20...v0.2.21"
)


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> Any:
    """Shape a gh invocation result."""
    import subprocess

    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# =============================================================================
# Stripping the appended summary
# =============================================================================


def test_the_generated_summary_and_its_comparison_link_are_removed_together() -> None:
    """GitHub writes both as one block, and a changelog body contains neither."""
    assert strip_generated_notes(CHANGELOG_BODY + APPENDED) == CHANGELOG_BODY


def test_a_body_without_the_summary_is_unchanged_apart_from_trailing_space() -> None:
    """A release published after the workflow disabled the summary must not be rewritten."""
    assert strip_generated_notes(CHANGELOG_BODY) == CHANGELOG_BODY


def test_a_heading_that_merely_mentions_changes_is_not_stripped() -> None:
    """Only GitHub's own heading marks the appended block."""
    body = "### Added\n- A thing.\n\n## Changes In Behaviour\n- Another.\n"
    assert strip_generated_notes(body) == body


def test_the_summary_is_detected_on_a_published_body() -> None:
    """The report says whether the section was there, so the user learns what changed."""
    published = ReleaseBody(tag="v1", published=CHANGELOG_BODY + APPENDED, expected=CHANGELOG_BODY)
    assert (published.differs, published.carries_generated_notes) == (True, True)


def test_a_body_already_equal_to_the_changelog_needs_no_edit() -> None:
    """Republishing every release on every run would churn the release feed."""
    matching = ReleaseBody(tag="v1", published=CHANGELOG_BODY, expected=CHANGELOG_BODY)
    assert matching.differs is False


def test_trailing_whitespace_alone_is_not_a_difference() -> None:
    """GitHub normalises trailing newlines, which must not read as drift forever."""
    spaced = ReleaseBody(tag="v1", published=CHANGELOG_BODY + "\n\n", expected=CHANGELOG_BODY)
    assert spaced.differs is False


# =============================================================================
# Reading and writing releases
# =============================================================================


def test_published_releases_are_listed_newest_first() -> None:
    """The listing drives `--all`, so its order is the order releases are visited."""
    payload = json.dumps([{"tagName": "v0.2.21"}, {"tagName": "v0.2.20"}])
    with patch("devops_cli.github.release_notes.run_gh", return_value=_completed(payload)):
        assert list_published_releases(REPO) == ["v0.2.21", "v0.2.20"]


def test_a_failed_listing_raises_rather_than_reporting_no_releases() -> None:
    """An empty sweep and an unreachable API must not print the same thing."""
    with patch("devops_cli.github.release_notes.run_gh", return_value=_completed(returncode=1)):
        with pytest.raises(GitHubOperationError):
            list_published_releases(REPO)


def test_a_malformed_listing_raises() -> None:
    """Unparseable output is not an empty repository."""
    with patch("devops_cli.github.release_notes.run_gh", return_value=_completed("{oops")):
        with pytest.raises(GitHubOperationError):
            list_published_releases(REPO)


def test_an_unreadable_release_body_is_none() -> None:
    """A release that cannot be read is skipped, not overwritten from a guess."""
    with patch("devops_cli.github.release_notes.run_gh", return_value=_completed(returncode=1)):
        assert get_release_body(REPO, "v0.2.21") is None


def test_a_body_is_read_from_the_release() -> None:
    """The comparison needs what is actually published, not what was published once."""
    payload = json.dumps({"body": CHANGELOG_BODY})
    with patch("devops_cli.github.release_notes.run_gh", return_value=_completed(payload)):
        assert get_release_body(REPO, "v0.2.21") == CHANGELOG_BODY


def test_a_failed_edit_is_reported_rather_than_counted_as_success() -> None:
    """A release left wrong must not print as fixed."""
    with patch("devops_cli.github.release_notes.run_gh", return_value=_completed(returncode=1)):
        assert set_release_body(REPO, "v0.2.21", CHANGELOG_BODY) is False


def test_the_new_body_is_passed_to_the_edit() -> None:
    """The whole point is that the release ends up carrying the changelog text."""
    with patch("devops_cli.github.release_notes.run_gh", return_value=_completed()) as invoked:
        set_release_body(REPO, "v0.2.21", CHANGELOG_BODY)
    assert CHANGELOG_BODY in invoked.call_args.args[0]


# =============================================================================
# The command
# =============================================================================


def _invoke(args: list[str], published: str, expected: str | None) -> Any:
    """Run sync-notes against one release with a fixed published and changelog body."""
    with (
        patch("devops_cli.commands.gh._resolve_repo", return_value=REPO),
        patch("devops_cli.github.release_notes.get_release_body", return_value=published),
        patch("devops_cli.commands.release._resolve_release_notes", return_value=expected),
        patch("devops_cli.github.release_notes.set_release_body", return_value=True) as edited,
    ):
        result = runner.invoke(app, ["sync-notes", *args])
    return result, edited


def test_the_command_republishes_a_release_carrying_the_generated_summary() -> None:
    """This is the case the four affected releases were in."""
    result, edited = _invoke(["--version", "0.2.21"], CHANGELOG_BODY + APPENDED, CHANGELOG_BODY)
    assert (result.exit_code, edited.call_count) == (0, 1)


def test_the_command_says_what_it_removed() -> None:
    """A silent rewrite of a published artifact leaves no way to tell what happened."""
    result, _ = _invoke(["--version", "0.2.21"], CHANGELOG_BODY + APPENDED, CHANGELOG_BODY)
    assert "removed GitHub's generated summary" in result.output


def test_a_release_already_in_sync_is_left_alone() -> None:
    """Rewriting an unchanged release would churn the feed on every run."""
    result, edited = _invoke(["--version", "0.2.21"], CHANGELOG_BODY, CHANGELOG_BODY)
    assert (result.exit_code, edited.call_count) == (0, 0)


def test_a_release_without_a_changelog_entry_is_skipped() -> None:
    """An absent entry is not an instruction to blank the release."""
    result, edited = _invoke(["--version", "0.9.9"], CHANGELOG_BODY, None)
    assert (edited.call_count, "no changelog entry" in result.output) == (0, True)


def test_an_unreadable_release_is_skipped() -> None:
    """Overwriting a release whose body could not be read would destroy it."""
    with (
        patch("devops_cli.commands.gh._resolve_repo", return_value=REPO),
        patch("devops_cli.github.release_notes.get_release_body", return_value=None),
        patch("devops_cli.commands.release._resolve_release_notes", return_value=CHANGELOG_BODY),
        patch("devops_cli.github.release_notes.set_release_body", return_value=True) as edited,
    ):
        result = runner.invoke(app, ["sync-notes", "--version", "0.2.21"])
    assert (edited.call_count, "could not be read" in result.output) == (0, True)
