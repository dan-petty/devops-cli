"""Tests for `devops roadmap consolidate --apply` (#3743)."""

from __future__ import annotations

from datetime import date

import pytest

from devops_cli.exceptions.validation import ValidationError as InvalidInputError
from devops_cli.roadmap.consolidate import Group, GroupMember, PendingClose, Plan
from devops_cli.roadmap.consolidate_apply import apply_group
from devops_cli.roadmap.consolidate_judge import Refutation, Shape
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
