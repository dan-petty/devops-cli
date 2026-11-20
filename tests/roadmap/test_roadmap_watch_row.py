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
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from devops_cli.config.constants import (
    CONST_ROADMAP_WATCH_LEDGER_FILENAME,
    CONST_SERVICE_METRIC_FIX_CHECKS_JOBS,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stores.store import (
    FixChecksRecordKey,
    ImplementRecordKey,
    ItemField,
    StageRecordKey,
)
from devops_cli.roadmap.watch_row import (
    WatchLedger,
    WatchRoundResult,
    watch_round,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.github import (
    GitHubApiFake,
    github_json,
    route_compare_files,
    route_file,
)
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_run import NOW, REPO

pytestmark = pytest.mark.usefixtures("keyring_store", "cluster")

HEAD_FAIL = "1" * 40
HEAD_NEW = "2" * 40
HEAD_PASS = "3" * 40
PLAN_BODY = "The plan of the item: the change folder and its tasks."
TASKS_GROUP_5_UNTICKED = (
    "# Tasks\n\n"
    "## 1. Add the RAG rows\n\nChanges: `src/devops_cli/sample.py`.\n\n- [x] 1.1 Add the rows\n\n"
    "## 5. Document the RAG rows\n\nChanges: `docs/SAMPLE.md`.\n\n"
    "- [ ] 5.1 Document the rows\n- [ ] 5.2 Document the start\n"
)


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
    check_name: str = "Tests & Coverage",
    body: str = "",
    title: str = "feat: test",
    base_ref: str = "main",
    labels: tuple[str, ...] = (),
    contexts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if contexts is None:
        contexts = [
            {
                "__typename": "CheckRun",
                "name": check_name,
                "status": "COMPLETED",
                "conclusion": check_conclusion,
            }
        ]
    return {
        "number": number,
        "title": title,
        "body": body,
        "isDraft": is_draft,
        "labels": {"nodes": [{"name": name} for name in labels]},
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
                            "contexts": {"nodes": contexts},
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


def _route_draft(
    api: GitHubApiFake, pull: int, branch: str, *, tasks: tuple[str, str] | None = None
) -> None:
    """Answer the reads of `draft_readiness` for draft `pull` on `branch` at `HEAD_PASS`: the pull
    request, its compare with `main`, and the `tasks.md` of `tasks` (path, text) when given."""
    api.route(
        "GET",
        f"/repos/{REPO}/pulls/{pull}",
        github_json(
            {
                "state": "open",
                "draft": True,
                "title": "feat(roadmap): Add the sample",
                "body": PLAN_BODY,
                "head": {"sha": HEAD_PASS, "ref": branch},
                "base": {"ref": "main", "repo": {"default_branch": "main"}},
            }
        ),
    )
    changed = [{"filename": "src/devops_cli/sample.py", "status": "modified"}]
    if tasks is not None:
        changed.append({"filename": tasks[0], "status": "added"})
        route_file(api, REPO, tasks[0], HEAD_PASS, tasks[1])
    route_compare_files(api, REPO, "main", HEAD_PASS, *changed, merge_base="c" * 40)


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


@pytest.mark.parametrize(
    ("end", "calls"),
    [
        ({FixChecksRecordKey.RESULT: "repaired"}, 1),
        ({ImplementRecordKey.RESULT: "drafted"}, 1),
        ({ImplementRecordKey.RESULT: "stopped"}, 0),
        ({}, 0),
    ],
    ids=["repaired", "drafted", "stopped", "no-end"],
)
def test_a_green_delivery_draft_gets_the_ready_path_after_a_fix_or_a_drafted_end_once_a_head(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    end: dict[Any, str],
    calls: int,
) -> None:
    """A delivery draft that a fix Job repaired, or whose implement Job ended at the draft, gets
    the ready path of the step, in mode `plan` without `--confirm`, once for its head (#5027,
    #6559). The row leaves a draft whose Job stopped."""
    from devops_cli.roadmap import watch_row
    from devops_cli.roadmap.steps.fix_checks import FixChecksReport
    from devops_cli.roadmap.stores.store import FixChecksResult

    issue = store.seed_issue("Issue 1", fields={ItemField.PRIORITY: "P1-High"})
    held = store.item(issue)
    assert held is not None
    marks: dict[Any, str | None] = {
        ImplementRecordKey.JOB: f"devops-cli-implement-project-{issue}-abc123",
        ImplementRecordKey.JOB_STATE: "succeeded",
        **end,
    }
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


def test_a_ready_path_that_raises_runs_again_for_the_same_head(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The row records the head as judged only after the ready path returns a report, so a GitHub
    error in the first round leaves the head for the next round (#6559)."""
    from devops_cli.exceptions import GitHubOperationError
    from devops_cli.roadmap import watch_row
    from devops_cli.roadmap.steps.fix_checks import FixChecksReport
    from devops_cli.roadmap.stores.store import FixChecksResult

    issue = store.seed_issue("Issue 1", fields={ItemField.PRIORITY: "P1-High"})
    held = store.item(issue)
    assert held is not None
    store.set_marks(
        held,
        {
            ImplementRecordKey.JOB: f"devops-cli-implement-project-{issue}-abc123",
            ImplementRecordKey.JOB_STATE: "succeeded",
            ImplementRecordKey.RESULT: "drafted",
        },
    )
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
    calls: list[int] = []

    def ready_path(store: Any, repo: str, pull: int, **kwargs: Any) -> FixChecksReport:
        calls.append(pull)
        if len(calls) == 1:
            raise GitHubOperationError("502 Bad Gateway", operation="get_pull_status")
        return FixChecksReport(repo=repo, pull=pull, result=FixChecksResult.PLANNED)

    monkeypatch.setattr(watch_row, "run_fix_checks", ready_path)
    ledger = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    for tick in range(3):
        _route_graphql(github_api, [node])
        try:
            watch_round(store, repo=REPO, ledger_path=ledger, now=NOW + timedelta(minutes=tick))
        except GitHubOperationError:
            pass

    assert calls == [pr_num, pr_num]


def _drafted_delivery(store: InMemoryRoadmapStore, *, staged: bool = False) -> tuple[int, int]:
    """Seed an item In Review whose implement Job ended at its draft pull request, and that draft:
    the record holds `implement.result` drafted and `implement.pr` (#6559). A Staged item also
    holds the draft as its plan pull request (`stage.pr`). Gives the item and the draft."""
    issue = store.seed_issue("Issue 1", fields={ItemField.PRIORITY: "P1-High"})
    pr_num = store.seed_pull("feat: delivery PR", head_ref=f"feat/{issue}-deliv", draft=True)
    held = store.item(issue)
    assert held is not None
    marks: dict[Any, str] = {
        ImplementRecordKey.JOB: f"devops-cli-implement-project-{issue}-abc123",
        ImplementRecordKey.JOB_STATE: "succeeded",
        ImplementRecordKey.RESULT: "drafted",
        ImplementRecordKey.PR: str(pr_num),
    }
    if staged:
        marks[StageRecordKey.PR] = str(pr_num)
    store.set_field(held, ItemField.STATUS, "In Review", marks=marks)
    return issue, pr_num


def _delivery_node(pr_num: int, issue: int, **fields: Any) -> dict[str, Any]:
    """The GraphQL node of the draft of `_drafted_delivery`; `fields` change the defaults."""
    values: dict[str, Any] = {
        "is_draft": True,
        "body": f"Closes #{issue}",
        "author": "devops-cli-service",
        "head": HEAD_FAIL,
        **fields,
    }
    return _graphql_pr_node(number=pr_num, **values)


def _rounds(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    ledger: Path,
    nodes: Sequence[dict[str, Any]],
    ticks: Sequence[int] = (0, 31, 62),
) -> list[WatchRoundResult]:
    """Run one watch round for each node, at each minute of `ticks` after NOW."""
    results = []
    for node, tick in zip(nodes, ticks, strict=False):
        _route_graphql(github_api, [node])
        results.append(
            watch_round(store, repo=REPO, ledger_path=ledger, now=NOW + timedelta(minutes=tick))
        )
    return results


def _stop_facts(store: InMemoryRoadmapStore, issue: int) -> tuple[Any, ...]:
    """The Status, the stop, the class and the result of the item, and its count of comments."""
    held = store.item(issue)
    assert held is not None
    record = held.job_record
    return (
        held.status,
        record.get(ImplementRecordKey.STOPPED),
        record.get(ImplementRecordKey.FAILURE),
        record.get(ImplementRecordKey.RESULT),
        len(store.comments_on(issue)),
    )


_NOT_STOPPED: Final = ("In Review", None, None, "drafted", 0)


@pytest.mark.parametrize(
    ("check", "conclusion", "mergeable", "klass", "staged"),
    [
        ("Semantic PR title", "FAILURE", "MERGEABLE", "ci_infra", False),
        ("Tests & Coverage", "CANCELLED", "MERGEABLE", "ci_infra", False),
        ("Tests & Coverage", "SUCCESS", "CONFLICTING", "conflict", False),
        ("Tests & Coverage", "CANCELLED", "MERGEABLE", "ci_infra", True),
        ("Tests & Coverage", "SUCCESS", "CONFLICTING", "conflict", True),
    ],
    ids=["ci-infra", "cancelled", "conflict", "staged-cancelled", "staged-conflict"],
)
def test_a_drafted_delivery_draft_that_no_unit_takes_stops_its_item_once(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    check: str,
    conclusion: str,
    mergeable: str,
    klass: str,
    staged: bool,
) -> None:
    """A failed check that no fix-checks unit repairs, a cancelled check and a conflict with the
    base leave a drafted delivery draft with no actor, so the row stops its item through the stop
    flow, once: Status Blocked, the class, `implement.result` stopped, and one stop comment that
    names the cause (#6559). A Staged item whose plan pull request is also its delivery draft gets
    the same stop: the record, not the kind of the pull request, says that it is the delivery."""
    issue, pr_num = _drafted_delivery(store, staged=staged)
    node = _delivery_node(
        pr_num,
        issue,
        mergeable=mergeable,
        check_state="SUCCESS" if conclusion == "SUCCESS" else "FAILURE",
        check_conclusion=conclusion,
        check_name=check,
    )
    _rounds(store, github_api, tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME, [node] * 3)

    comments = [c.body for c in store.comments_on(issue)]
    named = "conflict" if klass == "conflict" else check
    assert (*_stop_facts(store, issue), named in comments[0]) == (
        "Blocked",
        "pull request",
        klass,
        "stopped",
        1,
        True,
    )


@pytest.mark.parametrize(
    ("mode", "record"),
    [
        ("off", {}),
        ("plan", {}),
        ("on", {"result": "failed"}),
        ("on", {"result": "stopped"}),
        ("on", {"outcome": "error"}),
        ("on", {"outcome": "none", "attempt": 9}),
    ],
    ids=["mode-off", "mode-plan", "unit-failed", "unit-stopped", "unit-error", "unit-spent"],
)
def test_a_failed_test_check_with_no_repair_owner_stops_the_item_of_its_delivery_draft(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    config: Any,
    mode: str,
    record: dict[str, Any],
) -> None:
    """A failed check of the class test has a repair owner only in mode `on`, and only while the
    fix-checks unit of the head and the check has not ended with no repair: the last round of the
    step on them failed or stopped, or the unit record holds an outcome or spent its attempts. In
    each other case the row stops the item (#6559)."""
    config(roadmap={"fix_checks": {"mode": mode}})
    issue, pr_num = _drafted_delivery(store)
    held = store.item(issue)
    assert held is not None
    check = "Tests & Coverage"
    if "result" in record:
        store.set_marks(
            held,
            {
                FixChecksRecordKey.KEY: f"{HEAD_FAIL}:{check}",
                FixChecksRecordKey.RESULT: record["result"],
            },
        )
    if "outcome" in record:
        unit = {"attempt": record.get("attempt", 1), "outcome": record["outcome"]}
        units = json.dumps({f"{pr_num}:{HEAD_FAIL}:{check}": unit})
        store.set_marks(held, {FixChecksRecordKey.UNITS: units})

    _rounds(
        store,
        github_api,
        tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME,
        [_delivery_node(pr_num, issue)],
    )

    assert _stop_facts(store, issue) == ("Blocked", "pull request", "test", "stopped", 1)


def test_a_failed_test_check_of_a_delivery_draft_in_mode_on_gets_a_fix_unit_and_no_stop(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config: Any,
) -> None:
    """In mode `on` a fix-checks unit owns a failed check of the class test while the unit of the
    head and the check has not ended, so the row hands the unit to the fix round and does not stop
    the item (#6559)."""
    from devops_cli.roadmap import watch_row
    from devops_cli.roadmap.fix_checks_row import FixChecksRound

    config(roadmap={"fix_checks": {"mode": "on"}})
    issue, pr_num = _drafted_delivery(store)
    handed: list[tuple[int, str, str]] = []

    def fix_round(repo: str, due: Sequence[Any], **kwargs: Any) -> FixChecksRound:
        handed.extend((unit.pull, unit.head, unit.check) for unit in due)
        return FixChecksRound()

    monkeypatch.setattr(watch_row, "run_fix_checks_round", fix_round)

    _rounds(
        store,
        github_api,
        tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME,
        [_delivery_node(pr_num, issue)],
    )

    assert (handed, _stop_facts(store, issue)) == (
        [(pr_num, HEAD_FAIL, "Tests & Coverage")],
        _NOT_STOPPED,
    )


@pytest.mark.parametrize("claim", ["item", "pull"])
def test_a_claimed_delivery_draft_gets_no_stop(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path, claim: str
) -> None:
    """An owner label on the item or on its pull request claims the draft, as the step
    `fix-checks` reads it, so the row leaves a cancelled check of a claimed draft to the claimant
    (#6559)."""
    issue, pr_num = _drafted_delivery(store)
    if claim == "item":
        store.add_label(issue, "owner/human")
    node = _delivery_node(
        pr_num,
        issue,
        check_conclusion="CANCELLED",
        labels=("owner/agent",) if claim == "pull" else (),
    )

    _rounds(store, github_api, tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME, [node])

    assert _stop_facts(store, issue)[1:] == _NOT_STOPPED[1:]


@pytest.mark.parametrize("staged", [False, True], ids=["delivery", "staged"])
def test_a_stopped_delivery_draft_gets_no_ready_mark_when_its_checks_pass(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config: Any,
    staged: bool,
) -> None:
    """The stop writes `implement.result` stopped, as the stop flow of the Job does, so a person
    who runs a cancelled check again does not get the stopped draft marked ready: the item stays
    Blocked and its pull request stays a draft until the stop is cleared (#6559)."""
    from devops_cli.roadmap import watch_row

    config(roadmap={"fix_checks": {"mode": "on"}})
    issue, pr_num = _drafted_delivery(store, staged=staged)
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        watch_row, "run_fix_checks", lambda store, repo, pull, **kwargs: calls.append(("fix", pull))
    )
    monkeypatch.setattr(
        watch_row, "read_ready_draft", lambda repo, pull, **kwargs: calls.append(("plan", pull))
    )
    nodes = [
        _delivery_node(pr_num, issue, head=HEAD_PASS, check_conclusion="CANCELLED"),
        _delivery_node(
            pr_num, issue, head=HEAD_PASS, check_state="SUCCESS", check_conclusion="SUCCESS"
        ),
    ]

    results = _rounds(store, github_api, tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME, nodes)

    assert (calls, results[-1].marked_ready, _stop_facts(store, issue)) == (
        [],
        (),
        ("Blocked", "pull request", "ci_infra", "stopped", 1),
    )


def test_a_cancelled_run_beside_a_newer_passing_run_of_the_same_check_stops_nothing(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each event of a pull request starts its checks in a new suite, so the rollup can hold an
    old cancelled run beside the newer run that replaced it. The row judges only the latest run of
    each check name, as the REST read does (#5383), so the draft gets the ready path and no stop
    (#6559)."""
    from devops_cli.roadmap import watch_row
    from devops_cli.roadmap.steps.fix_checks import FixChecksReport
    from devops_cli.roadmap.stores.store import FixChecksResult

    issue, pr_num = _drafted_delivery(store)
    calls: list[int] = []

    def ready_path(store: Any, repo: str, pull: int, **kwargs: Any) -> FixChecksReport:
        calls.append(pull)
        return FixChecksReport(repo=repo, pull=pull, result=FixChecksResult.PLANNED)

    monkeypatch.setattr(watch_row, "run_fix_checks", ready_path)
    runs = [
        ("CANCELLED", "2026-11-20T10:00:00Z", "2026-11-20T10:01:00Z"),
        ("SUCCESS", "2026-11-20T10:02:00Z", "2026-11-20T10:09:00Z"),
    ]
    contexts = [
        {
            "__typename": "CheckRun",
            "name": "Fail-to-Pass Check",
            "status": "COMPLETED",
            "conclusion": conclusion,
            "startedAt": started,
            "completedAt": completed,
        }
        for conclusion, started, completed in runs
    ]
    node = _delivery_node(pr_num, issue, head=HEAD_PASS, check_state="SUCCESS", contexts=contexts)

    _rounds(store, github_api, tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME, [node])

    assert (calls, _stop_facts(store, issue)) == ([pr_num], _NOT_STOPPED)


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
    pr_num = store.seed_pull("plan: my plan", head_ref=f"feat/{issue_num}-test", draft=True)
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
    _route_draft(github_api, pr_num, f"feat/{issue_num}-test")

    # Route ready mark (gh pr ready runs via run_gh or client)
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME
    res = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
    assert pr_num in res.marked_ready

    # store updated with stage.ready
    updated_item = store.item(issue_num)
    assert updated_item is not None
    assert updated_item.job_record.get(StageRecordKey.READY) == str(pr_num)


def test_watch_row_leaves_an_implement_draft_with_an_unticked_task_group_a_draft(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    tmp_path: Path,
) -> None:
    """#6041: the plan branch of the item is also its implement branch, so the record holds the
    pull request as `stage.pr` and as `implement.pr`. Its checks pass and task group 5 is not
    ticked. `draft_readiness` refuses it, so the watch row sends no `gh pr ready` and records no
    `stage.ready`, also in a second round (#6123)."""
    issue = store.seed_issue("Onboard checks", fields={ItemField.PRIORITY: "P2-Medium"})
    branch = f"feat/{issue}-onboard-checks"
    pull = store.seed_pull("feat(roadmap): Add the sample", head_ref=branch, draft=True)
    item = store.item(issue)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pull), ImplementRecordKey.PR: str(pull)})
    node = _graphql_pr_node(
        number=pull,
        head=HEAD_PASS,
        is_draft=True,
        author="devops-cli-service[bot]",
        check_state="SUCCESS",
        check_conclusion="SUCCESS",
    )
    _route_graphql(github_api, [node])
    tasks = f"openspec/changes/archive/2026-11-17-{issue}-onboard-checks/tasks.md"
    _route_draft(github_api, pull, branch, tasks=(tasks, TASKS_GROUP_5_UNTICKED))
    ledger_path = tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME

    first = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)
    second = watch_round(store, repo=REPO, ledger_path=ledger_path, now=NOW)

    _, gh = github_api_and_gh
    assert (first.marked_ready, second.marked_ready) == ((), ())
    assert [call.argv for call in gh.calls if call.argv[1:3] == ("pr", "ready")] == []
    updated = store.item(issue)
    assert updated is not None
    assert updated.job_record.get(StageRecordKey.READY) is None


def test_watch_row_holds_the_ready_mark_of_a_plan_that_a_verdict_sent_back(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A green plan draft with a verdict label other than `verdict/mergeable` stays a draft, so
    the review step and the watch row do not undo each other (#6024)."""
    issue_num = store.seed_issue("Plan Issue", fields={ItemField.PRIORITY: "P2-Medium"})
    pr_num = store.seed_pull("plan: my plan", head_ref=f"feat/{issue_num}-test", draft=True)
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
        labels=("verdict/issue-changed",),
    )
    _route_graphql(github_api, [node])

    res = watch_round(
        store, repo=REPO, ledger_path=tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME, now=NOW
    )

    assert pr_num not in res.marked_ready
    updated = store.item(issue_num)
    assert updated is not None
    assert updated.job_record.get(StageRecordKey.READY) is None


def test_watch_row_comments_on_person_conflict(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A conflicting delivery PR from a person gets one conflict comment that names its head."""
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


def test_watch_row_edits_the_conflict_comment_of_an_older_head_in_place(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The pull request holds the conflict comment of an older head. A conflict at a new head
    edits that comment with the new head and posts no second comment, so the pull request holds
    one conflict comment (#6199)."""
    issue_num = store.seed_issue("Conflict Issue", fields={ItemField.PRIORITY: "P2-Medium"})
    pr_num = store.seed_pull("feat: delivery PR", head_ref="feat/conflict")
    old_note = MESSAGES.roadmap.pr_conflicts_comment.format(
        number=pr_num, base="main", head=HEAD_FAIL[:12]
    )
    node = _graphql_pr_node(
        number=pr_num,
        head=HEAD_NEW,
        mergeable="CONFLICTING",
        body=f"Closes #{issue_num}",
        check_state="SUCCESS",
        check_conclusion="SUCCESS",
    )
    _route_graphql(github_api, [node])
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    github_api.route(
        "GET",
        f"/repos/{REPO}/issues/{pr_num}/comments?per_page=100",
        github_json(
            [
                {"id": 7, "body": "A review of a person.", "user": {"login": "reviewer"}},
                {"id": 8, "body": old_note, "user": {"login": "octocat"}},
            ]
        ),
    )
    github_api.route("PATCH", f"/repos/{REPO}/issues/comments/8", github_json({"id": 8}))

    res = watch_round(
        store, repo=REPO, ledger_path=tmp_path / CONST_ROADMAP_WATCH_LEDGER_FILENAME, now=NOW
    )

    writes = [
        (sent.method, sent.url.path, json.loads(sent.content)["body"])
        for sent in github_api.sent
        if sent.method in {"POST", "PATCH"} and "/graphql" not in sent.url.path
    ]
    new_note = MESSAGES.roadmap.pr_conflicts_comment.format(
        number=pr_num, base="main", head=HEAD_NEW[:12]
    )
    assert (pr_num in res.commented_conflicts, writes) == (
        True,
        [("PATCH", f"/repos/{REPO}/issues/comments/8", new_note)],
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
    pr_num = store.seed_pull("plan: plan pr", head_ref=f"feat/{issue_num}-test", draft=True)
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
    _route_draft(github_api, pr_num, f"feat/{issue_num}-test")

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
    pr_num = store.seed_pull("plan: plan pr", head_ref=f"feat/{issue_num}-test", draft=True)
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
    _route_draft(github_api, pr_num, f"feat/{issue_num}-test")

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
