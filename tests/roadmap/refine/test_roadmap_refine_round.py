"""A refine round writes each item when that item is done (#3631).

A Service stop ends the round and loses at most the item in progress. A write that fails costs the
other items nothing, and the round logs its start and its end with the counts of items taken,
written and failed. `plan_refine` writes nothing unless the caller gives it a writer.

The roadmap is the in-memory store, the model edge is the fake, and git runs on a temporary
repository.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from devops_cli.exceptions import RoadmapRefineError, ServiceStoppingError
from devops_cli.roadmap.refine.refine import plan_refine
from devops_cli.roadmap.run import _run_refine_adapter
from devops_cli.roadmap.service_stop import begin_service_stop, reset_service_stop
from devops_cli.roadmap.stores.store import ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.service_stop import stop_error

if TYPE_CHECKING:
    from devops_cli.roadmap.stores.store import IssueComment
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
_READY = json.dumps(
    {
        "problem_statement": "The item needs a design.",
        "existing_tool": "Pydantic covers the schema check.",
        "acceptance_criteria": [
            {
                "name": "A design",
                "requirement": "The item SHALL have a design.",
                "scenario": "A person reads the item",
                "when": "a person reads the item",
                "then": "the design is in the item",
            }
        ],
    }
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A checkout of `REPO` whose one commit holds `src/sample.py`."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        _git(repo, "config", key, value)
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "remote", "add", "origin", f"https://example.com/{REPO}.git")
    (repo / "src" / "sample.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


class _StopsOnComments(InMemoryRoadmapStore):
    """A store whose second read of the comments of issue `stopped` fails as the request budget
    fails it when the Service is stopping (#2753). The selection makes the first read, so the stop
    falls in the plan of that item, after the plans of the items before it."""

    stopped = 0
    comment_reads = 0

    def comments_on(self, number: int) -> list[IssueComment]:
        if number == self.stopped:
            self.comment_reads += 1
            if self.comment_reads == 2:
                raise stop_error()
        return super().comments_on(number)


def _seed_three(store: InMemoryRoadmapStore) -> list[int]:
    """Three New backlog items on a private repository, refined in the order returned."""
    store.seed_visibility(is_private=True)
    numbers = [
        store.seed_issue(
            f"Item {priority}",
            body=f"Body {priority}",
            fields={ItemField.STATUS: "New", ItemField.PRIORITY: priority},
        )
        for priority in ("P1-High", "P2-Medium", "P3-Low")
    ]
    return numbers


def _statuses(store: InMemoryRoadmapStore, numbers: list[int]) -> list[str | None]:
    return [item.status for item in (store.item(number) for number in numbers) if item]


def _round_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The lines that a round logs at its start and at its end."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "devops_cli.roadmap.refine.refine"
        and record.getMessage().startswith("Refine round")
    ]


def test_a_round_that_stops_in_item_three_keeps_items_one_and_two_and_the_next_round_takes_three(
    git_repo: Path, model_fake: ModelFake, caplog: pytest.LogCaptureFixture
) -> None:
    store = _StopsOnComments(repo=REPO)
    first, second, third = _seed_three(store)
    store.stopped = third
    model_fake.answer(_READY)

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.refine.refine"):
        with pytest.raises(ServiceStoppingError) as stopped:
            _run_refine_adapter(store, repo=REPO, clone_path=git_repo)
    after_stop = _statuses(store, [first, second, third])
    store.stopped = 0
    asked = model_fake.call_count
    _run_refine_adapter(store, repo=REPO, clone_path=git_repo)

    assert (
        stopped.value.error_code,
        after_stop,
        [json.loads(call.prompt)["number"] for call in model_fake.calls[asked:]],
        _statuses(store, [first, second, third]),
        _round_lines(caplog)[:2],
    ) == (
        "SERVICE_STOPPING",
        ["Ready", "Ready", "New"],
        [third],
        ["Ready", "Ready", "Ready"],
        [
            f"Refine round for {REPO} started: 3 item(s) taken.",
            f"Refine round for {REPO} ended: taken=3, written=2, failed=0.",
        ],
    )


def test_a_stop_during_item_one_writes_item_one_and_the_next_round_takes_the_others(
    git_repo: Path, model_fake: ModelFake
) -> None:
    """The Service gets SIGTERM while it refines item 1. Item 1 runs on to its write, then no next
    item starts, and the round ends with the stop. The next round takes items 2 and 3 (#4485)."""
    store = InMemoryRoadmapStore(repo=REPO)
    first, second, third = _seed_three(store)

    def ready(_prompt: str) -> str:
        begin_service_stop()
        return _READY

    model_fake.answer(ready)
    with pytest.raises(ServiceStoppingError) as stopped:
        _run_refine_adapter(store, repo=REPO, clone_path=git_repo)
    after_stop = _statuses(store, [first, second, third])
    reset_service_stop()
    asked = model_fake.call_count
    model_fake.answer(_READY)
    _run_refine_adapter(store, repo=REPO, clone_path=git_repo)

    assert (
        stopped.value.error_code,
        after_stop,
        [json.loads(call.prompt)["number"] for call in model_fake.calls[asked:]],
    ) == ("SERVICE_STOPPING", ["Ready", "New", "New"], [second, third])


def test_a_write_that_fails_costs_the_other_items_nothing_and_the_round_logs_its_counts(
    git_repo: Path, model_fake: ModelFake, caplog: pytest.LogCaptureFixture
) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    first, second, third = _seed_three(store)
    store.fail_write(write="set_field", item=second)
    model_fake.answer(_READY)

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.refine.refine"):
        with pytest.raises(RoadmapRefineError) as raised:
            _run_refine_adapter(store, repo=REPO, clone_path=git_repo)

    assert (
        _statuses(store, [first, second, third]),
        list(raised.value.failed_items),
        raised.value.readied_count,
        _round_lines(caplog),
    ) == (
        ["Ready", "New", "Ready"],
        [second],
        2,
        [
            f"Refine round for {REPO} started: 3 item(s) taken.",
            f"Refine round for {REPO} ended: taken=3, written=2, failed=1.",
        ],
    )


def test_plan_refine_without_a_writer_writes_nothing(git_repo: Path, model_fake: ModelFake) -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    numbers = _seed_three(store)
    model_fake.answer(_READY)

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (len(plan.refined_items), store.writes, _statuses(store, numbers)) == (
        3,
        [],
        ["New", "New", "New"],
    )
