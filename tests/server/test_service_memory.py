"""The roadmap Service holds no more memory after 50 rounds than its bounds allow (#4116).

The pod of the Service was OOMKilled at its 1 GiB limit after hours. A round reads GitHub through
the process's one session, which keeps its GET answers for the next conditional GET, and it
exports spans and metrics through the tracer. This test runs the status lane's round 50 times
over the real worker, session and tracer, with the fakes of GitHub and of the collector, and
measures the heap with `MemoryProfiler` (`tracemalloc`). Each round reads one answer of a new URL,
so the session's store is the structure that can grow with the number of rounds.

A store with no byte bound keeps each answer up to its count bound of 64, so the heap at round 50
holds 50 answers and the heap at round 10 holds 10: a growth of 40 MiB. With a byte budget, both
hold the budget.
"""

from __future__ import annotations

import gc
import tracemalloc
from datetime import UTC, datetime

import httpx2
import pytest

from devops_cli.config.constants import CONST_GITHUB_DIFF_MEDIA_TYPE, CONST_SERVICE_LANE_STATUS
from devops_cli.github import session_transport
from devops_cli.github.session import get_github_session
from devops_cli.server.service import RepoWorker, TriggerBatch
from devops_cli.telemetry.memory_profiler import MemoryProfiler
from tests.support.fakes.github import GitHubApiFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

REPO = "example-org/repo1"
ROUNDS = 50
EARLY_ROUND = 10
MIB = 1024 * 1024
BUDGET_BYTES = 8 * MIB
"""The byte budget of the session's stored answers in this test; the default is larger."""
ANSWER_BYTES = MIB
"""One answer: a pull request diff, which has no size bound on GitHub's side."""
SLACK_BYTES = 6 * MIB
"""What the rest of the process may gain in 40 rounds: metric series, the span buffer and the
fakes' request records, which are small and bounded or grow by a few bytes for each round."""


def _heap_bytes() -> int:
    """The traced heap now, after a collection."""
    gc.collect()
    return tracemalloc.get_traced_memory()[0]


def test_the_heap_at_round_50_is_within_the_byte_budget_of_the_heap_at_round_10(
    github_api: GitHubApiFake, otlp: FakeCollector, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The growth between round 10 and round 50 is at most the session's byte budget less what
    round 10 held, plus the slack of the rest of the process, and the failure names the
    allocation sites that grew.

    `raising=False`: the base tree has no byte budget, so the replay of this test on the base
    fails on the growth, not on the missing name.
    """
    monkeypatch.setattr(
        session_transport, "DEFAULT_GH_SESSION_ETAG_CACHE_BYTES", BUDGET_BYTES, raising=False
    )
    body = ("+" * ANSWER_BYTES).encode()
    """One buffer for every answer, so the fake holds the diff once, not once for each route."""
    served = 0

    def round_job(batch: TriggerBatch) -> None:
        get_github_session().rest(
            "GET", f"/repos/{REPO}/pulls/{served}", accept=CONST_GITHUB_DIFF_MEDIA_TYPE
        )

    worker = RepoWorker(
        repo=REPO,
        lane=CONST_SERVICE_LANE_STATUS,
        job_func=round_job,
        clock=lambda: datetime.now(UTC),
    )
    profiler = MemoryProfiler("service-rounds")
    profiler.start()
    worker.start()
    heaps: dict[int, int] = {}
    try:
        for number in range(1, ROUNDS + 1):
            served = number
            github_api.route(
                "GET",
                f"/repos/{REPO}/pulls/{number}",
                httpx2.Response(
                    200,
                    headers={
                        "content-type": f"{CONST_GITHUB_DIFF_MEDIA_TYPE}; charset=utf-8",
                        "etag": f'"{number}"',
                    },
                    content=body,
                ),
            )
            worker.enqueue("webhook", "pull_request", "synchronize")
            assert worker.wait_active(THREAD_HANDOFF_BOUND_SECONDS)
            otlp.clear()  # the fake collector keeps every export it gets; the Service does not
            if number in (EARLY_ROUND, ROUNDS):
                heaps[number] = _heap_bytes()
    finally:
        worker.stop()
        assert worker.join(THREAD_HANDOFF_BOUND_SECONDS)
        report = profiler.stop(top_n=6)

    growth = heaps[ROUNDS] - heaps[EARLY_ROUND]
    sites = [
        f"{item.filename}:{item.line_number} {item.size_human}" for item in report.top_allocations
    ]
    assert len(github_api.sent) == ROUNDS
    assert growth <= SLACK_BYTES, (
        f"The heap grew {growth / MIB:.1f} MiB between round {EARLY_ROUND} and round {ROUNDS}, "
        f"past the {SLACK_BYTES / MIB:.0f} MiB the rest of the process may gain; "
        f"the largest allocation sites: {sites}"
    )
