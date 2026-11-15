"""`devops roadmap follow`: the recorded table of the last run, then the masked tail of the log of
the runner Job pod, from one read of the item (#3076)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from devops_cli.roadmap.implement.implement_trace import ImplementTrace
from devops_cli.roadmap.stores.store import ImplementRecordKey, ItemField
from tests.support.fakes.kubernetes import FakeCluster, pod
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/example"
SECRET = "ghp_ABC1234567890123456789012345678901234567"
TABLE_ROW = "| group 1 | stopped | 1 | 1000/200 | `uv run mypy` |"

Cli = Callable[..., Any]


def _trace() -> ImplementTrace:
    """The trace of one step, whose check failed."""
    trace = ImplementTrace(step="group 1")
    trace.model_call("test-model", 1000, 200, 3.0)
    trace.check("uv run mypy", 1)
    trace.attempt(1, "standard", "check_failed", "mypy failed", repair=True)
    return trace


def _item(store: InMemoryRoadmapStore, *, state: str | None = None) -> int:
    """An item whose job record names runner Job `runner-7` and holds the trace of its run, with
    the Job `state` when it is given."""
    number = store.seed_issue("feat(roadmap): work", fields={ItemField.PRIORITY: "P1-High"})
    item = store.item(number)
    assert item is not None
    marks: dict[ImplementRecordKey, str | None] = {
        ImplementRecordKey.TRACE: _trace().encode(),
        ImplementRecordKey.JOB: "runner-7",
    }
    if state is not None:
        marks[ImplementRecordKey.JOB_STATE] = state
    store.set_marks(item, marks)
    return number


def _follow(cli: Cli, number: int) -> Any:
    return cli("roadmap", "follow", str(number), "--repo", REPO)


def _pod_log(cluster: FakeCluster, log: str) -> None:
    """The one pod of Job `runner-7`, whose log is `log`."""
    cluster.core.answers["list_namespaced_pod"] = [pod("runner-7-abc", namespace="devops")]
    cluster.core.answers["read_namespaced_pod_log"] = log


def test_follow_reads_the_item_once_and_prints_the_live_line(
    cli: Cli, roadmap_store: InMemoryRoadmapStore, cluster: FakeCluster
) -> None:
    running = _item(roadmap_store)
    _pod_log(cluster, f"step group 1\n{SECRET}\n")
    roadmap_store.reads.clear()

    result = _follow(cli, running)

    assert result.exit_code == 0, result.output
    assert TABLE_ROW in result.output
    assert SECRET not in result.output
    assert "<masked-github-token>" in result.output
    assert roadmap_store.reads == ["item"]

    finished = _item(roadmap_store, state="succeeded")
    roadmap_store.reads.clear()
    cluster.core.calls.clear()
    cluster.connects.clear()

    result = _follow(cli, finished)

    assert result.exit_code == 0, result.output
    assert TABLE_ROW in result.output
    assert (cluster.core.calls, cluster.connects) == ([], [])
