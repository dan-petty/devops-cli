"""A comment of a person is new input for a suspended roadmap job (#2754).

A job that failed its limit of rounds in a row does not run until its input changes. The input of
a job that failed a round holds the creation time of the newest comment of a person on an issue
of its repository, so a person's answer starts the job again, and no other comment does. The
rounds run over `InMemoryRoadmapStore`, which gives its comments newest first as the GitHub
listing does, and over rows whose runners fail as the test says.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.defaults import (
    DEFAULT_GH_REST_PER_PAGE,
    DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES,
    DEFAULT_SERVICE_MAX_FAILED_ROUNDS,
)
from devops_cli.exceptions import RoadmapRunError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.run import FailureLedger, JobOutcome, build_stub_table, run_due_jobs
from devops_cli.roadmap.stores.store import IssueComment
from tests.support.fakes.roadmap_store import DEFAULT_ROADMAP_MEMORY_ACTOR, InMemoryRoadmapStore

REPO = "example-org/repo1"
START = datetime(2026, 11, 5, 12, tzinfo=UTC)
POLL = {("poll", "", ""): 1}
WEBHOOK = {("webhook", "issues", "labeled"): 1}
LIMIT = DEFAULT_SERVICE_MAX_FAILED_ROUNDS
PERSON = ("alice", "OWNER")
APP_BOT = ("devops-cli-service[bot]", "CONTRIBUTOR")


class _Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


class _Store(InMemoryRoadmapStore):
    """The in-memory roadmap that counts each read of the comments and each comment it gives."""

    def __init__(self, clock: _Clock) -> None:
        super().__init__(clock=clock)
        self.reads = 0
        self.taken = 0
        self.since: list[datetime | None] = []
        self.broken = False

    def comments_since(self, since: datetime | None) -> Iterator[IssueComment]:
        self.reads += 1
        self.since.append(since)
        if self.broken:
            raise GitHubOperationError("the comments could not be read")
        for comment in super().comments_since(since):
            self.taken += 1
            yield comment


class _World:
    """Rounds over one repository, one ledger and one store. `rows` gives, for each row of the
    table, its outcomes in turn: True is a success, False a failure. A row fails when it has no
    outcome left."""

    def __init__(
        self,
        tmp_path: Path,
        rows: Mapping[str, Sequence[bool]] | None = None,
        *,
        limit: int = LIMIT,
    ) -> None:
        self.clock = _Clock()
        self.store = _Store(self.clock)
        self.issue = self.store.seed_issue("An item")
        self.ledger = FailureLedger(limit=limit)
        self.ran: list[str] = []
        self._plans = {name: list(plan) for name, plan in (rows or {"intake": ()}).items()}
        self._table = build_stub_table({name: self._runner(name) for name in self._plans})
        self._tmp_path = tmp_path

    def _runner(self, name: str) -> Any:
        def run(**_: Any) -> JobOutcome:
            self.ran.append(name)
            plan = self._plans[name]
            if plan.pop(0) if plan else False:
                return JobOutcome()
            raise GitHubOperationError(f"the {name} row failed")

        return run

    def poll(
        self,
        step: timedelta = timedelta(minutes=30),
        *,
        dry_run: bool = False,
        batch: Mapping[tuple[str, str, str], int] = POLL,
    ) -> list[str]:
        """One round that `batch` starts (a poll unless given), `step` after the last, and the
        rows that ran in it."""
        self.clock.now += step
        before = len(self.ran)
        try:
            run_due_jobs(
                REPO,
                self.store,
                batch,
                table=self._table,
                data_dir=self._tmp_path,
                now=self.clock.now,
                failures=self.ledger,
                dry_run=dry_run,
            )
        except RoadmapRunError:
            pass
        return self.ran[before:]

    def comment(
        self, author: tuple[str | None, str | None], *, on_pull_request: bool = False
    ) -> None:
        """A comment on the item, or on a pull request, 30 seconds after the last round."""
        self.clock.now += timedelta(seconds=30)
        login, association = author
        number = self.issue
        if on_pull_request:
            number = self.store.seed_pull("A pull request", head_ref="feat/1-a-change")
        self.store.seed_comment(
            number, "An answer", author_login=login, author_association=association
        )

    def bury(self) -> None:
        """Newer comments of the bot, enough to fill the window that a round reads."""
        for _ in range(DEFAULT_GH_REST_PER_PAGE):
            self.clock.now += timedelta(seconds=1)
            self.store.seed_comment(
                self.issue,
                "A notice",
                author_login=APP_BOT[0],
                author_association=APP_BOT[1],
            )

    def suspend(self) -> None:
        """Run the rounds that make the `intake` row fail its limit, and one more that the
        suspension skips."""
        assert [self.poll() for _ in range(LIMIT)] == [["intake"]] * LIMIT
        assert self.poll() == []


def test_a_comment_of_a_person_starts_a_suspended_job_again(tmp_path: Path) -> None:
    world = _World(tmp_path)
    world.suspend()

    world.comment(PERSON)

    assert world.poll() == ["intake"]


def test_a_restarted_job_runs_for_its_limit_of_rounds_and_then_stops(tmp_path: Path) -> None:
    world = _World(tmp_path)
    world.suspend()
    world.comment(PERSON)

    assert [world.poll() for _ in range(LIMIT + 2)] == [["intake"]] * LIMIT + [[], []]


@pytest.mark.parametrize(
    "author",
    [
        pytest.param(APP_BOT, id="the App bot"),
        pytest.param(("dependabot[bot]", "COLLABORATOR"), id="a bot with write access"),
        pytest.param((DEFAULT_ROADMAP_MEMORY_ACTOR, "OWNER"), id="the account of the process"),
        pytest.param(("stranger", "NONE"), id="an account with no write access"),
        pytest.param((None, "OWNER"), id="an author with no login"),
    ],
)
def test_a_comment_of_another_author_leaves_a_suspended_job_suspended(
    tmp_path: Path, author: tuple[str | None, str | None]
) -> None:
    world = _World(tmp_path)
    world.suspend()

    world.comment(author)

    assert world.poll() == []


def test_a_comment_of_a_person_on_a_pull_request_leaves_a_suspended_job_suspended(
    tmp_path: Path,
) -> None:
    world = _World(tmp_path)
    world.suspend()

    world.comment(PERSON, on_pull_request=True)

    assert world.poll() == []


def test_a_poll_with_no_new_comment_leaves_a_suspended_job_suspended(tmp_path: Path) -> None:
    world = _World(tmp_path)
    world.comment(PERSON)

    assert [world.poll() for _ in range(LIMIT + 2)] == [["intake"]] * LIMIT + [[], []]


def test_a_comment_made_before_the_last_success_leaves_a_suspended_job_suspended(
    tmp_path: Path,
) -> None:
    world = _World(tmp_path, {"intake": [True]})
    world.comment(PERSON)

    assert world.poll() == ["intake"]
    assert [world.poll() for _ in range(LIMIT + 1)] == [["intake"]] * LIMIT + [[]]


def test_a_second_failed_job_does_not_start_a_suspended_job_with_an_older_comment(
    tmp_path: Path,
) -> None:
    """The read of a round starts at the oldest last success of the jobs that failed. A job
    that starts to fail later can move it back to a comment that is older than another job's
    last success, and that comment is new input for no job that succeeded after it."""
    interval = timedelta(minutes=DEFAULT_ROADMAP_ALTERNATIVES_INTERVAL_MINUTES)
    world = _World(tmp_path, {"intake": [True, True], "alternatives": [True]}, limit=2)
    # Both rows succeed. A person comments after `alternatives` and before the last success of
    # `intake`, which succeeds again at the next round.
    assert world.poll() == ["intake", "alternatives"]
    world.comment(PERSON)
    assert world.poll() == ["intake"]
    # `intake` fails its limit of rounds, and the comment is not new input for it.
    assert [world.poll(), world.poll(), world.poll()] == [["intake"], ["intake"], []]
    # `alternatives` is due again and fails. The read of the next round starts at its last
    # success, so it finds the comment, and the comment is not newer than the success of `intake`.
    assert world.poll(interval) == ["alternatives"]

    assert world.poll() == ["alternatives"]
    assert world.store.since[-1] == START + timedelta(minutes=30)


def test_the_round_reads_the_comments_once_for_all_failed_jobs_and_stops_at_a_person(
    tmp_path: Path,
) -> None:
    world = _World(tmp_path, {"intake": (), "refine": (), "alternatives": ()})
    world.comment(PERSON)
    world.comment(PERSON)
    world.comment(APP_BOT)

    reads = []
    for _ in range(LIMIT + 1):
        before = (world.store.reads, world.store.taken)
        world.poll()
        reads.append((world.store.reads - before[0], world.store.taken - before[1]))

    # The first round has no failed job. Each later round reads once, takes the comment of the
    # bot, which is newest, and stops at the comment of the person before it.
    assert reads == [(0, 0), (1, 2), (1, 2), (1, 2)]


def test_a_round_reads_one_page_of_comments_at_most(tmp_path: Path) -> None:
    """A comment of a person that a page of newer comments follows is not read: the round
    keeps its input, and the job stays suspended."""
    world = _World(tmp_path)
    world.suspend()
    world.comment(PERSON)
    world.bury()
    taken = world.store.taken

    assert world.poll() == []
    assert world.store.taken - taken == DEFAULT_GH_REST_PER_PAGE


def test_a_comment_of_a_person_that_a_page_of_comments_follows_starts_the_job_once_more(
    tmp_path: Path,
) -> None:
    """The input of the job held that comment. When it falls out of the page that a round reads,
    the input is the one of before, so the job runs again and counts from one."""
    world = _World(tmp_path)
    world.suspend()
    world.comment(PERSON)
    assert [world.poll() for _ in range(LIMIT + 1)] == [["intake"]] * LIMIT + [[]]

    world.bury()

    assert [world.poll() for _ in range(LIMIT + 1)] == [["intake"]] * LIMIT + [[]]


def test_a_round_that_a_webhook_started_reads_no_comments(tmp_path: Path) -> None:
    """The time of such a round is new input for every job, so a comment adds nothing."""
    world = _World(tmp_path)
    world.suspend()
    world.comment(PERSON)
    reads = world.store.reads

    assert world.poll(batch=WEBHOOK) == ["intake"]
    assert world.store.reads == reads


def test_a_round_with_no_failed_job_reads_no_comments(tmp_path: Path) -> None:
    world = _World(tmp_path, {"intake": [True, True, True]})
    world.comment(PERSON)

    assert [world.poll() for _ in range(3)] == [["intake"]] * 3
    assert world.store.reads == 0


def test_a_dry_run_reads_no_comments(tmp_path: Path) -> None:
    world = _World(tmp_path)
    world.suspend()
    reads = world.store.reads

    assert world.poll(dry_run=True) == []
    assert world.store.reads == reads


def test_a_failed_read_of_the_comments_ends_the_round_and_counts_no_failed_round(
    tmp_path: Path,
) -> None:
    world = _World(tmp_path)
    assert world.poll() == ["intake"]
    causes = world.ledger.causes(REPO, "intake")

    world.store.broken = True
    with pytest.raises(GitHubOperationError, match="could not be read"):
        world.poll()

    assert (world.ran, world.ledger.causes(REPO, "intake")) == (["intake"], causes)


def test_the_line_that_suspends_a_job_names_a_comment_of_a_person(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="devops_cli.roadmap.run")
    world = _World(tmp_path)

    world.suspend()

    (line,) = [r.getMessage() for r in caplog.records if "failed 3 rounds" in r.getMessage()]
    assert "a comment of a person" in line
