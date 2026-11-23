"""`devops roadmap consolidate --apply`: apply one accepted group from the latest plan (#3743)."""

from __future__ import annotations

import re

from devops_cli.exceptions.validation import ValidationError as InvalidInputError
from devops_cli.lang import MESSAGES
from devops_cli.output.console import print_info
from devops_cli.roadmap.consolidate import Group, Plan
from devops_cli.roadmap.consolidate_judge import Shape
from devops_cli.roadmap.stores.store import CloseReason, GitHubState, RoadmapStore

CONSOLIDATE_SECTION_START = "<!-- devops-roadmap-consolidate:start -->"
CONSOLIDATE_SECTION_END = "<!-- devops-roadmap-consolidate:end -->"


def group_of(plan: Plan, group_id: str) -> Group:
    """The group of id `group_id` in `plan`, or raise an invalid input error."""
    found = next((g for g in plan.groups if g.id == group_id), None)
    if found is None:
        raise InvalidInputError(
            MESSAGES.roadmap.consolidate_apply_unknown.format(group=group_id),
            field="apply",
        )
    return found


def _extract_section(body: str, title: str) -> str | None:
    lines = body.splitlines(keepends=True)
    pattern = re.compile(rf"^(#+)\s+{re.escape(title)}\s*$", re.IGNORECASE)
    start_idx: int | None = None
    level = 0
    end_idx: int | None = None

    for i, line in enumerate(lines):
        if start_idx is None:
            m = pattern.match(line.rstrip("\r\n"))
            if m:
                start_idx = i
                level = len(m.group(1))
        else:
            m = re.match(r"^(#+)\s+\S", line)
            if m and len(m.group(1)) <= level:
                end_idx = i
                break

    if start_idx is None:
        return None
    if end_idx is None:
        end_idx = len(lines)

    return "".join(lines[start_idx:end_idx]).strip()


def _format_merge_section(group: Group, member_bodies: list[tuple[int, str]]) -> str:
    members_str = ", ".join(f"#{m.number}" for m in group.members)
    parts = [
        CONSOLIDATE_SECTION_START,
        f"## Consolidated from {members_str}",
        "",
        group.root_cause,
    ]
    for _num, body in member_bodies:
        criteria = _extract_section(body, "Acceptance criteria")
        if criteria:
            parts.extend(["", criteria])
        questions = _extract_section(body, "Key questions")
        if questions:
            parts.extend(["", questions])
    parts.extend(["", CONSOLIDATE_SECTION_END])
    return "\n".join(parts)


def _apply_merge(store: RoadmapStore, plan: Plan, group: Group) -> None:
    anchor_body = store.read_issue_body(group.anchor)
    member_bodies = [(m.number, store.read_issue_body(m.number)) for m in group.members]
    marked_section = _format_merge_section(group, member_bodies)

    if CONSOLIDATE_SECTION_START in anchor_body and CONSOLIDATE_SECTION_END in anchor_body:
        start_pos = anchor_body.index(CONSOLIDATE_SECTION_START)
        end_pos = anchor_body.index(CONSOLIDATE_SECTION_END) + len(CONSOLIDATE_SECTION_END)
        new_body = f"{anchor_body[:start_pos]}{marked_section}{anchor_body[end_pos:]}"
    else:
        if anchor_body and not anchor_body.endswith("\n"):
            prefix = f"{anchor_body}\n\n"
        elif anchor_body and not anchor_body.endswith("\n\n"):
            prefix = f"{anchor_body}\n"
        else:
            prefix = anchor_body
        new_body = f"{prefix}{marked_section}\n"

    store.write_issue_body(group.anchor, new_body)

    for member in group.members:
        comment = f"Merged into #{group.anchor}: {member.reason}"
        store.close(member.number, CloseReason.NOT_PLANNED, comment=comment)


def _apply_parent(store: RoadmapStore, plan: Plan, group: Group) -> None:
    anchor_issue = store.issue(group.anchor)
    anchor_has_milestone = anchor_issue is not None and bool(anchor_issue.milestone)

    for member in group.members:
        child_issue = store.issue(member.number)
        child_has_milestone = child_issue is not None and bool(child_issue.milestone)
        if anchor_has_milestone:
            store.add_blocked_by(member.number, group.anchor)
        elif not child_has_milestone:
            store.add_sub_issue(group.anchor, member.number)

    lines = ["Consolidated parent task with children in order:"]
    for member in group.members:
        lines.append(f"- #{member.number}")
    store.comment(group.anchor, "\n".join(lines))


def _apply_close(store: RoadmapStore, plan: Plan, group: Group) -> None:
    anchor_issue = store.issue(group.anchor)
    is_completed = (
        anchor_issue is not None
        and anchor_issue.state == GitHubState.CLOSED
        and anchor_issue.state_reason == CloseReason.COMPLETED.value
    )
    if not is_completed:
        print_info(
            MESSAGES.roadmap.consolidate_duplicate_waits.format(group=group.id, anchor=group.anchor)
        )
        return

    comment = f"Duplicate of #{group.anchor}."
    for member in group.members:
        store.close(member.number, CloseReason.DUPLICATE, comment=comment)


def _apply_link_only(store: RoadmapStore, plan: Plan, group: Group) -> None:
    comment = MESSAGES.roadmap.consolidate_link_comment.format(anchor=group.anchor)
    for member in group.members:
        store.comment(member.number, comment)


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
