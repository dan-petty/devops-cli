"""The errors of a run: what a failed run keeps and which failures are a configuration error only
(#981).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions import (
    ConfigurationError,
    GitOperationError,
    RoadmapRunError,
    RoadmapStageError,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.run import (
    STATUS_LANE_ROWS,
    TRIAGE_LANE_ROWS,
    JobOutcome,
    build_stub_table,
    run_due_jobs,
    service_job,
)
from devops_cli.server.service import TriggerBatch
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import NOW, OPENED, REPO, SimulatedGit, lane_table, recorded

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_roadmap_run_error_is_configuration_only() -> None:
    """RoadmapRunError.is_configuration_only checks if all cause group exceptions are ConfigurationError (#1365)."""
    cfg1 = ConfigurationError("bad labels 1", key="service.repos")
    cfg2 = ConfigurationError("bad labels 2", key="labels")
    unexpected = RuntimeError("unexpected crash")

    # Group of configuration errors only
    group_cfg = ExceptionGroup("jobs", [cfg1, cfg2])
    err1 = RoadmapRunError("failed", failed_jobs=("intake", "metrics"))
    err1.__cause__ = group_cfg
    assert err1.is_configuration_only is True

    # Group of mixed errors
    group_mixed = ExceptionGroup("jobs", [cfg1, unexpected])
    err2 = RoadmapRunError("failed", failed_jobs=("intake", "metrics"))
    err2.__cause__ = group_mixed
    assert err2.is_configuration_only is False

    # Group of unexpected errors only
    group_unexpected = ExceptionGroup("jobs", [unexpected])
    err3 = RoadmapRunError("failed", failed_jobs=("metrics",))
    err3.__cause__ = group_unexpected
    assert err3.is_configuration_only is False

    # Single ConfigurationError cause
    err4 = RoadmapRunError("failed", failed_jobs=("intake",))
    err4.__cause__ = cfg1
    assert err4.is_configuration_only is True

    # No cause or non-config single cause
    err5 = RoadmapRunError("failed", failed_jobs=("intake",))
    err5.__cause__ = unexpected
    assert err5.is_configuration_only is False

    err6 = RoadmapRunError("failed", failed_jobs=())
    assert err6.is_configuration_only is False


def test_failed_run_keeps_every_job_error_and_clone_error(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    git_sim: SimulatedGit,
) -> None:
    """A failed run keeps every job's error, names intake and metrics, refine with clone failure,
    carries ExceptionGroup cause with PEP 678 notes, is not config-only, and emits no ERROR log (#1365)."""
    data_dir = tmp_path / "data"
    missing_remote = tmp_path / "missing_remote"
    ran: list[str] = []

    def fail_intake(**_: Any) -> JobOutcome:
        raise ConfigurationError("invalid labels.yml", key="labels")

    def stub(name: str) -> Callable[..., JobOutcome]:
        return recorded(ran, name)

    table = build_stub_table(
        {"intake": fail_intake, "metrics": stub("metrics"), "refine": stub("refine")},
        needs_clone=True,
    )

    with caplog.at_level(logging.ERROR, logger="devops_cli.roadmap.run"):
        with pytest.raises(RoadmapRunError) as exc_info:
            run_due_jobs(
                REPO,
                seeded_store,
                batch={OPENED: 1},
                table=table,
                data_dir=data_dir,
                remote_url=str(missing_remote),
                now=NOW,
            )

    err = exc_info.value
    assert err.failed_jobs == ("metrics", "intake", "refine")
    assert "intake: invalid labels.yml" in str(err)
    assert "metrics, refine: git clone " in str(err)
    assert err.is_configuration_only is False

    cause = err.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert len(cause.exceptions) == 2
    notes = {exc.__notes__[0]: exc for exc in cause.exceptions}
    assert "intake" in notes
    assert isinstance(notes["intake"], ConfigurationError)
    assert "metrics, refine" in notes
    assert isinstance(notes["metrics, refine"], GitOperationError)

    # No ERROR records emitted by devops_cli.roadmap.run
    error_records = [
        r
        for r in caplog.records
        if r.name == "devops_cli.roadmap.run" and r.levelno >= logging.ERROR
    ]
    assert error_records == []


def test_failed_run_configuration_only(seeded_store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """A run failing only with ConfigurationError is marked is_configuration_only (#1365)."""
    data_dir = tmp_path / "data"

    def fail_intake(**_: Any) -> JobOutcome:
        raise ConfigurationError("missing labels", key="labels")

    table = build_stub_table({"intake": fail_intake})

    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=table,
            data_dir=data_dir,
            now=NOW,
        )

    err = exc_info.value
    assert err.failed_jobs == ("intake",)
    assert "intake: missing labels" in str(err)
    assert err.is_configuration_only is True
    assert isinstance(err.__cause__, ExceptionGroup)
    assert len(err.__cause__.exceptions) == 1
    assert err.__cause__.exceptions[0].__notes__ == ["intake"]


def test_clone_fails_with_missing_git_binary(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, git_fake: GitFake
) -> None:
    """When git binary is missing, clone rows fail with FileNotFoundError as group member (#1365)."""
    data_dir = tmp_path / "data"
    missing_remote = tmp_path / "missing_remote"
    ran: list[str] = []

    git_fake.answer(
        ["git", "clone"],
        ProcessAnswer(side_effect=FileNotFoundError(2, "No such file or directory: 'git'")),
    )

    def stub(name: str) -> Callable[..., JobOutcome]:
        return recorded(ran, name)

    table = build_stub_table(
        {"metrics": stub("metrics"), "refine": stub("refine")},
        needs_clone=True,
    )

    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=table,
            data_dir=data_dir,
            remote_url=str(missing_remote),
            now=NOW,
        )

    err = exc_info.value
    assert err.failed_jobs == ("metrics", "refine")
    cause = err.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert len(cause.exceptions) == 1
    assert isinstance(cause.exceptions[0], FileNotFoundError)
    assert cause.exceptions[0].__notes__ == ["metrics, refine"]
    assert str(cause.exceptions[0]).splitlines()[0] in str(err)


def test_a_service_round_needs_no_roadmap_file(
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repository with no roadmap file runs its round: service_job opens the store of the
    batch's repository and reads no file (ADR 0016)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    batch = TriggerBatch(repo="example/repo", counts={OPENED: 1}, first_at=NOW, last_at=NOW)
    ran: list[str] = []
    service_job(
        batch,
        table=lane_table(STATUS_LANE_ROWS, metrics=recorded(ran, "metrics")),
        lane="metrics",
    )
    assert (ran, roadmap_store_repos) == (["metrics"], ["example/repo"])


@pytest.mark.usefixtures("roadmap_bot")
def test_service_job_unreadable_github_roadmap_propagates_unchanged(
    unreadable_github_roadmap: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A round of the lane of intake whose read of the changes GitHub cannot answer (HTTP 503)
    raises GitHubOperationError unchanged (#1365, #1534)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    batch = TriggerBatch(repo="example/repo", counts={OPENED: 1}, first_at=NOW, last_at=NOW)

    with pytest.raises(GitHubOperationError) as exc_info:
        service_job(batch, table=TRIAGE_LANE_ROWS, lane="intake")

    assert not isinstance(exc_info.value, ConfigurationError)


def test_the_error_line_of_a_round_names_every_failed_item(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path, git_sim: SimulatedGit
) -> None:
    """The first line of an error is cut, so the numbers of its failed items follow it (#4535)."""

    def fail_stage(**_: Any) -> JobOutcome:
        raise RoadmapStageError(
            "Stage failed for 3 items: #1 (RoadmapStageError): " + "x" * 300 + "\nmore, #2, #3",
            failed_items=[1, 2, 3],
        )

    table = build_stub_table({"stage": fail_stage})

    with pytest.raises(RoadmapRunError) as exc_info:
        run_due_jobs(
            REPO,
            seeded_store,
            batch={OPENED: 1},
            table=table,
            data_dir=tmp_path / "data",
            now=NOW,
        )

    # The first line keeps its first 256 characters: 50 of the text and 206 of the reason.
    assert str(exc_info.value).endswith("): " + "x" * 206 + " (failed items: #1, #2, #3)")
