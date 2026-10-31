"""Tests for ServiceManager and RepoWorker status tracking and reporting (#1395)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from devops_cli.config.settings import GitHubAppConfig, ServiceConfig
from devops_cli.server.service import (
    RepoWorker,
    ServiceManager,
    TriggerBatch,
    WorkerRound,
)


def _now() -> datetime:
    return datetime(2026, 10, 31, 12, 0, 0, tzinfo=UTC)


def test_repo_worker_tracks_pending_triggers_and_last_round() -> None:
    current_time = _now()

    def clock() -> datetime:
        return current_time

    executed_batches: list[TriggerBatch] = []

    def job(batch: TriggerBatch) -> None:
        executed_batches.append(batch)

    worker = RepoWorker("org/repo", "status", job, clock)
    assert worker.pending_triggers == 0
    assert worker.last_round is None

    worker.enqueue("test", "push", "")
    assert worker.pending_triggers == 1

    batch = TriggerBatch(
        repo="org/repo",
        counts={("test", "push", ""): 1},
        first_at=current_time,
        last_at=current_time,
    )
    worker._execute_batch(batch)

    assert worker.last_round == WorkerRound(
        start=current_time,
        end=current_time,
        result="success",
    )


def test_repo_worker_records_error_result() -> None:
    current_time = _now()

    def clock() -> datetime:
        return current_time

    def failing_job(_batch: TriggerBatch) -> None:
        raise RuntimeError("boom")

    worker = RepoWorker("org/repo", "status", failing_job, clock)
    batch = TriggerBatch(
        repo="org/repo",
        counts={("test", "push", ""): 1},
        first_at=current_time,
        last_at=current_time,
    )
    worker._execute_batch(batch)

    assert worker.last_round is not None
    assert worker.last_round.result == "error"


def test_service_manager_lane_statuses() -> None:
    current_time = _now()
    config = ServiceConfig(
        repos=["org/repo1", "org/repo2"],
        github_app=GitHubAppConfig(bot_login="test-bot[bot]"),
    )
    manager = ServiceManager(
        config=config,
        secrets={},
        jobs={"status": lambda _batch: None, "model": lambda _batch: None},
        clock=lambda: current_time,
        sleep_func=lambda _s: asyncio.sleep(0),
    )

    all_statuses = manager.lane_statuses()
    assert len(all_statuses) == 4
    assert [(s.repo, s.lane, s.active, s.pending_triggers, s.last_round) for s in all_statuses] == [
        ("org/repo1", "status", False, 0, None),
        ("org/repo1", "model", False, 0, None),
        ("org/repo2", "status", False, 0, None),
        ("org/repo2", "model", False, 0, None),
    ]

    repo1_statuses = manager.lane_statuses("org/repo1")
    assert len(repo1_statuses) == 2
    assert [s.lane for s in repo1_statuses] == ["status", "model"]

    unknown = manager.lane_statuses("unknown/repo")
    assert unknown == []
