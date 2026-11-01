"""`read_inbox` (#2915): what waits for a person, in the order of the gates, each line with its
number, its age and the one step that clears it. A fake repository holds the issues, the pull
requests and the labels; no request leaves the process."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.exceptions.git import GitHubFileNotFoundError
from devops_cli.roadmap.inbox import Inbox, InboxKind, InboxLine, read_inbox, render_inbox
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import (
    GitHubState,
    ImplementRecordKey,
    ItemField,
    RefineRecordKey,
    StageRecordKey,
    encode_job_record,
    with_record,
)

REPO = "example/roadmap"
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
LABELS = "- name: type/bug\n  color: D73A4A\n  description: A defect\n"


def _ago(**span: float) -> datetime:
    return NOW - timedelta(**span)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    made = InMemoryRoadmapStore(repo=REPO, clock=lambda: NOW)
    made.seed_file(CONST_ROADMAP_LABELS_PATH, LABELS)
    made.seed_label("type/bug", "D73A4A", "A defect")
    return made


def _item(
    store: InMemoryRoadmapStore,
    title: str = "work",
    *,
    marks: Mapping[Any, str | None] | None = None,
    fields: Mapping[ItemField, str] | None = None,
    updated_at: datetime | None = None,
    state: GitHubState = GitHubState.OPEN,
) -> int:
    """An item of the roadmap whose job record holds `marks`."""
    block = encode_job_record({}, marks or {}) if marks else None
    return store.seed_issue(
        title,
        body=with_record("", block),
        fields={ItemField.PRIORITY: "P2-Medium", **(fields or {})},
        updated_at=updated_at,
        state=state,
    )


def _lines(inbox: Inbox, kind: InboxKind) -> list[InboxLine]:
    return [line for line in (*inbox.jobs, *inbox.people) if line.kind is kind]


def _read(store: InMemoryRoadmapStore) -> Inbox:
    return read_inbox(store, repo=REPO, now=NOW)


def test_every_category_is_listed_once_in_the_order_of_the_gates(
    store: InMemoryRoadmapStore,
) -> None:
    plan = store.seed_pull("plan", head_ref="feat/1-plan", updated_at=_ago(days=2))
    _item(store, marks={StageRecordKey.PR: str(plan)})
    work = store.seed_pull("work", head_ref="feat/2-work", updated_at=_ago(days=1))
    _item(store, marks={ImplementRecordKey.PR: str(work)})
    release = store.seed_pull(
        "release",
        head_ref="release-please--branches--main--components--x",
        updated_at=_ago(hours=3),
    )
    blocked = _item(
        store, fields={ItemField.STATUS: "Blocked"}, marks={ImplementRecordKey.STOPPED: "group 2"}
    )
    claimed = _item(store, fields={ItemField.OWNER: "Agent"}, updated_at=_ago(days=9))
    store.seed_file(CONST_ROADMAP_LABELS_PATH, LABELS + "- name: scope/ci\n  color: 0E8A16\n")

    inbox = _read(store)

    assert [(line.kind, line.number) for line in inbox.jobs] == [
        (InboxKind.PLAN, plan),
        (InboxKind.IMPLEMENT, work),
        (InboxKind.RELEASE, release),
        (InboxKind.BLOCKED, blocked),
        (InboxKind.CLAIM, claimed),
        (InboxKind.LABELS, None),
    ]
    assert inbox.people == ()


def test_a_draft_of_a_job_is_not_listed_and_is_not_a_persons_pull_request(
    store: InMemoryRoadmapStore,
) -> None:
    draft = store.seed_pull("plan", head_ref="feat/1-plan", draft=True)
    _item(store, marks={StageRecordKey.PR: str(draft)})
    inbox = _read(store)
    assert (inbox.jobs, inbox.people) == ((), ())


def test_one_pull_request_of_the_stage_and_the_implement_job_is_an_implementation(
    store: InMemoryRoadmapStore,
) -> None:
    shared = store.seed_pull("one pull request", head_ref="feat/1-work")
    _item(store, marks={StageRecordKey.PR: str(shared), ImplementRecordKey.PR: str(shared)})
    inbox = _read(store)
    assert [(line.kind, line.number) for line in inbox.jobs] == [(InboxKind.IMPLEMENT, shared)]


def test_a_pull_request_that_a_runner_job_holds_is_not_listed(
    store: InMemoryRoadmapStore,
) -> None:
    held = store.seed_pull("pushed to", head_ref="feat/1-work")
    _item(store, marks={StageRecordKey.PR: str(held), ImplementRecordKey.JOB: "runner-abc"})
    inbox = _read(store)
    assert (inbox.jobs, inbox.people) == ((), ())


def test_a_job_pull_request_of_a_closed_item_is_a_persons(store: InMemoryRoadmapStore) -> None:
    """The record of a closed item names a pull request that is open again or never merged; it
    is no job's work in progress, so it is listed as any other pull request."""
    stray = store.seed_pull("stray", head_ref="feat/1-work")
    _item(store, marks={ImplementRecordKey.PR: str(stray)}, state=GitHubState.CLOSED)
    inbox = _read(store)
    assert ([line.number for line in inbox.people], inbox.jobs) == ([stray], ())


def test_each_line_has_its_number_its_age_and_the_step_that_clears_it(
    store: InMemoryRoadmapStore,
) -> None:
    plan = store.seed_pull("plan", head_ref="feat/1-plan", updated_at=_ago(days=2, hours=3))
    _item(store, marks={StageRecordKey.PR: str(plan)})
    work = store.seed_pull("work", head_ref="feat/2-work")
    _item(store, marks={ImplementRecordKey.PR: str(work)})
    release = store.seed_pull("release", head_ref="release-please--branches--main")
    claimed = _item(store, fields={ItemField.OWNER: "Human"}, updated_at=_ago(days=8))
    store.seed_file(CONST_ROADMAP_LABELS_PATH, LABELS + "- name: scope/ci\n  color: 0E8A16\n")

    inbox = _read(store)
    clears = {line.kind: line.clear for line in inbox.jobs}

    assert inbox.jobs[0].age == timedelta(days=2, hours=3)
    assert clears[InboxKind.PLAN] == f"Review it, then merge it (G1): {_url(plan)}"
    assert clears[InboxKind.IMPLEMENT] == f"Review it, then merge it (G2): {_url(work)}"
    assert clears[InboxKind.RELEASE] == f"Review it, then merge it (G3): {_url(release)}"
    assert clears[InboxKind.CLAIM] == f"devops roadmap release {claimed} --repo {REPO} --confirm"
    assert clears[InboxKind.LABELS] == f"devops gh labels sync --repo {REPO}"


def _url(number: int) -> str:
    return f"https://github.com/{REPO}/pull/{number}"


def test_a_stopped_item_shows_its_step_and_is_cleared_by_the_retry_comment(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(
        store, fields={ItemField.STATUS: "Blocked"}, marks={ImplementRecordKey.STOPPED: "group 2"}
    )
    (line,) = _lines(_read(store), InboxKind.BLOCKED)
    assert (line.number, "group 2" in line.subject, line.clear) == (
        number,
        True,
        f"Fix the cause, then comment `implement: retry` on #{number}.",
    )


def test_a_block_a_person_set_says_that_no_cause_is_recorded(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store, fields={ItemField.STATUS: "Blocked"})
    (line,) = _lines(_read(store), InboxKind.BLOCKED)
    assert ("no cause is recorded" in line.subject, number in {line.number}) == (True, True)


def test_the_blockers_that_refine_recorded_are_the_cause_of_a_block(
    store: InMemoryRoadmapStore,
) -> None:
    _item(
        store, fields={ItemField.STATUS: "Blocked"}, marks={RefineRecordKey.BLOCKED_BY: "#12, #13"}
    )
    (line,) = _lines(_read(store), InboxKind.BLOCKED)
    assert "#12, #13" in line.subject


def test_a_pull_request_on_the_branch_of_the_issue_keeps_a_claim_young(
    store: InMemoryRoadmapStore,
) -> None:
    claimed = _item(store, fields={ItemField.OWNER: "Agent"}, updated_at=_ago(days=10))
    store.seed_pull("work", head_ref=f"feat/{claimed}-work", draft=True, updated_at=_ago(days=1))
    assert _lines(_read(store), InboxKind.CLAIM) == []


def test_a_claim_with_no_activity_for_eight_days_is_old_and_shows_its_age(
    store: InMemoryRoadmapStore,
) -> None:
    claimed = _item(store, fields={ItemField.OWNER: "Human"}, updated_at=_ago(days=8))
    _item(store, fields={ItemField.OWNER: "Service"}, updated_at=_ago(days=6, hours=23))
    (line,) = _lines(_read(store), InboxKind.CLAIM)
    assert (line.number, line.age, "human" in line.subject) == (claimed, timedelta(days=8), True)


def test_a_pull_request_of_another_issue_does_not_keep_a_claim_young(
    store: InMemoryRoadmapStore,
) -> None:
    claimed = _item(store, fields={ItemField.OWNER: "Agent"}, updated_at=_ago(days=10))
    store.seed_pull("other", head_ref=f"feat/{claimed + 1}-other", updated_at=_ago(days=1))
    assert [line.number for line in _lines(_read(store), InboxKind.CLAIM)] == [claimed]


def test_the_pull_requests_of_people_are_listed_apart_and_a_draft_is_marked(
    store: InMemoryRoadmapStore,
) -> None:
    plan = store.seed_pull("plan", head_ref="feat/1-plan")
    _item(store, marks={StageRecordKey.PR: str(plan)})
    ready = store.seed_pull("mine, ready", head_ref="feat/3-mine", updated_at=_ago(days=1))
    draft = store.seed_pull("mine, draft", head_ref="fix/4-mine", draft=True)

    inbox = _read(store)

    assert [(line.number, line.kind) for line in inbox.jobs] == [(plan, InboxKind.PLAN)]
    assert [line.number for line in inbox.people] == [ready, draft]
    assert inbox.people[0].clear == f"Review it, then merge it (G2): {_url(ready)}"
    assert "draft" in inbox.people[1].subject
    assert inbox.people[1].clear == (
        f"Wait for the checks with `devops pr monitor {draft} --repo {REPO}`, "
        f"then run `devops pr ready {draft} --repo {REPO}`."
    )


def test_the_lines_of_one_kind_are_oldest_first(store: InMemoryRoadmapStore) -> None:
    newer = store.seed_pull("newer", head_ref="feat/1-a", updated_at=_ago(hours=1))
    older = store.seed_pull("older", head_ref="feat/2-b", updated_at=_ago(days=3))
    _item(store, marks={StageRecordKey.PR: str(newer)})
    _item(store, marks={StageRecordKey.PR: str(older)})
    assert [line.number for line in _read(store).jobs] == [older, newer]


def test_labels_that_differ_are_one_line_with_the_age_of_the_labels_file(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_file(
        CONST_ROADMAP_LABELS_PATH,
        "- name: type/bug\n  color: '000000'\n  description: A defect\n"
        "- name: scope/ci\n  color: 0E8A16\n",
    )
    store.seed_commit(CONST_ROADMAP_LABELS_PATH, at=_ago(days=4))
    (line,) = _lines(_read(store), InboxKind.LABELS)
    assert (line.number, line.age, "scope/ci" in line.subject, "type/bug" in line.subject) == (
        None,
        timedelta(days=4),
        True,
        True,
    )


def test_labels_in_step_with_the_file_give_no_line_and_no_commit_read(
    store: InMemoryRoadmapStore,
) -> None:
    assert _read(store) == Inbox(jobs=(), people=())


def test_a_repository_without_the_labels_file_fails_the_read_and_does_not_hide_it(
    store: InMemoryRoadmapStore,
) -> None:
    empty = InMemoryRoadmapStore(repo=REPO, clock=lambda: NOW)
    with pytest.raises(GitHubFileNotFoundError, match=r"no \.github/labels\.yml"):
        _read(empty)


def test_the_inbox_reads_open_work_only_writes_nothing_and_never_lists_every_issue(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    for name in ("issues", "items", "candidates", "backlog"):
        monkeypatch.setattr(store, name, lambda *a, _n=name, **k: calls.append(_n) or [])
    store.seed_pull("plan", head_ref="feat/1-plan")
    _read(store)
    assert (calls, store.job_writes()) == ([], [])


def test_the_rendered_inbox_names_each_section_with_its_lines(store: InMemoryRoadmapStore) -> None:
    plan = store.seed_pull("plan", head_ref="feat/1-plan", updated_at=_ago(days=1))
    _item(store, marks={StageRecordKey.PR: str(plan)})
    store.seed_pull("mine", head_ref="feat/3-mine")

    text = render_inbox(_read(store), repo=REPO)

    assert f"#{plan}" in text
    assert "Ready plan pull requests of the jobs (G1)" in text
    assert "Pull requests of people and agents" in text
    assert text.index("(G1)") < text.index("Pull requests of people and agents")
    assert "devops argo cd apps status devops" in text


def test_an_empty_inbox_says_that_nothing_waits(store: InMemoryRoadmapStore) -> None:
    assert render_inbox(_read(store), repo=REPO).startswith(
        f"Nothing waits for a person in {REPO}."
    )
