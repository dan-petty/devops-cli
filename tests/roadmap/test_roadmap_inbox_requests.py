"""The reads of `devops roadmap inbox` and their plan (#2915).

The plan lists the same listings the store reads, built by the same functions, so a dry run
cannot drift from a run. The inbox sends only reads, and never reads the listing of every issue.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT,
    CONST_ROADMAP_LABELS_PATH,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.inbox import Inbox, InboxKind, InboxLine, read_inbox
from devops_cli.roadmap.request_plan import StoreRequests, inbox_requests
from devops_cli.roadmap.stores.github_store import (
    issues_endpoint,
    labels_endpoint,
    listing_path,
    path_commits_args,
    pulls_endpoint,
)
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    encode_job_record,
    with_record,
)
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS
from tests.support.fakes.github import API
from tests.support.fakes.github_repository import GitHubFake
from tests.support.roadmap_github_store import REPO as STORE_REPO
from tests.support.roadmap_github_store import fake_store

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


# ── The line of a stop sends no read of its own (#3648) ───────────────────────

LABELS = "- name: scope/cli\n  color: DCDCD6\n  description: The CLI\n"
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
STOP: dict[ImplementRecordKey, str] = {
    ImplementRecordKey.STOPPED: "group 2",
    ImplementRecordKey.FAILURE: "check_failed",
    ImplementRecordKey.LEFT_ACTION: "wait",
}


def _repository(marks: Mapping[Any, str | None]) -> GitHubFake:
    """A repository whose one open issue holds a Priority and `status/blocked`, and the job
    record `marks`. The repository holds each label that `.github/labels.yml` declares, so the
    inbox has no line of the labels and both runs read the same listings."""
    github = GitHubFake(STORE_REPO, files={CONST_ROADMAP_LABELS_PATH: LABELS})
    github.seed_label("scope/cli", "DCDCD6", "The CLI")
    for spec in WORKFLOW_LABELS:
        github.seed_label(spec.name, spec.color, spec.description)
    github.seed_issue(
        1,
        "work",
        labels=("priority/p2-medium", "status/blocked"),
        body=with_record("", encode_job_record({}, marks)),
    )
    return github


def _inbox(github: GitHubFake) -> Inbox:
    """The inbox of the repository `github` fakes, read as `devops roadmap inbox` reads it."""
    return read_inbox(
        fake_store(github),
        repo=STORE_REPO,
        now=NOW,
        planned_limit=20,
        draft_days=7,
        wait_days=7,
    )


def _path(args: list[str]) -> str:
    """The path of one `gh` call: the URL of a listing, or the path that `gh api` reads."""
    if args[0].startswith(f"{API}/"):
        return args[0].removeprefix(f"{API}/")
    return next(arg for arg in args[1:] if "/" in arg and not arg.startswith(("-", "Accept")))


def _blocked(github: GitHubFake) -> InboxLine:
    """The one blocked line of the inbox of the repository `github` fakes."""
    lines = [line for line in _inbox(github).jobs if line.kind is InboxKind.BLOCKED]
    assert len(lines) == 1, lines
    return lines[0]


def test_the_inbox_sends_the_same_requests_for_a_stopped_item_as_for_an_item_with_no_stop() -> None:
    """The line of a stopped item states its class and its action left from the job record that
    the listing read already, so its run sends the same requests as a run whose item holds no
    stop, and no call reads one issue."""
    stopped, running = _repository(STOP), _repository({})

    stopped_line, running_line = _blocked(stopped), _blocked(running)

    assert stopped_line.subject == "work: stopped at group 2, with the class check_failed"
    assert stopped_line.clear == (
        f"Fix the cause, then comment `{CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT}` on #1. "
        "The action left is `wait`."
    )
    assert "check_failed" not in running_line.subject
    assert "`wait`" not in running_line.clear
    assert [_path(args) for args in stopped.calls] == [_path(args) for args in running.calls]
    assert not [path for path in map(_path, stopped.calls) if "/issues/" in path]
