"""Refine selects edited or commented Ready items again (#6452)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import time_machine

from devops_cli.config.constants import (
    CONST_ROADMAP_ACTIONS_BOT_LOGIN,
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
    CONST_ROADMAP_REFINE_COMMENT_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.roadmap.body_hash import body_hashes, extract_section_and_outside
from devops_cli.roadmap.refine.refine import select_candidates
from devops_cli.roadmap.stores.store import IssueComment, ItemField, RefineRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    READY,
    blocked_by_issue,
    refine_round,
    require_item,
    seed_item,
)

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store")

_T0 = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
_SECTION = (
    f"{CONST_ROADMAP_REFINE_START_MARKER}\n"
    "## Proposed design\n\n"
    "### Dependencies\nNone.\n"
    f"{CONST_ROADMAP_REFINE_END_MARKER}"
)


def _seed_refined_ready(
    store: InMemoryRoadmapStore,
    *,
    author_login: str | None = "alice",
    author_association: str | None = "OWNER",
    repeated_at: datetime | None = None,
) -> int:
    """An open refined Ready item with matching refine hashes and a refine marker comment at `_T0`."""
    store.seed_visibility(is_private=True)
    with time_machine.travel(_T0, tick=False):
        number = store.seed_issue(
            "feat(roadmap): ready item",
            body=f"Original scope.\n\n{_SECTION}",
            fields={ItemField.STATUS: CONST_ROADMAP_STATUS_READY, ItemField.PRIORITY: "P2-Medium"},
            author_login=author_login,
            author_association=author_association,
        )
        store.set_field(require_item(store, number), ItemField.STATUS, CONST_ROADMAP_STATUS_READY)
        item = require_item(store, number)
        body_hash, section_hash = body_hashes(item.body)
        marks: dict[RefineRecordKey, str | None] = {
            RefineRecordKey.BODY_HASH: body_hash,
            RefineRecordKey.SECTION_HASH: section_hash,
            RefineRecordKey.NEXT_STEP: "ready",
        }
        if repeated_at is not None:
            marks[RefineRecordKey.REPEATED_AT] = repeated_at.isoformat()
        store.set_marks(item, marks)
        store.seed_comment(number, f"{CONST_ROADMAP_REFINE_COMMENT_MARKER}\nNext step: ready.")
    return number


def test_refinable_takes_ready_item_edited_outside_refine_section(
    store: InMemoryRoadmapStore,
) -> None:
    number = _seed_refined_ready(store)
    store.as_actor("alice").write_issue_body(number, f"Updated scope.\n\n{_SECTION}")

    selected, _ = select_candidates(store)

    assert [it.number for it in selected] == [number]


@pytest.mark.parametrize("use_repeated_at", [False, True], ids=["refine-comment", "repeated-at"])
def test_refinable_takes_ready_item_with_trusted_comment_after_last_round(
    store: InMemoryRoadmapStore, use_repeated_at: bool
) -> None:
    repeated = _T0 + timedelta(minutes=10) if use_repeated_at else None
    number = _seed_refined_ready(store, repeated_at=repeated)
    comment_at = (repeated or _T0) + timedelta(minutes=5)
    with time_machine.travel(comment_at, tick=False):
        store.seed_comment(
            number,
            "Depends on #99 now.",
            author_association="OWNER",
            author_login="alice",
        )

    selected, _ = select_candidates(store)

    assert [it.number for it in selected] == [number]


@pytest.mark.parametrize(
    ("association", "login"),
    [
        ("CONTRIBUTOR", CONST_ROADMAP_ACTIONS_BOT_LOGIN),
        ("OWNER", "helper[bot]"),
        ("NONE", "stranger"),
    ],
    ids=["actions-bot", "owner-bot", "stranger"],
)
def test_refinable_skips_ready_item_with_bot_or_untrusted_comment(
    store: InMemoryRoadmapStore, association: str, login: str
) -> None:
    number = _seed_refined_ready(store)
    with time_machine.travel(_T0 + timedelta(minutes=5), tick=False):
        store.seed_comment(
            number,
            "Automated notice.",
            author_association=association,
            author_login=login,
        )

    selected, _ = select_candidates(store)

    assert selected == []


def test_refinable_skips_unchanged_ready_item_with_no_comment_after_last_round(
    store: InMemoryRoadmapStore,
) -> None:
    repeated = _T0 + timedelta(minutes=10)
    number = _seed_refined_ready(store, repeated_at=repeated)
    with time_machine.travel(_T0 + timedelta(minutes=5), tick=False):
        store.seed_comment(
            number,
            "Comment before repeated_at.",
            author_association="OWNER",
            author_login="alice",
        )

    selected, _ = select_candidates(store)

    assert selected == []


def test_refine_section_write_does_not_change_outside_body_hash() -> None:
    body = "Initial problem.\n\nDetails."
    before, _ = body_hashes(body)
    updated = f"Initial problem.\n\nDetails.\n\n{_SECTION}"
    after, section_hash = body_hashes(updated)

    assert (before, after) == (before, before)
    assert section_hash is not None


def test_round_keeps_edited_ready_item_ready_and_updates_body_hash(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P2-Medium", body="Original scope.")
    model_fake.answer(READY, READY)
    refine_round(store, git_repo)

    store.as_actor("alice").write_issue_body(
        number,
        require_item(store, number).body.replace(
            "Original scope.", "Edited scope outside section."
        ),
    )

    second = refine_round(store, git_repo)

    updated = require_item(store, number)
    assert [r.item.number for r in second.refined_items] == [number]
    assert updated.status == CONST_ROADMAP_STATUS_READY
    assert updated.job_record.get(RefineRecordKey.BODY_HASH) == body_hashes(updated.body)[0]


def test_edited_ready_item_with_open_blocker_returns_to_new(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    blocker = seed_item(store, "In Progress", "P1-High")
    number = seed_item(store, "New", "P2-Medium", body="Original scope.")
    model_fake.answer(READY, blocked_by_issue(blocker))
    refine_round(store, git_repo)
    assert require_item(store, number).status == CONST_ROADMAP_STATUS_READY

    outside, _ = extract_section_and_outside(require_item(store, number).body)
    new_body = require_item(store, number).body.replace(
        outside.strip(), "Updated scope mentioning dependency."
    )
    store.as_actor("alice").write_issue_body(number, new_body)

    refine_round(store, git_repo)

    updated = require_item(store, number)
    _, section = extract_section_and_outside(updated.body)
    assert updated.status == "New"
    assert updated.job_record.get(RefineRecordKey.BLOCKED_BY) == str(blocker)
    assert section is not None
    assert f"#{blocker}" in section


def test_commented_ready_item_with_open_blocker_returns_to_new(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    blocker = seed_item(store, "In Progress", "P1-High")
    number = seed_item(store, "New", "P2-Medium", body="Original scope.")
    model_fake.answer(READY, blocked_by_issue(blocker))
    with time_machine.travel(_T0, tick=False) as clock:
        refine_round(store, git_repo)
        clock.shift(timedelta(minutes=5))
        store.as_actor("alice").comment(number, f"This now depends on #{blocker}.")
        clock.shift(timedelta(minutes=5))
        refine_round(store, git_repo)

    updated = require_item(store, number)
    _, section = extract_section_and_outside(updated.body)
    assert updated.status == "New"
    assert updated.job_record.get(RefineRecordKey.BLOCKED_BY) == str(blocker)
    assert section is not None
    assert f"#{blocker}" in section


def test_bot_filed_ready_item_with_trusted_comment_is_refinable(
    store: InMemoryRoadmapStore,
) -> None:
    number = _seed_refined_ready(
        store,
        author_login=CONST_ROADMAP_ACTIONS_BOT_LOGIN,
        author_association="CONTRIBUTOR",
    )
    with time_machine.travel(_T0 + timedelta(minutes=5), tick=False):
        store.seed_comment(
            number,
            "Depends on #77 now.",
            author_association="OWNER",
            author_login="alice",
        )
    item = require_item(store, number)
    store.set_marks(item, {RefineRecordKey.JUDGE: "approved"})

    selected, _ = select_candidates(store)

    assert [it.number for it in selected] == [number]


def test_unchanged_ready_item_with_zero_comments_reads_no_comments(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_item(store, CONST_ROADMAP_STATUS_READY, "P2-Medium", refined=True)
    reads: list[int] = []
    original = store.comments_on

    def counted(issue_number: int) -> list[IssueComment]:
        reads.append(issue_number)
        return original(issue_number)

    monkeypatch.setattr(store, "comments_on", counted)
    selected, _ = select_candidates(store)

    assert (selected, [n for n in reads if n == number]) == ([], [])


def test_job_marker_comment_after_last_round_does_not_reselect_ready_item(
    store: InMemoryRoadmapStore,
) -> None:
    number = _seed_refined_ready(store)
    with time_machine.travel(_T0 + timedelta(minutes=5), tick=False):
        store.comment(number, f"{CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER}\nNo tool covers.")
    selected, _ = select_candidates(store)

    assert selected == []
