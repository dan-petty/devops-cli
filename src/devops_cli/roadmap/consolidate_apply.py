"""`devops roadmap consolidate --apply`: apply one accepted group from the latest plan (#3743)."""

from __future__ import annotations

from devops_cli.exceptions.validation import ValidationError as InvalidInputError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.consolidate import Group, Plan
from devops_cli.roadmap.consolidate_judge import Shape
from devops_cli.roadmap.stores.store import RoadmapStore


def group_of(plan: Plan, group_id: str) -> Group:
    """The group of id `group_id` in `plan`, or raise an invalid input error."""
    found = next((g for g in plan.groups if g.id == group_id), None)
    if found is None:
        raise InvalidInputError(
            MESSAGES.roadmap.consolidate_apply_unknown.format(group=group_id),
            field="apply",
        )
    return found


def _apply_merge(store: RoadmapStore, plan: Plan, group: Group) -> None:
    pass


def _apply_parent(store: RoadmapStore, plan: Plan, group: Group) -> None:
    pass


def _apply_close(store: RoadmapStore, plan: Plan, group: Group) -> None:
    pass


def _apply_link_only(store: RoadmapStore, plan: Plan, group: Group) -> None:
    pass


def apply_group(store: RoadmapStore, plan: Plan, group_id: str, *, confirm: bool) -> None:
    """Apply one group from `plan` to `store` when `confirm` is true."""
    if not confirm:
        raise InvalidInputError(
            MESSAGES.roadmap.consolidate_apply_needs_confirm,
            field="confirm",
        )
    group = group_of(plan, group_id)
    match group.shape:
        case Shape.MERGE:
            _apply_merge(store, plan, group)
        case Shape.PARENT:
            _apply_parent(store, plan, group)
        case Shape.CLOSE:
            _apply_close(store, plan, group)
        case Shape.LINK_ONLY:
            _apply_link_only(store, plan, group)


__all__ = [
    "apply_group",
    "group_of",
]
