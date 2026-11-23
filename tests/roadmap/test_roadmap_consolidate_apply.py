"""Tests for `devops roadmap consolidate --apply` (#3743)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from devops_cli.exceptions.validation import ValidationError as InvalidInputError
from devops_cli.roadmap.consolidate import Group, GroupMember, PendingClose, Plan
from devops_cli.roadmap.consolidate_apply import apply_group
from devops_cli.roadmap.consolidate_judge import Action, Refutation, Shape
from devops_cli.roadmap.stores.store import CloseReason, GitHubState
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore


def make_group(
    id: str = "g1",
    anchor: int = 10,
    shape: Shape = Shape.MERGE,
    members: tuple[GroupMember, ...] = (),
    root_cause: str = "Shared root cause.",
    theme: str = "A common theme.",
) -> Group:
    return Group(
        id=id,
        anchor=anchor,
        shape=shape,
        theme=theme,
        root_cause=root_cause,
        members=members,
        consistency_gained="Consistency.",
        confidence=0.9,
        verdict=Refutation.KEPT,
    )


def make_plan(
    repo: str = "example/roadmap",
    groups: tuple[Group, ...] = (),
    pending_closes: tuple[PendingClose, ...] = (),
) -> Plan:
    return Plan(
        repo=repo,
        day=date(2026, 11, 23),
        groups=groups,
        pending_closes=pending_closes,
    )


def test_apply_without_confirm_writes_nothing() -> None:
    store = InMemoryRoadmapStore()
    group = make_group("g1")
    plan = make_plan(groups=(group,))

    with pytest.raises(InvalidInputError, match="--confirm"):
        apply_group(store, plan, "g1", confirm=False)

    assert store.writes == []


def test_unknown_group_id_writes_nothing() -> None:
    store = InMemoryRoadmapStore()
    group = make_group("g1")
    plan = make_plan(groups=(group,))

    with pytest.raises(InvalidInputError, match="g9"):
        apply_group(store, plan, "g9", confirm=True)

    assert store.writes == []


def test_generated_command_docs_name_the_apply_option() -> None:
    doc = Path("docs/commands/roadmap.md").read_text(encoding="utf-8")
    assert "--apply" in doc


def test_merge_section_is_marked_and_text_outside_stays() -> None:
    store = InMemoryRoadmapStore()
    anchor_body = "## Overview\n\nAnchor description.\n"
    anchor = store.seed_issue("Anchor", body=anchor_body)
    m1 = store.seed_issue("Member 1", body="## Overview\n\nM1\n")
    m2 = store.seed_issue("Member 2", body="## Overview\n\nM2\n")

    group = make_group(
        "g1",
        anchor=anchor,
        shape=Shape.MERGE,
        members=(
            GroupMember(number=m1, action=Action.MERGE, reason="Duplicate parser logic."),
            GroupMember(number=m2, action=Action.MERGE, reason="Duplicate parser logic."),
        ),
    )
    plan = make_plan(groups=(group,))

    apply_group(store, plan, "g1", confirm=True)

    body = store.read_issue_body(anchor)
    assert "<!-- devops-roadmap-consolidate:start -->" in body
    assert "<!-- devops-roadmap-consolidate:end -->" in body
    assert f"## Consolidated from #{m1}, #{m2}" in body
    assert body.startswith(anchor_body)


def test_copied_member_sections_and_root_cause() -> None:
    store = InMemoryRoadmapStore()
    anchor = store.seed_issue("Anchor", body="Anchor body.\n")
    m1_body = (
        "## Problem\n\nSome problem.\n\n"
        "## Acceptance criteria\n\n- The job keeps every comment.\n\n"
        "## Key questions\n\n- Why was it dropped?\n"
    )
    m1 = store.seed_issue("Member 1", body=m1_body)

    group = make_group(
        "g1",
        anchor=anchor,
        shape=Shape.MERGE,
        root_cause="Shared parser bug in ast.py.",
        members=(GroupMember(number=m1, action=Action.MERGE, reason="Same root cause."),),
    )
    plan = make_plan(groups=(group,))

    apply_group(store, plan, "g1", confirm=True)

    body = store.read_issue_body(anchor)
    assert "Shared parser bug in ast.py." in body
    assert "## Acceptance criteria\n\n- The job keeps every comment." in body
    assert "## Key questions\n\n- Why was it dropped?" in body


def test_each_member_is_closed_as_not_planned() -> None:
    store = InMemoryRoadmapStore()
    anchor = store.seed_issue("Anchor", body="Anchor body.\n")
    m1 = store.seed_issue("Member 1", body="M1 body.\n")
    m2 = store.seed_issue("Member 2", body="M2 body.\n")

    group = make_group(
        "g1",
        anchor=anchor,
        shape=Shape.MERGE,
        members=(
            GroupMember(number=m1, action=Action.MERGE, reason="Redundant with anchor."),
            GroupMember(number=m2, action=Action.MERGE, reason="Part of same work."),
        ),
    )
    plan = make_plan(groups=(group,))

    apply_group(store, plan, "g1", confirm=True)

    item1 = store.issue(m1)
    item2 = store.issue(m2)
    assert item1 is not None
    assert item1.state == GitHubState.CLOSED
    assert item2 is not None
    assert item2.state == GitHubState.CLOSED
    assert item1.state_reason == CloseReason.NOT_PLANNED.value
    assert item2.state_reason == CloseReason.NOT_PLANNED.value

    comments1 = store.comments_on(m1)
    assert len(comments1) == 1
    assert comments1[0].body.startswith(f"Merged into #{anchor}:")

    comments2 = store.comments_on(m2)
    assert len(comments2) == 1
    assert comments2[0].body.startswith(f"Merged into #{anchor}:")


def test_second_apply_replaces_the_section() -> None:
    store = InMemoryRoadmapStore()
    anchor_prefix = "Anchor overview.\n\n"
    anchor = store.seed_issue("Anchor", body=anchor_prefix)
    m1 = store.seed_issue("Member 1", body="M1 body.\n")

    group = make_group(
        "g1",
        anchor=anchor,
        shape=Shape.MERGE,
        root_cause="Initial cause.",
        members=(GroupMember(number=m1, action=Action.MERGE, reason="Same work."),),
    )
    plan1 = make_plan(groups=(group,))
    apply_group(store, plan1, "g1", confirm=True)

    group2 = make_group(
        "g1",
        anchor=anchor,
        shape=Shape.MERGE,
        root_cause="Updated cause.",
        members=(GroupMember(number=m1, action=Action.MERGE, reason="Same work."),),
    )
    store.reopen_issue(m1)
    plan2 = make_plan(groups=(group2,))
    apply_group(store, plan2, "g1", confirm=True)

    body = store.read_issue_body(anchor)
    assert body.count("<!-- devops-roadmap-consolidate:start -->") == 1
    assert body.count("<!-- devops-roadmap-consolidate:end -->") == 1
    assert "Updated cause." in body
    assert "Initial cause." not in body
    assert body.startswith(anchor_prefix)
