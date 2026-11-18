"""The metrics row of the due table: what it reads from its own clone and from GitHub, and what it
sends (#981).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from devops_cli.config.constants import (
    CONST_GITHUB_APP_PRIVATE_KEY_ENV,
    CONST_ROADMAP_LABELS_PATH,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES
from devops_cli.config.settings import RoadmapConfig
from devops_cli.github.item_label_times import ITEM_LABEL_TIMES_FILE
from devops_cli.github.session import reset_github_session
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
    run_due_jobs,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import (
    ItemField,
)
from devops_cli.telemetry.instruments import (
    PROJECT_ITEMS,
    PROJECT_RELEASES,
    PROJECT_STARS,
    PROJECT_TRAFFIC_VIEWS,
    ROADMAP_INBOX_ITEMS,
    ROADMAP_ITEM_AGE,
    ROADMAP_OLDEST_ITEM,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import API, RunnerSession
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

# The labels file of the repository: one label, which the repository holds.
LABELS = "- name: scope/cli\n  color: DCDCD6\n  description: The CLI\n"


@pytest.fixture(scope="module")
def app_key() -> str:
    """The App's private key in PEM form, made for this run, so the session can sign its JWT."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


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
    interval = row.cadence(RoadmapConfig()).interval_minutes if row.cadence else None
    remote = bare_remote(tmp_path)
    for tag in ("v0.1.0", "v0.2.0"):
        git_in(remote, "tag", tag, "main")
    github = GitHubFake(REPO, milestones=[{"number": 26, "title": PLANNED, "state": "open"}])
    github.install(git_fake)
    github.serve_session(web)
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
    seeded_store.seed_file(CONST_ROADMAP_LABELS_PATH, LABELS)
    seeded_store.seed_issue("feat: export", labels=("type/feature",), fields=PLACED)
    seeded_store.seed_issue("A candidate", labels=("type/feature",))
    data_dir = tmp_path / "data"
    with caplog.at_level(logging.WARNING):
        ran = run_due_jobs(
            REPO, seeded_store, table=(row,), data_dir=data_dir, remote_url=str(remote), now=NOW
        )
    clone = data_dir / "roadmap" / "example" / "roadmap" / "clone"
    assert (
        (row.needs_clone, row.first_run_due, interval),
        ran,
        (clone / ".git").is_dir(),
        otlp.points(PROJECT_RELEASES.name),
        otlp.points(PROJECT_ITEMS.name),
        [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING],
    ) == (
        (True, True, DEFAULT_ROADMAP_METRICS_INTERVAL_MINUTES),
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


def _label_event_reads(github: GitHubFake, number: int) -> list[str]:
    """Each read of the label events of issue `number` that the fake answered, by its path."""
    endpoint = f"/issues/{number}/events"
    return [arg for args in github.calls for arg in args if endpoint in arg]


def test_the_metrics_row_keeps_the_label_times_in_the_state_directory_of_its_repository(
    git_fake: GitFake,
    tmp_path: Path,
    web: WebFake,
    git_sim: SimulatedGit,
    otlp: FakeCollector,
) -> None:
    """The row keeps the `updated_at` and the label times of each open Item in
    item-label-times.json of the state directory that holds its schedule.json, so its second
    round reads no label events of an Item whose `updated_at` did not move, and still sends the
    Item's age (#3634)."""
    row = next(row for row in DEFAULT_DUE_TABLE if row.name == "metrics")
    remote = bare_remote(tmp_path)
    github = GitHubFake(
        REPO,
        milestones=[{"number": 26, "title": PLANNED, "state": "open"}],
        events=[
            {
                "event": "labeled",
                "created_at": "2026-10-01T00:00:00Z",
                "actor": {"login": "dan-petty"},
                "label": {"name": "status/ready"},
            }
        ],
    )
    item = 1
    github.seed_issue(item, "ready item", labels=("priority/p2-medium", "status/ready"))
    github.install(git_fake)
    github.serve_session(web)
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
    store = GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))
    data_dir = tmp_path / "data"
    run_due_jobs(REPO, store, table=(row,), data_dir=data_dir, remote_url=str(remote), now=NOW)
    otlp.clear()

    run_due_jobs(
        REPO,
        store,
        table=(row,),
        data_dir=data_dir,
        remote_url=str(remote),
        now=NOW + timedelta(minutes=20),
    )

    record = data_dir / "roadmap" / REPO / ITEM_LABEL_TIMES_FILE
    ages = {attrs["phase"]: value for attrs, value in otlp.points(ROADMAP_ITEM_AGE.name)}
    assert (
        len(_label_event_reads(github, item)),
        record.is_file(),
        ages["ready"] > 0.0,
    ) == (1, True, True)


def test_the_metrics_row_sends_the_age_of_a_blocked_item_and_logs_no_collection_failure(
    process_fake: ProcessFake,
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    web: WebFake,
    otlp: FakeCollector,
) -> None:
    """The metrics row of the Service asks for the item ages (#2919, #5495). A Ready item sends its
    age and its number with the labels `repo` and `phase`, and the row logs no warning from the
    collection."""
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / ".git").mkdir()
    GitHubFake(REPO).install(process_fake)
    seeded_store.seed_file(CONST_ROADMAP_LABELS_PATH, LABELS)
    number = seeded_store.seed_issue("ready item", fields=PLACED)
    ready = seeded_store.item(number)
    assert ready is not None
    seeded_store.set_field(ready, ItemField.STATUS, "Ready")
    with caplog.at_level(logging.WARNING):
        run_metrics_adapter(store=seeded_store, repo=REPO, clone_path=clone)
    ages = {
        attrs["phase"]: (attrs["repo"], value)
        for attrs, value in otlp.points(ROADMAP_ITEM_AGE.name)
    }
    numbers = {attrs["phase"]: value for attrs, value in otlp.points(ROADMAP_OLDEST_ITEM.name)}
    assert (
        ages["ready"][0],
        ages["ready"][1] > 0.0,
        numbers["ready"],
        numbers["planned"],
        [
            record.getMessage()
            for record in caplog.records
            if record.levelno >= logging.WARNING and "collection failed" in record.getMessage()
        ],
    ) == (REPO, True, float(number), 0.0, [])


def test_metrics_adapter_emits_inbox_counts(
    process_fake: ProcessFake,
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    web: WebFake,
    otlp: FakeCollector,
) -> None:
    """The metrics row sends the count of each counted kind of the inbox of its repository, so the
    dashboard shows the counts without a person who runs the command (#2968)."""
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / ".git").mkdir()
    GitHubFake(REPO).install(process_fake)
    seeded_store.seed_file(CONST_ROADMAP_LABELS_PATH, LABELS)
    number = seeded_store.seed_issue("blocked item", fields=PLACED)
    item = seeded_store.item(number)
    assert item is not None
    seeded_store.set_field(item, ItemField.STATUS, "Blocked")

    run_metrics_adapter(store=seeded_store, repo=REPO, clone_path=clone, now=NOW)

    points = {
        attrs["kind"]: (attrs["repo"], value)
        for attrs, value in otlp.points(ROADMAP_INBOX_ITEMS.name)
    }
    assert (points["blocked"], points["refine"], len(points)) == ((REPO, 1.0), (REPO, 0.0), 8)


def test_the_metrics_row_sends_no_inbox_count_when_the_inbox_cannot_be_read(
    process_fake: ProcessFake,
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    web: WebFake,
    otlp: FakeCollector,
) -> None:
    """A repository whose labels file the row cannot read sends no inbox count, and one warning
    names it. The other gauges of the row stay, so a failed section fails no round (#2968)."""
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / ".git").mkdir()
    GitHubFake(REPO).install(process_fake)

    with caplog.at_level(logging.WARNING):
        run_metrics_adapter(store=seeded_store, repo=REPO, clone_path=clone, now=NOW)

    assert (
        otlp.points(ROADMAP_INBOX_ITEMS.name),
        otlp.points(PROJECT_STARS.name),
        [
            record.getMessage()
            for record in caplog.records
            if record.levelno >= logging.WARNING and "inbox count" in record.getMessage()
        ],
    ) == (
        [],
        [({"repo": REPO}, 0.0)],
        [
            f"No inbox count is sent for {REPO} this round, because its inbox could not be "
            f"read: {REPO} has no .github/labels.yml on its default branch."
        ],
    )


def test_the_metrics_row_counts_the_failed_deliveries_of_the_hooks_of_its_repository(
    process_fake: ProcessFake,
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    web: WebFake,
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
    github.serve_session(web)
    GLOBAL_METRICS.clear_metric(CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES)
    seeded_store.seed_file(CONST_ROADMAP_LABELS_PATH, LABELS)

    run_metrics_adapter(store=seeded_store, repo=REPO, clone_path=clone, now=NOW)

    assert (
        GLOBAL_METRICS.get_gauge_value(
            CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES, labels={"repo": REPO, "code": "403"}
        )
        == 2.0
    )


@pytest.mark.parametrize(
    ("traffic_answer", "views", "warnings"),
    [
        pytest.param(None, [({"repo": REPO}, 0.0)], [], id="read"),
        pytest.param(
            (1, "gh: Resource not accessible by integration (HTTP 403)"),
            [],
            [
                f"GitHub refused the traffic of {REPO}: the token has no administration: read. "
                "The process asks for it no more until it restarts."
            ],
            id="refused",
        ),
    ],
)
def test_the_metrics_job_of_the_app_reads_the_traffic_of_the_repository(
    traffic_answer: tuple[int, str] | None,
    views: list[tuple[dict[str, str], float]],
    warnings: list[str],
    app_key: str,
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
    """The installation token of the Service asks for Administration read (#4757), so the round
    reads the four traffic paths and sends the views and the stars with the label of the
    repository. When GitHub refuses the traffic, the round sends the stars and no traffic series,
    and one warning names the permission."""
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / ".git").mkdir()
    github = GitHubFake(REPO, traffic_answer=traffic_answer)
    github.install(git_fake)
    github.serve_session(web)
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    web.respond(
        "POST",
        f"{API}/app/installations/42/access_tokens",
        201,
        {"token": "installation-token", "expires_at": expires_at},
    )
    seeded_store.seed_file(CONST_ROADMAP_LABELS_PATH, LABELS)
    config(
        service={"github_app": {"app_id": 1001, "installation_id": 42, "slug": "devops-roadmap"}}
    )
    monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, app_key)
    reset_github_session()
    with caplog.at_level(logging.WARNING):
        run_metrics_adapter(store=seeded_store, repo=REPO, clone_path=clone)
    assert (
        github.traffic_calls(),
        otlp.points(PROJECT_TRAFFIC_VIEWS.name),
        otlp.points(PROJECT_STARS.name),
        [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING],
    ) == (
        [
            f"repos/{REPO}/traffic/{endpoint}"
            for endpoint in ("views", "clones", "popular/referrers", "popular/paths")
        ],
        views,
        [({"repo": REPO}, 0.0)],
        warnings,
    )
