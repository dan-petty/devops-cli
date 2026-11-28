"""Tests that every other roadmap row leaves out an item that left the repository (#7363)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.client.models import AIClientError
from devops_cli.exceptions.git import GitHubNotAnIssueError
from devops_cli.github.metrics import get_item_age_metrics
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.release_title import RELEASE_CONFIG_PATH
from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE, STAGE_TEMPLATE
from devops_cli.k8s.cluster_job_api import ClusterJobs
from devops_cli.roadmap.failure import FailureClass, StepName
from devops_cli.roadmap.implement import implement_submit
from devops_cli.roadmap.implement.implement import (
    ImplementPlan,
    LeftOut,
    NeedsFix,
    parse_implement_filters,
    plan_implement,
)
from devops_cli.roadmap.intake.intake import apply_intake
from devops_cli.roadmap.open_row import run_open_round
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.refine.refine import (
    RefineFailure,
    RefineWriter,
    plan_refine,
    raise_for_failed_items,
    select_candidates,
)
from devops_cli.roadmap.retitle import RetitleReply, apply_retitle, plan_retitle
from devops_cli.roadmap.return_item import apply_return, plan_return
from devops_cli.roadmap.stage.stage import StageFailure, walk_named
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_submit import job_name_of, run_stage_round
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import FIX_PLAN_LABEL, Verification
from devops_cli.roadmap.steps import open as open_mod
from devops_cli.roadmap.steps.fix_plan import FixPlanResult, run_fix_plan
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import FileSnapshotStore, IncrementalListing
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    ItemField,
    StageRecordKey,
)
from devops_cli.roadmap.watch_row import WatchRoundResult, watch_round
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import GitHubApiFake, RunnerSession, github_json
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.model import ModelFake
from tests.support.fakes.openspec import OpenSpecFake
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.job_templates import cronjob_template
from tests.support.roadmap_fix_plan import (
    REPAIRED_WHY,
    finding,
    needs_fix_plan,
    valid_changes,
)
from tests.support.roadmap_implement import merge_plan, seed_staged
from tests.support.roadmap_intake import FakeModel as FakeIntakeModel
from tests.support.roadmap_intake import Roadmap as IntakeRoadmap
from tests.support.roadmap_refine import PLACED, READY
from tests.support.roadmap_stage import (
    GONE,
    STAGE_REPO,
    StageRepo,
    later_review,
    seed_stageable,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = STAGE_REPO
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
ONE = "#%d is no issue of %s now. The store leaves it out."
CRONJOBS = ("batch", "v1", "cronjobs")


def _lines_for(caplog: pytest.LogCaptureFixture, number: int) -> list[str]:
    return [r.getMessage() for r in caplog.records if f"#{number} " in r.getMessage()]


def _commit_on_branch(repo: StageRepo, branch: str, path: str, text: str) -> str:
    repo.git("switch", "-q", "-c", branch)
    target = repo.clone / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", f"add {path}")
    repo.git("push", "-q", "origin", branch)
    repo.git("switch", "-q", "main")
    return repo.git("rev-parse", branch)


# ── Error classes for an item that left ───────────────────────────────────────


def test_implement_submit_fresh_raises_github_not_an_issue_not_lookup_error() -> None:
    """`implement_submit._fresh` and `GitHubNotAnIssueError.require_issue` enforce the number (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    gone = store.seed_issue("fix(ci): left", fields={ItemField.PRIORITY: "P1-High"})
    store.leave(gone)

    with pytest.raises(GitHubNotAnIssueError) as err:
        implement_submit._fresh(store, gone)

    assert err.value.number == gone
    err.value.require_issue(gone)
    with pytest.raises(GitHubNotAnIssueError) as mismatch:
        err.value.require_issue(gone + 1)
    assert mismatch.value.number == gone


def test_return_item_raises_github_not_an_issue_for_missing_issue() -> None:
    """`plan_return` and `apply_return` raise `GitHubNotAnIssueError` when the issue left (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    gone = store.seed_issue("fix(ci): left plan", fields={ItemField.PRIORITY: "P1-High"})
    gone_apply = store.seed_issue("fix(ci): left apply", fields={ItemField.PRIORITY: "P1-High"})
    store.leave(gone)

    with pytest.raises(GitHubNotAnIssueError) as err:
        plan_return(store, gone, "Evidence.", REPO)
    assert err.value.number == gone

    planned = plan_return(store, gone_apply, "Evidence.", REPO)
    store.leave(gone_apply)
    with pytest.raises(GitHubNotAnIssueError) as apply_err:
        apply_return(store, planned)
    assert apply_err.value.number == gone_apply


# ── implement row ─────────────────────────────────────────────────────────────


def test_implement_row_skips_item_that_left_and_continues(
    stage_repo: StageRepo,
    cluster: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`plan_implement`, `_report_ended`, `_note_needs_fix`, and `_submit_selected_targets` skip an
    item that left and continue with other items (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    gone = store.seed_issue(
        "fix(ci): stopped left",
        labels=("priority/p1-high", "type/bug", "effort/low", "approved"),
        fields={
            ItemField.STATUS: "Planned",
            ItemField.PRIORITY: "P1-High",
            ItemField.EFFORT: "Low",
        },
    )
    stay = seed_staged(store, status="Planned")
    gone_submit = seed_staged(store, status="Planned")
    gone2 = store.seed_issue(
        "fix(ci): report gone",
        labels=("priority/p1-high", "type/bug", "approved"),
        fields={
            ItemField.STATUS: "Planned",
            ItemField.PRIORITY: "P1-High",
            ItemField.EFFORT: "Low",
        },
    )
    gone3 = store.seed_issue(
        "fix(ci): fix plan gone",
        labels=("priority/p1-high", "type/bug", "approved"),
        fields={
            ItemField.STATUS: "Ready",
            ItemField.PRIORITY: "P1-High",
            ItemField.EFFORT: "Low",
        },
    )
    gone_item = store.item(gone)
    stay_item = store.item(stay)
    gs_item = store.item(gone_submit)
    g2 = store.item(gone2)
    g3 = store.item(gone3)
    assert gone_item is not None
    assert stay_item is not None
    assert gs_item is not None
    assert g2 is not None
    assert g3 is not None
    store.set_marks(
        gone_item,
        {
            ImplementRecordKey.STOPPED: "tests",
            ImplementRecordKey.JOB: "devops-cli-runner-gone",
        },
    )
    store.set_marks(g2, {ImplementRecordKey.JOB: "devops-cli-runner-report-gone"})
    store.set_marks(g3, {ImplementRecordKey.NEEDS_FIX: "99"})
    merge_plan(stage_repo, gone)
    merge_plan(stage_repo, stay)
    merge_plan(stage_repo, gone_submit)
    planned = PlannedChanges(
        "main",
        {
            gone: f"{gone}-the-job-drops-a-comment",
            stay: f"{stay}-the-job-drops-a-comment",
            gone_submit: f"{gone_submit}-the-job-drops-a-comment",
        },
        {},
    )
    plan_gs = plan_implement(
        store,
        repo=REPO,
        source=stage_repo.clone,
        filters=parse_implement_filters(()),
        item_number=gone_submit,
        planned=planned,
        remote_heads="",
    )
    orig_comments = store.comments_on

    def _leave_on_retry_comment(number: int) -> list[Any]:
        if number == gone:
            store.leave(gone)
        return orig_comments(number)

    with caplog.at_level(logging.WARNING):
        # Leave inside `retry_asked_on` -> `comments_on` so `_named` catches `GitHubNotAnIssueError`.
        with monkeypatch.context() as m:
            m.setattr(store, "comments_on", _leave_on_retry_comment)
            plan_named = plan_implement(
                store,
                repo=REPO,
                source=stage_repo.clone,
                filters=parse_implement_filters(()),
                item_number=gone,
                planned=planned,
                remote_heads="",
            )
        plan = plan_implement(
            store,
            repo=REPO,
            source=stage_repo.clone,
            filters=parse_implement_filters(()),
            planned=planned,
            remote_heads="",
        )
        store.leave(gone2)
        jobs = ClusterJobs()
        reported = implement_submit._report_ended(store, jobs, {}, REPO)
        cronjob = cronjob_template(RUNNER_TEMPLATE)
        cluster.custom_objects.objects[CRONJOBS] = [cronjob]
        orig_set_field = store.set_field

        def _leave_on_submit(
            item: Any, field: Any, value: Any, *, marks: Any = None, **kwargs: Any
        ) -> Any:
            if item.number == gone_submit and field is ItemField.OWNER:
                store.leave(gone_submit)
            return orig_set_field(item, field, value, marks=marks, **kwargs)

        with monkeypatch.context() as m:
            m.setattr(store, "set_field", _leave_on_submit)
            created, _ = implement_submit._submit_selected_targets(
                store,
                jobs,
                REPO,
                [*plan_gs.selected, *plan.selected],
                "example-roadmap",
                stage_repo.clone,
                planned,
                None,
            )
        orig_set_marks = store.set_marks

        def _leave_on_needs_fix(item: Any, marks: Any, **kwargs: Any) -> None:
            if item.number == gone3 and ImplementRecordKey.NEEDS_FIX in marks:
                store.leave(gone3)
            orig_set_marks(item, marks, **kwargs)

        with monkeypatch.context() as m:
            m.setattr(store, "set_marks", _leave_on_needs_fix)
            noted = implement_submit._note_needs_fix(
                store,
                ImplementPlan(
                    REPO,
                    needs_fix=(NeedsFix(g3, 88),),
                    left_out=(LeftOut(gone3, "done", g3.title),),
                ),
            )
        # Also test clearing `NEEDS_FIX` on an item that leaves during clear.
        gone_clear = store.seed_issue(
            "fix(ci): clear fix plan gone",
            labels=("priority/p1-high", "type/bug", "approved"),
            fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
        )
        gc_item = store.item(gone_clear)
        assert gc_item is not None
        store.set_marks(gc_item, {ImplementRecordKey.NEEDS_FIX: "77"})

        def _leave_on_clear(item: Any, marks: Any, **kwargs: Any) -> None:
            if item.number == gone_clear and ImplementRecordKey.NEEDS_FIX in marks:
                store.leave(gone_clear)
            orig_set_marks(item, marks, **kwargs)

        with monkeypatch.context() as m:
            m.setattr(store, "set_marks", _leave_on_clear)
            cleared = implement_submit._note_needs_fix(
                store,
                ImplementPlan(
                    REPO,
                    needs_fix=(),
                    left_out=(LeftOut(gone_clear, "done", gc_item.title),),
                ),
            )
        del cleared

    assert (
        plan_named.selected,
        [t.item.number for t in plan.selected],
        reported,
        len(created),
        noted,
        [
            w
            for w in store._roadmap.job_writes
            if w.number == gone and w.key == ImplementRecordKey.FAILURE.value
        ],
    ) == ((), [stay], (), 1, (), [])
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]
    assert _lines_for(caplog, gone2) == [ONE % (gone2, REPO)]
    assert _lines_for(caplog, gone3) == [ONE % (gone3, REPO)]
    assert _lines_for(caplog, gone_submit) == [ONE % (gone_submit, REPO)]
    assert _lines_for(caplog, gone_clear) == [ONE % (gone_clear, REPO)]


# ── stage row ─────────────────────────────────────────────────────────────────


def test_stage_row_skips_item_that_left_and_continues(
    stage_repo: StageRepo,
    cluster: FakeCluster,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`run_stage_round`, `walk_named`, and `_record_failures` skip left items (#7363)."""
    from devops_cli.roadmap.stage import stage as stage_mod

    config(roadmap={"stage": {"jobs": 2}})
    store = InMemoryRoadmapStore(repo=REPO)
    gone = seed_stageable(store)
    stay = seed_stageable(store)
    gone_fail = store.seed_issue("fix(ci): fail gone", fields={ItemField.PRIORITY: "P1-High"})
    gone_walk = store.seed_issue("fix(ci): walk gone", fields={ItemField.PRIORITY: "P1-High"})
    gone_rec = store.seed_issue("fix(ci): recover gone", fields={ItemField.PRIORITY: "P1-High"})
    github_api.route("GET", f"/repos/{REPO}/pulls?state=open&per_page=100", github_json([]))
    cronjob = cronjob_template(STAGE_TEMPLATE)
    cluster.custom_objects.objects[CRONJOBS] = [cronjob]
    jobs = ClusterJobs()
    gone_item = store.item(gone)
    stay_item = store.item(stay)
    gf_item = store.item(gone_fail)
    gw_item = store.item(gone_walk)
    gr_item = store.item(gone_rec)
    assert gone_item is not None
    assert stay_item is not None
    assert gf_item is not None
    assert gw_item is not None
    assert gr_item is not None
    store.set_field(
        gr_item,
        ItemField.OWNER,
        "Service",
        marks={StageRecordKey.JOB: job_name_of(REPO, gr_item)},
    )
    orig_set_field = store.set_field

    def _fail_gone_hooks(
        item: Any, field: Any, value: Any, *, marks: Any = None, **kwargs: Any
    ) -> Any:
        if (
            item.number == gone
            and field is ItemField.OWNER
            and marks
            and StageRecordKey.JOB in marks
        ):
            store.leave(gone)
        if item.number == gone_rec and marks and StageRecordKey.JOB in marks:
            store.leave(gone_rec)
        return orig_set_field(item, field, value, marks=marks, **kwargs)

    def _walk_judge(it: Any) -> int | str:
        if it.number == gone_walk:
            store.leave(gone_walk)
            store.set_marks(it, {StageRecordKey.FAILED_CLASS: "provider"})
        return it.number

    with caplog.at_level(logging.WARNING):
        with monkeypatch.context() as m:
            m.setattr(store, "set_field", _fail_gone_hooks)
            result = run_stage_round(store, repo=REPO, source=stage_repo.clone, jobs=jobs, now=NOW)
        walked = walk_named([gw_item, stay_item], _walk_judge, limit=2)
        store.leave(gone_fail)
        stage_mod._record_failures(
            store,
            [
                StageFailure(
                    gone_fail,
                    "left",
                    "DevOpsCLIError",
                    "boom",
                    gf_item,
                    failure_class=FailureClass.PROVIDER,
                    step=StepName.APPLY,
                ),
                StageFailure(
                    stay,
                    "ok",
                    "DevOpsCLIError",
                    "boom",
                    stay_item,
                    failure_class=FailureClass.PROVIDER,
                    step=StepName.APPLY,
                ),
            ],
            NOW,
            repo=REPO,
        )

    assert (
        result.created,
        walked.taken,
        any(
            w.number == gone and w.key == StageRecordKey.FAILED_CLASS.value
            for w in store._roadmap.job_writes
        ),
        any(
            w.number == gone_fail and w.key == StageRecordKey.FAILED_CLASS.value
            for w in store._roadmap.job_writes
        ),
        (store.item(stay) or stay_item).job_record.get(StageRecordKey.FAILED_CLASS),
    ) == (
        (job_name_of(REPO, stay_item),),
        (stay,),
        False,
        False,
        FailureClass.PROVIDER.value,
    )
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]
    assert _lines_for(caplog, gone_fail) == [ONE % (gone_fail, REPO)]
    assert _lines_for(caplog, gone_walk) == [ONE % (gone_walk, REPO)]
    assert _lines_for(caplog, gone_rec) == [ONE % (gone_rec, REPO)]


# ── watch row ─────────────────────────────────────────────────────────────────


def test_watch_row_skips_item_that_left_and_continues(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    tmp_path: Path,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`watch_round` skips left items across closed plans, GraphQL nodes, and REST fallback (#7363)."""
    config(roadmap={"fix_checks": {"mode": "off"}})
    api, _ = github_api_and_gh
    store = InMemoryRoadmapStore(repo=REPO)
    gone = store.seed_issue(
        "fix(ci): watch gone",
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    stay = store.seed_issue(
        "fix(ci): watch stay",
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    gone_gql = store.seed_issue(
        "fix(ci): watch gql gone",
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    gone_rest = store.seed_issue(
        "fix(ci): watch rest gone",
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    gone_rest_open = store.seed_issue(
        "fix(ci): watch rest open gone",
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    pr_gql = store.seed_pull(f"fix: gql #{gone_gql}", head_ref=f"fix/{gone_gql}-gql")
    pr_rest_open = store.seed_pull(
        f"fix: rest #{gone_rest_open}", head_ref=f"fix/{gone_rest_open}-rest-open"
    )
    for num in (gone, stay, gone_gql, gone_rest, gone_rest_open):
        it = store.item(num)
        assert it is not None
        store.set_field(it, ItemField.STATUS, "Ready")
    gone_item = store.item(gone)
    stay_item = store.item(stay)
    gql_item = store.item(gone_gql)
    rest_item = store.item(gone_rest)
    ro_item = store.item(gone_rest_open)
    assert gone_item is not None
    assert stay_item is not None
    assert gql_item is not None
    assert rest_item is not None
    assert ro_item is not None
    store.set_marks(
        gone_item, {StageRecordKey.PR: "101", StageRecordKey.BRANCH: f"fix/{gone}-gone"}
    )
    store.set_marks(
        stay_item, {StageRecordKey.PR: "102", StageRecordKey.BRANCH: f"fix/{stay}-stay"}
    )
    store.set_marks(
        gql_item,
        {
            ImplementRecordKey.PR: str(pr_gql),
            ImplementRecordKey.RESULT: "drafted",
        },
    )
    store.set_marks(
        ro_item,
        {
            ImplementRecordKey.PR: str(pr_rest_open),
            ImplementRecordKey.RESULT: "drafted",
        },
    )
    head_fail = "1" * 40
    # Use isDraft=True with a non-repairable check failure so DueStep.STOP triggers
    # `_stop_unowned_draft` -> `store.comment(item.number, ...)`, raising inside `_evaluate_pull`.
    gql_node = {
        "number": pr_gql,
        "title": f"fix: gql #{gone_gql}",
        "body": f"Closes #{gone_gql}",
        "isDraft": True,
        "labels": {"nodes": []},
        "mergeable": "MERGEABLE",
        "headRefOid": head_fail,
        "headRefName": f"fix/{gone_gql}-gql",
        "baseRefName": "main",
        "author": {"login": "app[bot]"},
        "commits": {
            "nodes": [
                {
                    "commit": {
                        "oid": head_fail,
                        "message": "fix",
                        "statusCheckRollup": {
                            "state": "FAILURE",
                            "contexts": {
                                "nodes": [
                                    {
                                        "__typename": "CheckRun",
                                        "name": "Static Analysis",
                                        "status": "COMPLETED",
                                        "conclusion": "FAILURE",
                                    }
                                ]
                            },
                        },
                    }
                }
            ]
        },
    }
    api.route(
        "POST",
        "/graphql",
        github_json(
            {
                "data": {
                    "repository": {
                        "pullRequests": {
                            "nodes": [gql_node],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        ),
    )
    for pr_num, branch in (
        (101, f"fix/{gone}-gone"),
        (102, f"fix/{stay}-stay"),
        (104, f"fix/{gone_rest}-rest"),
    ):
        api.route(
            "GET",
            f"/repos/{REPO}/pulls/{pr_num}",
            github_json(
                {
                    "number": pr_num,
                    "title": f"docs(spec): plan #{pr_num - 100}",
                    "state": "closed",
                    "draft": False,
                    "merged": True,
                    "mergeable": True,
                    "mergeable_state": "clean",
                    "head": {"ref": branch, "sha": "a" * 40},
                    "base": {"ref": "main"},
                    "labels": [],
                    "user": {"login": "app[bot]"},
                }
            ),
        )
    for pr_num, target, branch in (
        (pr_gql, gone_gql, f"fix/{gone_gql}-gql"),
        (pr_rest_open, gone_rest_open, f"fix/{gone_rest_open}-rest-open"),
    ):
        api.route(
            "GET",
            f"/repos/{REPO}/pulls/{pr_num}",
            github_json(
                {
                    "number": pr_num,
                    "title": f"fix: rest #{target}",
                    "state": "open",
                    "draft": True,
                    "merged": False,
                    "mergeable": True,
                    "mergeable_state": "clean",
                    "body": f"Closes #{target}",
                    "head": {"ref": branch, "sha": head_fail},
                    "base": {"ref": "main", "repo": {"default_branch": "main"}},
                    "labels": [],
                    "user": {"login": "app[bot]"},
                }
            ),
        )
    api.route(
        "GET",
        f"/repos/{REPO}/commits/{head_fail}/check-runs?per_page=100",
        github_json(
            {
                "check_runs": [
                    {"name": "Static Analysis", "status": "completed", "conclusion": "failure"}
                ]
            }
        ),
    )
    orig_set_marks = store.set_marks
    orig_comment = store.comment

    def _leave_closed_gql(item: Any, marks: Any, **kwargs: Any) -> None:
        if item.number == gone and StageRecordKey.READY in marks:
            store.leave(gone)
        orig_set_marks(item, marks, **kwargs)

    def _leave_on_stop_comment(number: int, body: str) -> Any:
        if number in {gone_gql, gone_rest_open}:
            store.leave(number)
        return orig_comment(number, body)

    def _leave_on_rest_closed(item: Any, marks: Any, **kwargs: Any) -> None:
        if item.number == gone_rest and StageRecordKey.READY in marks:
            store.leave(gone_rest)
        orig_set_marks(item, marks, **kwargs)

    with caplog.at_level(logging.WARNING):
        with monkeypatch.context() as m:
            m.setattr(store, "set_marks", _leave_closed_gql)
            m.setattr(store, "comment", _leave_on_stop_comment)
            res: WatchRoundResult = watch_round(
                store, repo=REPO, ledger_path=tmp_path / "watch.json", now=NOW
            )
        store.set_marks(
            rest_item, {StageRecordKey.PR: "104", StageRecordKey.BRANCH: f"fix/{gone_rest}-rest"}
        )
        get_github_rate_limiter().update_quota(
            "graphql", remaining=0, limit=5000, reset_epoch=time.time() + 600.0
        )
        try:
            with monkeypatch.context() as m:
                m.setattr(store, "set_marks", _leave_on_rest_closed)
                m.setattr(store, "comment", _leave_on_stop_comment)
                rest_res = watch_round(
                    store, repo=REPO, ledger_path=tmp_path / "watch-rest.json", now=NOW
                )
        finally:
            get_github_rate_limiter().update_quota(
                "graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
            )

    stay_after = store.item(stay)
    assert (
        res.watched,
        rest_res.watched,
        stay_after is not None and stay_after.status == "Planned",
        any(
            w.number in {gone, gone_rest} and w.key == StageRecordKey.READY.value
            for w in store._roadmap.job_writes
        ),
    ) == (1, 1, True, False)
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]
    assert _lines_for(caplog, gone_gql) == [ONE % (gone_gql, REPO)]
    assert _lines_for(caplog, gone_rest) == [ONE % (gone_rest, REPO)]
    assert _lines_for(caplog, gone_rest_open) == [ONE % (gone_rest_open, REPO)]


# ── open row ──────────────────────────────────────────────────────────────────


def test_open_row_and_open_steps_skip_item_that_left_and_continue(
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`run_open_round` and `open` mark/status helpers leave out an item that left (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    store.seed_file(
        ".github/labels.yml",
        '- name: "scope/ci"\n  color: "ededed"\n- name: "type/bug"\n  color: "ededed"\n',
        ref="main",
    )
    store.seed_file(
        RELEASE_CONFIG_PATH, Path(RELEASE_CONFIG_PATH).read_text(encoding="utf-8"), ref="main"
    )
    gone = store.seed_issue("fix(ci): open gone", fields={ItemField.PRIORITY: "P1-High"})
    gone_sync = store.seed_issue("fix(ci): open sync gone", fields={ItemField.PRIORITY: "P1-High"})
    stay = store.seed_issue("fix(ci): open stay", fields={ItemField.PRIORITY: "P1-High"})
    gone_item = store.item(gone)
    gs_item = store.item(gone_sync)
    stay_item = store.item(stay)
    assert gone_item is not None
    assert gs_item is not None
    assert stay_item is not None
    store.set_field(gs_item, ItemField.STATUS, "Planned")
    b_gone = f"fix/{gone}-open-gone"
    b_stay = f"fix/{stay}-open-stay"
    store.set_marks(gone_item, {ImplementRecordKey.BRANCH: b_gone})
    store.set_marks(stay_item, {ImplementRecordKey.BRANCH: b_stay})
    sha_gone = _commit_on_branch(stage_repo, b_gone, f"src/gone_{gone}.py", "X = 1\n")
    sha_stay = _commit_on_branch(stage_repo, b_stay, f"src/stay_{stay}.py", "Y = 2\n")
    for sha, mod_path in ((sha_gone, f"src/gone_{gone}.py"), (sha_stay, f"src/stay_{stay}.py")):
        github_api.route("GET", f"/repos/{REPO}/commits/{sha}/pulls?per_page=100", github_json([]))
        github_api.route(
            "GET",
            f"/repos/{REPO}/compare/main...{sha}?per_page=1",
            github_json(
                {
                    "merge_base_commit": {"sha": "base"},
                    "files": [{"filename": mod_path, "status": "added"}],
                }
            ),
        )
    for pr_num, branch in ((201, b_gone), (202, b_stay)):
        github_api.route(
            "GET",
            f"/repos/{REPO}/pulls?head=example:{branch}&state=open",
            github_json([]),
        )
        github_api.route(
            "POST",
            f"/repos/{REPO}/pulls/{pr_num}/requested_reviewers",
            github_json({"requested_reviewers": [{"login": "example"}]}),
        )
    github_api.route(
        "POST",
        f"/repos/{REPO}/pulls",
        github_json(
            {"number": 202, "html_url": f"https://github.com/{REPO}/pull/202"},
            status=201,
        ),
    )

    orig_set_marks = store.set_marks
    orig_set_field = store.set_field

    def _leave_on_mark(item: Any, marks: Any, **kwargs: Any) -> None:
        if item.number == gone and ImplementRecordKey.PR in marks:
            store.leave(gone)
        orig_set_marks(item, marks, **kwargs)

    def _leave_on_sync(item: Any, field: Any, value: Any, **kwargs: Any) -> Any:
        if item.number == gone_sync and field is ItemField.STATUS:
            store.leave(gone_sync)
        return orig_set_field(item, field, value, **kwargs)

    with caplog.at_level(logging.WARNING):
        with monkeypatch.context() as m:
            m.setattr(store, "set_marks", _leave_on_mark)
            open_mod._record_pr_marks(store, gone, "delivery", 201, b_gone)
        with monkeypatch.context() as m:
            m.setattr(store, "set_field", _leave_on_sync)
            open_mod._sync_status(store, gone_sync, "delivery")
        res = run_open_round(store, repo=REPO, source=stage_repo.clone, mode="on", base="main")

    assert (
        res.opened,
        res.failed,
        any(
            w.number in {gone, gone_sync} and w.key == ImplementRecordKey.FAILURE.value
            for w in store._roadmap.job_writes
        ),
    ) == (
        [202],
        [],
        False,
    )
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]
    assert _lines_for(caplog, gone_sync) == [ONE % (gone_sync, REPO)]


# ── refine row ────────────────────────────────────────────────────────────────


def test_refine_row_skips_item_that_left_and_continues(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`select_candidates`, `plan_refine`, and `RefineWriter` skip items that left (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    store.seed_visibility(is_private=True)
    gone_sel = store.seed_issue(
        "fix(ci): refine select gone",
        fields={**PLACED, ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    gone_mid = store.seed_issue(
        "fix(ci): refine mid gone",
        fields={**PLACED, ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )
    gone_settle = store.seed_issue(
        "fix(ci): refine settle gone",
        fields={**PLACED, ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )
    stay = store.seed_issue(
        "fix(ci): refine stay",
        fields={**PLACED, ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )
    # Mark `gone_sel` approved so `_refinable` enters `comments_on` on a Ready item.
    gs_sel_item = store.item(gone_sel)
    assert gs_sel_item is not None
    store.set_field(gs_sel_item, ItemField.STATUS, "Ready")
    store.seed_comment(gone_sel, "owner reply")
    gs_item = store.item(gone_settle)
    assert gs_item is not None
    orig_comments = store.comments_on
    orig_item = store.item

    def _leave_on_comments(number: int) -> list[Any]:
        if number == gone_sel:
            store.leave(gone_sel)
        return orig_comments(number)

    def _leave_during_refine_item(number: int, *, fresh: bool = False) -> Any:
        if number == gone_mid and fresh:
            store.leave(gone_mid)
        return orig_item(number, fresh=fresh)

    model_fake.answer(READY)
    writer = RefineWriter(store, REPO)

    with caplog.at_level(logging.WARNING):
        with monkeypatch.context() as m:
            m.setattr(store, "comments_on", _leave_on_comments)
            selected, _ = select_candidates(store, limit=5)
        store.seed_comment(gone_mid, "owner note")

        def _leave_mid_comments(number: int) -> list[Any]:
            if number == gone_mid:
                store.leave(gone_mid)
            return orig_comments(number)

        with monkeypatch.context() as m:
            m.setattr(store, "item", _leave_during_refine_item)
            m.setattr(store, "comments_on", _leave_mid_comments)
            plan = plan_refine(
                store,
                repo=REPO,
                source=stage_repo.clone,
                limit=5,
                writer=writer,
            )
        store.leave(gone_settle)
        writer.settle(RefineFailure.of(gs_item, AIClientError("boom")))
        raise_for_failed_items(plan, writer.readied_count)

    assert (
        gone_sel not in [i.number for i in selected],
        [r.item.number for r in plan.refined_items],
        plan.failed_items,
        writer.failed_count,
    ) == (True, [gone_settle, stay], [], 0)
    assert _lines_for(caplog, gone_sel) == [ONE % (gone_sel, REPO)]
    assert _lines_for(caplog, gone_mid) == [ONE % (gone_mid, REPO)]
    assert _lines_for(caplog, gone_settle) == [ONE % (gone_settle, REPO)]


# ── retitle row ───────────────────────────────────────────────────────────────


def test_retitle_row_skips_item_that_left_and_continues(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`plan_retitle` and `apply_retitle` leave out items that left and continue (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    long_title = "fix(roadmap): " + "very long summary word " * 5
    gone_plan = store.seed_issue(long_title, fields={ItemField.PRIORITY: "P1-High"})
    gone_apply = store.seed_issue(long_title, fields={ItemField.PRIORITY: "P1-High"})
    gone_skip = store.seed_issue(
        "unlisted(roadmap): " + "very long summary word " * 5,
        fields={ItemField.PRIORITY: "P1-High"},
    )
    stay = store.seed_issue(long_title, fields={ItemField.PRIORITY: "P1-High"})
    orig_comments = store.comments_on
    orig_set_title = store.set_title

    class _RetitleModel:
        def summarize(self, _prompt: str) -> RetitleReply:
            return RetitleReply(summary="shortened summary of item")

    def _leave_on_comments(number: int) -> list[Any]:
        if number == gone_plan:
            store.leave(gone_plan)
        return orig_comments(number)

    def _leave_on_set_title(number: int, title: str) -> Any:
        if number == gone_apply:
            store.leave(gone_apply)
        return orig_set_title(number, title)

    with caplog.at_level(logging.WARNING):
        with monkeypatch.context() as m:
            m.setattr(store, "comments_on", _leave_on_comments)
            plan = plan_retitle(store, repo=REPO, model=_RetitleModel())
        store.leave(gone_skip)
        with monkeypatch.context() as m:
            m.setattr(store, "set_title", _leave_on_set_title)
            written = apply_retitle(store, plan)

    assert (
        gone_plan not in [c.item.number for c in plan.changes],
        [c.item.number for c in plan.changes],
        [s.item.number for s in plan.skips],
        written,
    ) == (True, [gone_apply, stay], [gone_skip], 1)
    assert _lines_for(caplog, gone_plan) == [ONE % (gone_plan, REPO)]
    assert _lines_for(caplog, gone_apply) == [ONE % (gone_apply, REPO)]
    assert ONE % (gone_skip, REPO) in _lines_for(caplog, gone_skip)


# ── fix-plan row ──────────────────────────────────────────────────────────────


def test_fix_plan_row_skips_item_that_left_and_completes_next_item(
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`run_fix_plan` skips an item that left mid-attempt and completes the next candidate (#7363)."""
    valid_changes(openspec_fake)
    store = InMemoryRoadmapStore(repo=REPO)
    plan = needs_fix_plan(store, stage_repo, github_api)
    stay = plan.number
    gone = store.seed_issue(
        "fix(ci): higher priority gone",
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P0-Critical"},
    )
    gone_item = store.item(gone)
    assert gone_item is not None
    gone_branch = f"fix/{gone}-gone"
    gone_sha = _commit_on_branch(
        stage_repo, gone_branch, f"openspec/changes/{gone}-gone/tasks.md", "- [ ] 1.1 Fix\n"
    )
    store.set_marks(gone_item, {StageRecordKey.PR: "88", StageRecordKey.BRANCH: gone_branch})
    pull88_payload = {
        "number": 88,
        "state": "open",
        "draft": True,
        "merged": False,
        "title": f"docs(spec): plan #{gone}",
        "body": f"Plans #{gone}.",
        "head": {"sha": gone_sha, "ref": gone_branch},
        "base": {"ref": "main", "repo": {"default_branch": "main"}},
        "labels": [{"name": FIX_PLAN_LABEL}],
    }
    github_api.route("GET", f"/repos/{REPO}/pulls/88", github_json(pull88_payload))
    github_api.route("PATCH", f"/repos/{REPO}/pulls/88", github_json(pull88_payload))
    orig_set_marks = store.set_marks

    def _leave_on_start(item: Any, marks: Any, **kwargs: Any) -> None:
        if item.number == gone:
            store.leave(gone)
        orig_set_marks(item, marks, **kwargs)

    verifier = ModelFake()
    verifier.answer(
        Verification(findings=[finding(DefectType.CRITERION_DROPPED)]), later_review(GONE)
    )
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    with caplog.at_level(logging.WARNING), monkeypatch.context() as m:
        m.setattr(store, "set_marks", _leave_on_start)
        run = run_fix_plan(
            store,
            repo=REPO,
            source=stage_repo.clone,
            confirm=True,
            now=NOW,
            verifier=ToolboxModel(verifier),
        )

    assert (
        run.target is not None and run.target.item.number,
        run.attempt is not None and run.attempt.result,
        any(
            w.number == gone and w.key == StageRecordKey.FAILED_CLASS.value
            for w in store._roadmap.job_writes
        ),
    ) == (stay, FixPlanResult.CLEARED, False)
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]


# ── intake row & GitHubRoadmapStore GraphQL timeline ──────────────────────────


def test_intake_row_drops_record_that_is_no_issue_and_continues(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`intake` leaves out left items during plan and apply and places the rest (#7363)."""
    roadmap = IntakeRoadmap()
    gone_check = roadmap.issue("Gone during check")
    gone_decide = roadmap.issue("Gone during decide")
    gone_apply = roadmap.issue("Gone before apply")
    stay = roadmap.issue("Valid candidate")
    orig_closures = roadmap.store.closures

    def _leave_on_closures(number: int) -> list[Any]:
        if number == gone_check:
            roadmap.store.leave(gone_check)
        return orig_closures(number)

    class _LeavingIntakeModel(FakeIntakeModel):
        def propose(self, request: Any) -> Any:
            if request.title == "Gone during decide":
                roadmap.store.leave(gone_decide)
                raise GitHubNotAnIssueError(REPO, gone_decide)
            return super().propose(request)

    with caplog.at_level(logging.WARNING):
        with monkeypatch.context() as m:
            m.setattr(roadmap.store, "closures", _leave_on_closures)
            plan = roadmap.plan(_LeavingIntakeModel())
        roadmap.store.leave(gone_apply)
        applied = apply_intake(roadmap.store, plan, repo=REPO)

    assert (
        [d.subject.number for d in plan.decisions],
        applied.placed,
        applied.placed_critical_or_p0 >= 0,
        [f.number for f in applied.failed],
        roadmap.fields(stay)[0],
    ) == ([gone_apply, stay], 1, True, [], "New")
    assert _lines_for(caplog, gone_check) == [ONE % (gone_check, REPO)]
    assert _lines_for(caplog, gone_apply) == [ONE % (gone_apply, REPO)]


def test_github_store_closures_drops_left_issue_and_raises_not_an_issue(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """`GitHubRoadmapStore.closures` & `last_renamed_at` drop a left issue on GraphQL error (#7363)."""
    fake = GitHubFake("acme/widgets")
    fake.seed_issue(7, "docs(ci): moved issue", labels=("status/new",), body="Body")
    listing = IncrementalListing(FileSnapshotStore(tmp_path))
    first = GitHubRoadmapStore(
        "acme/widgets", runner=fake, session=RunnerSession(fake), listing=listing
    )
    assert [i.number for i in first.issues()] == [7]
    fake.move_issue(7, to="acme/other", as_number=12)

    def _runner_with_graphql_error(args: list[str], **kwargs: Any) -> Any:
        if "graphql" in args:
            from subprocess import CompletedProcess

            return CompletedProcess(
                args, 1, "", "Could not resolve to an Issue with the number of 7."
            )
        return fake(args, **kwargs)

    store = GitHubRoadmapStore(
        "acme/widgets",
        runner=_runner_with_graphql_error,
        session=RunnerSession(fake),
        listing=listing,
    )
    with caplog.at_level(logging.WARNING), pytest.raises(GitHubNotAnIssueError) as err:
        store.closures(7)
    with caplog.at_level(logging.WARNING), pytest.raises(GitHubNotAnIssueError) as err_rename:
        store.last_renamed_at(7)

    assert err.value.number == 7
    assert err_rename.value.number == 7
    assert [i.number for i in store.issues()] == []
    assert len(_lines_for(caplog, 7)) == 1


# ── metrics row ───────────────────────────────────────────────────────────────


def test_metrics_omits_age_of_item_that_left_and_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`get_item_age_metrics` omits an item that left without failing and reports other ages (#7363)."""
    t = NOW - timedelta(hours=4)
    store = InMemoryRoadmapStore(repo=REPO, clock=lambda: t)
    gone = store.seed_issue(
        "fix(ci): metric gone", fields={ItemField.PRIORITY: "P1-High", ItemField.STATUS: "Ready"}
    )
    stay = store.seed_issue(
        "fix(ci): metric stay", fields={ItemField.PRIORITY: "P1-High", ItemField.STATUS: "Ready"}
    )
    stay_item = store.item(stay)
    assert stay_item is not None
    store.set_field(stay_item, ItemField.STATUS, "Planned")
    store.leave(gone)

    with caplog.at_level(logging.WARNING):
        ages, _claim, _phases, counts = get_item_age_metrics(store, REPO, lambda: NOW)

    assert (ages != [], counts.get("service", 0) >= 0) == (True, True)
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]
