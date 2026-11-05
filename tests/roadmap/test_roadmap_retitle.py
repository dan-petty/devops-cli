"""`devops roadmap retitle` (#3486): the job shortens the long title of an open item, keeps its
type and scope, takes the summary of a Planned item from its plan pull request with no model call,
and leaves a title that a person changed. Intake refuses a new candidate with a long summary."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_RETITLE_COMMENT_MARKER
from devops_cli.exceptions.validation import ValidationError
from devops_cli.roadmap.inbox import InboxKind, read_inbox
from devops_cli.roadmap.intake import NewCandidate
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS, summary_length, title_problems
from devops_cli.roadmap.retitle import (
    RetitleReply,
    apply_retitle,
    plan_retitle,
    render_retitle_plan,
)
from devops_cli.roadmap.store import ItemField, StageRecordKey

REPO = "example/roadmap"
LONG = "Shorten the title of an item that a job leaves out because it is too long"
OLD = f"fix(roadmap): {LONG}"
NEW_SUMMARY = "Shorten the long title of an item"


class Clock:
    """A clock that a test moves, so that the order of events is exact."""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


class FakeModel:
    """Records each request and answers from a list of summaries, the last one repeated."""

    def __init__(self, *summaries: str) -> None:
        self.requests: list[str] = []
        self._summaries = list(summaries) or [NEW_SUMMARY]

    def summarize(self, request: str) -> RetitleReply:
        self.requests.append(request)
        index = min(len(self.requests), len(self._summaries)) - 1
        return RetitleReply(summary=self._summaries[index])


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO, clock=Clock())


def _item(store: InMemoryRoadmapStore, title: str = OLD, status: str = "Ready") -> int:
    return store.seed_issue(
        title,
        body="It asks for one change.",
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: status},
    )


def _planned(store: InMemoryRoadmapStore, plan_title: str | None) -> int:
    number = _item(store, status="Planned")
    pull = store.seed_pull(
        plan_title or "docs(openspec): not a plan title", head_ref=f"docs/{number}-plan"
    )
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pull)})
    return number


def _title(store: InMemoryRoadmapStore, number: int) -> str:
    item = store.item(number)
    assert item is not None
    return item.title


def test_a_plan_lists_the_new_title_and_writes_nothing(store: InMemoryRoadmapStore) -> None:
    number = _item(store)
    model = FakeModel()

    plan = plan_retitle(store, repo=REPO, model=model, limit=None)

    assert [(c.item.number, c.title) for c in plan.changes] == [
        (number, f"fix(roadmap): {NEW_SUMMARY}")
    ]
    assert f"`{OLD}` becomes `fix(roadmap): {NEW_SUMMARY}`" in render_retitle_plan(plan)
    assert _title(store, number) == OLD
    assert store.job_writes() == []


def test_confirm_writes_the_title_and_one_comment(store: InMemoryRoadmapStore) -> None:
    number = _item(store)
    plan = plan_retitle(store, repo=REPO, model=FakeModel())

    written = apply_retitle(store, plan)

    assert written == 1
    assert _title(store, number) == f"fix(roadmap): {NEW_SUMMARY}"
    comments = store.comments_on(number)
    assert len(comments) == 1
    assert CONST_ROADMAP_RETITLE_COMMENT_MARKER in comments[0].body
    assert OLD in comments[0].body
    # The job does not select the item again.
    assert plan_retitle(store, repo=REPO, model=FakeModel()).changes == ()


def test_the_pass_keeps_the_type_and_the_scope_and_the_new_title_passes_the_form(
    store: InMemoryRoadmapStore,
) -> None:
    kinds = {
        "feat(k8s)": _item(store, f"feat(k8s): {LONG}"),
        "fix": _item(store, f"fix: {LONG}"),
        "docs(roadmap)": _item(store, f"docs(roadmap): {LONG}"),
    }

    plan = plan_retitle(store, repo=REPO, model=FakeModel())

    assert len(plan.changes) == 3
    for change in plan.changes:
        prefix = next(k for k, n in kinds.items() if n == change.item.number)
        assert change.title.startswith(f"{prefix}: ")
        assert summary_length(change.title.partition(": ")[2]) <= SUMMARY_MAX_CHARS
        assert title_problems(change.title) == []


def test_a_title_with_a_short_summary_is_not_selected(store: InMemoryRoadmapStore) -> None:
    _item(store, "fix(roadmap): a short summary")
    model = FakeModel()

    plan = plan_retitle(store, repo=REPO, model=model)

    assert (plan.changes, plan.skips, model.requests) == ((), (), [])


def test_a_reply_that_fails_the_form_gets_one_more_request_with_its_faults(
    store: InMemoryRoadmapStore,
) -> None:
    _item(store)
    model = FakeModel(LONG, NEW_SUMMARY)

    plan = plan_retitle(store, repo=REPO, model=model)

    assert [c.title for c in plan.changes] == [f"fix(roadmap): {NEW_SUMMARY}"]
    assert len(model.requests) == 2
    assert "The limit is 60" in model.requests[1]


def test_two_replies_that_fail_the_form_leave_the_item(store: InMemoryRoadmapStore) -> None:
    number = _item(store)
    model = FakeModel(LONG)

    plan = plan_retitle(store, repo=REPO, model=model)

    assert plan.changes == ()
    assert [s.item.number for s in plan.skips] == [number]
    assert len(model.requests) == 2
    assert apply_retitle(store, plan) == 0
    assert store.comments_on(number) == []


def test_a_planned_item_takes_the_summary_of_its_plan_title_with_no_model_call(
    store: InMemoryRoadmapStore,
) -> None:
    number = _planned(store, "docs(openspec): plan #1 Add a title repair pass")
    model = FakeModel()

    plan = plan_retitle(store, repo=REPO, model=model)

    assert [c.title for c in plan.changes] == ["fix(roadmap): Add a title repair pass"]
    assert [c.item.number for c in plan.changes] == [number]
    assert model.requests == []


def test_a_planned_item_without_a_usable_plan_title_is_left_with_a_comment_and_no_model_call(
    store: InMemoryRoadmapStore,
) -> None:
    number = _planned(store, None)
    model = FakeModel()

    plan = plan_retitle(store, repo=REPO, model=model)

    assert plan.changes == ()
    assert [s.item.number for s in plan.skips] == [number]
    assert model.requests == []
    apply_retitle(store, plan)
    apply_retitle(store, plan)
    assert _title(store, number) == OLD
    assert len(store.comments_on(number)) == 1  # the second pass adds no second comment


def test_a_planned_item_with_no_recorded_plan_is_left_and_the_model_stays_unused(
    store: InMemoryRoadmapStore,
) -> None:
    _item(store, status="Planned")
    model = FakeModel()

    plan = plan_retitle(store, repo=REPO, model=model)

    assert (plan.changes, len(plan.skips), model.requests) == ((), 1, [])


def test_a_title_that_a_person_changed_after_the_last_job_comment_stays(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store)
    store.comment(number, "<!-- devops roadmap intake: reason -->\nPlaced.")
    store.rename_by_hand(number, f"fix(roadmap): {LONG} again")
    model = FakeModel()

    plan = plan_retitle(store, repo=REPO, model=model)

    assert plan.changes == ()
    assert [s.item.number for s in plan.skips] == [number]
    assert "A person changed the title" in plan.skips[0].reason
    assert model.requests == []


def test_a_title_that_a_person_changed_before_the_last_job_comment_is_shortened(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store)
    store.rename_by_hand(number, OLD)
    store.comment(number, "<!-- devops roadmap intake: reason -->\nPlaced.")

    plan = plan_retitle(store, repo=REPO, model=FakeModel())

    assert [c.item.number for c in plan.changes] == [number]


def test_a_title_that_changed_after_the_plan_read_it_is_not_written(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store)
    plan = plan_retitle(store, repo=REPO, model=FakeModel())
    store.rename_by_hand(number, "fix(roadmap): a person wrote this")

    assert apply_retitle(store, plan) == 0
    assert _title(store, number) == "fix(roadmap): a person wrote this"


def test_the_limit_caps_the_items_and_the_report_counts_the_rest(
    store: InMemoryRoadmapStore,
) -> None:
    first, _second = _item(store), _item(store)

    plan = plan_retitle(store, repo=REPO, model=FakeModel(), limit=1)

    assert [c.item.number for c in plan.changes] == [first]
    assert plan.left == 1
    assert "1 more item(s)" in render_retitle_plan(plan)


def test_the_inbox_lists_a_blocked_item_whose_title_summary_is_over_the_limit(
    store: InMemoryRoadmapStore,
) -> None:
    from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH

    store.seed_file(CONST_ROADMAP_LABELS_PATH, "- name: type/bug\n  color: D73A4A\n")
    store.seed_label("type/bug", "D73A4A")
    number = _item(store, status="Blocked")

    inbox = read_inbox(store, repo=REPO, now=datetime(2026, 11, 5, tzinfo=UTC))

    assert [line.number for line in inbox.jobs if line.kind is InboxKind.BLOCKED] == [number]


def test_a_new_candidate_with_a_summary_over_the_limit_is_refused() -> None:
    candidate = NewCandidate(title="fix(roadmap): " + "x" * 61, body="Body.")

    with pytest.raises(ValidationError, match=r"61 characters.*limit is 60"):
        candidate.refuse_long_summary()


def test_a_new_candidate_with_a_summary_at_the_limit_is_kept() -> None:
    candidate = NewCandidate(title="fix(roadmap): " + "x" * 60, body="Body.")

    assert candidate.refuse_long_summary() is None


def test_the_intake_command_refuses_a_long_summary_and_writes_no_issue(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    body = tmp_path / "body.md"
    body.write_text("A body that is long enough.", encoding="utf-8")

    result = cli(
        "roadmap", "intake", "--repo", REPO, "--title", "fix(roadmap): " + "x" * 61,
        "--body-file", str(body), "--confirm",
    )  # fmt: skip

    assert result.exit_code == 1
    assert "61" in result.output
    assert "60" in result.output
    assert roadmap_store.issues() == []
    assert roadmap_store.job_writes() == []


def test_the_retitle_command_prints_the_titles_and_writes_only_with_confirm(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("devops_cli.roadmap.retitle.build_retitle_model", FakeModel)
    number = _item(roadmap_store)

    preview = cli("roadmap", "retitle", "--repo", REPO)
    assert preview.exit_code == 0, preview.output
    assert NEW_SUMMARY in preview.stdout
    assert _title(roadmap_store, number) == OLD

    written = cli("roadmap", "retitle", "--repo", REPO, "--confirm")
    assert written.exit_code == 0, written.output
    assert _title(roadmap_store, number) == f"fix(roadmap): {NEW_SUMMARY}"


def test_the_retitle_dry_run_makes_no_request(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
) -> None:
    result = cli("roadmap", "retitle", "--repo", REPO, "--dry-run")

    assert result.exit_code == 0, result.output
    assert roadmap_store_repos == []
