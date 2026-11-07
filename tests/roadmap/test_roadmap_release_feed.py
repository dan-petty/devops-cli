"""The releases of a repository and the closed issues each one carries (#2917).

GitHub is faked at the `gh` process edge (`GitHubFake`). A release names its pull requests in its
changelog, and the body of each pull request names the issues it closes.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.release_feed import (
    GitHubReleaseFeed,
    ReleaseInfo,
    closing_numbers,
    pull_numbers,
)
from tests.support.fakes.github_repository import GitHubFake

REPO = "example/roadmap"
PUBLISHED = datetime(2026, 11, 2, 9, 30, tzinfo=UTC)
CHANGELOG = (
    "## [1.0.0](https://example.com/compare/v0.9.0...v1.0.0) (2026-11-02)\n\n"
    "### Features\n\n"
    "* **a:** x ([#1](https://example.com/issues/1)) ([abc](https://example.com/commit/abc))\n"
    "* **b:** y ([#2](https://example.com/issues/2)) ([def](https://example.com/commit/def))\n"
)


def test_the_pull_requests_of_a_release_are_the_links_of_its_changelog() -> None:
    assert pull_numbers(CHANGELOG) == (1, 2)
    assert pull_numbers("## 1.0.0\n\nNo links, and (#3) is plain text.") == ()


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Closes #101\n\nMore text", (101,)),
        ("Summary\n\nfixes #102\nResolved #103", (102, 103)),
        ("CLOSES #104", (104,)),
        ("This does not close #105", ()),
        ("Closes #x", ()),
        ("Closes #7\nCloses #7", (7,)),
    ],
    ids=["closes", "fixes-resolved", "upper-case", "inside-a-sentence", "not-a-number", "twice"],
)
def test_the_issues_of_a_pull_request_follow_a_closing_word_at_the_start_of_a_line(
    body: str, expected: tuple[int, ...]
) -> None:
    assert closing_numbers(body) == expected


def _feed() -> tuple[GitHubFake, GitHubReleaseFeed]:
    github = GitHubFake(REPO)
    return github, GitHubReleaseFeed(REPO, runner=github)


def test_the_list_of_releases_is_one_read_with_the_limit() -> None:
    github, feed = _feed()
    github.seed_release("v0.9.0", "old", PUBLISHED.replace(day=1))
    github.seed_release("v1.0.0", CHANGELOG, PUBLISHED)
    github.seed_release("v1.1.0-rc.1", "rc", PUBLISHED.replace(hour=11), prerelease=True)
    github.seed_release("v1.1.0", "draft", PUBLISHED.replace(hour=12), draft=True)

    releases = feed.releases(30)

    assert github.calls == [["api", "repos/example/roadmap/releases?per_page=30"]]
    assert [(r.tag, r.draft, r.prerelease) for r in releases] == [
        ("v1.1.0", True, False),
        ("v1.1.0-rc.1", False, True),
        ("v1.0.0", False, False),
        ("v0.9.0", False, False),
    ]
    assert releases[2] == ReleaseInfo(
        tag="v1.0.0",
        url="https://github.com/example/roadmap/releases/tag/v1.0.0",
        published_at=PUBLISHED,
        draft=False,
        prerelease=False,
        body=CHANGELOG,
    )


def test_the_closed_issues_come_from_the_pull_requests_of_the_changelog() -> None:
    github, feed = _feed()
    github.seed_issue(1, "pull one", state="closed", body="Closes #101", pull_request=True)
    github.seed_issue(
        2, "pull two", state="closed", body="Fixes #102\nCloses #101", pull_request=True
    )
    github.seed_issue(101, "one", state="closed")
    github.seed_issue(102, "two", state="closed")
    github.seed_release("v1.0.0", CHANGELOG, PUBLISHED)
    release = feed.releases(30)[0]
    github.calls.clear()

    assert feed.closed_issues(release) == (101, 102)
    assert [call[1] for call in github.calls] == [
        "repos/example/roadmap/issues/1",
        "repos/example/roadmap/issues/2",
        "repos/example/roadmap/issues/101",
        "repos/example/roadmap/issues/102",
    ]


def test_an_open_issue_and_a_pull_request_are_not_closed_issues() -> None:
    github, feed = _feed()
    github.seed_issue(
        1, "pull", state="closed", body="Closes #103\nCloses #104\nCloses #105", pull_request=True
    )
    github.seed_issue(103, "still open")
    github.seed_issue(104, "another pull", state="closed", pull_request=True)
    github.seed_issue(105, "done", state="closed")
    release = ReleaseInfo("v1.0.0", "u", PUBLISHED, False, False, "([#1](https://e.com/1))")

    assert feed.closed_issues(release) == (105,)


def test_an_issue_that_answers_404_is_left_out() -> None:
    github, feed = _feed()
    github.seed_issue(1, "pull", state="closed", body="Closes #404\nCloses #105", pull_request=True)
    github.seed_issue(105, "done", state="closed")
    release = ReleaseInfo("v1.0.0", "u", PUBLISHED, False, False, "([#1](https://e.com/1))")

    assert feed.closed_issues(release) == (105,)


def test_any_other_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    github, feed = _feed()
    github.seed_issue(1, "pull", state="closed", body="Closes #105", pull_request=True)
    original = github._answer

    def broken(args: list[str], stdin: str | None) -> object:
        return (
            (1, "gh: Server Error (HTTP 500)")
            if args[-1].endswith("issues/1")
            else original(args, stdin)
        )

    monkeypatch.setattr(github, "_answer", broken)
    release = ReleaseInfo("v1.0.0", "u", PUBLISHED, False, False, "([#1](https://e.com/1))")

    with pytest.raises(GitHubOperationError, match="Could not read #1"):
        feed.closed_issues(release)


def test_a_failed_list_raises() -> None:
    def failing(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "gh: Server Error (HTTP 500)")

    feed = GitHubReleaseFeed(REPO, runner=failing)

    with pytest.raises(GitHubOperationError, match="Could not read the releases"):
        feed.releases(30)
