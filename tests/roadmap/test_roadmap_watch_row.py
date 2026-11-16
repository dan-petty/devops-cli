"""Tests for the `watch` row of the status lane (ADR 0021, section 8; #5024).

Verifies:
1. 1 GraphQL request per repository and tick.
2. 30-minute failed head backoff (does not re-read within 30 min).
3. Dry-run execution sends 0 requests.
4. Fallback to REST during GraphQL quota hold.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import (
    CONST_ROADMAP_WATCH_LEDGER_FILENAME,
    CONST_SERVICE_METRIC_FIX_CHECKS_JOBS,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stores.store import ImplementRecordKey, ItemField, StageRecordKey
from devops_cli.roadmap.watch_row import (
    WatchLedger,
    watch_round,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_run import NOW, REPO

pytestmark = pytest.mark.usefixtures("keyring_store", "cluster")

HEAD_FAIL = "1" * 40
HEAD_NEW = "2" * 40
HEAD_PASS = "3" * 40


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO)


@pytest.fixture
def github_api(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> GitHubApiFake:
    api, process = github_api_and_gh
    process.answer(
        "gh pr ready",
        ProcessAnswer(stdout="", returncode=0),
    )
    return api


def _graphql_pr_node(
    number: int,
    head: str,
    *,
    is_draft: bool = False,
    mergeable: str = "MERGEABLE",
    author: str = "alice",
    check_state: str = "FAILURE",
    check_conclusion: str = "FAILURE",
    body: str = "",
    title: str = "feat: test",
    base_ref: str = "main",
) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "isDraft": is_draft,
        "mergeable": mergeable,
        "headRefOid": head,
        "baseRefName": base_ref,
        "author": {"login": author},
        "commits": {
            "nodes": [
                {
                    "commit": {
                        "oid": head,
                        "message": title,
                        "statusCheckRollup": {
                            "state": check_state,
                            "contexts": {
                                "nodes": [
                                    {
                                        "__typename": "CheckRun",
                                        "name": "Tests & Coverage",
                                        "status": "COMPLETED",
                                        "conclusion": check_conclusion,
                                    }
                                ]
                            },
                        },
                    }
                }
            ]
        },
    }


def _route_graphql(api: GitHubApiFake, nodes: list[dict[str, Any]]) -> None:
    api.route(
        "POST",
        "/graphql",
        github_json(
            {
                "data": {
                    "repository": {
                        "pullRequests": {
                            "nodes": nodes,
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        ),
    )


def test_watch_row_sends_one_graphql_request_and_backs_off_failed_head(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A row test with fake GitHub sends 1 GraphQL request for each tick, and does not re-read a
    failed head within 30 min (#5024)."""
    issue_num = store.seed_issue("Issue 1", fields={ItemField.PRIORITY: "P1-High"})
    pr_num = store.seed_pull("feat: delivery PR", head_ref="feat/1-deliv")

    node = _graphql_pr_node(
        number=pr_num,
        head=HEAD_FAIL,
        is_draft=False,
        body=f"Closes #{issue_num}",
        check_state="FAILURE",
        check_conclusion="FAILURE",
    )
    _route_graphql(github_api, [node])

    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    t0 = NOW

    # Tick 1: first run
    res1 = watch_round(store, repo=REPO, ledger_path=ledger_path, now=t0)
    assert res1.watched == 1
    assert pr_num in res1.failed_heads

    # Verified 1 GraphQL request sent in tick 1
    graphql_reqs_1 = [r for r in github_api.sent if r.url.path == "/graphql"]
    assert len(graphql_reqs_1) == 1

    # Ledger holds failed head and next_read_at in 30 minutes
    ledger1 = WatchLedger.read(ledger_path)
    entry1 = ledger1.pulls.get(pr_num)
    assert entry1 is not None
    assert entry1.head == HEAD_FAIL
    assert entry1.verdict == "failed"
    assert entry1.next_read_at == (t0 + timedelta(minutes=30)).isoformat()

    # Tick 2: 10 minutes later (still within 30 min backoff)
    t1 = t0 + timedelta(minutes=10)
    _route_graphql(github_api, [node])

    res2 = watch_round(store, repo=REPO, ledger_path=ledger_path, now=t1)
    # The pull request was in backoff so checks were not re-evaluated
    assert pr_num in res2.failed_heads

    graphql_reqs_2 = [r for r in github_api.sent if r.url.path == "/graphql"]
    # Total GraphQL requests across the 2 ticks is 2 (1 per tick)
    assert len(graphql_reqs_2) == 2

    # Tick 3: 31 minutes later (backoff expired)
    t2 = t0 + timedelta(minutes=31)
    _route_graphql(github_api, [node])

    res3 = watch_round(store, repo=REPO, ledger_path=ledger_path, now=t2)
    assert pr_num in res3.failed_heads

    graphql_reqs_3 = [r for r in github_api.sent if r.url.path == "/graphql"]
    assert len(graphql_reqs_3) == 3


def test_a_bot_pull_request_with_a_failed_test_check_gets_one_fix_job_and_no_github_write(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path, cluster: FakeCluster
) -> None:
    """A finished bot delivery PR, whose implement Job ended, with a failed `Tests & Coverage`:
    the row starts one fix-checks Job in mode `plan`, with no `--confirm`, and writes nothing to
    GitHub. The record of the ended Job holds nothing against the PR (#5027)."""
    template = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    cluster.custom_objects.objects[("batch", "v1", "cronjobs")] = [template]
    issue = store.seed_issue("Issue 1", fields={ItemField.PRIORITY: "P1-High"})
    held = store.item(issue)
    assert held is not None
    store.set_marks(
        held,
        {
            ImplementRecordKey.JOB: f"devops-cli-implement-project-{issue}-abc123",
            ImplementRecordKey.JOB_STATE: "succeeded",
        },
    )
    pr_num = store.seed_pull("feat: delivery PR", head_ref=f"feat/{issue}-deliv")
    node = _graphql_pr_node(
        number=pr_num,
        head=HEAD_FAIL,
        body=f"Closes #{issue}",
        author="devops-cli-service",
    )
    _route_graphql(github_api, [node])

    result = watch_round(
        store, repo=REPO, ledger_path=tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME, now=NOW
    )

    (job,) = cluster.custom_objects.objects[("batch", "v1", "jobs")]
    args = job["spec"]["template"]["spec"]["containers"][0]["args"]
    assert (result.fix_checks.created, args[-2:], "--confirm" in args) == (
        (job["metadata"]["name"],),
        ["--check", "Tests & Coverage"],
        False,
    )
    assert [(r.method, r.url.path) for r in github_api.sent] == [("POST", "/graphql")]


@pytest.mark.parametrize("broken", ["cronjob", "limits"])
def test_a_kubernetes_or_configuration_error_of_the_fix_round_does_not_fail_the_row(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    cluster: FakeCluster,
    config: Any,
    caplog: pytest.LogCaptureFixture,
    broken: str,
) -> None:
    """A missing CronJob (`ClusterJobError`) or limits that do not nest (`ConfigurationError`)
    stop only the fix-checks round: the row logs and counts the error, writes its ledger and
    gives its result (#6018)."""
    if broken == "limits":
        template = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
        cluster.custom_objects.objects[("batch", "v1", "cronjobs")] = [template]
        config(roadmap={"implement": {"step_time_limit_seconds": 13000}})
    issue = store.seed_issue("Issue 1", fields={ItemField.PRIORITY: "P1-High"})
    held = store.item(issue)
    assert held is not None
    store.set_marks(
        held,
        {
            ImplementRecordKey.JOB: f"devops-cli-implement-project-{issue}-abc123",
            ImplementRecordKey.JOB_STATE: "succeeded",
        },
    )
    pr_num = store.seed_pull("feat: delivery PR", head_ref=f"feat/{issue}-deliv")
    node = _graphql_pr_node(
        number=pr_num, head=HEAD_FAIL, body=f"Closes #{issue}", author="devops-cli-service"
    )
    _route_graphql(github_api, [node])
    ledger = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    labels = {"repo": REPO, "result": "round_error"}
    before = GLOBAL_METRICS.get_counter_value(CONST_SERVICE_METRIC_FIX_CHECKS_JOBS, labels=labels)

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.fix_checks_row"):
        result = watch_round(store, repo=REPO, ledger_path=ledger, now=NOW)

    after = GLOBAL_METRICS.get_counter_value(CONST_SERVICE_METRIC_FIX_CHECKS_JOBS, labels=labels)
    assert (
        result.watched,
        result.failed_heads,
        result.fix_checks.created,
        after - before,
        any("fix-checks round" in r.getMessage() for r in caplog.records),
        pr_num in WatchLedger.read(ledger).pulls,
    ) == (1, (pr_num,), (), 1, True, True)


@pytest.mark.parametrize(("repaired", "calls"), [(True, 1), (False, 0)])
def test_a_green_delivery_draft_gets_the_ready_path_only_after_a_fix_and_once_for_each_head(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repaired: bool,
    calls: int,
) -> None:
    """A delivery draft whose implement Job ended is the implement Job's: the row marks nothing.
    A draft that a fix Job repaired gets the ready path of the step, in mode `plan` without
    `--confirm`, once for its head (#5027)."""
    from devops_cli.roadmap import watch_row
    from devops_cli.roadmap.steps.fix_checks import FixChecksReport, FixChecksResult
    from devops_cli.roadmap.stores.store import FixChecksRecordKey

    issue = store.seed_issue("Issue 1", fields={ItemField.PRIORITY: "P1-High"})
    held = store.item(issue)
    assert held is not None
    marks: dict[Any, str | None] = {
        ImplementRecordKey.JOB: f"devops-cli-implement-project-{issue}-abc123",
        ImplementRecordKey.JOB_STATE: "succeeded",
    }
    if repaired:
        marks[FixChecksRecordKey.RESULT] = "repaired"
    store.set_marks(held, marks)
    pr_num = store.seed_pull("feat: delivery PR", head_ref=f"feat/{issue}-deliv", draft=True)
    node = _graphql_pr_node(
        number=pr_num,
        head=HEAD_PASS,
        is_draft=True,
        body=f"Closes #{issue}",
        author="devops-cli-service",
        check_state="SUCCESS",
        check_conclusion="SUCCESS",
    )
    seen: list[tuple[int, str | None, bool]] = []

    def ready_path(store: Any, repo: str, pull: int, **kwargs: Any) -> FixChecksReport:
        # The row asks for the ready path only, so a check that fails between the read of the
        # row and the read of the step needs no repair (#6018).
        assert kwargs.get("ready_only") is True
        seen.append((pull, kwargs.get("head"), kwargs.get("confirm", False)))
        return FixChecksReport(repo=repo, pull=pull, result=FixChecksResult.PLANNED)

    monkeypatch.setattr(watch_row, "run_fix_checks", ready_path)
    ledger = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    for tick in range(2):
        _route_graphql(github_api, [node])
        result = watch_round(
            store, repo=REPO, ledger_path=ledger, now=NOW + timedelta(minutes=tick)
        )

    assert (seen, result.marked_ready) == ([(pr_num, HEAD_PASS, False)] * calls, ())
    assert [r for r in github_api.sent if r.method != "POST" or r.url.path != "/graphql"] == []


def test_watch_row_dry_run_sends_zero_requests(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A dry-run test sees 0 requests (#5024)."""
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    res = watch_round(store, repo=REPO, ledger_path=ledger_path, dry_run=True)
    assert res.watched == 0
    assert len(github_api.sent) == 0


def test_watch_row_marks_ready_bot_plan_draft(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A green draft plan pull request of the bot is marked ready."""
    issue_num = store.seed_issue("Plan Issue", fields={ItemField.PRIORITY: "P2-Medium"})
    pr_num = store.seed_pull("plan: my plan", head_ref="plan/1-test", draft=True)
    item = store.item(issue_num)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pr_num)})

    node = _graphql_pr_node(
        number=pr_num,
        head=HEAD_PASS,
        is_draft=True,
        author="devops-cli-service[bot]",
        check_state="SUCCESS",
        check_conclusion="SUCCESS",
    )
    _route_graphql(github_api, [node])
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls/{pr_num}",
        github_json(
            {
                "state": "open",
                "draft": True,
                "body": "",
                "head": {"sha": HEAD_PASS, "ref": "plan/1-test"},
                "base": {"ref": "main", "repo": {"default_branch": "main"}},
            }
        ),
    )

    # Route ready mark (gh pr ready runs via run_gh or client)
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    res = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
    assert pr_num in res.marked_ready

    # store updated with stage.ready
    updated_item = store.item(issue_num)
    assert updated_item is not None
    assert updated_item.job_record.get(StageRecordKey.READY) == str(pr_num)


def test_watch_row_comments_on_person_conflict(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A conflicting delivery PR from a person gets one comment per head."""
    issue_num = store.seed_issue("Conflict Issue", fields={ItemField.PRIORITY: "P2-Medium"})
    pr_num = store.seed_pull("feat: delivery PR", head_ref="feat/conflict")

    node = _graphql_pr_node(
        number=pr_num,
        head=HEAD_FAIL,
        is_draft=False,
        author="alice",
        mergeable="CONFLICTING",
        body=f"Closes #{issue_num}",
        check_state="SUCCESS",
        check_conclusion="SUCCESS",
    )
    _route_graphql(github_api, [node])
    github_api.route(
        "POST", f"/repos/{REPO}/issues/{pr_num}/comments", github_json({"id": 1}, status=201)
    )

    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    res = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
    assert pr_num in res.commented_conflicts

    comments = [
        json.loads(sent.content)["body"]
        for sent in github_api.sent
        if sent.method == "POST" and sent.url.path == f"/repos/{REPO}/issues/{pr_num}/comments"
    ]
    assert len(comments) == 1
    assert (
        MESSAGES.roadmap.pr_conflicts_comment.format(
            number=pr_num, base="main", head=HEAD_FAIL[:12]
        )
        in comments[0]
    )


def test_watch_ledger_read_corrupt_raises_roadmap_run_error(tmp_path: Path) -> None:
    """A corrupted watch ledger raises RoadmapRunError."""
    from devops_cli.exceptions import RoadmapRunError

    bad_file = tmp_path / "watch.json"
    bad_file.write_text("{corrupt json", encoding="utf-8")
    with pytest.raises(RoadmapRunError) as exc_info:
        WatchLedger.read(bad_file)
    assert "can't be read" in str(exc_info.value)


def test_watch_row_normalizes_mergeable_states(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """watch_round normalizes various GraphQL mergeable states."""
    issue_num = store.seed_issue("Delivery Issue", fields={ItemField.PRIORITY: "P1-High"})
    node_clean = _graphql_pr_node(
        number=201, head=HEAD_PASS, mergeable="MERGEABLE", body=f"Closes #{issue_num}"
    )
    node_dirty = _graphql_pr_node(
        number=202, head=HEAD_PASS, mergeable="CONFLICTING", body=f"Closes #{issue_num}"
    )
    node_behind = _graphql_pr_node(
        number=203, head=HEAD_PASS, mergeable="BEHIND", body=f"Closes #{issue_num}"
    )
    node_bool_true = _graphql_pr_node(
        number=204, head=HEAD_PASS, mergeable=True, body=f"Closes #{issue_num}"
    )
    node_bool_false = _graphql_pr_node(
        number=205, head=HEAD_PASS, mergeable=False, body=f"Closes #{issue_num}"
    )
    node_unknown = _graphql_pr_node(
        number=206, head=HEAD_PASS, mergeable=None, body=f"Closes #{issue_num}"
    )
    _route_graphql(
        github_api,
        [node_clean, node_dirty, node_behind, node_bool_true, node_bool_false, node_unknown],
    )
    github_api.route(
        "POST", f"/repos/{REPO}/issues/202/comments", github_json({"id": 1}, status=201)
    )
    github_api.route(
        "POST", f"/repos/{REPO}/issues/205/comments", github_json({"id": 2}, status=201)
    )
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    res = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
    assert 202 in res.commented_conflicts
    assert 205 in res.commented_conflicts


def test_watch_row_skips_non_delivering_pull_requests(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """watch_round skips pull requests that do not deliver an open roadmap item."""
    from devops_cli.roadmap.stores.store import GitHubState

    open_issue = store.seed_issue("Item 1", fields={ItemField.PRIORITY: "P1-High"})
    closed_issue = store.seed_issue(
        "Item Closed", fields={ItemField.PRIORITY: "P1-High"}, state=GitHubState.CLOSED
    )

    node1 = _graphql_pr_node(
        number=101, head=HEAD_PASS, base_ref="feature", body=f"Closes #{open_issue}"
    )
    node2 = _graphql_pr_node(number=102, head=HEAD_PASS, base_ref="main", body="Just a regular PR")
    node3 = _graphql_pr_node(
        number=103, head=HEAD_PASS, base_ref="main", body=f"Closes #{closed_issue}"
    )
    _route_graphql(github_api, [node1, node2, node3])

    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    res = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
    assert res.watched == 0
    assert len(res.marked_ready) == 0
    assert len(res.commented_conflicts) == 0


def test_watch_row_graphql_pagination_and_non_roadmap_pr(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """GraphQL pagination reads multiple pages and skips non-roadmap PRs."""
    issue_num = store.seed_issue("Plan Issue", fields={ItemField.PRIORITY: "P2-Medium"})
    pr_num = store.seed_pull("plan: plan pr", head_ref="plan/1-test", draft=True)
    item = store.item(issue_num)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pr_num)})

    # Page 1 has non-roadmap PR #999 and hasNextPage=True
    non_roadmap_node = _graphql_pr_node(
        number=999, head=HEAD_PASS, is_draft=False, body="Random PR"
    )
    # Page 2 has the plan PR
    plan_node = _graphql_pr_node(
        number=pr_num,
        head=HEAD_PASS,
        is_draft=True,
        author="devops-cli-service[bot]",
        check_state="SUCCESS",
        check_conclusion="SUCCESS",
    )

    page1 = {
        "data": {
            "repository": {
                "pullRequests": {
                    "nodes": [non_roadmap_node],
                    "pageInfo": {"hasNextPage": True, "endCursor": "cur1"},
                }
            }
        }
    }
    page2 = {
        "data": {
            "repository": {
                "pullRequests": {
                    "nodes": [plan_node],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
    }

    github_api.route("POST", "/graphql", github_json(page1), github_json(page2))
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls/{pr_num}",
        github_json(
            {
                "state": "open",
                "draft": True,
                "body": "",
                "head": {"sha": HEAD_PASS, "ref": "plan/1-test"},
                "base": {"ref": "main", "repo": {"default_branch": "main"}},
            }
        ),
    )

    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    res = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
    assert res.watched == 1
    assert pr_num in res.marked_ready


def test_watch_row_jev_completeness_and_needs_fix(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    config: Any,
) -> None:
    """Jev completeness holds a green plan draft, and clears on ok; needs-fix skips ready."""
    from devops_cli.roadmap.jev_completeness import CompletenessOutcome

    issue_num = store.seed_issue(
        "Plan Issue",
        body="## Acceptance Criteria\n- criterion 1",
        fields={ItemField.PRIORITY: "P2-Medium"},
    )
    pr_num = store.seed_pull("plan: plan pr", head_ref="plan/1-test", draft=True)
    item = store.item(issue_num)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pr_num)})

    node = _graphql_pr_node(
        number=pr_num,
        head=HEAD_PASS,
        is_draft=True,
        author="devops-cli-service[bot]",
        check_state="SUCCESS",
        check_conclusion="SUCCESS",
    )
    _route_graphql(github_api, [node])

    # Case 1: needs-fix mark on item
    store.set_marks(item, {StageRecordKey.NEEDS_FIX: str(pr_num)})
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    res1 = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
    assert pr_num not in res1.marked_ready
    store.set_marks(item, {StageRecordKey.NEEDS_FIX: None})

    # Case 2: jev_completeness is True and item has JEV held mark
    config(roadmap={"stage": {"jev_completeness": True}})
    store.set_marks(item, {StageRecordKey.JEV: f"{HEAD_PASS}:{CompletenessOutcome.HELD}"})

    res2 = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
    assert pr_num not in res2.marked_ready

    # Case 3: jev_completeness is False (default) and mark cleared, marks ready
    config(roadmap={"stage": {"jev_completeness": False}})
    store.set_marks(item, {StageRecordKey.JEV: None})
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls/{pr_num}",
        github_json(
            {
                "state": "open",
                "draft": True,
                "body": "",
                "head": {"sha": HEAD_PASS, "ref": "plan/1-test"},
                "base": {"ref": "main", "repo": {"default_branch": "main"}},
            }
        ),
    )
    res3 = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
    assert pr_num in res3.marked_ready


def test_watch_row_rest_fallback_and_closed_stage_plans(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
) -> None:
    """REST fallback processes open and closed stage plans, syncing status."""
    import time

    from devops_cli.github.rate_limiter import get_github_rate_limiter

    get_github_rate_limiter().update_quota(
        "graphql", remaining=0, limit=5000, reset_epoch=time.time() + 600.0
    )
    try:
        issue_num = store.seed_issue("Delivery Issue", fields={ItemField.PRIORITY: "P1-High"})
        delivery_pr = store.seed_pull("feat: deliv", head_ref="feat/deliv")

        plan_issue = store.seed_issue("Closed Plan Issue", fields={ItemField.PRIORITY: "P1-High"})
        plan_item = store.item(plan_issue)
        assert plan_item is not None
        plan_pr = 555
        store.set_marks(plan_item, {StageRecordKey.PR: str(plan_pr)})

        github_api.route(
            "GET",
            f"/repos/{REPO}/pulls/{delivery_pr}",
            github_json(
                {
                    "number": delivery_pr,
                    "state": "open",
                    "merged": False,
                    "draft": False,
                    "body": f"Closes #{issue_num}",
                    "head": {"sha": HEAD_PASS, "ref": "feat/deliv"},
                    "base": {"ref": "main", "repo": {"default_branch": "main"}},
                }
            ),
        )
        github_api.route(
            "GET",
            f"/repos/{REPO}/commits/{HEAD_PASS}/check-runs",
            github_json(
                {"check_runs": [{"name": "test", "status": "completed", "conclusion": "success"}]}
            ),
        )
        github_api.route(
            "GET",
            f"/repos/{REPO}/pulls/{plan_pr}",
            github_json(
                {
                    "number": plan_pr,
                    "state": "closed",
                    "merged": True,
                    "draft": False,
                    "body": "Plan PR",
                    "head": {"sha": HEAD_PASS, "ref": "plan/closed"},
                    "base": {"ref": "main", "repo": {"default_branch": "main"}},
                }
            ),
        )

        ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
        res = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
        assert res.watched == 1

        updated_plan_item = store.item(plan_issue)
        assert updated_plan_item is not None
        assert updated_plan_item.job_record.get(StageRecordKey.READY) == str(plan_pr)
    finally:
        get_github_rate_limiter().update_quota(
            "graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
        )
