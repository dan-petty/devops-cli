"""The row of each GitHub request of a Service round (#6012): the rows of the due table, the
round's own reads under the loop that started it, and the check of open work under `idle_check`.
No request of the Service counts under the row `other`, so the metric names the loop that spends
the budget. One lane of a repository reads the open work, not each lane.

The contract runs every lane that `service_jobs` builds, in the workers of the Service, over the
repository fake. Each row of the table reads one issue, so the test sees the requests that the
round sends outside its rows.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.settings import GitHubAppConfig, ServiceConfig
from devops_cli.github import session_transport
from devops_cli.github.rate_limiter import count_request
from devops_cli.github.request_scope import request_labels
from devops_cli.roadmap import run
from devops_cli.roadmap.run import DEFAULT_DUE_TABLE, JobOutcome, service_jobs
from devops_cli.roadmap.stores.store import RoadmapStore
from devops_cli.server.service import IdleRepos, ServiceManager
from tests.support.fakes.github import API
from tests.support.fakes.github_repository import GitHubFake
from tests.support.roadmap_run import REPO, lane_table, serve_over, service_github
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

pytestmark = pytest.mark.usefixtures("keyring_store", "roadmap_bot")

ROWS = frozenset(row.name for row in DEFAULT_DUE_TABLE)
OPEN_LISTING = f"{API}/repos/{REPO}/issues?state=open"


class _Requests:
    """The repository fake, and the row and the URL or argv tail of each request sent to it or
    through the GitHub session. One lock covers the fake, so the lanes send one at a time."""

    def __init__(self, github: GitHubFake) -> None:
        self._github = github
        self._lock = threading.Lock()
        self.sent: list[tuple[str, str]] = []

    def __call__(self, args: list[str], **kwargs: Any) -> Any:
        with self._lock:
            self.sent.append((request_labels()["row"], args[-1]))
            return self._github(args, **kwargs)

    def count(self, resource: str, method: str, status: int | None, labels: dict[str, str]) -> None:
        """Record a request of the GitHub session, and count it as the session does."""
        with self._lock:
            self.sent.append((labels["row"], f"session {method}"))
        count_request(resource, method, status, labels)

    def rows(self) -> set[str]:
        return {row for row, _ in self.sent}

    def open_listing_rows(self) -> list[str]:
        return [row for row, sent in self.sent if sent.startswith(OPEN_LISTING)]


def _reads_one_issue(store: RoadmapStore, **_: Any) -> JobOutcome:
    store.issue(1)
    return JobOutcome()


@pytest.fixture
def requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Requests:
    """The Service's stores open over the repository fake, no row of the table has run, and each
    row reads one issue and needs no clone."""
    sent = _Requests(service_github([]))
    serve_over(tmp_path, monkeypatch, sent, stamped=False)
    stubs = dict.fromkeys(ROWS, _reads_one_issue)
    monkeypatch.setattr(run, "DEFAULT_DUE_TABLE", lane_table(DEFAULT_DUE_TABLE, **stubs))
    monkeypatch.setattr(session_transport, "count_request", sent.count)
    return sent


@pytest.fixture
def service(tmp_path: Path, requests: _Requests) -> Iterator[ServiceManager]:
    """The Service of one repository with every lane that `service_jobs` builds over the stores
    of `requests`, its workers started and no poll loop."""
    idle = IdleRepos()
    manager = ServiceManager(
        config=ServiceConfig(
            repos=[REPO],
            github_app=GitHubAppConfig(app_id=1001, installation_id=42, slug="bot-account"),
            github_requests_per_hour=5000,
        ),
        secrets={},
        jobs=service_jobs(tmp_path / "roadmap", {}, idle.update),
        clock=lambda: datetime.now(UTC),
        sleep_func=asyncio.sleep,
        idle=idle,
    )
    for worker in manager.workers.values():
        worker.start()
    yield manager
    for worker in manager.workers.values():
        worker.stop()
        worker.join(THREAD_HANDOFF_BOUND_SECONDS)


def _one_round(service: ServiceManager, enqueue: Callable[[], object]) -> list[str]:
    """The result of the round of each lane after `enqueue` starts one."""
    enqueue()
    workers = service.workers.values()
    assert wait_until(lambda: all(worker.last_round is not None for worker in workers))
    assert all(worker.wait_active(THREAD_HANDOFF_BOUND_SECONDS) for worker in workers)
    return sorted({worker.last_round.result for worker in workers if worker.last_round})


@pytest.mark.parametrize(
    ("source", "event", "action"), [("poll", "", ""), ("webhook", "issues", "labeled")]
)
def test_no_request_of_a_service_round_counts_as_other(
    service: ServiceManager, requests: _Requests, source: str, event: str, action: str
) -> None:
    """Every lane runs a round with every row due. Each row's read counts under its row, the
    round's own reads under the loop that started it, and the read of the open work under
    `idle_check`. No request counts as `other`."""
    results = _one_round(service, lambda: service.enqueue_trigger(REPO, source, event, action))

    assert (results, sorted(requests.rows() - ROWS)) == (["success"], ["idle_check", source])


def test_one_lane_of_a_repository_reads_its_open_work_in_a_round(
    service: ServiceManager, requests: _Requests
) -> None:
    """All lanes of a repository run a round for one poll, and only the lane of `intake` reads
    the open issues for the idle state of the repository: one read, where each of the 14 lanes
    read it before (#6012)."""
    results = _one_round(service, lambda: service.enqueue_trigger(REPO, "poll", "", ""))

    assert (results, requests.open_listing_rows(), service.idle.is_idle(REPO)) == (
        ["success"],
        ["idle_check"],
        False,
    )
