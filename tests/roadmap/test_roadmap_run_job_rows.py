"""What the alternatives row and the release comments row of the due table do and when they are due
(#981).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.roadmap.run import (
    MODEL_LANE_ROWS,
    STATUS_LANE_ROWS,
    TRIAGE_LANE_ROWS,
    FailureLedger,
    run_due_jobs,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.oci_registry import RegistryFake
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_jobs import due_job_runner
from tests.support.roadmap_run import (
    NOW,
    OPENED,
    POLL_KEY,
    REPO,
    lane_table,
    poll_round,
    stamp_successes,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


run_release_comments_adapter = due_job_runner("release_comments")


def test_the_alternatives_row_follows_refine_and_is_due_every_719_minutes_and_by_no_hint(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """The row is due on a first run, 719 minutes after its last success and not before, and a
    webhook hint that makes intake due makes it due no sooner (#2652)."""
    five_minutes_ago = NOW - timedelta(minutes=5)
    recent = {
        "intake": five_minutes_ago,
        "refine": five_minutes_ago,
        "retitle": five_minutes_ago,
        "stage": five_minutes_ago,
    }

    def ran(batch: dict[tuple[str, str, str], int], **stamps: datetime) -> tuple[str, ...]:
        stamp_successes(tmp_path, **stamps)
        return poll_round(
            seeded_store,
            tmp_path,
            table=lane_table((*TRIAGE_LANE_ROWS, *MODEL_LANE_ROWS)),
            batch=batch,
        )

    first = ran({POLL_KEY: 1})
    too_soon = ran({POLL_KEY: 1}, **recent, alternatives=NOW - timedelta(minutes=718))
    on_time = ran({POLL_KEY: 1}, **recent, alternatives=NOW - timedelta(minutes=719))
    hinted = ran({OPENED: 1}, **recent, alternatives=NOW - timedelta(hours=2))

    assert (first, too_soon, on_time, hinted) == (
        ("intake", "retitle", "stage", "refine", "alternatives"),
        (),
        ("alternatives",),
        ("intake",),
    )


def test_the_dry_run_of_the_cli_lists_the_alternatives_row(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
) -> None:
    """On a first run every row is due, and the CLI's dry run lists the alternatives row last
    (#2652)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    result = cli(["roadmap", "run", "--dry-run", "-R", REPO])

    assert (
        result.exit_code,
        "Due: metrics, implement, stage_ready, release_comments, github_status, cloudflare_status,"
        " pr_conflicts, intake, retitle, stage, refine, alternatives\n" in result.output,
    ) == (0, True)


def test_the_dry_run_of_the_cli_lists_the_read_of_the_newest_issue(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
) -> None:
    """The dry run lists the read of the newest issue after the read of the issue events: both
    judge which jobs are due (#4540)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("COLUMNS", "400")

    output = cli(["roadmap", "run", "--dry-run", "-R", REPO]).output
    events = output.find(f"/repos/{REPO}/issues/events")
    newest = output.find(f"/repos/{REPO}/issues?state=all&sort=created&direction=desc&per_page=10")

    assert (events > -1, newest > events) == (True, True)


RELEASE_COMMENTS_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "release_comments")


def test_the_release_comments_row_calls_no_model_needs_no_clone_and_is_due_every_eleven_minutes() -> (
    None
):
    """It follows stage_ready on the status lane, and it is due on a first run (#2917)."""
    assert (
        RELEASE_COMMENTS_ROW.needs_clone,
        RELEASE_COMMENTS_ROW.first_run_due,
        RELEASE_COMMENTS_ROW.interval,
        "release_comments" in [row.name for row in MODEL_LANE_ROWS],
    ) == (False, True, timedelta(minutes=11), False)


def test_the_release_comments_adapter_comments_a_release_and_keeps_its_ledger(
    process_fake: ProcessFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cluster: FakeCluster,
    web: WebFake,
) -> None:
    """Over the edge fakes of GitHub, the cluster and the registry, a round posts the `Released
    in` comment of a seeded release and writes `release_comments.json` in the directory of the
    repository (#2917)."""
    github = GitHubFake(REPO)
    github.seed_issue(11, "pull", state="closed", body="Closes #101", pull_request=True)
    github.seed_issue(101, "done", state="closed")
    github.seed_release("v1.0.0", "* x ([#11](https://example.com/11))\n", NOW - timedelta(hours=1))
    github.install(process_fake)
    prefix = "ghcr.io/dan-petty/devops-cli"
    digests = {f"{prefix}/service:v1.0.0": "sha256:" + "1" * 64}
    digests[f"{prefix}/runner:v1.0.0"] = "sha256:" + "2" * 64
    web.serve(RegistryFake(digests))
    template = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    template["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["image"] = (
        f"{prefix}/runner@sha256:{'3' * 64}"
    )
    cluster.custom_objects.objects[("batch", "v1", "cronjobs")] = [template]
    cluster.custom_objects.objects[("apps", "v1", "deployments")] = [
        {
            "metadata": {"name": "roadmap-service", "namespace": "devops"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {"name": "service", "image": f"{prefix}/service@sha256:{'1' * 64}"}
                        ]
                    }
                }
            },
        }
    ]
    store = GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))

    run_release_comments_adapter(store, repo=REPO, repo_dir=tmp_path, now=NOW)

    assert github.comments[101][0].startswith("<!-- devops roadmap release v1.0.0 released -->")
    assert (tmp_path / "release_comments.json").is_file()


def test_rounds_with_a_404_on_a_new_release_up_to_the_limit_suspend_no_row(
    process_fake: ProcessFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cluster: FakeCluster,
    web: WebFake,
    seeded_store: InMemoryRoadmapStore,
) -> None:
    """A release of 5 minutes ago has no image yet, so the registry answers HTTP 404. The row
    `release_comments` fails no round, and its record in the ledger of failed rounds stays empty
    (#3507)."""
    github = GitHubFake(REPO)
    github.seed_release("v1.0.0", "* x\n", NOW - timedelta(minutes=5))
    github.install(process_fake)
    prefix = "ghcr.io/dan-petty/devops-cli"
    web.serve(RegistryFake({}))
    template = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    template["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["image"] = (
        f"{prefix}/runner@sha256:{'2' * 64}"
    )
    cluster.custom_objects.objects[("batch", "v1", "cronjobs")] = [template]
    cluster.custom_objects.objects[("apps", "v1", "deployments")] = [
        {
            "metadata": {"name": "roadmap-service", "namespace": "devops"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {"name": "service", "image": f"{prefix}/service@sha256:{'1' * 64}"}
                        ]
                    }
                }
            },
        }
    ]
    failures = FailureLedger()
    store = GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))
    ran: list[tuple[str, ...]] = []

    # A data directory per round has no schedule, so the row is due in each round.
    for step in range(failures.limit):
        ran.append(
            run_due_jobs(
                REPO,
                store,
                batch={POLL_KEY: 1},
                table=lane_table(STATUS_LANE_ROWS, release_comments=run_release_comments_adapter),
                data_dir=tmp_path / str(step),
                now=NOW + timedelta(minutes=step),
                failures=failures,
            )
        )

    assert (
        failures.holds_failure(REPO, "release_comments"),
        [names.count("release_comments") for names in ran],
    ) == (False, [1] * failures.limit)
