"""The service that `devops roadmap run` feeds: its lanes, its halt and budget files, and its MCP
mirror (#981).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.ai.mcp.server import roadmap_run
from devops_cli.config.constants import (
    CONST_ROADMAP_RUN_CLONE_DIRNAME,
    CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME,
    CONST_SERVICE_BUDGET_FILENAME,
    CONST_SERVICE_HALT_FILENAME,
    CONST_SERVICE_LANE_MODEL,
    CONST_SERVICE_LANE_STATUS,
    CONST_SERVICE_LANE_TRIAGE,
)
from devops_cli.roadmap.run import (
    MODEL_LANE_ROWS,
    STATUS_LANE_ROWS,
    TRIAGE_LANE_ROWS,
    service_state_dir,
)
from devops_cli.server.service import TriggerBatch, no_round_pause
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import NOW, OPENED, PLACED, REPO

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture
def service_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The settings `devops serve --service` needs to manage REPO as a GitHub App."""
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_REPOS", f'["{REPO}"]')
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_APP_ID", "1001")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_INSTALLATION_ID", "42")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_SLUG", "devops-roadmap")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY", "test-app-private-key")
    monkeypatch.setenv("DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS", f'{{"{REPO}":"secret-1"}}')


@pytest.mark.usefixtures("service_settings")
def test_service_wiring(
    seeded_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    cli: Callable[..., Any],
) -> None:
    """`devops serve --service` passes the three lanes' jobs to create_service_app, with no
    reader of a round pause: no roadmap read has a budget refusal that names one (ADR 0016).
    Each lane's job opens the store and runs its own rows in its own clone (#1532, #1534)."""
    with patch("uvicorn.run") as mock_uvicorn:
        res = cli(["serve", "--service"])
        fastapi_app = mock_uvicorn.call_args[0][0]()

    batch = TriggerBatch(repo=REPO, counts={OPENED: 1}, first_at=NOW, last_at=NOW)
    with patch("devops_cli.roadmap.run.run_due_jobs") as mock_run:
        for lane_job in fastapi_app.state.jobs.values():
            lane_job(batch)

    lanes = [
        (call.args[0], call.kwargs["table"], call.kwargs["clone_dirname"])
        for call in mock_run.call_args_list
    ]
    assert (
        res.exit_code,
        list(fastapi_app.state.jobs),
        fastapi_app.state.pause_until is no_round_pause,
        REPO in roadmap_store_repos,
        lanes,
        [
            [row.name for row in rows]
            for rows in (STATUS_LANE_ROWS, TRIAGE_LANE_ROWS, MODEL_LANE_ROWS)
        ],
    ) == (
        0,
        [CONST_SERVICE_LANE_STATUS, CONST_SERVICE_LANE_TRIAGE, CONST_SERVICE_LANE_MODEL],
        True,
        True,
        [
            (REPO, STATUS_LANE_ROWS, CONST_ROADMAP_RUN_CLONE_DIRNAME),
            (REPO, TRIAGE_LANE_ROWS, CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME),
            (REPO, MODEL_LANE_ROWS, CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME),
        ],
        [
            [
                "metrics",
                "implement",
                "stage_ready",
                "stage",
                "release_comments",
                "github_status",
                "cloudflare_status",
                "pr_conflicts",
            ],
            ["intake"],
            ["retitle", "fix_plan", "refine", "alternatives"],
        ],
    )


@pytest.mark.usefixtures("service_settings")
def test_the_service_that_serve_starts_reads_its_halt_and_budget_from_the_volume(
    cli: Callable[..., Any],
) -> None:
    """`devops serve --service` gives the Service the state directory on its volume. A Service
    that starts there after a halt and after 60 requests in the budget window is still halted,
    and its budget still counts the 60 requests (#2474, #2523)."""
    volume = service_state_dir()
    volume.mkdir(parents=True)
    halt = {"identity": "devops-roadmap[bot]", "repo": REPO, "kind": "GitHubUnauthenticatedError"}
    (volume / CONST_SERVICE_HALT_FILENAME).write_text(json.dumps(halt), encoding="utf-8")
    window = [[(datetime.now(UTC) - timedelta(minutes=5)).isoformat(), 60]]
    (volume / CONST_SERVICE_BUDGET_FILENAME).write_text(json.dumps(window), encoding="utf-8")

    with patch("uvicorn.run") as mock_uvicorn:
        res = cli(["serve", "--service"])
        manager = mock_uvicorn.call_args[0][0]().state.service_manager

    assert (res.exit_code, manager.pause.halted(), manager.budget.spent()) == (0, True, 60)


def test_mcp_mirror_roadmap_run(seeded_store: InMemoryRoadmapStore) -> None:
    """FastMCP roadmap_run returns due tuple, mutates nothing, and calls no stub."""
    seeded_store.seed_issue("An item", fields=PLACED)
    items_before = [it.model_dump() for it in seeded_store.items()]
    writes_before = seeded_store.job_writes()

    due = roadmap_run(repo=REPO)

    assert isinstance(due, str)
    assert [it.model_dump() for it in seeded_store.items()] == items_before
    assert seeded_store.job_writes() == writes_before
