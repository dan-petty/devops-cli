"""The reads of `devops roadmap inbox` and their plan (#2915).

The plan lists the same listings the store reads, built by the same functions, so a dry run
cannot drift from a run. The inbox sends only reads, and never reads the listing of every issue.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.github_store import (
    issues_endpoint,
    labels_endpoint,
    listing_path,
    path_commits_args,
    pulls_endpoint,
)
from devops_cli.roadmap.request_plan import StoreRequests, inbox_requests
from tests.support.fakes.github import API

REPO = "example/roadmap"


def _urls(plan: tuple[object, ...] | list[object]) -> list[str]:
    return [request.argv[1] for request in plan if request.argv[0] == "GET"]  # type: ignore[attr-defined]


def test_the_plan_of_each_listing_is_the_path_the_store_reads() -> None:
    store = StoreRequests(REPO)
    assert (
        _urls(store.open_items()),
        _urls(store.open_pulls()),
        _urls(store.repository_labels()),
    ) == (
        [f"{API}{listing_path(issues_endpoint(REPO, 'state=open'))}"],
        [f"{API}{listing_path(pulls_endpoint(REPO))}"],
        [f"{API}{listing_path(labels_endpoint(REPO))}"],
    )


def test_a_listing_is_read_once_and_again_for_each_page() -> None:
    page = MESSAGES.roadmap.plan_repeat_page
    assert [r.repeat for r in StoreRequests(REPO).open_pulls()] == [page]


def test_the_inbox_plan_reads_open_issues_not_every_issue_and_writes_nothing() -> None:
    reads, writes = inbox_requests(REPO)
    urls = _urls(reads)
    assert (
        writes,
        any("state=all" in url for url in urls),
        any("state=open" in url and "/issues?" in url for url in urls),
    ) == ((), False, True)


def test_the_commit_of_the_labels_file_is_read_only_when_the_labels_differ() -> None:
    reads, _ = inbox_requests(REPO)
    commit = ("gh", *path_commits_args(REPO, CONST_ROADMAP_LABELS_PATH))
    commits = [r for r in reads if r.argv == commit]
    assert [r.condition for r in commits] == [MESSAGES.roadmap.plan_conditions["labels_differ"]]


def test_a_run_reads_three_listings_a_file_and_a_commit_that_differing_labels_make() -> None:
    """The page `docs/roadmap/inbox.md` states these reads: three listings that repeat for each
    page, one read of the labels file, one commit read that only differing labels make, and one
    check-run read for each open draft of a job."""
    reads, _ = inbox_requests(REPO)
    page = MESSAGES.roadmap.plan_repeat_page
    differ = MESSAGES.roadmap.plan_conditions["labels_differ"]

    assert [(r.repeat, r.condition) for r in reads] == [
        (page, ""),
        (page, ""),
        (page, ""),
        ("", ""),
        ("", differ),
        (MESSAGES.roadmap.plan_repeat_draft, MESSAGES.roadmap.plan_conditions["job_drafts"]),
    ]


def test_the_dry_run_lists_reads_for_each_service_repo_and_no_write(
    cli: Callable[..., Any],
    config: Callable[..., Any],
    roadmap_store_repos: list[str],
) -> None:
    config(service={"repos": ["example/app", "example/roadmap"]})

    result = cli("roadmap", "inbox", "--dry-run")

    assert result.exit_code == 0, result.output
    assert roadmap_store_repos == []
    for repo in ("example/app", "example/roadmap"):
        assert f"{API}{listing_path(pulls_endpoint(repo))}" in result.output
    assert "PATCH" not in result.output


def test_check_reads_are_listed_only_for_open_job_drafts() -> None:
    reads, writes = inbox_requests(REPO)
    checks = [request for request in reads if "check-runs" in request.argv[1]]
    assert writes == ()
    assert [request.condition for request in checks] == [
        MESSAGES.roadmap.plan_conditions["job_drafts"]
    ]
