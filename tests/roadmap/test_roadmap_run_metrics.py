"""The metrics row of the due table: what it reads from its own clone and from GitHub, and what it
sends (#981).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_GITHUB_APP_PRIVATE_KEY_ENV,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES
from devops_cli.github.session import reset_github_session
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    run_due_jobs,
)
from devops_cli.roadmap.stores.store import (
    ItemField,
)
from devops_cli.telemetry.instruments import (
    PROJECT_ITEMS,
    PROJECT_RELEASES,
    PROJECT_STARS,
    PROJECT_TRAFFIC_VIEWS,
    ROADMAP_ITEM_AGE,
    ROADMAP_OLDEST_ITEM,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import API
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import (
    NOW,
    PLACED,
    PLANNED,
    REPO,
    SimulatedGit,
    bare_remote,
    git_in,
    run_metrics_adapter,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


# ── The metrics job ───────────────────────────────────────────────────────────


def test_the_metrics_job_walks_the_version_tags_of_its_own_clone(
    git_fake: GitFake,
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    web: WebFake,
    git_sim: SimulatedGit,
    otlp: FakeCollector,
) -> None:
    """The default table's metrics row clones the repository and walks its version tags there,
    not in the working directory, which in the Service is no git repository (#1358). The gauge
    reads the remote's two past tags, and the job counts the open item of the store it was given
    (#2263). It logs no warning, so every GitHub read it made was answered."""
    row = next(row for row in DEFAULT_DUE_TABLE if row.name == "metrics")
    remote = bare_remote(tmp_path)
    for tag in ("v0.1.0", "v0.2.0"):
        git_in(remote, "tag", tag, "main")
    github = GitHubFake(REPO, milestones=[{"number": 26, "title": PLANNED, "state": "open"}])
    github.install(git_fake)
    web.page(
        f"{API}/user",
        json.dumps({"login": "test-bot"}),
        headers={"content-type": "application/json"},
    )
    web.page(
        f"{API}/users/test-bot",
        json.dumps({"id": 4242, "login": "test-bot"}),
        headers={"content-type": "application/json"},
    )
    seeded_store.seed_issue("feat: export", labels=("type/feature",), fields=PLACED)
    seeded_store.seed_issue("A candidate", labels=("type/feature",))
    data_dir = tmp_path / "data"
    with caplog.at_level(logging.WARNING):
        ran = run_due_jobs(
            REPO, seeded_store, table=(row,), data_dir=data_dir, remote_url=str(remote), now=NOW
        )
    clone = data_dir / "roadmap" / "example" / "roadmap" / "clone"
    assert (
        (row.needs_clone, row.first_run_due, row.interval),
        ran,
        (clone / ".git").is_dir(),
        otlp.points(PROJECT_RELEASES.name),
        otlp.points(PROJECT_ITEMS.name),
        [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING],
    ) == (
        (True, True, timedelta(minutes=DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES)),
        ("metrics",),
        True,
        [({"repo": REPO}, 2.0)],
        [
            (
                {
                    "repo": REPO,
                    "release": "",
                    "state": "open",
                    "type": "feature",
                    "priority": "P2-Medium",
                },
                1.0,
            )
        ],
        [],
    )


def test_the_metrics_row_sends_the_age_of_a_blocked_item_and_logs_no_collection_failure(
    process_fake: ProcessFake,
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    web: WebFake,
    otlp: FakeCollector,
) -> None:
    """The metrics row of the Service asks for the item ages (#2919). A Blocked item sends its age
    and its number with the labels `repo`, `state` and `plan`, and the row logs no warning from
    the collection."""
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / ".git").mkdir()
    GitHubFake(REPO).install(process_fake)
    number = seeded_store.seed_issue("blocked item", fields=PLACED)
    blocked = seeded_store.item(number)
    assert blocked is not None
    seeded_store.set_field(blocked, ItemField.STATUS, "Blocked")
    with caplog.at_level(logging.WARNING):
        run_metrics_adapter(store=seeded_store, repo=REPO, clone_path=clone)
    ages = {
        attrs["plan"]: (attrs["repo"], value)
        for attrs, value in otlp.points(ROADMAP_ITEM_AGE.name)
        if attrs["state"] == "blocked"
    }
    numbers = {
        attrs["plan"]: value
        for attrs, value in otlp.points(ROADMAP_OLDEST_ITEM.name)
        if attrs["state"] == "blocked"
    }
    assert (
        ages["false"][0],
        ages["false"][1] > 0.0,
        numbers["false"],
        numbers["true"],
        [
            record.getMessage()
            for record in caplog.records
            if record.levelno >= logging.WARNING and "collection failed" in record.getMessage()
        ],
    ) == (REPO, True, float(number), 0.0, [])


def test_the_metrics_row_counts_the_failed_deliveries_of_the_hooks_of_its_repository(
    process_fake: ProcessFake,
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    otlp: FakeCollector,
) -> None:
    """A refusal at the Cloudflare edge never gets to the webhook route, so the metrics row reads
    GitHub's record of the deliveries of each hook of its repository, and sets the gauge of the
    Service by code to the deliveries of the last 15 minutes that got no 2xx answer (#5017)."""
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / ".git").mkdir()
    github = GitHubFake(REPO)
    github.seed_hook(
        7,
        [
            {"delivered_at": (NOW - timedelta(minutes=minutes)).isoformat(), "status_code": code}
            for minutes, code in ((1, 403), (2, 202), (4, 403), (30, 403))
        ],
    )
    github.install(process_fake)
    GLOBAL_METRICS.clear_metric(CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES)

    run_metrics_adapter(store=seeded_store, repo=REPO, clone_path=clone, now=NOW)

    assert (
        GLOBAL_METRICS.get_gauge_value(
            CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES, labels={"repo": REPO, "code": "403"}
        )
        == 2.0
    )


def test_the_metrics_job_of_the_app_asks_no_traffic_endpoint(
    config: Callable[..., Path],
    git_fake: GitFake,
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    web: WebFake,
    git_sim: SimulatedGit,
    otlp: FakeCollector,
) -> None:
    """The installation token of the Service has no Administration permission, so GitHub
    answers each traffic path with 403 and the round spends four requests a repository for
    nothing (#2752). The round sends none, logs no warning, and sends the stars and no
    traffic series."""
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / ".git").mkdir()
    github = GitHubFake(
        REPO, traffic_answer=(1, "gh: Resource not accessible by integration (HTTP 403)")
    )
    github.install(git_fake)
    config(
        service={"github_app": {"app_id": 1001, "installation_id": 42, "slug": "devops-roadmap"}}
    )
    monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, "app-key")
    reset_github_session()
    with caplog.at_level(logging.WARNING):
        run_metrics_adapter(store=seeded_store, repo=REPO, clone_path=clone)
    assert (
        github.traffic_calls(),
        otlp.points(PROJECT_TRAFFIC_VIEWS.name),
        otlp.points(PROJECT_STARS.name),
        [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING],
    ) == ([], [], [({"repo": REPO}, 0.0)], [])
