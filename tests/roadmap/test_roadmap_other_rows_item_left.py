"""Tests that every other roadmap row leaves out an item that left the repository (#7363)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions.git import GitHubNotAnIssueError
from devops_cli.github.metrics import get_item_age_metrics
from devops_cli.github.release_title import RELEASE_CONFIG_PATH
from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE, STAGE_TEMPLATE
from devops_cli.k8s.cluster_job_api import ClusterJobs
from devops_cli.roadmap.failure import FailureClass, StepName
from devops_cli.roadmap.implement import implement_submit
from devops_cli.roadmap.implement.implement import parse_implement_filters, plan_implement
from devops_cli.roadmap.intake.intake import apply_intake
from devops_cli.roadmap.open_row import run_open_round
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.refine.refine import (
    RefineWriter,
    plan_refine,
    raise_for_failed_items,
    select_candidates,
)
from devops_cli.roadmap.retitle import RetitleReply, apply_retitle, plan_retitle
from devops_cli.roadmap.return_item import plan_return
from devops_cli.roadmap.stage import stage as stage_mod
from devops_cli.roadmap.stage.stage import StageFailure
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
    """`implement_submit._fresh` must raise `GitHubNotAnIssueError` when an item left (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    gone = store.seed_issue("fix(ci): left", fields={ItemField.PRIORITY: "P1-High"})
    store.leave(gone)

    with pytest.raises(GitHubNotAnIssueError) as err:
        implement_submit._fresh(store, gone)

    assert err.value.number == gone


def test_return_item_raises_github_not_an_issue_for_missing_issue() -> None:
    """`plan_return` must raise `GitHubNotAnIssueError` when the issue left the repository (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    gone = store.seed_issue("fix(ci): left", fields={ItemField.PRIORITY: "P1-High"})
    store.leave(gone)

    with pytest.raises(GitHubNotAnIssueError) as err:
        plan_return(store, gone, "Evidence.", REPO)

    assert err.value.number == gone


# ── implement row ─────────────────────────────────────────────────────────────


def test_implement_row_skips_item_that_left_and_continues(
    stage_repo: StageRepo,
    cluster: FakeCluster,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`plan_implement`, `_report_ended`, `_note_needs_fix`, and `_submit_selected_targets` skip an
    item that left and continue with other items (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    gone = store.seed_issue(
        "fix(ci): stopped left",
        labels=("priority/p1-high", "type/bug", "effort/low", "approved"),
        fields={
            ItemField.STATUS: "Blocked",
            ItemField.PRIORITY: "P1-High",
            ItemField.EFFORT: "Low",
        },
    )
    stay = seed_staged(store, status="Planned")
    gone_item = store.item(gone)
    stay_item = store.item(stay)
    assert gone_item is not None
    assert stay_item is not None
    store.set_marks(
        gone_item,
        {
            ImplementRecordKey.STOPPED: "tests",
            ImplementRecordKey.JOB: "devops-cli-runner-gone",
        },
    )
    merge_plan(stage_repo, stay)
    planned = PlannedChanges(
        "main", {gone: f"{gone}-left", stay: f"{stay}-the-job-drops-a-comment"}, {}
    )
    store.leave(gone)

    with caplog.at_level(logging.WARNING):
        plan = plan_implement(
            store,
            repo=REPO,
            source=stage_repo.clone,
            filters=parse_implement_filters(()),
            planned=planned,
            remote_heads="",
        )
        gone2 = store.seed_issue(
            "fix(ci): report gone",
            labels=("priority/p1-high", "type/bug", "approved"),
            fields={
                ItemField.STATUS: "Planned",
                ItemField.PRIORITY: "P1-High",
                ItemField.EFFORT: "Low",
            },
        )
        g2 = store.item(gone2)
        assert g2 is not None
        store.set_marks(g2, {ImplementRecordKey.JOB: "devops-cli-runner-report-gone"})
        store.leave(gone2)
        jobs = ClusterJobs()
        reported = implement_submit._report_ended(store, jobs, {}, REPO)
        cronjob = cronjob_template(RUNNER_TEMPLATE)
        cluster.custom_objects.objects[CRONJOBS] = [cronjob]
        created, _ = implement_submit._submit_selected_targets(
            store,
            jobs,
            REPO,
            list(plan.selected),
            "example-roadmap",
            stage_repo.clone,
            planned,
            None,
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
        g3 = store.item(gone3)
        assert g3 is not None
        store.leave(gone3)
        from devops_cli.roadmap.implement.implement import ImplementPlan, NeedsFix

        noted = implement_submit._note_needs_fix(
            store, ImplementPlan(REPO, needs_fix=(NeedsFix(g3, 99),))
        )

    assert (
        [t.item.number for t in plan.selected],
        reported,
        len(created),
        noted,
        [
            w
            for w in store._roadmap.job_writes
            if w.number == gone and w.key == ImplementRecordKey.FAILURE.value
        ],
    ) == ([stay], (), 1, (), [])
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]
    assert _lines_for(caplog, gone2) == [ONE % (gone2, REPO)]
    assert _lines_for(caplog, gone3) == [ONE % (gone3, REPO)]


# ── stage row ─────────────────────────────────────────────────────────────────


def test_stage_row_skips_item_that_left_and_continues(
    stage_repo: StageRepo,
    cluster: FakeCluster,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`run_stage_round` and `_record_failures` skip an item that left without failing (#7363)."""
    config(roadmap={"stage": {"jobs": 2}})
    store = InMemoryRoadmapStore(repo=REPO)
    gone = seed_stageable(store)
    stay = seed_stageable(store)
    gone_fail = store.seed_issue("fix(ci): fail gone", fields={ItemField.PRIORITY: "P1-High"})
    github_api.route("GET", f"/repos/{REPO}/pulls?state=open&per_page=100", github_json([]))
    cronjob = cronjob_template(STAGE_TEMPLATE)
    cluster.custom_objects.objects[CRONJOBS] = [cronjob]
    jobs = ClusterJobs()
    gone_item = store.item(gone)
    stay_item = store.item(stay)
    gf_item = store.item(gone_fail)
    assert gone_item is not None
    assert stay_item is not None
    assert gf_item is not None
    orig_set_field = store.set_field

    def _fail_gone_claim(
        item: Any, field: Any, value: Any, *, marks: Any = None, **kwargs: Any
    ) -> Any:
        if (
            item.number == gone
            and field is ItemField.OWNER
            and marks
            and StageRecordKey.JOB in marks
        ):
            store.leave(gone)
        return orig_set_field(item, field, value, marks=marks, **kwargs)

    monkeypatch.setattr(store, "set_field", _fail_gone_claim)

    with caplog.at_level(logging.WARNING):
        result = run_stage_round(store, repo=REPO, source=stage_repo.clone, jobs=jobs, now=NOW)
        monkeypatch.undo()
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
        any(
            w.number == gone and w.key == StageRecordKey.FAILED_CLASS.value
            for w in store._roadmap.job_writes
        ),
        any(
            w.number == gone_fail and w.key == StageRecordKey.FAILED_CLASS.value
            for w in store._roadmap.job_writes
        ),
        (store.item(stay) or stay_item).job_record.get(StageRecordKey.FAILED_CLASS),
    ) == ((job_name_of(REPO, stay_item),), False, False, FailureClass.PROVIDER.value)
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]
    assert _lines_for(caplog, gone_fail) == [ONE % (gone_fail, REPO)]


# ── watch row ─────────────────────────────────────────────────────────────────


def test_watch_row_skips_item_that_left_and_continues(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`watch_round` skips an item that left when setting marks or syncing status (#7363)."""
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
    gone_item = store.item(gone)
    stay_item = store.item(stay)
    assert gone_item is not None
    assert stay_item is not None
    store.set_field(gone_item, ItemField.STATUS, "Ready")
    store.set_field(stay_item, ItemField.STATUS, "Ready")
    gone_item = store.item(gone)
    stay_item = store.item(stay)
    assert gone_item is not None
    assert stay_item is not None
    store.set_marks(
        gone_item, {StageRecordKey.PR: "101", StageRecordKey.BRANCH: f"fix/{gone}-gone"}
    )
    store.set_marks(
        stay_item, {StageRecordKey.PR: "102", StageRecordKey.BRANCH: f"fix/{stay}-stay"}
    )
    api.route(
        "POST",
        "/graphql",
        github_json({"data": {"repository": {"pullRequests": {"nodes": []}}}}),
    )
    for pr_num, branch in ((101, f"fix/{gone}-gone"), (102, f"fix/{stay}-stay")):
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
    orig_set_marks = store.set_marks

    def _leave_before_watch_write(item: Any, marks: Any, **kwargs: Any) -> None:
        if item.number == gone and StageRecordKey.READY in marks:
            store.leave(gone)
        orig_set_marks(item, marks, **kwargs)

    monkeypatch.setattr(store, "set_marks", _leave_before_watch_write)

    with caplog.at_level(logging.WARNING):
        res: WatchRoundResult = watch_round(
            store, repo=REPO, ledger_path=tmp_path / "watch.json", now=NOW
        )

    stay_after = store.item(stay)
    assert (
        res.watched,
        stay_after is not None and stay_after.status == "Planned",
        any(
            w.number == gone and w.key == StageRecordKey.READY.value
            for w in store._roadmap.job_writes
        ),
    ) == (0, True, False)
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]


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
    stay = store.seed_issue("fix(ci): open stay", fields={ItemField.PRIORITY: "P1-High"})
    gone_item = store.item(gone)
    stay_item = store.item(stay)
    assert gone_item is not None
    assert stay_item is not None
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

    with caplog.at_level(logging.WARNING):
        store.leave(gone)
        open_mod._record_pr_marks(store, gone, "delivery", 201, b_gone)
        open_mod._sync_status(store, gone, "delivery")
        gone_mid = store.seed_issue(
            "fix(ci): open mid gone", fields={ItemField.PRIORITY: "P1-High"}
        )
        gm_item = store.item(gone_mid)
        assert gm_item is not None
        b_mid = f"fix/{gone_mid}-open-mid"
        store.set_marks(gm_item, {ImplementRecordKey.BRANCH: b_mid})
        sha_mid = _commit_on_branch(stage_repo, b_mid, f"src/mid_{gone_mid}.py", "Z = 3\n")
        github_api.route(
            "GET", f"/repos/{REPO}/commits/{sha_mid}/pulls?per_page=100", github_json([])
        )
        github_api.route(
            "GET",
            f"/repos/{REPO}/compare/main...{sha_mid}?per_page=1",
            github_json(
                {
                    "merge_base_commit": {"sha": "base"},
                    "files": [{"filename": f"src/mid_{gone_mid}.py", "status": "added"}],
                }
            ),
        )
        orig_set_marks = store.set_marks

        def _leave_mid(item: Any, marks: Any, **kwargs: Any) -> None:
            if item.number == gone_mid and ImplementRecordKey.PR in marks:
                store.leave(gone_mid)
            orig_set_marks(item, marks, **kwargs)

        monkeypatch.setattr(store, "set_marks", _leave_mid)
        github_api.route(
            "GET",
            f"/repos/{REPO}/pulls?head=example:{b_mid}&state=open",
            github_json([]),
        )
        github_api.route(
            "POST",
            f"/repos/{REPO}/pulls",
            github_json(
                {"number": 203, "html_url": f"https://github.com/{REPO}/pull/203"},
                status=201,
            ),
        )
        github_api.route(
            "POST",
            f"/repos/{REPO}/pulls/203/requested_reviewers",
            github_json({"requested_reviewers": [{"login": "example"}]}),
        )
        res = run_open_round(store, repo=REPO, source=stage_repo.clone, mode="on", base="main")

    assert (
        len(res.opened) >= 1,
        res.failed,
        any(
            w.number in {gone, gone_mid} and w.key == ImplementRecordKey.FAILURE.value
            for w in store._roadmap.job_writes
        ),
    ) == (
        True,
        [],
        False,
    )
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]
    assert _lines_for(caplog, gone_mid) == [ONE % (gone_mid, REPO)]


# ── refine row ────────────────────────────────────────────────────────────────


def test_refine_row_skips_item_that_left_and_continues(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`plan_refine` and `RefineWriter` skip an item that left and refine remaining items (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    store.seed_visibility(is_private=True)
    gone = store.seed_issue(
        "fix(ci): refine gone",
        fields={**PLACED, ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )
    stay = store.seed_issue(
        "fix(ci): refine stay",
        fields={**PLACED, ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )
    model_fake.answer(READY)
    writer = RefineWriter(store, REPO)

    with caplog.at_level(logging.WARNING):
        selected, _ = select_candidates(store, limit=5)
        store.leave(gone)
        plan = plan_refine(
            store,
            repo=REPO,
            source=stage_repo.clone,
            limit=5,
            writer=writer,
        )
        raise_for_failed_items(plan, writer.readied_count)

    assert (
        [i.number for i in selected],
        [r.item.number for r in plan.refined_items],
        plan.failed_items,
    ) == ([gone, stay], [stay], [])
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]


# ── retitle row ───────────────────────────────────────────────────────────────


def test_retitle_row_skips_item_that_left_and_continues(caplog: pytest.LogCaptureFixture) -> None:
    """`plan_retitle` and `apply_retitle` leave out an item that left and continue (#7363)."""
    store = InMemoryRoadmapStore(repo=REPO)
    long_title = "fix(roadmap): " + "very long summary word " * 5
    gone = store.seed_issue(long_title, fields={ItemField.PRIORITY: "P1-High"})
    stay = store.seed_issue(long_title, fields={ItemField.PRIORITY: "P1-High"})

    class _RetitleModel:
        def summarize(self, _prompt: str) -> RetitleReply:
            return RetitleReply(summary="shortened summary of item")

    store.leave(gone)

    with caplog.at_level(logging.WARNING):
        plan = plan_retitle(store, repo=REPO, model=_RetitleModel())
        written = apply_retitle(store, plan)

    assert ([c.item.number for c in plan.changes], plan.skips, written) == ([stay], (), 1)
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]


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

    monkeypatch.setattr(store, "set_marks", _leave_on_start)
    verifier = ModelFake()
    verifier.answer(
        Verification(findings=[finding(DefectType.CRITERION_DROPPED)]), later_review(GONE)
    )
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    with caplog.at_level(logging.WARNING):
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
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`intake` leaves out a number that raises `GitHubNotAnIssueError` and places the rest (#7363)."""
    roadmap = IntakeRoadmap()
    gone = roadmap.issue("Gone candidate")
    stay = roadmap.issue("Valid candidate")
    roadmap.store.leave(gone)

    with caplog.at_level(logging.WARNING):
        plan = roadmap.plan(FakeIntakeModel())
        applied = apply_intake(roadmap.store, plan, repo=REPO)

    assert (
        [d.subject.number for d in plan.decisions],
        applied.placed,
        applied.failed,
        roadmap.fields(stay)[0],
    ) == ([stay], 1, (), "New")
    assert _lines_for(caplog, gone) == [ONE % (gone, REPO)]


def test_github_store_closures_drops_left_issue_and_raises_not_an_issue(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """`GitHubRoadmapStore.closures` drops a left issue on GraphQL error and logs once (#7363)."""
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

    assert err.value.number == 7
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
