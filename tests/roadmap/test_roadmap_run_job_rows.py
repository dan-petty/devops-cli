"""What the alternatives row and the release comments row of the due table do and when they are due
(#981).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
import yaml

from devops_cli.ai.client import LLMClient
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions.roadmap import RoadmapRunError
from devops_cli.roadmap.run import (
    MODEL_LANE_ROWS,
    STATUS_LANE_ROWS,
    TRIAGE_LANE_ROWS,
    FailureLedger,
    JobOutcome,
    run_due_jobs,
)
from devops_cli.roadmap.stage.stage_verify import Verification
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.oci_registry import RegistryFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.llm_stream_fakes import serve_llm
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_fix_plan import needs_fix_plan, valid_changes
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
from tests.support.roadmap_stage import STAGE_REPO

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.roadmap_stage import StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")


run_release_comments_adapter = due_job_runner("release_comments")


def test_the_alternatives_row_follows_refine_and_is_due_every_239_minutes_and_by_no_hint(
    seeded_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """The row is due on a first run, 239 minutes after its last success and not before, and a
    webhook hint that makes intake due makes it due no sooner (#2652)."""
    five_minutes_ago = NOW - timedelta(minutes=5)
    recent = {
        "intake": five_minutes_ago,
        "refine": five_minutes_ago,
        "retitle": five_minutes_ago,
        "stage": five_minutes_ago,
        "fix_plan": five_minutes_ago,
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
    too_soon = ran({POLL_KEY: 1}, **recent, alternatives=NOW - timedelta(minutes=238))
    on_time = ran({POLL_KEY: 1}, **recent, alternatives=NOW - timedelta(minutes=239))
    hinted = ran({OPENED: 1}, **recent, alternatives=NOW - timedelta(hours=2))

    assert (first, too_soon, on_time, hinted) == (
        ("intake", "retitle", "fix_plan", "refine", "alternatives"),
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
        "Due: metrics, implement, plan_drift, watch, stage, open, release_comments, github_status,"
        " cloudflare_status, intake, retitle, fix_plan, refine, alternatives\n" in result.output,
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
    image_repo = "dan-petty/devops-cli"
    github = GitHubFake(image_repo)
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
    store = GitHubRoadmapStore(image_repo, runner=github, session=RunnerSession(github))

    run_release_comments_adapter(store, repo=image_repo, repo_dir=tmp_path, now=NOW)

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
    image_repo = "dan-petty/devops-cli"
    github = GitHubFake(image_repo)
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
    store = GitHubRoadmapStore(image_repo, runner=github, session=RunnerSession(github))
    ran: list[tuple[str, ...]] = []

    # A data directory per round has no schedule, so the row is due in each round.
    for step in range(failures.limit):
        ran.append(
            run_due_jobs(
                image_repo,
                store,
                batch={POLL_KEY: 1},
                table=lane_table(STATUS_LANE_ROWS, release_comments=run_release_comments_adapter),
                data_dir=tmp_path / str(step),
                now=NOW + timedelta(minutes=step),
                failures=failures,
            )
        )

    assert (
        failures.holds_failure(image_repo, "release_comments"),
        [names.count("release_comments") for names in ran],
    ) == (False, [1] * failures.limit)


def test_an_unrelated_repository_posts_released_comments_without_checking_images(
    process_fake: ProcessFake,
    tmp_path: Path,
    cluster: FakeCluster,
    web: WebFake,
) -> None:
    """An unrelated repository skips cluster and GHCR digest checks even when its release is older
    than the grace limit and cluster or registry targets are absent (#7062)."""
    unrelated_repo = "dan-petty/devtools"
    github = GitHubFake(unrelated_repo)
    github.seed_issue(11, "pull", state="closed", body="Closes #101", pull_request=True)
    github.seed_issue(101, "done", state="closed")
    github.seed_release("v1.1.0", "* x ([#11](https://example.com/11))\n", NOW - timedelta(hours=2))
    github.install(process_fake)
    web.serve(RegistryFake({}))
    store = GitHubRoadmapStore(unrelated_repo, runner=github, session=RunnerSession(github))

    run_release_comments_adapter(store, repo=unrelated_repo, repo_dir=tmp_path, now=NOW)

    comments = github.comments[101]
    assert len(comments) == 1
    assert comments[0].startswith("<!-- devops roadmap release v1.1.0 released -->")
    assert web.sent == []
    assert json.loads((tmp_path / "release_comments.json").read_text("utf-8"))["releases"][
        "v1.1.0"
    ] == {"released": True, "live": False}


def test_each_row_runs_in_a_child_span_of_the_round(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    otlp: FakeCollector,
) -> None:
    """Each due row runs in a `service.row <name>` child span of the round with `service.repo`,
    `service.row` and `service.result` (#5415)."""
    from devops_cli.telemetry import trace_span

    retitle_row = next(row for row in MODEL_LANE_ROWS if row.name == "retitle")
    table = lane_table((*TRIAGE_LANE_ROWS, retitle_row))

    with trace_span(f"service.job {REPO}", attributes={"service.repo": REPO}):
        ran = run_due_jobs(
            REPO, seeded_store, batch={POLL_KEY: 1}, table=table, data_dir=tmp_path, now=NOW
        )

    assert ran == ("intake", "retitle")
    (round_span,) = [span for span in otlp.spans if span.name == f"service.job {REPO}"]
    rows = [span for span in otlp.spans if span.name.startswith("service.row ")]
    assert [
        (
            span.name,
            span.parent_span_id,
            span.attributes.get("service.repo"),
            span.attributes.get("service.row"),
            span.attributes.get("service.result"),
        )
        for span in rows
    ] == [
        ("service.row intake", round_span.span_id, REPO, "intake", "success"),
        ("service.row retitle", round_span.span_id, REPO, "retitle", "success"),
    ]


def test_the_fix_plan_row_span_carries_its_mode(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    otlp: FakeCollector,
) -> None:
    """The `service.row fix_plan` span records the configured fix-plan mode in `service.mode`
    (#5415)."""
    from devops_cli.telemetry import trace_span

    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_FIX_PLAN_MODE", "plan")
    fix_plan_row = next(row for row in MODEL_LANE_ROWS if row.name == "fix_plan")
    table = lane_table((fix_plan_row,))

    with trace_span(f"service.job {REPO}", attributes={"service.repo": REPO}):
        run_due_jobs(
            REPO, seeded_store, batch={POLL_KEY: 1}, table=table, data_dir=tmp_path, now=NOW
        )

    (fix_plan_span,) = [span for span in otlp.spans if span.name == "service.row fix_plan"]
    assert fix_plan_span.attributes.get("service.mode") == "plan"


def test_a_failed_row_span_has_status_error(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    otlp: FakeCollector,
) -> None:
    """A due row whose runner raises ends with `STATUS_CODE_ERROR` and `service.result="error"`
    (#5415)."""
    from devops_cli.telemetry import trace_span

    def _boom(**_: Any) -> JobOutcome:
        raise RuntimeError("boom")

    table = lane_table(TRIAGE_LANE_ROWS, intake=_boom)

    with (
        trace_span(f"service.job {REPO}", attributes={"service.repo": REPO}),
        pytest.raises(RoadmapRunError, match=r"intake: boom"),
    ):
        run_due_jobs(
            REPO, seeded_store, batch={POLL_KEY: 1}, table=table, data_dir=tmp_path, now=NOW
        )

    (row_span,) = [span for span in otlp.spans if span.name == "service.row intake"]
    assert (row_span.status_code, row_span.attributes.get("service.result")) == (
        "STATUS_CODE_ERROR",
        "error",
    )


def test_a_row_span_is_the_parent_of_its_model_requests(
    seeded_store: InMemoryRoadmapStore,
    tmp_path: Path,
    web: WebFake,
    otlp: FakeCollector,
) -> None:
    """The active row span is the parent of child `LLMClient` spans, without recording prompt or
    tool content on the row span (#5415)."""
    from devops_cli.telemetry import trace_span

    reply = {
        "model": "gpt-4o",
        "choices": [{"message": {"content": "secret-reply-text"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15},
    }
    serve_llm(web, lambda _request: httpx2.Response(200, json=reply))
    client = LLMClient(
        AIConfig(provider="openai", model="gpt-4o", api_base_url="https://example.com/v1"),
        api_key="sk-test",
        cache_enabled=False,
    )

    def _refine_call(**_: Any) -> JobOutcome:
        client.chat("secret-system-prompt", "secret-user-prompt", use_cache=False)
        return JobOutcome()

    refine_row = next(row for row in MODEL_LANE_ROWS if row.name == "refine")
    table = lane_table((refine_row,), refine=_refine_call)

    with trace_span(f"service.job {REPO}", attributes={"service.repo": REPO}):
        run_due_jobs(
            REPO, seeded_store, batch={POLL_KEY: 1}, table=table, data_dir=tmp_path, now=NOW
        )

    (row_span,) = [span for span in otlp.spans if span.name == "service.row refine"]
    (chat_span,) = [span for span in otlp.spans if span.name == "ai.llm.chat"]
    (dispatch_span,) = [span for span in otlp.spans if span.name == "ai.llm.dispatch"]
    exported_row = json.dumps(row_span.attributes)
    assert (
        chat_span.parent_span_id,
        dispatch_span.parent_span_id,
        dispatch_span.trace_id,
        dispatch_span.attributes.get("gen_ai.usage.input_tokens"),
        "secret-" in exported_row,
    ) == (row_span.span_id, chat_span.span_id, row_span.trace_id, "11", False)


def test_the_implement_runner_root_span_carries_the_row(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    config: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    otlp: FakeCollector,
) -> None:
    """The `implement` runner Job sets `service.row="implement"` on the root span of its CLI trace
    (#5415)."""
    from devops_cli import ai
    from devops_cli.ai.client import factory
    from devops_cli.core import process_hardening
    from devops_cli.roadmap import run
    from devops_cli.roadmap.implement import implement, implement_run
    from devops_cli.roadmap.implement.implement import ImplementPlan
    from devops_cli.roadmap.stage.stage import LeftOut

    config(roadmap={"implement": {"in_runner": True}})
    plan = ImplementPlan(
        repo=REPO,
        left_out=(LeftOut(number=1, title="Item one", reason="not ready"),),
    )
    monkeypatch.delenv("TRACEPARENT", raising=False)
    monkeypatch.setattr(implement_run, "require_runner", lambda _repo: None)
    monkeypatch.setattr(implement_run, "deny_environment_reads", lambda: None)
    monkeypatch.setattr(process_hardening, "deny_environment_reads", lambda: None)
    monkeypatch.setattr(factory, "get_task_model", lambda _task: None)
    monkeypatch.setattr(ai.client, "get_llm_client", lambda **_: None)
    monkeypatch.setattr(implement, "plan_implement", lambda *_, **__: plan)
    monkeypatch.setattr(run, "model_clone", lambda _repo: tmp_path)

    result = cli("roadmap", "implement", "--repo", REPO, "--item", "1", "--confirm")

    assert result.exit_code == 0, result.output
    (root_span,) = [span for span in otlp.spans if span.parent_span_id is None]
    assert root_span.attributes.get("service.row") == "implement"


def test_the_fix_plan_job_root_span_carries_the_row(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    monkeypatch: pytest.MonkeyPatch,
    otlp: FakeCollector,
) -> None:
    """The `fix-plan` Job sets `service.row="fix_plan"` on the root span of its CLI trace
    (#5415)."""
    monkeypatch.delenv("TRACEPARENT", raising=False)
    valid_changes(openspec_fake)
    plan = needs_fix_plan(roadmap_store, stage_repo, github_api)
    model_fake.answer(Verification())

    result = cli(
        "roadmap",
        "step",
        "fix-plan",
        "--repo",
        STAGE_REPO,
        "--source",
        str(stage_repo.clone),
        "--confirm",
        "--item",
        str(plan.number),
    )

    assert result.exit_code == 0, result.output
    (root_span,) = [span for span in otlp.spans if span.parent_span_id is None]
    assert root_span.attributes.get("service.row") == "fix_plan"
