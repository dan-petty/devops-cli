"""Functional change fallback for repositories without OpenSpec (#4730):
`CHANGELOG.md` sections (`Features` and `Bug Fixes` in the first release), then `feat` and `fix`
commit subjects, then `listing.merged_titles` pull request titles, else `skipped`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from devops_cli.config.settings import load_settings
from devops_cli.roadmap.project_review.catalog import load_catalog
from devops_cli.roadmap.project_review.data import FactStatus, ReviewWindow, WindowKind
from devops_cli.roadmap.project_review.dispatch import ReadContext, read_catalog
from devops_cli.roadmap.project_review.functional import changelog_sections, functional_change
from devops_cli.roadmap.stores.listing_snapshot import FileSnapshotStore
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer

REPO = "example/project"
END = datetime(2026, 11, 11, 14, 51, 23, tzinfo=UTC)
WINDOW = ReviewWindow(
    kind=WindowKind.PERIOD,
    id="w",
    base_sha="a" * 40,
    head_sha="b" * 40,
    start=END - timedelta(days=7),
    end=END,
    previous_id=None,
)


def _pr_row(number: int, title: str, merged_at: str) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "html_url": f"https://github.com/{REPO}/pull/{number}",
        "body": "",
        "state": "closed",
        "created_at": "2026-11-04T00:00:00Z",
        "updated_at": merged_at,
        "closed_at": merged_at,
        "labels": [],
        "pull_request": {"merged_at": merged_at},
    }


def test_changelog_sections_reads_only_features_and_bug_fixes_of_the_first_release() -> None:
    text = """\
# Changelog

## [0.2.0](https://example.com/compare/v0.1.0...v0.2.0) (2026-11-11)

### Features

* **cli:** add profile flag ([#10](https://example.com/issues/10))

### Performance Improvements

* speed up startup

### Bug Fixes

* keep valid paths

## [0.1.0](https://example.com/releases/tag/v0.1.0) (2026-11-01)

### Features

* initial release
"""
    assert changelog_sections(text) == [
        "cli: add profile flag (#10)",
        "keep valid paths",
    ]


def test_the_changelog_gives_the_functional_change_then_the_subjects_then_the_pull_request_titles(
    tmp_path: Path, git_fake: GitFake
) -> None:
    checkout = tmp_path / "repo"
    checkout.mkdir()
    changelog = checkout / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [1.0.0](https://example.com) (2026-11-11)\n\n"
        "### Features\n\n* add health probe\n\n### Bug Fixes\n\n* close stale file\n",
        encoding="utf-8",
    )

    from_changelog = functional_change(checkout, WINDOW, ["Merged PR title"])
    assert (
        from_changelog.id,
        from_changelog.section,
        from_changelog.source,
        from_changelog.status,
        from_changelog.n,
        from_changelog.value,
    ) == (
        "functional.change",
        "changes",
        "changelog",
        FactStatus.OK,
        2,
        ["add health probe", "close stale file"],
    )

    changelog.unlink()
    git_fake.answer(
        lambda call: "log" in call.argv,
        ProcessAnswer(
            stdout=(
                "\x1e" + ("c" * 40) + "\x1f1794300000\x1ffeat(api): expose readiness\x00"
                "\x1e" + ("d" * 40) + "\x1f1794200000\x1fchore: bump tool\x00"
                "\x1e" + ("e" * 40) + "\x1f1794100000\x1ffix: handle empty list\x00"
            )
        ),
    )
    from_subjects = functional_change(checkout, WINDOW, ["Merged PR title"])
    assert (
        from_subjects.source,
        from_subjects.status,
        from_subjects.n,
        from_subjects.value,
    ) == (
        "subjects",
        FactStatus.OK,
        2,
        ["feat(api): expose readiness", "fix: handle empty list"],
    )

    git_fake.answer(
        lambda call: "log" in call.argv,
        ProcessAnswer(stdout="\x1e" + ("d" * 40) + "\x1f1794200000\x1fchore: bump tool\x00"),
    )
    from_prs = functional_change(checkout, WINDOW, ["Add deployment job", "Fix config parser"])
    assert (from_prs.source, from_prs.status, from_prs.n, from_prs.value) == (
        "pull_requests",
        FactStatus.OK,
        2,
        ["Add deployment job", "Fix config parser"],
    )

    skipped = functional_change(checkout, WINDOW, [])
    assert (skipped.source, skipped.status, skipped.value, skipped.n) == (
        "functional",
        FactStatus.SKIPPED,
        None,
        None,
    )
    assert skipped.reason


def test_listing_merged_titles_returns_titles_and_empty_list_as_ok(
    tmp_path: Path, git_fake: GitFake, github_api: GitHubApiFake
) -> None:
    """`listing.merged_titles` collects merged PR titles in the window and yields `[]` with `n=0`
    and status `ok` when none merged (#4730)."""
    git_fake.answer(lambda call: "ls-tree" in call.argv, ProcessAnswer(stdout=""))
    catalog = load_catalog()
    since = WINDOW.start.strftime("%Y-%m-%dT%H:%M:%SZ")
    issues_path = (
        f"/repos/{REPO}/issues?state=all&sort=updated&direction=desc&since={since}&per_page=100"
    )

    first_root = tmp_path / "with_prs"
    first_root.mkdir()
    github_api.route(
        "GET",
        issues_path,
        github_json(
            [
                _pr_row(1, "Outside window", "2026-10-01T00:00:00Z"),
                _pr_row(2, "Add cache warm", "2026-11-08T10:00:00Z"),
                _pr_row(3, "Fix retry delay", "2026-11-10T12:00:00Z"),
            ]
        ),
    )
    context = ReadContext(
        checkout=first_root,
        repo=REPO,
        window=WINDOW,
        settings=load_settings(),
        now=END,
        snapshots=FileSnapshotStore(first_root / "snap"),
        review_snapshots=FileSnapshotStore(first_root / "rev"),
    )
    result = read_catalog(catalog, context)
    [merged] = [fact for fact in result.facts if fact.id == "listing.merged_titles"]
    assert (merged.status, merged.n, merged.value) == (
        FactStatus.OK,
        2,
        ["Fix retry delay", "Add cache warm"],
    ), merged.reason

    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    github_api.route("GET", issues_path, github_json([]))
    empty_result = read_catalog(
        catalog,
        ReadContext(
            checkout=empty_root,
            repo=REPO,
            window=WINDOW,
            settings=load_settings(),
            now=END,
            snapshots=FileSnapshotStore(empty_root / "snap"),
            review_snapshots=FileSnapshotStore(empty_root / "rev"),
        ),
    )
    [empty_merged] = [fact for fact in empty_result.facts if fact.id == "listing.merged_titles"]
    assert (empty_merged.status, empty_merged.n, empty_merged.value) == (FactStatus.OK, 0, [])
