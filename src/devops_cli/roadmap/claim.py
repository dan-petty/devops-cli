"""The claim of a roadmap Item (#2910, ADR 0016): who works on it now.

One label of the family `owner/service`, `owner/agent`, `owner/human` claims an Item, and an
Item has at most one. Any actor may claim a free Item. A claim of an Item that another owner
holds is refused, except that a person's claim takes an Item from the Service: a person's claim
beats the Service's. The Service takes no Item that an agent or a person holds. A release
clears the label, whoever holds it. No job releases the claim of an agent or a person.

The label is the Owner field of the store, so a claim is a field write: it replaces the family,
the job record names the owner it set, and the write raises `RoadmapItemChangedError` when
someone changed the owner after the read (ADR 0002). A person who adds an `owner/*` label on
GitHub by hand is also a claim, and it wins over the label that a job set.

`plan_claim` and `apply_claim` serve `devops roadmap claim` and `devops roadmap release`. The
Service claims with `service_claim` and releases with `service_release`; `claim_as_agent` serves
`devops repos worktrees add`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from devops_cli.config.constants import (
    CONST_ROADMAP_OWNER_AGENT,
    CONST_ROADMAP_OWNER_HUMAN,
    CONST_ROADMAP_OWNER_SERVICE,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.exceptions.roadmap import RoadmapClaimError, RoadmapItemChangedError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.request_plan import StoreRequests
from devops_cli.roadmap.store import Item, ItemField, RoadmapStore


class Claimant(StrEnum):
    """Who claims by hand: an agentic coder, or a person. The Service claims with
    `service_claim`, never by this name."""

    AGENT = "agent"
    HUMAN = "human"


_OWNER: Final[Mapping[Claimant, str]] = {
    Claimant.AGENT: CONST_ROADMAP_OWNER_AGENT,
    Claimant.HUMAN: CONST_ROADMAP_OWNER_HUMAN,
}


@dataclass(frozen=True)
class ClaimPlan:
    """A claim or a release: the Item, its owner now, and the owner it gets (None for a release)."""

    number: int
    title: str
    repo: str
    current: str | None
    target: str | None


def claimed_by(item: Item) -> str | None:
    """The owner, in lower case, that holds `item` against the Service: `agent` or `human`. The
    Service's own claim holds nothing against its jobs, so it gives None."""
    if item.owner is None or item.owner == CONST_ROADMAP_OWNER_SERVICE:
        return None
    return item.owner.lower()


def _item(store: RoadmapStore, number: int) -> Item:
    found = store.item(number)
    if found is None:
        raise RoadmapClaimError(MESSAGES.roadmap.claim_not_item.format(number=number))
    return found


def _allowed(item: Item, target: str | None) -> bool:
    """Whether `target` may own `item`: a release, a free Item, the owner that holds it, or a
    person taking the Item from the Service."""
    current = item.owner
    if target is None or current is None or current == target:
        return True
    return current == CONST_ROADMAP_OWNER_SERVICE and target == CONST_ROADMAP_OWNER_HUMAN


def _require_allowed(item: Item, target: str | None) -> None:
    if _allowed(item, target):
        return
    owner = (item.owner or "").lower()
    raise RoadmapClaimError(
        MESSAGES.roadmap.claim_held.format(number=item.number, owner=owner),
        owner=owner,
        details={"item": item.number},
    )


def plan_claim(store: RoadmapStore, number: int, claimant: Claimant | None, repo: str) -> ClaimPlan:
    """The plan to claim Item `number` as `claimant`, or to release it when `claimant` is None.
    Raises `RoadmapClaimError` when the issue is no Item or another owner holds it."""
    item = _item(store, number)
    target = None if claimant is None else _OWNER[claimant]
    _require_allowed(item, target)
    return ClaimPlan(number, item.title, repo, item.owner, target)


def apply_claim(store: RoadmapStore, plan: ClaimPlan) -> bool:
    """Write the plan. The Item is read again and judged again, so a claim made after the plan is
    refused and never reverted. True when a label was written, False when the Item had the owner
    already."""
    item = _item(store, plan.number)
    _require_allowed(item, plan.target)
    if item.owner == plan.target:
        return False
    store.set_field(item, ItemField.OWNER, plan.target)
    return True


def render_claim_plan(plan: ClaimPlan) -> str:
    """The plan as the report of the command."""
    none = MESSAGES.roadmap.claim_no_owner
    return MESSAGES.roadmap.claim_plan.format(
        number=plan.number,
        title=plan.title,
        current=plan.current or none,
        target=plan.target or none,
    )


def dry_run_claim(repo: str, number: int) -> tuple[list[PlannedRequest], list[PlannedRequest]]:
    """The requests of a claim or a release, in order: the reads, and the writes that
    `--confirm` adds."""
    requests = StoreRequests(repo)
    subject = f"#{number}"
    reads = [*requests.issue(subject)]
    writes = [*requests.set_field(subject, field_name=ItemField.OWNER.value)]
    return reads, writes


def claim_as_agent(repo: str, number: int) -> str | None:
    """Claim issue `number` of `repo` for an agent, as `devops repos worktrees add` does after it
    makes a worktree. The work does not wait for the label, so a claim that fails gives the
    reason, in a sentence, and raises nothing; None when the Item is claimed."""
    try:
        store = roadmap_store.get_roadmap_store(repo)
        apply_claim(store, plan_claim(store, number, Claimant.AGENT, repo))
    except DevOpsCLIError as exc:
        return str(exc)
    return None


def claim_request_lines(repo: str, number: int) -> list[str]:
    """The requests of `claim_as_agent`, one line each, for the dry run of a worktree."""
    reads, writes = dry_run_claim(repo, number)
    return [request.line() for request in (*reads, *writes)]


def service_claim(store: RoadmapStore, number: int, marks: Mapping[Any, str | None]) -> bool:
    """Set `owner/service` and `marks` in one write. False, with nothing written, when an agent or
    a person holds the Item now or claimed it since the read: the Service takes no claimed Item."""
    item = _item(store, number)
    if claimed_by(item) is not None:
        return False
    try:
        store.set_field(item, ItemField.OWNER, CONST_ROADMAP_OWNER_SERVICE, marks=marks)
    except RoadmapItemChangedError:
        return False
    return True


def service_release(store: RoadmapStore, number: int, marks: Mapping[Any, str | None]) -> None:
    """Clear `owner/service` and set `marks`, in one write. The claim of an agent or a person
    stays: only `marks` are written then, and a label `owner/service` that a person's label stands
    beside goes. A person's claim between the read and the write ends the release: `marks` are
    written and the owner is left as the person set it."""
    item = _item(store, number)
    try:
        if item.owner is not None:
            kept = None if item.owner == CONST_ROADMAP_OWNER_SERVICE else item.owner
            store.set_field(item, ItemField.OWNER, kept, marks=marks)
            return
    except RoadmapItemChangedError:
        item = _item(store, number)
    store.set_marks(item, marks)


__all__ = [
    "ClaimPlan",
    "Claimant",
    "apply_claim",
    "claim_as_agent",
    "claim_request_lines",
    "claimed_by",
    "dry_run_claim",
    "plan_claim",
    "render_claim_plan",
    "service_claim",
    "service_release",
]
