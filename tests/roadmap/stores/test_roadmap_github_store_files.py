"""The files, the directories and the commits of a path that the GitHub roadmap store reads from
the repository (#1335).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from devops_cli.exceptions.git import (
    GitHubFileNotFoundError,
    GitHubOperationError,
)
from tests.support.roadmap_github_store import REPO, recorded_store


def test_repository_file_reads_raw_contents_at_the_ref() -> None:
    store, runner = recorded_store({"contents/": "- name: type/bug\n"})
    texts = (
        store.repository_file(".github/labels.yml", ref="feat/topic"),
        store.repository_file(".github/labels.yml"),
    )
    assert (texts, [args for args, _ in runner.calls]) == (
        ("- name: type/bug\n", "- name: type/bug\n"),
        [
            [
                "api",
                "-H",
                "Accept: application/vnd.github.raw+json",
                f"repos/{REPO}/contents/.github/labels.yml?ref=feat%2Ftopic",
            ],
            [
                "api",
                "-H",
                "Accept: application/vnd.github.raw+json",
                f"repos/{REPO}/contents/.github/labels.yml",
            ],
        ],
    )


def test_a_missing_file_raises_not_found_and_another_failure_raises_as_a_failed_read() -> None:
    missing, _ = recorded_store({"contents/": (1, "gh: Not Found (HTTP 404)")})
    broken, _ = recorded_store({"contents/": (1, "gh: Server Error (HTTP 502)")})
    with pytest.raises(GitHubFileNotFoundError, match=r"has no \.github/labels\.yml at main"):
        missing.repository_file(".github/labels.yml", ref="main")
    with pytest.raises(
        GitHubOperationError, match=r"Could not read \.github/labels\.yml"
    ) as failed:
        broken.repository_file(".github/labels.yml", ref="main")
    assert type(failed.value) is GitHubOperationError


def test_repository_files_lists_the_files_of_a_directory_through_the_contents_request() -> None:
    listing = json.dumps(
        [
            {"name": "0001-a.md", "path": "docs/adr/0001-a.md", "type": "file"},
            {"name": "old", "path": "docs/adr/old", "type": "dir"},
            {"name": "0002-b.md", "path": "docs/adr/0002-b.md", "type": "file"},
        ]
    )
    store, runner = recorded_store({"contents/docs/adr": listing})

    paths = store.repository_files("docs/adr", ref="feat/topic")

    assert (paths, [args for args, _ in runner.calls]) == (
        ["docs/adr/0001-a.md", "docs/adr/0002-b.md"],
        [
            [
                "api",
                "-H",
                "Accept: application/vnd.github.raw+json",
                f"repos/{REPO}/contents/docs/adr?ref=feat%2Ftopic",
            ]
        ],
    )


def test_a_missing_directory_raises_not_found_and_another_failure_raises_as_a_failed_read() -> None:
    missing, _ = recorded_store({"contents/": (1, "gh: Not Found (HTTP 404)")})
    broken, _ = recorded_store({"contents/": (1, "gh: Server Error (HTTP 502)")})
    with pytest.raises(GitHubFileNotFoundError, match=r"has no docs/adr at main"):
        missing.repository_files("docs/adr", ref="main")
    with pytest.raises(GitHubOperationError, match=r"Could not read docs/adr") as failed:
        broken.repository_files("docs/adr", ref="main")
    assert type(failed.value) is GitHubOperationError


def test_a_path_that_is_a_file_is_no_directory_listing() -> None:
    store, _ = recorded_store({"contents/": "text of a file\n"})

    with pytest.raises(GitHubOperationError, match=r"malformed docs/adr"):
        store.repository_files("docs/adr")


def test_path_changed_at_reads_the_newest_commit_of_a_path_once_for_the_stores_life() -> None:
    """The newest commit on the default branch that changed a path, one commit a page, as the
    commits API lists them newest first; a path no commit changed has no time, and each path is
    read once for the store's life (#2005)."""
    newest = {"sha": "0a2bfe1f", "commit": {"committer": {"date": "2026-10-24T06:06:57Z"}}}
    store, runner = recorded_store({"path=src%2Fapp.py": [newest], "path=src%2Fgone.py": []})
    times = [store.path_changed_at(path) for path in ("src/app.py", "src/app.py", "src/gone.py")]
    assert (times, [args for args, _ in runner.calls]) == (
        [datetime(2026, 10, 24, 6, 6, 57, tzinfo=UTC)] * 2 + [None],
        [
            ["api", f"repos/{REPO}/commits?path=src%2Fapp.py&per_page=1"],
            ["api", f"repos/{REPO}/commits?path=src%2Fgone.py&per_page=1"],
        ],
    )


def test_a_failed_read_of_the_commits_of_a_path_raises() -> None:
    store, _ = recorded_store({"path=": (1, "gh: Server Error (HTTP 502)")})
    with pytest.raises(GitHubOperationError, match=r"Could not read the commits of src/app\.py"):
        store.path_changed_at("src/app.py")
