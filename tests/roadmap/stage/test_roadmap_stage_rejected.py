"""`devops roadmap stage`: a plan pull request that a person closed with no merge leaves its reason
on the issue, returns the item to New and holds it until its text or a named file changes (#3503)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_REJECTED_MARKER,
)
from devops_cli.exceptions import GitHubUnauthenticatedError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.stage.stage import (
    StagePlan,
    StageSelection,
    parse_filters,
    plan_stage,
    read_stage_selection,
    render_stage_plan,
)
from devops_cli.roadmap.stage.stage_rejected import (
    EVIDENCE_MIN_CHARS,
    RejectedPlan,
    recorded_rejection,
)
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_NAME,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    no_findings,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from devops_cli.roadmap.stores.store import Item
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

BRANCH = "fix/1-the-job-drops-a-comment"
CLOSED_AT = datetime(2026, 11, 2, 20, 22, 45, tzinfo=UTC)
SERVICE = f"{STAGE_NAME}"
EVIDENCE = (
    "The premise does not hold: `src/devops_cli/roadmap/runner_tools.py` names `bwrap` in "
    "`NOT_IN_RUNNER`, so the runner can run no review. I ran the command and it failed closed."
)
OTHER_EVIDENCE = "The plan repeats the check that `docs/roadmap/stage.md` already states."


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    return openspec_fake


@pytest.fixture(autouse=True)
def service_app(config: Callable[..., object]) -> None:
    """The Service App has the bot login `devops-roadmap[bot]`."""
    config(service={"github_app": {"slug": "devops-roadmap"}})


def _pull_state(
    api: GitHubApiFake, pull: int, *, state: str = "closed", merged: bool = False
) -> None:
    """Answer the read of plan pull request `pull`."""
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{pull}",
        github_json(
            {
                "state": state,
                "merged": merged,
                "draft": False,
                "closed_at": CLOSED_AT.isoformat() if state == "closed" else None,
                "head": {"sha": "abc", "ref": BRANCH},
            }
        ),
    )


def _staged(
    store: InMemoryRoadmapStore,
    api: GitHubApiFake,
    *,
    state: str = "closed",
    merged: bool = False,
    body: str = "The job drops the last comment of a thread.",
    status: str = "Ready",
    hashed: bool = True,
) -> tuple[int, int]:
    """A staged item with the plan pull request it records, and the two numbers. The pull request
    is marked ready, as the row `stage_ready` leaves it. The record holds the hash of the text that
    the plan came from, as `_stage_one` writes it, unless `hashed` is False."""
    number = seed_stageable(store, body=body)
    if status != "Ready":
        store.set_field(_item(store, number), ItemField.STATUS, status)
    pull = store.seed_pull("docs(openspec): plan #1 the job drops a comment", head_ref=BRANCH)
    store.set_marks(
        _item(store, number),
        {
            StageRecordKey.BRANCH: BRANCH,
            StageRecordKey.PR: str(pull),
            StageRecordKey.READY: str(pull),
            StageRecordKey.SHA: "abc",
            StageRecordKey.GROUPS: json.dumps([["Group", 100]]),
            StageRecordKey.TEXT_HASH: body_hashes(body)[0] if hashed else None,
        },
    )
    _pull_state(api, pull, state=state, merged=merged)
    return number, pull


def _item(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _comment(
    store: InMemoryRoadmapStore,
    pull: int,
    text: str,
    *,
    login: str = "alice",
    association: str = "OWNER",
) -> None:
    store.seed_comment(pull, text, author_association=association, author_login=login)


def _round(store: InMemoryRoadmapStore, repo: StageRepo) -> StagePlan:
    """The plan of a round that names no item to stage, so only the rejections are judged."""
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(("status=ready", "type=docs")),
    )


def _applied(store: InMemoryRoadmapStore, repo: StageRepo) -> tuple[StagePlan, tuple[int, ...]]:
    plan = _round(store, repo)
    return plan, apply_stage(store, plan, source=repo.clone).rejected


def _branches(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


def _last_comment(store: InMemoryRoadmapStore, number: int) -> str:
    return store.comments_on(number)[-1].body


def _record(store: InMemoryRoadmapStore, number: int) -> dict[str, str]:
    return {
        key.value: value
        for key, value in _item(store, number).job_record.items()
        if key.value.startswith("stage.") and value is not None
    }


# ── The reason reaches the issue ──────────────────────────────────────────────


def test_a_plan_closed_with_no_merge_leaves_its_last_long_comment_on_the_issue(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, OTHER_EVIDENCE)
    _comment(store, pull, EVIDENCE)
    _comment(store, pull, "rejected")
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    plan, rejected = _applied(store, stage_repo)

    comment = _last_comment(store, number)
    assert [r.number for r in plan.rejections] == [number]
    assert rejected == (number,)
    assert CONST_ROADMAP_STAGE_COMMENT_MARKER in comment
    assert CONST_ROADMAP_STAGE_REJECTED_MARKER in comment
    assert f"#{pull}" in comment
    assert f"> {EVIDENCE}" in comment
    assert OTHER_EVIDENCE not in comment
    assert "> rejected" not in comment


def test_a_rejected_plan_returns_the_item_to_new_and_records_the_rejection(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    _applied(store, stage_repo)

    item = _item(store, number)
    rejected = recorded_rejection(item)
    assert item.status == "New"
    assert set(_record(store, number)) == {StageRecordKey.REJECTED.value}
    assert rejected == RejectedPlan(
        pull=pull,
        text_hash=body_hashes(item.body)[0],
        closed_at=CLOSED_AT,
        paths=("src/devops_cli/roadmap/runner_tools.py",),
    )


def test_an_item_that_a_person_already_returned_stays_new_and_gets_the_comment(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api, status="New")
    _comment(store, pull, EVIDENCE)

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(("status=new",)),
    )
    apply_stage(store, plan, source=stage_repo.clone)

    assert _item(store, number).status == "New"
    assert f"> {EVIDENCE}" in _last_comment(store, number)
    assert set(_record(store, number)) == {StageRecordKey.REJECTED.value}


def test_the_last_comment_of_the_service_bot_or_of_an_outsider_is_no_reason(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)
    _comment(store, pull, "x" * (EVIDENCE_MIN_CHARS + 20), login=SERVICE, association="CONTRIBUTOR")
    _comment(store, pull, "y" * (EVIDENCE_MIN_CHARS + 20), login="stranger", association="NONE")

    _applied(store, stage_repo)

    comment = _last_comment(store, number)
    assert f"> {EVIDENCE}" in comment
    assert "xxxx" not in comment
    assert "yyyy" not in comment


def test_a_comment_of_a_roadmap_job_on_the_pull_request_is_no_reason(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)
    _comment(store, pull, f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\n" + "z" * 100)

    _applied(store, stage_repo)

    assert f"> {EVIDENCE}" in _last_comment(store, number)


def test_a_comment_of_the_minimum_length_is_no_reason_and_a_longer_one_is(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, "a" * (EVIDENCE_MIN_CHARS + 1))
    _comment(store, pull, "b" * EVIDENCE_MIN_CHARS)

    _applied(store, stage_repo)

    comment = _last_comment(store, number)
    assert "a" * (EVIDENCE_MIN_CHARS + 1) in comment
    assert "bbbb" not in comment


def test_a_plan_with_no_long_comment_gets_a_comment_that_says_so_and_is_recorded(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, "rejected")

    _plan, rejected = _applied(store, stage_repo)

    assert rejected == (number,)
    assert MESSAGES.roadmap.stage_rejected_no_reason in _last_comment(store, number)
    recorded = recorded_rejection(_item(store, number))
    assert recorded is not None
    assert (recorded.pull, recorded.paths) == (pull, ())


@pytest.mark.parametrize(("state", "merged"), [("open", False), ("closed", True)])
def test_an_open_or_merged_plan_pull_request_is_no_rejection(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    state: str,
    merged: bool,
) -> None:
    number, pull = _staged(store, github_api, state=state, merged=merged)
    _comment(store, pull, EVIDENCE)
    before = list(store.comments_on(number))

    plan, rejected = _applied(store, stage_repo)

    assert (plan.rejections, rejected) == ((), ())
    assert store.comments_on(number) == before
    assert StageRecordKey.REJECTED.value not in _record(store, number)
    assert _item(store, number).status == "Ready"


def test_a_secret_in_the_reason_is_masked_and_the_reason_is_cut_to_the_reply_cap(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    token = "ghp_" + "a1B2c3D4e5" * 4
    _comment(store, pull, f"{EVIDENCE} The token {token} leaked. " + "word " * 20000)

    _applied(store, stage_repo)

    comment = _last_comment(store, number)
    assert token not in comment
    assert len(comment) < CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS * 8


def test_the_plan_report_lists_the_rejection_and_the_branch_that_the_job_deletes(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    report = render_stage_plan(_round(store, stage_repo))

    assert MESSAGES.roadmap.stage_heading_rejected in report
    assert f"- #{number}: pull request #{pull} closed with no merge" in report
    assert f"`{BRANCH}`" in report


# ── The staged branch ─────────────────────────────────────────────────────────


def test_the_staged_branch_of_a_rejected_plan_goes_when_only_the_session_wrote_to_it(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)

    plan, _ = _applied(store, stage_repo)

    assert plan.kept == ()
    assert _branches(stage_repo) == ["main"]


def test_the_staged_branch_of_a_rejected_plan_stays_when_another_author_wrote_to_it(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)
    stage_repo.push_branch(BRANCH, author="Person")

    plan, rejected = _applied(store, stage_repo)

    assert [(k.number, k.branch) for k in plan.kept] == [(number, BRANCH)]
    assert rejected == (number,)
    assert _branches(stage_repo) == [BRANCH, "main"]
    assert f"> {EVIDENCE}" in _last_comment(store, number)
    assert set(_record(store, number)) == {StageRecordKey.REJECTED.value}


def test_a_commit_pushed_after_the_plan_keeps_the_branch_and_the_rest_is_still_written(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)
    plan = _round(store, stage_repo)

    stage_repo.push_branch(BRANCH, author="Person")
    applied = apply_stage(store, plan, source=stage_repo.clone)

    assert applied.rejected == (number,)
    assert applied.failed == ()
    assert _branches(stage_repo) == [BRANCH, "main"]
    assert f"> {EVIDENCE}" in _last_comment(store, number)
    assert set(_record(store, number)) == {StageRecordKey.REJECTED.value}


def test_a_branch_that_is_gone_needs_no_delete(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)

    plan, rejected = _applied(store, stage_repo)

    assert ([r.branch for r in plan.rejections], plan.kept, rejected) == ([None], (), (number,))


# ── The hold ──────────────────────────────────────────────────────────────────


def _rejected_item(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    api: GitHubApiFake,
    *,
    body: str = "The job drops the last comment of a thread.",
) -> int:
    """A Ready item after a round wrote its rejected plan, and refine set it Ready again."""
    number, pull = _staged(store, api, body=body)
    _comment(store, pull, EVIDENCE)
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)
    _applied(store, stage_repo)
    store.set_field(_item(store, number), ItemField.STATUS, "Ready")
    return number


def _selection(
    store: InMemoryRoadmapStore, repo: StageRepo, *, item: int | None = None
) -> StageSelection:
    return read_stage_selection(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(("status=ready",)),
        limit=3,
        planned_limit=20,
        item_number=item,
    ).selection


def test_the_job_leaves_out_an_item_whose_plan_was_rejected_and_names_the_pull_request(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = _rejected_item(store, stage_repo, github_api)
    rejected = recorded_rejection(_item(store, number))
    assert rejected is not None

    selection = _selection(store, stage_repo)

    reasons = {left.number: left.reason for left in selection.left_out}
    assert selection.selected == ()
    assert reasons == {number: MESSAGES.roadmap.stage_left_rejected.format(pull=rejected.pull)}


def test_a_body_edit_ends_the_hold_and_the_deleted_branch_holds_nothing(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = _rejected_item(store, stage_repo, github_api)

    store.write_issue_body(
        number, "The job drops the last comment of a thread, but only in a reply."
    )
    selection = _selection(store, stage_repo)

    assert [target.item.number for target in selection.selected] == [number]
    assert selection.left_out == ()
    assert _branches(stage_repo) == ["main"]


def test_a_rewrite_of_the_section_of_refine_does_not_end_the_hold(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    section = "<!-- devops-roadmap-refine:start -->\n{}\n<!-- devops-roadmap-refine:end -->"
    text = "The job drops the last comment of a thread."
    number = _rejected_item(store, stage_repo, github_api, body=f"{text}\n{section.format('one')}")

    store.write_issue_body(number, f"{text}\n{section.format('two')}")
    selection = _selection(store, stage_repo)

    assert selection.selected == ()
    assert [left.number for left in selection.left_out] == [number]


def test_an_edit_made_before_the_first_look_of_the_job_ends_the_hold(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    store.write_issue_body(number, "The job drops the last comment of a thread, in a reply only.")
    _comment(store, pull, EVIDENCE)
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)
    _applied(store, stage_repo)
    store.set_field(_item(store, number), ItemField.STATUS, "Ready")

    selection = _selection(store, stage_repo)

    assert [target.item.number for target in selection.selected] == [number]


def test_a_record_with_no_hash_of_the_planned_text_holds_from_the_text_of_the_first_look(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api, hashed=False)
    _comment(store, pull, EVIDENCE)
    _applied(store, stage_repo)
    store.set_field(_item(store, number), ItemField.STATUS, "Ready")

    assert _selection(store, stage_repo).selected == ()


def test_a_commit_that_changed_a_file_the_reason_names_ends_the_hold(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = _rejected_item(store, stage_repo, github_api)
    store.seed_commit("src/devops_cli/roadmap/runner_tools.py", at=CLOSED_AT - timedelta(days=1))
    held = _selection(store, stage_repo)

    store.seed_commit("src/devops_cli/roadmap/runner_tools.py", at=CLOSED_AT + timedelta(hours=1))
    freed = _selection(store, stage_repo)

    assert held.selected == ()
    assert [target.item.number for target in freed.selected] == [number]


def test_a_commit_that_changed_another_file_does_not_end_the_hold(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _rejected_item(store, stage_repo, github_api)
    store.seed_commit("src/devops_cli/roadmap/other.py", at=CLOSED_AT + timedelta(hours=1))

    assert _selection(store, stage_repo).selected == ()


def test_a_person_who_names_the_item_takes_it_though_its_plan_was_rejected(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number = _rejected_item(store, stage_repo, github_api)

    selection = _selection(store, stage_repo, item=number)

    assert [target.item.number for target in selection.selected] == [number]


@pytest.mark.parametrize("pushed", [False, True], ids=["branch gone", "branch pushed"])
def test_a_run_that_names_the_item_stages_a_new_plan_and_the_item_stays_ready(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    model_fake: ModelFake,
    pushed: bool,
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)
    if pushed:
        stage_repo.push_branch(BRANCH, author=STAGE_NAME)
    github_api.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json({"number": 9, "html_url": "https://example.com/pull/9"}, status=201),
    )
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(("status=ready",)),
        item_number=number,
    )
    applied = apply_stage(store, plan, source=stage_repo.clone)

    assert applied.staged == (number,)
    assert _item(store, number).status == "Ready"
    assert _record(store, number)[StageRecordKey.PR.value] == "9"
    assert f"> {EVIDENCE}" in store.comments_on(number)[-2].body


def test_the_run_that_finds_a_rejection_leaves_the_item_out_though_its_branch_is_gone(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)

    plan = plan_stage(
        store, repo=STAGE_REPO, source=stage_repo.clone, filters=parse_filters(("status=ready",))
    )

    assert [r.number for r in plan.rejections] == [number]
    assert plan.ready == ()
    assert [left.number for left in plan.left_out] == [number]


def test_only_the_named_item_has_its_plan_pull_request_read(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    first, first_pull = _staged(store, github_api)
    store.add_label(first, "needs-split")
    _, second_pull = _staged_second(store, github_api)
    _comment(store, first_pull, EVIDENCE)
    _comment(store, second_pull, EVIDENCE)

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(("status=ready",)),
        item_number=first,
    )

    reads = [line for line in github_api.requested if "/pulls/" in line]
    assert [r.number for r in plan.rejections] == [first]
    assert reads == [f"GET https://api.github.com/repos/{STAGE_REPO}/pulls/{first_pull}"]


def test_an_item_whose_plan_is_on_the_default_branch_has_no_pull_request_read(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)
    stage_repo.track({f"openspec/changes/{number}-the-job-drops-a-comment/tasks.md": "# Tasks\n"})

    plan = _round(store, stage_repo)

    assert plan.rejections == ()
    assert [line for line in github_api.requested if "/pulls/" in line] == []


def test_a_plan_pull_request_that_cannot_be_read_fails_that_item_and_the_run_goes_on(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    number, pull = _staged(store, github_api)
    github_api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{pull}",
        github_json({"message": "Not Found"}, status=404),
    )
    other, other_pull = _staged_second(store, github_api)
    _comment(store, other_pull, EVIDENCE)

    plan = _round(store, stage_repo)

    assert [f.number for f in plan.failed] == [number]
    assert [r.number for r in plan.rejections] == [other]


def test_rejected_credentials_stop_the_run_at_the_read_of_a_plan_pull_request(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    _, pull = _staged(store, github_api)
    github_api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{pull}",
        github_json({"message": "Bad credentials"}, status=401),
    )

    with pytest.raises(GitHubUnauthenticatedError, match=re.escape("refused the session's token")):
        _round(store, stage_repo)


def _staged_second(store: InMemoryRoadmapStore, api: GitHubApiFake) -> tuple[int, int]:
    """A second staged item, the one the first number's read does not reach."""
    number = seed_stageable(store, "fix(roadmap): the job drops a label")
    pull = store.seed_pull("docs(openspec): plan #3", head_ref="fix/3-the-job-drops-a-label")
    store.set_marks(_item(store, number), {StageRecordKey.PR: str(pull)})
    _pull_state(api, pull)
    return number, pull


# ── The request ───────────────────────────────────────────────────────────────


def _requests(model_fake: ModelFake) -> list[dict[str, object]]:
    """The planner requests of the run, as JSON."""
    found: list[dict[str, object]] = []
    for call_ in model_fake.calls:
        try:
            request = json.loads(call_.prompt)
        except ValueError:
            continue
        if isinstance(request, dict) and "body" in request:
            found.append(request)
    return found


def test_the_plan_request_of_an_item_with_a_rejected_plan_holds_the_reason(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    model_fake: ModelFake,
) -> None:
    number = _rejected_item(store, stage_repo, github_api)
    store.write_issue_body(number, "The job drops the last comment of a thread, in a reply only.")
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())

    plan_stage(
        store, repo=STAGE_REPO, source=stage_repo.clone, filters=parse_filters(("status=ready",))
    )

    (request,) = _requests(model_fake)
    reason = str(request["rejected_plan"])
    assert EVIDENCE in reason
    assert CONST_ROADMAP_STAGE_COMMENT_MARKER not in reason
    assert CONST_ROADMAP_STAGE_REJECTED_MARKER not in reason


def test_the_plan_request_of_an_item_that_was_never_rejected_holds_no_such_key(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    seed_stageable(store)
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())

    plan_stage(
        store, repo=STAGE_REPO, source=stage_repo.clone, filters=parse_filters(("status=ready",))
    )

    (request,) = _requests(model_fake)
    assert "rejected_plan" not in request


def test_a_staged_plan_clears_the_record_of_the_rejection(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    model_fake: ModelFake,
) -> None:
    number = _rejected_item(store, stage_repo, github_api)
    edited = "The job drops the last comment of a thread, in a reply only."
    store.write_issue_body(number, edited)
    github_api.route(
        "POST",
        f"/repos/{STAGE_REPO}/pulls",
        github_json({"number": 9, "html_url": "https://example.com/pull/9"}, status=201),
    )
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())

    plan = plan_stage(
        store, repo=STAGE_REPO, source=stage_repo.clone, filters=parse_filters(("status=ready",))
    )
    apply_stage(store, plan, source=stage_repo.clone)

    record = _record(store, number)
    assert StageRecordKey.REJECTED.value not in record
    assert record[StageRecordKey.PR.value] == "9"
    assert record[StageRecordKey.TEXT_HASH.value] == body_hashes(edited)[0]


def test_the_request_of_a_run_that_names_the_item_holds_the_reason_that_the_run_finds(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    model_fake: ModelFake,
) -> None:
    number, pull = _staged(store, github_api)
    _comment(store, pull, EVIDENCE)
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(("status=ready",)),
        item_number=number,
    )

    (request,) = _requests(model_fake)
    assert [r.number for r in plan.rejections] == [number]
    assert [change.target.item.number for change in plan.ready] == [number]
    assert EVIDENCE in str(request["rejected_plan"])
